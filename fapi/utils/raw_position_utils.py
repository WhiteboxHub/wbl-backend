from sqlalchemy.orm import Session
from fapi.db.models import RawPositionORM
from fapi.db.schemas import RawPositionCreate, RawPositionUpdate
from typing import List, Optional

def get_raw_positions(db: Session, skip: int = 0, limit: int = 100) -> List[RawPositionORM]:
    return db.query(RawPositionORM).offset(skip).limit(limit).all()

def get_raw_position(db: Session, raw_position_id: int) -> Optional[RawPositionORM]:
    return db.query(RawPositionORM).filter(RawPositionORM.id == raw_position_id).first()

def create_raw_position(db: Session, raw_position: RawPositionCreate) -> RawPositionORM:
    db_raw_position = RawPositionORM(**raw_position.model_dump())
    db.add(db_raw_position)
    db.commit()
    db.refresh(db_raw_position)
    return db_raw_position

def update_raw_position(db: Session, raw_position_id: int, raw_position: RawPositionUpdate) -> Optional[RawPositionORM]:
    db_raw_position = db.query(RawPositionORM).filter(RawPositionORM.id == raw_position_id).first()
    if not db_raw_position:
        return None
    
    update_data = raw_position.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_raw_position, key, value)
    
    db.commit()
    db.refresh(db_raw_position)
    return db_raw_position

def delete_raw_position(db: Session, raw_position_id: int) -> bool:
    db_raw_position = db.query(RawPositionORM).filter(RawPositionORM.id == raw_position_id).first()
    if not db_raw_position:
        return False
    
    db.delete(db_raw_position)
    db.commit()
    return True

async def insert_raw_positions_bulk(positions: List[RawPositionCreate], db: Session) -> dict:
    """Bulk insert raw positions with duplicate handling"""
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
                    existing = db.query(RawPositionORM).filter(
                        RawPositionORM.source == pos_data.source,
                        RawPositionORM.source_uid == pos_data.source_uid
                    ).first()
                
                if existing:
                    duplicates += 1
                    continue
                
                # Insert new position
                db_pos = RawPositionORM(**pos_data.model_dump())
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
