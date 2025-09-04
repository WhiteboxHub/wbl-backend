
from fapi.db.database import SessionLocal
from fapi.db.models import EmployeeORM

def clean_invalid_values(row: dict) -> dict:
    return {k: (None if v is None else v) for k, v in row.items() if k != "_sa_instance_state"}

def get_all_employees() -> list[dict]:
    with SessionLocal() as session:
        employees = session.query(EmployeeORM).order_by(EmployeeORM.id.desc()).all()
        return [clean_invalid_values(emp.__dict__.copy()) for emp in employees]

def create_employee_db(employee_data: dict) -> None:
    with SessionLocal() as session:
        employee = EmployeeORM(**employee_data)
        session.add(employee)
        session.commit()

def delete_employee_db(employee_id: int) -> None:
    with SessionLocal() as session:
        employee = session.query(EmployeeORM).filter(EmployeeORM.id == employee_id).first()
        if not employee:
            raise ValueError("Employee not found")
        session.delete(employee)
        session.commit()


def update_employee_db(employee_id: int, fields: dict) -> EmployeeORM:
    with SessionLocal() as session:
        employee = session.query(EmployeeORM).filter(EmployeeORM.id == employee_id).first()
        if not employee:
            raise ValueError("Employee not found")

        print(f"Before update: {employee.name}, {employee.email}")  # Debug log
        for key, value in fields.items():
            if hasattr(employee, key):
                print(f"Setting {key} to {value}")  # Debug log
                setattr(employee, key, value)

        session.commit()
        session.refresh(employee)
        print(f"After update: {employee.name}, {employee.email}")  # Debug log
        return employee
