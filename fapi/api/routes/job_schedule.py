import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from fapi.db import schemas
from fapi.db.database import get_db
from fapi.utils import job_schedule_utils

logger = logging.getLogger(__name__)
router = APIRouter()

security = HTTPBearer()


@router.get("/job-schedule", response_model=List[schemas.JobScheduleOut])
def read_job_schedules(
    search: Optional[str] = Query(None, description="Search by frequency or timezone"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get all job schedules"""
    return job_schedule_utils.get_all_job_schedules(db, skip=skip, limit=limit, search=search)


@router.get("/job-schedule/{job_schedule_id}", response_model=schemas.JobScheduleOut)
def read_job_schedule(
    job_schedule_id: int = Path(...),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get a specific job schedule by ID"""
    db_job_schedule = job_schedule_utils.get_job_schedule_by_id(db, job_schedule_id)
    if not db_job_schedule:
        raise HTTPException(status_code=404, detail="Job schedule not found")
    return db_job_schedule


@router.get("/job-schedule/definition/{job_definition_id}", response_model=List[schemas.JobScheduleOut])
def read_job_schedules_by_definition(
    job_definition_id: int = Path(...),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get all job schedules for a specific job definition"""
    return job_schedule_utils.get_job_schedules_by_definition(db, job_definition_id)


@router.get("/job-schedule/enabled/all", response_model=List[schemas.JobScheduleOut])
def read_enabled_job_schedules(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get all enabled job schedules"""
    return job_schedule_utils.get_enabled_schedules(db)


@router.post("/job-schedule", response_model=schemas.JobScheduleOut)
def create_job_schedule(
    job_schedule: schemas.JobScheduleCreate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Create a new job schedule"""
    return job_schedule_utils.create_job_schedule(db, job_schedule)


@router.put("/job-schedule/{job_schedule_id}", response_model=schemas.JobScheduleOut)
def update_job_schedule(
    job_schedule_id: int,
    job_schedule: schemas.JobScheduleUpdate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Update an existing job schedule"""
    db_job_schedule = job_schedule_utils.update_job_schedule(db, job_schedule_id, job_schedule)
    if not db_job_schedule:
        raise HTTPException(status_code=404, detail="Job schedule not found")
    return db_job_schedule


@router.delete("/job-schedule/{job_schedule_id}", response_model=schemas.JobScheduleOut)
def delete_job_schedule(
    job_schedule_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Delete a job schedule"""
    db_job_schedule = job_schedule_utils.delete_job_schedule(db, job_schedule_id)
    if not db_job_schedule:
        raise HTTPException(status_code=404, detail="Job schedule not found")
    return db_job_schedule
