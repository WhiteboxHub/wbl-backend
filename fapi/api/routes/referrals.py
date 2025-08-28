from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.db.models import LeadORM, AuthUserORM
from fapi.db.schemas import LeadCreate
from fapi.utils.email_utils import send_referral_emails
from fapi.utils.user_dashboard_utils import get_current_user
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class ReferralCreate(LeadCreate):
    """Schema for referral submissions - extends LeadCreate"""
    pass

@router.post("/referrals")
async def create_referral(
    referral: ReferralCreate,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new referral submission.
    Stores referral in lead table with referrer information in notes field.
    Sends email notifications to specified recipients.
    """
    try:
        # Get referrer information - current_user is already the AuthUserORM object
        referrer = current_user
        
        # Create referral note with referrer information
        referral_note = f"Referred by {referrer.fullname or referrer.uname} (ID: {referrer.id})"
        if referral.notes:
            referral_note = f"{referral_note}. Additional notes: {referral.notes}"
        
        # Create new lead entry with referral information
        new_lead = LeadORM(
            full_name=referral.full_name,
            email=referral.email,
            phone=referral.phone,
            workstatus=referral.workstatus,
            address=referral.address,
            notes=referral_note,
            entry_date=datetime.now(),
            last_modified=datetime.now(),
            status="referral"
        )
        
        db.add(new_lead)
        db.commit()
        db.refresh(new_lead)
        
        # Send email notifications
        try:
            # Debug logging
            logger.info(f"Sending referral email with data:")
            logger.info(f"Referrer: {referrer.fullname or referrer.uname} ({referrer.uname})")
            logger.info(f"Candidate: {referral.full_name} ({referral.email})")
            logger.info(f"Phone: {referral.phone}")
            logger.info(f"Work Status: {referral.workstatus}")
            logger.info(f"Address: {referral.address}")
            logger.info(f"Notes: {referral.notes}")
            
            await send_referral_emails(
                referrer_name=referrer.fullname or referrer.uname,
                referrer_email=referrer.uname,
                referrer_phone=referrer.phone or "Not provided",
                candidate_name=referral.full_name,
                candidate_email=referral.email,
                candidate_phone=referral.phone or "Not provided",
                candidate_workstatus=referral.workstatus or "Not provided",
                candidate_address=referral.address or "Not provided",
                additional_notes=referral.notes or "None"
            )
        except Exception as email_error:
            logger.error(f"Failed to send referral emails: {str(email_error)}")
            # Don't fail the API call if email fails, just log it
        
        return {
            "message": "Referral submitted successfully",
            "referral_id": new_lead.id,
            "referrer": referrer.fullname or referrer.uname
        }
        
    except Exception as e:
        logger.error(f"Error creating referral: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to submit referral")
