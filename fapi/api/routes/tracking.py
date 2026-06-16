from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.db.models import ApplicationReportORM

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
    submitted_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # Pydantic v2 (replaces orm_mode)


# ---- Endpoints --------------------------------------------------------------

@router.get("/applications/today", response_model=List[ApplicationReportOut])
async def get_application_reports_today(
    db: Session = Depends(get_db),
):
    """Return all ATS application reports submitted today (UTC date).

    Uses a UTC-aware window (midnight UTC → next midnight UTC) so records
    stored by MySQL's NOW() (UTC) are never missed due to timezone skew.
    """
    now_utc = datetime.now(timezone.utc)
    # Start of today in UTC (midnight)
    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    # Start of tomorrow in UTC (exclusive upper bound)
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
):
    """Persist a batch of ATS application field-ownership reports."""
    db_reports = [ApplicationReportORM(**r.dict()) for r in reports]
    db.add_all(db_reports)
    db.commit()
    return {"status": "success", "inserted": len(db_reports)}
