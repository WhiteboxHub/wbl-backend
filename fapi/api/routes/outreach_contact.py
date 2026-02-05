import logging
from fastapi import APIRouter, Depends, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.db import schemas
from fapi.db.models import OutreachContactORM

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()

@router.get("/outreach-contact", response_model=List[schemas.OutreachContactOut])
@router.head("/outreach-contact")
def read_contacts(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return db.query(OutreachContactORM).all()

@router.post("/outreach-contact", response_model=schemas.OutreachContactOut)
def create_contact(
    contact: schemas.OutreachContactCreate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    from sqlalchemy.exc import IntegrityError
    from fastapi import HTTPException
    
    try:
        db_contact = OutreachContactORM(
            **contact.model_dump()
        )
        db.add(db_contact)
        db.commit()
        db.refresh(db_contact)
        return db_contact
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, 
            detail=f"Contact with email {contact.email} already exists"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/outreach-contact/{contact_id}", response_model=schemas.OutreachContactOut)
def update_contact(
    contact_id: int,
    contact_update: schemas.OutreachContactUpdate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    db_contact = db.query(OutreachContactORM).filter(OutreachContactORM.id == contact_id).first()
    if not db_contact:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Contact not found")
    
    update_data = contact_update.model_dump(exclude_unset=True)
        
    for key, value in update_data.items():
        setattr(db_contact, key, value)
    
    # If users didn't provide updated_at, force it to now.
    # If they DID provide it, respect their value (allows manual override)
    if 'updated_at' not in update_data:
        from sqlalchemy import func
        db_contact.updated_at = func.now()
        logger.info(f"Auto-updating updated_at for contact {contact_id}")
    else:
        logger.info(f"Manual updated_at provided for contact {contact_id}: {update_data['updated_at']}")
    
    db.commit()
    db.refresh(db_contact)
    return db_contact

@router.delete("/outreach-contact/{contact_id}")
def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    db_contact = db.query(OutreachContactORM).filter(OutreachContactORM.id == contact_id).first()
    if not db_contact:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Contact not found")
    
    db.delete(db_contact)
    db.commit()
    return {"message": "Contact deleted"}
