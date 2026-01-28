from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.utils.permission_gate import enforce_access
from fapi.db.schemas import EmployeeDashboardMetrics
from fapi.utils.employee_dashboard_utils import get_employee_dashboard_metrics
from fapi.db.models import EmployeeORM

router = APIRouter()

@router.get("/metrics/employee", response_model=EmployeeDashboardMetrics)
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
        
    return metrics
