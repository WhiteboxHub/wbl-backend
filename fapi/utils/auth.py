# from sqlalchemy.orm import Session
# from fapi.utils.db_queries import get_user_by_username, fetch_candidate_id_and_status_by_email
# from fapi.utils.auth_utils import verify_md5_hash
# from fapi.db.models import EmployeeORM


# def determine_user_role(user):
#     if user.uname.lower() == "admin":
#         return "admin"
#     return "candidate"


# async def authenticate_user(uname: str, passwd: str, db: Session):
#     user = get_user_by_username(db, uname)
#     if not user or not verify_md5_hash(passwd, user.passwd):
#         return None

#     if uname.lower() == "admin":
#         return {**user.__dict__, "candidateid": None}

#     if user.status.lower() != "active":
#         return "inactive_authuser"

#     # First try candidate lookup (existing behavior)
#     candidate_info = fetch_candidate_id_and_status_by_email(db, uname)
#     if candidate_info:
#         if candidate_info.status.lower() not in ("active", "closed"):
#             return "inactive_candidate"
#         return {**user.__dict__, "candidateid": candidate_info.candidateid}

#     # If not a candidate, check if this email exists as an Employee.
#     # Treat the provided username as an email for employee lookup.
#     employee = db.query(EmployeeORM).filter(EmployeeORM.email == uname).first()
#     if employee:
#         # Grant employee an admin-like role for avatar access.
#         # We set role and is_admin flags; token creation will respect explicit role if provided.
#         return {**user.__dict__, "candidateid": None, "role": "admin", "is_admin": True, "is_employee": True}

#     # Not a candidate and not an employee
#     return "not_a_candidate"
from sqlalchemy.orm import Session
from fapi.utils.db_queries import get_user_by_username, fetch_candidate_id_and_status_by_email
from fapi.utils.auth_utils import verify_md5_hash
from fapi.db.models import EmployeeORM


def determine_user_role(user):
    from fapi.db.database import SessionLocal
    from fapi.db.models import EmployeeORM
    if user.uname.lower() == "admin":
        return {"role": "admin", "is_admin": True, "is_employee": False}

    # Check if user is employee (email in employee table)
    with SessionLocal() as db:
        employee = db.query(EmployeeORM).filter(EmployeeORM.email == user.uname).first()
        if employee:
            return {"role": "employee", "is_admin": True, "is_employee": True}

    # Default to candidate
    return {"role": "candidate", "is_admin": False, "is_employee": False}


async def authenticate_user(uname: str, passwd: str, db: Session):
    user = get_user_by_username(db, uname)
    if not user or not verify_md5_hash(passwd, user.passwd):
        return None

    if uname.lower() == "admin":
        return {**user.__dict__, "candidateid": None}

    if user.status.lower() != "active":
        return "inactive_authuser"

    # First try candidate lookup (existing behavior)
    candidate_info = fetch_candidate_id_and_status_by_email(db, uname)
    if candidate_info:
        if candidate_info.status.lower() not in ("active", "closed"):
            return "inactive_candidate"
        return {**user.__dict__, "candidateid": candidate_info.candidateid}

    # If not a candidate, check if this email exists as an Employee.
    # Treat the provided username as an email for employee lookup.
    employee = db.query(EmployeeORM).filter(EmployeeORM.email == uname).first()
    if employee:
        # Grant employee an admin-like role for avatar access.
        # We set role and is_admin flags; token creation will respect explicit role if provided.
        return {**user.__dict__, "candidateid": None, "role": "admin", "is_admin": True, "is_employee": True}

    # Not a candidate and not an employee
    return "not_a_candidate"
