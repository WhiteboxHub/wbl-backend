import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, cast, String
from sqlalchemy.orm import Session
from fapi.db.models import CampaignEmailORM
from fapi.db.schemas import CampaignEmailCreate, CampaignEmailUpdate
from fapi.utils.table_fingerprint import generate_version_for_model
from fastapi import Response, HTTPException
from fapi.core.cache import cache_result, invalidate_cache

logger = logging.getLogger(__name__)

CACHE_PREFIX = "campaign_emails"


@cache_result(ttl=300, prefix=CACHE_PREFIX)
def get_all(
    db: Session,
    status: Optional[str] = None,
    candidate_id: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None
) -> List[CampaignEmailORM]:
    query = db.query(CampaignEmailORM)
    
    if status:
        query = query.filter(CampaignEmailORM.status == status)
    if candidate_id:
        query = query.filter(CampaignEmailORM.candidate_id == candidate_id)
        
    query = query.order_by(CampaignEmailORM.created_at.desc())
    
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
        
    return query.all()


@cache_result(ttl=300, prefix=CACHE_PREFIX)
def get_paginated(
    db: Session, page: int, limit: int, search: str, search_by: str, sort: str
):
    query = db.query(CampaignEmailORM)

    if search:
        if search_by == "vendor_email":
            query = query.filter(CampaignEmailORM.vendor_email.ilike(f"%{search}%"))
        elif search_by == "status":
            query = query.filter(CampaignEmailORM.status.ilike(f"%{search}%"))
        elif search_by == "workflow_id" and search.isdigit():
            query = query.filter(CampaignEmailORM.workflow_id == int(search))
        elif search_by == "candidate_id" and search.isdigit():
            query = query.filter(CampaignEmailORM.candidate_id == int(search))
        else:  # search_by == "all"
            query = query.filter(
                or_(
                    CampaignEmailORM.vendor_email.ilike(f"%{search}%"),
                    CampaignEmailORM.status.ilike(f"%{search}%"),
                    cast(CampaignEmailORM.workflow_id, String).ilike(f"%{search}%"),
                    cast(CampaignEmailORM.candidate_id, String).ilike(f"%{search}%"),
                )
            )

    if sort:
        sort_fields = sort.split(",")
        for field in sort_fields:
            if ":" in field:
                col, direction = field.split(":")
                if hasattr(CampaignEmailORM, col):
                    column = getattr(CampaignEmailORM, col)
                    query = query.order_by(column.desc() if direction == "desc" else column.asc())

    total = query.count()
    emails = query.offset((page - 1) * limit).limit(limit).all()
    return {"data": emails, "total": total, "page": page, "limit": limit}


@cache_result(ttl=300, prefix=CACHE_PREFIX)
def get_by_id(db: Session, record_id: int) -> CampaignEmailORM:
    row = db.query(CampaignEmailORM).filter(
        CampaignEmailORM.id == record_id
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Campaign email not found")
    return row


@cache_result(ttl=300, prefix=CACHE_PREFIX)
def get_by_workflow(
    db: Session, workflow_id: int
) -> List[CampaignEmailORM]:
    return db.query(CampaignEmailORM).filter(
        CampaignEmailORM.workflow_id == workflow_id
    ).order_by(CampaignEmailORM.created_at.desc()).all()


def create(db: Session, data: CampaignEmailCreate) -> CampaignEmailORM:
    invalidate_cache(CACHE_PREFIX)
    row = CampaignEmailORM(**data.model_dump(exclude_none=True))
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
        return row
    except Exception as e:
        db.rollback()
        logger.error("Failed to create campaign email: %s", e)
        raise HTTPException(
            status_code=500, detail="Failed to create campaign email"
        )


def create_bulk(db: Session, data_list: List[CampaignEmailCreate]) -> int:
    invalidate_cache(CACHE_PREFIX)
    objects = [
        CampaignEmailORM(**item.model_dump(exclude_none=True))
        for item in data_list
    ]
    db.bulk_save_objects(objects)
    try:
        db.commit()
        return len(objects)
    except Exception as e:
        db.rollback()
        logger.error("Failed to bulk create campaign emails: %s", e)
        raise HTTPException(
            status_code=500, detail="Failed to bulk insert campaign emails"
        )


def update(
    db: Session, record_id: int, data: CampaignEmailUpdate
) -> CampaignEmailORM:
    invalidate_cache(CACHE_PREFIX)
    row = get_by_id(db, record_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    try:
        db.commit()
        db.refresh(row)
        return row
    except Exception as e:
        db.rollback()
        logger.error("Failed to update campaign email id=%s: %s", record_id, e)
        raise HTTPException(
            status_code=500, detail="Failed to update campaign email"
        )


def delete(db: Session, record_id: int):
    invalidate_cache(CACHE_PREFIX)
    row = get_by_id(db, record_id)
    db.delete(row)
    db.commit()
    return {"message": "Campaign email deleted"}


def get_version(db: Session) -> Response:
    return generate_version_for_model(db, CampaignEmailORM)


# ── Outreach Orchestrator Functions ──────────────────────────────────────────

from sqlalchemy import text  # noqa: E402


def generate_snapshot(db: Session, candidate_id: int, workflow_id: int, scheduler_id: Optional[int] = None):
    """
    Snapshot all eligible recruiters for a candidate into campaign_emails
    as 'pending'. Uses INSERT IGNORE so re-running is always safe.
    Only picks contacts not already in campaign_emails for this candidate
    and the specific scheduler.
    """
    sql = text("""
        INSERT IGNORE INTO campaign_emails
            (workflow_id, candidate_id, vendor_email, scheduler_id,
             status, retry_count, created_at, updated_at)
        SELECT
            :workflow_id,
            :candidate_id,
            oe.email,
            :scheduler_id,
            'pending',
            0,
            NOW(),
            NOW()
        FROM outreach_emails oe
        LEFT JOIN campaign_emails ce
            ON ce.candidate_id = :candidate_id
            AND ce.vendor_email = oe.email
            AND (ce.scheduler_id = :scheduler_id OR (ce.scheduler_id IS NULL AND :scheduler_id IS NULL))
        WHERE oe.email IS NOT NULL
          AND oe.status = 'ACTIVE'
          AND oe.validation_status = 'VALID'
          AND ce.id IS NULL
    """)
    db.execute(sql, {
        "workflow_id": workflow_id,
        "candidate_id": candidate_id,
        "scheduler_id": scheduler_id,
    })
    db.commit()
    return {"message": "Snapshot generated"}


def dispatch_pending(db: Session, candidate_id: int, limit: int, scheduler_id: Optional[int] = None):
    """
    Atomically claim up to `limit` pending emails for delivery.
    Uses FOR UPDATE SKIP LOCKED so concurrent workers never grab same rows.
    Returns list of {id, vendor_email} dicts ready to be sent to Celery.
    """
    scheduler_cond = "AND scheduler_id = :scheduler_id" if scheduler_id is not None else "AND scheduler_id IS NULL"
    
    lock_sql = text(f"""
        SELECT id, vendor_email
        FROM campaign_emails
        WHERE candidate_id = :candidate_id
          AND status = 'pending'
          {scheduler_cond}
        LIMIT :limit
        FOR UPDATE SKIP LOCKED
    """)
    records = db.execute(
        lock_sql, {"candidate_id": candidate_id, "limit": limit, "scheduler_id": scheduler_id}
    ).fetchall()

    if not records:
        return []

    ids = [r[0] for r in records]

    # Build named placeholders for IN clause — SQLAlchemy text() does not
    # support binding a tuple to :param, so we expand manually.
    placeholders = ", ".join(f":id_{i}" for i in range(len(ids)))
    update_sql = text(
        f"UPDATE campaign_emails SET status = 'processing' "
        f"WHERE id IN ({placeholders})"
    )
    params = {f"id_{i}": id_val for i, id_val in enumerate(ids)}
    db.execute(update_sql, params)
    db.commit()

    return [{"id": r[0], "vendor_email": r[1]} for r in records]


def get_pending_count(db: Session, candidate_id: int, scheduler_id: Optional[int] = None) -> int:
    """Return number of still-pending emails for a candidate."""
    scheduler_cond = "AND scheduler_id = :scheduler_id" if scheduler_id is not None else "AND scheduler_id IS NULL"
    
    result = db.execute(
        text(
            f"SELECT COUNT(*) FROM campaign_emails "
            f"WHERE candidate_id = :candidate_id AND status = 'pending' {scheduler_cond}"
        ),
        {"candidate_id": candidate_id, "scheduler_id": scheduler_id},
    ).scalar()
    return int(result or 0)
