from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional
from fapi.db import models, schemas
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException
from difflib import get_close_matches
from datetime import timedelta

def get_all_tasks(db: Session, project_id: Optional[int] = None, employee_id: Optional[int] = None) -> list:
    query = db.query(models.EmployeeTaskORM).options(
        joinedload(models.EmployeeTaskORM.employee),
        joinedload(models.EmployeeTaskORM.project)
    )

    if project_id:
        query = query.filter(models.EmployeeTaskORM.project_id == project_id)
    
    if employee_id:
        query = query.filter(models.EmployeeTaskORM.employee_id == employee_id)

    tasks = query.order_by(models.EmployeeTaskORM.id.desc()).all()

    result = []
    for t in tasks:
        result.append({
            "id": t.id,
            "employee_id": t.employee_id,
            "employee_name": t.employee.name if t.employee else None,
            "project_id": t.project_id,
            "project_name": t.project.name if t.project else None,
            "task": t.task,
            "assigned_date": t.assigned_date,
            "due_date": t.due_date,
            "status": t.status,
            "priority": t.priority,
            "notes": t.notes
        })
    return result


def get_task_by_id(db: Session, task_id: int) -> Optional[models.EmployeeTaskORM]:
    return db.query(models.EmployeeTaskORM).filter(models.EmployeeTaskORM.id == task_id).first()


def _find_employee_by_name(db: Session, name_input: str) -> models.EmployeeORM:
    if not name_input or not name_input.strip():
        raise HTTPException(status_code=400, detail="Employee name is required")

    employee_name_clean = "".join(name_input.strip().lower().split())    
    employees = db.query(models.EmployeeORM).all()
    db_names = {e.id: "".join(e.name.strip().lower().split()) for e in employees if e.name}
    employee = None

    for eid, name in db_names.items():
        if employee_name_clean == name:
            employee = next(e for e in employees if e.id == eid)
            break


    if not employee:
        for eid, name in db_names.items():
            if employee_name_clean in name or name in employee_name_clean:
                employee = next(e for e in employees if e.id == eid)
                break


    if not employee:
        matches = get_close_matches(employee_name_clean, db_names.values(), n=5, cutoff=0.7)
        if len(matches) == 1:
            match_name = matches[0]
            employee_id = next(k for k, v in db_names.items() if v == match_name)
            employee = next(e for e in employees if e.id == employee_id)
        elif len(matches) > 1:

            matched_names = [e.name for e in employees if "".join(e.name.strip().lower().split()) in matches]
            raise HTTPException(
                status_code=400,
                detail=f"Multiple employees found matching '{name_input}': {matched_names}. Please provide exact name."
            )


    if not employee:
        all_names = [e.name for e in employees]
        raise HTTPException(
            status_code=400,
            detail=f"Employee '{name_input}' not found. Existing employees: {all_names}"
        )
    
    return employee


def create_task(db: Session, task: schemas.EmployeeTaskCreate):
    if task.employee_id:
        employee = db.query(models.EmployeeORM).filter(models.EmployeeORM.id == task.employee_id).first()
        if not employee:
             raise HTTPException(status_code=400, detail=f"Employee ID {task.employee_id} not found")
    elif task.employee_name:
        employee = _find_employee_by_name(db, task.employee_name)
    else:
        raise HTTPException(status_code=400, detail="Employee name or ID is required")
    project_id = task.project_id
    if hasattr(task, 'project_name') and task.project_name:
        project = db.query(models.ProjectORM).filter(models.ProjectORM.name == task.project_name).first()
        if project:
            project_id = project.id

    due_date = task.due_date
    if not due_date and task.assigned_date:
        due_date = task.assigned_date + timedelta(days=7)

    db_task = models.EmployeeTaskORM(
        employee_id=employee.id,
        project_id=project_id,
        task=task.task,
        assigned_date=task.assigned_date,
        due_date=due_date,
        status=task.status.lower() if task.status else "pending",
        priority=task.priority.lower() if task.priority else "medium",
        notes=task.notes
    )

    db.add(db_task)
    try:
        db.flush()
        db.commit()
        db.refresh(db_task)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database Integrity Error: {str(e.orig)}")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")

    db_task.employee_name = employee.name
    return db_task



def update_task(db: Session, task_id: int, task: schemas.EmployeeTaskUpdate):
    db_task = get_task_by_id(db, task_id)
    if not db_task:
        return None

    update_data = task.dict(exclude_unset=True)
    
    if "employee_name" in update_data:
        new_name = update_data.pop("employee_name")
        if new_name:
             employee = _find_employee_by_name(db, new_name)
             db_task.employee_id = employee.id
    
    if "project_name" in update_data:
        project_name = update_data.pop("project_name")
        if project_name:
            project = db.query(models.ProjectORM).filter(models.ProjectORM.name == project_name).first()
            if project:
                db_task.project_id = project.id
        else:
            db_task.project_id = None
    
    if "project_id" in update_data:
        db_task.project_id = update_data.pop("project_id")

    for key, value in update_data.items():
        if key in {"status", "priority"}:
            if value is not None:
                value = value.lower()
            else:
                continue  

        setattr(db_task, key, value)

    try:
        db.commit()
        db.refresh(db_task)
    except Exception as e:
        db.rollback()
        raise e
    
    return db_task


def delete_task(db: Session, task_id: int) -> Optional[models.EmployeeTaskORM]:
    db_task = get_task_by_id(db, task_id)
    if not db_task:
        return None
    db.delete(db_task)
    db.commit()
    return db_task