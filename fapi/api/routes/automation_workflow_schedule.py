from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.utils.table_fingerprint import generate_version_for_model
from fapi.db.models import AutomationWorkflowScheduleORM
from fapi.db.schemas import AutomationWorkflowSchedule, AutomationWorkflowScheduleCreate, AutomationWorkflowScheduleUpdate
from fapi.utils.permission_gate import enforce_access
import hashlib
from fastapi import Response
from sqlalchemy import func

router = APIRouter(prefix="/automation-workflow-schedule", tags=["Automation Workflow Schedule"])

security = HTTPBearer()

@router.head("/")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return generate_version_for_model(db, AutomationWorkflowScheduleORM)

def check_workflow_schedules_version(db: Session = Depends(get_db)):
    try:
        result = db.query(
            func.count().label("cnt"),
            func.max(AutomationWorkflowScheduleORM.id).label("max_id"),
            func.sum(
                func.crc32(
                    func.concat_ws(
                        '|',
                        AutomationWorkflowScheduleORM.id,
                        func.coalesce(AutomationWorkflowScheduleORM.workflow_id, ''),
                        func.coalesce(AutomationWorkflowScheduleORM.frequency, ''),
                        func.coalesce(AutomationWorkflowScheduleORM.enabled, '')
                    )
                )
            ).label("checksum")
        ).first()

        response = Response(status_code=200)
        if result and result.cnt > 0:
            fingerprint = f"{result.cnt}|{result.max_id}|{result.checksum}"
            version_hash = hashlib.md5(fingerprint.encode()).hexdigest()
            response.headers["X-Data-Version"] = version_hash
            response.headers["Last-Modified"] = version_hash
        else:
            response.headers["X-Data-Version"] = "empty"
            response.headers["Last-Modified"] = "empty"

        return response
    except Exception as e:
        response = Response(status_code=200)
        response.headers["X-Data-Version"] = "error"
        response.headers["Last-Modified"] = "error"
        return response

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
