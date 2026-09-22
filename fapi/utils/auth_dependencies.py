import os
import secrets
import logging
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from fapi.db.database import get_db
from fapi.db.models import AuthUserORM

logger = logging.getLogger("wbl")
security = HTTPBearer(auto_error=False)
security_optional = HTTPBearer(auto_error=False)

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
INTERNAL_WORKFLOW_SECRET = os.getenv("INTERNAL_WORKFLOW_SECRET")


def _check_internal_secret(request: Request):
    internal_secret = request.headers.get("X-Internal-Secret")
    if (
        INTERNAL_WORKFLOW_SECRET
        and internal_secret
        and secrets.compare_digest(internal_secret, INTERNAL_WORKFLOW_SECRET)
    ):
        class DummyInternalUser:
            id = 0
            uname = "scheduler_worker"
            role = "admin"
            is_admin = True
            is_employee = True
        return DummyInternalUser()
    return None


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
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
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
        internal_user = _check_internal_secret(request)
        if internal_user:
            return internal_user
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_token(token)
    user_id_or_name = payload.get("sub") or payload.get("user_id")

    if not user_id_or_name:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # fetch AuthUser by ID or uname
    user = None
    try:
        user = db.query(AuthUserORM).filter(AuthUserORM.id == int(user_id_or_name)).first()
    except ValueError:
        user = db.query(AuthUserORM).filter(AuthUserORM.uname == str(user_id_or_name)).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # attach token flags
    for attr in ["role", "is_admin", "is_employee"]:
        if attr in payload:
            try:
                setattr(user, attr, payload[attr])
            except Exception:
                pass

    return user
User = AuthUserORM


def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
    db: Session = Depends(get_db)
) -> Optional[AuthUserORM]:
    """Like get_current_user but returns None instead of raising 401 when no token
    is provided. Used by enforce_access to allow unauthenticated access to public
    GET/HEAD routes (e.g. /api/course-content, /api/course-contents).
    If a token is provided but invalid/expired, raises HTTP 401.
    """
    token = None

    if credentials and credentials.credentials:
        token = credentials.credentials
    else:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        internal_user = _check_internal_secret(request)
        if internal_user:
            return internal_user
        # No token provided -> return None for unauthenticated requests
        return None

    # Token provided: decode_token raises 401 if token is invalid or expired
    payload = decode_token(token)

    user_id_or_name = payload.get("sub") or payload.get("user_id")
    if not user_id_or_name:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = None
    try:
        user = db.query(AuthUserORM).filter(AuthUserORM.id == int(user_id_or_name)).first()
    except ValueError:
        user = db.query(AuthUserORM).filter(AuthUserORM.uname == str(user_id_or_name)).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    for attr in ["role", "is_admin", "is_employee"]:
        if attr in payload:
            try:
                setattr(user, attr, payload[attr])
            except Exception:
                pass

    return user

    for attr in ["role", "is_admin", "is_employee"]:
        if attr in payload:
            try:
                setattr(user, attr, payload[attr])
            except Exception:
                pass

    return user


def admin_required(current_user=Depends(get_current_user)):
    uname = (getattr(current_user, "uname", "") or "").lower()

    if (
        getattr(current_user, "role", None) == "admin"
        or getattr(current_user, "is_admin", False)
        or uname == "admin"
    ):
        return current_user

    raise HTTPException(status_code=403, detail="Admin privileges required")


def staff_or_admin_required(current_user=Depends(get_current_user)):
    """Admin, or employee (JWT is_employee), for CoderPad authoring and similar internal tools."""
    uname = (getattr(current_user, "uname", "") or "").lower()
    if (
        getattr(current_user, "role", None) == "admin"
        or getattr(current_user, "is_admin", False)
        or getattr(current_user, "is_employee", False)
        or uname == "admin"
    ):
        return current_user
    raise HTTPException(status_code=403, detail="Staff privileges required")


def check_modify_permission(request: Request, current_user=Depends(get_current_user)):
    modifying_methods = {"POST", "PUT", "PATCH", "DELETE"}
    method = request.method.upper()

    uname = (getattr(current_user, "uname", "") or "").lower()
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
        raise HTTPException(
            status_code=403,
            detail=f"Only admin users are allowed to perform {method} requests."
        )

    return True


def require_admin(current_user=Depends(get_current_user)):
    uname = (getattr(current_user, "uname", "") or "").lower()

    if getattr(current_user, "role", None) == "admin" or getattr(current_user, "is_admin", False) or uname == "admin":
        return current_user

    raise HTTPException(status_code=403, detail="only admins can access")


