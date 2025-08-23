from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from fapi.db.schemas import GoogleUserCreate
from fapi.db.database import SessionLocal, get_db
from fapi.utils.db_queries import fetch_candidate_id_and_status_by_email
from fapi.utils.google_auth_utils import get_google_user_by_email, insert_google_user_db
from fapi.auth import create_google_access_token
from fapi.core.config import SECRET_KEY, ALGORITHM
import jwt

router = APIRouter()


@router.post("/check_user/")
async def check_user_exists(user: GoogleUserCreate, db: Session = Depends(get_db)):
    existing_user = get_google_user_by_email(db, user.email)
    if existing_user:
        return {"exists": True, "status": existing_user.status}
    return {"exists": False}


@router.post("/check_user_direct/")
async def check_user_exists_direct(user: GoogleUserCreate):
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
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive account. Please contact admin."
            )

    insert_google_user_db(db, email=user.email, name=user.name, google_id=user.google_id)
    return {"message": "Google user registered successfully!"}


@router.post("/google_login/")
async def login_google_user(user: GoogleUserCreate, db: Session = Depends(get_db)):
    # 1. Look up AuthUser
    existing_user = get_google_user_by_email(db, user.email)
    if existing_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # 2. Check AuthUser status
    if existing_user.status.lower() != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive account. Please contact admin."
        )

    # 3. Candidate table check
    candidate_info = fetch_candidate_id_and_status_by_email(db, user.email)
    if not candidate_info:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Candidate record not found. Please register or contact support."
        )
    if candidate_info.status.lower() != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Candidate account is inactive. Please contact Recruiting at +1 925-557-1053."
        )

    # 4. Generate JWT
    token_data = {
        "sub": existing_user.uname,
        "team": getattr(existing_user, "team", "default_team")
    }
    access_token = await create_google_access_token(data=token_data)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "team": getattr(existing_user, "team", "default_team")
    }


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
