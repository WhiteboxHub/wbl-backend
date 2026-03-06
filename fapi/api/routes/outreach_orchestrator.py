from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
import logging

from fapi.db.database import get_db
from fapi.utils import outreach_orchestrator_utils as orc_utils

router = APIRouter(prefix="/orchestrator", tags=["Outreach Orchestrator"])
logger = logging.getLogger(__name__)
security = HTTPBearer()

# Pydantic models

class SqlExecutionRequest(BaseModel):
    sql_query: str
    parameters: Dict[str, Any] = {}


class LogCreate(BaseModel):
    workflow_id: int
    schedule_id: Optional[int] = None
    run_id: str
    status: str
    started_at: Optional[str] = None
    parameters_used: Optional[Any] = None
    execution_metadata: Optional[Any] = None


class LogUpdate(BaseModel):
    status: Optional[str] = None
    records_processed: Optional[int] = None
    records_failed: Optional[int] = None
    error_summary: Optional[str] = None
    execution_metadata: Optional[Any] = None
    finished_at: Optional[str] = None


# Schedules

@router.get("/schedules/due")
def get_due_schedules(db: Session = Depends(get_db)):
    """Fetch all schedules that are enabled, due, and not currently running."""
    try:
        return orc_utils.get_due_schedules(db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching due schedules: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedules/{schedule_id}/lock")
def lock_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Atomically lock a schedule to prevent double-execution."""
    try:
        success = orc_utils.lock_schedule(db, schedule_id)
        return {"success": success}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error locking schedule %s: %s", schedule_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schedules/{schedule_id}")
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Fetch a single schedule by ID with its workflow status."""
    try:
        return orc_utils.get_schedule(db, schedule_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching schedule %s: %s", schedule_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/schedules/{schedule_id}")
def update_schedule(
    schedule_id: int,
    updates: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """Update schedule fields (only whitelisted columns are accepted)."""
    try:
        orc_utils.update_schedule(db, schedule_id, updates)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating schedule %s: %s", schedule_id, e)
        raise HTTPException(status_code=500, detail=str(e))


# Workflows

@router.get("/workflows/key/{key}")
def get_workflow_by_key(key: str, db: Session = Depends(get_db)):
    """Fetch a workflow by its string key."""
    return orc_utils.get_workflow_by_key(db, key)


@router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: int, db: Session = Depends(get_db)):
    """Fetch a workflow by numeric ID."""
    return orc_utils.get_workflow(db, workflow_id)


@router.put("/workflows/{workflow_id}")
def update_workflow(
    workflow_id: int,
    updates: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """Update workflow fields (only whitelisted columns are accepted)."""
    try:
        orc_utils.update_workflow(db, workflow_id, updates)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating workflow %s: %s", workflow_id, e)
        raise HTTPException(status_code=500, detail=str(e))


# Dynamic SQL execution endpoints

@router.post("/workflows/{workflow_id}/execute-recipient-sql")
def execute_recipient_sql(
    workflow_id: int,
    req: SqlExecutionRequest,
    db: Session = Depends(get_db),
):
    """Execute the SELECT query to find recipients. RESTRICTED: Only SELECT allowed."""
    return orc_utils.execute_recipient_sql(db, req.sql_query, req.parameters)


@router.post("/workflows/{workflow_id}/execute-reset-sql")
def execute_reset_sql(
    workflow_id: int,
    req: SqlExecutionRequest,
    db: Session = Depends(get_db),
):
    """Execute the UPDATE query to reset flags. RESTRICTED: Only UPDATE allowed."""
    orc_utils.execute_reset_sql(db, req.sql_query, req.parameters)
    return {"success": True}

# Candidate credentials

@router.get("/candidate-credentials/{candidate_id}")
def get_candidate_credentials(candidate_id: int, db: Session = Depends(get_db)):
    """Return sender email/password/IMAP credentials for an active candidate marketing record."""
    return orc_utils.get_candidate_credentials(db, candidate_id)

# Delivery engine & email template

@router.get("/delivery-engine/{engine_id}")
def get_engine(engine_id: int, db: Session = Depends(get_db)):
    return orc_utils.get_delivery_engine(db, engine_id)


@router.get("/email-template/{template_id}")
def get_template(template_id: int, db: Session = Depends(get_db)):
    return orc_utils.get_email_template(db, template_id)


# Logs

@router.get("/logs")
def list_logs(
    workflow_id: Optional[int] = None,
    run_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return orc_utils.list_logs(db, workflow_id=workflow_id, run_id=run_id)


@router.post("/logs")
def create_log(log: LogCreate, db: Session = Depends(get_db)):
    try:
        new_log = orc_utils.create_log(db, log.model_dump())
        return {"id": new_log.id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating log: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/logs/{log_id}")
def update_log(log_id: int, log: LogUpdate, db: Session = Depends(get_db)):
    try:
        orc_utils.update_log(db, log_id, log.model_dump(exclude_unset=True))
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating log %s: %s", log_id, e)
        raise HTTPException(status_code=500, detail=str(e))

