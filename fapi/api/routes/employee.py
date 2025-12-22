from fastapi import FastAPI, HTTPException, status, APIRouter, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from fapi.db.models import EmployeeORM
from fapi.db.database import SessionLocal, get_db
from fapi.db import models, schemas
from typing import List, Dict
from fapi.db.schemas import Employee, EmployeeCreate, EmployeeUpdate,EmployeeDetailSchema
from fapi.utils.employee_search_utils import (
    search_employees,
    get_employee_details,
    get_employee_candidates,
     get_employee_sessions_and_recordings,
     get_employee_placements,
)
from typing import List
from fapi.utils.employee_utils import (
    get_all_employees,
    create_employee_db,
    update_employee_db,
    delete_employee_db,
    clean_invalid_values
)
from fapi.utils.avatar_dashboard_utils import get_employee_birthdays

app = FastAPI()
router = APIRouter()

security = HTTPBearer()

@router.get("/employees", response_model=list[Employee])
def get_employees(
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    try:
        rows = get_all_employees()
        return [Employee(**row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/employee-birthdays")
def employee_birthdays(db: Session = Depends(get_db)):
    birthdays = get_employee_birthdays(db)
    return birthdays


@router.post("/employees", response_model=Employee)
def create_employee(employee_data: EmployeeCreate, db: Session = Depends(get_db)):
    try:
 
        if not employee_data.name or not employee_data.email:
            raise HTTPException(status_code=400, detail="Name and email are required")

        db_employee = EmployeeORM(**employee_data.model_dump())
        db.add(db_employee)
        db.commit()
        db.refresh(db_employee)
        return db_employee
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create employee: {str(e)}")


@router.put("/employees/{employee_id}", response_model=Employee)
def update_employee(
    employee_id: int,
    employee_data: EmployeeUpdate,  
    db: Session = Depends(get_db)
):
    try:
        updated_employee = update_employee_db(employee_id, employee_data.model_dump(exclude_unset=True))
        return updated_employee
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update employee: {str(e)}")
    

@router.delete("/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(employee_id: int):
    try:
        delete_employee_db(employee_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


# ---------------------------------employee search--------------------------------------


@router.get("/employees/search", response_model=List[EmployeeDetailSchema])
def employee_search(query: str = "", db: Session = Depends(get_db)):
    employees = get_employee_details(db)
    if query:
        query_lower = query.lower()
        employees = [e for e in employees if e["name"] and query_lower in e["name"].lower()]
    return employees


@router.get("/employees/{employee_id}/candidates", response_model=Dict)
def employee_candidates(employee_id: int, db: Session = Depends(get_db)):
    emp = db.query(models.EmployeeORM).filter(models.EmployeeORM.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    candidates = get_employee_candidates(db, employee_id)
    return candidates




@router.get("/employees/{employee_id}/session-class-data")
def get_employee_session_class_data(employee_id: int, db: Session = Depends(get_db)):
    
    data = get_employee_sessions_and_recordings(db, employee_id)
    if "error" in data:
        return {"error": data["error"], "class_count": 0, "session_count": 0, "timeline": []}

    timeline: List[Dict] = []

    for r in data["recordings"]:
        timeline.append({
            "type": "class",
            "title": r.description or "Untitled",
            "date": str(r.classdate) if r.classdate else None,
            "link": r.link
        })
    for s in data["sessions"]:
        timeline.append({
            "type": "session",
            "title": s.title or "Untitled",
            "date": str(s.sessiondate) if s.sessiondate else None,
            "link": s.link
        })

    timeline.sort(key=lambda x: x["date"] or "", reverse=True)

    return {
        "class_count": len(data["recordings"]),
        "session_count": len(data["sessions"]),
        "timeline": timeline
    }
    
@router.get("/employees/{employee_id}/placements")
def get_employee_placements_endpoint(employee_id: int, db: Session = Depends(get_db)):
    placements = get_employee_placements(db, employee_id)
    return placements