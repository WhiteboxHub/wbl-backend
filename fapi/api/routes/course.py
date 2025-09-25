from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db import schemas
from fapi.utils import course_utils

router = APIRouter()

security = HTTPBearer()

@router.get("/courses", response_model=List[schemas.CourseResponse])
def get_courses(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    courses = course_utils.get_all_courses(db)
    return courses

@router.get("/courses/{course_id}", response_model=schemas.CourseResponse)
def get_course(
    course_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    course = course_utils.get_course_by_id(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.post("/courses", response_model=schemas.CourseResponse)
def create_course(course: schemas.CourseCreate, db: Session = Depends(get_db)):
    try:
        db_course = course_utils.create_course(db, course)
        return db_course
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.put("/courses/{course_id}", response_model=schemas.CourseResponse) 
def update_course(course_id: int, course: schemas.CourseUpdate, db: Session = Depends(get_db)):
    try:
        db_course = course_utils.update_course(db, course_id, course)
        return db_course
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.delete("/courses/{course_id}")
def delete_course(course_id: int, db: Session = Depends(get_db)):
    try:
        course_utils.delete_course(db, course_id)
        return {"status": "success", "message": "Course deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

