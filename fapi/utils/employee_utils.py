
# from fapi.db.database import SessionLocal
# from fapi.db.models import EmployeeORM

# # def get_all_employees() -> list[dict]:
# #     with SessionLocal() as session:
# #         employees = session.query(EmployeeORM).order_by(EmployeeORM.id.desc()).all()
# #         return [emp.__dict__ for emp in employees]
# # def get_all_employees() -> list[dict]:
# #     with SessionLocal() as session:
# #         employees = session.query(EmployeeORM).order_by(EmployeeORM.id.desc()).all()
# #         return [clean_invalid_values(emp.__dict__.copy()) for emp in employees]

# def update_employee_db(employee_id: int, fields: dict) -> None:
#     with SessionLocal() as session:
#         employee = session.query(EmployeeORM).filter(EmployeeORM.id == employee_id).first()
#         if not employee:
#             raise ValueError("Employee not found")
#         for key, value in fields.items():
#             if hasattr(employee, key):
#                 setattr(employee, key, value)
#         session.commit()

# def create_employee_db(data: dict) -> dict:
#     with SessionLocal() as session:
#         new_employee = EmployeeORM(**data)
#         session.add(new_employee)
#         session.commit()
#         session.refresh(new_employee)
#         return new_employee.__dict__

# # def update_employee_db(employee_id: int, fields: dict) -> None:
# #     with SessionLocal() as session:
# #         employee = session.query(EmployeeORM).filter(EmployeeORM.id == employee_id).first()
# #         if not employee:
# #             raise ValueError("Employee not found")
# #         for key, value in fields.items():
# #             if hasattr(employee, key):
# #                 setattr(employee, key, value)
# #         session.commit()


# def update_employee_db(employee_id: int, fields: dict) -> EmployeeORM:
#     with SessionLocal() as session:
#         employee = session.query(EmployeeORM).filter(EmployeeORM.id == employee_id).first()
#         if not employee:
#             raise ValueError("Employee not found")
#         for key, value in fields.items():
#             if hasattr(employee, key):
#                 setattr(employee, key, value)
#         session.commit()
#         session.refresh(employee)
#         return employee

# def delete_employee_db(employee_id: int) -> None:
#     with SessionLocal() as session:
#         employee = session.query(EmployeeORM).filter(EmployeeORM.id == employee_id).first()
#         if not employee:
#             raise ValueError("Employee not found")
#         session.delete(employee)
#         session.commit()

# def clean_invalid_values(record: dict) -> dict:
 
#     for field in ["dob", "startdate", "enddate"]:
#         val = record.get(field)
#         if val and str(val).startswith("0000-00-00"):
#             record[field] = None
    
 
#     if record.get("phone") in ["000-000-0000", "0", ""]:
#         record["phone"] = None

#     return record



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

def update_employee_db(employee_id: int, fields: dict) -> None:
    with SessionLocal() as session:
        employee = session.query(EmployeeORM).filter(EmployeeORM.id == employee_id).first()
        if not employee:
            raise ValueError("Employee not found")
        for key, value in fields.items():
            if hasattr(employee, key):
                setattr(employee, key, value)
        session.commit()

def delete_employee_db(employee_id: int) -> None:
    with SessionLocal() as session:
        employee = session.query(EmployeeORM).filter(EmployeeORM.id == employee_id).first()
        if not employee:
            raise ValueError("Employee not found")
        session.delete(employee)
        session.commit()
