import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.utils.table_fingerprint import generate_version_for_model
from fapi.db import schemas
from fapi.utils import authuser_utils
from fapi.db.models import AuthUserORM

import hashlib
from fastapi import Response, APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy import func

logger = logging.getLogger(__name__)
router = APIRouter()

security = HTTPBearer()

@router.head("/users")
@router.head("/user")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return generate_version_for_model(db, AuthUserORM)

def check_users_version(db: Session = Depends(get_db)):
    try:
        result = db.query(
            func.count().label("cnt"),
            func.max(AuthUserORM.id).label("max_id"),
            func.sum(
                func.crc32(
                    func.concat_ws(
                        '|',
                        AuthUserORM.id,
                        func.coalesce(AuthUserORM.uname, ''),
                        func.coalesce(AuthUserORM.status, ''),
                        func.coalesce(AuthUserORM.role, ''),
                        func.coalesce(AuthUserORM.team, '')
                    )
                )
            ).label("checksum")
        ).first()

        response = Response(status_code=200)
        if result and result.cnt > 0:
            fingerprint = f"{result.cnt}|{result.max_id}|{result.checksum}"
            version_hash = hashlib.md5(fingerprint.encode()).hexdigest()
            response.headers["X-Data-Version"] = version_hash
            response.headers["Last-Modified"] = version_hash
        else:
            response.headers["X-Data-Version"] = "empty"
            response.headers["Last-Modified"] = "empty"

        return response
    except Exception:
        response = Response(status_code=200)
        response.headers["X-Data-Version"] = "error"
        response.headers["Last-Modified"] = "error"
        return response


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
