from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from fapi.db import models
from fapi.db import schemas

def get_all_course_subjects(db: Session) -> List[models.CourseSubject]:
    """Get all course-subject relationships"""
    return db.query(models.CourseSubject).all()

def create_course_subject(db: Session, course_subject: schemas.CourseSubjectCreate) -> models.CourseSubject:
    """Create a new course-subject relationship"""
    course_exists = db.query(models.Course.id).filter(models.Course.id == course_subject.course_id).first()
    subject_exists = db.query(models.Subject.id).filter(models.Subject.id == course_subject.subject_id).first()
    
    if not course_exists:
        raise ValueError("Course not found")
    if not subject_exists:
        raise ValueError("Subject not found")
    
    existing = db.query(models.CourseSubject).filter(
        models.CourseSubject.course_id == course_subject.course_id,
        models.CourseSubject.subject_id == course_subject.subject_id
    ).first()
    
    if existing:
        raise ValueError("This course-subject relationship already exists")
    
    db_course_subject = models.CourseSubject(
        course_id=course_subject.course_id,
        subject_id=course_subject.subject_id,
        lastmoddatetime=datetime.now()
    )
    db.add(db_course_subject)
    db.commit()
    db.refresh(db_course_subject)
    return db_course_subject

def update_course_subject(
    db: Session, 
    course_id: int, 
    subject_id: int, 
    course_subject_update: schemas.CourseSubjectUpdate
) -> models.CourseSubject:
    """
    Update a course-subject relationship's lastmoddatetime.
    """
    db_course_subject = db.query(models.CourseSubject).filter(
        models.CourseSubject.course_id == course_id,
        models.CourseSubject.subject_id == subject_id
    ).first()
    
    if not db_course_subject:
        raise ValueError("Course-Subject relationship not found")
    
    update_data = course_subject_update.model_dump(exclude_unset=True)
    
    if not update_data.get('lastmoddatetime'):
        update_data['lastmoddatetime'] = datetime.now()
    
    for field, value in update_data.items():
        setattr(db_course_subject, field, value)
    
    db.add(db_course_subject)
    db.commit()
    db.refresh(db_course_subject)
    
    return db_course_subject

def delete_course_subject(db: Session, course_id: int, subject_id: int) -> bool:
    """Delete a course-subject relationship"""
    course_subject = db.query(models.CourseSubject).filter(
        models.CourseSubject.course_id == course_id,
        models.CourseSubject.subject_id == subject_id
    ).first()
    
    if not course_subject:
        raise ValueError("Course-Subject relationship not found")
    
    db.delete(course_subject)
    db.commit()
    return True
