import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.db import schemas
from fapi.utils import authuser_utils
from fapi.db.models import AuthUserORM

logger = logging.getLogger(__name__)
router = APIRouter()

security = HTTPBearer()


@router.get("/users", response_model=List[schemas.AuthUserResponse])
def get_all_users(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    try:
        users = db.query(AuthUserORM).order_by(AuthUserORM.id.desc()).all()
        return [authuser_utils.clean_dates(u) for u in users]
    except Exception as e:
        logger.exception("Error fetching users")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user", response_model=schemas.PaginatedUsers)
def read_users(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(100, ge=1, le=100, description="Users per page"),
    search_id: int = Query(None, description="Search by user ID"),
    search_name: str = Query(None, description="Search by user name"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    return authuser_utils.get_users_paginated(
        db, page=page, per_page=per_page, search_id=search_id, search_name=search_name
    )


@router.get("/user/{user_id}", response_model=schemas.AuthUserResponse)
def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    user = authuser_utils.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("/user", response_model=schemas.AuthUserResponse)
def create_user(user: schemas.AuthUserCreate, db: Session = Depends(get_db)):
    return authuser_utils.create_user(db, user)


@router.put("/user/{user_id}", response_model=schemas.AuthUserResponse)
def update_user(user_id: int, user: schemas.AuthUserUpdate, db: Session = Depends(get_db)):
    updated_user = authuser_utils.update_user(db, user_id, user)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user


@router.delete("/user/{user_id}", response_model=schemas.AuthUserResponse)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    deleted_user = authuser_utils.delete_user(db, user_id)
    if not deleted_user:
        raise HTTPException(status_code=404, detail="User not found")
    return deleted_user
