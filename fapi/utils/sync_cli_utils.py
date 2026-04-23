import math
import uuid
import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException

from fapi.db.models import FieldAnswerSync, LocatorSync, SyncVersion
from fapi.db.schemas import FieldAnswerInput, LocatorInput, UploadPayload, DownloadPayload

logger = logging.getLogger(__name__)


# ---------- Helpers ----------

def _get_or_create_version(db: Session) -> str:
    """Return the latest version string, creating v1.0.0 if none exists."""
    latest = db.query(SyncVersion).order_by(SyncVersion.id.desc()).first()
    if not latest:
        latest = SyncVersion(version="v1.0.0", notes="Initial sync")
        db.add(latest)
        db.commit()
    return latest.version


def _bump_version(db: Session) -> None:
    """Insert a new version row after a successful aggregation."""
    new_version = SyncVersion(
        version=f"v1.0.{uuid.uuid4().hex[:6]}",
        notes="Aggregated from client upload"
    )
    db.add(new_version)


# ---------- Upload / Aggregate ----------

def aggregate_knowledge(db: Session, payload: UploadPayload) -> dict:
    """
    Aggregate client-submitted field answers and locators into the central DB.
    - Ignores weak data (total_success < 3)
    - Accumulates success/failure counts
    - Updates the stored value only when the incoming data has higher success
    - Bumps the sync version after any change
    """
    current_version = _get_or_create_version(db)
    data_changed = False

    # --- Field Answers ---
    for fa in payload.field_answers:
        if fa.total_success < 3:
            continue

        existing = db.query(FieldAnswerSync).filter_by(
            ats_type=fa.ats_type,
            normalized_label=fa.normalized_label,
            value=fa.value
        ).first()

        if existing:
            old_success = existing.total_success
            existing.total_success += fa.total_success
            existing.total_failure += fa.total_failure
            total = existing.total_success + existing.total_failure
            existing.confidence = existing.total_success / total if total > 0 else 0.0

            if fa.total_success > old_success:
                existing.version = current_version
                data_changed = True
        else:
            db.add(FieldAnswerSync(
                ats_type=fa.ats_type,
                normalized_label=fa.normalized_label,
                value=fa.value,
                total_success=fa.total_success,
                total_failure=fa.total_failure,
                confidence=fa.confidence,
                version=current_version
            ))
            data_changed = True

    # --- Locators ---
    for loc in payload.locators:
        if loc.total_success < 3:
            continue

        existing = db.query(LocatorSync).filter_by(
            ats_type=loc.ats_type,
            purpose=loc.purpose,
            selector=loc.selector
        ).first()

        if existing:
            existing.total_success += loc.total_success
            existing.total_failure += loc.total_failure
            total = existing.total_success + existing.total_failure
            existing.confidence = existing.total_success / total if total > 0 else 0.0
            existing.version = current_version
            data_changed = True
        else:
            db.add(LocatorSync(
                ats_type=loc.ats_type,
                purpose=loc.purpose,
                selector=loc.selector,
                selector_type=loc.selector_type,
                domain_pattern=loc.domain_pattern,
                total_success=loc.total_success,
                total_failure=loc.total_failure,
                confidence=loc.confidence,
                version=current_version
            ))
            data_changed = True

    try:
        if data_changed:
            _bump_version(db)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Knowledge aggregation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to aggregate knowledge")

    return {"status": "success", "message": "Knowledge aggregated."}


# ---------- Download / Distribute ----------

def get_knowledge_updates(db: Session, current_version: str) -> DownloadPayload:
    """
    Return aggregated field answers and top-ranked locators.
    Returns empty lists if the client is already on the latest version.
    """
    latest = db.query(SyncVersion).order_by(SyncVersion.id.desc()).first()

    if not latest or latest.version == current_version:
        return DownloadPayload(
            version=current_version,
            field_answers=[],
            locators=[]
        )

    # Field answers — one row per (ats_type, normalized_label, value) due to unique key
    all_fas = db.query(FieldAnswerSync).all()
    out_fas = [
        FieldAnswerInput(
            ats_type=fa.ats_type,
            normalized_label=fa.normalized_label,
            value=fa.value,
            total_success=fa.total_success,
            total_failure=fa.total_failure,
            confidence=float(fa.confidence),
        )
        for fa in all_fas
    ]

    # Locators — group by (ats_type, purpose), rank by score, return top 3
    all_locs = db.query(LocatorSync).all()
    grouped: dict = {}
    for loc in all_locs:
        key = (loc.ats_type, loc.purpose)
        score = loc.confidence + math.log(max(loc.total_success, 1))
        grouped.setdefault(key, []).append((score, loc))

    out_locs = []
    for items in grouped.values():
        items.sort(key=lambda x: x[0], reverse=True)
        for _, loc in items[:3]:
            out_locs.append(
                LocatorInput(
                    ats_type=loc.ats_type,
                    purpose=loc.purpose,
                    selector=loc.selector,
                    selector_type=loc.selector_type,
                    domain_pattern=loc.domain_pattern,
                    total_success=loc.total_success,
                    total_failure=loc.total_failure,
                    confidence=float(loc.confidence),
                )
            )

    return DownloadPayload(
        version=latest.version,
        field_answers=out_fas,
        locators=out_locs
    )
