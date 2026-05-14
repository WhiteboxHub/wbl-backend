from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Query, Session

from fapi.db.models import JobLinkClicksORM, JobListingORM
from fapi.db.schemas import JobListingCreate, JobListingUpdate, PositionStatusEnum
from fapi.utils.table_fingerprint import generate_version_for_model
from fastapi import Response
from fapi.core.cache import cache_result, invalidate_cache


def _apply_positions_search(query: Query, search: Optional[str]) -> Query:
    """Restrict a JobListing query by optional free-text search (title / company / location)."""
    if not search or not str(search).strip():
        return query
    term = f"%{str(search).strip()}%"
    return query.filter(
        or_(
            JobListingORM.title.ilike(term),
            JobListingORM.company_name.ilike(term),
            JobListingORM.location.ilike(term),
        )
    )


@cache_result(ttl=300, prefix="positions")
def get_positions(
    db: Session,
    skip: int = 0,
    limit: Optional[int] = None,
    search: Optional[str] = None,
) -> List[JobListingORM]:
    DEFAULT_LIMIT = 5000
    MAX_LIMIT = 999999

    query = db.query(JobListingORM)
    query = _apply_positions_search(query, search)
    query = query.order_by(JobListingORM.id.desc()).offset(skip)
    if limit is None:
        query = query.limit(DEFAULT_LIMIT)
    else:
        query = query.limit(min(limit, MAX_LIMIT))

    return query.all()

@cache_result(ttl=300, prefix="positions")
def get_position(db: Session, position_id: int) -> Optional[JobListingORM]:
    return db.query(JobListingORM).filter(JobListingORM.id == position_id).first()

def create_position(db: Session, position: JobListingCreate) -> JobListingORM:
    invalidate_cache("positions")
    db_position = JobListingORM(**position.model_dump())
    db.add(db_position)
    db.commit()
    db.refresh(db_position)
    return db_position

def update_position(db: Session, position_id: int, position: JobListingUpdate) -> Optional[JobListingORM]:
    invalidate_cache("positions")
    db_position = db.query(JobListingORM).filter(JobListingORM.id == position_id).first()
    if not db_position:
        return None
    
    update_data = position.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_position, key, value)
    
    db.commit()
    db.refresh(db_position)
    return db_position

def delete_position(db: Session, position_id: int) -> bool:
    invalidate_cache("positions")
    db_position = db.query(JobListingORM).filter(JobListingORM.id == position_id).first()
    if not db_position:
        return False
    
    db.delete(db_position)
    db.commit()
    return True

@cache_result(ttl=300, prefix="positions")
def search_positions(db: Session, term: str) -> List[JobListingORM]:
    return db.query(JobListingORM).filter(
        or_(
            JobListingORM.title.ilike(f"%{term}%"),
            JobListingORM.company_name.ilike(f"%{term}%")
        )
    ).limit(100).all()

@cache_result(ttl=300, prefix="positions")
def count_positions(db: Session, search: Optional[str] = None) -> int:
    """Get total count of job listings for pagination (optional search filter)."""
    q = db.query(JobListingORM)
    q = _apply_positions_search(q, search)
    return q.count()

async def insert_positions_bulk(positions: List[JobListingCreate], db: Session) -> dict:
    invalidate_cache("positions")
    """Bulk insert job listings with duplicate handling"""
    inserted = 0
    failed = 0
    duplicates = 0
    failed_contacts = []
    
    try:
        for pos_data in positions:
            try:
                # Check for duplicates by source and source_uid
                existing = None
                if pos_data.source_uid:
                    existing = db.query(JobListingORM).filter(
                        JobListingORM.source == pos_data.source,
                        JobListingORM.source_uid == pos_data.source_uid
                    ).first()
                
                if existing:
                    duplicates += 1
                    continue
                
                # Insert new position
                db_pos = JobListingORM(**pos_data.model_dump())
                db.add(db_pos)
                inserted += 1
                
                # Flush every 100 records to keep memory low
                if inserted % 100 == 0:
                    db.flush()
                    
            except Exception as e:
                failed += 1
                failed_contacts.append({
                    "source_uid": pos_data.source_uid,
                    "reason": str(e)
                })
        
        db.commit()
        
        return {
            "inserted": inserted,
            "skipped": duplicates,
            "total": len(positions),
            "failed_contacts": failed_contacts
        }
        
    except Exception as e:
        db.rollback()
        raise e

def get_positions_version(db: Session) -> Response:
    return generate_version_for_model(db, JobListingORM)


def query_cli_window_listings(
    db: Session,
    days: int = 7,
    page_size: int = 5000,
    status: Optional[str] = "open",
    authuser_id: Optional[int] = None,
    offset: int = 0,
) -> Tuple[List[dict], int]:
    """Listings for JobCLI — not cached, sorted oldest-first.

    When ``days`` is 0, no ``created_at`` lower bound is applied (same universe
    as dashboard listings with a non-empty ``job_url``). When ``days`` > 0,
    only rows created within the last ``days`` UTC days are included.

    ``already_applied`` is True when this user has a ``job_link_clicks`` row
    for the listing (engagement proxy). JobCLI may still reconcile with local
    submission state.
    """
    q = db.query(JobListingORM).filter(
        JobListingORM.job_url.isnot(None),
        func.length(func.trim(JobListingORM.job_url)) > 0,
    )
    if days and days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_cmp = cutoff.replace(tzinfo=None)
        q = q.filter(JobListingORM.created_at >= cutoff_cmp)

    st_raw = (status or "").strip().lower()
    if st_raw not in ("", "all", "*", "__any__", "any"):
        try:
            st_enum = PositionStatusEnum(st_raw)
            q = q.filter(JobListingORM.status == st_enum)
        except ValueError:
            q = q.filter(JobListingORM.status == (status or "").strip())

    total_in_window = q.count()

    lim = min(max(1, page_size), 10000)
    off = max(0, int(offset))
    rows = (
        q.order_by(JobListingORM.created_at.asc(), JobListingORM.id.asc())
        .offset(off)
        .limit(lim)
        .all()
    )

    clicked_ids: set[int] = set()
    if authuser_id and rows:
        jids = [int(r.id) for r in rows]
        for chunk_start in range(0, len(jids), 500):
            chunk = jids[chunk_start : chunk_start + 500]
            res = (
                db.query(JobLinkClicksORM.job_listing_id)
                .filter(
                    JobLinkClicksORM.authuser_id == authuser_id,
                    JobLinkClicksORM.job_listing_id.in_(chunk),
                )
                .all()
            )
            clicked_ids.update(int(r[0]) for r in res)

    data: List[dict] = []
    for r in rows:
        raw_status = getattr(r.status, "value", r.status)
        raw_source = getattr(r.source, "value", r.source)
        jid = int(r.id)
        data.append(
            {
                "id": jid,
                "job_url": (r.job_url or "").strip(),
                "title": r.title or "",
                "company_name": r.company_name or "",
                "created_at": r.created_at,
                "status": str(raw_status),
                "source": str(raw_source),
                "already_applied": jid in clicked_ids,
            }
        )

    return data, total_in_window
