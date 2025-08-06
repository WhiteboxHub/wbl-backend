
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fapi.db.database import SessionLocal
from fapi.db.schemas import ContactCreate, ContactFormResponse
from fapi.utils.contact_utils import save_contact_form

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/contact", response_model=ContactFormResponse)
def submit_contact_form_route(contact: ContactCreate, db: Session = Depends(get_db)):
    try:
        lead = save_contact_form(
            db=db,
            first_name=contact.first_name,
            last_name=contact.last_name,
            email=contact.email,
            phone=contact.phone,
            notes=contact.notes ,
            workstatus=contact.workstatus
        )
        return lead
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while submitting the contact form."
        )



