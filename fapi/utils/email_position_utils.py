from sqlalchemy.orm import Session
from sqlalchemy import or_
from fapi.db.models import EmailPositionORM
from fapi.db.schemas import EmailPositionCreate, EmailPositionUpdate
from typing import List, Optional
from fapi.utils.table_fingerprint import generate_version_for_model
from fastapi import Response

def get_email_positions(db: Session, skip: int = 0, limit: Optional[int] = None) -> List[EmailPositionORM]:
    DEFAULT_LIMIT = 5000
    MAX_LIMIT = 999999 
    
    query = db.query(EmailPositionORM).order_by(EmailPositionORM.id.desc()).offset(skip)
    if limit is None:
        query = query.limit(DEFAULT_LIMIT)
    else:
        query = query.limit(min(limit, MAX_LIMIT))
    
    return query.all()

def get_email_position(db: Session, email_position_id: int) -> Optional[EmailPositionORM]:
    return db.query(EmailPositionORM).filter(EmailPositionORM.id == email_position_id).first()

def create_email_position(db: Session, email_position: EmailPositionCreate) -> EmailPositionORM:
    db_email_position = EmailPositionORM(**email_position.model_dump())
    db.add(db_email_position)
    db.commit()
    db.refresh(db_email_position)
    return db_email_position

def update_email_position(db: Session, email_position_id: int, email_position: EmailPositionUpdate) -> Optional[EmailPositionORM]:
    db_email_position = db.query(EmailPositionORM).filter(EmailPositionORM.id == email_position_id).first()
    if not db_email_position:
        return None
    
    update_data = email_position.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_email_position, key, value)
    
    db.commit()
    db.refresh(db_email_position)
    return db_email_position

def delete_email_position(db: Session, email_position_id: int) -> bool:
    db_email_position = db.query(EmailPositionORM).filter(EmailPositionORM.id == email_position_id).first()
    if not db_email_position:
        return False
    
    db.delete(db_email_position)
    db.commit()
    return True

def search_email_positions(db: Session, term: str) -> List[EmailPositionORM]:
    return db.query(EmailPositionORM).filter(
        or_(
            EmailPositionORM.title.ilike(f"%{term}%"),
            EmailPositionORM.company.ilike(f"%{term}%"),
            EmailPositionORM.location.ilike(f"%{term}%"),
            EmailPositionORM.source_uid.ilike(f"%{term}%")
        )
    ).limit(100).all()

def count_email_positions(db: Session) -> int:
    """Get total count of email positions for pagination"""
    return db.query(EmailPositionORM).count()

async def insert_email_positions_bulk(positions: List[EmailPositionCreate], db: Session) -> dict:
    """Bulk insert email positions with duplicate handling"""
    inserted = 0
    failed = 0
    duplicates = 0
    failed_contacts = []
    
    try:
        for pos_data in positions:
            try:
                # Check for duplicates by source and source_uid
                existing = None
                if pos_data.source_uid:
                    existing = db.query(EmailPositionORM).filter(
                        EmailPositionORM.source == pos_data.source,
                        EmailPositionORM.source_uid == pos_data.source_uid
                    ).first()
                
                if existing:
                    duplicates += 1
                    continue
                
                # Insert new position
                db_pos = EmailPositionORM(**pos_data.model_dump())
                db.add(db_pos)
                inserted += 1
                
                # Flush every 100 records to keep memory low
                if inserted % 100 == 0:
                    db.flush()
                    
            except Exception as e:
                failed += 1
                failed_contacts.append({
                    "source_uid": pos_data.source_uid,
                    "reason": str(e)
                })
        
        db.commit()
        
        return {
            "inserted": inserted,
            "skipped": duplicates,
            "total": len(positions),
            "failed_contacts": failed_contacts
        }
        
    except Exception as e:
        db.rollback()
        raise e

def get_email_positions_version(db: Session) -> Response:
    return generate_version_for_model(db, EmailPositionORM)
