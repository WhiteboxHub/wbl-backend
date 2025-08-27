from fastapi import FastAPI, HTTPException, status,APIRouter, Depends
from sqlalchemy.orm import Session
from fapi.db.models import EmployeeORM
from fapi.db.database import SessionLocal,get_db
from fapi.db.schemas import Employee, EmployeeCreate, EmployeeUpdate
from fapi.utils.employee_utils import get_all_employees,create_employee_db,update_employee_db,delete_employee_db,clean_invalid_values
from fapi.utils.avatar_dashboard_utils import get_employee_birthdays

app = FastAPI()
router = APIRouter()

@router.get("/employees", response_model=list[Employee])
def get_employees():
    try:
        rows = get_all_employees()
        return [Employee(**row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/employee-birthdays")
def employee_birthdays(db: Session = Depends(get_db)):
    birthdays = utils.get_employee_birthdays(db)
    return birthdays

@router.post("/employees", response_model=Employee, status_code=status.HTTP_201_CREATED)
def create_employee(employee_data: EmployeeCreate):
    try:
        new_employee = create_employee_db(employee_data.dict())
        return Employee(**new_employee)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create employee: {str(e)}")

@router.put("/employees/{employee_id}", response_model=Employee)
async def update_employee(employee_id: int, update_data: EmployeeUpdate):
    fields = update_data.dict(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No data to update")
    try:
        fields.pop("id", None)
        update_employee_db(employee_id, fields)
        return Employee(**fields, id=employee_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

@router.delete("/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(employee_id: int):
    try:
        delete_employee_db(employee_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")
