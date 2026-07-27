from fapi.utils.permission_gate import enforce_access
from fapi.utils.auth_dependencies import staff_or_admin_required
from fastapi import APIRouter, Depends, HTTPException, Security, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import List
import logging

from fapi.db.database import get_db
from fapi.db.schemas import JobLinkClickBatchIn, JobLinkClickAnalytics
from fapi.utils.job_click_utils import bulk_upsert_job_clicks, get_job_click_analytics
from fapi.utils.permission_gate import enforce_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidates", tags=["Job Link Click Tracking"])
security = HTTPBearer()

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
    try:
        if not user or not hasattr(user, 'id'):
            raise HTTPException(status_code=401, detail="User identity not found in token")

        processed_count = bulk_upsert_job_clicks(
            db=db,
            authuser_id=user.id,
            clicks=[c.model_dump() for c in payload.clicks]
        )

        # Invalidate the dashboard cache so candidate_stats refreshes on next load
        try:
            from fapi.core.cache import invalidate_cache
            invalidate_cache("candidates")
        except Exception as cache_err:
            logger.warning(f"Cache invalidation failed after click tracking: {cache_err}")
            
        return {"status": "success", "processed": processed_count}
    except Exception as e:
        logger.error(f"Error tracking batch: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to track clicks: {str(e)}")


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
    try:
        from fapi.utils.job_click_utils import get_paginated_job_click_analytics
        return get_paginated_job_click_analytics(db, page=page, page_size=page_size)
    except Exception as e:
        logger.error(f"Error fetching click analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch analytics: {str(e)}")

@router.get("/click-analytics/me")
def get_my_job_click_analytics_endpoint(
    db: Session = Depends(get_db),
    user: any = Depends(enforce_access),
):
    """
    **Get click analytics for the currently authenticated candidate only**
    """
    try:
        if not user or not hasattr(user, 'id'):
            raise HTTPException(status_code=401, detail="User identity not found in token")

        from fapi.utils.job_click_utils import get_my_job_click_analytics
        return get_my_job_click_analytics(db, authuser_id=user.id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching own click analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch analytics: {str(e)}")


@router.get("/click-analytics", response_model=List[JobLinkClickAnalytics])
def get_job_click_analytics_endpoint(
    db: Session = Depends(get_db),
    user: any = Depends(enforce_access),
    _staff: any = Depends(staff_or_admin_required),
):
    """
    **Get comprehensive click analytics from MySQL**
    """
    try:
        return get_job_click_analytics(db)
    except Exception as e:
        logger.error(f"Error fetching click analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch analytics: {str(e)}")


@router.head("/click-analytics")
def check_click_analytics_version(
    db: Session = Depends(get_db),
    user: any = Depends(enforce_access),
    _staff: any = Depends(staff_or_admin_required),
):
    """
    **Check data version for caching**
    """
    from fapi.utils.job_click_utils import get_job_clicks_version
    return get_job_clicks_version(db)

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
    try:
        from fapi.utils.job_click_utils import delete_job_click
        success = delete_job_click(db, click_id)
        if not success:
            raise HTTPException(status_code=404, detail="Click record not found")
        return {"status": "success", "message": "Click record deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting click analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete click: {str(e)}")
