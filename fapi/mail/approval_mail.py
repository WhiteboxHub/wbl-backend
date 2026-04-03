# fapi/mail/approval_mail.py
import os
import smtplib
from typing import List, Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: Optional[str] = os.getenv("SMTP_USER")
SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")

APPROVAL_BASE_URL = os.getenv("APPROVAL_BASE_URL")  # e.g. http://127.0.0.1:8000


def _build_body(uid: str, approver_email: str, username: str,
                original_filename: str, drive_file_id: str) -> str:
    accept_url = f"{APPROVAL_BASE_URL}/api/approval/accept?uid={uid}&email={approver_email}"
    decline_url = f"{APPROVAL_BASE_URL}/api/approval/decline?uid={uid}&email={approver_email}"
    file_link = f"https://drive.google.com/file/d/{drive_file_id}/view"

    return f"""
    <html>
      <body>
        <p>User <b>{username}</b> uploaded file: <b>{original_filename}</b> (UID: <b>{uid}</b>)</p>
        <p>File: <a href="{file_link}">Open in Google Drive</a></p>
        <p>Please choose an action:</p>
        <p>
          <a href="{accept_url}" style="padding:8px 16px;background:#4CAF50;color:#fff;text-decoration:none;">Accept</a>
          &nbsp;&nbsp;
          <a href="{decline_url}" style="padding:8px 16px;background:#f44336;color:#fff;text-decoration:none;">Decline</a>
        </p>
      </body>
    </html>
    """


def send_approval_emails(
    uid: str,
    username: str,
    email: str,
    original_filename: str,
    drive_file_id: str,
    approvers: List[str],
) -> None:
    if not SMTP_USER or not SMTP_PASSWORD:
        raise ValueError("SMTP_USER and SMTP_PASSWORD must be set in environment to send approval emails")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)

        for approver in approvers:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Approval required: {original_filename}"
            msg["From"] = SMTP_USER
            msg["To"] = approver

            body_html = _build_body(uid, approver, username, original_filename, drive_file_id)
            msg.attach(MIMEText(body_html, "html"))

            server.sendmail(SMTP_USER, [approver], msg.as_string())