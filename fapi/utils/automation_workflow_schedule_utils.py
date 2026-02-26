from sqlalchemy.orm import Session
from fapi.db.models import AutomationWorkflowScheduleORM
from fapi.db.schemas import AutomationWorkflowScheduleCreate, AutomationWorkflowScheduleUpdate
from typing import List, Optional
from fapi.utils.table_fingerprint import generate_version_for_model
from fastapi import Response

def get_automation_workflow_schedules(db: Session) -> List[AutomationWorkflowScheduleORM]:
    return db.query(AutomationWorkflowScheduleORM).all()

def get_automation_workflow_schedule(db: Session, schedule_id: int) -> Optional[AutomationWorkflowScheduleORM]:
    return db.query(AutomationWorkflowScheduleORM).filter(AutomationWorkflowScheduleORM.id == schedule_id).first()

def create_automation_workflow_schedule(db: Session, schedule: AutomationWorkflowScheduleCreate) -> AutomationWorkflowScheduleORM:
    db_schedule = AutomationWorkflowScheduleORM(**schedule.model_dump())
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    return db_schedule

def update_automation_workflow_schedule(db: Session, schedule_id: int, schedule: AutomationWorkflowScheduleUpdate) -> Optional[AutomationWorkflowScheduleORM]:
    db_schedule = db.query(AutomationWorkflowScheduleORM).filter(AutomationWorkflowScheduleORM.id == schedule_id).first()
    if not db_schedule:
        return None
    
    update_data = schedule.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_schedule, key, value)
    
    db.commit()
    db.refresh(db_schedule)
    return db_schedule

def delete_automation_workflow_schedule(db: Session, schedule_id: int) -> bool:
    db_schedule = db.query(AutomationWorkflowScheduleORM).filter(AutomationWorkflowScheduleORM.id == schedule_id).first()
    if not db_schedule:
        return False
    db.delete(db_schedule)
    db.commit()
    return True

def get_automation_workflow_schedules_version(db: Session) -> Response:
    return generate_version_for_model(db, AutomationWorkflowScheduleORM)
