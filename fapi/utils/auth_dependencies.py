# wbl-backend/fapi/utils/auth_dependencies.py

import os
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from fapi.db.database import get_db
from fapi.db.models import AuthUserORM

# Security scheme
security = HTTPBearer(auto_error=False)

# Environment variables
SECRET_KEY = os.getenv("SECRET_KEY", "change_this_secret")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


# 🔐 Decode the JWT token
def decode_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# 👤 Get currently logged-in user (handles both admin & normal users)
def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    # token = credentials.credentials if credentials else request.headers.get("access-tokan")
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

    # 🧩 Works for both numeric IDs and username-based tokens
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


# 👑 Allow access only for admin users
def admin_required(current_user=Depends(get_current_user)):
    # accept role flag, boolean flag, OR username 'admin'
    uname = (getattr(current_user, "uname", None) or getattr(current_user, "username", "") or "").lower()
    if (
        getattr(current_user, "role", None) == "admin"
        or getattr(current_user, "is_admin", False)
        or uname == "admin"
    ):
        return current_user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
        
    
# fapi/utils/auth_dependencies.py


