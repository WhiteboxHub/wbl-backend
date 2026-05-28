from sqlalchemy.orm import Session
from sqlalchemy import or_
from fapi.db.models import OutreachEmailORM
from fapi.db.schemas import OutreachEmailCreate, OutreachEmailUpdate
from typing import List, Optional
from fapi.utils.table_fingerprint import generate_version_for_model
from fastapi import Response
from fapi.core.cache import cache_result, invalidate_cache

CACHE_PREFIX = "outreach_emails"

@cache_result(ttl=300, prefix=CACHE_PREFIX)
def get_emails(db: Session, skip: int = 0, limit: Optional[int] = None) -> List[OutreachEmailORM]:
    DEFAULT_LIMIT = 5000
    MAX_LIMIT = 999999
    
    query = db.query(OutreachEmailORM).order_by(OutreachEmailORM.id.desc()).offset(skip)
    
    if limit is None:
        query = query.limit(DEFAULT_LIMIT)
    else:
        query = query.limit(min(limit, MAX_LIMIT))
        
    return query.all()

@cache_result(ttl=300, prefix=CACHE_PREFIX)
def get_email_by_id(db: Session, email_id: int) -> Optional[OutreachEmailORM]:
    return db.query(OutreachEmailORM).filter(OutreachEmailORM.id == email_id).first()

@cache_result(ttl=300, prefix=CACHE_PREFIX)
def get_email_by_address(db: Session, email: str) -> Optional[OutreachEmailORM]:
    return db.query(OutreachEmailORM).filter(OutreachEmailORM.email == email.lower().strip()).first()

def create_email(db: Session, email_data: OutreachEmailCreate) -> OutreachEmailORM:
    invalidate_cache(CACHE_PREFIX)
    db_email = OutreachEmailORM(**email_data.model_dump())
    db.add(db_email)
    db.commit()
    db.refresh(db_email)
    return db_email

def update_email(db: Session, email_id: int, email_data: OutreachEmailUpdate) -> Optional[OutreachEmailORM]:
    invalidate_cache(CACHE_PREFIX)
    db_email = db.query(OutreachEmailORM).filter(OutreachEmailORM.id == email_id).first()
    if not db_email:
        return None
    
    update_data = email_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_email, key, value)
        
    db.commit()
    db.refresh(db_email)
    return db_email

def delete_email(db: Session, email_id: int) -> bool:
    invalidate_cache(CACHE_PREFIX)
    db_email = db.query(OutreachEmailORM).filter(OutreachEmailORM.id == email_id).first()
    if not db_email:
        return False
    
    db.delete(db_email)
    db.commit()
    return True

@cache_result(ttl=300, prefix=CACHE_PREFIX)
def search_emails(db: Session, term: str) -> List[OutreachEmailORM]:
    return db.query(OutreachEmailORM).filter(
        or_(
            OutreachEmailORM.email.ilike(f"%{term}%"),
            OutreachEmailORM.status.ilike(f"%{term}%"),
            OutreachEmailORM.validation_status.ilike(f"%{term}%")
        )
    ).limit(100).all()

@cache_result(ttl=300, prefix=CACHE_PREFIX)
def count_emails(db: Session) -> int:
    return db.query(OutreachEmailORM).count()

def get_emails_version(db: Session) -> Response:
    return generate_version_for_model(db, OutreachEmailORM)
