"""
Dynamic Weekly Marketing Report Service
Generates professional marketing dashboards based on database queries and sends to chosen recipients.
"""
import logging
import smtplib
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

from sqlalchemy import func, case, and_, or_
from sqlalchemy.orm import Session

from fapi.db.models import (
    CandidateORM,
    CandidateMarketingORM,
    CandidateInterview,
    AuthUserORM,
    JobLinkClicksORM,
    AutomationWorkflowLogORM,
    JobTypeORM,
    JobActivityLogORM
)

logger = logging.getLogger(__name__)

def generate_weekly_marketing_report(db: Session) -> Dict[str, Any]:
    """
    Generate dynamic professional marketing report data and HTML
    """
    # 1. Calculate date ranges
    end_date = datetime.now(timezone.utc)
    # 7-day range for Interviews & Feedback
    start_date = (end_date - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    # 1-day range for Outreach, LinkedIn, Automations, and Clicks
    daily_start_date = (end_date - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    logger.info(f"Generating Marketing Report: Weekly from {start_date.date()}, Daily from {daily_start_date.date()}")

    # 2. Query 7-Day Interview & Candidate Data
    interviews_query = db.query(
        CandidateORM.id,
        CandidateORM.full_name,
        CandidateORM.email,
        func.sum(case((CandidateInterview.mode_of_interview == 'Assessment', 1), else_=0)).label('assessment_count'),
        func.sum(case((CandidateInterview.type_of_interview == 'Recruiter Call', 1), else_=0)).label('recruiter_call_count'),
        func.sum(case((CandidateInterview.type_of_interview == 'Technical', 1), else_=0)).label('technical_count'),
        func.sum(case((CandidateInterview.mode_of_interview == 'In Person', 1), else_=0)).label('onsite_count'),
        func.sum(case((CandidateInterview.feedback == 'Positive', 1), else_=0)).label('feedback_positive'),
        func.sum(case((CandidateInterview.feedback == 'Negative', 1), else_=0)).label('feedback_negative'),
    ).join(
        CandidateMarketingORM, CandidateORM.id == CandidateMarketingORM.candidate_id
    ).outerjoin(
        CandidateInterview, and_(
            CandidateInterview.candidate_id == CandidateORM.id,
            CandidateInterview.interview_date >= start_date.date(),
            CandidateInterview.interview_date <= end_date.date()
        )
    ).filter(
        CandidateMarketingORM.status == 'active'
    ).group_by(
        CandidateORM.id, CandidateORM.full_name, CandidateORM.email
    ).all()

    # 3. Query Daily Job Clicks
    job_clicks_raw = db.query(
        AuthUserORM.uname,
        func.sum(JobLinkClicksORM.click_count).label('total_clicks')
    ).join(
        JobLinkClicksORM, JobLinkClicksORM.authuser_id == AuthUserORM.id
    ).filter(
        JobLinkClicksORM.last_clicked_at >= daily_start_date,
        JobLinkClicksORM.last_clicked_at <= end_date
    ).group_by(
        AuthUserORM.uname
    ).all()
    click_mapping = {row.uname.lower(): int(row.total_clicks or 0) for row in job_clicks_raw if row.uname}

    # 4. Query Daily Outreach & Automations (Workflow IDs 1, 3, 6, 7, 9, 10)
    outreach_logs = db.query(AutomationWorkflowLogORM).filter(
        AutomationWorkflowLogORM.workflow_id.in_([1, 3, 6, 7, 9, 10]),
        AutomationWorkflowLogORM.created_at >= daily_start_date
    ).all()

    # Active Candidate Mapping for logs
    active_candidates = db.query(CandidateORM).join(
        CandidateMarketingORM, CandidateORM.id == CandidateMarketingORM.candidate_id
    ).filter(CandidateMarketingORM.status == 'active').all()
    email_to_cand_id = {c.email.lower(): c.id for c in active_candidates if c.email}

    outreach_dict = {}
    portal_dict = {}
    for log in outreach_logs:
        params = log.parameters_used or {}
        cand_id = params.get('candidate_id')
        if not cand_id:
            ekey = params.get('email') or params.get('username')
            if ekey:
                cand_id = email_to_cand_id.get(ekey.lower())
        
        if not cand_id:
            continue
            
        if log.workflow_id in [1, 3, 6, 7]: # Outreach types
            outreach_dict[cand_id] = outreach_dict.get(cand_id, 0) + 1
        elif log.workflow_id in [9, 10]: # Portal Automations (LinkedIn EA, etc)
            portal_dict[cand_id] = portal_dict.get(cand_id, 0) + 1

    # 5. Combine and Sort A-Z
    final_candidates = []
    total_interviews = 0
    total_clicks = 0

    for row in interviews_query:
        cand_id = row.id
        cand_clicks = click_mapping.get(row.full_name.lower(), 0) or click_mapping.get(row.email.lower(), 0)
        
        total_interviews += (row.recruiter_call_count + row.technical_count + row.onsite_count + row.assessment_count)
        total_clicks += cand_clicks

        final_candidates.append({
            'full_name': row.full_name,
            'outreach_count': outreach_dict.get(cand_id, 0),
            'linkedin_easy_apply_count': portal_dict.get(cand_id, 0) if portal_dict.get(cand_id, 0) > 0 else 0,
            'job_portal_automation_count': portal_dict.get(cand_id, 0),
            'job_clicks': cand_clicks,
            'assessment_count': int(row.assessment_count or 0),
            'recruiter_call_count': int(row.recruiter_call_count or 0),
            'technical_count': int(row.technical_count or 0),
            'onsite_count': int(row.onsite_count or 0),
            'total_interviews': int(row.recruiter_call_count + row.technical_count + row.onsite_count + row.assessment_count),
            'feedback_positive': int(row.feedback_positive or 0),
            'feedback_negative': int(row.feedback_negative or 0),
            'feedback_pending': int(row.recruiter_call_count + row.technical_count + row.onsite_count + row.assessment_count) - int(row.feedback_positive or 0) - int(row.feedback_negative or 0)
        })

    # Sort A-Z by full_name
    final_candidates.sort(key=lambda x: x['full_name'])

    return {
        "status": "success",
        "candidates": final_candidates,
        "summary": {
            "total_candidates": len(final_candidates),
            "total_interviews": total_interviews,
            "total_clicks": total_clicks,
            "start_date": start_date.strftime('%B %d, %Y'),
            "end_date": end_date.strftime('%B %d, %Y')
        }
    }

def send_email_with_retry(html_content: str, max_retries: int = 3) -> bool:
    """
    Robust email sending with SMTP/SSL fallback and retries.
    """
    for attempt in range(max_retries):
        try:
            email_user = os.getenv("REPORT_EMAIL_USER")
            email_pass = os.getenv("REPORT_EMAIL_PASS")
            smtp_server = os.getenv("MAIL_SERVER", "smtp.gmail.com")
            smtp_port = int(os.getenv("REPORT_SMTP_PORT", os.getenv("MAIL_PORT", 587)))
            recipients_raw = os.getenv("MARKETING_REPORT_RECIPIENTS", "")
            
            if not all([email_user, email_pass, recipients_raw]):
                logger.error("Email credentials or recipients missing in .env")
                return False
                
            recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
            
            # Create Message
            msg = MIMEMultipart()
            msg['From'] = email_user
            msg['To'] = ", ".join(recipients)
            msg['Subject'] = f"WBL Marketing Report - {datetime.now().strftime('%B %d, %Y')}"
            msg['Date'] = formatdate(localtime=True)
            msg['Message-ID'] = make_msgid()
            
            msg.attach(MIMEText("Marketing Dashboard", 'plain'))
            msg.attach(MIMEText(html_content, 'html'))

            # Dispatch with SSL/TLS detection
            logger.info(f"Attempt {attempt+1}: Sending report via {smtp_server}:{smtp_port}")
            
            if smtp_port == 465:
                with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=60) as server:
                    server.login(email_user, email_pass)
                    server.sendmail(email_user, recipients, msg.as_string())
            else:
                with smtplib.SMTP(smtp_server, smtp_port, timeout=60) as server:
                    server.starttls()
                    server.login(email_user, email_pass)
                    server.sendmail(email_user, recipients, msg.as_string())

            logger.info("Report sent successfully!")
            return True
        except Exception as e:
            logger.warning(f"Attempt {attempt+1} failed: {e}")
            if attempt == max_retries - 1:
                logger.error("All email retry attempts failed.")
                return False
    return False

def send_weekly_marketing_report(db: Session) -> Dict[str, Any]:
    """
    Core function to trigger the report generation and dispatch it via SMTP.
    Used by the Backend internal scheduler.
    """
    try:
        # Note: In the standalone architecture, we use the API to serve this data.
        # But this function remains for the internal WBL Scheduler trigger.
        # We explicitly DO NOT send the email here. We just return a mock success
        # to properly close out the backend scheduler loop, while the external 
        # python script on the Windows machine does the actual email sending.
        return {
            "status": "success",
            "records_processed": 0,
            "message": "Report dispatch is handled by standalone external worker."
        }
    except Exception as e:
        logger.error(f"Failed to send marketing report from Backend: {e}")
        return {"status": "error", "message": str(e)}

# Alias for backward compatibility with existing routes
get_weekly_report_data = generate_weekly_marketing_report