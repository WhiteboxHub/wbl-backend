from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.db import schemas
from fapi.utils import projects_utils

router = APIRouter(prefix="/projects", tags=["Projects"])

# ----------------- Projects CRUD -----------------

@router.post("/", response_model=schemas.ProjectOut)
def create_project(project: schemas.ProjectCreate, db: Session = Depends(get_db)):
    try:
        return projects_utils.create_project(db, project)
    except Exception as e:
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
    return projects_utils.list_projects(db, status, priority, owner)

@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    return projects_utils.get_project_by_id(db, project_id)

@router.put("/{project_id}", response_model=schemas.ProjectOut)
def update_project(project_id: int, project_in: schemas.ProjectUpdate, db: Session = Depends(get_db)):
    try:
        return projects_utils.update_project(db, project_id, project_in)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    try:
        return projects_utils.delete_project(db, project_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
