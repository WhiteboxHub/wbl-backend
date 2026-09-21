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

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM") or os.getenv("ALGORITHM") or "HS256"


def decode_token(token: str):
    secret = os.getenv("SECRET_KEY") or SECRET_KEY
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication secret key is not configured",
        )
    algorithm = os.getenv("JWT_ALGORITHM") or os.getenv("ALGORITHM") or ALGORITHM or "HS256"
    try:
        return jwt.decode(token, secret, algorithms=[algorithm])
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

    if credentials and isinstance(credentials.credentials, str):
        token = credentials.credentials
    else:
        auth_header = request.headers.get("Authorization") if hasattr(request, "headers") and hasattr(request.headers, "get") else None
        if isinstance(auth_header, str) and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
        else:
            query_token = None
            if hasattr(request, "query_params") and hasattr(request.query_params, "get"):
                raw_q = request.query_params.get("token")
                if isinstance(raw_q, str) and raw_q:
                    query_token = raw_q

            cookie_token = None
            if not query_token and hasattr(request, "cookies") and hasattr(request.cookies, "get"):
                raw_c = request.cookies.get("access_token") or request.cookies.get("token")
                if isinstance(raw_c, str) and raw_c:
                    cookie_token = raw_c

            token = query_token or cookie_token

    if not token:
        internal_secret = request.headers.get("X-Internal-Secret")
        expected_internal_secret = os.getenv("INTERNAL_WORKFLOW_SECRET")
        if (
            internal_secret
            and expected_internal_secret
            and secrets.compare_digest(internal_secret, expected_internal_secret)
        ):
            class DummyInternalUser:
                id = 0
                uname = "scheduler_worker"
                role = "admin"
                is_admin = True
                is_employee = True
            return DummyInternalUser()
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


