import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.db.schemas import (
    EmailActivityLogCreate,
    EmailActivityLogUpdate,
    EmailActivityLogOut
)
from fapi.utils import email_activity_log_utils

logger = logging.getLogger(__name__)
router = APIRouter()

# Use HTTPBearer for Swagger auth
security = HTTPBearer()


# ---------- CRUD: Email Activity Log ----------

@router.get("/email_activity_logs", response_model=List[EmailActivityLogOut])
def get_all_email_activity_logs(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Get all email activity logs with candidate names"""
    return email_activity_log_utils.get_all_email_activity_logs(db)


@router.get("/email_activity_logs/{log_id}", response_model=EmailActivityLogOut)
def get_email_activity_log(
    log_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Get single email activity log by ID"""
    return email_activity_log_utils.get_email_activity_log_by_id(db, log_id)


@router.get("/email_activity_logs/candidate_marketing/{candidate_marketing_id}", response_model=List[EmailActivityLogOut])
def get_logs_by_candidate_marketing(
    candidate_marketing_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Get all logs for specific candidate marketing ID"""
    return email_activity_log_utils.get_logs_by_candidate_marketing_id(db, candidate_marketing_id)


@router.post("/email_activity_logs", response_model=EmailActivityLogOut)
def create_email_activity_log(
    log_data: EmailActivityLogCreate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Create new email activity log (prevents duplicates)"""
    return email_activity_log_utils.create_email_activity_log(db, log_data)


@router.put("/email_activity_logs/{log_id}", response_model=EmailActivityLogOut)
def update_email_activity_log(
    log_id: int = Path(..., gt=0),
    update_data: EmailActivityLogUpdate = ...,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Update email activity log"""
    logger.info(f"Update schema received: {update_data.dict(exclude_unset=True)}")
    return email_activity_log_utils.update_email_activity_log(db, log_id, update_data)


@router.delete("/email_activity_logs/{log_id}")
def delete_email_activity_log(
    log_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Delete email activity log"""
    return email_activity_log_utils.delete_email_activity_log(db, log_id)