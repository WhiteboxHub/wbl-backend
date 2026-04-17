# fapi/mail/approval_mail.py
import json
import os
import smtplib
from typing import List, Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from urllib.parse import quote

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: Optional[str] = os.getenv("SMTP_USER")
SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")

APPROVAL_BASE_URL = os.getenv("APPROVAL_BASE_URL", "http://127.0.0.1:8000")  # e.g. http://127.0.0.1:8000


def _build_body(uid: str, approver_email: str, username: str,
                original_filename: str, drive_file_ids: list,
                document_type: str) -> str:

    print("BUILD BODY FOR:", uid)

    accept_url = (
        f"{APPROVAL_BASE_URL}/api/approval/accept"
        f"?uid={quote(uid)}"
        f"&username={quote(username)}"
        f"&original_filename={quote(original_filename)}"
        f"&approver_email={quote(approver_email)}"
    )

    decline_url = (
        f"{APPROVAL_BASE_URL}/api/approval/decline"
        f"?uid={quote(uid)}"
        f"&username={quote(username)}"
        f"&original_filename={quote(original_filename)}"
        f"&approver_email={quote(approver_email)}"
    )
    status_url = f"{APPROVAL_BASE_URL}/status?uid={quote(uid)}"

    file_links_html = ""
    for file in drive_file_ids:
        # Some items might be "SIGNATURE_ONLY" or dicts
        if isinstance(file, dict) and 'id' in file:
            link = f"https://drive.google.com/file/d/{file['id']}/view"
            file_links_html += f"<li><a href='{link}'>{file['name']}</a></li>"
        else:
            file_links_html += f"<li>{file}</li>"

    custom_msg = ""
    document_label = original_filename
    
    if document_type == "placement":
        custom_msg = """
        <p style="color: #4f46e5; font-weight: bold; font-size: 16px;">
          The user has agreed the terms and conditions for the placement and agreed to proceed.
        </p>
        """
        document_label = "Signature Document"
    elif document_type == "enrollment":
        document_label = "Enrollment and Signature Documents"

    return f"""
    <html>
      <body>
        <h3>Document Approval Request</h3>

        <p>
         User <b>{username}</b> has completed final submission.
        </p>

        {custom_msg}
        
        <p><b>Documents:</b><br/>
         {document_label}
        </p>

        <p>
          UID: <b>{uid}</b><br/>
          User Email: <b>{approver_email}</b>
        </p>

        <p>
          <b>Google Drive Links:</b>
          {file_links_html}
        </p>

        <p>Please choose an action:</p>

        <p>
          <a href="{accept_url}" style="padding:10px 18px;background:#4CAF50;color:#fff;text-decoration:none;border-radius:5px;">Accept All</a>
          &nbsp;&nbsp;
          <a href="{decline_url}" style="padding:10px 18px;background:#f44336;color:#fff;text-decoration:none;border-radius:5px;">Decline All</a>
        </p>

        <p>
          <a href="{status_url}" style="padding:8px 16px;background:#6c63ff;color:#fff;text-decoration:none;border-radius:5px;">
            View Status
          </a>
        </p>

        <hr />

        <p style="font-size:12px;color:#999;">
          Files are also attached to this email for your convenience.
        </p>

      </body>
    </html>
    """


def send_approval_emails(
    uid: str,
    username: str,
    email: str,
    original_filename: str,
    drive_file_ids: list,
    approvers: List[str],
    document_type: str = "",
    attachments: Optional[List[dict]] = None  # Each: {"content": bytes, "filename": str, "mime_type": str}
) -> None:
    if not SMTP_USER or not SMTP_PASSWORD:
        raise ValueError("SMTP_USER and SMTP_PASSWORD must be set in environment to send approval emails")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)

        for approver in approvers:
            msg = MIMEMultipart("mixed")
            msg["Subject"] = f"Approval required: Final Submission for {username}"
            msg["From"] = email
            msg["Reply-To"] = email
            msg["To"] = approver

            body_html = _build_body(uid, email, username, original_filename, drive_file_ids, document_type)
            msg.attach(MIMEText(body_html, "html"))

            if attachments:
                for att in attachments:
                    mtype = att.get("mime_type", "application/octet-stream")
                    maintype, subtype = mtype.split("/", 1)
                    part = MIMEBase(maintype, subtype)
                    part.set_payload(att["content"])
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename={att['filename']}",
                    )
                    msg.attach(part)

            server.sendmail(SMTP_USER, [approver], msg.as_string())
