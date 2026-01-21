from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.db import models, schemas
from datetime import date

router = APIRouter(prefix="/projects", tags=["Projects"])

# ----------------- Projects CRUD -----------------

@router.post("/", response_model=schemas.ProjectOut)
def create_project(project: schemas.ProjectCreate, db: Session = Depends(get_db)):
    try:
        db_project = models.ProjectORM(**project.dict())
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        return db_project
    except Exception as e:
        db.rollback()
        print(f"Error creating project: {e}")
        print(f"Project data received: {project.dict()}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[schemas.ProjectOut])
def list_projects(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    owner: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.ProjectORM)
    if status:
        query = query.filter(models.ProjectORM.status == status)
    if priority:
        query = query.filter(models.ProjectORM.priority == priority)
    if owner:
        query = query.filter(models.ProjectORM.owner == owner)
    return query.all()

@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(models.ProjectORM).filter(models.ProjectORM.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.put("/{project_id}", response_model=schemas.ProjectOut)
def update_project(project_id: int, project_in: schemas.ProjectUpdate, db: Session = Depends(get_db)):
    project = db.query(models.ProjectORM).filter(models.ProjectORM.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    update_data = project_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    
    db.commit()
    db.refresh(project)
    return project

@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(models.ProjectORM).filter(models.ProjectORM.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    db.delete(project)
    db.commit()
    return {"message": "Project deleted successfully"}
