from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.db.schemas import DashboardMetrics, BatchMetrics, FinancialMetrics, PlacementMetrics, InterviewMetrics, UpcomingBatch
from fapi.utils.dashboard_utils import (
    get_batch_metrics,
    get_financial_metrics,
    get_placement_metrics,
    get_interview_metrics,
    get_upcoming_batches,
    get_top_batches_revenue
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/metrics/batch", response_model=BatchMetrics)
def get_batch_metrics_endpoint(db: Session = Depends(get_db)):
    return get_batch_metrics(db)

@router.get("/metrics/financial", response_model=FinancialMetrics)
def get_financial_metrics_endpoint(db: Session = Depends(get_db)):
    return get_financial_metrics(db)

@router.get("/metrics/placement", response_model=PlacementMetrics)
def get_placement_metrics_endpoint(db: Session = Depends(get_db)):
    return get_placement_metrics(db)

@router.get("/metrics/interview", response_model=InterviewMetrics)
def get_interview_metrics_endpoint(db: Session = Depends(get_db)):
    return get_interview_metrics(db)

@router.get("/metrics/all", response_model=DashboardMetrics)
def get_all_metrics_endpoint(db: Session = Depends(get_db)):
    return {
        "batch_metrics": get_batch_metrics(db),
        "financial_metrics": get_financial_metrics(db),
        "placement_metrics": get_placement_metrics(db),
        "interview_metrics": get_interview_metrics(db)
    }

@router.get("/upcoming-batches", response_model=list[UpcomingBatch])
def get_upcoming_batches_endpoint(limit: int = 3, db: Session = Depends(get_db)):
    return get_upcoming_batches(db, limit)

@router.get("/top-batches-revenue")
def get_top_batches_revenue_endpoint(limit: int = 5, db: Session = Depends(get_db)):
    return get_top_batches_revenue(db, limit)