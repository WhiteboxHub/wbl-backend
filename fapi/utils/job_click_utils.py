import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.dialects.mysql import insert
from fapi.db.models import JobLinkClicksORM, AuthUserORM, CandidateORM, JobListingORM
from fapi.utils.table_fingerprint import generate_version_for_model
from fastapi import Response
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def bulk_upsert_job_clicks(db: Session, authuser_id: int, clicks: List[Dict[str, Any]]) -> int:
    """
    Perform a single bulk UPSERT to MySQL for a batch of clicks.
    Optimized for Service Worker flushes.
    """
    if not clicks:
        return 0

    try:
        processed_count = 0
        for click in clicks:
            try:
                job_id = click.get("job_listing_id")
                count = click.get("count", 1)

                if not job_id:
                    continue

                # SQLAlchemy core insert for ON DUPLICATE KEY UPDATE support
                stmt = insert(JobLinkClicksORM).values(
                    authuser_id=authuser_id,
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
            except Exception as inner_e:
                logger.warning(f"Skipping job click due to error (likely invalid job_id {job_id}): {str(inner_e)}")
                db.rollback() # Rollback the single failed statement
                continue
        
        db.commit()
        return processed_count
    except Exception as e:
        db.rollback()
        logger.error(f"Bulk upsert failed for user {authuser_id}: {str(e)}")
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
