# email_activity_log_utils.py

from typing import List, Dict, Any, Optional
from datetime import date, datetime
import logging

from sqlalchemy import func, and_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException

from fapi.db.models import EmailActivityLogORM, CandidateMarketingORM, CandidateORM
from fapi.db.schemas import EmailActivityLogCreate, EmailActivityLogUpdate

logger = logging.getLogger(__name__)


# ---------- CRUD: Email Activity Log ----------

def get_all_email_activity_logs(db: Session) -> List[Dict[str, Any]]:
    """Get all email activity logs with candidate name"""
    try:
        logs = (
            db.query(
                EmailActivityLogORM,
                CandidateORM.full_name.label("candidate_name")
            )
            .join(
                CandidateMarketingORM,
                EmailActivityLogORM.candidate_marketing_id == CandidateMarketingORM.id
            )
            .join(
                CandidateORM,
                CandidateMarketingORM.candidate_id == CandidateORM.id
            )
            .order_by(EmailActivityLogORM.activity_date.desc())
            .all()
        )
        
        result = []
        for log, candidate_name in logs:
            log_dict = {
                "id": log.id,
                "candidate_marketing_id": log.candidate_marketing_id,
                "email": log.email,
                "activity_date": log.activity_date,
                "emails_read": log.emails_read,
                "last_updated": log.last_updated,
                "candidate_name": candidate_name
            }
            result.append(log_dict)
        
        return result
    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch email activity logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


def get_email_activity_log_by_id(db: Session, log_id: int) -> Dict[str, Any]:
    """Get single email activity log by ID"""
    log = db.query(EmailActivityLogORM).filter(EmailActivityLogORM.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Email activity log not found")
    return log


def get_logs_by_candidate_marketing_id(
    db: Session, 
    candidate_marketing_id: int
) -> List[EmailActivityLogORM]:
    """Get all logs for a specific candidate marketing ID"""
    return (
        db.query(EmailActivityLogORM)
        .filter(EmailActivityLogORM.candidate_marketing_id == candidate_marketing_id)
        .order_by(EmailActivityLogORM.activity_date.desc())
        .all()
    )


def create_email_activity_log(
    db: Session, 
    log_data:EmailActivityLogCreate
) -> EmailActivityLogORM:
    """Create new email activity log - prevents duplicates"""
    payload = log_data.dict()
    
    # Check for duplicate (email + activity_date)
    existing = (
        db.query(EmailActivityLogORM)
        .filter(
            and_(
                EmailActivityLogORM.email == payload["email"],
                EmailActivityLogORM.activity_date == payload.get("activity_date", date.today())
            )
        )
        .first()
    )
    
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"Activity log already exists for {payload['email']} on {payload.get('activity_date', date.today())}"
        )
    
    # Verify candidate_marketing_id exists
    marketing_record = (
        db.query(CandidateMarketingORM)
        .filter(CandidateMarketingORM.id == payload["candidate_marketing_id"])
        .first()
    )
    if not marketing_record:
        raise HTTPException(status_code=404, detail="Candidate marketing record not found")
    
    new_log = EmailActivityLogORM(**payload)
    db.add(new_log)
    
    try:
        db.commit()
        db.refresh(new_log)
        return new_log
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error: {str(e)}")
        raise HTTPException(status_code=400, detail="Duplicate entry or constraint violation")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Create failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Create failed: {str(e)}")


def update_email_activity_log(
    db: Session, 
    log_id: int, 
    update_data:EmailActivityLogUpdate
) -> EmailActivityLogORM:
    """Update email activity log (mainly emails_read count)"""
    fields = update_data.dict(exclude_unset=True)
    
    if not fields:
        raise HTTPException(status_code=400, detail="No data to update")
    
    log = db.query(EmailActivityLogORM).filter(EmailActivityLogORM.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Email activity log not found")
    
    try:
        for key, value in fields.items():
            setattr(log, key, value)
        
        db.commit()
        db.refresh(log)
        return log
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Update failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


def delete_email_activity_log(db: Session, log_id: int) -> Dict[str, str]:
    """Delete email activity log"""
    log = db.query(EmailActivityLogORM).filter(EmailActivityLogORM.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Email activity log not found")
    
    try:
        db.delete(log)
        db.commit()
        return {"message": f"Email activity log with ID {log_id} deleted successfully"}
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Delete failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")