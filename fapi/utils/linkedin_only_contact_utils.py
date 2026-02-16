from sqlalchemy.orm import Session
from sqlalchemy import or_
from fapi.db.models import LinkedinOnlyContact
from fapi.db.schemas import LinkedinOnlyContactCreate, LinkedinOnlyContactUpdate
from typing import List, Optional

def get_linkedin_only_contacts(db: Session, skip: int = 0, limit: Optional[int] = None) -> List[LinkedinOnlyContact]:
    DEFAULT_LIMIT = 5000
    MAX_LIMIT = 999999
    
    query = db.query(LinkedinOnlyContact).order_by(LinkedinOnlyContact.id.desc()).offset(skip)
    
    # Apply limit with sensible defaults
    if limit is None:
        query = query.limit(DEFAULT_LIMIT)
    else:
        # Cap at MAX_LIMIT to prevent abuse
        query = query.limit(min(limit, MAX_LIMIT))
    
    return query.all()

def get_linkedin_only_contact(db: Session, contact_id: int) -> Optional[LinkedinOnlyContact]:
    return db.query(LinkedinOnlyContact).filter(LinkedinOnlyContact.id == contact_id).first()

def create_linkedin_only_contact(db: Session, contact: LinkedinOnlyContactCreate) -> LinkedinOnlyContact:
    db_contact = LinkedinOnlyContact(**contact.model_dump())
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact

def update_linkedin_only_contact(db: Session, contact_id: int, contact: LinkedinOnlyContactUpdate) -> Optional[LinkedinOnlyContact]:
    db_contact = db.query(LinkedinOnlyContact).filter(LinkedinOnlyContact.id == contact_id).first()
    if not db_contact:
        return None
    
    update_data = contact.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_contact, key, value)
    
    db.commit()
    db.refresh(db_contact)
    return db_contact

def delete_linkedin_only_contact(db: Session, contact_id: int) -> bool:
    db_contact = db.query(LinkedinOnlyContact).filter(LinkedinOnlyContact.id == contact_id).first()
    if not db_contact:
        return False
    
    db.delete(db_contact)
    db.commit()
    return True

def search_linkedin_only_contacts(db: Session, term: str) -> List[LinkedinOnlyContact]:
    return db.query(LinkedinOnlyContact).filter(
        or_(
            LinkedinOnlyContact.name.ilike(f"%{term}%"),
            LinkedinOnlyContact.job_title.ilike(f"%{term}%"),
            LinkedinOnlyContact.city.ilike(f"%{term}%"),
            LinkedinOnlyContact.country.ilike(f"%{term}%"),
            LinkedinOnlyContact.linkedin_id.ilike(f"%{term}%")
        )
    ).limit(100).all()

def count_linkedin_only_contacts(db: Session) -> int:
    """Get total count of company contacts for pagination"""
    return db.query(LinkedinOnlyContact).count()
