from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.db.models import OutreachContactORM
from sqlalchemy import func
import base64
import os

import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/outreach-feedback")
def handle_feedback(
    request: Request,
    token: str = Query(None, description="Encoded email token"),
    email: str = Query(None, description="Direct email address"),
    type: str = Query("unsubscribe", description="Type of feedback: unsubscribe, bounce, complaint"),
    reason: str = Query(None),
    db: Session = Depends(get_db)
):
    """
    Updates existing outreach records for unsubscribes, bounces, or complaints.
    """
    target_email = None
    if token:
        try:
            target_email = base64.b64decode(token).decode('utf-8').lower()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid token")
    elif email:
        target_email = email.lower()
    
    if not target_email:
        raise HTTPException(status_code=400, detail="Token or email required")

    # Find the record - check both email and email_lc for robustness
    contact = db.query(OutreachContactORM).filter(
        (OutreachContactORM.email_lc == target_email) | 
        (OutreachContactORM.email == target_email)
    ).first()

    if not contact:
        # Create a new record as suppressed
        logger.info(f"Creating new suppressed record for {target_email} ({type})")
        contact = OutreachContactORM(
            email=target_email,
            email_lc=target_email,  # Explicitly set this to avoid NULL issues
            source_type="MANUAL_UNSUB",
            status=type if type != "unsubscribe" else "unsubscribed",
            unsubscribe_flag=(type == "unsubscribe"),
            bounce_flag=(type == "bounce"),
            complaint_flag=(type == "complaint"),
            unsubscribe_at=func.now() if type == "unsubscribe" else None,
            unsubscribe_reason=reason if type == "unsubscribe" else None
        )
        db.add(contact)
    else:
        # Ensure email_lc is set if it was missing
        if not contact.email_lc:
            contact.email_lc = target_email
            
        if type == "unsubscribe":
            contact.unsubscribe_flag = True
            contact.unsubscribe_at = func.now()
            contact.unsubscribe_reason = reason
            contact.status = "unsubscribed"
        elif type == "bounce":
            contact.bounce_flag = True
            contact.bounced_at = func.now()
            contact.status = "bounced"
        elif type == "complaint":
            contact.complaint_flag = True
            contact.complained_at = func.now()
            contact.status = "complaint"

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving feedback for {target_email}: {e}")
        # If it's a duplicate error (race condition), just ignore it as it means they are already unsubscribed
        if "Duplicate entry" not in str(e):
            raise HTTPException(status_code=500, detail="Database error occurred")
    
    # Check if this is an API call (AJAX) or a browser click
    # 1. Check Accept header
    accept_header = request.headers.get("accept", "").lower()
    # 2. Check for X-Requested-With
    is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest"
    # 3. Check if 'json' is in query params (backup)
    wants_json = request.query_params.get("format") == "json"
    
    frontend_url = os.getenv("PUBLIC_UNSUBSCRIBE_SUCCESS_URL", "/solutions/unsubscribe-success")
    
    if "application/json" in accept_header or is_ajax or wants_json:
        # For manual form submissions (manual page)
        return {"message": "Unsubscribed successfully", "status": "success", "redirect": frontend_url}
    
    # For direct link clicks (vendor in email)
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=frontend_url)

@router.get("/outreach-unsubscribe")
def outreach_unsubscribe(
    request: Request,
    token: str = Query(None), 
    email: str = Query(None),
    reason: str = Query(None), 
    db: Session = Depends(get_db)
):
    return handle_feedback(request, token, email, "unsubscribe", reason, db)

@router.get("/unsubscribe")
def unsubscribe_alias(
    request: Request,
    token: str = Query(None), 
    email: str = Query(None),
    reason: str = Query(None), 
    db: Session = Depends(get_db)
):
    return handle_feedback(request, token, email, "unsubscribe", reason, db)