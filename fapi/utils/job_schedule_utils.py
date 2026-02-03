from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from fapi.db.models import JobScheduleORM
from fapi.db import schemas
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


def get_all_job_schedules(db: Session, skip: int = 0, limit: int = 100, search: Optional[str] = None) -> List[JobScheduleORM]:
    """Get all job schedules with optional search"""
    query = db.query(JobScheduleORM)
    
    if search:
        query = query.filter(
            (JobScheduleORM.frequency.contains(search)) |
            (JobScheduleORM.timezone.contains(search))
        )
    
    return query.offset(skip).limit(limit).all()


def get_job_schedule_by_id(db: Session, job_schedule_id: int) -> Optional[JobScheduleORM]:
    """Get a specific job schedule by ID"""
    return db.query(JobScheduleORM).filter(JobScheduleORM.id == job_schedule_id).first()


def create_job_schedule(db: Session, job_schedule: schemas.JobScheduleCreate) -> JobScheduleORM:
    """Create a new job schedule"""
    try:
        db_job_schedule = JobScheduleORM(**job_schedule.model_dump())
        db.add(db_job_schedule)
        db.commit()
        db.refresh(db_job_schedule)
        return db_job_schedule
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error creating job schedule: {e}")
        raise HTTPException(status_code=400, detail="Error creating job schedule. Check foreign key constraints.")


def update_job_schedule(db: Session, job_schedule_id: int, job_schedule: schemas.JobScheduleUpdate) -> Optional[JobScheduleORM]:
    """Update an existing job schedule"""
    db_job_schedule = get_job_schedule_by_id(db, job_schedule_id)
    if not db_job_schedule:
        return None
    
    update_data = job_schedule.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_job_schedule, key, value)
    
    try:
        db.commit()
        db.refresh(db_job_schedule)
        return db_job_schedule
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error updating job schedule: {e}")
        raise HTTPException(status_code=400, detail="Error updating job schedule")


def delete_job_schedule(db: Session, job_schedule_id: int) -> Optional[JobScheduleORM]:
    """Delete a job schedule"""
    db_job_schedule = get_job_schedule_by_id(db, job_schedule_id)
    if not db_job_schedule:
        return None
    
    try:
        db.delete(db_job_schedule)
        db.commit()
        return db_job_schedule
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting job schedule: {e}")
        raise HTTPException(status_code=400, detail="Error deleting job schedule")


def get_job_schedules_by_definition(db: Session, job_definition_id: int) -> List[JobScheduleORM]:
    """Get all job schedules for a specific job definition"""
    return db.query(JobScheduleORM).filter(
        JobScheduleORM.job_definition_id == job_definition_id
    ).all()


def get_enabled_schedules(db: Session) -> List[JobScheduleORM]:
    """Get all enabled job schedules"""
    return db.query(JobScheduleORM).filter(JobScheduleORM.enabled == True).all()
