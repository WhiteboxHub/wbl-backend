import smtplib
import os
import sys
from datetime import datetime, date
from pathlib import Path

# Ensure wbl-backend is in the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fapi.db.database import SessionLocal
from fapi.db.models import ApplicationReportORM
from fapi.mail.templets.application_report_email import get_ats_daily_report_email
from fapi.utils.email_utils import send_html_email, get_email_config

def run_daily_report():
    db = SessionLocal()
    try:
        today = date.today()

        # Query all records submitted today
        records = db.query(ApplicationReportORM).filter(
            ApplicationReportORM.submitted_at >= today
        ).all()

        if not records:
            print(f"No applications submitted on {today}. Skipping email.")
            return

        # Compute totals
        total_apps     = len(records)
        total_fields   = sum(r.total_fields for r in records)
        total_autofill = sum(r.autofill_fields for r in records)
        total_llm      = sum(r.llm_fields for r in records)
        total_human    = sum(r.human_fields for r in records)
        overall_auto   = round(((total_autofill + total_llm) / total_fields) * 100, 2) if total_fields else 0

        # Build table rows
        table_rows = "".join(f"""
            <tr>
                <td>{r.candidate_name}</td><td>{r.company_name}</td>
                <td>{r.ats_platform}</td><td>{r.total_fields}</td>
                <td>{r.autofill_fields}</td><td>{r.llm_fields}</td>
                <td>{r.human_fields}</td><td>{r.automation_rate}%</td>
            </tr>""" for r in records)

        html = get_ats_daily_report_email(
            total_apps, total_fields, total_autofill,
            total_llm, total_human, overall_auto, table_rows
        )

        # Send using EXISTING email infrastructure
        config = get_email_config()
        subject = f"CLI Daily ATS Report – {today.strftime('%Y-%m-%d')}"

        with smtplib.SMTP(config['smtp_server'], int(config['smtp_port'])) as server:
            server.starttls()
            server.login(config['from_email'], config['password'])
            send_html_email(
                server=server,
                from_email=config['from_email'],
                to_emails=[config['to_admin_email']],
                subject=subject,
                html_content=html
            )

        print(f"Report sent: {total_apps} applications for {today}")

    except Exception as e:
        print(f"Failed to send daily report: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_daily_report()
