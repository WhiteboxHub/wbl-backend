
# WBL_Backend\fapi\api\routes\jobs.py
from fapi.utils.user_dashboard_utils import get_current_user
from fapi.db.models import AuthUserORM
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.db.schemas import (
    JobActivityLogCreate,
    JobActivityLogUpdate,
    JobActivityLogOut,
    JobTypeOut,
    JobTypeCreate,
    JobTypeUpdate
)
from fapi.utils import jobs_utils

logger = logging.getLogger(__name__)
router = APIRouter()

security = HTTPBearer()


@router.get("/job_activity_logs", response_model=List[JobActivityLogOut])
def get_all_job_activity_logs(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Get all job activity logs with job name, candidate name, and employee name"""
    return jobs_utils.get_all_job_activity_logs(db)


@router.get("/job_activity_logs/{log_id}", response_model=JobActivityLogOut)
def get_job_activity_log(
    log_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Get single job activity log by ID"""
    return jobs_utils.get_job_activity_log_by_id(db, log_id)


@router.get("/job_activity_logs/job/{job_id}", response_model=List[JobActivityLogOut])
def get_logs_by_job(
    job_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Get all logs for specific job ID"""
    return jobs_utils.get_logs_by_job_id(db, job_id)


@router.get("/job_activity_logs/employee/{employee_id}", response_model=List[JobActivityLogOut])
def get_logs_by_employee(
    employee_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Get all logs for specific employee ID"""
    return jobs_utils.get_logs_by_employee_id(db, employee_id)


@router.post("/job_activity_logs", response_model=JobActivityLogOut)
def create_job_activity_log(
    log_data: JobActivityLogCreate,
    db: Session = Depends(get_db),
    current_user: AuthUserORM = Depends(get_current_user)
):
    """Create new job activity log"""
    return jobs_utils.create_job_activity_log(db, log_data, current_user)


@router.put("/job_activity_logs/{log_id}", response_model=JobActivityLogOut)
def update_job_activity_log(
    log_id: int = Path(..., gt=0),
    update_data: JobActivityLogUpdate = ...,
    db: Session = Depends(get_db),
    current_user: AuthUserORM = Depends(get_current_user)
):
    """Update job activity log"""
    return jobs_utils.update_job_activity_log(db, log_id, update_data, current_user)


@router.delete("/job_activity_logs/{log_id}")
def delete_job_activity_log(
    log_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Delete job activity log"""
    return jobs_utils.delete_job_activity_log(db, log_id)


@router.get("/job-types", response_model=List[JobTypeOut])
def get_all_job_types(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Get all job types"""
    return jobs_utils.get_all_job_types(db)


@router.get("/job-types/{job_type_id}", response_model=JobTypeOut)
def get_job_type(
    job_type_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Get single job type by ID"""
    return jobs_utils.get_job_type_by_id(db, job_type_id)


@router.post("/job-types", response_model=JobTypeOut)
def create_job_type(
    job_type_data: JobTypeCreate,
    db: Session = Depends(get_db),
    current_user: AuthUserORM = Depends(get_current_user)
):
    """Create new job type"""
    return jobs_utils.create_job_type(db, job_type_data, current_user)


@router.put("/job-types/{job_type_id}", response_model=JobTypeOut)
def update_job_type(
    job_type_id: int = Path(..., gt=0),
    update_data: JobTypeUpdate = ...,
    db: Session = Depends(get_db),
    current_user: AuthUserORM = Depends(get_current_user)
):
    """Update job type"""
    return jobs_utils.update_job_type(db, job_type_id, update_data, current_user)


@router.delete("/job-types/{job_type_id}")
def delete_job_type(
    job_type_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Delete job type"""
    return jobs_utils.delete_job_type(db, job_type_id)
