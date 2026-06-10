from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.db.models import ApplicationReportORM

router = APIRouter(prefix="/reports", tags=["ATS Reporting"])

class ApplicationReportSchema(BaseModel):
    candidate_name:  str
    company_name:    str
    ats_platform:    str
    total_fields:    int
    autofill_fields: int
    llm_fields:      int
    human_fields:    int
    automation_rate: float

@router.post("/applications/bulk")
async def save_application_reports_bulk(
    reports: List[ApplicationReportSchema],
    db: Session = Depends(get_db)
):
    db_reports = [ApplicationReportORM(**r.dict()) for r in reports]
    db.add_all(db_reports)
    db.commit()
    return {"status": "success", "inserted": len(db_reports)}
