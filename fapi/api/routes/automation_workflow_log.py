from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db.models import AutomationWorkflowLogORM
from fapi.db.schemas import AutomationWorkflowLog
from fapi.utils.permission_gate import enforce_access

router = APIRouter(prefix="/automation-workflow-log", tags=["Automation Workflow Log"])

@router.get("/", response_model=List[AutomationWorkflowLog])
def get_automation_workflow_logs(db: Session = Depends(get_db)):
    return db.query(AutomationWorkflowLogORM).all()

@router.get("/{log_id}", response_model=AutomationWorkflowLog)
def get_automation_workflow_log(log_id: int, db: Session = Depends(get_db)):
    db_log = db.query(AutomationWorkflowLogORM).filter(AutomationWorkflowLogORM.id == log_id).first()
    if not db_log:
        raise HTTPException(status_code=404, detail="Automation Workflow Log not found")
    return db_log

@router.delete("/{log_id}")
def delete_automation_workflow_log(log_id: int, db: Session = Depends(get_db)):
    db_log = db.query(AutomationWorkflowLogORM).filter(AutomationWorkflowLogORM.id == log_id).first()
    if not db_log:
        raise HTTPException(status_code=404, detail="Automation Workflow Log not found")
    db.delete(db_log)
    db.commit()
    return {"message": "Automation Workflow Log deleted"}
