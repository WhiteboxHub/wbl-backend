"""WboxCLI usage analytics API (ingest from CLI, read for Avatar admin)."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.db.schemas import (
    CliApplyRunBackfillResponse,
    CliApplyRunLatestOut,
    CliUsageEventBulkCreate,
    CliUsageEventBulkResponse,
    CliUsageAnalyticsSummary,
    CliUsageUserSummary,
    CliUsageUserMetricsUpdate,
    CliUsageUserMutationResponse,
    PaginatedCliUsageEvents,
    PaginatedCliUsageUsers,
)
from fapi.utils import cli_analytics_utils
from fapi.utils.auth_dependencies import staff_or_admin_required
from fapi.utils.user_dashboard_utils import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["WboxCLI Analytics"])


@router.post("/usage_events/bulk", response_model=CliUsageEventBulkResponse)
def ingest_usage_events_bulk(
    body: CliUsageEventBulkCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Ingest usage events from WboxCLI (authenticated WBL users)."""
    _ = current_user
    return cli_analytics_utils.insert_usage_events_bulk(db, body.events)


@router.get("/summary", response_model=CliUsageAnalyticsSummary)
def analytics_summary(
    db: Session = Depends(get_db),
    current_user=Depends(staff_or_admin_required),
):
    """Global WboxCLI usage counters for staff dashboards."""
    _ = current_user
    return cli_analytics_utils.get_global_summary(db)


@router.post("/apply-runs/backfill", response_model=CliApplyRunBackfillResponse)
def backfill_apply_analytics(
    limit: Optional[int] = Query(None, ge=1, le=100000),
    db: Session = Depends(get_db),
    current_user=Depends(staff_or_admin_required),
):
    """Staff: backfill wboxcli_apply_analytics from historical cli_usage_events."""
    _ = current_user
    return cli_analytics_utils.backfill_apply_analytics_from_events(db, limit=limit)


@router.get("/users/{user_id}/applications/summary", response_model=CliUsageUserSummary)
def analytics_user_summary(
    user_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(staff_or_admin_required),
):
    """Per-user application totals from CLI usage events."""
    _ = current_user
    return cli_analytics_utils.get_user_summary(db, user_id)


@router.get("/users/{user_id:path}/apply-run/latest", response_model=CliApplyRunLatestOut)
def latest_apply_run_for_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(staff_or_admin_required),
):
    """Latest apply_run_log JSON and per-job rows for staff analytics UI."""
    _ = current_user
    payload = cli_analytics_utils.get_latest_apply_run_for_user(db, user_id)
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail=f"No apply run log found for user_id={user_id!r}",
        )
    return payload


@router.patch("/users/{user_id:path}", response_model=CliUsageUserMutationResponse)
def update_usage_user_metrics(
    user_id: str,
    body: CliUsageUserMetricsUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(staff_or_admin_required),
):
    """Staff: adjust aggregated job counters for a WboxCLI user."""
    _ = current_user
    try:
        return cli_analytics_utils.update_user_usage_metrics(db, user_id, body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/users/{user_id:path}", response_model=CliUsageUserMutationResponse)
def delete_usage_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(staff_or_admin_required),
):
    """Staff: delete all CLI usage events for a WboxCLI user."""
    _ = current_user
    try:
        return cli_analytics_utils.delete_user_usage_events(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/users", response_model=PaginatedCliUsageUsers)
def list_usage_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    user_id: Optional[str] = Query(None, description="Filter by user email (partial match)"),
    db: Session = Depends(get_db),
    current_user=Depends(staff_or_admin_required),
):
    """Per-user job application totals (one row per WBL login)."""
    _ = current_user
    return cli_analytics_utils.get_paginated_users(
        db, page=page, page_size=page_size, user_id=user_id
    )


@router.get("/usage_events", response_model=PaginatedCliUsageEvents)
def list_usage_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    user_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(staff_or_admin_required),
):
    """Paginated recent CLI usage events for admin review."""
    _ = current_user
    return cli_analytics_utils.get_paginated_events(
        db, page=page, page_size=page_size, user_id=user_id
    )
