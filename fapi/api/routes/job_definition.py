import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from fapi.db import schemas
from fapi.db.database import get_db
from fapi.utils import job_definition_utils

logger = logging.getLogger(__name__)
router = APIRouter()

security = HTTPBearer()


@router.get("/job-definition", response_model=List[schemas.JobDefinitionOut])
def read_job_definitions(
    search: Optional[str] = Query(None, description="Search by job type or status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get all job definitions"""
    return job_definition_utils.get_all_job_definitions(db, skip=skip, limit=limit, search=search)


@router.get("/job-definition/{job_definition_id}", response_model=schemas.JobDefinitionOut)
def read_job_definition(
    job_definition_id: int = Path(...),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get a specific job definition by ID"""
    db_job_definition = job_definition_utils.get_job_definition_by_id(db, job_definition_id)
    if not db_job_definition:
        raise HTTPException(status_code=404, detail="Job definition not found")
    return db_job_definition


@router.get("/job-definition/candidate/{candidate_marketing_id}", response_model=List[schemas.JobDefinitionOut])
def read_job_definitions_by_candidate(
    candidate_marketing_id: int = Path(...),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get all job definitions for a specific candidate"""
    return job_definition_utils.get_job_definitions_by_candidate(db, candidate_marketing_id)


@router.post("/job-definition", response_model=schemas.JobDefinitionOut)
def create_job_definition(
    job_definition: schemas.JobDefinitionCreate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Create a new job definition"""
    return job_definition_utils.create_job_definition(db, job_definition)


@router.put("/job-definition/{job_definition_id}", response_model=schemas.JobDefinitionOut)
def update_job_definition(
    job_definition_id: int,
    job_definition: schemas.JobDefinitionUpdate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Update an existing job definition"""
    db_job_definition = job_definition_utils.update_job_definition(db, job_definition_id, job_definition)
    if not db_job_definition:
        raise HTTPException(status_code=404, detail="Job definition not found")
    return db_job_definition


@router.delete("/job-definition/{job_definition_id}", response_model=schemas.JobDefinitionOut)
def delete_job_definition(
    job_definition_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Delete a job definition"""
    db_job_definition = job_definition_utils.delete_job_definition(db, job_definition_id)
    if not db_job_definition:
        raise HTTPException(status_code=404, detail="Job definition not found")
    return db_job_definition
