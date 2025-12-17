from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from fapi.db import schemas
from fapi.db.database import get_db
from fapi.utils.employeetasks_utils import (
    get_all_tasks,
    create_task,
    update_task,
    delete_task
)

router = APIRouter()


@router.get("/employee-tasks", response_model=List[schemas.EmployeeTask])
def read_tasks(db: Session = Depends(get_db)):
    return get_all_tasks(db)


@router.post("/employee-tasks", response_model=schemas.EmployeeTask)
def create_new_task(task: schemas.EmployeeTaskCreate, db: Session = Depends(get_db)):
    return create_task(db, task)


@router.put("/employee-tasks/{task_id}", response_model=schemas.EmployeeTask)
def update_existing_task(task_id: int, task: schemas.EmployeeTaskUpdate, db: Session = Depends(get_db)):
    updated_task = update_task(db, task_id, task)
    if not updated_task:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated_task


@router.delete("/employee-tasks/{task_id}", response_model=schemas.EmployeeTask)
def delete_existing_task(task_id: int, db: Session = Depends(get_db)):
    deleted_task = delete_task(db, task_id)
    if not deleted_task:
        raise HTTPException(status_code=404, detail="Task not found")
    return deleted_task