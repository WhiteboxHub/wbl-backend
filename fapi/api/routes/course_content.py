from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from fapi.db.database import get_db
from fapi.db import schemas
from fapi.utils import course_content_utils

router = APIRouter()

# 1. GET ALL - Return all course contents
@router.get("/", response_model=List[schemas.CourseContentResponse])
def get_all_course_contents(db: Session = Depends(get_db)):
    course_contents = course_content_utils.get_all_course_contents(db)
    return course_contents

# 2. GET by ID - Return specific course content (FIXED FUNCTION NAME)
@router.get("/{content_id}", response_model=schemas.CourseContentResponse)
def get_course_content_by_id(content_id: int, db: Session = Depends(get_db)):  # ← CHANGED FUNCTION NAME
    course_content = course_content_utils.get_course_content(db, content_id)
    if not course_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course content not found"
        )
    return course_content

# 3. POST - Create a new course content
@router.post("/", response_model=schemas.CourseContentResponse, status_code=status.HTTP_201_CREATED)
def create_course_content(course_content: schemas.CourseContentCreate, db: Session = Depends(get_db)):
    try:
        db_course_content = course_content_utils.create_course_content(db, course_content)
        return db_course_content
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

# 4. PUT - Update a course content
@router.put("/{content_id}", response_model=schemas.CourseContentResponse)
def update_course_content(
    content_id: int, 
    course_content_update: schemas.CourseContentUpdate, 
    db: Session = Depends(get_db)
):
    """
    Update a course content
    """
    try:
        updated_content = course_content_utils.update_course_content(
            db, content_id, course_content_update
        )
        return updated_content
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

# 5. DELETE - Remove a course content
@router.delete("/{content_id}")
def delete_course_content(content_id: int, db: Session = Depends(get_db)):
    try:
        course_content_utils.delete_course_content(db, content_id)
        return {"status": "success", "message": "Course content deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    
    