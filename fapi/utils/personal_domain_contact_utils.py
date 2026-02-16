from sqlalchemy.orm import Session
from sqlalchemy import or_
from fapi.db.models import PersonalDomainContact
from fapi.db.schemas import PersonalDomainContactCreate, PersonalDomainContactUpdate
from typing import List, Optional

def get_personal_domain_contacts(db: Session, skip: int = 0, limit: Optional[int] = None) -> List[PersonalDomainContact]:
    DEFAULT_LIMIT = 5000
    MAX_LIMIT = 999999
    
    query = db.query(PersonalDomainContact).order_by(PersonalDomainContact.id.desc()).offset(skip)
    
    if limit is None:
        query = query.limit(DEFAULT_LIMIT)
    else:
        query = query.limit(min(limit, MAX_LIMIT))
    
    return query.all()

def get_personal_domain_contact(db: Session, contact_id: int) -> Optional[PersonalDomainContact]:
    return db.query(PersonalDomainContact).filter(PersonalDomainContact.id == contact_id).first()

def create_personal_domain_contact(db: Session, contact: PersonalDomainContactCreate) -> PersonalDomainContact:
    db_contact = PersonalDomainContact(**contact.model_dump())
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact

def update_personal_domain_contact(db: Session, contact_id: int, contact: PersonalDomainContactUpdate) -> Optional[PersonalDomainContact]:
    db_contact = db.query(PersonalDomainContact).filter(PersonalDomainContact.id == contact_id).first()
    if not db_contact:
        return None
    
    update_data = contact.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_contact, key, value)
    
    db.commit()
    db.refresh(db_contact)
    return db_contact

def delete_personal_domain_contact(db: Session, contact_id: int) -> bool:
    db_contact = db.query(PersonalDomainContact).filter(PersonalDomainContact.id == contact_id).first()
    if not db_contact:
        return False
    
    db.delete(db_contact)
    db.commit()
    return True

def search_personal_domain_contacts(db: Session, term: str) -> List[PersonalDomainContact]:
    return db.query(PersonalDomainContact).filter(
        or_(
            PersonalDomainContact.name.ilike(f"%{term}%"),
            PersonalDomainContact.email.ilike(f"%{term}%"),
            PersonalDomainContact.job_title.ilike(f"%{term}%"),
            PersonalDomainContact.city.ilike(f"%{term}%")
        )
    ).limit(100).all()

def count_personal_domain_contacts(db: Session) -> int:
    return db.query(PersonalDomainContact).count()
