from sqlalchemy.orm import Session
from sqlalchemy import or_
from fapi.db.models import OutreachEmailRecipient
from fapi.db.schemas import OutreachEmailRecipientCreate, OutreachEmailRecipientUpdate
from typing import List, Optional

def get_recipients(db: Session, skip: int = 0, limit: Optional[int] = None) -> List[OutreachEmailRecipient]:
    DEFAULT_LIMIT = 5000
    MAX_LIMIT = 999999
    
    query = db.query(OutreachEmailRecipient).order_by(OutreachEmailRecipient.id.desc()).offset(skip)
    
    if limit is None:
        query = query.limit(DEFAULT_LIMIT)
    else:
        query = query.limit(min(limit, MAX_LIMIT))
    
    return query.all()

def get_recipient(db: Session, recipient_id: int) -> Optional[OutreachEmailRecipient]:
    return db.query(OutreachEmailRecipient).filter(OutreachEmailRecipient.id == recipient_id).first()

def create_recipient(db: Session, recipient: OutreachEmailRecipientCreate) -> OutreachEmailRecipient:
    db_recipient = OutreachEmailRecipient(**recipient.model_dump())
    db.add(db_recipient)
    db.commit()
    db.refresh(db_recipient)
    return db_recipient

def update_recipient(db: Session, recipient_id: int, recipient: OutreachEmailRecipientUpdate) -> Optional[OutreachEmailRecipient]:
    db_recipient = db.query(OutreachEmailRecipient).filter(OutreachEmailRecipient.id == recipient_id).first()
    if not db_recipient:
        return None
    
    update_data = recipient.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_recipient, key, value)
    
    db.commit()
    db.refresh(db_recipient)
    return db_recipient

def delete_recipient(db: Session, recipient_id: int) -> bool:
    db_recipient = db.query(OutreachEmailRecipient).filter(OutreachEmailRecipient.id == recipient_id).first()
    if not db_recipient:
        return False
    
    db.delete(db_recipient)
    db.commit()
    return True

def search_recipients(db: Session, term: str) -> List[OutreachEmailRecipient]:
    return db.query(OutreachEmailRecipient).filter(
        or_(
            OutreachEmailRecipient.email.ilike(f"%{term}%"),
            OutreachEmailRecipient.source_type.ilike(f"%{term}%"),
            OutreachEmailRecipient.status.ilike(f"%{term}%")
        )
    ).limit(100).all()

def count_recipients(db: Session) -> int:
    return db.query(OutreachEmailRecipient).count()
