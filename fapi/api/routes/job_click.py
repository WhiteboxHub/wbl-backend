from fapi.utils.permission_gate import enforce_access
from fapi.utils.auth_dependencies import staff_or_admin_required
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import logging

from fapi.db.database import get_db
from fapi.db.schemas import JobLinkClickBatchIn, JobLinkClickAnalytics, TodayJobClickSummary
from fapi.utils.job_click_utils import (
    bulk_upsert_job_clicks,
    get_job_click_analytics,
    get_my_job_click_analytics,
    get_paginated_job_click_analytics,
    get_job_clicks_version,
    delete_job_click,
    track_clicks_with_cache_invalidation,
    get_today_job_click_summary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidates", tags=["Job Link Click Tracking"])


@router.post("/track-clicks-batch")
def track_clicks_batch_endpoint(
    payload: JobLinkClickBatchIn,
    db: Session = Depends(get_db),
    user: any = Depends(enforce_access),
):
    """
    **Batch track candidate clicks on job listings**

    Direct bulk write to MySQL (optimized for Service Worker flushes).
    """
    return track_clicks_with_cache_invalidation(
        db=db,
        authuser_id=user.id,
        clicks=[c.model_dump() for c in payload.clicks],
    )


@router.get("/click-analytics/paginated")
def get_job_click_paginated_endpoint(
    page: int = 1,
    page_size: int = 5000,
    db: Session = Depends(get_db),
    user: any = Depends(enforce_access),
    _staff: any = Depends(staff_or_admin_required),
):
    """
    **Get paginated comprehensive click analytics from MySQL**
    """
    return get_paginated_job_click_analytics(db, page=page, page_size=page_size)


@router.get("/click-analytics/me")
def get_my_job_click_analytics_endpoint(
    db: Session = Depends(get_db),
    user: any = Depends(enforce_access),
):
    """
    **Get click analytics for the currently authenticated candidate only**
    """
    return get_my_job_click_analytics(db, authuser_id=user.id)


@router.get("/click-analytics", response_model=List[JobLinkClickAnalytics])
def get_job_click_analytics_endpoint(
    db: Session = Depends(get_db),
    user: any = Depends(enforce_access),
    _staff: any = Depends(staff_or_admin_required),
):
    """
    **Get comprehensive click analytics from MySQL**
    """
    return get_job_click_analytics(db)


@router.head("/click-analytics")
def check_click_analytics_version(
    db: Session = Depends(get_db),
    user: any = Depends(enforce_access),
    _staff: any = Depends(staff_or_admin_required),
):
    """
    **Check data version for caching**
    """
    return get_job_clicks_version(db)


@router.get("/click-summary/today", response_model=TodayJobClickSummary)
@router.get("/job-clicks/today", response_model=TodayJobClickSummary)
def get_today_job_click_summary_endpoint(
    db: Session = Depends(get_db),
    user: any = Depends(enforce_access),
):
    """
    **Get Job Board Clicks Today summary & daily goal status for authenticated user**
    """
    return get_today_job_click_summary(db, authuser_id=user.id)


@router.delete("/click-analytics/{click_id}")
def delete_click_analytics_endpoint(
    click_id: int,
    db: Session = Depends(get_db),
    user: any = Depends(enforce_access),
    _staff: any = Depends(staff_or_admin_required),
):
    """
    **Delete a job click analytics record**
    """
    success = delete_job_click(db, click_id, user)
    if not success:
        raise HTTPException(status_code=404, detail="Click record not found")
    return {"status": "success", "message": "Click record deleted"}
