import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from fapi.db import schemas
from fapi.db.database import get_db
from fapi.utils import job_run_utils

logger = logging.getLogger(__name__)
router = APIRouter()

security = HTTPBearer()


@router.get("/job-run", response_model=List[schemas.JobRunOut])
def read_job_runs(
    search: Optional[str] = Query(None, description="Search by run status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get all job runs"""
    return job_run_utils.get_all_job_runs(db, skip=skip, limit=limit, search=search)


@router.get("/job-run/{job_run_id}", response_model=schemas.JobRunOut)
def read_job_run(
    job_run_id: int = Path(...),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get a specific job run by ID"""
    db_job_run = job_run_utils.get_job_run_by_id(db, job_run_id)
    if not db_job_run:
        raise HTTPException(status_code=404, detail="Job run not found")
    return db_job_run


@router.get("/job-run/definition/{job_definition_id}", response_model=List[schemas.JobRunOut])
def read_job_runs_by_definition(
    job_definition_id: int = Path(...),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get all job runs for a specific job definition"""
    return job_run_utils.get_job_runs_by_definition(db, job_definition_id)


@router.get("/job-run/schedule/{job_schedule_id}", response_model=List[schemas.JobRunOut])
def read_job_runs_by_schedule(
    job_schedule_id: int = Path(...),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get all job runs for a specific job schedule"""
    return job_run_utils.get_job_runs_by_schedule(db, job_schedule_id)


@router.get("/job-run/status/{run_status}", response_model=List[schemas.JobRunOut])
def read_job_runs_by_status(
    run_status: str = Path(...),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get all job runs with a specific status"""
    return job_run_utils.get_job_runs_by_status(db, run_status)


@router.post("/job-run", response_model=schemas.JobRunOut)
def create_job_run(
    job_run: schemas.JobRunCreate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Create a new job run"""
    return job_run_utils.create_job_run(db, job_run)


@router.put("/job-run/{job_run_id}", response_model=schemas.JobRunOut)
def update_job_run(
    job_run_id: int,
    job_run: schemas.JobRunUpdate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Update an existing job run"""
    db_job_run = job_run_utils.update_job_run(db, job_run_id, job_run)
    if not db_job_run:
        raise HTTPException(status_code=404, detail="Job run not found")
    return db_job_run


@router.delete("/job-run/{job_run_id}", response_model=schemas.JobRunOut)
def delete_job_run(
    job_run_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Delete a job run"""
    db_job_run = job_run_utils.delete_job_run(db, job_run_id)
    if not db_job_run:
        raise HTTPException(status_code=404, detail="Job run not found")
    return db_job_run
