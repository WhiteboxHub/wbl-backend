# fapi/api/approval.py
"""
Approval routes — thin wrappers that delegate to approval_utils.
"""
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi import Query, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from fapi.db.database import get_db
from fapi.utils import approval_utils
from fapi.utils import onboarding_utils
from fapi.utils.auth_dependencies import get_current_user

router = APIRouter(prefix="/approval", tags=["approval"])


@router.post("/upload")
async def upload_with_approval(
    uid: str = Form(...),
    file: UploadFile = File(...),
    username: str = Form(...),
    email: str = Form(...),
    document_type: str = Form(...),
    db: Session = Depends(get_db),
):
    return await approval_utils.upload_file(uid, file, username, email, document_type, db)


@router.get("/accept", response_class=HTMLResponse)
def accept(
    uid: str = Query(None),
    username: str = Query(None),
    approver_email: str = Query(None),
    db: Session = Depends(get_db),
):
    return approval_utils.accept_approval(uid, username, approver_email, db)


@router.get("/decline", response_class=HTMLResponse)
def decline(
    uid: str = Query(None),
    username: str = Query(None),
    approver_email: str = Query(None),
    db: Session = Depends(get_db),
):
    return approval_utils.decline_approval(uid, username, approver_email, db)


@router.get("/documents")
def get_documents(email: str, db: Session = Depends(get_db)):
    return approval_utils.get_documents(email, db)


@router.delete("/documents/{uid}")
def delete_document(uid: str, db: Session = Depends(get_db)):
    return approval_utils.delete_documents(uid, db)


@router.get("/documents/status")
def get_document_status(email: str, db: Session = Depends(get_db)):
    return approval_utils.get_document_status(email, db)


@router.post("/send-for-approval")
async def send_for_approval(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    return approval_utils.process_send_for_approval(data, db)


@router.post("/submit-signature")
async def submit_signature(
    uid: str = Form(...),
    email: str = Form(...),
    username: str = Form(...),
    signature: UploadFile = File(...),
    document_type: str = Form("enrollment"),
    db: Session = Depends(get_db),
):
    return await approval_utils.process_submit_signature(
        uid, email, username, signature, document_type, db
    )


@router.post("/create-session")
def create_session(username: str, email: str):
    return approval_utils.create_session(username, email)


class BasicInfoPayload(BaseModel):
    email: EmailStr
    full_name: str
    phone: str
    linkedin_url: str
    emergency_contact_name: str
    emergency_contact_phone: str
    emergency_contact_email: EmailStr
    original_resume_text: str | None = None
    has_user_input_error: bool = False


class EmailPayload(BaseModel):
    email: EmailStr


class IdVerificationPayload(BaseModel):
    email: EmailStr
    id_verification_status: str


class AgreementSignPayload(BaseModel):
    email: EmailStr
    agreement_type: str  # enrollment | placement
    agreed: bool
    signed: bool


@router.get("/onboarding/status")
def onboarding_status(email: EmailStr, db: Session = Depends(get_db)):
    return onboarding_utils.get_onboarding_snapshot(db, str(email))


@router.post("/onboarding/basic-info")
def submit_basic_info(payload: BasicInfoPayload, db: Session = Depends(get_db)):
    required_values = [
        payload.full_name,
        payload.phone,
        payload.linkedin_url,
        payload.emergency_contact_name,
        payload.emergency_contact_phone,
        payload.emergency_contact_email,
    ]
    if any(not isinstance(v, str) or not v.strip() for v in required_values):
        raise HTTPException(status_code=400, detail="All basic information fields are mandatory.")

    if payload.has_user_input_error and not (payload.original_resume_text and payload.original_resume_text.strip()):
        raise HTTPException(
            status_code=400,
            detail="You entered something incorrectly. Please copy and paste your original resume text here.",
        )

    state = onboarding_utils.mark_basic_info_validated(db, str(payload.email), payload.dict())
    return {
        "message": "Thank you",
        "onboarding": state,
    }


@router.post("/onboarding/id/cancel")
def cancel_id_upload(payload: EmailPayload, db: Session = Depends(get_db)):
    state = onboarding_utils.record_id_cancel(db, str(payload.email))
    if state["id_cancel_blocked"]:
        return {
            "message": "ID upload is now mandatory. Cancellation is no longer allowed.",
            "onboarding": state,
        }
    return {"message": "ID upload cancelled.", "onboarding": state}


@router.post("/onboarding/id/uploaded")
def id_uploaded(payload: EmailPayload, db: Session = Depends(get_db)):
    state = onboarding_utils.mark_id_uploaded(db, str(payload.email))
    return {"message": "ID uploaded successfully.", "onboarding": state}


@router.post("/onboarding/id/verification")
def set_id_verification(payload: IdVerificationPayload, db: Session = Depends(get_db)):
    try:
        state = onboarding_utils.set_id_verification_status(
            db, str(payload.email), payload.id_verification_status
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"onboarding": state}


@router.post("/onboarding/signature/adopt")
def adopt_signature(payload: EmailPayload):
    name = payload.email.split("@")[0].replace(".", " ").title()
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='500' height='140'>"
        "<rect width='100%' height='100%' fill='white'/>"
        "<text x='20' y='88' font-family='cursive' font-size='52' fill='#111827'>"
        f"{name}"
        "</text>"
        "</svg>"
    )
    return {
        "signature_svg": svg,
        "note": "Generated signature based on user name.",
    }


@router.post("/onboarding/agreements/sign")
def sign_agreement(payload: AgreementSignPayload, db: Session = Depends(get_db)):
    if not payload.agreed or not payload.signed:
        raise HTTPException(status_code=400, detail="Please adopt signature, agree to terms, and sign.")
    try:
        state = onboarding_utils.mark_agreement_signed(db, str(payload.email), payload.agreement_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "message": f"{payload.agreement_type.title()} agreement signed and archived.",
        "onboarding": state,
    }


@router.post("/onboarding/id/reminders/trigger")
def trigger_id_verification_reminders(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    uname = (getattr(current_user, "uname", "") or "").lower()
    is_admin = (
        getattr(current_user, "role", None) == "admin"
        or getattr(current_user, "is_admin", False)
        or uname == "admin"
    )
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    sent = onboarding_utils.trigger_id_pending_reminders(db)
    return {"message": "Reminder run completed.", "emails_sent": sent}