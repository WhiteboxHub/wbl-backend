from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from fapi.db.models import JobDefinitionORM
from fapi.db import schemas
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


def get_all_job_definitions(db: Session, search: Optional[str] = None) -> List[JobDefinitionORM]:
    """Get all job definitions with optional search"""
    query = db.query(JobDefinitionORM)
    
    if search:
        query = query.filter(
            (JobDefinitionORM.job_type.contains(search)) |
            (JobDefinitionORM.status.contains(search))
        )
    
    return query.all()


def get_job_definition_by_id(db: Session, job_definition_id: int) -> Optional[JobDefinitionORM]:
    """Get a specific job definition by ID"""
    return db.query(JobDefinitionORM).filter(JobDefinitionORM.id == job_definition_id).first()


def create_job_definition(db: Session, job_definition: schemas.JobDefinitionCreate) -> JobDefinitionORM:
    """Create a new job definition"""
    try:
        db_job_definition = JobDefinitionORM(**job_definition.model_dump())
        db.add(db_job_definition)
        db.commit()
        db.refresh(db_job_definition)
        return db_job_definition
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error creating job definition: {e}")
        raise HTTPException(status_code=400, detail="Error creating job definition. Check foreign key constraints.")


def update_job_definition(db: Session, job_definition_id: int, job_definition: schemas.JobDefinitionUpdate) -> Optional[JobDefinitionORM]:
    """Update an existing job definition"""
    db_job_definition = get_job_definition_by_id(db, job_definition_id)
    if not db_job_definition:
        return None
    
    update_data = job_definition.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_job_definition, key, value)
    
    try:
        db.commit()
        db.refresh(db_job_definition)
        return db_job_definition
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error updating job definition: {e}")
        raise HTTPException(status_code=400, detail="Error updating job definition")


def delete_job_definition(db: Session, job_definition_id: int) -> Optional[JobDefinitionORM]:
    """Delete a job definition"""
    db_job_definition = get_job_definition_by_id(db, job_definition_id)
    if not db_job_definition:
        return None
    
    try:
        db.delete(db_job_definition)
        db.commit()
        return db_job_definition
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting job definition: {e}")
        raise HTTPException(status_code=400, detail="Error deleting job definition")


def get_job_definitions_by_candidate(db: Session, candidate_marketing_id: int) -> List[JobDefinitionORM]:
    """Get all job definitions for a specific candidate"""
    return db.query(JobDefinitionORM).filter(
        JobDefinitionORM.candidate_marketing_id == candidate_marketing_id
    ).all()
