# routes/contact.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fapi.db.schemas import ContactForm
from fapi.db.database import SessionLocal, get_db
from fapi.utils.contact_utils import save_contact_lead
from fapi.utils.email_utils import send_contact_emails
from fapi.utils.recaptcha_utils import verify_recaptcha_token, ReCAPTCHAVerificationError

router = APIRouter()


@router.post("/contact")
async def contact(user: ContactForm, db: Session = Depends(get_db)):
    # Verify reCAPTCHA token first
    try:
        recaptcha_result = await verify_recaptcha_token(user.recaptcha_token)
    except ReCAPTCHAVerificationError as e:
        raise HTTPException(status_code=400, detail=f"CAPTCHA verification failed: {str(e)}")
    
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
