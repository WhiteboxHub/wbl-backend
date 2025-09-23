from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from fapi.db import models, schemas


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


def create_task(db: Session, task: schemas.EmployeeTaskCreate) -> models.EmployeeTaskORM:
    db_task = models.EmployeeTaskORM(**task.dict())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


def update_task(db: Session, task_id: int, task: schemas.EmployeeTaskUpdate) -> Optional[models.EmployeeTaskORM]:
    db_task = get_task_by_id(db, task_id)
    if not db_task:
        return None
    for key, value in task.dict().items():
        setattr(db_task, key, value)
    db.commit()
    db.refresh(db_task)
    return db_task


def delete_task(db: Session, task_id: int) -> Optional[models.EmployeeTaskORM]:
    db_task = get_task_by_id(db, task_id)
    if not db_task:
        return None
    db.delete(db_task)
    db.commit()
    return db_task
