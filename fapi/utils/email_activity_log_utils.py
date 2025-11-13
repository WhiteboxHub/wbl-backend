# email_activity_log_utils.py

from typing import List, Dict, Any, Optional
from datetime import date, datetime
import logging
from sqlalchemy import func, and_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException

from fapi.db.models import EmailActivityLogORM, CandidateMarketingORM, CandidateORM,VendorContactExtractsORM
from fapi.db.schemas import EmailActivityLogCreate, EmailActivityLogUpdate

logger = logging.getLogger(__name__)


# ---------- CRUD: Email Activity Log ----------

def get_all_email_activity_logs(db: Session) -> List[Dict[str, Any]]:
    """Get all email activity logs with candidate name and total extracted count"""
    try:
        logs = (
            db.query(
                EmailActivityLogORM,
                CandidateORM.full_name.label("candidate_name"),
                func.count(VendorContactExtractsORM.id).label("total_extracted")  
            )
            .join(
                CandidateMarketingORM,
                EmailActivityLogORM.candidate_marketing_id == CandidateMarketingORM.id
            )
            .join(
                CandidateORM,
                CandidateMarketingORM.candidate_id == CandidateORM.id
            )
            .outerjoin(
                VendorContactExtractsORM,
                and_(
                    EmailActivityLogORM.email.collate("utf8mb4_unicode_ci") == 
                    VendorContactExtractsORM.source_email.collate("utf8mb4_unicode_ci"),  
                    EmailActivityLogORM.activity_date == VendorContactExtractsORM.extraction_date  
                )
            )
            .group_by(EmailActivityLogORM.id, CandidateORM.full_name)
            .order_by(EmailActivityLogORM.activity_date.desc())
            .all()
        )
        
        result = []
        for log, candidate_name, total_extracted in logs:
            log_dict = {
                "id": log.id,
                "candidate_marketing_id": log.candidate_marketing_id,
                "email": log.email,
                "activity_date": log.activity_date,
                "emails_read": log.emails_read,
                "last_updated": log.last_updated,
                "candidate_name": candidate_name,
                "total_extracted": total_extracted or 0
            }
            result.append(log_dict)
        
        return result
    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch email activity logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


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


from sqlalchemy import case

def get_all_email_activity_logs(db: Session) -> List[Dict[str, Any]]:
    """Get all email activity logs with candidate name and total extracted count"""
    try:
        from fapi.db.models import VendorContactExtractsORM
        
        logs = (
            db.query(
                EmailActivityLogORM.id,
                EmailActivityLogORM.candidate_marketing_id,
                EmailActivityLogORM.email,
                EmailActivityLogORM.activity_date,
                EmailActivityLogORM.emails_read,
                EmailActivityLogORM.last_updated,
                CandidateORM.full_name.label("candidate_name"),
                func.count(VendorContactExtractsORM.id).label("total_extracted")
            )
            .join(
                CandidateMarketingORM,
                EmailActivityLogORM.candidate_marketing_id == CandidateMarketingORM.id
            )
            .join(
                CandidateORM,
                CandidateMarketingORM.candidate_id == CandidateORM.id
            )
            .outerjoin(
                VendorContactExtractsORM,
                and_(
                    EmailActivityLogORM.email.collate("utf8mb4_unicode_ci") == 
                    VendorContactExtractsORM.source_email.collate("utf8mb4_unicode_ci"),
                    EmailActivityLogORM.activity_date == VendorContactExtractsORM.extraction_date
                )
            )
            .group_by(
                EmailActivityLogORM.id,
                EmailActivityLogORM.candidate_marketing_id,
                EmailActivityLogORM.email,
                EmailActivityLogORM.activity_date,
                EmailActivityLogORM.emails_read,
                EmailActivityLogORM.last_updated,
                CandidateORM.full_name
            )
            .order_by(EmailActivityLogORM.activity_date.desc())
            .all()
        )
        
        result = []
        for row in logs:
            log_dict = {
                "id": row.id,
                "candidate_marketing_id": row.candidate_marketing_id,
                "email": row.email,
                "activity_date": row.activity_date,
                "emails_read": row.emails_read,
                "last_updated": row.last_updated,
                "candidate_name": row.candidate_name,
                "total_extracted": row.total_extracted or 0
            }
            result.append(log_dict)
        
        return result
    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch email activity logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")

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