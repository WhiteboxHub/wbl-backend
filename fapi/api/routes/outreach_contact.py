from fastapi import APIRouter, Depends, HTTPException, status, Response, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from fapi.db.database import get_db
from fapi.db.models import OutreachContactORM
from fapi.db.schemas import OutreachContact, OutreachContactCreate, OutreachContactUpdate
from fapi.utils.permission_gate import enforce_access

router = APIRouter(prefix="/outreach-contact", tags=["Outreach Contact"])
security = HTTPBearer()

@router.head("/")
def check_outreach_contacts_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    try:
        # Calculate a simple hash/version based on count and max updated_at
        stats = db.query(
            func.count(OutreachContactORM.id).label("count"),
            func.max(OutreachContactORM.updated_at).label("last_update")
        ).first()
        
        last_mod = f"{stats.count}:{stats.last_update}"
        
        response = Response()
        response.headers["Last-Modified"] = last_mod
        return response
    except Exception as e:
        return Response(status_code=500)

@router.get("/", response_model=List[OutreachContact])
def get_outreach_contacts(db: Session = Depends(get_db)):
    return db.query(OutreachContactORM).all()

@router.post("/", response_model=OutreachContact, status_code=status.HTTP_201_CREATED)
def create_outreach_contact(contact: OutreachContactCreate, db: Session = Depends(get_db)):
    db_contact = OutreachContactORM(**contact.model_dump())
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact

@router.put("/{contact_id}", response_model=OutreachContact)
def update_outreach_contact(contact_id: int, contact: OutreachContactUpdate, db: Session = Depends(get_db)):
    db_contact = db.query(OutreachContactORM).filter(OutreachContactORM.id == contact_id).first()
    if not db_contact:
        raise HTTPException(status_code=404, detail="Outreach Contact not found")
    
    update_data = contact.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_contact, key, value)
    
    db.commit()
    db.refresh(db_contact)
    return db_contact

@router.delete("/{contact_id}")
def delete_outreach_contact(contact_id: int, db: Session = Depends(get_db)):
    db_contact = db.query(OutreachContactORM).filter(OutreachContactORM.id == contact_id).first()
    if not db_contact:
        raise HTTPException(status_code=404, detail="Outreach Contact not found")
    db.delete(db_contact)
    db.commit()
    return {"message": "Outreach Contact deleted"}
