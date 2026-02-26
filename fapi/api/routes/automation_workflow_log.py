import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db.models import AutomationWorkflowLogORM
from fapi.db.schemas import AutomationWorkflowLog, AutomationWorkflowLogCreate, AutomationWorkflowLogUpdate
from fapi.utils.permission_gate import enforce_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/automation-workflow-log", tags=["Automation Workflow Log"])

@router.get("/", response_model=List[AutomationWorkflowLog])
def get_automation_workflow_logs(db: Session = Depends(get_db)):
    return db.query(AutomationWorkflowLogORM).all()


@router.get("/latest", response_model=AutomationWorkflowLog)
def get_latest_automation_workflow_log(
    workflow_id: int,
    db: Session = Depends(get_db),
):
    """
    Return the most recently *finished* workflow log entry for the given workflow
    that has non-null execution_metadata. Used by the bot to recover last_uid
    per candidate when last_run.json is missing.
    """
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
    logger.info(
        "Fetched latest log for workflow_id=%s run_id=%s finished_at=%s",
        workflow_id, db_log.run_id, db_log.finished_at,
    )
    return db_log


@router.get("/{log_id}", response_model=AutomationWorkflowLog)
def get_automation_workflow_log(log_id: int, db: Session = Depends(get_db)):
    db_log = db.query(AutomationWorkflowLogORM).filter(AutomationWorkflowLogORM.id == log_id).first()
    if not db_log:
        raise HTTPException(status_code=404, detail="Automation Workflow Log not found")
    return db_log

@router.post("/", response_model=AutomationWorkflowLog, status_code=status.HTTP_201_CREATED)
def create_automation_workflow_log(log: AutomationWorkflowLogCreate, db: Session = Depends(get_db)):
    """Create a new workflow run log entry (start_run)."""
    db_log = AutomationWorkflowLogORM(**log.model_dump(exclude_none=True))
    db.add(db_log)
    try:
        db.commit()
        db.refresh(db_log)
        logger.info("Created workflow log run_id=%s workflow_id=%s", log.run_id, log.workflow_id)
        return db_log
    except Exception as e:
        db.rollback()
        logger.error("Failed to create workflow log: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create workflow log")


@router.patch("/by-run-id/{run_id}", response_model=AutomationWorkflowLog)
def update_automation_workflow_log_by_run_id(
    run_id: str,
    update_data: AutomationWorkflowLogUpdate,
    db: Session = Depends(get_db),
):
    """Update status, metadata, and timing of a workflow run log by run_id."""
    db_log = db.query(AutomationWorkflowLogORM).filter(AutomationWorkflowLogORM.run_id == run_id).first()
    if not db_log:
        raise HTTPException(status_code=404, detail=f"Workflow log with run_id '{run_id}' not found")

    for key, value in update_data.model_dump(exclude_none=True).items():
        setattr(db_log, key, value)
    try:
        db.commit()
        db.refresh(db_log)
        logger.info("Updated workflow log run_id=%s status=%s", run_id, update_data.status)
        return db_log
    except Exception as e:
        db.rollback()
        logger.error("Failed to update workflow log run_id=%s: %s", run_id, e)
        raise HTTPException(status_code=500, detail="Failed to update workflow log")


@router.delete("/{log_id}")
def delete_automation_workflow_log(log_id: int, db: Session = Depends(get_db)):
    db_log = db.query(AutomationWorkflowLogORM).filter(AutomationWorkflowLogORM.id == log_id).first()
    if not db_log:
        raise HTTPException(status_code=404, detail="Automation Workflow Log not found")
    db.delete(db_log)
    db.commit()
    return {"message": "Automation Workflow Log deleted"}
