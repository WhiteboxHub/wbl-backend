from fastapi import APIRouter, Depends, HTTPException, Security, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from fapi.db.database import get_db
from fapi.utils.table_fingerprint import generate_version_for_model
from fapi.db import schemas, models
from fapi.utils import course_utils
import hashlib

router = APIRouter()

security = HTTPBearer()

@router.head("/courses")
def check_courses_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    try:
        result = db.query(
            func.count().label("cnt"),
            func.max(models.Course.id).label("max_id"),
            func.sum(
                func.crc32(
                    func.concat_ws(
                        '|',
                        models.Course.id,
                        func.coalesce(models.Course.name, ''),
                        func.coalesce(models.Course.alias, ''),
                        func.coalesce(models.Course.description, '')
                    )
                )
            ).label("checksum")
        ).first()

        response = Response(status_code=200)
        if result and result.cnt > 0:
            fingerprint = f"{result.cnt}|{result.max_id}|{result.checksum}"
            version_hash = hashlib.md5(fingerprint.encode()).hexdigest()
            response.headers["X-Data-Version"] = version_hash
            response.headers["Last-Modified"] = version_hash
        else:
            response.headers["X-Data-Version"] = "empty"
            response.headers["Last-Modified"] = "empty"

        return response
    except Exception as e:
        print(f"[ERROR] HEAD /courses failed: {e}")
        response = Response(status_code=200)
        response.headers["X-Data-Version"] = "error"
        response.headers["Last-Modified"] = "error"
        return response

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

