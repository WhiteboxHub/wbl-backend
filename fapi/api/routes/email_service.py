
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import json

router = APIRouter()
logger = logging.getLogger(__name__)

class Recipient(BaseModel):
    email: str
    unsubscribe_link: Optional[str] = None

class EmailEngineConfig(BaseModel):
    provider: str
    credentials_json: Dict[str, Any]

class EmailDispatchPayload(BaseModel):
    job_run_id: int
    job_type: str
    candidate_info: Dict[str, Any]
    recipients: List[Recipient]
    engine: EmailEngineConfig
    config_json: Dict[str, Any]

@router.post("/email-service/send")
async def send_emails(payload: EmailDispatchPayload):
    """
    Internal Email Service Endpoint.
    Receives a batch of recipients and sends emails using the provided engine credentials.
    """
    logger.info(f"📧 Internal Service received dispatch for JobRun {payload.job_run_id}")
    
    succeeded = 0
    failed = 0
    total = len(payload.recipients)
    
    # Extract Engine Credentials
    creds = payload.engine.credentials_json
    smtp_server = creds.get("smtp_server") or creds.get("host")
    smtp_port = creds.get("smtp_port") or creds.get("port")
    smtp_user = creds.get("username") or creds.get("user") or creds.get("email")
    smtp_pass = creds.get("password") or creds.get("pass")
    
    if not (smtp_server and smtp_port and smtp_user and smtp_pass):
        logger.error("❌ Missing SMTP credentials in payload")
        raise HTTPException(status_code=400, detail="Invalid SMTP credentials")
        
    try:
        # Prepare content
        subject = payload.config_json.get("subject", "Information from Innovapath")
        body_template = payload.config_json.get("body_template", "")
        
        # Connect to SMTP Server
        server = smtplib.SMTP(smtp_server, int(smtp_port))
        server.starttls()
        server.login(smtp_user, smtp_pass)
        
        for recipient in payload.recipients:
            try:
                # Basic Template Replacement (can be expanded)
                content = body_template
                content = content.replace("{{first_name}}", "Candidate") # Placeholder logic
                content = content.replace("{{unsubscribe_link}}", recipient.unsubscribe_link or "#")
                
                # Check for Candidate Marketing context
                cand_info = payload.candidate_info
                if cand_info:
                    content = content.replace("{{candidate_name}}", cand_info.get("full_name", ""))
                    content = content.replace("{{candidate_intro}}", cand_info.get("candidate_intro", ""))
                
                msg = MIMEMultipart()
                msg['From'] = f"{payload.candidate_info.get('full_name', 'Innovapath')} <{smtp_user}>"
                msg['To'] = recipient.email
                msg['Subject'] = subject
                msg.attach(MIMEText(content, 'html'))
                
                server.sendmail(smtp_user, recipient.email, msg.as_string())
                succeeded += 1
            except Exception as e:
                logger.error(f"Failed to send to {recipient.email}: {e}")
                failed += 1
                
        server.quit()
        
    except Exception as e:
        logger.error(f"SMTP Connection Error: {e}")
        return {
            "run_status": "FAILED",
            "items_total": total,
            "items_succeeded": 0,
            "items_failed": total,
            "error": str(e)
        }

    return {
        "run_status": "SUCCESS" if failed == 0 else "PARTIAL",
        "items_total": total,
        "items_succeeded": succeeded,
        "items_failed": failed
    }
