# fapi/mail/approval_mail.py
import os
import smtplib
from typing import List, Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: Optional[str] = os.getenv("SMTP_USER")
SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")

APPROVAL_BASE_URL = os.getenv("APPROVAL_BASE_URL", "http://127.0.0.1:8000")  # e.g. http://127.0.0.1:8000


def _build_body(uid: str, approver_email: str, username: str,
                original_filename: str, drive_file_id: str,
                document_type: str) -> str:

   

    accept_url = (
    f"{APPROVAL_BASE_URL}/api/approval/accept"
    f"?uid={quote(uid)}"
    f"&file_id={quote(drive_file_id)}"
    f"&username={quote(username)}"
    f"&original_filename={quote(original_filename)}"
    f"&approver_email={quote(approver_email)}"
)

    decline_url = (
    f"{APPROVAL_BASE_URL}/api/approval/decline"
    f"?uid={quote(uid)}"
    f"&file_id={quote(drive_file_id)}"
    f"&username={quote(username)}"
    f"&original_filename={quote(original_filename)}"
    f"&approver_email={quote(approver_email)}"
)
    file_link = f"https://drive.google.com/file/d/{drive_file_id}/view"
    status_url = f"{APPROVAL_BASE_URL}/status?uid={quote(uid)}"

    print("ACCEPT URL:", accept_url)
    print("DECLINE URL:", decline_url)

    return f"""
    <html>
      <body>
        <h3>Document Approval Request</h3>

        <p>
          User <b>{username}</b> uploaded 
          <b>{document_type.upper().replace("_", " ")}</b>:
          <b>{original_filename}</b>
        </p>

        <p>
          UID: <b>{uid}</b><br/>
          Uploaded by: <b>{approver_email}</b>
        </p>

        <p>
          <a href="{file_link}">📄 View File</a>
        </p>

        <p>Please choose an action:</p>

        <p>
          <a href="{accept_url}" style="padding:10px 18px;background:#4CAF50;color:#fff;text-decoration:none;">Accept</a>
          &nbsp;&nbsp;
          <a href="{decline_url}" style="padding:10px 18px;background:#f44336;color:#fff;text-decoration:none;">Decline</a>
        </p>

        <p>
          <a href="{status_url}" style="padding:8px 16px;background:#6c63ff;color:#fff;text-decoration:none;">
            View Status
          </a>
        </p>

        <hr />

        <p style="font-size:12px;color:#999;">
          You can respond only once. Subsequent actions will be ignored.
        </p>

        <p style="font-size:12px;color:#666;">
          Need help? Contact your coordinator or support team.
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
    document_type: str = "",
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

            body_html = _build_body(uid, email, username, original_filename, drive_file_id, document_type)
            msg.attach(MIMEText(body_html, "html"))

            server.sendmail(SMTP_USER, [approver], msg.as_string())
