
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
