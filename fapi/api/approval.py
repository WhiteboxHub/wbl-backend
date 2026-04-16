# fapi/api/approval.py
"""
Approval routes — thin wrappers that delegate to approval_utils.
"""
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi import Query, Request
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.utils import approval_utils

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