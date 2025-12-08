# from fastapi import APIRouter, Depends, Request
# from sqlalchemy.orm import Session
# from fapi.db.database import SessionLocal, get_db
# from fapi.db.schemas import UserRegistration
# from fapi.utils.register_utils import create_user_and_lead
# from fapi.utils.email_utils import send_email_to_user
# from fapi.utils.auth_utils import md5_hash


# router = APIRouter()



# @router.post("/signup")
# async def register_user_api(request: Request, user: UserRegistration, db: Session = Depends(get_db)):
#     user.uname = user.uname.lower().strip()
#     user.passwd = md5_hash(user.passwd)

#     create_user_and_lead(db, user)

#     send_email_to_user(
#         user_email=user.uname,
#         user_name=f"{user.firstname or ''} {user.lastname or ''}".strip(),
#         user_phone=user.phone
#     )

#     return {"message": "User registered successfully. Confirmation email sent to the user and admin."}






from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

router = APIRouter()

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    captcha_token: str

class RegisterResponse(BaseModel):
    message: str
    user_id: int
    email: str
    timestamp: str

@router.post("/signup")
async def register_user(user: RegisterRequest):
    """Register a new user"""
    # Validate password strength
    if len(user.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long"
        )
    
    # TODO: Verify CAPTCHA token
    # TODO: Hash password
    # TODO: Check if user already exists
    # TODO: Save to database
    
    # Mock registration
    return RegisterResponse(
        message="Registration successful. Please check your email to verify your account.",
        user_id=1001,
        email=user.email,
        timestamp=datetime.now().isoformat()
    )

@router.get("/signup/test")
async def test_register():
    """Test endpoint for registration"""
    return {
        "message": "Registration endpoint is working",
        "endpoint": "POST /api/signup",
        "status": "active",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/signup/check-email/{email}")
async def check_email_availability(email: str):
    """Check if email is available"""
    # Mock check - Replace with actual database check
    taken_emails = ["admin@example.com", "test@example.com"]
    
    if email in taken_emails:
        return {"available": False, "message": "Email already registered"}
    
    return {"available": True, "message": "Email is available"}
