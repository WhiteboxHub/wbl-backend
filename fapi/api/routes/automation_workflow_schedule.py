from fastapi import Security, APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List
from fapi.db.database import get_db
from fapi.db.schemas import AutomationWorkflowSchedule, AutomationWorkflowScheduleCreate, AutomationWorkflowScheduleUpdate
from fapi.utils import automation_workflow_schedule_utils
from fapi.utils.automation_workflow_schedule_utils import get_automation_workflow_schedules_version

router = APIRouter(prefix="/automation-workflow-schedule", tags=["Automation Workflow Schedule"])

security = HTTPBearer()

@router.head("/")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return get_automation_workflow_schedules_version(db)

@router.get("/", response_model=List[AutomationWorkflowSchedule])
def get_automation_workflow_schedules(db: Session = Depends(get_db)):
    return automation_workflow_schedule_utils.get_automation_workflow_schedules(db)

@router.post("/", response_model=AutomationWorkflowSchedule, status_code=status.HTTP_201_CREATED)
def create_automation_workflow_schedule(schedule: AutomationWorkflowScheduleCreate, db: Session = Depends(get_db)):

    return automation_workflow_schedule_utils.create_automation_workflow_schedule(db, schedule)

    db_schedule = AutomationWorkflowScheduleORM(**schedule.model_dump())
    db.add(db_schedule)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Related Automation Workflow does not exist or database constraint failed.")
    db.refresh(db_schedule)
    return db_schedule


@router.put("/{schedule_id}", response_model=AutomationWorkflowSchedule)
def update_automation_workflow_schedule(schedule_id: int, schedule: AutomationWorkflowScheduleUpdate, db: Session = Depends(get_db)):
    db_schedule = automation_workflow_schedule_utils.update_automation_workflow_schedule(db, schedule_id, schedule)
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Automation Workflow Schedule not found")

    
    update_data = schedule.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_schedule, key, value)
    
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Related Automation Workflow does not exist or database constraint failed.")
    
    db.refresh(db_schedule)

    return db_schedule

@router.delete("/{schedule_id}")
def delete_automation_workflow_schedule(schedule_id: int, db: Session = Depends(get_db)):
    success = automation_workflow_schedule_utils.delete_automation_workflow_schedule(db, schedule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Automation Workflow Schedule not found")
    return {"message": "Automation Workflow Schedule deleted"}
