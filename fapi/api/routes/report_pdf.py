from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from fastapi.responses import Response
import os
from fpdf import FPDF
from datetime import datetime, timezone
from fapi.db.database import get_db
from fapi.api.routes.report_data import get_marketing_report_raw_data

router = APIRouter(tags=["Marketing Report PDF"])

REPORT_API_KEY = os.getenv("REPORT_API_KEY", "wbl_marketing_secret_2024")


def generate_report_pdf(data):
    """
    Generates a landscape A4 PDF with 13-column marketing report using fpdf2.
    Returns a FastAPI Response object ready to serve as a file download.
    """
    summary = data.get("summary", {})
    candidates = data.get("candidates", [])
    now_str = datetime.now(timezone.utc).strftime('%B %d, %Y')

    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()

    # --- Header ---
    pdf.set_fill_color(31, 41, 55)
    pdf.rect(0, 0, 297, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_y(10)
    pdf.cell(0, 10, "Weekly Marketing Report", 0, 1, 'C')
    pdf.set_font("Helvetica", "", 10)
    date_label = summary.get('start_date', '')
    if summary.get('end_date'):
        date_label += f" - {summary.get('end_date')}"
    pdf.cell(0, 10, date_label, 0, 1, 'C')

    # --- Summary Boxes ---
    box_w = 90
    box_h = 20
    startX = (297 - (box_w * 3)) / 2

    def draw_box(x, y, value, label, color):
        pdf.set_draw_color(229, 231, 235)
        pdf.set_fill_color(249, 250, 251)
        pdf.rect(x, y, box_w, box_h, 'DF')
        pdf.set_xy(x, y + 4)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(color[0], color[1], color[2])
        pdf.cell(box_w, 7, str(value), 0, 1, 'C')
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(107, 114, 128)
        pdf.cell(box_w, 5, label, 0, 0, 'C')

    draw_box(startX, 45, summary.get('total_candidates', 0), "CANDIDATES", (59, 130, 246))
    draw_box(startX + box_w, 45, summary.get('total_interviews', 0), "INTERVIEWS", (16, 185, 129))
    draw_box(startX + (box_w * 2), 45, summary.get('total_clicks', 0), "JOB CLICKS", (245, 158, 11))

    # --- Table Header ---
    pdf.set_y(75)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(255, 255, 255)
    pdf.set_fill_color(59, 89, 152)

    cols = [
        ("Candidate", 35),
        ("EMAIL", 18), ("LINKEDIN", 18), ("PORTAL", 18), ("CLICKS", 18),
        ("ASSESS", 18), ("RECRUIT", 18), ("TECH", 18), ("ONSITE", 18),
        ("Total", 18),
        ("POS", 18), ("NEG", 18), ("PEND", 18)
    ]

    startX_table = 10
    pdf.set_x(startX_table)
    for label, width in cols:
        pdf.cell(width, 10, label, 1, 0, 'C', True)
    pdf.ln()

    # --- Table Body ---
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(31, 41, 55)

    for i, c in enumerate(candidates):
        pdf.set_x(startX_table)
        pdf.set_fill_color(248, 250, 252) if i % 2 == 1 else pdf.set_fill_color(255, 255, 255)

        pdf.cell(35, 8, str(c.get('full_name', '')), 1, 0, 'L', True)
        pdf.cell(18, 8, str(c.get('outreach_count', 0)), 1, 0, 'C', True)
        pdf.cell(18, 8, str(c.get('linkedin_easy_apply_count', 0)), 1, 0, 'C', True)
        pdf.cell(18, 8, str(c.get('job_portal_automation_count', 0)), 1, 0, 'C', True)

        pdf.set_text_color(234, 88, 12)
        pdf.cell(18, 8, str(c.get('job_clicks', 0)), 1, 0, 'C', True)
        pdf.set_text_color(31, 41, 55)

        pdf.cell(18, 8, str(c.get('assessment_count', 0)), 1, 0, 'C', True)
        pdf.cell(18, 8, str(c.get('recruiter_call_count', 0)), 1, 0, 'C', True)
        pdf.cell(18, 8, str(c.get('technical_count', 0)), 1, 0, 'C', True)
        pdf.cell(18, 8, str(c.get('onsite_count', 0)), 1, 0, 'C', True)

        pdf.set_font("Helvetica", "B", 7)
        pdf.set_fill_color(236, 253, 245)
        pdf.cell(18, 8, str(c.get('total_interviews', 0)), 1, 0, 'C', True)

        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(22, 163, 74)
        pdf.cell(18, 8, str(c.get('feedback_positive', 0)), 1, 0, 'C', True)
        pdf.set_text_color(239, 68, 68)
        pdf.cell(18, 8, str(c.get('feedback_negative', 0)), 1, 0, 'C', True)
        pdf.set_text_color(217, 119, 6)
        pdf.cell(18, 8, str(c.get('feedback_pending', 0)), 1, 0, 'C', True)
        pdf.set_text_color(31, 41, 55)
        pdf.ln()

    # --- Footer ---
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(156, 163, 175)
    pdf.cell(0, 10, f"Whitebox Learning Audit System - Generated on {now_str}", 0, 0, 'C')

    # Return as downloadable PDF response
    pdf_bytes = bytes(pdf.output())
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Marketing_Report_{now_str.replace(' ', '_')}.pdf"}
    )


@router.get("/report-pdf")
@router.get("/report-pdf/")
def download_report_pdf(key: str = Query(..., alias="key"), db: Session = Depends(get_db)):
    if key != REPORT_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    try:
        data = get_marketing_report_raw_data(x_api_key=key, db=db)
        return generate_report_pdf(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
