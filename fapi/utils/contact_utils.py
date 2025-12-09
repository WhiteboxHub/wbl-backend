# utils/contact_utils.py
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from sqlalchemy.orm import Session
from fapi.db.models import LeadORM
from datetime import datetime

def save_contact_lead(
    db: Session, full_name: str, email: str = None,
    phone: str = None, message: str = None, status: str = "Open"
):
    try:
        lead = LeadORM(
            full_name=full_name.strip().lower() if full_name else None,
            email=email.strip().lower() if email else None,
            phone=phone,
            notes=message,
            moved_to_candidate=False,
            entry_date=datetime.utcnow(),
            last_modified=datetime.utcnow(),
            status=status
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return lead
    
    except IntegrityError as e:
        db.rollback()
        error_message = str(e.orig) if hasattr(e, "orig") else str(e)
        print(f"[DEBUG] IntegrityError: {error_message}")

        if "Duplicate entry" in error_message and "'lead.unique_email'" in error_message:
            raise HTTPException(status_code=409, detail="A contact with this email already exists.")
        else:
            raise HTTPException(status_code=400, detail="Invalid data or constraint violation.")

    except Exception as e:
        db.rollback()
        print(f"[DEBUG] Unexpected Exception: {str(e)}")  
        raise HTTPException(status_code=500, detail="An unexpected error occurred while saving contact.")
