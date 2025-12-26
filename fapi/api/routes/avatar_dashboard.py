from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db.schemas import DashboardMetrics, FinancialMetrics, UpcomingBatch, BatchClassSummary, EmployeeTask
from fapi.db.models import EmployeeORM
from fapi.utils.avatar_dashboard_utils import (
    get_batch_metrics,
    get_financial_metrics,
    get_placement_metrics,
    get_interview_metrics,
    get_upcoming_batches,
    get_classes_per_latest_batches,
    get_employee_task_metrics,
    get_job_metrics,
    get_tasks_by_employee_id_for_dashboard,
    get_job_types_by_employee_id_for_dashboard,
)
from fapi.utils.permission_gate import enforce_access

router = APIRouter()


@router.get("/metrics/financial", response_model=FinancialMetrics)
def get_financial_metrics_endpoint(db: Session = Depends(get_db)):
    return get_financial_metrics(db)


@router.get("/metrics/all", response_model=DashboardMetrics)
def get_all_metrics_endpoint(db: Session = Depends(get_db), current_user = Depends(enforce_access)):
    metrics = {
        "batch_metrics": get_batch_metrics(db),
        "financial_metrics": get_financial_metrics(db),
        "placement_metrics": get_placement_metrics(db),
        "interview_metrics": get_interview_metrics(db),
        "employee_task_metrics": get_employee_task_metrics(db),
        "jobs_metrics": get_job_metrics(db),
        "my_tasks": None,
        "my_jobs": None,
        "employee_name": None
    }
    email = getattr(current_user, "uname", None)
    if email:
        employee = db.query(EmployeeORM).filter(EmployeeORM.email == email).first()
        if employee:
            metrics["my_tasks"] = get_tasks_by_employee_id_for_dashboard(db, employee.id)
            metrics["my_jobs"] = get_job_types_by_employee_id_for_dashboard(db, employee.id)
            metrics["employee_name"] = employee.name

    return metrics


@router.get("/top-batches-revenue")
def get_top_batches_revenue_endpoint(limit: int = 5, db: Session = Depends(get_db)):
    return get_top_batches_revenue(db, limit)


@router.get("/upcoming-batches", response_model=list[UpcomingBatch])
def get_upcoming_batches_endpoint(limit: int = 3, db: Session = Depends(get_db)):
    return get_upcoming_batches(db, limit)




@router.get("/batches/latest/classes", response_model=list[BatchClassSummary])
def get_latest_batches_classes(db: Session = Depends(get_db)):
    return get_classes_per_latest_batches(db)