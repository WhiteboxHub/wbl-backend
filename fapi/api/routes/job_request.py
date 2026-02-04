import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from fapi.db import schemas
from fapi.db.database import get_db
from fapi.utils import job_request_utils

logger = logging.getLogger(__name__)
router = APIRouter()

security = HTTPBearer()


@router.get("/job-request", response_model=List[schemas.JobRequestOut])
def read_job_requests(
    search: Optional[str] = Query(None, description="Search by job type or status"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get all job requests"""
    return job_request_utils.get_all_job_requests(db, search=search)


@router.get("/job-request/{job_request_id}", response_model=schemas.JobRequestOut)
def read_job_request(
    job_request_id: int = Path(...),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get a specific job request by ID"""
    db_job_request = job_request_utils.get_job_request_by_id(db, job_request_id)
    if not db_job_request:
        raise HTTPException(status_code=404, detail="Job request not found")
    return db_job_request


@router.get("/job-request/candidate/{candidate_marketing_id}", response_model=List[schemas.JobRequestOut])
def read_job_requests_by_candidate(
    candidate_marketing_id: int = Path(...),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get all job requests for a specific candidate"""
    return job_request_utils.get_job_requests_by_candidate(db, candidate_marketing_id)


@router.get("/job-request/status/{status}", response_model=List[schemas.JobRequestOut])
def read_job_requests_by_status(
    status: str = Path(...),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get all job requests with a specific status"""
    return job_request_utils.get_job_requests_by_status(db, status)


@router.get("/job-request/pending/all", response_model=List[schemas.JobRequestOut])
def read_pending_job_requests(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get all pending job requests"""
    return job_request_utils.get_pending_job_requests(db)


@router.post("/job-request", response_model=schemas.JobRequestOut)
def create_job_request(
    job_request: schemas.JobRequestCreate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Create a new job request"""
    return job_request_utils.create_job_request(db, job_request)


@router.put("/job-request/{job_request_id}", response_model=schemas.JobRequestOut)
def update_job_request(
    job_request_id: int,
    job_request: schemas.JobRequestUpdate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Update an existing job request"""
    db_job_request = job_request_utils.update_job_request(db, job_request_id, job_request)
    if not db_job_request:
        raise HTTPException(status_code=404, detail="Job request not found")
    return db_job_request


@router.delete("/job-request/{job_request_id}", response_model=schemas.JobRequestOut)
def delete_job_request(
    job_request_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Delete a job request"""
    db_job_request = job_request_utils.delete_job_request(db, job_request_id)
    if not db_job_request:
        raise HTTPException(status_code=404, detail="Job request not found")
    return db_job_request
