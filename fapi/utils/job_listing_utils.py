from sqlalchemy.orm import Session
from sqlalchemy import or_
from fapi.db.models import JobListingORM
from fapi.db.schemas import JobListingCreate, JobListingUpdate
from typing import List, Optional

def get_positions(db: Session, skip: int = 0, limit: Optional[int] = None) -> List[JobListingORM]:
    DEFAULT_LIMIT = 5000
    MAX_LIMIT = 999999 
    
    query = db.query(JobListingORM).order_by(JobListingORM.id.desc()).offset(skip)
    if limit is None:
        query = query.limit(DEFAULT_LIMIT)
    else:
        query = query.limit(min(limit, MAX_LIMIT))
    
    return query.all()

def get_position(db: Session, position_id: int) -> Optional[JobListingORM]:
    return db.query(JobListingORM).filter(JobListingORM.id == position_id).first()

def create_position(db: Session, position: JobListingCreate) -> JobListingORM:
    db_position = JobListingORM(**position.model_dump())
    db.add(db_position)
    db.commit()
    db.refresh(db_position)
    return db_position

def update_position(db: Session, position_id: int, position: JobListingUpdate) -> Optional[JobListingORM]:
    db_position = db.query(JobListingORM).filter(JobListingORM.id == position_id).first()
    if not db_position:
        return None
    
    update_data = position.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_position, key, value)
    
    db.commit()
    db.refresh(db_position)
    return db_position

def delete_position(db: Session, position_id: int) -> bool:
    db_position = db.query(JobListingORM).filter(JobListingORM.id == position_id).first()
    if not db_position:
        return False
    
    db.delete(db_position)
    db.commit()
    return True

def search_positions(db: Session, term: str) -> List[JobListingORM]:
    return db.query(JobListingORM).filter(
        or_(
            JobListingORM.title.ilike(f"%{term}%"),
            JobListingORM.company_name.ilike(f"%{term}%")
        )
    ).limit(100).all()

def count_positions(db: Session) -> int:
    """Get total count of job listings for pagination"""
    return db.query(JobListingORM).count()
