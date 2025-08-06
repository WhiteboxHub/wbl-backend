
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status
from datetime import datetime
from fapi.db.models import LeadORM



def save_contact_form(
    db: Session,
    first_name: str,
    last_name: str,
    email: str,
    phone: str = None,
    notes: str = None,
    workstatus: str = None
) -> LeadORM:
    try:
        full_name = f"{first_name.strip()} {last_name.strip()}"
        now = datetime.utcnow()

        new_lead = LeadORM(
            full_name=full_name,
            email=email.strip().lower(),
            phone=phone.strip() if phone else None,
            notes=notes,
            entry_date=now,
            last_modified=now,
            status="Open",
            workstatus=workstatus,
            moved_to_candidate=False
        )

        db.add(new_lead)
        db.commit()
        db.refresh(new_lead)
        return new_lead

    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save contact: {str(e)}"
        )