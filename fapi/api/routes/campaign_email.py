from fastapi import Security, APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import logging
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db.schemas import (
    CampaignEmailOut, CampaignEmailCreate, CampaignEmailUpdate
)
from fapi.utils import campaign_email_utils

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/campaign-emails", tags=["Campaign Emails"]
)

security = HTTPBearer()


@router.head("/")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return campaign_email_utils.get_version(db)


@router.get("/paginated")
def get_campaign_emails_paginated(
    page: int = 1,
    limit: int = 100,
    search: str = None,
    search_by: str = "all",
    sort: str = Query("created_at:desc"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return campaign_email_utils.get_paginated(db, page, limit, search, search_by, sort)


@router.get("/", response_model=List[CampaignEmailOut])
def get_all_campaign_emails(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return campaign_email_utils.get_all(db)


@router.get("/by-workflow/{workflow_id}",
            response_model=List[CampaignEmailOut])
def get_campaign_emails_by_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return campaign_email_utils.get_by_workflow(db, workflow_id)


@router.get("/{record_id}", response_model=CampaignEmailOut)
def get_campaign_email(
    record_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return campaign_email_utils.get_by_id(db, record_id)


@router.post("/", response_model=CampaignEmailOut,
             status_code=status.HTTP_201_CREATED)
def create_campaign_email(
    data: CampaignEmailCreate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    row = campaign_email_utils.create(db, data)
    logger.info(
        "Created campaign_email id=%s workflow=%s",
        row.id, row.workflow_id,
    )
    return row


@router.get("/bulk", status_code=status.HTTP_201_CREATED)
def create_bulk_campaign_emails(
    data: List[CampaignEmailCreate],
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    count = campaign_email_utils.create_bulk(db, data)
    logger.info("Bulk created %s campaign_emails", count)
    return {
        "message": f"Successfully inserted {count} records",
        "count": count
    }


@router.put("/{record_id}", response_model=CampaignEmailOut)
def update_campaign_email(
    record_id: int,
    data: CampaignEmailUpdate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    row = campaign_email_utils.update(db, record_id, data)
    logger.info("Updated campaign_email id=%s", record_id)
    return row


@router.delete("/{record_id}")
def delete_campaign_email(
    record_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return campaign_email_utils.delete(db, record_id)


# ── Outreach Orchestrator Endpoints (no extra auth — internal calls) ──────────

@router.post("/candidates/{candidate_id}/snapshot")
def trigger_snapshot(
    candidate_id: int,
    workflow_id: int,
    scheduler_id: int = Query(None),
    db: Session = Depends(get_db),
):
    """
    Generate a frozen snapshot of all eligible recruiter emails for a
    candidate. Inserts them into campaign_emails as 'pending'.
    Safe to call multiple times — INSERT IGNORE prevents duplicates.
    """
    return campaign_email_utils.generate_snapshot(
        db, candidate_id, workflow_id, scheduler_id
    )


@router.post("/candidates/{candidate_id}/dispatch")
def trigger_dispatch(
    candidate_id: int,
    limit: int,
    scheduler_id: int = Query(None),
    db: Session = Depends(get_db),
):
    """
    Atomically claim up to `limit` pending emails using FOR UPDATE SKIP LOCKED.
    Returns the locked records so the scheduler can enqueue them to Celery.
    """
    records = campaign_email_utils.dispatch_pending(db, candidate_id, limit, scheduler_id)
    return {
        "message": f"Dispatched {len(records)} emails",
        "records": records,
    }


@router.get("/candidates/{candidate_id}/pending-count")
def get_pending_count(
    candidate_id: int,
    scheduler_id: int = Query(None),
    db: Session = Depends(get_db),
):
    """Return the number of still-pending emails for a candidate."""
    count = campaign_email_utils.get_pending_count(db, candidate_id, scheduler_id)
    return {"candidate_id": candidate_id, "count": count}
