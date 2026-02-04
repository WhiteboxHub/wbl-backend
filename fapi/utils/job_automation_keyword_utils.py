from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from typing import Optional, List
from fapi.db import models, schemas


def get_keyword(db: Session, keyword_id: int) -> Optional[models.JobAutomationKeywordORM]:
    """Get a single keyword by ID"""
    return db.query(models.JobAutomationKeywordORM).filter(
        models.JobAutomationKeywordORM.id == keyword_id
    ).first()


def get_keywords(
    db: Session,
    category: Optional[str] = None,
    source: Optional[str] = None,
    is_active: Optional[bool] = None,
    action: Optional[str] = None
) -> tuple[List[models.JobAutomationKeywordORM], int]:
    """Get keywords with optional filtering"""
    query = db.query(models.JobAutomationKeywordORM)
    
    # Apply filters
    if category:
        query = query.filter(models.JobAutomationKeywordORM.category == category)
    if source:
        query = query.filter(models.JobAutomationKeywordORM.source == source)
    if is_active is not None:
        query = query.filter(models.JobAutomationKeywordORM.is_active == is_active)
    if action:
        query = query.filter(models.JobAutomationKeywordORM.action == action)
    
    # Get total count
    total = query.count()
    
    # Apply ordering
    keywords = query.order_by(
        asc(models.JobAutomationKeywordORM.priority),
        desc(models.JobAutomationKeywordORM.created_at)
    ).all()
    
    return keywords, total


def create_keyword(
    db: Session,
    keyword: schemas.JobAutomationKeywordCreate
) -> models.JobAutomationKeywordORM:
    """Create a new keyword"""
    db_keyword = models.JobAutomationKeywordORM(**keyword.model_dump())
    db.add(db_keyword)
    db.commit()
    db.refresh(db_keyword)
    return db_keyword


def update_keyword(
    db: Session,
    keyword_id: int,
    keyword_update: schemas.JobAutomationKeywordUpdate
) -> Optional[models.JobAutomationKeywordORM]:
    """Update an existing keyword"""
    db_keyword = get_keyword(db, keyword_id)
    if not db_keyword:
        return None
    
    update_data = keyword_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_keyword, field, value)
    
    db.commit()
    db.refresh(db_keyword)
    return db_keyword


def delete_keyword(db: Session, keyword_id: int) -> bool:
    """Delete a keyword"""
    db_keyword = get_keyword(db, keyword_id)
    if not db_keyword:
        return False
    
    db.delete(db_keyword)
    db.commit()
    return True


def get_active_keywords_by_category(
    db: Session,
    category: str,
    source: Optional[str] = None
) -> List[models.JobAutomationKeywordORM]:
    """Get all active keywords for a specific category, ordered by priority"""
    query = db.query(models.JobAutomationKeywordORM).filter(
        models.JobAutomationKeywordORM.category == category,
        models.JobAutomationKeywordORM.is_active == True
    )
    
    if source:
        query = query.filter(models.JobAutomationKeywordORM.source == source)
    
    return query.order_by(asc(models.JobAutomationKeywordORM.priority)).all()
