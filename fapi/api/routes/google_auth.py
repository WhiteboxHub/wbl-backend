# wbl-backend\fapi\api\routes\google_auth.py
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from fapi.db.schemas import GoogleUserCreate
from fapi.db.database import SessionLocal
from fapi.utils.google_auth_utils import get_google_user_by_email, insert_google_user_db,get_google_user_by_email
from  fapi.auth import create_google_access_token
from fapi.core.config import SECRET_KEY, ALGORITHM
from fapi.db import models
import jwt

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# SECRET_KEY = "your_secret_key"
# ALGORITHM = "HS256"

@router.post("/check_user/")
async def check_user_exists(user: GoogleUserCreate, db: Session = Depends(get_db)):
    existing_user = get_google_user_by_email(db, user.email)
    if existing_user:
        return {"exists": True, "status": existing_user.status}
    return {"exists": False}


@router.post("/check_user_direct/")
async def check_user_exists_direct(user: GoogleUserCreate):
    # from app.db.database import SessionLocal
    db = SessionLocal()
    try:
        existing_user = get_google_user_by_email(db, user.email)
        if existing_user:
            return {"exists": True, "status": existing_user.status}
        return {"exists": False}
    finally:
        db.close()

@router.post("/google_users/")
async def register_google_user(user: GoogleUserCreate, db: Session = Depends(get_db)):
    existing_user = get_google_user_by_email(db, user.email)

    if existing_user:
        if existing_user.status == "active":
            return {"message": "User already registered and active, please log in."}
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive account. Please contact admin.")

    insert_google_user_db(db, email=user.email, name=user.name, google_id=user.google_id)
    return {"message": "Google user registered successfully!"}

@router.post("/google_login/")
async def login_google_user(user: GoogleUserCreate, db: Session = Depends(get_db)):
    existing_user = get_google_user_by_email(db, user.email)
    if existing_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if existing_user.status == "inactive":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive account. Please contact admin.")

    token_data = {
        "sub": existing_user.uname,
        "name": existing_user.fullname,
        "google_id": existing_user.googleId,
    }
    # Assume the token function is imported
    access_token = await create_google_access_token(data=token_data)
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/verify_google_token/")
async def verify_google_token(token: str):
    try:
        if token.startswith('"') and token.endswith('"'):
            token = token[1:-1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
