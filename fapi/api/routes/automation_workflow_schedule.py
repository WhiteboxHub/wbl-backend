from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db.models import AutomationWorkflowScheduleORM
from fapi.db.schemas import AutomationWorkflowSchedule, AutomationWorkflowScheduleCreate, AutomationWorkflowScheduleUpdate
from fapi.utils.permission_gate import enforce_access

router = APIRouter(prefix="/automation-workflow-schedule", tags=["Automation Workflow Schedule"])

@router.get("/", response_model=List[AutomationWorkflowSchedule])
def get_automation_workflow_schedules(db: Session = Depends(get_db)):
    return db.query(AutomationWorkflowScheduleORM).all()

@router.post("/", response_model=AutomationWorkflowSchedule, status_code=status.HTTP_201_CREATED)
def create_automation_workflow_schedule(schedule: AutomationWorkflowScheduleCreate, db: Session = Depends(get_db)):
    db_schedule = AutomationWorkflowScheduleORM(**schedule.model_dump())
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    return db_schedule

@router.put("/{schedule_id}", response_model=AutomationWorkflowSchedule)
def update_automation_workflow_schedule(schedule_id: int, schedule: AutomationWorkflowScheduleUpdate, db: Session = Depends(get_db)):
    db_schedule = db.query(AutomationWorkflowScheduleORM).filter(AutomationWorkflowScheduleORM.id == schedule_id).first()
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Automation Workflow Schedule not found")
    
    update_data = schedule.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_schedule, key, value)
    
    db.commit()
    db.refresh(db_schedule)
    return db_schedule

@router.delete("/{schedule_id}")
def delete_automation_workflow_schedule(schedule_id: int, db: Session = Depends(get_db)):
    db_schedule = db.query(AutomationWorkflowScheduleORM).filter(AutomationWorkflowScheduleORM.id == schedule_id).first()
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Automation Workflow Schedule not found")
    db.delete(db_schedule)
    db.commit()
    return {"message": "Automation Workflow Schedule deleted"}
