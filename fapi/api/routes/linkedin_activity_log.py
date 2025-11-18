# routes.py
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Security
# from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.db.schemas import (
    LinkedInActivityLogCreate,
    LinkedInActivityLogUpdate,
    LinkedInActivityLogOut
)
from fapi.utils import linkedin_activity_log_utils

logger = logging.getLogger(__name__)
router = APIRouter()

# Use HTTPBearer for Swagger auth
# security = HTTPBearer()


# ---------- CRUD: LinkedIn Activity Log ----------

@router.get("/linkedin_activity_logs", response_model=List[LinkedInActivityLogOut])
def get_all_linkedin_activity_logs(
    db: Session = Depends(get_db),
    # credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Get all LinkedIn activity logs with candidate names"""
    return linkedin_activity_log_utils.get_all_linkedin_activity_logs(db)


@router.get("/linkedin_activity_logs/{log_id}", response_model=LinkedInActivityLogOut)
def get_linkedin_activity_log(
    log_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    # credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Get single LinkedIn activity log by ID"""
    return linkedin_activity_log_utils.get_linkedin_activity_log_by_id(db, log_id)


@router.get("/linkedin_activity_logs/candidate/{candidate_id}", response_model=List[LinkedInActivityLogOut])
def get_logs_by_candidate(
    candidate_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    # credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Get all logs for specific candidate ID"""
    return linkedin_activity_log_utils.get_logs_by_candidate_id(db, candidate_id)


@router.post("/linkedin_activity_logs", response_model=LinkedInActivityLogOut)
def create_linkedin_activity_log(
    log_data: LinkedInActivityLogCreate,
    db: Session = Depends(get_db),
    # credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Create new LinkedIn activity log"""
    return linkedin_activity_log_utils.create_linkedin_activity_log(db, log_data)


@router.put("/linkedin_activity_logs/{log_id}", response_model=LinkedInActivityLogOut)
def update_linkedin_activity_log(
    log_id: int = Path(..., gt=0),
    update_data: LinkedInActivityLogUpdate = ...,
    db: Session = Depends(get_db),
    # credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Update LinkedIn activity log"""
    logger.info(f"Update schema received: {update_data.dict(exclude_unset=True)}")
    return linkedin_activity_log_utils.update_linkedin_activity_log(db, log_id, update_data)


@router.delete("/linkedin_activity_logs/{log_id}")
def delete_linkedin_activity_log(
    log_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    # credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Delete LinkedIn activity log"""
    return linkedin_activity_log_utils.delete_linkedin_activity_log(db, log_id)