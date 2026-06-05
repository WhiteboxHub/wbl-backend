"""
Dynamic Weekly Marketing Report API Routes
Provides endpoints for generating and sending dynamic weekly reports
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.utils.dynamic_weekly_report_utils import (
    send_weekly_marketing_report,
    get_weekly_report_data,
    generate_weekly_marketing_report,
)
from fapi.utils.permission_gate import enforce_access

router = APIRouter(prefix="/dynamic-weekly-report", tags=["Dynamic Weekly Report"])
logger = logging.getLogger(__name__)


@router.post("/send")
async def send_weekly_report(
    db: Session = Depends(get_db),
    # dependencies=[Depends(enforce_access)]  # Uncomment if authentication needed
) -> Dict[str, Any]:
    """
    Generate and send the dynamic weekly marketing report via email.

    This endpoint:
    1. Queries the database for the last 7 days of candidate activity
    2. Generates a professional HTML report
    3. Sends the report to configured admin email addresses

    Returns:
        Dict with status, message, recipients, and subject
    """
    try:
        result = send_weekly_marketing_report(db)
        return result
    except Exception as e:
        logger.error(f"Error sending weekly report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send weekly report: {str(e)}")


@router.get("/preview")
async def preview_weekly_report(
    db: Session = Depends(get_db),
    # dependencies=[Depends(enforce_access)]  # Uncomment if authentication needed
) -> Dict[str, Any]:
    """
    Generate the weekly report data without sending email (JSON response).

    Returns:
        Dict with status, html_report, recipients, and generated_at timestamp
    """
    try:
        result = get_weekly_report_data(db)
        return result
    except Exception as e:
        logger.error(f"Error generating weekly report preview: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report preview: {str(e)}")


@router.get("/preview-html", response_class=HTMLResponse)
async def preview_weekly_report_html(
    db: Session = Depends(get_db),
):
    """
    Generate the weekly report and return it as rendered HTML.

    Open this URL in a browser to see exactly what the email will look like.
    This is useful for testing and verifying the report before sending.
    """
    try:
        report_data = generate_weekly_marketing_report(db)
        html_report = report_data.get('html', "")
        return HTMLResponse(content=html_report, status_code=200)
    except Exception as e:
        logger.error(f"Error generating weekly report HTML preview: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.get("/health")
async def check_report_health() -> Dict[str, str]:
    """
    Health check endpoint for the dynamic weekly report system.

    Returns:
        Basic health status
    """
    return {
        "status": "healthy",
        "service": "dynamic_weekly_report",
        "message": "Weekly report system is operational"
    }