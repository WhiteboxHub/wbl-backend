# routes/contact.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fapi.db.schemas import ContactForm
from fapi.db.database import SessionLocal, get_db
from fapi.utils.contact_utils import save_contact_lead
from fapi.utils.email_utils import send_contact_emails

router = APIRouter()


@router.post("/contact")
async def contact(user: ContactForm, db: Session = Depends(get_db)):
    # Send email
    send_contact_emails(
        first_name=user.firstName,
        last_name=user.lastName,
        email=user.email,
        phone=user.phone,
        message=user.message
    )

    # Save to DB
    full_name = f"{user.firstName} {user.lastName}"
    save_contact_lead(
        db=db,
        full_name=full_name,
        email=user.email,
        phone=user.phone,
        message=user.message,
        status = "open"
    )

    return {"detail": "Message sent successfully"}
