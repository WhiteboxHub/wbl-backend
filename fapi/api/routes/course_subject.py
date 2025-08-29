from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from fapi.db.database import get_db
from fapi.db import schemas
from fapi.utils import course_subject_utils

router = APIRouter()

@router.get("/course-subjects", response_model=List[schemas.CourseSubjectResponse])
def get_course_subjects(db: Session = Depends(get_db)):
    course_subjects = course_subject_utils.get_all_course_subjects(db)
    return course_subjects

@router.post("/course-subjects", response_model=schemas.CourseSubjectResponse)
def create_course_subject(course_subject: schemas.CourseSubjectCreate, db: Session = Depends(get_db)):
    try:
        db_course_subject = course_subject_utils.create_course_subject(db, course_subject)
        return db_course_subject
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

@router.put("/course-subjects", response_model=schemas.CourseSubjectResponse)
def update_course_subject(
    course_subject_update: schemas.CourseSubjectUpdate,  # Only request body
    db: Session = Depends(get_db)
):
    """
    Update the lastmoddatetime of a course-subject relationship.
    If no datetime is provided, uses current time.
    """
    try:
        updated_relationship = course_subject_utils.update_course_subject(
            db, 
            course_subject_update.course_id, 
            course_subject_update.subject_id, 
            course_subject_update
        )
        return updated_relationship
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))  
    

# @router.delete("/course-subjects")
# def delete_course_subject(course_id: int, subject_id: int, db: Session = Depends(get_db)):
#     try:
#         course_subject_utils.delete_course_subject(db, course_id, subject_id)
#         return {"status": "success", "message": "Course-Subject relationship deleted successfully"}
#     except ValueError as e:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    
# Change from query params to path parameters
@router.delete("/course-subjects/{course_id}/{subject_id}")
def delete_course_subject(course_id: int, subject_id: int, db: Session = Depends(get_db)):
    try:
        course_subject_utils.delete_course_subject(db, course_id, subject_id)
        return {"status": "success", "message": "Course-Subject relationship deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))