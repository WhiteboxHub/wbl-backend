
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.utils.auth import authenticate_user
from fapi.auth import create_access_token
from fapi.db.schemas import Token
from fapi.core.config import limiter
from fapi.db.models import AuthUserORM
from fapi.utils.user_utils import get_user_by_username

router = APIRouter()


@router.post("/login", response_model=Token)
@limiter.limit("15/minute")
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    print(f"Login attempt for username: {form_data.username}")
    user = await authenticate_user(form_data.username, form_data.password, db)
    print(f"Authenticate user result: {user}")

    if user == "inactive_authuser":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive. Please contact Recruiting at +1 925-557-1053.",
        )

    if user == "inactive_candidate":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Candidate account is inactive. Please contact Recruiting at +1 925-557-1053.",
        )

    if user == "inactive_employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee account is inactive. Contact company admin.",
        )

    if user == "not_a_candidate":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Candidate/Employee record not found. Please contact support.",
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid username or password.",
        )
    db_user = get_user_by_username(db, user.get("uname"))
    if db_user:

        db_user.logincount = (db_user.logincount or 0) + 1
        db.commit()
        db.refresh(db_user)
        login_count = db_user.logincount
    else:
        login_count = 0
    token_data = {
        "sub": user.get("uname"),
        "team": user.get("team", "default_team"),
        "role": user.get("role", None),
        "is_admin": user.get("is_admin", False),
        "is_employee": user.get("is_employee", False),
    }

    access_token = create_access_token(token_data)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "team": user.get("team", "default_team"),
        "login_count": login_count
    }
