# fapi/routes/user_role.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, ExpiredSignatureError, jwt
from sqlalchemy.orm import Session
from fapi.db.database import SessionLocal
from fapi.utils.auth import determine_user_role
from fapi.utils.db_queries import get_user_by_username
from fapi.core.config import SECRET_KEY, ALGORITHM
import os

router = APIRouter()
security = HTTPBearer()

# SECRET_KEY = os.getenv("SECRET_KEY")
# ALGORITHM = os.getenv("ALGORITHM", "HS256")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/api/user_role")
async def get_user_role(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
    except (ExpiredSignatureError, JWTError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    userinfo = get_user_by_username(db, username)
    if not userinfo:
        raise HTTPException(status_code=404, detail="User not found")

    role = determine_user_role(userinfo)
    return {"role": role}
