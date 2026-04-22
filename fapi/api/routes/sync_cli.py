import math
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.db.models import FieldAnswerSync, LocatorSync, SyncVersion
from fapi.db.schemas import FieldAnswerInput, LocatorInput, UploadPayload, DownloadPayload

router = APIRouter(
    prefix="/sync_cli",
    tags=["JobCLI Sync"],
)

# --- Routes ---

@router.post("/knowledge_sync")
def upload_knowledge(
    payload: UploadPayload,
    db: Session = Depends(get_db)
):
    # Fetch current version or create one
    latest_version = db.query(SyncVersion).order_by(SyncVersion.id.desc()).first()
    if not latest_version:
        latest_version = SyncVersion(version="v1.0.0", notes="Initial sync")
        db.add(latest_version)
        db.commit()
    
    current_version_str = latest_version.version
    data_changed = False

    # Process field answers
    for fa in payload.field_answers:
        # Ignore weak data from client
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
                existing.value = fa.value
                existing.version = current_version_str
                data_changed = True
        else:
            new_fa = FieldAnswerSync(
                ats_type=fa.ats_type,
                normalized_label=fa.normalized_label,
                value=fa.value,
                total_success=fa.total_success,
                total_failure=fa.total_failure,
                confidence=fa.confidence,
                version=current_version_str
            )
            db.add(new_fa)
            data_changed = True

    # Process locators
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
            existing.version = current_version_str
            data_changed = True
        else:
            new_loc = LocatorSync(
                ats_type=loc.ats_type,
                purpose=loc.purpose,
                selector=loc.selector,
                selector_type=loc.selector_type,
                domain_pattern=loc.domain_pattern,
                total_success=loc.total_success,
                total_failure=loc.total_failure,
                confidence=loc.confidence,
                version=current_version_str
            )
            db.add(new_loc)
            data_changed = True

    if data_changed:
        # User defined: Version should update after aggregation
        new_version_str = f"v1.0.{uuid.uuid4().hex[:6]}"
        new_version = SyncVersion(version=new_version_str, notes="Aggregated from client upload")
        db.add(new_version)
        
        # update the versions of all affected rows or let them use the old version if they weren't updated.
        # Actually, simpler to just insert the new version into SyncVersion.
    
    db.commit()
    return {"status": "success", "message": "Knowledge aggregated."}

@router.get("/knowledge_updates", response_model=DownloadPayload)
def download_updates(
    current_version: str,
    db: Session = Depends(get_db)
):
    latest_version = db.query(SyncVersion).order_by(SyncVersion.id.desc()).first()
    
    if not latest_version:
        return DownloadPayload(version=current_version, field_answers=[], locators=[])
        
    if latest_version.version == current_version:
        # Usually 304 Not Modified, but FastAPI handles this via Response or exception.
        # Let's return empty lists with the same version
        return DownloadPayload(version=current_version, field_answers=[], locators=[])
    
    # Aggregation Rules - Field Answers
    # Group by (ats_type, normalized_label), choose value with highest total_success.
    # We can do this in Python since data isn't massively huge, or with a subquery.
    # Since existing records are inherently grouped by (ats_type, normalized_label) due to Unique constraint,
    # we just fetch all of them!
    all_fas = db.query(FieldAnswerSync).all()
    
    out_fas = [
        FieldAnswerInput(
            ats_type=fa.ats_type,
            normalized_label=fa.normalized_label,
            value=fa.value,
            total_success=fa.total_success,
            total_failure=fa.total_failure,
            confidence=fa.confidence,
        ) for fa in all_fas
    ]

    # Aggregation Rules - Locators
    # Group by (ats_type, purpose), Rank selectors using score = confidence + log(total_success)
    all_locs = db.query(LocatorSync).all()
    
    # Group in python
    grouped_locs = {}
    for loc in all_locs:
        key = (loc.ats_type, loc.purpose)
        if key not in grouped_locs:
            grouped_locs[key] = []
        score = loc.confidence + math.log(loc.total_success if loc.total_success > 0 else 1)
        grouped_locs[key].append((score, loc))
    
    # Sort each group by score descending and take the best ones (e.g. top 3, or all sorted)
    out_locs = []
    for key, items in grouped_locs.items():
        items.sort(key=lambda x: x[0], reverse=True)
        # Let's take the top 3 best locators per purpose
        for score, loc in items[:3]:
            out_locs.append(
                LocatorInput(
                    ats_type=loc.ats_type,
                    purpose=loc.purpose,
                    selector=loc.selector,
                    selector_type=loc.selector_type,
                    domain_pattern=loc.domain_pattern,
                    total_success=loc.total_success,
                    total_failure=loc.total_failure,
                    confidence=loc.confidence,
                )
            )

    return DownloadPayload(
        version=latest_version.version,
        field_answers=out_fas,
        locators=out_locs
    )
