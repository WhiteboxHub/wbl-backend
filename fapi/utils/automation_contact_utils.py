import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException

from fapi.db.models import AutomationContactExtractORM
from fapi.db.schemas import (
    AutomationContactExtractCreate, 
    AutomationContactExtractUpdate,
    ContactProcessingStatusEnum
)

logger = logging.getLogger(__name__)

async def get_all_automation_extracts(db: Session, status: Optional[str] = None, source_email: Optional[str] = None) -> List[AutomationContactExtractORM]:
    try:
        query = db.query(AutomationContactExtractORM)
        if status:
            query = query.filter(AutomationContactExtractORM.processing_status == status)
        if source_email:
            query = query.filter(AutomationContactExtractORM.source_reference == source_email)
        return query.order_by(AutomationContactExtractORM.id.desc()).all()
    except SQLAlchemyError as e:
        logger.error(f"Error fetching automation extracts: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching automation extracts")

def count_automation_extracts(db: Session, status: Optional[str] = None) -> int:
    try:
        query = db.query(AutomationContactExtractORM)
        if status:
            query = query.filter(AutomationContactExtractORM.processing_status == status)
        return query.count()
    except SQLAlchemyError as e:
        logger.error(f"Error counting automation extracts: {str(e)}")
        raise HTTPException(status_code=500, detail="Error counting automation extracts")

def get_automation_extracts_paginated(db: Session, skip: int = 0, limit: int = 100, status: Optional[str] = None) -> List[AutomationContactExtractORM]:
    try:
        query = db.query(AutomationContactExtractORM)
        if status:
            query = query.filter(AutomationContactExtractORM.processing_status == status)
        return query.order_by(AutomationContactExtractORM.id.desc()).offset(skip).limit(limit).all()
    except SQLAlchemyError as e:
        logger.error(f"Error fetching paginated automation extracts: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching paginated automation extracts")

async def get_automation_extract_by_id(extract_id: int, db: Session) -> AutomationContactExtractORM:
    extract = db.query(AutomationContactExtractORM).filter(AutomationContactExtractORM.id == extract_id).first()
    if not extract:
        raise HTTPException(status_code=404, detail="Automation extract not found")
    return extract

async def insert_automation_extract(extract: AutomationContactExtractCreate, db: Session) -> AutomationContactExtractORM:
    try:
        db_extract = AutomationContactExtractORM(**extract.dict())
        db.add(db_extract)
        db.commit()
        db.refresh(db_extract)
        return db_extract
    except Exception as e:
        db.rollback()
        logger.error(f"Insert error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Insert error: {str(e)}")

async def update_automation_extract(extract_id: int, update_data: AutomationContactExtractUpdate, db: Session) -> AutomationContactExtractORM:
    db_extract = await get_automation_extract_by_id(extract_id, db)
    try:
        update_fields = update_data.dict(exclude_unset=True)
        for field, value in update_fields.items():
            setattr(db_extract, field, value)
        
        db.commit()
        db.refresh(db_extract)
        return db_extract
    except Exception as e:
        db.rollback()
        logger.error(f"Update error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Update error: {str(e)}")

async def delete_automation_extract(extract_id: int, db: Session) -> dict:
    db_extract = await get_automation_extract_by_id(extract_id, db)
    try:
        db.delete(db_extract)
        db.commit()
        return {"message": f"Automation extract {extract_id} deleted successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Delete error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Delete error: {str(e)}")

async def insert_automation_extracts_bulk(extracts: List[AutomationContactExtractCreate], db: Session) -> dict:
    inserted = 0
    failed = 0
    duplicates = 0
    errors = []
    
    for ext in extracts:
        try:
            with db.begin_nested():
                db_extract = AutomationContactExtractORM(**ext.dict())
                db.add(db_extract)
                db.flush()
            inserted += 1
        except IntegrityError:
            duplicates += 1
        except Exception as e:
            failed += 1
            errors.append({"full_name": ext.full_name, "email": ext.email, "error": str(e)})
            logger.error(f"Failed to insert extract {ext.full_name}: {str(e)}")
            
    db.commit()
    return {
        "total": len(extracts),
        "inserted": inserted,
        "duplicates": duplicates,
        "failed": failed,
        "errors": errors
    }

async def delete_automation_extracts_bulk(extract_ids: List[int], db: Session) -> dict:
    try:
        deleted_count = db.query(AutomationContactExtractORM).filter(
            AutomationContactExtractORM.id.in_(extract_ids)
        ).delete(synchronize_session=False)
        db.commit()
        return {"deleted": deleted_count, "message": f"Successfully deleted {deleted_count} extracts"}
    except Exception as e:
        db.rollback()
        logger.error(f"Bulk delete error: {str(e)}")
        raise HTTPException(status_code=500, detail="Bulk delete error")

async def check_existing_emails_bulk(emails: List[str], db: Session) -> List[str]:
    """Check which of the provided emails already exist in the extract table"""
    if not emails:
        return []
    try:
        normalized = [e.strip().lower() for e in emails if e]
        rows = (
            db.query(AutomationContactExtractORM.email)
            .filter(AutomationContactExtractORM.email.in_(normalized))
            .all()
        )
        return [row[0].strip().lower() for row in rows if row[0]]
    except Exception as e:
        logger.error(f"Bulk email check failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Bulk email check failed")
