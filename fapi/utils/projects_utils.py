from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db import models, schemas
from fastapi import HTTPException

def create_project(db: Session, project: schemas.ProjectCreate):
    try:
        db_project = models.ProjectORM(**project.dict())
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        return db_project
    except Exception as e:
        db.rollback()
        raise e

def list_projects(
    db: Session,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    owner: Optional[str] = None
):
    query = db.query(models.ProjectORM)
    if status:
        query = query.filter(models.ProjectORM.status == status)
    if priority:
        query = query.filter(models.ProjectORM.priority == priority)
    if owner:
        query = query.filter(models.ProjectORM.owner == owner)
    return query.all()

def get_project_by_id(db: Session, project_id: int):
    project = db.query(models.ProjectORM).filter(models.ProjectORM.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

def update_project(db: Session, project_id: int, project_in: schemas.ProjectUpdate):
    project = get_project_by_id(db, project_id)
    
    update_data = project_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    
    db.commit()
    db.refresh(project)
    return project

def delete_project(db: Session, project_id: int):
    project = get_project_by_id(db, project_id)
    db.delete(project)
    db.commit()
    return {"message": "Project deleted successfully"}
