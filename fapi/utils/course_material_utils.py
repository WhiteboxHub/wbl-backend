from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db import models
from fapi.db import schemas

COURSE_MATERIAL_TYPE_MAPPING = {
    "P": "Presentations",
    "C": "Cheatsheets", 
    "D": "Diagrams",
    "S": "Softwares",
    "I": "Installations",
    "B": "Books",
    "N": "Newsletters",
    "M": "Materials"
}

def get_type_display_name(type_code: str) -> str:
    """Get full type name from type code"""
    return COURSE_MATERIAL_TYPE_MAPPING.get(type_code, type_code)

def get_subject_fallback(subject_id: int) -> str:
    """Get fallback subject name for orphan IDs"""
    if subject_id == 0:
        return "Basic Fundamentals"
    return f"Subject ID: {subject_id}"

def get_course_fallback(course_id: int) -> str:
    """Get fallback course name for orphan IDs"""
    if course_id == 0:
        return "Fundamentals"
    return f"Course ID: {course_id}"

def get_all_course_materials_enriched(db: Session) -> List[dict]:
    """Get all course materials with enriched data using SQL JOIN"""
    materials = db.query(
        models.CourseMaterial,
        models.Course.name.label('course_name'),
        models.Subject.name.label('subject_name')
    ).join(
        models.Course, models.CourseMaterial.courseid == models.Course.id, isouter=True
    ).join(
        models.Subject, models.CourseMaterial.subjectid == models.Subject.id, isouter=True
    ).order_by(models.CourseMaterial.sortorder).all()
    
    enriched_materials = []
    for material, course_name, subject_name in materials:
        enriched_material = {
            "id": material.id,
            "subjectid": material.subjectid,
            "courseid": material.courseid,
            "name": material.name,
            "description": material.description,
            "type": material.type,
            "link": material.link,
            "sortorder": material.sortorder,
            "cm_subject": subject_name if subject_name else get_subject_fallback(material.subjectid),
            "cm_course": course_name if course_name else get_course_fallback(material.courseid),
            "material_type": get_type_display_name(material.type),
        }
        enriched_materials.append(enriched_material)
    
    return enriched_materials

def get_course_material_enriched(db: Session, material_id: int) -> Optional[dict]:
    """Get a specific course material by ID with enriched data using JOIN"""
    result = db.query(
        models.CourseMaterial,
        models.Course.name.label('course_name'),
        models.Subject.name.label('subject_name')
    ).join(
        models.Course, models.CourseMaterial.courseid == models.Course.id, isouter=True
    ).join(
        models.Subject, models.CourseMaterial.subjectid == models.Subject.id, isouter=True
    ).filter(models.CourseMaterial.id == material_id).first()
    
    if not result:
        return None
    
    material, course_name, subject_name = result
    return {
        "id": material.id,
        "subjectid": material.subjectid,
        "courseid": material.courseid,
        "name": material.name,
        "description": material.description,
        "type": material.type,
        "link": material.link,
        "sortorder": material.sortorder,
        "cm_subject": subject_name if subject_name else get_subject_fallback(material.subjectid),
        "cm_course": course_name if course_name else get_course_fallback(material.courseid),
        "material_type": get_type_display_name(material.type),
    }

# Updated CRUD functions
def get_all_course_materials(db: Session) -> List[models.CourseMaterial]:
    """Get all course materials with raw data (for editing)"""
    return db.query(models.CourseMaterial).order_by(models.CourseMaterial.sortorder).all()

def get_course_material(db: Session, material_id: int) -> Optional[models.CourseMaterial]:
    """Get a specific course material by ID (for editing)"""
    return db.query(models.CourseMaterial).filter(models.CourseMaterial.id == material_id).first()

def create_course_material(db: Session, course_material: schemas.CourseMaterialCreate) -> dict:
    """Create a new course material and return enriched data"""
    valid_types = ['P', 'C', 'D', 'S', 'I', 'B', 'N', 'M']
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
    
    return get_course_material_enriched(db, db_course_material.id)

def update_course_material(
    db: Session, 
    material_id: int, 
    course_material_update: schemas.CourseMaterialUpdate
) -> dict:
    """Update a course material and return enriched data"""
    db_course_material = get_course_material(db, material_id)
    if not db_course_material:
        raise ValueError("Course material not found")
    
    update_data = course_material_update.model_dump(exclude_unset=True)
    
    if 'type' in update_data:
        valid_types = ['P', 'C', 'D', 'S', 'I', 'B', 'N', 'M']
        if update_data['type'] not in valid_types:
            raise ValueError(f"Invalid material type. Must be one of: {valid_types}")
    
    for field, value in update_data.items():
        setattr(db_course_material, field, value)
    
    db.add(db_course_material)
    db.commit()
    db.refresh(db_course_material)
    
    return get_course_material_enriched(db, material_id)

def delete_course_material(db: Session, material_id: int) -> bool:
    """Delete a course material"""
    course_material = get_course_material(db, material_id)
    if not course_material:
        raise ValueError("Course material not found")
    
    db.delete(course_material)
    db.commit()
    return True
