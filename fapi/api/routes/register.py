from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from fapi.db.database import SessionLocal
from fapi.db.schemas import UserRegistration
from fapi.utils.register_utils import create_user_and_lead
from fapi.utils.email_utils import send_email_to_user
from fapi.utils.auth_utils import md5_hash


router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/api/signup")
async def register_user_api(request: Request, user: UserRegistration, db: Session = Depends(get_db)):
    user.uname = user.uname.lower().strip()
    user.passwd = md5_hash(user.passwd)

    create_user_and_lead(db, user)

    send_email_to_user(
        user_email=user.uname,
        user_name=f"{user.firstname or ''} {user.lastname or ''}".strip(),
        user_phone=user.phone
    )

    return {"message": "User registered successfully. Confirmation email sent to the user and admin."}
