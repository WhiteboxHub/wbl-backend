from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from jose import JWTError
from fapi.db.database import get_db
from fapi.utils.db_queries import get_user_by_username, update_user_password
from fapi.utils.auth_utils import create_reset_token, verify_reset_token
from fapi.utils.email_utils import send_reset_password_email
from fapi.utils.token_utils import verify_token
from fapi.db.schemas import TokenRequest

from fapi.db.schemas import ResetPasswordRequest, ResetPassword

router = APIRouter()

@router.post("/forget-password")
async def forget_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(db, request.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = create_reset_token(user.uname)
    await send_reset_password_email(user.uname, token)
    return JSONResponse(content={"message": "Password reset link has been sent to your email", "token": token})


@router.post("/reset-password")
async def reset_password(data: ResetPassword, db: Session = Depends(get_db)):
    uname = verify_reset_token(data.token)
    if uname is None:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = update_user_password(db, uname, data.new_password)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "Password updated successfully"}

@router.post("/verify-token")
async def verify_token_endpoint(token: TokenRequest):
    try:
        payload = verify_token(token.access_token)
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

