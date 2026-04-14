"""
Dynamic Weekly Marketing Report Service
Generates weekly reports based on database queries and sends professional emails
"""
import logging
import smtplib
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

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
from fapi.utils.email_utils import get_email_config, send_html_email, validate_email_config

logger = logging.getLogger(__name__)


def generate_weekly_marketing_report(db: Session) -> Dict[str, Any]:
    """
    Generate dynamic weekly marketing report HTML based on database queries
    Returns:
        Dict with 'html' and 'count' (number of candidates)
    """
    # Calculate date range (last 7 days) in UTC
    end_date = datetime.now(timezone.utc)
    start_date = (end_date - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)

    logger.info(f"Generating weekly report for {start_date} to {end_date}")

    # Query 1: Get interviews data
    interviews_query = db.query(
        CandidateORM.id,
        CandidateORM.full_name,
        CandidateORM.email,
        func.count(CandidateInterview.id).label('total_interviews'),
        func.sum(case((CandidateInterview.mode_of_interview == 'Assessment', 1), else_=0)).label('assessment_count'),
        func.sum(case((CandidateInterview.type_of_interview == 'Recruiter Call', 1), else_=0)).label('recruiter_call_count'),
        func.sum(case((CandidateInterview.type_of_interview == 'Technical', 1), else_=0)).label('technical_count'),
        func.sum(case((CandidateInterview.mode_of_interview == 'In Person', 1), else_=0)).label('onsite_count'),
        func.sum(case((CandidateInterview.feedback == 'Positive', 1), else_=0)).label('feedback_positive'),
        func.sum(case((CandidateInterview.feedback == 'Negative', 1), else_=0)).label('feedback_negative'),
        func.sum(case((CandidateInterview.feedback == 'Pending', 1), else_=0)).label('feedback_pending'),
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

    # Query 2: Get job clicks joined with authuser emails
    # 1. Filtered by the report date range (last_clicked_at)
    # 2. Counting unique job roles (records) instead of summing all repeated clicks
    job_clicks_raw = db.query(
        AuthUserORM.uname,
        func.count(JobLinkClicksORM.id).label('total_clicks')
    ).join(
        JobLinkClicksORM, JobLinkClicksORM.authuser_id == AuthUserORM.id
    ).filter(
        JobLinkClicksORM.last_clicked_at >= start_date,
        JobLinkClicksORM.last_clicked_at <= end_date
    ).group_by(
        AuthUserORM.uname
    ).all()
    
    click_mapping = {}
    for email, count in job_clicks_raw:
        if email:
            click_mapping[email.lower()] = count

    # Query 3: Get outreach data (Workflow IDs 1, 3, 4, 6, 7, 8, 9, 10)
    # 1: Daily Vendor Outreach, 3: Weekly Vendor Outreach, 6: Cold Intro, 8: LinkedIn Non-Easy Extraction, 9: Hiring Cafe, 10: Raw_Positions_Auto_Apply
    outreach_logs = db.query(AutomationWorkflowLogORM).filter(
        AutomationWorkflowLogORM.workflow_id.in_([1, 3, 4, 6, 7, 8, 9, 10]),
        AutomationWorkflowLogORM.created_at >= start_date
    ).all()

    # Get all active candidates to build an email mapping
    candidates_for_mapping = db.query(CandidateORM).join(
        CandidateMarketingORM, CandidateORM.id == CandidateMarketingORM.candidate_id
    ).filter(CandidateMarketingORM.status == 'active').all()
    
    # Email to Candidate ID mapping
    email_to_cand_id = {c.email.lower(): c.id for c in candidates_for_mapping if c.email}
    
    # Also check marketing email for each candidate
    marketing_records = db.query(CandidateMarketingORM).filter(CandidateMarketingORM.status == 'active').all()
    for mc in marketing_records:
        if mc.email:
            email_to_cand_id[mc.email.lower()] = mc.candidate_id

    # Map outreach logs to candidates
    outreach_dict = {}  # Email Outreach (1, 3, 6, 10)
    portal_automation_dict = {}  # Job Portal Automations (7, 9)
    
    for log in outreach_logs:
        params = log.parameters_used or {}
        cand_id = params.get('candidate_id')
        
        # Robust mapping: If no candidate_id, try email or usernames
        if not cand_id:
            email_key = params.get('email') or params.get('campaign_username') or params.get('username') or params.get('linkedin_username')
            if email_key:
                cand_id = email_to_cand_id.get(str(email_key).strip().lower())
        
        if cand_id:
            c_id = int(cand_id)
            records = log.records_processed or 0
            
            # Workflow 1 (Daily Vendor Outreach), 10 (Raw_Positions_Auto_Apply) are grouped in Outreach
            if log.workflow_id in [1, 3, 6, 10]:
                outreach_dict[c_id] = outreach_dict.get(c_id, 0) + records
            elif log.workflow_id in [7, 9]:
                portal_automation_dict[c_id] = portal_automation_dict.get(c_id, 0) + records

    # Query 4: Get ALL Linkedin Easy Apply activity (Playwright or Extension)
    linkedin_activity_query = db.query(
        JobActivityLogORM.candidate_id,
        JobActivityLogORM.notes,
        JobActivityLogORM.activity_count
    ).join(
        JobTypeORM, JobActivityLogORM.job_type_id == JobTypeORM.id
    ).filter(
        JobTypeORM.name.ilike('%Linkedin Easy Apply%'),
        JobActivityLogORM.activity_date >= start_date.date(),
        JobActivityLogORM.activity_date <= end_date.date()
    ).all()

    linkedin_dict = {}
    for row in linkedin_activity_query:
        cand_id = row.candidate_id
        
        # Fallback mapping: If no candidate_id, try to find candidate name in notes
        if not cand_id and row.notes:
            notes_lower = row.notes.lower()
            for email_key, c_id in email_to_cand_id.items():
                # Check for email in notes OR check for common name parts
                if email_key in notes_lower:
                    cand_id = c_id
                    break
            
            if not cand_id:
                # Try name mapping if email didn't work
                for c in candidates_for_mapping:
                    if c.full_name and c.full_name.lower() in notes_lower:
                        cand_id = c.id
                        break
        
        if cand_id:
            linkedin_dict[int(cand_id)] = linkedin_dict.get(int(cand_id), 0) + (row.activity_count or 0)

    # Combine the data
    candidates_data = []
    for interview_row in interviews_query:
        # Robust Job Clicks Mapping: Check candidate email and marketing email
        cand_click_count = 0
        if interview_row.email and interview_row.email.lower() in click_mapping:
            cand_click_count += click_mapping[interview_row.email.lower()]
            
        # Also check if marketing email is different and has clicks
        marketing_email = next((m.email for m in marketing_records if m.candidate_id == interview_row.id), None)
        if marketing_email and marketing_email.lower() != (interview_row.email or "").lower():
            if marketing_email.lower() in click_mapping:
                cand_click_count += click_mapping[marketing_email.lower()]

        # User wants the TOTAL in the report to match exactly the sum of the visible sub-columns
        # to avoid mismatch with hidden interview types (like Prep Call, HR, etc.)
        total_interviews_visible = (
            (interview_row.assessment_count or 0) +
            (interview_row.recruiter_call_count or 0) +
            (interview_row.technical_count or 0) +
            (interview_row.onsite_count or 0)
        )
        job_clicks = cand_click_count
        outreach_count = outreach_dict.get(interview_row.id, 0)
        linkedin_applies = linkedin_dict.get(interview_row.id, 0)

        positive_fb = interview_row.feedback_positive or 0
        negative_fb = interview_row.feedback_negative or 0
        calculated_pending = max(0, total_interviews_visible - positive_fb - negative_fb)

        candidates_data.append({
            'id': interview_row.id,
            'full_name': interview_row.full_name,
            'email': interview_row.email,
            'total_interviews': total_interviews_visible,
            'assessment_count': interview_row.assessment_count or 0,
            'recruiter_call_count': interview_row.recruiter_call_count or 0,
            'technical_count': interview_row.technical_count or 0,
            'onsite_count': interview_row.onsite_count or 0,
            'feedback_positive': positive_fb,
            'feedback_negative': negative_fb,
            'feedback_pending': calculated_pending,
            'job_clicks': job_clicks,
            'outreach_count': outreach_count,
            'linkedin_easy_apply_count': linkedin_applies,
            'job_portal_automation_count': portal_automation_dict.get(interview_row.id, 0)
        })

    # Sort candidates alphabetically by name
    candidates_data.sort(key=lambda x: (x['full_name'] or "").lower())

    # Calculate global total UNIQUE clicks for the specific period to match summary cards
    global_total_clicks = db.query(func.count(JobLinkClicksORM.id)).filter(
        JobLinkClicksORM.last_clicked_at >= start_date,
        JobLinkClicksORM.last_clicked_at <= end_date
    ).scalar() or 0

    logger.info(f"Report generated for {len(candidates_data)} active marketing candidates.")

    # Generate HTML report with a modern dashboard aesthetic
    html_content = f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f3f4f6; margin: 0; padding: 40px 20px;">
        <div style="max-width: 950px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05); overflow: hidden;">
            
            <!-- Header -->
            <div style="background-color: #1f2937; color: #ffffff; padding: 30px; text-align: center;">
                <h1 style="margin: 0; font-size: 24px; font-weight: 600; letter-spacing: 0.5px;">Weekly Marketing Report</h1>
                <p style="margin: 10px 0 0 0; font-size: 14px; color: #9ca3af;">{start_date.strftime('%B %d')} &mdash; {end_date.strftime('%B %d, %Y')}</p>
            </div>
            
            <div style="padding: 30px;">
    """

    # Show all active marketing candidates in the report, including those with 0 activity
    candidates_with_activity = candidates_data

    if not candidates_with_activity:
        html_content += """
                <div style="text-align: center; padding: 40px 20px; background-color: #f9fafb; border-radius: 6px; border: 1px dashed #d1d5db;">
                    <p style="margin: 0; color: #6b7280; font-size: 14px;">No candidate activity recorded during this period.</p>
                </div>
        """
    else:
        # Calculate summary stats
        total_candidates = len(candidates_with_activity)
        total_interviews = sum(row['total_interviews'] for row in candidates_with_activity)
        total_clicks = global_total_clicks

        # Summary Boxes
        html_content += f"""
                <table width="100%" cellpadding="0" cellspacing="5" style="margin-bottom: 30px;">
                    <tr>
                        <td width="25%" style="background-color: #f9fafb; padding: 20px 10px; text-align: center; border-radius: 6px; border: 1px solid #e5e7eb;">
                            <div style="font-size: 28px; font-weight: bold; color: #3b82f6; margin-bottom: 4px;">{total_candidates}</div>
                            <div style="font-size: 11px; color: #6b7280; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Candidates</div>
                        </td>
                        <td width="25%" style="background-color: #f9fafb; padding: 20px 10px; text-align: center; border-radius: 6px; border: 1px solid #e5e7eb;">
                            <div style="font-size: 28px; font-weight: bold; color: #10b981; margin-bottom: 4px;">{total_interviews}</div>
                            <div style="font-size: 11px; color: #6b7280; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Interviews</div>
                        </td>
                        <td width="25%" style="background-color: #f9fafb; padding: 20px 10px; text-align: center; border-radius: 6px; border: 1px solid #e5e7eb;">
                            <div style="font-size: 28px; font-weight: bold; color: #f59e0b; margin-bottom: 4px;">{total_clicks}</div>
                            <div style="font-size: 11px; color: #6b7280; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Job Clicks</div>
                        </td>
                        <td width="25%" style="background-color: #f9fafb; padding: 15px 10px; text-align: left; border-radius: 6px; border: 1px solid #e5e7eb; vertical-align: top;">
                            <div style="font-size: 11px; font-weight: 600; color: #8b5cf6; margin-bottom: 6px; text-align: center; text-transform: uppercase; letter-spacing: 0.5px;">Daily Automations</div>
                            <ul style="font-size: 10px; color: #4b5563; margin: 0; padding-left: 20px; line-height: 1.4;">
                                <li style="margin-bottom: 2px;">LinkedIn</li>
                                <li style="margin-bottom: 2px;">Vendor Mass Emails</li>
                                <li>Manual Applications</li>
                            </ul>
                        </td>
                    </tr>
                </table>

                <div style="overflow-x: auto;">
                    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: separate; border-spacing: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 10px; border: 1px solid #e2e8f0; border-radius: 12px 12px 0 0;">
                        <thead>
                            <tr style="color: #ffffff; font-weight: 700;">
                                <th rowspan="2" style="padding: 15px 10px; text-align: center; vertical-align: middle; background-color: #3b5998; border-right: 1px solid #ffffff; width: 14%; border-top-left-radius: 11px; font-size: 11px;">Candidate</th>
                                <th colspan="4" style="padding: 12px; text-align: center; background-color: #4d71bb; border-right: 1px solid #ffffff; text-transform: uppercase; letter-spacing: 1.5px; font-size: 11px;">APPLICATIONS</th>
                                <th colspan="4" style="padding: 12px; text-align: center; background-color: #6d8acb; border-right: 1px solid #ffffff; text-transform: uppercase; letter-spacing: 1.5px; font-size: 11px;">INTERVIEWS</th>
                                <th rowspan="2" style="padding: 15px 10px; text-align: center; vertical-align: middle; background-color: #38ada9; border-right: 1px solid #ffffff; width: 6%; font-size: 11px;">Total</th>
                                <th colspan="3" style="padding: 12px; text-align: center; background-color: #8da3dc; border-right: 1px solid #ffffff; text-transform: uppercase; letter-spacing: 1.5px; font-size: 11px; border-top-right-radius: 11px;">FEEDBACK</th>
                            </tr>
                            <tr style="background-color: #f0f4f8; color: #334e81; font-weight: 700; text-transform: uppercase; font-size: 9px;">
                                <th style="padding: 12px 4px; text-align: center; border-right: 1px solid #e2e8f0; line-height: 1.3;">EMAIL<br>OUTREACH</th>
                                <th style="padding: 12px 4px; text-align: center; border-right: 1px solid #e2e8f0; line-height: 1.3;">LINKEDIN<br>EASYAPPLY</th>
                                <th style="padding: 12px 4px; text-align: center; border-right: 1px solid #e2e8f0; line-height: 1.3;">JOB PORTAL<br>AUTOMATIONS</th>
                                <th style="padding: 12px 4px; text-align: center; border-right: 1px solid #e2e8f0; line-height: 1.3;">JOB<br>LISTINGS<br>CLICKS</th>
                                <th style="padding: 12px 4px; text-align: center; border-right: 1px solid #e2e8f0; line-height: 1.3;">ASSESSMENTS</th>
                                <th style="padding: 12px 4px; text-align: center; border-right: 1px solid #e2e8f0; line-height: 1.3;">RECRUITER</th>
                                <th style="padding: 12px 4px; text-align: center; border-right: 1px solid #e2e8f0; line-height: 1.3;">TECHNICAL</th>
                                <th style="padding: 12px 4px; text-align: center; border-right: 1px solid #e2e8f0; line-height: 1.3;">ONSITE</th>
                                <th style="padding: 12px 4px; text-align: center; border-right: 1px solid #e2e8f0; line-height: 1.3; color: #16a34a;">POSITIVE</th>
                                <th style="padding: 12px 4px; text-align: center; border-right: 1px solid #e2e8f0; line-height: 1.3; color: #ef4444;">NEGATIVE</th>
                                <th style="padding: 12px 4px; text-align: center; border-right: 1px solid #e2e8f0; line-height: 1.3; color: #d97706;">PENDING</th>
                            </tr>
                        </thead>
                        <tbody>
        """

        for idx, row in enumerate(candidates_with_activity):
            row_bg = "#ffffff" if idx % 2 == 0 else "#f8fafc"
            html_content += f"""
                            <tr style="background-color: {row_bg};">
                                <td style="padding: 12px 16px; border-bottom: 1px solid #e2e8f0; border-right: 1px solid #e2e8f0; color: #1e293b; font-weight: 600;">{row['full_name']}</td>
                                <td style="padding: 12px 8px; border-bottom: 1px solid #e2e8f0; border-right: 1px solid #e2e8f0; text-align: center; color: #334155; font-weight: bold;">{row['outreach_count'] or '-'}</td>
                                <td style="padding: 12px 8px; border-bottom: 1px solid #e2e8f0; border-right: 1px solid #e2e8f0; text-align: center; color: #334155; font-weight: bold;">{row['linkedin_easy_apply_count'] or '-'}</td>
                                <td style="padding: 12px 8px; border-bottom: 1px solid #e2e8f0; border-right: 1px solid #e2e8f0; text-align: center; color: #334155; font-weight: bold;">{row['job_portal_automation_count'] or '-'}</td>
                                <td style="padding: 12px 8px; border-bottom: 1px solid #e2e8f0; border-right: 1px solid #e2e8f0; text-align: center; color: #ea580c; font-weight: 700;">{row['job_clicks'] or '-'}</td>
                                <td style="padding: 12px 8px; border-bottom: 1px solid #e2e8f0; border-right: 1px solid #e2e8f0; text-align: center; color: #334155; font-weight: bold;">{row['assessment_count'] or '-'}</td>
                                <td style="padding: 12px 8px; border-bottom: 1px solid #e2e8f0; border-right: 1px solid #e2e8f0; text-align: center; color: #334155; font-weight: bold;">{row['recruiter_call_count'] or '-'}</td>
                                <td style="padding: 12px 8px; border-bottom: 1px solid #e2e8f0; border-right: 1px solid #e2e8f0; text-align: center; color: #334155; font-weight: bold;">{row['technical_count'] or '-'}</td>
                                <td style="padding: 12px 8px; border-bottom: 1px solid #e2e8f0; border-right: 1px solid #e2e8f0; text-align: center; color: #334155; font-weight: bold;">{row['onsite_count'] or '-'}</td>
                                <td style="padding: 12px 8px; border-bottom: 1px solid #e2e8f0; border-right: 1px solid #e2e8f0; text-align: center; color: #0f172a; font-weight: 800; background-color: #ecfdf5;">{row['total_interviews'] or '0'}</td>
                                <td style="padding: 12px 8px; border-bottom: 1px solid #e2e8f0; border-right: 1px solid #e2e8f0; text-align: center; color: #16a34a; font-weight: bold;">{row['feedback_positive'] or '-'}</td>
                                <td style="padding: 12px 8px; border-bottom: 1px solid #e2e8f0; border-right: 1px solid #e2e8f0; text-align: center; color: #ef4444; font-weight: bold;">{row['feedback_negative'] or '-'}</td>
                                <td style="padding: 12px 8px; border-bottom: 1px solid #e2e8f0; text-align: center; color: #d97706; font-weight: bold;">{row['feedback_pending'] or '-'}</td>
                            </tr>
            """


        html_content += """
                        </tbody>
                    </table>
                </div>
        """

    html_content += f"""
            </div>
            
            <!-- Footer -->
            <div style="background-color: #f9fafb; padding: 20px; text-align: center; border-top: 1px solid #e5e7eb;">
                <p style="margin: 0; font-size: 11px; color: #9ca3af;">Automated Weekly Marketing Report</p>
                <p style="margin: 4px 0 0 0; font-size: 11px; color: #9ca3af;">Generated on {datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M')} UTC</p>
            </div>
            
        </div>
    </body>
    </html>
    """
    
    return {
        "html": html_content,
        "count": len(candidates_with_activity)
    }



def generate_weekly_marketing_report_text(db: Session) -> str:
    """
    Generate a plain-text version of the weekly marketing report
    """
    # Calculate date range (last 7 days) in UTC
    end_date = datetime.now(timezone.utc)
    start_date = (end_date - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)

    # Use the same logic as the HTML version to get candidates_data
    # (Small duplication here for simplicity, or we could refactor the query part out)
    interviews_query = db.query(
        CandidateORM.id,
        CandidateORM.full_name,
        CandidateORM.email,
        func.count(CandidateInterview.id).label('total_interviews'),
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

    total_candidates = len(interviews_query)
    total_interviews = sum(row.total_interviews or 0 for row in interviews_query)

    text_content = f"Weekly Marketing Report\n"
    text_content += f"Period: {start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}\n\n"
    text_content += f"Summary:\n"
    text_content += f"- Active Candidates: {total_candidates}\n"
    text_content += f"- Total Interviews: {total_interviews}\n\n"
    text_content += f"Candidate Activity (Top Candidates):\n"
    
    # Show candidates in alphabetical order
    sorted_candidates = sorted(interviews_query, key=lambda x: (x.full_name or "").lower())
    for row in sorted_candidates[:20]:  # Top 20 for brevity in plain text
        if row.total_interviews > 0:
            text_content += f"- {row.full_name}: {row.total_interviews} interviews\n"

    text_content += f"\nView full report in an HTML compatible email client.\n"
    text_content += f"Generated on {datetime.now(timezone.utc).strftime('%B %d, %Y at %I:%M %p')} UTC\n"

    return text_content


def send_weekly_marketing_report(db: Session) -> Dict[str, Any]:
    """
    Generate and send the weekly marketing report via email
    """
    try:
        # Generate the report versions
        report_data = generate_weekly_marketing_report(db)
        html_report = report_data.get('html')
        candidate_count = report_data.get('count', 0)
        
        # Recalculate dates for logging (consistent with internal report logic)
        end_date = datetime.now(timezone.utc)
        start_date = (end_date - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        text_report = generate_weekly_marketing_report_text(db)

        # Get email configuration
        config = get_email_config()
        admin_emails = validate_email_config(config)

        # Include the sender in the recipients so they also receive a copy
        if config['from_email'] and config['from_email'] not in admin_emails:
            admin_emails.append(config['from_email'])

        # Send emails to all recipients with a unique subject (timestamp)
        now = datetime.now(timezone.utc)
        subject = f"Weekly Marketing Report - {now.strftime('%B %d, %Y [%H:%M:%S]')} UTC"
        from_display = f"WBL Marketing <{config['from_email']}>"
        logger.info(f"Dispatching report to {admin_emails} with subject: {subject}")

        with smtplib.SMTP(config['smtp_server'], int(config['smtp_port']), timeout=60) as server:
            server.starttls()
            server.login(config['from_email'], config['password'])

            for admin_email in admin_emails:
                try:
                    logger.info(f"Attempting individual delivery to: {admin_email}")
                    send_html_email(
                        server=server,
                        from_email=from_display,
                        to_emails=[admin_email],
                        subject=subject,
                        html_content=html_report,
                        text_content=text_report
                    )
                    logger.info(f"Deliver Success: {admin_email}")
                except Exception as e:
                    logger.error(f"Deliver Failed to {admin_email}: {e}")
                    # Continue with other recipients

        return {
            "status": "success",
            "message": f"Weekly marketing report sent to {len(admin_emails)} recipients",
            "recipients": admin_emails,
            "subject": subject,
            "records_processed": candidate_count
        }

    except Exception as e:
        logger.error(f"Failed to generate/send weekly marketing report: {e}")
        return {
            "status": "error",
            "message": f"Failed to generate/send report: {str(e)}"
        }


def get_weekly_report_data(db: Session) -> Dict[str, Any]:
    """
    Get the raw data for the weekly report without sending email
    """
    try:
        report_data = generate_weekly_marketing_report(db)
        html_report = report_data.get('html')
        candidate_count = report_data.get('count', 0)

        # Get email configuration for recipients
        config = get_email_config()
        admin_emails = validate_email_config(config)

        return {
            "status": "success",
            "html_report": html_report,
            "recipients": admin_emails,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "records_processed": candidate_count
        }

    except Exception as e:
        logger.error(f"Failed to generate weekly report data: {e}")
        return {
            "status": "error",
            "message": f"Failed to generate report: {str(e)}"
        }