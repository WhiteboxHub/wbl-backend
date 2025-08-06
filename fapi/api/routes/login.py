# wbl-backend/fapi/api/routes/login.py
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from fapi.db.database import SessionLocal
# from fapi.db.database import get_db
from fapi.utils.auth import authenticate_user
from fapi.auth import create_access_token
from fapi.db.schemas import Token
from fastapi_limiter.depends import RateLimiter

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/login", response_model=Token, dependencies=[Depends(RateLimiter(times=15, seconds=60))])
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
    # _=Depends(RateLimiter(times=15, seconds=60)),
):
    user = await authenticate_user(form_data.username, form_data.password, db)

    if user == "inactive_authuser":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive in the system. Please contact Recruiting at +1 925-557-1053.",
        )
    elif user == "inactive_candidate":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Candidate account is inactive. Please contact Recruiting at +1 925-557-1053.",
        )
    elif user == "not_a_candidate":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Candidate record not found. Please register or contact support.",
        )
    elif not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid username or password.",
        )


    access_token = create_access_token(
        data={
            "sub": user.get("uname"),
            "team": user.get("team", "default_team")  
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "team": user.get("team", "default_team")
    }


