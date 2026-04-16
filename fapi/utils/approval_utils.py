# fapi/utils/approval_utils.py
"""
Business logic for the approval workflow.
All helper functions and DB operations extracted from api/approval.py
to follow the established route/utils separation pattern.
"""
import os
import time
import mimetypes
import smtplib
import tempfile
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fpdf import FPDF

from fapi.db import models
from fapi.utils.drive_service import (
    upload_to_temp,
    move_file_to_user_folder,
    rename_file,
    delete_file,
    download_file_bytes,
)
from fapi.mail import approval_mail

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _load_approver_emails() -> List[str]:
    """Load approver emails from environment, falling back to MANAGER_EMAILS."""
    emails = [
        e.strip()
        for e in os.getenv("APPROVER_EMAILS", "").split(",")
        if e.strip()
    ]
    if not emails:
        emails = [
            e.strip()
            for e in os.getenv("MANAGER_EMAILS", "").split(",")
            if e.strip()
        ]
    return emails


APPROVER_EMAILS = _load_approver_emails()
REQUIRED_APPROVALS = int(os.getenv("REQUIRED_APPROVALS", "1"))

print("APPROVER_EMAILS raw:", os.getenv("APPROVER_EMAILS"))
print("APPROVER_EMAILS parsed:", APPROVER_EMAILS)
print("REQUIRED_APPROVALS:", REQUIRED_APPROVALS)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def generate_uid(username_or_email: str, original_filename: str) -> str:
    """Generate a unique identifier from username/email + timestamp."""
    base = username_or_email.replace("@", "_").replace(".", "_")
    ts = int(time.time())
    ext = original_filename.split(".")[-1] if "." in original_filename else "dat"
    return f"UID_{base}_{ts}.{ext}"


def display_name(username: str | None, email: str) -> str:
    """Return the username if available, otherwise the email."""
    return username if isinstance(username, str) and username else email


def document_type_or_default(value: object, default: str) -> str:
    """Return the document type value, or a default if empty/None."""
    return value if isinstance(value, str) and value else default


def send_email(to_email: str, subject: str, body: str) -> None:
    """Send an HTML email via SMTP."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not smtp_user or not smtp_password:
        raise HTTPException(status_code=500, detail="SMTP credentials are not configured")

    message = MIMEMultipart("alternative")
    message["From"] = smtp_user
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, [to_email], message.as_string())


# ---------------------------------------------------------------------------
# Shared verification status logic (de-duplicated)
# ---------------------------------------------------------------------------

def _compute_verification_status(
    response: dict,
    document_types_keys: List[str],
    email: str,
    db: Session,
) -> dict:
    """
    Compute the verification status block used by both
    /documents and /documents/status endpoints.
    """
    candidate = db.query(models.CandidateORM).filter(
        models.CandidateORM.email == email
    ).first()

    profile_status = "Verified" if candidate and candidate.status == "active" else "Pending"

    all_approved = all([
        response.get(t) and response[t]["status"] == "APPROVED"
        for t in document_types_keys
    ])
    any_declined = any([
        response.get(t) and response[t]["status"] == "DECLINED"
        for t in document_types_keys
    ])

    if all_approved:
        docs_status = "Verified"
    elif any_declined:
        docs_status = "Rejected"
    else:
        all_uploaded = all([
            response.get(t) and response[t]["status"] in ["UPLOADED", "APPROVED"]
            for t in document_types_keys
        ])
        if all_uploaded:
            docs_status = "Under Review"
        else:
            docs_status = "Pending"

    return {
        "profile": profile_status,
        "documents": docs_status,
    }


# ---------------------------------------------------------------------------
# Core business-logic functions (one per route)
# ---------------------------------------------------------------------------

async def upload_file(
    uid: str,
    file,  # UploadFile
    username: str,
    email: str,
    document_type: str,
    db: Session,
) -> dict:
    """Upload a file to Google Drive temp folder and save a DB record."""
    print("UPLOAD_ENDPOINT_HIT", username, email)
    print("file:", file.filename)
    print("uid:", uid)
    print("document_type:", document_type)

    if not APPROVER_EMAILS:
        raise HTTPException(status_code=500, detail="No approver emails configured")

    try:
        original_filename = file.filename or "upload.dat"

        content = await file.read()

        mime_type, _ = mimetypes.guess_type(original_filename)
        mime_type = mime_type or "application/octet-stream"

        drive_file_id = upload_to_temp(content, mime_type, uid)

        new_file = models.FileApproval(
            uid=uid,
            username=username,
            email=email,
            original_filename=original_filename,
            document_type=document_type,
            drive_file_id=drive_file_id,
            approvals_count=0,
            is_approved=False,
            is_declined=False,
        )

        db.add(new_file)
        db.commit()
        db.refresh(new_file)

        print("SAVED UID:", uid, "FILE:", original_filename)

        return {
            "uid": uid,
            "status": "pending",
            "message": "File uploaded successfully",
        }

    except Exception as e:
        print("UPLOAD ERROR:", str(e))
        raise HTTPException(status_code=500, detail="File upload failed")


def accept_approval(
    uid: str,
    username: str,
    approver_email: str,
    db: Session,
) -> HTMLResponse:
    """Record an 'accept' decision and move files when threshold is met."""
    print(f"ACCEPT HIT: UID={uid}, Approver={approver_email}")

    files = db.query(models.FileApproval).filter(
        models.FileApproval.uid == uid
    ).all()

    if not files:
        return HTMLResponse("<h3>No documents found for this UID.</h3>", status_code=404)

    existing = db.query(models.FileApprovalAction).filter_by(
        uid=uid,
        approver_email=approver_email,
    ).first()

    if existing:
        return HTMLResponse("<h3>You already responded to this request.</h3>")

    action = models.FileApprovalAction(
        uid=uid,
        approver_email=approver_email,
        decision="accept",
    )
    db.add(action)

    for approval in files:
        if approval.is_declined:
            continue

        approval.approvals_count += 1

        if approval.approvals_count >= REQUIRED_APPROVALS:
            approval.is_approved = True
            approval.status = "approved"

            if not approval.drive_file_id:
                print(f"DEBUG: Skipping move for record ID {approval.id} (No drive_file_id)")
                continue

            try:
                name = display_name(approval.username, approval.email)
                move_file_to_user_folder(
                    file_id=approval.drive_file_id,
                    username=name,
                )
                rename_file(
                    file_id=approval.drive_file_id,
                    username=name,
                    original_name=approval.original_filename,
                    document_type=document_type_or_default(approval.document_type, "document"),
                )
            except Exception as e:
                print(f"ERROR moving file {approval.drive_file_id}: {str(e)}")

    db.commit()
    return HTMLResponse("<h3>✅ All files have been approved and moved successfully.</h3>")


def decline_approval(
    uid: str,
    username: str,
    approver_email: str,
    db: Session,
) -> HTMLResponse:
    """Record a 'decline' decision and mark all files as declined."""
    print(f"DECLINE HIT: UID={uid}, Approver={approver_email}")

    files = db.query(models.FileApproval).filter(
        models.FileApproval.uid == uid
    ).all()

    if not files:
        return HTMLResponse("<h3>No documents found for this UID.</h3>", status_code=404)

    existing = db.query(models.FileApprovalAction).filter_by(
        uid=uid,
        approver_email=approver_email,
    ).first()

    if existing:
        return HTMLResponse("<h3>You already responded to this request.</h3>")

    action = models.FileApprovalAction(
        uid=uid,
        approver_email=approver_email,
        decision="decline",
    )
    db.add(action)

    for approval in files:
        approval.is_declined = True
        approval.status = "declined"

    db.commit()
    return HTMLResponse("<h3>❌ The application has been declined.</h3>")


def get_documents(email: str, db: Session) -> dict:
    """Fetch all documents for a user and compute verification status."""
    files = db.query(models.FileApproval).filter(
        models.FileApproval.email.ilike(email)
    ).order_by(models.FileApproval.id.desc()).all()

    response = {
        "identity": None,
        "address": None,
        "work_auth": None,
        "recent_activity": [],
    }

    for f in files:
        status = "UPLOADED"
        if f.is_approved:
            status = "APPROVED"
        elif f.is_declined:
            status = "DECLINED"
        file_data = {
            "uid": f.uid,
            "filename": f.original_filename,
            "status": status,
            "uploaded_at": f.id,  # or timestamp if you have
            "drive_file_id": f.drive_file_id,
        }

        if (f.document_type == "id_proof" or f.document_type == "identity") and response["identity"] is None:
            response["identity"] = file_data
        elif (f.document_type == "address_proof" or f.document_type == "address") and response["address"] is None:
            response["address"] = file_data
        elif (f.document_type == "work_proof" or f.document_type == "work_auth") and response["work_auth"] is None:
            response["work_auth"] = file_data

        response["recent_activity"].append(file_data)

    document_types_keys = ["identity", "address", "work_auth"]
    response["verification"] = _compute_verification_status(
        response, document_types_keys, email, db
    )

    return response


def delete_documents(uid: str, db: Session) -> dict:
    """Delete all files associated with a UID from Drive and DB."""
    approvals = db.query(models.FileApproval).filter(
        models.FileApproval.uid == uid
    ).all()

    if not approvals:
        raise HTTPException(404, "File group not found")

    for approval in approvals:
        if approval.drive_file_id:
            try:
                delete_file(approval.drive_file_id)
            except Exception as e:
                print(f"Error deleting drive file {approval.drive_file_id}: {e}")

        db.delete(approval)

    db.commit()

    return {"message": f"Deleted {len(approvals)} files successfully"}


def get_document_status(email: str, db: Session) -> dict:
    """Get the latest document per type and compute verification status."""
    document_types = ["identity", "address", "work_auth"]

    response = {
        "identity": None,
        "address": None,
        "work_auth": None,
        "recent_activity": [],
    }

    for doc_type in document_types:
        file = (
            db.query(models.FileApproval)
            .filter(
                models.FileApproval.email == email,
                models.FileApproval.document_type == doc_type,
            )
            .order_by(models.FileApproval.created_at.desc())
            .first()
        )

        if not file:
            continue

        status = "UPLOADED"
        if file.is_approved:
            status = "APPROVED"
        elif file.is_declined:
            status = "DECLINED"

        file_data = {
            "uid": file.uid,
            "filename": file.original_filename,
            "status": status,
            "uploaded_at": file.created_at,
            "drive_file_id": file.drive_file_id,
        }

        response[doc_type] = file_data
        response["recent_activity"].append(file_data)

    response["verification"] = _compute_verification_status(
        response, document_types, email, db
    )

    return response


def process_send_for_approval(data: dict, db: Session) -> dict:
    """Save a signature-only record and send approval emails."""
    uid = f"SIG_{int(time.time())}"

    username = data.get("username")
    email = data.get("approver_email")
    signature = data.get("signature")
    document_type = data.get("document_type")

    if not signature:
        raise HTTPException(status_code=400, detail="Signature required")

    new_file = models.FileApproval(
        uid=uid,
        username=username,
        email=email,
        original_filename="digital_signature.png",
        document_type="signature",
        drive_file_id=None,
        approvals_count=0,
        is_approved=False,
        is_declined=False,
    )

    db.add(new_file)
    db.commit()

    approval_mail.send_approval_emails(
        uid=uid,
        username=username,
        email=email,
        original_filename="digital_signature.png",
        drive_file_ids=["SIGNATURE_ONLY"],
        approvers=APPROVER_EMAILS,
    )

    return {"message": "Sent for approval"}


async def process_submit_signature(
    uid: str,
    email: str,
    username: str,
    signature,  # UploadFile
    document_type: str,
    db: Session,
) -> dict:
    """
    Generate a PDF from the signature image, upload to Drive,
    collect all files for the UID, and send an approval email with attachments.
    """
    print(f"=== SUBMIT SIGNATURE HIT: {uid} ===")

    try:
        # 1. Process Signature Image to PDF
        sig_bytes = await signature.read()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img:
            tmp_img.write(sig_bytes)
            tmp_img_path = tmp_img.name

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("helvetica", "B", 16)
        pdf.cell(0, 10, "Enrollment Terms & Conditions - Signature", ln=True, align="C")
        pdf.ln(10)
        pdf.set_font("helvetica", "", 12)
        pdf.multi_cell(
            0, 10,
            f"Candidate Name: {username}\nEmail: {email}\nUID: {uid}\nDate: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        pdf.ln(20)
        pdf.cell(0, 10, "Digital Signature:", ln=True)
        pdf.image(tmp_img_path, x=20, w=100)

        pdf_bytes = pdf.output(dest='S')
        os.unlink(tmp_img_path)  # cleanup

        # 2. Upload Signature PDF to Drive Temp
        sig_filename = f"Signature_{username}.pdf"
        drive_file_id = upload_to_temp(pdf_bytes, "application/pdf", sig_filename)

        # 3. Save Signature Record to DB
        new_sig = models.FileApproval(
            uid=uid,
            username=username,
            email=email,
            original_filename=sig_filename,
            document_type=document_type,
            drive_file_id=drive_file_id,
            approvals_count=0,
            is_approved=False,
            is_declined=False,
        )
        db.add(new_sig)
        db.commit()

        # 4. Collect ALL files for this UID for email attachments
        all_files = db.query(models.FileApproval).filter(
            models.FileApproval.uid == uid
        ).order_by(models.FileApproval.id.asc()).all()

        # Deduplicate: Keep only the latest of each type for this UID
        unique_files_map = {}
        for f in all_files:
            unique_files_map[f.document_type] = f

        final_file_list = list(unique_files_map.values())

        attachments = []
        file_list_for_body = []

        for f in final_file_list:
            if not f.drive_file_id:
                print(f"DEBUG: Skipping attachment for {f.original_filename} (Null drive_file_id)")
                continue

            try:
                content = download_file_bytes(f.drive_file_id)
                mime_type, _ = mimetypes.guess_type(f.original_filename)
                attachments.append({
                    "content": content,
                    "filename": f.original_filename,
                    "mime_type": mime_type or "application/octet-stream",
                })
                file_list_for_body.append({"id": f.drive_file_id, "name": f.original_filename})
            except Exception as e:
                print(f"Failed to download/attach file {f.original_filename}: {e}")

        # 5. Send Email with Attachments
        approval_mail.send_approval_emails(
            uid=uid,
            username=username,
            email=email,
            original_filename="Signature Document",
            drive_file_ids=file_list_for_body,
            approvers=APPROVER_EMAILS,
            document_type=document_type,
            attachments=attachments,
        )

        return {
            "message": "Final enrollment submission successful. Email sent with attachments.",
            "uid": uid,
            "files_count": len(all_files),
        }

    except Exception as e:
        print("SUBMISSION ERROR:", str(e))
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Submission failed: {str(e)}")


def create_session(username: str, email: str) -> dict:
    """Generate a new session UID."""
    uid = generate_uid(username, email)
    return {"uid": uid}
