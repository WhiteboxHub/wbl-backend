from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db import models
from fapi.db import schemas

def get_all_course_materials(db: Session) -> List[models.CourseMaterial]:
    """Get all course materials"""
    return db.query(models.CourseMaterial).order_by(models.CourseMaterial.sortorder).all()

def get_course_material(db: Session, material_id: int) -> Optional[models.CourseMaterial]:
    """Get a specific course material by ID"""
    return db.query(models.CourseMaterial).filter(models.CourseMaterial.id == material_id).first()

def create_course_material(db: Session, course_material: schemas.CourseMaterialCreate) -> models.CourseMaterial:
    """Create a new course material"""
  
    valid_types = ['P', 'C', 'D', 'S', 'I', 'B', 'N', 'T', 'G', 'M']
    if course_material.type not in valid_types:
        raise ValueError(f"Invalid material type. Must be one of: {valid_types}")
    
    db_course_material = models.CourseMaterial(
        subjectid=course_material.subjectid,
        courseid=course_material.courseid,
        name=course_material.name,
        description=course_material.description,
        type=course_material.type,
        link=course_material.link,
        sortorder=course_material.sortorder
    )
    
    db.add(db_course_material)
    db.commit()
    db.refresh(db_course_material)
    return db_course_material

def update_course_material(
    db: Session, 
    material_id: int, 
    course_material_update: schemas.CourseMaterialUpdate
) -> models.CourseMaterial:
    """Update a course material"""
    db_course_material = get_course_material(db, material_id)
    if not db_course_material:
        raise ValueError("Course material not found")
    
    update_data = course_material_update.model_dump(exclude_unset=True)
    
    if 'type' in update_data:
        valid_types = ['P', 'C', 'D', 'S', 'I', 'B', 'N', 'T', 'G', 'M']
        if update_data['type'] not in valid_types:
            raise ValueError(f"Invalid material type. Must be one of: {valid_types}")
    
    for field, value in update_data.items():
        setattr(db_course_material, field, value)
    
    db.add(db_course_material)
    db.commit()
    db.refresh(db_course_material)
    return db_course_material

def delete_course_material(db: Session, material_id: int) -> bool:
    """Delete a course material"""
    course_material = get_course_material(db, material_id)
    if not course_material:
        raise ValueError("Course material not found")
    
    db.delete(course_material)
    db.commit()
    return True
