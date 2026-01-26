# hr_contact_utils.py-

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException
from pydantic import BaseModel, EmailStr, ValidationError
from fapi.db.models import CompanyHRContact
from fapi.db.schemas import HRContactCreate, HRContactUpdate

logger = logging.getLogger(__name__)


# ---------- Helpers ----------
class _EmailValidator(BaseModel):
    email: EmailStr

def _normalize_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    try:
        # Validates & normalizes (lowercase) via pydantic
        valid = _EmailValidator(email=email.strip())
        return valid.email.lower()
    except ValidationError:
        logger.warning("Invalid email encountered while normalizing")
        return None


def _init_cap(text: Optional[str]) -> Optional[str]:
    """Converts a string to Init Cap (Title Case)."""
    if not text:
        return text
    # This specifically capitalizes each word, being more robust than .title() for some cases
    return " ".join(word.capitalize() for word in text.strip().split())


# ---------- CRUD: HR Contact ----------
def get_all_hr_contacts(db: Session) -> List[CompanyHRContact]:
    contacts = db.query(CompanyHRContact).order_by(CompanyHRContact.id.desc()).all()
    # Normalize/validate emails for outbound payload (does not persist changes)
    for c in contacts:
        c.email = _normalize_email(c.email)
    return contacts


def create_hr_contact(db: Session, contact: HRContactCreate) -> CompanyHRContact:
    payload = contact.dict()
    payload["email"] = _normalize_email(payload.get("email"))
    
    # Optional: enforce uniqueness on email if present
    if payload.get("email"):
        dup = (
            db.query(CompanyHRContact)
            .filter(func.lower(CompanyHRContact.email) == payload["email"])
            .first()
        )
        if dup:
            raise HTTPException(status_code=400, detail="Email already exists.")

    new_contact = CompanyHRContact(**payload)
    db.add(new_contact)
    try:
        db.commit()
        db.refresh(new_contact)
        return new_contact
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already exists.")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Create failed: {str(e)}")


def update_hr_contact_handler(db: Session, contact_id: int, update_data: HRContactUpdate) -> CompanyHRContact:
    fields = update_data.dict(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No data to update")

    contact = db.query(CompanyHRContact).filter(CompanyHRContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="HR Contact not found")

    # Normalize email if provided
    if "email" in fields:
        fields["email"] = _normalize_email(fields["email"])
        
    if "email" in fields and fields["email"]:
        dup = (
            db.query(CompanyHRContact)
            .filter(func.lower(CompanyHRContact.email) == fields["email"], CompanyHRContact.id != contact_id)
            .first()
        )
        if dup:
            raise HTTPException(status_code=400, detail="Email already exists.")

    try:
        for key, value in fields.items():
            setattr(contact, key, value)
        db.commit()
        db.refresh(contact)
        return contact
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


def delete_hr_contact(db: Session, contact_id: int) -> Dict[str, str]:
    contact = db.query(CompanyHRContact).filter(CompanyHRContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="HR Contact not found")
    try:
        db.delete(contact)
        db.commit()
        return {"message": f"HR Contact with ID {contact_id} deleted successfully"}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


def delete_hr_contacts_bulk(db: Session, contact_ids: List[int]) -> int:
    try:
        deleted_count = db.query(CompanyHRContact).filter(CompanyHRContact.id.in_(contact_ids)).delete(synchronize_session=False)
        db.commit()
        return deleted_count
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Bulk delete failed: {e}")
        raise HTTPException(status_code=500, detail=f"Bulk delete failed: {str(e)}")
