# wbl-backend/fapi/utils/authuser_utils.py
from sqlalchemy.orm import Session
from fapi.db.models import AuthUserORM
from fapi.db.schemas import AuthUserCreate, AuthUserUpdate
from fapi.utils.auth_utils import hash_password
from datetime import datetime





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


def create_user(db: Session, user: AuthUserCreate):
    db_user = AuthUserORM(
        uname=user.uname,
        passwd=hash_password(user.passwd),
        fullname=user.fullname,
        phone=user.phone,
        team=user.team,
        role=user.role,
        status=user.status,
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
    for key, value in user.dict(exclude_unset=True).items():
        setattr(db_user, key, value)
    db.commit()
    db.refresh(db_user)
    return clean_dates(db_user)


def delete_user(db: Session, user_id: int):
    db_user = db.query(AuthUserORM).filter(AuthUserORM.id == user_id).first()
    if db_user:
        db.delete(db_user)
        db.commit()
    return db_user
