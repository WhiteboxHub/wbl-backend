from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from fapi.db.models import JobRunORM
from fapi.db import schemas
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


def get_all_job_runs(db: Session, search: Optional[str] = None) -> List[JobRunORM]:
    """Get all job runs with optional search"""
    query = db.query(JobRunORM)
    
    if search:
        query = query.filter(JobRunORM.run_status.contains(search))
    
    return query.order_by(JobRunORM.started_at.desc()).all()


def get_job_run_by_id(db: Session, job_run_id: int) -> Optional[JobRunORM]:
    """Get a specific job run by ID"""
    return db.query(JobRunORM).filter(JobRunORM.id == job_run_id).first()


def create_job_run(db: Session, job_run: schemas.JobRunCreate) -> JobRunORM:
    """Create a new job run"""
    try:
        db_job_run = JobRunORM(**job_run.model_dump())
        db.add(db_job_run)
        db.commit()
        db.refresh(db_job_run)
        return db_job_run
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error creating job run: {e}")
        raise HTTPException(status_code=400, detail="Error creating job run. Check foreign key constraints.")


def update_job_run(db: Session, job_run_id: int, job_run: schemas.JobRunUpdate) -> Optional[JobRunORM]:
    """Update an existing job run"""
    db_job_run = get_job_run_by_id(db, job_run_id)
    if not db_job_run:
        return None
    
    update_data = job_run.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_job_run, key, value)
    
    try:
        db.commit()
        db.refresh(db_job_run)
        return db_job_run
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error updating job run: {e}")
        raise HTTPException(status_code=400, detail="Error updating job run")


def delete_job_run(db: Session, job_run_id: int) -> Optional[JobRunORM]:
    """Delete a job run"""
    db_job_run = get_job_run_by_id(db, job_run_id)
    if not db_job_run:
        return None
    
    try:
        db.delete(db_job_run)
        db.commit()
        return db_job_run
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting job run: {e}")
        raise HTTPException(status_code=400, detail="Error deleting job run")


def get_job_runs_by_definition(db: Session, job_definition_id: int) -> List[JobRunORM]:
    """Get all job runs for a specific job definition"""
    return db.query(JobRunORM).filter(
        JobRunORM.job_definition_id == job_definition_id
    ).order_by(JobRunORM.started_at.desc()).all()


def get_job_runs_by_schedule(db: Session, job_schedule_id: int) -> List[JobRunORM]:
    """Get all job runs for a specific job schedule"""
    return db.query(JobRunORM).filter(
        JobRunORM.job_schedule_id == job_schedule_id
    ).order_by(JobRunORM.started_at.desc()).all()


def get_job_runs_by_status(db: Session, run_status: str) -> List[JobRunORM]:
    """Get all job runs with a specific status"""
    return db.query(JobRunORM).filter(
        JobRunORM.run_status == run_status
    ).order_by(JobRunORM.started_at.desc()).all()
