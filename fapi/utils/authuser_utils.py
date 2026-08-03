# wbl-backend/fapi/utils/authuser_utils.py
import re 
from typing import List
from sqlalchemy.orm import Session
from fapi.db.models import AuthUserORM, EmployeeORM
from fapi.db.schemas import AuthUserCreate, AuthUserUpdate
from fapi.utils.auth_utils import hash_password
from datetime import datetime
from fastapi import HTTPException, Response
from fapi.utils.table_fingerprint import generate_version_for_model


def clean_dates(user):
    if not user:
        return None

    for field in ["lastlogin", "registereddate", "level3date", "token_expiry"]:
        value = getattr(user, field, None)
        if value and str(value) == "0000-00-00 00:00:00":
            setattr(user, field, None)
    return user


def get_users_paginated(db: Session, page: int = 1, per_page: int = 100, search_id: int = None, search_name: str = None):
    query = db.query(AuthUserORM)
    
    if search_id is not None:
        query = query.filter(AuthUserORM.id == search_id)
    
    if search_name:
        search_pattern = f"%{search_name}%"
        query = query.filter(
            (AuthUserORM.uname.ilike(search_pattern)) |
            (AuthUserORM.fullname.ilike(search_pattern))
        )
    
    total = query.count()
    offset = (page - 1) * per_page
    users = query.order_by(AuthUserORM.id.desc()).offset(offset).limit(per_page).all()
    
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "users": [clean_dates(u) for u in users],
    }


def get_user(db: Session, user_id: int):
    user = db.query(AuthUserORM).filter(AuthUserORM.id == user_id).first()
    return clean_dates(user)

def validate_password_strength(password: str):
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password):
        raise HTTPException(status_code=400, detail="Password must include at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise HTTPException(status_code=400, detail="Password must include at least one lowercase letter.")
    if not re.search(r"\d", password):
        raise HTTPException(status_code=400, detail="Password must include at least one number.")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise HTTPException(status_code=400, detail="Password must include at least one special character.")

def create_user(db: Session, user: AuthUserCreate):
    db_user = AuthUserORM(
        uname=user.uname,
        passwd=hash_password(user.passwd),
        fullname=user.fullname,
        phone=user.phone,
        team=user.team,
        role=user.role or "candidate",
        status=user.status or "inactive",
        visa_status=user.visa_status,
        lastmoddatetime=datetime.utcnow(),
        registereddate=datetime.utcnow(),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return clean_dates(db_user)


def update_user(db: Session, user_id: int, user: AuthUserUpdate):
    db_user = db.query(AuthUserORM).filter(AuthUserORM.id == user_id).first()
    if not db_user:
        return None

    update_data = user.dict(exclude_unset=True)
    if "passwd" in update_data:
        if update_data["passwd"]:
            validate_password_strength(update_data["passwd"])
            update_data["passwd"] = hash_password(update_data["passwd"])
        else:
            update_data.pop("passwd")

    # Capture the current role BEFORE applying updates (needed for change detection)
    old_role = getattr(db_user, "role", None)
    if hasattr(old_role, "value"):
        old_role = old_role.value
    if old_role is not None:
        old_role = str(old_role).lower().strip()

    for key, value in update_data.items():
        setattr(db_user, key, value)

    # Safely extract role value (handles both str and Enum instances)
    role_val = update_data.get("role")
    if hasattr(role_val, "value"):
        role_val = role_val.value
    if role_val is not None:
        role_val = str(role_val).lower().strip()

    # Safely extract status value
    status_val = update_data.get("status")
    if hasattr(status_val, "value"):
        status_val = status_val.value
    if status_val is not None:
        status_val = str(status_val).lower().strip()

    # Only invalidate refresh tokens when role ACTUALLY changed or account is deactivated
    # (avoids logging out users on profile-only updates where role is included but unchanged)
    role_changed = role_val is not None and role_val != old_role
    if role_changed or status_val == "inactive":
        db_user.refresh_token = None
        db_user.refresh_token_expiry = None

    # Auto-create Employee record when role is promoted to "employee"
    # so the employee dashboard works immediately after login
    if role_val == "employee" and db_user.uname:
        existing_employee = db.query(EmployeeORM).filter(
            EmployeeORM.email == db_user.uname.lower().strip()
        ).first()
        if not existing_employee:
            new_employee = EmployeeORM(
                name=db_user.fullname or db_user.uname,
                email=db_user.uname.lower().strip(),
                phone=db_user.phone,
            )
            db.add(new_employee)

    db_user.lastmoddatetime = datetime.utcnow()

    db.commit()
    db.refresh(db_user)
    return clean_dates(db_user)


def delete_user(db: Session, user_id: int):
    db_user = db.query(AuthUserORM).filter(AuthUserORM.id == user_id).first()
    if db_user:
        db.delete(db_user)
        db.commit()
    return db_user

def get_all_users(db: Session) -> List[AuthUserORM]:
    users = db.query(AuthUserORM).order_by(AuthUserORM.id.desc()).all()
    return [clean_dates(u) for u in users]

def get_users_version(db: Session) -> Response:
    return generate_version_for_model(db, AuthUserORM)
