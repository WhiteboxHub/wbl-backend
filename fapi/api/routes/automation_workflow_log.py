from fastapi import Security, APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import logging
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db.schemas import AutomationWorkflowLog, AutomationWorkflowLogCreate, AutomationWorkflowLogUpdate
from fapi.utils import automation_workflow_log_utils
from fapi.utils.automation_workflow_log_utils import (
    get_latest_log,
    create_log,
    update_log_by_run_id,
    get_automation_workflow_logs_version,
    get_all_logs,
    get_log_by_id,
    delete_log
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/automation-workflow-log", tags=["Automation Workflow Log"])

security = HTTPBearer()

@router.head("/")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return get_automation_workflow_logs_version(db)

@router.get("/", response_model=List[AutomationWorkflowLog])
def get_automation_workflow_logs(db: Session = Depends(get_db)):
    return automation_workflow_log_utils.get_all_logs(db)


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
    db_log = get_latest_log(db, workflow_id)
    logger.info(
        "Fetched latest log for workflow_id=%s run_id=%s finished_at=%s",
        workflow_id, db_log.run_id, db_log.finished_at,
    )
    return db_log


@router.get("/{log_id}", response_model=AutomationWorkflowLog)
def get_automation_workflow_log(log_id: int, db: Session = Depends(get_db)):
    return automation_workflow_log_utils.get_log_by_id(db, log_id)

@router.post("/", response_model=AutomationWorkflowLog, status_code=status.HTTP_201_CREATED)
def create_automation_workflow_log(log: AutomationWorkflowLogCreate, db: Session = Depends(get_db)):
    """Create a new workflow run log entry (start_run)."""
    db_log = create_log(db, log)
    logger.info("Created workflow log run_id=%s workflow_id=%s", log.run_id, log.workflow_id)
    return db_log


@router.patch("/by-run-id/{run_id}", response_model=AutomationWorkflowLog)
def update_automation_workflow_log_by_run_id(
    run_id: str,
    update_data: AutomationWorkflowLogUpdate,
    db: Session = Depends(get_db),
):
    """Update status, metadata, and timing of a workflow run log by run_id."""
    db_log = update_log_by_run_id(db, run_id, update_data)
    logger.info("Updated workflow log run_id=%s status=%s", run_id, update_data.status)
    return db_log


@router.delete("/{log_id}")
def delete_automation_workflow_log(log_id: int, db: Session = Depends(get_db)):
    return automation_workflow_log_utils.delete_log(db, log_id)
