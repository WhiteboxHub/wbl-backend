# # wbl-backend/fapi/api/routes/login.py
# from fastapi import APIRouter, Depends, HTTPException, status, Request
# from fastapi.security import OAuth2PasswordRequestForm
# from sqlalchemy.orm import Session
# from fapi.db.database import SessionLocal, get_db
# from fapi.utils.auth import authenticate_user
# from fapi.auth import create_access_token
# from fapi.db.schemas import Token
# from fapi.core.config import limiter 

# router = APIRouter()



# @router.post("/login", response_model=Token)
# @limiter.limit("15/minute")
# async def login_for_access_token(
#     request: Request,
#     form_data: OAuth2PasswordRequestForm = Depends(),
#     db: Session = Depends(get_db)
# ):
#     user = await authenticate_user(form_data.username, form_data.password, db)

#     if user == "inactive_authuser":
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Account is inactive. Please contact Recruiting at +1 925-557-1053.",
#         )
#     elif user == "inactive_candidate":
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Candidate account is inactive. Please contact Recruiting at +1 925-557-1053.",
#         )
#     elif user == "not_a_candidate":
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Candidate record not found. Please register or contact support.",
#         )
#     elif not user:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Invalid username or password.",
#         )

#     access_token = create_access_token(
#         data={
#             "sub": user.get("uname"),
#             "team": user.get("team", "default_team")  
#         }
#     )

#     return {
#         "access_token": access_token,
#         "token_type": "bearer",
#         "team": user.get("team", "default_team")
#     }
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.utils.auth import authenticate_user
from fapi.auth import create_access_token
from fapi.db.schemas import Token
from fapi.core.config import limiter

router = APIRouter()


@router.post("/login", response_model=Token)
@limiter.limit("15/minute")
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = await authenticate_user(form_data.username, form_data.password, db)

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

    # Create token (same as before)
    access_token = create_access_token(
        data={
            "sub": user.get("uname"),
            "team": user.get("team", "default_team"),
            "role": user.get("role", None),
            "is_admin": user.get("is_admin", False),
            "is_employee": user.get("is_employee", False),
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "team": user.get("team", "default_team"),
    }
