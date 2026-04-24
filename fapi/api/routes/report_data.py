from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import os
from fapi.db.database import get_db

router = APIRouter(prefix="/report-data", tags=["Marketing Report Data"])

# A simple API Key for security as discussed
REPORT_API_KEY = os.getenv("REPORT_API_KEY", "wbl_marketing_secret_2024")

@router.get("/")
def get_marketing_report_raw_data(
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Returns the full structured data for the professional marketing report dashboard.
    """
    if x_api_key != REPORT_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    try:
        from fapi.utils.dynamic_weekly_report_utils import (
            datetime, timezone, timedelta, func, case, and_,
            CandidateORM, CandidateMarketingORM, CandidateInterview,
            AuthUserORM, JobLinkClicksORM, AutomationWorkflowLogORM,
            JobTypeORM, JobActivityLogORM
        )
        
        # --- Time Ranges ---
        # --- Last 7 Days Logic ---
        end_date = datetime.now(timezone.utc)
        today = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Calculate exactly 7 days ago
        weekly_start_date = today - timedelta(days=7)
        
        # Labels for the report header (e.g. "April 17 - April 24, 2026")
        start_date_str = weekly_start_date.strftime('%B %d')
        end_date_str = end_date.strftime('%B %d, %Y')

        # 1. Interviews & Candidates
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
                CandidateInterview.interview_date >= weekly_start_date.date(),
                CandidateInterview.interview_date <= end_date.date()
            )
        ).filter(
            CandidateMarketingORM.status == 'active'
        ).group_by(
            CandidateORM.id, CandidateORM.full_name, CandidateORM.email
        ).all()

        # 2. Daily Job Clicks (Mapping email to count)
        job_clicks_raw = db.query(
            AuthUserORM.uname,
            func.sum(JobLinkClicksORM.click_count).label('total_clicks')
        ).join(
            JobLinkClicksORM, JobLinkClicksORM.authuser_id == AuthUserORM.id
        ).filter(
            JobLinkClicksORM.last_clicked_at >= weekly_start_date,
            JobLinkClicksORM.last_clicked_at < end_date
        ).group_by(
            AuthUserORM.uname
        ).all()
        click_mapping = {email.lower().strip(): int(count) for email, count in job_clicks_raw if email and count is not None}

        # 3. Outreach & Automations (Workflow IDs - from production):
        # Email Outreach: 1=daily_vendor_outreach, 3=weekly_vendor_outreach, 5=weekly_leads_outreach, 6=weekly_potential_leads_outreach
        # Portal Auto: 7=weekly_automation_application_engine, 10=Raw_Positions_Auto_Apply
        outreach_logs = db.query(AutomationWorkflowLogORM).filter(
            AutomationWorkflowLogORM.workflow_id.in_([1, 3, 5, 6, 7, 10]),
            AutomationWorkflowLogORM.created_at >= weekly_start_date,
            AutomationWorkflowLogORM.created_at < end_date
        ).all()

        # Email Mapping for Robust Lookup
        active_candidates = db.query(CandidateORM).join(
            CandidateMarketingORM, CandidateORM.id == CandidateMarketingORM.candidate_id
        ).filter(CandidateMarketingORM.status == 'active').all()
        email_map = {c.email.lower().strip(): c.id for c in active_candidates if c.email}

        outreach_dict = {}
        portal_dict = {}
        for log in outreach_logs:
            params = log.parameters_used or {}
            cand_id = params.get('candidate_id')
            if not cand_id:
                ekey = params.get('email') or params.get('username')
                cand_id = email_map.get(str(ekey).strip().lower()) if ekey else None
            
            if cand_id:
                c_id = int(cand_id)
                records = log.records_processed or 0
                if log.workflow_id in [1, 3, 5, 6]:
                    outreach_dict[c_id] = outreach_dict.get(c_id, 0) + records
                elif log.workflow_id in [7, 10]:
                    portal_dict[c_id] = portal_dict.get(c_id, 0) + records

        # 4. LinkedIn Easy Apply (Activity Logs)
        linkedin_activity = db.query(
            JobActivityLogORM.candidate_id,
            func.sum(func.coalesce(JobActivityLogORM.activity_count, 1)).label('total')
        ).join(
            JobTypeORM, JobActivityLogORM.job_type_id == JobTypeORM.id
        ).filter(
            JobTypeORM.name.ilike('%Linkedin%'),
            JobActivityLogORM.activity_date >= weekly_start_date.date(),
            JobActivityLogORM.activity_date < end_date.date()
        ).group_by(JobActivityLogORM.candidate_id).all()
        linkedin_dict = {int(row[0]): int(row[1]) for row in linkedin_activity if row[0]}

        # --- Assemble Results ---
        results = []
        for row in interviews_query:
            # Calculated Pending logic
            pos = int(row.feedback_positive or 0)
            neg = int(row.feedback_negative or 0)
            visible_total = (
                int(row.assessment_count or 0) + 
                int(row.recruiter_call_count or 0) + 
                int(row.technical_count or 0) + 
                int(row.onsite_count or 0)
            )
            pending = max(0, visible_total - pos - neg)
            
            c_email = (row.email or "").lower().strip()

            results.append({
                "id": row.id,
                "full_name": row.full_name,
                "email": row.email,
                "outreach_count": outreach_dict.get(row.id, 0),
                "linkedin_easy_apply_count": linkedin_dict.get(row.id, 0),
                "job_portal_automation_count": portal_dict.get(row.id, 0),
                "job_clicks": click_mapping.get(c_email, 0),
                "assessment_count": int(row.assessment_count or 0),
                "recruiter_call_count": int(row.recruiter_call_count or 0),
                "technical_count": int(row.technical_count or 0),
                "onsite_count": int(row.onsite_count or 0),
                "total_interviews": visible_total,
                "feedback_positive": pos,
                "feedback_negative": neg,
                "feedback_pending": pending
            })

        # Global Summary Stats
        global_total_clicks = db.query(func.sum(JobLinkClicksORM.click_count)).filter(
            JobLinkClicksORM.last_clicked_at >= weekly_start_date,
            JobLinkClicksORM.last_clicked_at < end_date
        ).scalar() or 0

        # Sort candidates alphabetically by name
        results.sort(key=lambda x: (x['full_name'] or "").lower())


        return {

            "status": "success",
            "summary": {
                "total_candidates": len(results),
                "total_interviews": sum(r["total_interviews"] for r in results),
                "total_clicks": int(global_total_clicks),
                "start_date": start_date_str,
                "end_date": end_date_str
            },
            "candidates": results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
