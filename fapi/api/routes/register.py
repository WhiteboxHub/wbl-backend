# wbl-backend/fapi/api/routes/register.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from fapi.db.schemas import UserRegistration
from fapi.db.database import get_db
from fapi.utils.register_utils import create_user_and_lead
from fapi.utils.auth_utils import md5_hash
from fapi.utils.captcha_utils import verify_recaptcha_token
from fapi.utils.email_utils import send_email_to_user

router = APIRouter()


@router.post("/signup")
async def register_user(user: UserRegistration, db: Session = Depends(get_db)):

    # VERIFY CAPTCHA TOKEN (common shared function)
    verify_recaptcha_token(user.captchaToken)

    # VALIDATE PASSWORD
    if len(user.passwd) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")

    # NORMALIZE DATA
    user.uname = user.uname.lower().strip()
    user.passwd = md5_hash(user.passwd)

    # CREATE BOTH USER + LEAD
    create_user_and_lead(db, user)

    # SEND EMAILS
    full_name = f"{user.firstname or ''} {user.lastname or ''}".strip()

    # Email to User
    send_email_to_user(
        user_email=user.uname,
        user_name=full_name,
        user_phone=user.phone
    )

    # FINAL RESPONSE
    return {
        "message": "User registered successfully.",
        "email": user.uname,
        "timestamp": datetime.utcnow().isoformat()
    }