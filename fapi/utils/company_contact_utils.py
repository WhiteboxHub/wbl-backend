from sqlalchemy.orm import Session
from sqlalchemy import or_
from fapi.db.models import CompanyContact
from fapi.db.schemas import CompanyContactCreate, CompanyContactUpdate
from typing import List, Optional

def get_company_contacts(db: Session, skip: int = 0, limit: Optional[int] = None) -> List[CompanyContact]:
    DEFAULT_LIMIT = 5000
    MAX_LIMIT = 999999
    
    query = db.query(CompanyContact).order_by(CompanyContact.id.desc()).offset(skip)
    
    # Apply limit with sensible defaults
    if limit is None:
        query = query.limit(DEFAULT_LIMIT)
    else:
        # Cap at MAX_LIMIT to prevent abuse
        query = query.limit(min(limit, MAX_LIMIT))
    
    return query.all()

def get_company_contact(db: Session, contact_id: int) -> Optional[CompanyContact]:
    return db.query(CompanyContact).filter(CompanyContact.id == contact_id).first()

def create_company_contact(db: Session, contact: CompanyContactCreate) -> CompanyContact:
    db_contact = CompanyContact(**contact.model_dump())
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact

def update_company_contact(db: Session, contact_id: int, contact: CompanyContactUpdate) -> Optional[CompanyContact]:
    db_contact = db.query(CompanyContact).filter(CompanyContact.id == contact_id).first()
    if not db_contact:
        return None
    
    update_data = contact.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_contact, key, value)
    
    db.commit()
    db.refresh(db_contact)
    return db_contact

def delete_company_contact(db: Session, contact_id: int) -> bool:
    db_contact = db.query(CompanyContact).filter(CompanyContact.id == contact_id).first()
    if not db_contact:
        return False
    
    db.delete(db_contact)
    db.commit()
    return True

def search_company_contacts(db: Session, term: str) -> List[CompanyContact]:
    return db.query(CompanyContact).filter(
        or_(
            CompanyContact.name.ilike(f"%{term}%"),
            CompanyContact.email.ilike(f"%{term}%"),
            CompanyContact.job_title.ilike(f"%{term}%")
        )
    ).limit(100).all()

def get_contacts_by_company(db: Session, company_id: int) -> List[CompanyContact]:
    return db.query(CompanyContact).filter(CompanyContact.company_id == company_id).all()

def count_company_contacts(db: Session) -> int:
    """Get total count of company contacts for pagination"""
    return db.query(CompanyContact).count()
