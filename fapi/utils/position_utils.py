from sqlalchemy.orm import Session
from sqlalchemy import or_
from fapi.db.models import PositionORM
from fapi.db.schemas import PositionCreate, PositionUpdate
from typing import List, Optional

def get_positions(db: Session, skip: int = 0, limit: int = 100) -> List[PositionORM]:
    return db.query(PositionORM).order_by(PositionORM.id.desc()).offset(skip).limit(limit).all()

def get_position(db: Session, position_id: int) -> Optional[PositionORM]:
    return db.query(PositionORM).filter(PositionORM.id == position_id).first()

def create_position(db: Session, position: PositionCreate) -> PositionORM:
    db_position = PositionORM(**position.model_dump())
    db.add(db_position)
    db.commit()
    db.refresh(db_position)
    return db_position

def update_position(db: Session, position_id: int, position: PositionUpdate) -> Optional[PositionORM]:
    db_position = db.query(PositionORM).filter(PositionORM.id == position_id).first()
    if not db_position:
        return None
    
    update_data = position.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_position, key, value)
    
    db.commit()
    db.refresh(db_position)
    return db_position

def delete_position(db: Session, position_id: int) -> bool:
    db_position = db.query(PositionORM).filter(PositionORM.id == position_id).first()
    if not db_position:
        return False
    
    db.delete(db_position)
    db.commit()
    return True

def search_positions(db: Session, term: str) -> List[PositionORM]:
    return db.query(PositionORM).filter(
        or_(
            PositionORM.title.ilike(f"%{term}%"),
            PositionORM.company_name.ilike(f"%{term}%")
        )
    ).limit(20).all()
