import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from fapi.db.models import EmailSenderEngineORM
from fapi.db import schemas

logger = logging.getLogger(__name__)

def get_all_engines(db: Session, skip: int = 0, limit: int = 100, search: Optional[str] = None) -> List[EmailSenderEngineORM]:
    """Get all email engines with optional search"""
    query = db.query(EmailSenderEngineORM)
    
    if search:
        query = query.filter(
            (EmailSenderEngineORM.engine_name.contains(search)) |
            (EmailSenderEngineORM.provider.contains(search))
        )
    
    return query.order_by(EmailSenderEngineORM.priority.asc()).offset(skip).limit(limit).all()

def get_engine_by_id(db: Session, engine_id: int) -> EmailSenderEngineORM:
    """Get an engine by ID"""
    engine = db.query(EmailSenderEngineORM).filter(EmailSenderEngineORM.id == engine_id).first()
    if not engine:
        raise HTTPException(status_code=404, detail="Email engine not found")
    return engine

def create_engine(db: Session, engine: schemas.EmailSenderEngineCreate) -> EmailSenderEngineORM:
    """Create a new email engine"""
    try:
        db_engine = EmailSenderEngineORM(**engine.model_dump())
        db.add(db_engine)
        db.commit()
        db.refresh(db_engine)
        return db_engine
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating email engine: {e}")
        raise HTTPException(status_code=400, detail=f"Error creating email engine: {str(e)}")

def update_engine(db: Session, engine_id: int, engine_update: schemas.EmailSenderEngineUpdate) -> EmailSenderEngineORM:
    """Update an existing email engine"""
    db_engine = get_engine_by_id(db, engine_id)
    
    update_data = engine_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_engine, key, value)
    
    try:
        db.commit()
        db.refresh(db_engine)
        return db_engine
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating email engine: {e}")
        raise HTTPException(status_code=400, detail=f"Error updating email engine: {str(e)}")

def delete_engine(db: Session, engine_id: int) -> bool:
    """Delete an email engine"""
    db_engine = get_engine_by_id(db, engine_id)
    try:
        db.delete(db_engine)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting email engine: {e}")
        raise HTTPException(status_code=400, detail=f"Error deleting email engine: {str(e)}")
