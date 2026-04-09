# fapi/api/approval.py
import os
import time
import mimetypes

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi import Query
from sqlalchemy.orm import Session
from fastapi import Request
from fapi.db.database import get_db
from fapi.db import models
from fapi.utils.drive_service import (
    upload_to_temp,
    move_file_to_user_folder,
    rename_file,
    delete_file,
    build_final_filename,
)
from fapi.mail import approval_mail



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
    document_type: str = Form(...),
    db: Session = Depends(get_db),
):
    print("UPLOAD_ENDPOINT_HIT", username, email)
    print("FORM DATA CHECK")
    print("username:", username)
    print("email:", email)
    print("document_type:", document_type)
    print("file:", file.filename)

    if not APPROVER_EMAILS:
        raise HTTPException(status_code=500, detail="No approver emails configured")

    original_filename = file.filename or "upload.dat"
    uid = _generate_uid(username or email, original_filename)

    content = await file.read()
    mime_type, _ = mimetypes.guess_type(original_filename)
    mime_type = mime_type or "application/octet-stream"

    drive_file_id = upload_to_temp(content, mime_type, uid)

    # ✅🔥 ADD THIS BLOCK (MOST IMPORTANT FIX)
    new_file = models.FileApproval(
        uid=uid,
        username=username,
        email=email,
        original_filename=original_filename,
        document_type=document_type,
        drive_file_id=drive_file_id,
        # status="pending",
        approvals_count=0,
        is_approved=False,
        is_declined=False,
    )

    db.add(new_file)
    db.commit()
    db.refresh(new_file)
    print("SAVED UID:", new_file.uid)
    

    approval_mail.send_approval_emails(
        uid=uid,
        username=username,
        email=email,
        original_filename=original_filename,
        drive_file_id=drive_file_id,
        approvers=APPROVER_EMAILS,
    )

    return {
        "uid": uid,
        "status": "pending",
        "message": "File uploaded; approval emails sent."
    }

@router.get("/accept", response_class=HTMLResponse)
def accept(
    uid: str = Query(None),
    file_id: str = Query(None),
    username: str = Query(None),
    original_filename: str = Query(None),
    approver_email: str = Query(None),
    db: Session = Depends(get_db),
):
    print("ACCEPT HIT:", uid, file_id, username, original_filename, approver_email)
    print("UID FROM URL:", uid)
    all_records = db.query(models.FileApproval).all()
    print("ALL DB UIDs:", [r.uid for r in all_records])    

    approval = db.query(models.FileApproval).filter(
    models.FileApproval.uid.contains(uid.split('.')[0])
        ).first()

    if not approval:
        return HTMLResponse("<h3>Invalid request.</h3>", status_code=404)

    if approval.is_declined:
        return HTMLResponse("<h3>Already declined.</h3>")

    if approval.is_approved:
        return HTMLResponse("<h3>Already fully approved.</h3>")

    # ✅ prevent duplicate voting
    existing = db.query(models.FileApprovalAction).filter_by(
        uid=uid,
        approver_email=approver_email
    ).first()

    if existing:
        return HTMLResponse("<h3>You already responded.</h3>")

    # ✅ record approval
    action = models.FileApprovalAction(
        uid=uid,
        approver_email=approver_email,
        decision="accept"
    )
    db.add(action)

    approval.approvals_count += 1

    # ✅ ONLY MOVE FILE WHEN FINAL APPROVAL REACHED
    

    if approval.approvals_count >= REQUIRED_APPROVALS:
        print("FINAL APPROVAL → MOVING FILE")

        approval.is_approved = True
        approval.status = "approved"

        try:
            move_file_to_user_folder(
                file_id=file_id,
                username=approval.username or approval.email
            )

            rename_file(
                file_id=file_id,
                username=approval.username or approval.email,
                original_name=original_filename,
                document_type=approval.document_type or "document"
            )

        except Exception as e:
            print("MOVE ERROR:", str(e))
            return HTMLResponse(f"<h3>❌ File move failed: {str(e)}</h3>")

    else:
        approval.status = "pending"

    db.commit()

    return HTMLResponse("<h3>✅ Approval recorded.</h3>")  

@router.get("/decline", response_class=HTMLResponse)
def decline(
    uid: str = Query(None),
    file_id: str = Query(None),
    username: str = Query(None),
    original_filename: str = Query(None),
    approver_email: str = Query(None),
    db: Session = Depends(get_db)
):
    print("DECLINE HIT:", uid, file_id, username, original_filename, approver_email)

    approval = db.query(models.FileApproval).filter(
    models.FileApproval.uid.contains(uid.split('.')[0])
        ).first()

    if not approval:
        return HTMLResponse("<h3>Invalid request.</h3>", status_code=404)

    if approval.is_approved:
        return HTMLResponse("<h3>Already approved.</h3>")

    if approval.is_declined:
        return HTMLResponse("<h3>Already declined.</h3>")

    existing = db.query(models.FileApprovalAction).filter_by(
        uid=uid,
        approver_email=approver_email
    ).first()

    if existing:
        return HTMLResponse("<h3>You already responded.</h3>")

    action = models.FileApprovalAction(
        uid=uid,
        approver_email=approver_email,
        decision="decline"
    )
    db.add(action)

    approval.is_declined = True

    db.commit()

    return HTMLResponse("<h3>❌ Declined.</h3>")

@router.get("/documents")

def get_documents(email: str, db: Session = Depends(get_db)):
    files = db.query(models.FileApproval).filter(
        models.FileApproval.email == email
    ).all()

    response = {
        "identity": None,
        "address": None,
        "work_auth": None,
        "recent_activity": []
    }

    for f in files:
        status = "pending"
        if f.is_approved:
            status = "approved"
        elif f.is_declined:
            status = "rejected"
        file_data = {
            "uid": f.uid,
            "filename": f.original_filename,
            "status": status,
            "uploaded_at": f.id,  # or timestamp if you have
            "drive_file_id": f.drive_file_id
        }

        if f.document_type == "identity":
            response["identity"] = file_data
        elif f.document_type == "address":
            response["address"] = file_data
        elif f.document_type == "work_auth":
            response["work_auth"] = file_data

        response["recent_activity"].append(file_data)

    return response

@router.delete("/documents/{uid}")
def delete_document(uid: str, db: Session = Depends(get_db)):
    approval = db.query(models.FileApproval).filter(
        models.FileApproval.uid == uid
    ).first()

    if not approval:
        raise HTTPException(404, "File not found")

    delete_file(approval.drive_file_id)

    db.delete(approval)
    db.commit()

    return {"message": "Deleted successfully"}

@router.get("/documents/status")
def get_document_status(email: str, db: Session = Depends(get_db)):

    document_types = ["identity", "address", "work_auth"]

    response = {
        "identity": None,
        "address": None,
        "work_auth": None,
        "recent_activity": []
    }

    for doc_type in document_types:
        file = (
            db.query(models.FileApproval)
            .filter(
                models.FileApproval.email == email,
                models.FileApproval.document_type == doc_type
            )
            .order_by(models.FileApproval.created_at.desc())
            .first()
        )

        if not file:
            continue

        # ✅ status logic
        if file.is_approved:
            status = "APPROVED"
        elif file.is_declined:
            status = "REJECTED"
        else:
            status = "UPLOADED"

        # ✅ structured response
        file_data = {
            "uid": file.uid,
            "filename": file.original_filename,
            "status": status,
            "uploaded_at": file.created_at,
            "drive_file_id": file.drive_file_id
        }

        response[doc_type] = file_data
        response["recent_activity"].append(file_data)

    return response

