import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.dialects.mysql import insert
from fapi.db.models import JobLinkClicksORM, AuthUserORM, CandidateORM, JobListingORM
from fapi.utils.table_fingerprint import generate_version_for_model
from fastapi import Response
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def track_clicks_with_cache_invalidation(
    db: Session,
    authuser_id: int,
    clicks: list,
) -> dict:

    if not authuser_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="User identity not found in token")

    logger.info(f"[CLICK_DEBUG] POST track-clicks-batch authuser_id={authuser_id}, clicks={clicks}")
    processed_count = bulk_upsert_job_clicks(
        db=db,
        authuser_id=authuser_id,
        clicks=clicks,
    )
    logger.info(f"[CLICK_DEBUG] processed: {processed_count}")

    try:
        from fapi.core.cache import invalidate_cache
        invalidate_cache("candidates")
    except Exception as cache_err:
        logger.warning(f"Cache invalidation failed after click tracking: {cache_err}")

    return {"status": "success", "processed": processed_count}

def bulk_upsert_job_clicks(db: Session, authuser_id: int, clicks: List[Dict[str, Any]]) -> int:
    """
    Perform a single bulk UPSERT to MySQL for a batch of clicks.
    Optimized for Service Worker flushes.
    """
    if not clicks:
        return 0

    # Normalize authuser_id to AuthUserORM.id if candidate_id was passed
    target_authuser_id = authuser_id
    auth_user = db.query(AuthUserORM.id).filter(AuthUserORM.id == authuser_id).first()
    if not auth_user:
        cand = db.query(CandidateORM).filter(CandidateORM.id == authuser_id).first()
        if cand and cand.email:
            linked_user = db.query(AuthUserORM).filter(func.lower(AuthUserORM.uname) == func.lower(cand.email)).first()
            if linked_user:
                target_authuser_id = linked_user.id

    logger.info(f"[CLICK_TRACKING] Starting bulk_upsert_job_clicks for user_id={authuser_id} (target={target_authuser_id}), clicks_count={len(clicks)}")

    try:
        processed_count = 0
        for click in clicks:
            try:
                job_id = click.get("job_listing_id")
                count = click.get("count", 1)

                if not job_id:
                    continue

                # Ensure job_listing_id exists in job_listing table before inserting into job_link_clicks
                existing_job = db.query(JobListingORM.id).filter(JobListingORM.id == job_id).first()
                if not existing_job:
                    try:
                        db.execute(
                            insert(JobListingORM).values(
                                id=job_id,
                                title="Job Listing",
                                company_name="Company"
                            ).on_duplicate_key_update(id=job_id)
                        )
                        db.flush()
                    except Exception as job_err:
                        logger.warning(f"[CLICK_TRACKING] Failed to auto-ensure JobListing {job_id}: {job_err}")

                # SQLAlchemy core insert for ON DUPLICATE KEY UPDATE support
                stmt = insert(JobLinkClicksORM).values(
                    authuser_id=target_authuser_id,
                    job_listing_id=job_id,
                    click_count=count,
                    first_clicked_at=func.now(),
                    last_clicked_at=func.now()
                )

                # Build the update clause for existing records
                update_stmt = stmt.on_duplicate_key_update(
                    click_count=JobLinkClicksORM.click_count + count,
                    last_clicked_at=func.now()
                )

                db.execute(update_stmt)
                processed_count += 1
                logger.info(f"[CLICK_TRACKING] Successfully recorded click for user_id={authuser_id}, job_listing_id={job_id}, count={count}")
            except Exception as inner_e:
                logger.warning(f"[CLICK_TRACKING] Skipping job click error for job_id {job_id}: {str(inner_e)}")
                db.rollback() # Rollback the single failed statement
                continue
        
        db.commit()
        logger.info(f"[CLICK_TRACKING] Committed {processed_count} click upserts for user_id={authuser_id}")
        return processed_count
    except Exception as e:
        db.rollback()
        logger.error(f"[CLICK_TRACKING] Bulk upsert failed for user_id={authuser_id}: {str(e)}")
        raise e


def get_job_click_analytics(db: Session) -> List[Dict[str, Any]]:
    """
    Get full click analytics with 3-table join.
    """
    results = (
        db.query(
            JobLinkClicksORM.id,
            JobLinkClicksORM.authuser_id,
            JobLinkClicksORM.job_listing_id,
            func.coalesce(CandidateORM.full_name, AuthUserORM.fullname).label("full_name"),
            AuthUserORM.uname.label("email"),
            JobListingORM.title.label("job_title"),
            JobListingORM.company_name,
            JobLinkClicksORM.click_count,
            JobLinkClicksORM.first_clicked_at,
            JobLinkClicksORM.last_clicked_at
        )
        .join(AuthUserORM, JobLinkClicksORM.authuser_id == AuthUserORM.id)
        .join(JobListingORM, JobLinkClicksORM.job_listing_id == JobListingORM.id)
        .outerjoin(CandidateORM, func.lower(AuthUserORM.uname) == func.lower(CandidateORM.email))
        .order_by(JobLinkClicksORM.last_clicked_at.desc())
        .all()
    )
    
    return [
        {
            "id": r.id,
            "authuser_id": r.authuser_id,
            "job_listing_id": r.job_listing_id,
            "full_name": r.full_name,
            "email": r.email,
            "job_title": r.job_title,
            "company_name": r.company_name,
            "click_count": r.click_count,
            "first_clicked_at": r.first_clicked_at,
            "last_clicked_at": r.last_clicked_at
        }
        for r in results
    ]

def get_my_job_click_analytics(db: Session, authuser_id: int) -> List[Dict[str, Any]]:
    """
    Get click analytics for a single authenticated user (their own job listing clicks).
    """
    results = (
        db.query(
            JobLinkClicksORM.id,
            JobLinkClicksORM.job_listing_id,
            JobListingORM.title.label("job_title"),
            JobListingORM.company_name,
            JobLinkClicksORM.click_count,
            JobLinkClicksORM.first_clicked_at,
            JobLinkClicksORM.last_clicked_at
        )
        .outerjoin(JobListingORM, JobLinkClicksORM.job_listing_id == JobListingORM.id)
        .filter(JobLinkClicksORM.authuser_id == authuser_id)
        .order_by(JobLinkClicksORM.last_clicked_at.desc())
        .all()
    )

    return [
        {
            "id": r.id,
            "job_listing_id": r.job_listing_id,
            "job_title": r.job_title or "Job listing no longer available",
            "company_name": r.company_name or "—",
            "click_count": r.click_count,
            "first_clicked_at": r.first_clicked_at,
            "last_clicked_at": r.last_clicked_at
        }
        for r in results
    ]

def get_paginated_job_click_analytics(db: Session, page: int = 1, page_size: int = 5000) -> Dict[str, Any]:
    """
    Get paginated full click analytics with 3-table join.
    """
    query = (
        db.query(
            JobLinkClicksORM.id,
            JobLinkClicksORM.authuser_id,
            JobLinkClicksORM.job_listing_id,
            func.coalesce(CandidateORM.full_name, AuthUserORM.fullname).label("full_name"),
            AuthUserORM.uname.label("email"),
            JobListingORM.title.label("job_title"),
            JobListingORM.company_name,
            JobLinkClicksORM.click_count,
            JobLinkClicksORM.first_clicked_at,
            JobLinkClicksORM.last_clicked_at
        )
        .join(AuthUserORM, JobLinkClicksORM.authuser_id == AuthUserORM.id)
        .join(JobListingORM, JobLinkClicksORM.job_listing_id == JobListingORM.id)
        .outerjoin(CandidateORM, func.lower(AuthUserORM.uname) == func.lower(CandidateORM.email))
    )

    total_count = query.count()
    offset = (page - 1) * page_size
    results = query.order_by(JobLinkClicksORM.last_clicked_at.desc()).offset(offset).limit(page_size).all()
    has_next = (offset + page_size) < total_count
    
    data = [
        {
            "id": r.id,
            "authuser_id": r.authuser_id,
            "job_listing_id": r.job_listing_id,
            "full_name": r.full_name,
            "email": r.email,
            "job_title": r.job_title,
            "company_name": r.company_name,
            "click_count": r.click_count,
            "first_clicked_at": r.first_clicked_at,
            "last_clicked_at": r.last_clicked_at
        }
        for r in results
    ]
    
    return {
        "data": data,
        "page": page,
        "page_size": page_size,
        "total": total_count,
        "has_next": has_next
    }

def get_job_clicks_version(db: Session) -> Response:
    """
    Returns the table version for caching.
    """
    return generate_version_for_model(db, JobLinkClicksORM)

from fastapi import HTTPException

def delete_job_click(db: Session, click_id: int) -> bool:
    """
    Deletes a specific job click record by ID.
    """
    try:
        record = db.query(JobLinkClicksORM).filter(JobLinkClicksORM.id == click_id).first()
        if not record:
            return False
        db.delete(record)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting job click {click_id}: {str(e)}")
        raise e

def get_today_job_click_summary(db: Session, authuser_id: int, target_clicks: int = 30) -> Dict[str, Any]:
    """
    Calculate today's job board clicks and goal status for the given authuser.

    Counts the number of distinct job listings (rows) whose last_clicked_at
    falls on today's date (server local or UTC). Each row in job_link_clicks represents a unique
    (authuser, job_listing) pair — so counting rows with last_clicked_at == today
    gives the number of unique jobs the user has clicked today.
    """
    from datetime import datetime, time, timezone
    from sqlalchemy import or_

    today_date = datetime.now().date()
    today_utc_date = datetime.now(timezone.utc).date()

    # Resolve candidate_id if authuser is linked to CandidateORM by email or ID
    possible_user_ids = {authuser_id}
    auth_user = db.query(AuthUserORM).filter(AuthUserORM.id == authuser_id).first()
    if auth_user and auth_user.uname:
        cand = db.query(CandidateORM).filter(func.lower(CandidateORM.email) == func.lower(auth_user.uname)).first()
        if cand:
            possible_user_ids.add(cand.id)
    else:
        cand = db.query(CandidateORM).filter(CandidateORM.id == authuser_id).first()
        if cand and cand.email:
            auth_user = db.query(AuthUserORM).filter(func.lower(AuthUserORM.uname) == func.lower(cand.email)).first()
            if auth_user:
                possible_user_ids.add(auth_user.id)

    logger.info(f"[CLICK_TRACKING] Querying today clicks for authuser_id={authuser_id}, possible_ids={possible_user_ids}, today_date={today_date}")

    clicks_today = (
        db.query(func.coalesce(func.sum(JobLinkClicksORM.click_count), 0))
        .filter(
            JobLinkClicksORM.authuser_id.in_(possible_user_ids),
            or_(
                func.date(JobLinkClicksORM.last_clicked_at) == today_date,
                func.date(JobLinkClicksORM.last_clicked_at) == today_utc_date,
                func.date(JobLinkClicksORM.last_clicked_at) == func.current_date(),
            )
        )
        .scalar()
    ) or 0

    job_board_clicks = int(clicks_today)
    remaining_clicks = max(0, target_clicks - job_board_clicks)

    if remaining_clicks == 0:
        status = "TARGET_COMPLETED"
        status_label = "GOAL COMPLETED"
        message = "Today's goal completed."
    else:
        status = "BELOW_TARGET"
        status_label = "BELOW TARGET"
        message = f"You need {remaining_clicks} more clicks to reach today's goal."

    logger.info(f"[CLICK_DEBUG] GET job-clicks-today authuser_id={authuser_id}, possible_ids={possible_user_ids}, clicks_today={clicks_today}, final={job_board_clicks}")
    logger.info(f"[CLICK_TRACKING] Today click summary for authuser_id={authuser_id}: job_board_clicks={job_board_clicks}, remaining_clicks={remaining_clicks}")

    return {
        "job_board_clicks": job_board_clicks,
        "target_clicks": target_clicks,
        "remaining_clicks": remaining_clicks,
        "status": status,
        "status_label": status_label,
        "message": message,
    }


def get_total_job_click_summary(db: Session, authuser_id: int) -> dict:
    """
    Get all-time total Job Board clicks for the authenticated user across ALL dates.
    """
    possible_user_ids = {authuser_id}
    auth_user = db.query(AuthUserORM).filter(AuthUserORM.id == authuser_id).first()
    if auth_user and auth_user.uname:
        cand = db.query(CandidateORM).filter(func.lower(CandidateORM.email) == func.lower(auth_user.uname)).first()
        if cand:
            possible_user_ids.add(cand.id)
    else:
        cand = db.query(CandidateORM).filter(CandidateORM.id == authuser_id).first()
        if cand and cand.email:
            auth_user = db.query(AuthUserORM).filter(func.lower(AuthUserORM.uname) == func.lower(cand.email)).first()
            if auth_user:
                possible_user_ids.add(auth_user.id)

    total_clicks = (
        db.query(func.coalesce(func.sum(JobLinkClicksORM.click_count), 0))
        .filter(JobLinkClicksORM.authuser_id.in_(possible_user_ids))
        .scalar()
    ) or 0

    logger.info(f"[CLICK_TRACKING] Total all-time click summary for authuser_id={authuser_id}: total_clicks={total_clicks}")

    return {
        "job_board_clicks": int(total_clicks),
        "total_job_board_clicks": int(total_clicks)
    }

