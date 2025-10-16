import os
import logging
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from fapi.db.database import get_db
from fapi.db.models import AuthUserORM
logger = logging.getLogger("wbl")
security = HTTPBearer(auto_error=False)

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


def decode_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    else:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = decode_token(token)
    user_id_or_name = payload.get("sub") or payload.get("user_id")
    if not user_id_or_name:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = None
    try:
        user = db.query(AuthUserORM).filter(AuthUserORM.id == int(user_id_or_name)).first()
    except ValueError:
        user = db.query(AuthUserORM).filter(AuthUserORM.uname == str(user_id_or_name)).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user

def admin_required(current_user=Depends(get_current_user)):
    uname = (getattr(current_user, "uname", None) or getattr(current_user, "username", "") or "").lower()
    if (
        getattr(current_user, "role", None) == "admin"
        or getattr(current_user, "is_admin", False)
        or uname == "admin"
    ):
        return current_user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")

def check_modify_permission(request: Request, current_user=Depends(get_current_user)):
    modifying_methods = {"POST", "PUT", "PATCH", "DELETE"}
    method = request.method.upper()

    uname = (getattr(current_user, "uname", None)
             or getattr(current_user, "username", "") or "").lower()
    is_admin = (
        getattr(current_user, "role", None) == "admin"
        or getattr(current_user, "is_admin", False)
        or uname == "admin"
    )

    logger.info(
        "check_modify_permission invoked -> user_id=%s uname=%s role=%s is_admin=%s method=%s",
        getattr(current_user, "id", None),
        uname,
        getattr(current_user, "role", None),
        getattr(current_user, "is_admin", None),
        method,
    )

    if method in modifying_methods and not is_admin:
        logger.warning("Modify blocked for user_id=%s method=%s role=%s", getattr(current_user, "id", None), method, getattr(current_user, "role", None))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only admin users are allowed to perform {method} requests."
        )

    return True



