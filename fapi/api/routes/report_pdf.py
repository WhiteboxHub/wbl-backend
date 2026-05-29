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


class ReportPDF(FPDF):
    def __init__(self, now_str: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.now_str = now_str

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(156, 163, 175)
        self.cell(0, 10, f"Whitebox Learning Audit System - Generated on {self.now_str}", 0, 0, 'C')


def generate_report_pdf(data):
    """
    Generates a landscape A4 PDF with 13-column marketing report using fpdf2.
    Returns a FastAPI Response object ready to serve as a file download.
    """
    summary = data.get("summary", {})
    candidates = data.get("candidates", [])
    now_str = datetime.now(timezone.utc).strftime('%B %d, %Y')

    pdf = ReportPDF(now_str, orientation='L', unit='mm', format='A4')
    pdf.add_page()

    # --- Header ---
    pdf.set_fill_color(31, 41, 55)
    pdf.rect(0, 0, 297, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_y(10)
    pdf.cell(0, 10, "Weekly Application Report", 0, 1, 'C')
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
        pdf.cell(box_w, 7, str(value), 0, 0, 'C')
        pdf.set_xy(x, y + 11)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(107, 114, 128)
        pdf.cell(box_w, 5, label, 0, 0, 'C')

    draw_box(startX, 45, summary.get('total_candidates', 0), "CANDIDATES", (59, 130, 246))
    draw_box(startX + box_w, 45, summary.get('total_interviews', 0), "INTERVIEWS", (16, 185, 129))
    draw_box(startX + (box_w * 2), 45, summary.get('total_clicks', 0), "JOB CLICKS", (245, 158, 11))

    # --- Table Header (Two-Row Grouped, matching HTML email format) ---
    y_start = 75
    startX_table = 10
    row1_h = 8
    row2_h = 7
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(255, 255, 255)

    # Row 1: S.No and Candidate span both rows (tall cells)
    pdf.set_fill_color(59, 89, 152)   # Dark blue
    pdf.set_xy(startX_table, y_start)
    pdf.cell(10, row1_h + row2_h, "S.No", 1, 0, 'C', True)
    pdf.set_xy(startX_table + 10, y_start)
    pdf.cell(35, row1_h + row2_h, "Candidate", 1, 0, 'C', True)

    # APPLICATIONS group (4 cols x 18mm = 72mm)
    pdf.set_fill_color(77, 113, 187)
    pdf.set_xy(startX_table + 45, y_start)
    pdf.cell(72, row1_h, "APPLICATIONS", 1, 0, 'C', True)

    # INTERVIEWS group (4 cols x 18mm = 72mm)
    pdf.set_fill_color(109, 138, 203)
    pdf.set_xy(startX_table + 117, y_start)
    pdf.cell(72, row1_h, "INTERVIEWS", 1, 0, 'C', True)

    # Total spans both rows (teal)
    pdf.set_fill_color(56, 173, 169)
    pdf.set_xy(startX_table + 189, y_start)
    pdf.cell(18, row1_h + row2_h, "Total", 1, 0, 'C', True)

    # FEEDBACK group (3 cols x 18mm = 54mm)
    pdf.set_fill_color(141, 163, 220)
    pdf.set_xy(startX_table + 207, y_start)
    pdf.cell(54, row1_h, "FEEDBACK", 1, 0, 'C', True)

    # Row 2: Sub-column labels for APPLICATIONS, INTERVIEWS, FEEDBACK
    pdf.set_font("Helvetica", "B", 6)   # smaller font so labels fit in 18mm cells
    pdf.set_fill_color(240, 244, 248)
    pdf.set_text_color(51, 78, 129)
    sub_y = y_start + row1_h
    sub_col_groups = [
        (startX_table + 45,  [("EMAIL", 18), ("LINKEDIN", 18), ("PORTAL/CLI", 18), ("CLICKS", 18)]),
        (startX_table + 117, [("ASSESSMENT", 18), ("RECRUITER", 18), ("TECH", 18), ("ONSITE", 18)]),
        (startX_table + 207, [("POS", 18), ("NEG", 18), ("PEND", 18)]),
    ]
    for x_grp, grp_cols in sub_col_groups:
        x = x_grp
        for label, width in grp_cols:
            pdf.set_xy(x, sub_y)
            pdf.cell(width, row2_h, label, 1, 0, 'C', True)
            x += width
    pdf.set_font("Helvetica", "B", 7)   # restore font for body

    # Move cursor below both header rows for body rendering
    pdf.set_xy(startX_table, y_start + row1_h + row2_h)

    # --- Table Body ---
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(31, 41, 55)

    for i, c in enumerate(candidates):
        pdf.set_x(startX_table)
        if i % 2 == 1:
            pdf.set_fill_color(248, 250, 252)
        else:
            pdf.set_fill_color(255, 255, 255)

        # S.No column
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(10, 8, str(i + 1), 1, 0, 'C', True)
        pdf.set_font("Helvetica", "", 7)

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

        # Restore row fill for feedback columns
        pdf.set_font("Helvetica", "", 7)
        if i % 2 == 1:
            pdf.set_fill_color(248, 250, 252)
        else:
            pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(22, 163, 74)
        pdf.cell(18, 8, str(c.get('feedback_positive', 0)), 1, 0, 'C', True)
        pdf.set_text_color(239, 68, 68)
        pdf.cell(18, 8, str(c.get('feedback_negative', 0)), 1, 0, 'C', True)
        pdf.set_text_color(217, 119, 6)
        pdf.cell(18, 8, str(c.get('feedback_pending', 0)), 1, 0, 'C', True)
        pdf.set_text_color(31, 41, 55)
        pdf.ln()

    # --- Total Row ---
    totals = {
        "outreach": sum(int(c.get("outreach_count", 0) or 0) for c in candidates),
        "linkedin": sum(int(c.get("linkedin_easy_apply_count", 0) or 0) for c in candidates),
        "portal": sum(int(c.get("job_portal_automation_count", 0) or 0) for c in candidates),
        "clicks": sum(int(c.get("job_clicks", 0) or 0) for c in candidates),
        "assess": sum(int(c.get("assessment_count", 0) or 0) for c in candidates),
        "recruiter": sum(int(c.get("recruiter_call_count", 0) or 0) for c in candidates),
        "tech": sum(int(c.get("technical_count", 0) or 0) for c in candidates),
        "onsite": sum(int(c.get("onsite_count", 0) or 0) for c in candidates),
        "interviews": sum(int(c.get("total_interviews", 0) or 0) for c in candidates),
        "pos": sum(int(c.get("feedback_positive", 0) or 0) for c in candidates),
        "neg": sum(int(c.get("feedback_negative", 0) or 0) for c in candidates),
        "pend": sum(int(c.get("feedback_pending", 0) or 0) for c in candidates),
    }

    # Prevent the totals row and repeated footer header from being split across different pages.
    # Combined height: totals row (8mm) + repeated table footer (7mm + 7mm = 14mm) = 22mm.
    # Checking this before drawing the totals row ensures they remain attached together on the same page.
    if pdf.get_y() + 22 > pdf.page_break_trigger:
        pdf.add_page()

    # Set formatting for the totals row (white text on dark blue background)
    pdf.set_x(startX_table)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_fill_color(18, 51, 89)  # Dark blue
    pdf.set_text_color(255, 255, 255)

    # Render totals row cells
    pdf.cell(10, 8, "Total", 1, 0, 'C', True)              # S.No column: label
    pdf.cell(35, 8, str(len(candidates)), 1, 0, 'C', True)  # Candidate column: count
    pdf.cell(18, 8, str(totals["outreach"] if totals["outreach"] > 0 else '-'), 1, 0, 'C', True)
    pdf.cell(18, 8, str(totals["linkedin"] if totals["linkedin"] > 0 else '-'), 1, 0, 'C', True)
    pdf.cell(18, 8, str(totals["portal"] if totals["portal"] > 0 else '-'), 1, 0, 'C', True)

    # Orange text style for total clicks
    pdf.set_text_color(251, 146, 60)
    pdf.cell(18, 8, str(totals["clicks"] if totals["clicks"] > 0 else '-'), 1, 0, 'C', True)

    # Reset text style back to white for standard totals
    pdf.set_text_color(255, 255, 255)
    pdf.cell(18, 8, str(totals["assess"] if totals["assess"] > 0 else '-'), 1, 0, 'C', True)
    pdf.cell(18, 8, str(totals["recruiter"] if totals["recruiter"] > 0 else '-'), 1, 0, 'C', True)
    pdf.cell(18, 8, str(totals["tech"] if totals["tech"] > 0 else '-'), 1, 0, 'C', True)
    pdf.cell(18, 8, str(totals["onsite"] if totals["onsite"] > 0 else '-'), 1, 0, 'C', True)

    # Highlighted green background for total interviews
    pdf.set_fill_color(6, 78, 59)
    pdf.cell(18, 8, str(totals["interviews"] if totals["interviews"] > 0 else '-'), 1, 0, 'C', True)

    # Green, Red, Amber text for feedback metrics
    pdf.set_fill_color(18, 51, 89)
    pdf.set_text_color(74, 222, 128)   # Green for POS
    pdf.cell(18, 8, str(totals["pos"] if totals["pos"] > 0 else '-'), 1, 0, 'C', True)
    pdf.set_text_color(248, 113, 113)  # Red for NEG
    pdf.cell(18, 8, str(totals["neg"] if totals["neg"] > 0 else '-'), 1, 0, 'C', True)
    pdf.set_text_color(251, 191, 36)   # Amber for PEND
    pdf.cell(18, 8, str(totals["pend"] if totals["pend"] > 0 else '-'), 1, 0, 'C', True)
    pdf.ln()

    # --- Repeated Footer Header (mirrors the top header, matching HTML email tfoot) ---
    # The two footer rows use manual set_xy() to simulate rowspan for S.No, Candidate, Total
    frow1_h = 7   # sub-label row height
    frow2_h = 7   # group-label row height

    f_y = pdf.get_y()
    pdf.set_font("Helvetica", "B", 6)

    # S.No — spans both footer rows (dark blue)
    pdf.set_fill_color(59, 89, 152)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(startX_table, f_y)
    pdf.cell(10, frow1_h + frow2_h, "S.No", 1, 0, 'C', True)

    # Candidate — spans both footer rows (dark blue)
    pdf.set_xy(startX_table + 10, f_y)
    pdf.cell(35, frow1_h + frow2_h, "Candidate", 1, 0, 'C', True)

    # Sub-labels row: EMAIL … ONSITE (light blue/grey, frow1_h)
    pdf.set_fill_color(240, 244, 248)
    pdf.set_text_color(51, 78, 129)
    footer_sub = [
        (startX_table + 45,  [("EMAIL", 18), ("LINKEDIN", 18), ("PORTAL/CLI", 18), ("CLICKS", 18)]),
        (startX_table + 117, [("ASSESSMENT", 18), ("RECRUITER", 18), ("TECH", 18), ("ONSITE", 18)]),
    ]
    for x_grp, grp_cols in footer_sub:
        x = x_grp
        for label, width in grp_cols:
            pdf.set_xy(x, f_y)
            pdf.cell(width, frow1_h, label, 1, 0, 'C', True)
            x += width

    # Total — spans both footer rows (teal)
    pdf.set_fill_color(56, 173, 169)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(startX_table + 189, f_y)
    pdf.cell(18, frow1_h + frow2_h, "Total", 1, 0, 'C', True)

    # POS / NEG / PEND sub-labels (light blue/grey, frow1_h)
    pdf.set_fill_color(240, 244, 248)
    pdf.set_text_color(51, 78, 129)
    x = startX_table + 207
    for label, width in [("POS", 18), ("NEG", 18), ("PEND", 18)]:
        pdf.set_xy(x, f_y)
        pdf.cell(width, frow1_h, label, 1, 0, 'C', True)
        x += width

    # Group-labels row: APPLICATIONS | INTERVIEWS | FEEDBACK (frow2_h)
    f_y2 = f_y + frow1_h
    pdf.set_text_color(255, 255, 255)

    pdf.set_fill_color(77, 113, 187)    # APPLICATIONS — mid blue
    pdf.set_xy(startX_table + 45, f_y2)
    pdf.cell(72, frow2_h, "APPLICATIONS", 1, 0, 'C', True)

    pdf.set_fill_color(109, 138, 203)   # INTERVIEWS — lighter blue
    pdf.set_xy(startX_table + 117, f_y2)
    pdf.cell(72, frow2_h, "INTERVIEWS", 1, 0, 'C', True)

    pdf.set_fill_color(141, 163, 220)   # FEEDBACK — lavender blue
    pdf.set_xy(startX_table + 207, f_y2)
    pdf.cell(54, frow2_h, "FEEDBACK", 1, 0, 'C', True)

    # Advance cursor past both footer rows
    pdf.set_xy(startX_table, f_y + frow1_h + frow2_h)
    pdf.ln(4)

    # Return as downloadable PDF response
    pdf_bytes = bytes(pdf.output())
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
           headers={"Content-Disposition": f'attachment; filename="Marketing_Report_{now_str.replace(" ", "_").replace(",", "")}.pdf"'}
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