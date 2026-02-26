import logging
from typing import List
from sqlalchemy.orm import Session
from fapi.db.models import AutomationWorkflowLogORM
from fapi.db.schemas import AutomationWorkflowLogCreate, AutomationWorkflowLogUpdate
from fastapi import HTTPException
from fapi.utils.table_fingerprint import generate_version_for_model
from fastapi import Response

logger = logging.getLogger(__name__)

def get_latest_log(db: Session, workflow_id: int):
    db_log = (
        db.query(AutomationWorkflowLogORM)
        .filter(
            AutomationWorkflowLogORM.workflow_id == workflow_id,
            AutomationWorkflowLogORM.finished_at.isnot(None),
            AutomationWorkflowLogORM.execution_metadata.isnot(None),
        )
        .order_by(AutomationWorkflowLogORM.finished_at.desc())
        .first()
    )
    if not db_log:
        raise HTTPException(
            status_code=404,
            detail=f"No completed workflow log with execution_metadata found for workflow_id {workflow_id}",
        )
    return db_log

def create_log(db: Session, log: AutomationWorkflowLogCreate):
    db_log = AutomationWorkflowLogORM(**log.model_dump(exclude_none=True))
    db.add(db_log)
    try:
        db.commit()
        db.refresh(db_log)
        return db_log
    except Exception as e:
        db.rollback()
        logger.error("Failed to create workflow log: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create workflow log")

def update_log_by_run_id(db: Session, run_id: str, update_data: AutomationWorkflowLogUpdate):
    db_log = db.query(AutomationWorkflowLogORM).filter(AutomationWorkflowLogORM.run_id == run_id).first()
    if not db_log:
        raise HTTPException(status_code=404, detail=f"Workflow log with run_id '{run_id}' not found")

    for key, value in update_data.model_dump(exclude_none=True).items():
        setattr(db_log, key, value)
    try:
        db.commit()
        db.refresh(db_log)
        return db_log
    except Exception as e:
        db.rollback()
        logger.error("Failed to update workflow log run_id=%s: %s", run_id, e)
        raise HTTPException(status_code=500, detail="Failed to update workflow log")

def get_all_logs(db: Session) -> List[AutomationWorkflowLogORM]:
    return db.query(AutomationWorkflowLogORM).all()

def get_log_by_id(db: Session, log_id: int) -> AutomationWorkflowLogORM:
    db_log = db.query(AutomationWorkflowLogORM).filter(AutomationWorkflowLogORM.id == log_id).first()
    if not db_log:
        raise HTTPException(status_code=404, detail="Automation Workflow Log not found")
    return db_log

def delete_log(db: Session, log_id: int):
    db_log = get_log_by_id(db, log_id)
    db.delete(db_log)
    db.commit()
    return {"message": "Automation Workflow Log deleted"}

def get_automation_workflow_logs_version(db: Session) -> Response:
    return generate_version_for_model(db, AutomationWorkflowLogORM)
