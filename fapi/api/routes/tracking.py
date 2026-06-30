from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.db.models import ApplicationReportORM, ExtensionKeyORM, AuthUserORM
from fapi.utils import extension_analytics_utils
from fapi.utils.auth_dependencies import staff_or_admin_required, admin_required

router = APIRouter(prefix="/reports", tags=["ATS Reporting"])


# ---- Pydantic schemas -------------------------------------------------------

class ApplicationReportIn(BaseModel):
    """Payload accepted when saving a batch of ATS application reports."""

    candidate_name:  str
    company_name:    str
    ats_platform:    str
    total_fields:    int
    autofill_fields: int
    llm_fields:      int
    human_fields:    int
    automation_rate: float


class ApplicationReportOut(ApplicationReportIn):
    """Response schema — adds DB-generated fields."""

    id:           int
    user_id:      Optional[int] = None
    submitted_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # Pydantic v2 (replaces orm_mode)


class HumanPatchIn(BaseModel):
    url: str
    human_fields: int


# ---- Helper Dependency for Extension authentication -----------------------

def get_user_id_from_headers(
    x_candidate_email: Optional[str] = Header(None, alias="X-Candidate-Email"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> int:
    """Retrieve user_id from candidate email header, fallback to extension API key."""
    user_id = None
    if x_candidate_email:
        user = db.query(AuthUserORM).filter(AuthUserORM.uname == x_candidate_email.strip()).first()
        if user:
            user_id = user.id

    if not user_id:
        api_key = x_api_key
        if not api_key and authorization and authorization.startswith("Bearer "):
            api_key = authorization.split(" ")[1]

        if api_key:
            key_row = db.query(ExtensionKeyORM).filter(
                ExtensionKeyORM.api_key == api_key,
                ExtensionKeyORM.is_active == True
            ).first()
            if key_row:
                user_id = key_row.user_id

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or missing authentication credentials")
    return user_id


# ---- Endpoints --------------------------------------------------------------

@router.get("/applications/today", response_model=List[ApplicationReportOut])
async def get_application_reports_today(
    db: Session = Depends(get_db),
    current_user=Depends(staff_or_admin_required),
):
    """Return all ATS application reports submitted today (UTC date)."""
    if not current_user or current_user.role not in ["staff", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    now_utc = datetime.now(timezone.utc)
    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    return (
        db.query(ApplicationReportORM)
        .filter(
            ApplicationReportORM.submitted_at >= today_start,
            ApplicationReportORM.submitted_at < tomorrow_start,
        )
        .order_by(ApplicationReportORM.submitted_at.asc())
        .all()
    )


@router.post("/applications/bulk")
async def save_application_reports_bulk(
    reports: List[ApplicationReportIn],
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id_from_headers),
):
    """Persist a batch of ATS application field-ownership reports.
    
    If X-API-Key or Bearer token matches a registered user key, maps reports to user_id.
    """
    print(f"[ATS Telemetry] Ingesting bulk reports. User ID: {user_id}, Reports: {reports}")
    db_reports = []
    for r in reports:
        report_dict = r.dict()
        report_dict["user_id"] = user_id
        db_reports.append(ApplicationReportORM(**report_dict))
        
    db.add_all(db_reports)
    db.commit()
    return {"status": "success", "inserted": len(db_reports)}


@router.patch("/applications/patch-human")
async def patch_human_fields(
    payload: HumanPatchIn,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id_from_headers),
):
    """Update human_fields and recalculate automation_rate on the most recent
    ApplicationReport record matching this candidate within the last 30 minutes.
    """
    print(f"[ATS Telemetry] Patching human fields. User ID: {user_id}, Payload: {payload}")
    query = db.query(ApplicationReportORM)
    if user_id:
        query = query.filter(ApplicationReportORM.user_id == user_id)
    else:
        try:
            from urllib.parse import urlparse
            domain = urlparse(payload.url).hostname or ""
            parts = domain.replace("www.", "").split(".")
            ats_token = parts[0] if parts else ""
        except Exception:
            ats_token = ""
        if ats_token:
            query = query.filter(ApplicationReportORM.ats_platform.ilike(f"%{ats_token}%"))
    record = query.order_by(ApplicationReportORM.id.desc()).first()
    print(f"[ATS Telemetry] Found record to patch: {getattr(record, 'id', None)}")
    if not record:
        return {"status": "not_found"}
    record.human_fields = payload.human_fields
    filled_total = (record.autofill_fields or 0) + payload.human_fields
    record.automation_rate = round(
        (record.autofill_fields / filled_total * 100) if filled_total > 0 else 0.0, 2
    )
    db.commit()
    db.refresh(record)
    return {
        "status": "updated",
        "id": record.id,
        "human_fields": record.human_fields,
        "automation_rate": float(record.automation_rate)
    }


# ---- Admin Extension Analytics Endpoints -------------------------------------

@router.get("/analytics/summary")
def get_extension_summary(
    db: Session = Depends(get_db),
    current_user=Depends(staff_or_admin_required),
):
    """Global aggregate stats for Chrome extension usage."""
    if not current_user or current_user.role not in ["staff", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return extension_analytics_utils.get_extension_global_summary(db)


@router.get("/analytics/users")
def get_extension_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(staff_or_admin_required),
):
    """Paginated candidates with aggregated application telemetry."""
    if not current_user or current_user.role not in ["staff", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return extension_analytics_utils.get_paginated_extension_users(
        db, page=page, page_size=page_size, search_query=search
    )


@router.get("/analytics/users/{user_identity:path}/logs")
def get_extension_user_logs(
    user_identity: str,
    db: Session = Depends(get_db),
    current_user=Depends(staff_or_admin_required),
):
    """Retrieve detailed form submission history for a given candidate email or name."""
    if not current_user or current_user.role not in ["staff", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return extension_analytics_utils.get_user_extension_logs(db, user_identity)


@router.delete("/analytics/users/{user_identity:path}")
def delete_extension_user_data(
    user_identity: str,
    db: Session = Depends(get_db),
    current_user=Depends(admin_required),
):
    """Clear all application telemetry reports for a given candidate email or name."""
    if not current_user or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin permissions required to delete telemetry")
    deleted_count = extension_analytics_utils.delete_user_extension_reports(db, user_identity)
    return {"status": "success", "user_identity": user_identity, "deleted_count": deleted_count}


