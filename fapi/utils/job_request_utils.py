from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from fapi.db.models import JobRequestORM
from fapi.db import schemas
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


def get_all_job_requests(db: Session, search: Optional[str] = None) -> List[JobRequestORM]:
    """Get all job requests with optional search"""
    query = db.query(JobRequestORM)
    
    if search:
        query = query.filter(
            (JobRequestORM.job_type.contains(search)) |
            (JobRequestORM.status.contains(search))
        )
    
    return query.order_by(JobRequestORM.requested_at.desc()).all()


def get_job_request_by_id(db: Session, job_request_id: int) -> Optional[JobRequestORM]:
    """Get a specific job request by ID"""
    return db.query(JobRequestORM).filter(JobRequestORM.id == job_request_id).first()


def create_job_request(db: Session, job_request: schemas.JobRequestCreate) -> JobRequestORM:
    """Create a new job request"""
    try:
        db_job_request = JobRequestORM(
            job_type=job_request.job_type,
            candidate_marketing_id=job_request.candidate_marketing_id,
            status="PENDING"
        )
        db.add(db_job_request)
        db.commit()
        db.refresh(db_job_request)
        return db_job_request
    except IntegrityError as e:
        db.rollback()
        # Check if it is a duplicate entry error
        if "Duplicate entry" in str(e):
             logger.warning(f"Duplicate job request: {e}")
             raise HTTPException(status_code=409, detail="A pending job request already exists for this candidate.")
        logger.error(f"Error creating job request: {e}")
        raise HTTPException(status_code=400, detail="Job request creation failed or foreign key constraint failed")


def update_job_request(db: Session, job_request_id: int, job_request: schemas.JobRequestUpdate) -> Optional[JobRequestORM]:
    """Update an existing job request"""
    db_job_request = get_job_request_by_id(db, job_request_id)
    if not db_job_request:
        return None
    
    update_data = job_request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_job_request, key, value)
    
    try:
        db.commit()
        db.refresh(db_job_request)
        return db_job_request
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error updating job request: {e}")
        raise HTTPException(status_code=400, detail="Error updating job request")


def delete_job_request(db: Session, job_request_id: int) -> Optional[JobRequestORM]:
    """Delete a job request"""
    db_job_request = get_job_request_by_id(db, job_request_id)
    if not db_job_request:
        return None
    
    try:
        db.delete(db_job_request)
        db.commit()
        return db_job_request
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting job request: {e}")
        raise HTTPException(status_code=400, detail="Error deleting job request")


def get_job_requests_by_candidate(db: Session, candidate_marketing_id: int) -> List[JobRequestORM]:
    """Get all job requests for a specific candidate"""
    return db.query(JobRequestORM).filter(
        JobRequestORM.candidate_marketing_id == candidate_marketing_id
    ).order_by(JobRequestORM.requested_at.desc()).all()


def get_job_requests_by_status(db: Session, status: str) -> List[JobRequestORM]:
    """Get all job requests with a specific status"""
    return db.query(JobRequestORM).filter(
        JobRequestORM.status == status
    ).order_by(JobRequestORM.requested_at.desc()).all()


def get_pending_job_requests(db: Session) -> List[JobRequestORM]:
    """Get all pending job requests"""
    return get_job_requests_by_status(db, "PENDING")
