from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.utils.auth_dependencies import get_current_user
from fapi.utils import onboarding_utils


router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


class BasicInfoValidateRequest(BaseModel):
    full_name: str
    phone: str
    email: str
    linkedin_url: str
    emergency_contact_name: str
    emergency_contact_email: str
    emergency_contact_phone: str
    emergency_contact_address: str
    resume_text: str


class AgreementSignRequest(BaseModel):
    agreement_type: str  # enrollment | placement


class IdVerifyRequest(BaseModel):
    verified: bool
    email: Optional[str] = None


@router.get("/status")
def get_onboarding_status(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    email = getattr(current_user, "uname", "")
    authuser_id = getattr(current_user, "id", None)
    state = onboarding_utils.get_or_create_onboarding_state(db, email, authuser_id)
    return onboarding_utils.onboarding_status_payload(state)


@router.post("/basic-info/validate")
def validate_basic_info(
    payload: BasicInfoValidateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    authuser_id = getattr(current_user, "id", None)
    return onboarding_utils.validate_basic_info(db, payload.email, payload.model_dump(), authuser_id)


@router.post("/id/cancel")
def cancel_id_upload(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    email = getattr(current_user, "uname", "")
    authuser_id = getattr(current_user, "id", None)
    status = onboarding_utils.increment_id_upload_cancel(db, email, authuser_id)
    return {"message": "ID upload wizard cancelled.", "status": status}


@router.post("/id/uploaded")
def mark_id_uploaded(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    email = getattr(current_user, "uname", "")
    authuser_id = getattr(current_user, "id", None)
    status = onboarding_utils.mark_id_uploaded(db, email, authuser_id)
    return {"message": "ID upload recorded.", "status": status}


@router.post("/id/verify")
def verify_id(
    payload: IdVerifyRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    email = payload.email or getattr(current_user, "uname", "")
    authuser_id = getattr(current_user, "id", None)
    status = onboarding_utils.set_id_verification_status(db, email, payload.verified, authuser_id)
    return {"message": "ID verification status updated.", "status": status}


@router.post("/agreements/sign")
def sign_agreements(
    payload: AgreementSignRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    email = getattr(current_user, "uname", "")
    authuser_id = getattr(current_user, "id", None)
    status = onboarding_utils.sign_agreement(db, email, payload.agreement_type, authuser_id)
    return {"message": "Agreement signed successfully.", "status": status}

