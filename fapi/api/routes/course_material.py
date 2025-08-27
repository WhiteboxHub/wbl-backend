from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from fapi.db.database import get_db
from fapi.db import schemas
from fapi.utils import course_material_utils

router = APIRouter()


@router.get("/course-materials", response_model=List[schemas.CourseMaterialResponse])
def get_all_course_materials(db: Session = Depends(get_db)):
    materials = course_material_utils.get_all_course_materials(db)
    return materials


@router.post("/course-materials", response_model=schemas.CourseMaterialResponse, status_code=status.HTTP_201_CREATED)
def create_course_material(course_material: schemas.CourseMaterialCreate, db: Session = Depends(get_db)):
    try:
        db_material = course_material_utils.create_course_material(db, course_material)
        return db_material
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

@router.put("/course-materials/{material_id}", response_model=schemas.CourseMaterialResponse)
def update_course_material(
    material_id: int, 
    course_material_update: schemas.CourseMaterialUpdate, 
    db: Session = Depends(get_db)
):
    try:
        updated_material = course_material_utils.update_course_material(
            db, material_id, course_material_update
        )
        return updated_material
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

@router.delete("/course-materials/{material_id}")
def delete_course_material(material_id: int, db: Session = Depends(get_db)):
    try:
        course_material_utils.delete_course_material(db, material_id)
        return {"status": "success", "message": "Course material deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
