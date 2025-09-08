from fastapi import FastAPI, HTTPException, status,APIRouter, Depends
from sqlalchemy.orm import Session
from fapi.db.models import EmployeeORM
from fapi.db.database import SessionLocal,get_db
from fapi.db.schemas import Employee, EmployeeCreate, EmployeeUpdate
from fapi.utils.employee_utils import get_all_employees,create_employee_db,update_employee_db,delete_employee_db,clean_invalid_values
from fapi.utils.avatar_dashboard_utils import get_employee_birthdays

app = FastAPI()
router = APIRouter()

# @router.get("/employees", response_model=list[Employee])
# def get_employees():
#     try:
#         rows = get_all_employees()
#         return [Employee(**row) for row in rows]
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))



@router.get("/employees", response_model=list[Employee])
def get_employees():
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
