from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db import models
from fapi.db import schemas

def get_all_subjects(db: Session) -> List[models.Subject]:
    """Get all subjects"""
    return db.query(models.Subject).all()

def get_subject_by_id(db: Session, subject_id: int) -> Optional[models.Subject]:
    """Get subject by ID"""
    return db.query(models.Subject).filter(models.Subject.id == subject_id).first()

def create_subject(db: Session, subject: schemas.SubjectCreate) -> models.Subject:
    """Create a new subject"""
    existing_subject = db.query(models.Subject).filter(models.Subject.name == subject.name).first()
    if existing_subject:
        raise ValueError("Subject with this name already exists")
    
    db_subject = models.Subject(**subject.model_dump())
    db.add(db_subject)
    db.commit()
    db.refresh(db_subject)
    return db_subject

def update_subject(db: Session, subject_id: int, subject: schemas.SubjectCreate) -> models.Subject:
    """Update an existing subject"""
    db_subject = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
    if not db_subject:
        raise ValueError("Subject not found")
    
    if subject.name != db_subject.name:
        existing_name = db.query(models.Subject).filter(
            models.Subject.name == subject.name,
            models.Subject.id != subject_id
        ).first()
        if existing_name:
            raise ValueError("Another subject with this name already exists")
    
    for field, value in subject.model_dump().items():
        setattr(db_subject, field, value)
    
    db.commit()
    db.refresh(db_subject)
    return db_subject

def delete_subject(db: Session, subject_id: int) -> bool:
    """Delete a subject"""
    db_subject = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
    if not db_subject:
        raise ValueError("Subject not found")
    
    db.delete(db_subject)
    db.commit()
    return True
