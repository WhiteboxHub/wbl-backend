"""
Dynamic Weekly Marketing Report Service
Generates weekly reports based on database queries and sends professional emails
"""
import logging
import smtplib
from datetime import datetime, timedelta
from typing import Dict, Any

from sqlalchemy import func, case, and_
from sqlalchemy.orm import Session

from fapi.db.models import (
    CandidateORM,
    CandidateMarketingORM,
    CandidateInterview,
    AuthUserORM,
    JobLinkClicksORM,
)
from fapi.utils.email_utils import get_email_config, send_html_email, validate_email_config

logger = logging.getLogger(__name__)


def generate_weekly_marketing_report(db: Session) -> str:
    """
    Generate dynamic weekly marketing report HTML based on database queries
    """
    # Calculate date range (last 7 days)
    end_date = datetime.now()
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

    # Query 2: Get job clicks data
    job_clicks_query = db.query(
        CandidateORM.id,
        func.sum(JobLinkClicksORM.click_count).label('job_clicks')
    ).outerjoin(
        AuthUserORM, func.lower(AuthUserORM.uname) == func.lower(CandidateORM.email)
    ).outerjoin(
        JobLinkClicksORM, and_(
            JobLinkClicksORM.authuser_id == AuthUserORM.id,
            JobLinkClicksORM.last_clicked_at.between(start_date, end_date)
        )
    ).group_by(
        CandidateORM.id
    ).all()

    # Create a dictionary for job clicks
    job_clicks_dict = {row.id: (row.job_clicks or 0) for row in job_clicks_query}

    # Combine the data
    candidates_data = []
    for interview_row in interviews_query:
        total_interviews = interview_row.total_interviews or 0
        job_clicks = job_clicks_dict.get(interview_row.id, 0)

        candidates_data.append({
            'full_name': interview_row.full_name,
            'email': interview_row.email,
            'total_interviews': total_interviews,
            'assessment_count': interview_row.assessment_count or 0,
            'recruiter_call_count': interview_row.recruiter_call_count or 0,
            'technical_count': interview_row.technical_count or 0,
            'job_clicks': job_clicks
        })

    logger.info(f"Report generated for {len(candidates_data)} active marketing candidates.")

    # Generate HTML report with MAXIMUM simplicity for deliverability
    # No <style> blocks, no classes, only basic inline styles
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #ffffff; margin: 0; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; border: 1px solid #dddddd; padding: 20px;">
            <div style="text-align: center; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; margin-bottom: 20px;">
                <h1 style="color: #2c3e50; margin: 0;">Weekly Marketing Report</h1>
                <p style="color: #666666; margin: 5px 0;">{start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')}</p>
            </div>
    """

    if not candidates_data:
        html_content += """
            <p style="text-align: center; padding: 20px; color: #666666;">No activity recorded during this period.</p>
        """
    else:
        # Calculate summary stats
        total_candidates = len(interviews_query)
        total_interviews = sum(row['total_interviews'] for row in candidates_data)
        total_clicks = sum(row['job_clicks'] for row in candidates_data)

        # Summary Table
        html_content += f"""
            <table width="100%" style="margin-bottom: 20px; border-collapse: collapse;">
                <tr>
                    <td style="background-color: #f8f9fa; padding: 15px; text-align: center; border: 1px solid #dddddd;">
                        <div style="font-size: 20px; font-weight: bold; color: #3498db;">{total_candidates}</div>
                        <div style="font-size: 11px; color: #666666; text-transform: uppercase;">Candidates</div>
                    </td>
                    <td style="background-color: #f8f9fa; padding: 15px; text-align: center; border: 1px solid #dddddd;">
                        <div style="font-size: 20px; font-weight: bold; color: #2ecc71;">{total_interviews}</div>
                        <div style="font-size: 11px; color: #666666; text-transform: uppercase;">Interviews</div>
                    </td>
                    <td style="background-color: #f8f9fa; padding: 15px; text-align: center; border: 1px solid #dddddd;">
                        <div style="font-size: 20px; font-weight: bold; color: #e67e22;">{total_clicks}</div>
                        <div style="font-size: 11px; color: #666666; text-transform: uppercase;">Job Clicks</div>
                    </td>
                </tr>
            </table>

            <table width="100%" style="border-collapse: collapse; border: 1px solid #eeeeee; font-size: 12px;">
                <thead>
                    <tr style="background-color: #eeeeee;">
                        <th style="padding: 8px; text-align: left; border-bottom: 1px solid #dddddd;">Candidate</th>
                        <th style="padding: 8px; text-align: center; border-bottom: 1px solid #dddddd;">Assm.</th>
                        <th style="padding: 8px; text-align: center; border-bottom: 1px solid #dddddd;">Recr.</th>
                        <th style="padding: 8px; text-align: center; border-bottom: 1px solid #dddddd;">Tech.</th>
                        <th style="padding: 8px; text-align: center; border-bottom: 1px solid #dddddd;">Total</th>
                        <th style="padding: 8px; text-align: center; border-bottom: 1px solid #dddddd;">Clicks</th>
                    </tr>
                </thead>
                <tbody>
        """

        for row in candidates_data:
            click_color = "#856404" if row['job_clicks'] > 0 else "#333333"
            row_bg = "#ffffff"
            
            html_content += f"""
                    <tr style="background-color: {row_bg};">
                        <td style="padding: 8px; border-bottom: 1px solid #eeeeee;"><b>{row['full_name']}</b></td>
                        <td style="padding: 8px; border-bottom: 1px solid #eeeeee; text-align: center;">{row['assessment_count'] or '-'}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #eeeeee; text-align: center;">{row['recruiter_call_count'] or '-'}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #eeeeee; text-align: center;">{row['technical_count'] or '-'}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #eeeeee; text-align: center;"><b>{row['total_interviews'] or '0'}</b></td>
                        <td style="padding: 8px; border-bottom: 1px solid #eeeeee; text-align: center; color: {click_color};"><b>{row['job_clicks'] or '0'}</b></td>
                    </tr>
            """

        html_content += """
                </tbody>
            </table>
        """

    html_content += f"""
            <div style="margin-top: 20px; text-align: center; font-size: 10px; color: #999999; border-top: 1px solid #eeeeee; padding-top: 10px;">
                <p>Automated Weekly Marketing Report | Generated on {datetime.now().strftime('%B %d, %H:%M')}</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content


def generate_weekly_marketing_report_text(db: Session) -> str:
    """
    Generate a plain-text version of the weekly marketing report
    """
    # Calculate date range (last 7 days)
    end_date = datetime.now()
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
    
    # Show candidates with activity first
    sorted_candidates = sorted(interviews_query, key=lambda x: x.total_interviews or 0, reverse=True)
    for row in sorted_candidates[:20]:  # Top 20 for brevity in plain text
        if row.total_interviews > 0:
            text_content += f"- {row.full_name}: {row.total_interviews} interviews\n"

    text_content += f"\nView full report in an HTML compatible email client.\n"
    text_content += f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}\n"

    return text_content


def send_weekly_marketing_report(db: Session) -> Dict[str, Any]:
    """
    Generate and send the weekly marketing report via email
    """
    try:
        # Generate the report versions
        html_report = generate_weekly_marketing_report(db)
        text_report = generate_weekly_marketing_report_text(db)

        # Get email configuration
        config = get_email_config()
        admin_emails = validate_email_config(config)

        # Include the sender in the recipients so they also receive a copy
        if config['from_email'] and config['from_email'] not in admin_emails:
            admin_emails.append(config['from_email'])

        # Send emails to each recipient individually for maximum reliability
        subject = f"Weekly Marketing Report - {datetime.now().strftime('%B %d, %Y')}"

        with smtplib.SMTP(config['smtp_server'], int(config['smtp_port'])) as server:
            server.starttls()
            server.login(config['from_email'], config['password'])

            for admin_email in admin_emails:
                try:
                    logger.info(f"Attempting to send Weekly Report to {admin_email}")
                    send_html_email(
                        server=server,
                        from_email=config['from_email'],
                        to_emails=[admin_email],
                        subject=subject,
                        html_content=html_report,
                        text_content=text_report
                    )
                    logger.info(f"Successfully delivered Weekly Report to {admin_email}")
                except Exception as e:
                    logger.error(f"Failed to deliver to {admin_email}: {e}")
                    # Log specific error but continue with others

        return {
            "status": "success",
            "message": f"Weekly marketing report sent to {len(admin_emails)} recipients",
            "recipients": admin_emails,
            "subject": subject
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
        html_report = generate_weekly_marketing_report(db)

        # Get email configuration for recipients
        config = get_email_config()
        admin_emails = validate_email_config(config)

        return {
            "status": "success",
            "html_report": html_report,
            "recipients": admin_emails,
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to generate weekly report data: {e}")
        return {
            "status": "error",
            "message": f"Failed to generate report: {str(e)}"
        }