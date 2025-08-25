# wbl-backend/fapi/api/routes/authuser.py
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db import schemas
from fapi.utils import authuser_utils


router = APIRouter()


@router.get("/user", response_model=schemas.PaginatedUsers)
def read_users(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(100, ge=1, le=100, description="Users per page"),
    db: Session = Depends(get_db),
):
    return authuser_utils.get_users_paginated(db, page=page, per_page=per_page)


@router.get("/user/{user_id}", response_model=schemas.AuthUserResponse)
def read_user(user_id: int, db: Session = Depends(get_db)):
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
