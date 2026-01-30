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
