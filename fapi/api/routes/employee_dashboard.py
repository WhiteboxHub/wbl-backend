from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.utils.permission_gate import enforce_access
from fapi.utils.employee_dashboard_utils import get_employee_dashboard_metrics
from fapi.db.models import EmployeeORM

router = APIRouter()

@router.get("/metrics/employee")
def get_employee_metrics_endpoint(db: Session = Depends(get_db), current_user = Depends(enforce_access)):
    email = getattr(current_user, "uname", None)
    if not email:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    employee = db.query(EmployeeORM).filter(EmployeeORM.email == email).first()
    if not employee:
        raise HTTPException(status_code=403, detail="Employee record not found")
        
    metrics = get_employee_dashboard_metrics(db, employee.id)
    if not metrics:
        raise HTTPException(status_code=404, detail="Metrics not found")
    
    # Transform prep candidates (tuple of CandidatePreparation, full_name) to include full_name
    prep_candidates_formatted = []
    for prep, full_name in metrics["assigned_prep_candidates"]:
        prep_dict = {
            "id": prep.id,
            "candidate_id": prep.candidate_id,
            "full_name": full_name,
            "status": prep.status,
            "start_date": str(prep.start_date) if prep.start_date else None,
        }
        prep_candidates_formatted.append(prep_dict)
    
    # Transform marketing candidates (tuple of CandidateMarketingORM, full_name) to include full_name
    marketing_candidates_formatted = []
    for marketing, full_name in metrics["assigned_marketing_candidates"]:
        marketing_dict = {
            "id": marketing.id,
            "candidate_id": marketing.candidate_id,
            "full_name": full_name,
            "status": marketing.status,
            "start_date": str(marketing.start_date) if marketing.start_date else None,
        }
        marketing_candidates_formatted.append(marketing_dict)
    
    # Update metrics with formatted data
    metrics["assigned_prep_candidates"] = prep_candidates_formatted
    metrics["assigned_marketing_candidates"] = marketing_candidates_formatted
        
    return metrics
