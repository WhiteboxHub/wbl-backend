from __future__ import annotations

import os
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Optional

from sqlalchemy.orm import Session

from fpdf import FPDF
from fapi.db import models
from fapi.mail import approval_mail


ID_CANCEL_LIMIT = int(os.getenv("ID_CANCEL_LIMIT", "10"))
ID_VERIFICATION_REMINDER_DAYS = int(os.getenv("ID_VERIFICATION_REMINDER_DAYS", "10"))


def _utcnow() -> datetime:
    return datetime.utcnow()


def _normalize_email(email: Optional[str]) -> Optional[str]:
    if not isinstance(email, str):
        return None
    value = email.strip().lower()
    return value or None


def _send_email(to_email: str, subject: str, body: str) -> None:
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not smtp_user or not smtp_password:
        return

    message = MIMEMultipart("alternative")
    message["From"] = smtp_user
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, [to_email], message.as_string())


def get_or_create_onboarding_state(db: Session, email: str) -> models.CandidateOnboardingState:
    normalized = _normalize_email(email)
    if not normalized:
        raise ValueError("email is required")

    record = (
        db.query(models.CandidateOnboardingState)
        .filter(models.CandidateOnboardingState.email == normalized)
        .first()
    )
    if record:
        return record

    record = models.CandidateOnboardingState(email=normalized)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _compute_next_step(record: models.CandidateOnboardingState) -> str:
    if not record.basic_info_validated:
        return "basic_info"
    if not record.id_uploaded or record.id_verification_status != "verified":
        return "id_upload"
    if not (record.enrollment_signed and record.placement_signed):
        return "agreements"
    if not (record.enrollment_verified and record.placement_verified):
        return "agreements"
    return "complete"


def serialize_onboarding_state(record: models.CandidateOnboardingState) -> Dict[str, object]:
    next_step = _compute_next_step(record)
    onboarding_complete = next_step == "complete"
    return {
        "basic_info_validated": bool(record.basic_info_validated),
        "id_uploaded": bool(record.id_uploaded),
        "id_verification_status": record.id_verification_status,
        "id_verification_pending": record.id_verification_status == "pending" and bool(record.id_uploaded),
        "id_cancel_count": int(record.id_cancel_count or 0),
        "id_cancel_limit": int(record.id_cancel_limit or ID_CANCEL_LIMIT),
        "id_cancel_blocked": bool((record.id_cancel_count or 0) >= (record.id_cancel_limit or ID_CANCEL_LIMIT)),
        "enrollment_signed": bool(record.enrollment_signed),
        "placement_signed": bool(record.placement_signed),
        "enrollment_verified": bool(record.enrollment_verified),
        "placement_verified": bool(record.placement_verified),
        "onboarding_complete": onboarding_complete,
        "next_step": next_step,
        "access_restricted": not onboarding_complete,
    }


def get_onboarding_snapshot(db: Session, email: str) -> Dict[str, object]:
    record = get_or_create_onboarding_state(db, email)
    result = serialize_onboarding_state(record)
    import logging
    logging.warning(f"ONBOARDING SNAPSHOT for {email}: {result}")
    return result


def mark_basic_info_validated(db: Session, email: str, data: dict) -> Dict[str, object]:
    record = get_or_create_onboarding_state(db, email)
    
    # Also update CandidateORM
    candidate = db.query(models.CandidateORM).filter(models.CandidateORM.email.ilike(email)).first()
    if candidate:
        candidate.full_name = data.get("full_name")
        candidate.phone = data.get("phone")
        candidate.linkedin_id = data.get("linkedin_url")
        candidate.emergcontactname = data.get("emergency_contact_name")
        candidate.emergcontactphone = data.get("emergency_contact_phone")
        candidate.emergcontactemail = data.get("emergency_contact_email")
        if data.get("has_user_input_error"):
            candidate.resume_content = data.get("original_resume_text")
    
    record.basic_info_validated = True
    record.basic_info_validated_at = _utcnow()
    db.commit()
    db.refresh(record)
    return serialize_onboarding_state(record)


def record_id_cancel(db: Session, email: str) -> Dict[str, object]:
    record = get_or_create_onboarding_state(db, email)
    limit = record.id_cancel_limit or ID_CANCEL_LIMIT
    if (record.id_cancel_count or 0) >= limit:
        return serialize_onboarding_state(record)
    record.id_cancel_count = (record.id_cancel_count or 0) + 1
    db.commit()
    db.refresh(record)
    return serialize_onboarding_state(record)


def mark_id_uploaded(db: Session, email: str) -> Dict[str, object]:
    record = get_or_create_onboarding_state(db, email)
    record.id_uploaded = True
    record.id_uploaded_at = _utcnow()
    record.id_verification_status = "pending"
    record.id_verification_requested_at = _utcnow()
    db.commit()
    db.refresh(record)

    _send_email(
        record.email,
        "ID upload received",
        "<p>Thank you. Your ID has been uploaded and is pending verification.</p>",
    )
    return serialize_onboarding_state(record)


def set_id_verification_status(db: Session, email: str, status_value: str) -> Dict[str, object]:
    allowed = {"pending", "verified", "rejected"}
    if status_value not in allowed:
        raise ValueError("Invalid id_verification_status")

    record = get_or_create_onboarding_state(db, email)
    record.id_verification_status = status_value
    if status_value == "verified":
        record.id_verified_at = _utcnow()
    if status_value == "rejected":
        record.id_uploaded = False
        record.id_uploaded_at = None
        record.id_verified_at = None
    db.commit()
    db.refresh(record)
    return serialize_onboarding_state(record)


def generate_agreement_pdf(candidate_name: str, agreement_type: str, date_str: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, f"{agreement_type.title()} Agreement", ln=True, align="C")
    pdf.ln(10)
    
    pdf.set_font("helvetica", "", 12)
    text = (
        f"This agreement is entered into by {candidate_name} on {date_str}. "
        f"By signing this document, the candidate agrees to the {agreement_type} terms and conditions "
        "provided by Whitebox Learning."
    )
    pdf.multi_cell(0, 10, text)
    pdf.ln(20)
    
    pdf.set_font("courier", "I", 14)
    pdf.cell(0, 10, f"Signed by: {candidate_name}", ln=True)
    pdf.cell(0, 10, f"Date: {date_str}", ln=True)
    
    return bytes(pdf.output())


def mark_agreement_signed(db: Session, email: str, agreement_type: str) -> Dict[str, object]:
    if agreement_type not in {"enrollment", "placement"}:
        raise ValueError("agreement_type must be enrollment or placement")

    record = get_or_create_onboarding_state(db, email)
    candidate = db.query(models.CandidateORM).filter(models.CandidateORM.email.ilike(email)).first()
    candidate_name = candidate.full_name if candidate else email.split("@")[0]
    now = _utcnow()
    date_str = now.strftime("%Y-%m-%d %H:%M:%S")

    if agreement_type == "enrollment":
        record.enrollment_signed = True
        record.enrollment_signed_at = now
    else:
        record.placement_signed = True
        record.placement_signed_at = now
    
    db.commit()
    db.refresh(record)

    return serialize_onboarding_state(record)


def mark_agreement_verified(db: Session, email: str, agreement_type: str) -> Dict[str, object]:
    if agreement_type not in {"enrollment", "placement"}:
        raise ValueError("agreement_type must be enrollment or placement")

    record = get_or_create_onboarding_state(db, email)
    if agreement_type == "enrollment":
        record.enrollment_verified = True
    else:
        record.placement_verified = True
    db.commit()
    db.refresh(record)
    return serialize_onboarding_state(record)


def pending_id_verification_needs_reminder(record: models.CandidateOnboardingState) -> bool:
    if not record.id_uploaded or record.id_verification_status != "pending":
        return False
    if not record.id_uploaded_at:
        return False
    if record.last_id_verification_reminder_at:
        return False
    return record.id_uploaded_at <= (_utcnow() - timedelta(days=ID_VERIFICATION_REMINDER_DAYS))


def trigger_id_pending_reminders(db: Session) -> int:
    admin_emails = [
        e.strip() for e in os.getenv("ID_VERIFICATION_ADMIN_EMAILS", "").split(",") if e.strip()
    ]
    if not admin_emails:
        admin_emails = [e.strip() for e in os.getenv("APPROVER_EMAILS", "").split(",") if e.strip()]

    if not admin_emails:
        return 0

    candidates = db.query(models.CandidateOnboardingState).all()
    sent = 0
    for record in candidates:
        if not pending_id_verification_needs_reminder(record):
            continue
        for admin_email in admin_emails:
            _send_email(
                admin_email,
                "Please verify the ID",
                f"<p>ID verification is pending for <b>{record.email}</b>. Please verify the ID.</p>",
            )
        record.last_id_verification_reminder_at = _utcnow()
        sent += 1

    if sent:
        db.commit()
    return sent
