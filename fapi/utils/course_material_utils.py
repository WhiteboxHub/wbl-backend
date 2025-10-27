
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
    "M": "Materials",
    "A": "Assignments"
}

def get_type_display_name(type_code: str) -> str:
    """Get full type name from type code"""
    return COURSE_MATERIAL_TYPE_MAPPING.get(type_code, type_code)

def get_subject_fallback(subject_id: int) -> str:
    """Get fallback subject name with strict validation"""
    if subject_id == 0:
        return "Basic Fundamentals"
    raise ValueError(f"Invalid subject ID: {subject_id}. Subject not found in database.")

def get_course_fallback(course_id: int) -> str:
    """Get fallback course name with strict validation"""
    if course_id == 0:
        return "Fundamentals"
    raise ValueError(f"Invalid course ID: {course_id}. Course not found in database.")

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
        # Validate subject and course associations
        if not subject_name:
            subject_name = get_subject_fallback(material.subjectid)
        if not course_name:
            course_name = get_course_fallback(material.courseid)
        
        enriched_material = {
            "id": material.id,
            "subjectid": material.subjectid,
            "courseid": material.courseid,
            "name": material.name,
            "description": material.description,
            "type": material.type,
            "link": material.link,
            "sortorder": material.sortorder,
            "cm_subject": subject_name,
            "cm_course": course_name,
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
    
    # Validate subject and course associations
    if not subject_name:
        subject_name = get_subject_fallback(material.subjectid)
    if not course_name:
        course_name = get_course_fallback(material.courseid)
    
    return {
        "id": material.id,
        "subjectid": material.subjectid,
        "courseid": material.courseid,
        "name": material.name,
        "description": material.description,
        "type": material.type,
        "link": material.link,
        "sortorder": material.sortorder,
        "cm_subject": subject_name,
        "cm_course": course_name,
        "material_type": get_type_display_name(material.type),
    }

def validate_course_material_associations(db: Session, subject_id: int, course_id: int) -> None:
    """Validate that subject and course IDs exist in database"""
    # Validate subject ID (allow 0 for fundamentals)
    if subject_id != 0:
        subject = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
        if not subject:
            raise ValueError(f"Subject ID {subject_id} does not exist in database")
    
    # Validate course ID (allow 0 for fundamentals)
    if course_id != 0:
        course = db.query(models.Course).filter(models.Course.id == course_id).first()
        if not course:
            raise ValueError(f"Course ID {course_id} does not exist in database")

# Updated CRUD functions
def get_all_course_materials(db: Session) -> List[models.CourseMaterial]:
    """Get all course materials with raw data (for editing)"""
    return db.query(models.CourseMaterial).order_by(models.CourseMaterial.sortorder).all()

def get_course_material(db: Session, material_id: int) -> Optional[models.CourseMaterial]:
    """Get a specific course material by ID (for editing)"""
    return db.query(models.CourseMaterial).filter(models.CourseMaterial.id == material_id).first()

def create_course_material(db: Session, course_material: schemas.CourseMaterialCreate) -> dict:
    """Create a new course material and return enriched data"""
    # Validate material type
    valid_types = ['P', 'C', 'D', 'S', 'I', 'B', 'N', 'M','A']
    if course_material.type not in valid_types:
        raise ValueError(f"Invalid material type. Must be one of: {valid_types}")
    
    # Validate subject and course associations
    validate_course_material_associations(db, course_material.subjectid, course_material.courseid)
    
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
    
    # Validate material type if being updated
    if 'type' in update_data:
        valid_types = ['P', 'C', 'D', 'S', 'I', 'B', 'N', 'M', 'A']
        if update_data['type'] not in valid_types:
            raise ValueError(f"Invalid material type. Must be one of: {valid_types}")
    
    # Validate subject and course associations if being updated
    subject_id = update_data.get('subjectid', db_course_material.subjectid)
    course_id = update_data.get('courseid', db_course_material.courseid)
    validate_course_material_associations(db, subject_id, course_id)
    
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

def get_orphaned_course_materials(db: Session) -> List[models.CourseMaterial]:
    """Utility function to find course materials with invalid subject/course associations"""
    all_materials = get_all_course_materials(db)
    orphaned_materials = []
    
    for material in all_materials:
        try:
            if material.subjectid != 0:
                subject = db.query(models.Subject).filter(models.Subject.id == material.subjectid).first()
                if not subject:
                    orphaned_materials.append(material)
                    continue
            
            if material.courseid != 0:
                course = db.query(models.Course).filter(models.Course.id == material.courseid).first()
                if not course:
                    orphaned_materials.append(material)
        except Exception:
            orphaned_materials.append(material)
    
    return orphaned_materials
