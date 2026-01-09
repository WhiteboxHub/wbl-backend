from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from fapi.db.database import SessionLocal, get_db
from fapi.db.schemas import UserRegistration
from fapi.utils.register_utils import create_user_and_lead
from fapi.utils.email_utils import send_email_to_user
from fapi.utils.auth_utils import md5_hash
from fapi.utils.recaptcha_utils import verify_recaptcha_token, ReCAPTCHAVerificationError


router = APIRouter()



@router.post("/signup")
async def register_user_api(request: Request, user: UserRegistration, db: Session = Depends(get_db)):
    # Verify reCAPTCHA token first
    try:
        recaptcha_result = await verify_recaptcha_token(user.recaptcha_token)
    except ReCAPTCHAVerificationError as e:
        raise HTTPException(status_code=400, detail=f"CAPTCHA verification failed: {str(e)}")
    
    user.uname = user.uname.lower().strip()
    user.passwd = md5_hash(user.passwd)

    create_user_and_lead(db, user)

    send_email_to_user(
        user_email=user.uname,
        user_name=f"{user.firstname or ''} {user.lastname or ''}".strip(),
        user_phone=user.phone
    )

    return {"message": "User registered successfully. Confirmation email sent to the user and admin."}
