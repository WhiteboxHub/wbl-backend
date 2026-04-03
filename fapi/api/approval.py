# fapi/api/approval.py
import os
import time
import mimetypes

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.db import models
from fapi.utils.drive_service import (
    upload_to_temp,
    move_file_to_user_folder,
    rename_file,
    build_final_filename,
)
from fapi.mail.approval_mail import send_approval_emails


router = APIRouter(prefix="/approval", tags=["approval"])

APPROVER_EMAILS = [
    e.strip()
    for e in os.getenv("APPROVER_EMAILS", "").split(",")
    if e.strip()
]
if not APPROVER_EMAILS:
    APPROVER_EMAILS = [
        e.strip()
        for e in os.getenv("MANAGER_EMAILS", "").split(",")
        if e.strip()
    ]
REQUIRED_APPROVALS = int(os.getenv("REQUIRED_APPROVALS", "1"))

print("APPROVER_EMAILS raw:", os.getenv("APPROVER_EMAILS"))
print("APPROVER_EMAILS parsed:", APPROVER_EMAILS)
print("REQUIRED_APPROVALS:", REQUIRED_APPROVALS)


def _generate_uid(username_or_email: str, original_filename: str) -> str:
    base = username_or_email.replace("@", "_").replace(".", "_")
    ts = int(time.time())
    ext = original_filename.split(".")[-1] if "." in original_filename else "dat"
    return f"UID_{base}_{ts}.{ext}"


@router.post("/upload")
async def upload_with_approval(
    file: UploadFile = File(...),
    username: str = Form(...),
    email: str = Form(...),
    db: Session = Depends(get_db),
):
    print("UPLOAD_ENDPOINT_HIT", username, email)
    if not APPROVER_EMAILS:
        raise HTTPException(status_code=500, detail="No approver emails configured")

    original_filename = file.filename or "upload.dat"
    uid = _generate_uid(username or email, original_filename)

    content = await file.read()
    mime_type, _ = mimetypes.guess_type(original_filename)
    mime_type = mime_type or "application/octet-stream"

    # 1) Upload to Google Drive temp folder
    drive_file_id = upload_to_temp(content, mime_type, uid)

    # 2) Save FileApproval in DB
    approval = models.FileApproval(
        uid=uid,
        username=username,
        email=email,
        drive_file_id=drive_file_id,
        original_filename=original_filename,
        approvals_count=0,
        is_approved=False,
        is_declined=False,
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)

    # 3) Send approval emails
    send_approval_emails(
        uid=uid,
        username=username,
        email=email,
        original_filename=original_filename,
        drive_file_id=drive_file_id,
        approvers=APPROVER_EMAILS,
    )

    return {"uid": uid, "status": "pending", "message": "File uploaded; approval emails sent."}


@router.get("/accept")
def accept(uid: str, email: str, db: Session = Depends(get_db)):
    approval = (
        db.query(models.FileApproval)
        .filter(models.FileApproval.uid == uid)
        .first()
    )
    if not approval:
        return HTMLResponse("<h3>Invalid or expired approval link.</h3>")

    if approval.is_declined:
        return HTMLResponse("<h3>This file was already declined.</h3>")

    if approval.is_approved:
        return HTMLResponse("<h3>This file is already fully approved.</h3>")

    # Increment approvals count
    approval.approvals_count += 1

    # If approvals reached threshold, finalize
    if approval.approvals_count >= REQUIRED_APPROVALS:
        approval.is_approved = True
    username_or_email = approval.username or approval.email

    move_file_to_user_folder(
        file_id=approval.drive_file_id,
        username=username_or_email,
    )

    rename_file(
        file_id=approval.drive_file_id,
        username=username_or_email,
        original_name=approval.original_filename,
    )

    db.add(approval)
    db.commit()
    db.refresh(approval)

    return HTMLResponse("<h3>Your approval has been recorded. The file will be saved once all approvers accept.</h3>")

@router.get("/decline", response_class=HTMLResponse)
def decline(uid: str, email: str, db: Session = Depends(get_db)):
    approval = db.query(models.FileApproval).filter(models.FileApproval.uid == uid).first()
    if not approval:
        return HTMLResponse("<h3>Invalid UID.</h3>", status_code=404)

    if approval.is_declined:
        return HTMLResponse("<h3>This request is already declined.</h3>")
    if approval.is_approved:
        return HTMLResponse("<h3>This request is already approved.</h3>")

    existing = (
        db.query(models.FileApprovalAction)
        .filter(
            models.FileApprovalAction.uid == uid,
            models.FileApprovalAction.approver_email == email,
        )
        .first()
    )
    if existing:
        return HTMLResponse("<h3>You already responded for this file.</h3>")

    action = models.FileApprovalAction(
        uid=uid,
        approver_email=email,
        decision="decline",
    )
    db.add(action)
    approval.is_declined = True

    db.commit()
    return HTMLResponse("<h3>Your decline has been recorded.</h3>")
