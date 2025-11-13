# linkedin_activity_log_utils.py

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException

from fapi.db.models import LinkedInActivityLogORM, CandidateMarketingORM, CandidateORM
from fapi.db.schemas import LinkedInActivityLogCreate, LinkedInActivityLogUpdate

logger = logging.getLogger(__name__)


# ---------- CRUD: LinkedIn Activity Log ----------

def get_all_linkedin_activity_logs(db: Session) -> List[Dict[str, Any]]:
    """Get all LinkedIn activity logs with candidate name"""
    try:
        logs = (
            db.query(
                LinkedInActivityLogORM,
                CandidateORM.full_name.label("candidate_name")
            )
            .join(
                CandidateMarketingORM,
                LinkedInActivityLogORM.candidate_id == CandidateMarketingORM.candidate_id  # FIXED
            )
            .join(
                CandidateORM,
                CandidateMarketingORM.candidate_id == CandidateORM.id
            )
            .order_by(LinkedInActivityLogORM.created_at.desc())
            .all()
        )
        
        result = []
        for log, candidate_name in logs:
            log_dict = {
                "id": log.id,
                "candidate_id": log.candidate_id,
                "source_email": log.source_email,
                "activity_type": log.activity_type,
                "linkedin_profile_url": log.linkedin_profile_url,
                "full_name": log.full_name,
                "company_name": log.company_name,
                "status": log.status,
                "message": log.message,
                "created_at": log.created_at,
                "candidate_name": candidate_name
            }
            result.append(log_dict)
        
        return result
    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch LinkedIn activity logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


def get_linkedin_activity_log_by_id(db: Session, log_id: int) -> Dict[str, Any]:
    """Get single LinkedIn activity log by ID"""
    try:
        result = (
            db.query(
                LinkedInActivityLogORM,
                CandidateORM.full_name.label("candidate_name")
            )
            .join(
                CandidateMarketingORM,
                LinkedInActivityLogORM.candidate_id == CandidateMarketingORM.id
            )
            .join(
                CandidateORM,
                CandidateMarketingORM.candidate_id == CandidateORM.id
            )
            .filter(LinkedInActivityLogORM.id == log_id)
            .first()
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="LinkedIn activity log not found")
        
        log, candidate_name = result
        log_dict = {
            "id": log.id,
            "candidate_id": log.candidate_id,
            "source_email": log.source_email,
            "activity_type": log.activity_type,
            "linkedin_profile_url": log.linkedin_profile_url,
            "full_name": log.full_name,
            "company_name": log.company_name,
            "status": log.status,
            "message": log.message,
            "created_at": log.created_at,
            "candidate_name": candidate_name
        }
        
        return log_dict
    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch LinkedIn activity log: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


def get_logs_by_candidate_id(
    db: Session, 
    candidate_id: int
) -> List[Dict[str, Any]]:
    """Get all logs for a specific candidate ID"""
    try:
        logs = (
            db.query(
                LinkedInActivityLogORM,
                CandidateORM.full_name.label("candidate_name")
            )
            .join(
                CandidateMarketingORM,
                LinkedInActivityLogORM.candidate_id == CandidateMarketingORM.id
            )
            .join(
                CandidateORM,
                CandidateMarketingORM.candidate_id == CandidateORM.id
            )
            .filter(LinkedInActivityLogORM.candidate_id == candidate_id)
            .order_by(LinkedInActivityLogORM.created_at.desc())
            .all()
        )
        
        result = []
        for log, candidate_name in logs:
            log_dict = {
                "id": log.id,
                "candidate_id": log.candidate_id,
                "source_email": log.source_email,
                "activity_type": log.activity_type,
                "linkedin_profile_url": log.linkedin_profile_url,
                "full_name": log.full_name,
                "company_name": log.company_name,
                "status": log.status,
                "message": log.message,
                "created_at": log.created_at,
                "candidate_name": candidate_name
            }
            result.append(log_dict)
        
        return result
    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch LinkedIn activity logs for candidate: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


def create_linkedin_activity_log(
    db: Session, 
    log_data: LinkedInActivityLogCreate
) -> Dict[str, Any]:
    """Create new LinkedIn activity log"""
    payload = log_data.dict()
    
    # Verify candidate_id exists
    marketing_record = (
        db.query(CandidateMarketingORM)
        .filter(CandidateMarketingORM.candidate_id== payload["candidate_id"])
        .first()
    )
    if not marketing_record:
        raise HTTPException(status_code=404, detail="Candidate marketing record not found")
    
    new_log = LinkedInActivityLogORM(**payload)
    db.add(new_log)
    
    try:
        db.commit()
        db.refresh(new_log)
        
        # Get candidate name for response
        candidate_name = (
            db.query(CandidateORM.full_name)
            .join(CandidateMarketingORM, CandidateMarketingORM.candidate_id == CandidateORM.id)
            .filter(CandidateMarketingORM.id == new_log.candidate_id)
            .scalar()
        )
        
        response_data = {
            "id": new_log.id,
            "candidate_id": new_log.candidate_id,
            "source_email": new_log.source_email,
            "activity_type": new_log.activity_type,
            "linkedin_profile_url": new_log.linkedin_profile_url,
            "full_name": new_log.full_name,
            "company_name": new_log.company_name,
            "status": new_log.status,
            "message": new_log.message,
            "created_at": new_log.created_at,
            "candidate_name": candidate_name
        }
        
        return response_data
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error: {str(e)}")
        raise HTTPException(status_code=400, detail="Constraint violation")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Create failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Create failed: {str(e)}")


def update_linkedin_activity_log(
    db: Session, 
    log_id: int, 
    update_data: LinkedInActivityLogUpdate
) -> Dict[str, Any]:
    """Update LinkedIn activity log"""
    fields = update_data.dict(exclude_unset=True)
    
    if not fields:
        raise HTTPException(status_code=400, detail="No data to update")
    
    log = db.query(LinkedInActivityLogORM).filter(LinkedInActivityLogORM.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="LinkedIn activity log not found")
    
    try:
        for key, value in fields.items():
            setattr(log, key, value)
        
        db.commit()
        db.refresh(log)
        
        # Get candidate name for response
        candidate_name = (
            db.query(CandidateORM.full_name)
            .join(CandidateMarketingORM, CandidateMarketingORM.candidate_id == CandidateORM.id)
            .filter(CandidateMarketingORM.candidate_id== log.candidate_id)
            .scalar()
        )
        
        response_data = {
            "id": log.id,
            "candidate_id": log.candidate_id,
            "source_email": log.source_email,
            "activity_type": log.activity_type,
            "linkedin_profile_url": log.linkedin_profile_url,
            "full_name": log.full_name,
            "company_name": log.company_name,
            "status": log.status,
            "message": log.message,
            "created_at": log.created_at,
            "candidate_name": candidate_name
        }
        
        return response_data
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Update failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


def delete_linkedin_activity_log(db: Session, log_id: int) -> Dict[str, str]:
    """Delete LinkedIn activity log"""
    log = db.query(LinkedInActivityLogORM).filter(LinkedInActivityLogORM.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="LinkedIn activity log not found")
    
    try:
        db.delete(log)
        db.commit()
        return {"message": f"LinkedIn activity log with ID {log_id} deleted successfully"}
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Delete failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")