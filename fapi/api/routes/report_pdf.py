from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from fastapi.responses import Response
import os
import io
from jinja2 import Template
from datetime import datetime, timezone
from xhtml2pdf import pisa
from fapi.db.database import get_db
from fapi.api.routes.report_data import get_marketing_report_raw_data

router = APIRouter(tags=["Marketing Report PDF"])

# Use the same API KEY for the link
REPORT_API_KEY = os.getenv("REPORT_API_KEY", "wbl_marketing_secret_2024")

def generate_pdf_from_html(html_content):
    """Converts HTML to PDF bytes."""
    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=pdf_buffer)
    if pisa_status.err:
        return None
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()

def format_html(data):
    """Matches the exact template used in the email."""
    if not data or data.get("status") != "success":
        return ""
    candidates = data.get("candidates", [])
    summary = data.get("summary", {})
    now_str = datetime.now(timezone.utc).strftime('%B %d, %Y')
    
    template_html = """
    <html>
    <head>
        <style>
            @page { size: A4 landscape; margin: 1cm; }
            body { font-family: Arial, sans-serif; background-color: #ffffff; margin: 0; padding: 0; color: #333; }
            table { border-collapse: collapse; width: 100%; }
            th { border: 1pt solid #ffffff; padding: 8pt; font-size: 7pt; text-transform: uppercase; background-color: #3b5998; color: #ffffff; }
            td { border: 1pt solid #e2e8f0; padding: 8pt; font-size: 7pt; text-align: center; }
            .header { background-color: #1f2937; color: #ffffff; padding: 20pt; text-align: center; margin-bottom: 20pt; }
            .summary-box { background-color: #f9fafb; padding: 10pt; text-align: center; border: 1pt solid #e5e7eb; }
        </style>
    </head>
    <body style="margin: 0; padding: 0;">
        <div class="header">
            <h1 style="margin: 0; font-size: 18pt;">Weekly Marketing Report</h1>
            <p style="margin: 5pt 0 0 0; font-size: 10pt; color: #9ca3af;">{{ summary.start_date }}{% if summary.end_date %} &mdash; {{ summary.end_date }}{% endif %}</p>
        </div>
        
        <div style="padding: 0 20pt;">
            <table width="100%" cellpadding="0" cellspacing="5" style="margin-bottom: 20pt; border: none;">
                <tr>
                    <td class="summary-box">
                        <div style="font-size: 16pt; font-weight: bold; color: #3b82f6;">{{ summary.total_candidates }}</div>
                        <div style="font-size: 8pt; color: #6b7280; text-transform: uppercase;">Candidates</div>
                    </td>
                    <td class="summary-box">
                        <div style="font-size: 16pt; font-weight: bold; color: #10b981;">{{ summary.total_interviews }}</div>
                        <div style="font-size: 8pt; color: #6b7280; text-transform: uppercase;">Interviews</div>
                    </td>
                    <td class="summary-box">
                        <div style="font-size: 16pt; font-weight: bold; color: #f59e0b;">{{ summary.total_clicks }}</div>
                        <div style="font-size: 8pt; color: #6b7280; text-transform: uppercase;">Job Clicks</div>
                    </td>
                </tr>
            </table>

            <table>
                <thead>
                    <tr>
                        <th rowspan="2" width="12%">Candidate</th>
                        <th colspan="4">APPLICATIONS</th>
                        <th colspan="4">INTERVIEWS</th>
                        <th rowspan="2" width="5%">Total</th>
                        <th colspan="3">FEEDBACK</th>
                    </tr>
                    <tr style="background-color: #f0f4f8;">
                        <th style="color: #333; background-color: #f0f4f8;">EMAIL</th>
                        <th style="color: #333; background-color: #f0f4f8;">LINKEDIN</th>
                        <th style="color: #333; background-color: #f0f4f8;">AUTO</th>
                        <th style="color: #333; background-color: #f0f4f8;">CLICKS</th>
                        <th style="color: #333; background-color: #f0f4f8;">ASSESS</th>
                        <th style="color: #333; background-color: #f0f4f8;">RECRUIT</th>
                        <th style="color: #333; background-color: #f0f4f8;">TECH</th>
                        <th style="color: #333; background-color: #f0f4f8;">ONSITE</th>
                        <th style="color: #16a34a; background-color: #f0f4f8;">POS</th>
                        <th style="color: #ef4444; background-color: #f0f4f8;">NEG</th>
                        <th style="color: #d97706; background-color: #f0f4f8;">PEND</th>
                    </tr>
                </thead>
                <tbody>
                    {% for c in candidates %}
                    <tr style="background-color: {{ '#ffffff' if loop.index0 % 2 == 0 else '#fcfcfc' }};">
                        <td style="text-align: left; font-weight: bold;">{{ c.full_name }}</td>
                        <td>{{ c.outreach_count or '0' }}</td>
                        <td>{{ c.linkedin_easy_apply_count or '0' }}</td>
                        <td>{{ c.job_portal_automation_count or '0' }}</td>
                        <td style="color: #ea580c; font-weight: bold;">{{ c.job_clicks or '0' }}</td>
                        <td>{{ c.assessment_count or '0' }}</td>
                        <td>{{ c.recruiter_call_count or '0' }}</td>
                        <td>{{ c.technical_count or '0' }}</td>
                        <td>{{ c.onsite_count or '0' }}</td>
                        <td style="background-color: #f0fff0; font-weight: bold;">{{ c.total_interviews or '0' }}</td>
                        <td style="color: #16a34a;">{{ c.feedback_positive or '0' }}</td>
                        <td style="color: #ef4444;">{{ c.feedback_negative or '0' }}</td>
                        <td style="color: #d97706;">{{ c.feedback_pending or '0' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            
            <div style="margin-top: 30pt; text-align: center; font-size: 8pt; color: #999;">
                Whitebox Learning Audit System • Generated on {{ now_str }}
            </div>
        </div>
    </body>
    </html>
    """
    return Template(template_html).render(candidates=candidates, summary=summary, now_str=now_str)

# Defined with and without trailing slash for compatibility
@router.get("/report-pdf")
@router.get("/report-pdf/")
def download_report_pdf(key: str = Query(..., alias="key"), db: Session = Depends(get_db)):
    if key != REPORT_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    try:
        data = get_marketing_report_raw_data(x_api_key=key, db=db)
        html_content = format_html(data)
        pdf_content = generate_pdf_from_html(html_content)
        if not pdf_content:
            raise Exception("PDF generation failed")
            
        filename = f"Marketing_Report_{datetime.now().strftime('%Y-%m-%d')}.pdf"
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
