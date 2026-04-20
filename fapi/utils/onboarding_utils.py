from datetime import datetime, timedelta
from typing import Any, Dict, List
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import HTTPException
from sqlalchemy.orm import Session

from fapi.db import models


MAX_ID_UPLOAD_CANCELLATIONS = int(os.getenv("MAX_ID_UPLOAD_CANCELLATIONS", "10"))


def _normalized_email(email: str) -> str:
    return (email or "").strip().lower()


def _send_email(to_emails: List[str], subject: str, body_html: str) -> None:
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    if not smtp_user or not smtp_password or not to_emails:
        return

    message = MIMEMultipart("alternative")
    message["From"] = smtp_user
    message["To"] = ", ".join(to_emails)
    message["Subject"] = subject
    message.attach(MIMEText(body_html, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, to_emails, message.as_string())


def _compute_basic_info_missing_fields(payload: Dict[str, Any]) -> List[str]:
    required = {
        "full_name": payload.get("full_name"),
        "phone": payload.get("phone"),
        "email": payload.get("email"),
        "linkedin_url": payload.get("linkedin_url"),
        "emergency_contact_name": payload.get("emergency_contact_name"),
        "emergency_contact_email": payload.get("emergency_contact_email"),
        "emergency_contact_phone": payload.get("emergency_contact_phone"),
        "emergency_contact_address": payload.get("emergency_contact_address"),
        "resume_text": payload.get("resume_text"),
    }
    return [k for k, v in required.items() if not isinstance(v, str) or not v.strip()]


def _sync_completion(state: models.OnboardingStateORM) -> None:
    agreements_done = bool(state.enrollment_terms_signed and state.placement_terms_signed)
    state.agreements_completed = agreements_done
    if agreements_done and not state.agreements_completed_at:
        state.agreements_completed_at = datetime.utcnow()

    completed = bool(
        state.basic_info_validated
        and state.id_upload_completed
        and state.id_upload_verified
        and agreements_done
    )
    state.onboarding_completed = completed
    if completed and not state.onboarding_completed_at:
        state.onboarding_completed_at = datetime.utcnow()
    if not completed:
        state.onboarding_completed_at = None


def get_or_create_onboarding_state(db: Session, email: str, authuser_id: int | None = None) -> models.OnboardingStateORM:
    email = _normalized_email(email)
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    state = db.query(models.OnboardingStateORM).filter(models.OnboardingStateORM.email == email).first()
    if state:
        if authuser_id and not state.authuser_id:
            state.authuser_id = authuser_id
            db.commit()
            db.refresh(state)
        return state

    state = models.OnboardingStateORM(email=email, authuser_id=authuser_id)
    db.add(state)
    db.commit()
    db.refresh(state)
    return state


def onboarding_status_payload(state: models.OnboardingStateORM) -> Dict[str, Any]:
    can_cancel_id_upload = state.id_upload_cancel_count < MAX_ID_UPLOAD_CANCELLATIONS

    if not state.basic_info_validated:
        next_step = "basic_information"
    elif not state.id_upload_completed or state.id_upload_rejected:
        next_step = "id_upload"
    elif not state.id_upload_verified:
        next_step = "id_verification_pending"
    elif not state.agreements_completed:
        next_step = "agreements"
    else:
        next_step = "completed"

    return {
        "basic_info_validated": state.basic_info_validated,
        "id_upload_completed": state.id_upload_completed,
        "id_upload_verified": state.id_upload_verified,
        "id_upload_rejected": state.id_upload_rejected,
        "id_upload_cancel_count": state.id_upload_cancel_count,
        "max_id_upload_cancellations": MAX_ID_UPLOAD_CANCELLATIONS,
        "can_cancel_id_upload": can_cancel_id_upload,
        "enrollment_terms_signed": state.enrollment_terms_signed,
        "placement_terms_signed": state.placement_terms_signed,
        "agreements_completed": state.agreements_completed,
        "onboarding_completed": state.onboarding_completed,
        "next_step": next_step,
    }


def validate_basic_info(db: Session, email: str, payload: Dict[str, Any], authuser_id: int | None = None) -> Dict[str, Any]:
    state = get_or_create_onboarding_state(db, email, authuser_id)
    missing_fields = _compute_basic_info_missing_fields(payload)

    if missing_fields:
        return {
            "success": False,
            "message": "You entered something incorrectly. Please copy and paste your original resume text here.",
            "missing_fields": missing_fields,
            "status": onboarding_status_payload(state),
        }

    state.basic_info_validated = True
    state.basic_info_completed_at = datetime.utcnow()
    _sync_completion(state)
    db.commit()
    db.refresh(state)
    return {
        "success": True,
        "message": "Thank you. Basic information wizard is completed.",
        "status": onboarding_status_payload(state),
    }


def increment_id_upload_cancel(db: Session, email: str, authuser_id: int | None = None) -> Dict[str, Any]:
    state = get_or_create_onboarding_state(db, email, authuser_id)
    if state.id_upload_cancel_count >= MAX_ID_UPLOAD_CANCELLATIONS:
        raise HTTPException(status_code=403, detail="ID upload is now mandatory and cannot be cancelled.")

    state.id_upload_cancel_count += 1
    db.commit()
    db.refresh(state)
    return onboarding_status_payload(state)


def mark_id_uploaded(db: Session, email: str, authuser_id: int | None = None) -> Dict[str, Any]:
    state = get_or_create_onboarding_state(db, email, authuser_id)
    state.id_upload_completed = True
    state.id_upload_rejected = False
    state.id_upload_verified = False
    state.id_uploaded_at = datetime.utcnow()
    _sync_completion(state)
    db.commit()
    db.refresh(state)

    _send_email(
        [state.email],
        "ID upload received",
        "<p>Your ID was uploaded successfully and is under review.</p>",
    )
    return onboarding_status_payload(state)


def set_id_verification_status(db: Session, email: str, verified: bool, authuser_id: int | None = None) -> Dict[str, Any]:
    state = get_or_create_onboarding_state(db, email, authuser_id)
    if verified:
        state.id_upload_verified = True
        state.id_upload_rejected = False
        state.id_verified_at = datetime.utcnow()
    else:
        state.id_upload_verified = False
        state.id_upload_rejected = True
        state.id_rejected_at = datetime.utcnow()
    _sync_completion(state)
    db.commit()
    db.refresh(state)
    return onboarding_status_payload(state)


def sign_agreement(db: Session, email: str, agreement_type: str, authuser_id: int | None = None) -> Dict[str, Any]:
    state = get_or_create_onboarding_state(db, email, authuser_id)
    normalized = (agreement_type or "").strip().lower()
    if normalized not in {"enrollment", "placement"}:
        raise HTTPException(status_code=400, detail="agreement_type must be 'enrollment' or 'placement'")

    if normalized == "enrollment":
        state.enrollment_terms_signed = True
    else:
        state.placement_terms_signed = True
    _sync_completion(state)
    db.commit()
    db.refresh(state)
    return onboarding_status_payload(state)


def trigger_id_verification_reminder_if_needed(db: Session, email: str, authuser_id: int | None = None) -> None:
    state = get_or_create_onboarding_state(db, email, authuser_id)
    if not state.id_upload_completed or state.id_upload_verified:
        return
    if not state.id_uploaded_at:
        return

    age = datetime.utcnow() - state.id_uploaded_at
    if age < timedelta(days=10):
        return
    if state.id_verification_reminder_sent_at is not None:
        return

    admin_emails_env = os.getenv("TO_ADMIN_EMAIL", "")
    recruiting_emails_env = os.getenv("TO_RECRUITING_EMAIL", "")
    recipients = []
    for raw in [admin_emails_env, recruiting_emails_env]:
        for email_addr in raw.split(","):
            cleaned = email_addr.strip()
            if cleaned:
                recipients.append(cleaned)
    recipients = sorted(set(recipients))

    _send_email(
        recipients,
        "ID verification pending for candidate",
        f"<p>Please verify the ID for candidate: <b>{state.email}</b>.</p>",
    )
    state.id_verification_reminder_sent_at = datetime.utcnow()
    db.commit()
