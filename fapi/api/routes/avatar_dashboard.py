from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db.schemas import DashboardMetrics, FinancialMetrics, UpcomingBatch,CombinedEmailExtractionSummary
from fapi.utils.avatar_dashboard_utils import (
    get_batch_metrics,
    get_financial_metrics,
    get_placement_metrics,
    get_interview_metrics,
    get_top_batches_revenue,
    get_upcoming_batches,
    get_combined_email_extraction_summary,
)

router = APIRouter()


@router.get("/metrics/financial", response_model=FinancialMetrics)
def get_financial_metrics_endpoint(db: Session = Depends(get_db)):
    return get_financial_metrics(db)


@router.get("/metrics/all", response_model=DashboardMetrics)
def get_all_metrics_endpoint(db: Session = Depends(get_db)):
    return {
        "batch_metrics": get_batch_metrics(db),
        "financial_metrics": get_financial_metrics(db),
        "placement_metrics": get_placement_metrics(db),
        "interview_metrics": get_interview_metrics(db)
    }


@router.get("/top-batches-revenue")
def get_top_batches_revenue_endpoint(limit: int = 5, db: Session = Depends(get_db)):
    return get_top_batches_revenue(db, limit)


@router.get("/upcoming-batches", response_model=list[UpcomingBatch])
def get_upcoming_batches_endpoint(limit: int = 3, db: Session = Depends(get_db)):
    return get_upcoming_batches(db, limit)

# @router.get("/email-reads", response_model=List[CandidateEmailRead])
# def get_email_reads_endpoint(db: Session = Depends(get_db)):
#     return get_today_email_reads(db)


# @router.get("/summary", response_model=list[EmailExtractionSummary])
# def email_extraction_summary(db: Session = Depends(get_db)):
#     data = get_total_email_extractions(db)
#     return data


@router.get("/EmailExtraction", response_model=list[CombinedEmailExtractionSummary])
def combined_email_extraction_summary(db: Session = Depends(get_db)):
    data = get_combined_email_extraction_summary(db)
    return data