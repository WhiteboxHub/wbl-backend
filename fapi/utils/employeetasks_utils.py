from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional
from fapi.db import models, schemas
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException
from difflib import get_close_matches

def get_all_tasks(db: Session) -> list:
    tasks = db.query(models.EmployeeTaskORM).options(joinedload(models.EmployeeTaskORM.employee)).all()

    result = []
    for t in tasks:
        result.append({
            "id": t.id,
            "employee_id": t.employee_id,
            "employee_name": t.employee.name if t.employee else None,
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



def create_task(db, task: schemas.EmployeeTaskCreate):
    if not task.employee_name or not task.employee_name.strip():
        raise HTTPException(status_code=400, detail="Employee name is required")

    employee_name_clean = "".join(task.employee_name.strip().lower().split())    
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
                detail=f"Multiple employees found matching '{task.employee_name}': {matched_names}. Please provide exact name."
            )


    if not employee:
        all_names = [e.name for e in employees]
        raise HTTPException(
            status_code=400,
            detail=f"Employee '{task.employee_name}' not found. Existing employees: {all_names}"
        )


    db_task = models.EmployeeTaskORM(
        employee_id=employee.id,
        task=task.task,
        assigned_date=task.assigned_date,
        due_date=task.due_date,
        status=task.status.lower() if task.status else "pending",
        priority=task.priority.lower() if task.priority else "medium",
        notes=task.notes
    )


    db_task.employee_name = employee.name


    db.add(db_task)
    try:
        db.commit()
        db.refresh(db_task)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database Integrity Error: {str(e.orig)}")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")

    return db_task



def update_task(db: Session, task_id: int, task: schemas.EmployeeTaskUpdate):
    db_task = get_task_by_id(db, task_id)
    if not db_task:
        return None

    for key, value in task.dict(exclude_unset=True).items():

        if key in {"status", "priority"}:
            if value is not None:
                value = value.lower()
            else:
                continue  # skip updating if None

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