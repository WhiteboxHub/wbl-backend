from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db import models
from fapi.db import schemas

def get_all_course_contents(db: Session) -> List[models.CourseContent]:
    """Get all course contents"""
    return db.query(models.CourseContent).all()

def get_course_content(db: Session, content_id: int) -> Optional[models.CourseContent]:
    """Get a specific course content by ID"""
    return db.query(models.CourseContent).filter(models.CourseContent.id == content_id).first()

def create_course_content(db: Session, course_content: schemas.CourseContentCreate) -> models.CourseContent:
    """Create a new course content"""
    if not course_content.AIML:
        raise ValueError("AIML field is required")
    
    db_course_content = models.CourseContent(
        Fundamentals=course_content.Fundamentals,
        AIML=course_content.AIML,
        UI=course_content.UI,
        QE=course_content.QE
    )
    
    db.add(db_course_content)
    db.commit()
    db.refresh(db_course_content)
    return db_course_content

def update_course_content(
    db: Session, 
    content_id: int, 
    course_content_update: schemas.CourseContentUpdate
) -> models.CourseContent:
    """Update a course content"""
    db_course_content = get_course_content(db, content_id)
    if not db_course_content:
        raise ValueError("Course content not found")
    
    update_data = course_content_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(db_course_content, field, value)
    
    db.add(db_course_content)
    db.commit()
    db.refresh(db_course_content)
    return db_course_content

def delete_course_content(db: Session, content_id: int) -> bool:
    """Delete a course content"""
    course_content = get_course_content(db, content_id)
    if not course_content:
        raise ValueError("Course content not found")
    
    db.delete(course_content)
    db.commit()
    return True
