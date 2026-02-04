from fastapi import APIRouter, Depends, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.db import schemas
from fapi.db.models import OutreachContactORM

router = APIRouter()
security = HTTPBearer()

@router.get("/outreach-contact", response_model=List[schemas.OutreachContactOut])
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
