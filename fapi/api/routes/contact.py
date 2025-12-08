# # routes/contact.py
# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from fapi.db.schemas import ContactForm
# from fapi.db.database import SessionLocal, get_db
# from fapi.utils.contact_utils import save_contact_lead
# from fapi.utils.email_utils import send_contact_emails

# router = APIRouter()


# @router.post("/contact")
# async def contact(user: ContactForm, db: Session = Depends(get_db)):
#     # Send email
#     send_contact_emails(
#         first_name=user.firstName,
#         last_name=user.lastName,
#         email=user.email,
#         phone=user.phone,
#         message=user.message
#     )

#     # Save to DB
#     full_name = f"{user.firstName} {user.lastName}"
#     save_contact_lead(
#         db=db,
#         full_name=full_name,
#         email=user.email,
#         phone=user.phone,
#         message=user.message,
#         status = "open"
#     )

#     return {"detail": "Message sent successfully"}











from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from datetime import datetime

router = APIRouter()

class ContactRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    message: str
    captcha_token: str

class ContactResponse(BaseModel):
    message: str
    contact_id: int
    timestamp: str

@router.post("/contact")
async def contact_submit(contact: ContactRequest):
    """Submit a contact form"""
    # Validate message length
    if len(contact.message.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Message must be at least 10 characters long"
        )
    
    # TODO: Verify CAPTCHA token
    # TODO: Save to database
    # TODO: Send email notification
    
    return ContactResponse(
        message="Thank you for your message. We'll get back to you soon.",
        contact_id=2001,
        timestamp=datetime.now().isoformat()
    )

@router.get("/contact/test")
async def test_contact():
    """Test endpoint for contact form"""
    return {
        "message": "Contact endpoint is working",
        "endpoint": "POST /api/contact",
        "status": "active",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/contact/stats")
async def contact_stats():
    """Get contact form statistics"""
    return {
        "total_submissions": 150,
        "today_submissions": 3,
        "average_response_time": "24 hours",
        "timestamp": datetime.now().isoformat()
    }

