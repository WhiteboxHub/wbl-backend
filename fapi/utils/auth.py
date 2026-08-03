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
from sqlalchemy.orm import Session
from fapi.utils.db_queries import get_user_by_username, fetch_candidate_id_and_status_by_email
from fapi.utils.auth_utils import verify_md5_hash
from fapi.db.models import EmployeeORM

import os

def _get_admin_emails():
    emails_env = os.getenv("TEST_ADMIN_EMAILS", "")
    return {e.strip().lower() for e in emails_env.split(",") if e.strip()}

def determine_user_role(user):
    from fapi.db.database import SessionLocal
    from fapi.db.models import EmployeeORM

    raw_uname = getattr(user, "uname", "") or ""
    if raw_uname.lower() == "admin":
        return {"role": "admin", "is_admin": True, "is_employee": True}

    uname = raw_uname.lower().strip()

    user_role = getattr(user, 'role', None)
    if user_role:
        user_role = user_role.lower().strip()

    # AuthUser.role is the primary authoritative source of truth
    if user_role == 'admin':
        return {"role": "admin", "is_admin": True, "is_employee": True}
    elif user_role == 'employee':
        return {"role": "employee", "is_admin": False, "is_employee": True}
    elif user_role == 'candidate':
        return {"role": "candidate", "is_admin": False, "is_employee": False}

    # Fallback for legacy database records where AuthUser.role is unset / None
    with SessionLocal() as db:
        employee = db.query(EmployeeORM).filter(EmployeeORM.email == uname).first()
        if employee:
            role_str = 'admin' if uname in _get_admin_emails() else 'employee'
            return {"role": role_str, "is_admin": (role_str == 'admin'), "is_employee": True}

    return {"role": "candidate", "is_admin": False, "is_employee": False}


async def authenticate_user(uname: str, passwd: str, db: Session):
    user = get_user_by_username(db, uname)
    if not user or not verify_md5_hash(passwd, user.passwd):
        return None

    if uname.lower() == "admin":
        return {**user.__dict__, "candidateid": None, "role": "admin", "is_admin": True, "is_employee": True}

    if (getattr(user, "status", "") or "").lower() != "active":
        return "inactive_authuser"

    user_role = (getattr(user, "role", None) or "").lower().strip()

    # AuthUser.role is the primary authoritative source of truth
    if user_role == "admin":
        return {
            **user.__dict__,
            "candidateid": None,
            "role": "admin",
            "is_admin": True,
            "is_employee": True
        }
    elif user_role == "employee":
        return {
            **user.__dict__,
            "candidateid": None,
            "role": "employee",
            "is_admin": False,
            "is_employee": True
        }
    elif user_role == "candidate":
        candidate_info = fetch_candidate_id_and_status_by_email(db, uname)
        if candidate_info:
            if candidate_info.status.lower() not in ("active", "closed"):
                return "inactive_candidate"
            return {
                **user.__dict__,
                "candidateid": candidate_info.candidateid,
                "role": "candidate",
                "is_admin": False,
                "is_employee": False
            }
        return {
            **user.__dict__,
            "candidateid": None,
            "role": "candidate",
            "is_admin": False,
            "is_employee": False
        }

    # Fallback for legacy database records where AuthUser.role is unset / None
    candidate_info = fetch_candidate_id_and_status_by_email(db, uname)
    if candidate_info:
        if candidate_info.status.lower() not in ("active", "closed"):
            return "inactive_candidate"
        return {
            **user.__dict__,
            "candidateid": candidate_info.candidateid,
            "role": "candidate",
            "is_admin": False,
            "is_employee": False
        }

    employee = db.query(EmployeeORM).filter(EmployeeORM.email == uname).first()
    if employee:
        role = "admin" if uname.lower() in _get_admin_emails() else "employee"
        return {
            **user.__dict__,
            "candidateid": None,
            "role": role,
            "is_admin": (role == "admin"),
            "is_employee": True
        }

    return {
        **user.__dict__,
        "candidateid": None,
        "role": "candidate",
        "is_admin": False,
        "is_employee": False
    }
