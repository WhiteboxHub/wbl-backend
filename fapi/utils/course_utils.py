from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db import models
from fapi.db import schemas
from datetime import datetime  

def get_all_courses(db: Session) -> List[models.Course]:
    """Get all courses"""
    return db.query(models.Course).all()

def get_course_by_id(db: Session, course_id: int) -> Optional[models.Course]:
    """Get course by ID"""
    return db.query(models.Course).filter(models.Course.id == course_id).first()

def create_course(db: Session, course: schemas.CourseCreate) -> models.Course:
    """Create a new course"""
    existing_course = db.query(models.Course).filter(models.Course.alias == course.alias).first()
    if existing_course:
        raise ValueError("Course with this alias already exists")
    
    db_course = models.Course(**course.model_dump())  
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course

def update_course(db: Session, course_id: int, course: schemas.CourseUpdate) -> models.Course:
    """Update an existing course"""
    db_course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not db_course:
        raise ValueError("Course not found")
    
    if course.alias and course.alias != db_course.alias:
        existing_alias = db.query(models.Course).filter(
            models.Course.alias == course.alias,
            models.Course.id != course_id
        ).first()
        if existing_alias:
            raise ValueError("Another course with this alias already exists")
    
    for field, value in course.model_dump(exclude_unset=True).items():
        if value is not None:  
            setattr(db_course, field, value)
    
    db.commit()
    db.refresh(db_course)
    return db_course

def delete_course(db: Session, course_id: int) -> bool:
    """Delete a course"""
    db_course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not db_course:
        raise ValueError("Course not found")
    
    db.delete(db_course)
    db.commit()
    return True
