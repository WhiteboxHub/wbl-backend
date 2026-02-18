from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any, Optional
from fapi.db.database import get_db
from fapi.db.models import (
    AutomationWorkflowORM, 
    AutomationWorkflowScheduleORM, 
    AutomationWorkflowLogORM,
    DeliveryEngineORM,
    EmailTemplateORM,
    CandidateMarketingORM,
    CandidateORM
)
from pydantic import BaseModel
import logging

router = APIRouter(prefix="/orchestrator", tags=["Outreach Orchestrator"])
logger = logging.getLogger(__name__)

# --- Models ---

class RecipientResult(BaseModel):
    email: str
    name: Optional[str]
    metadata: Dict[str, Any]

class Credential(BaseModel):
    email: str
    password: Optional[str]
    imap_password: Optional[str]
    start_date: Optional[str]

class SqlExecutionRequest(BaseModel):
    sql_query: str
    parameters: Dict[str, Any] = {}

class LogCreate(BaseModel):
    workflow_id: int
    schedule_id: Optional[int] = None
    run_id: str
    status: str
    started_at: str
    parameters_used: Optional[Any] = None
    execution_metadata: Optional[Any] = None

class LogUpdate(BaseModel):
    status: Optional[str] = None
    records_processed: Optional[int] = None
    records_failed: Optional[int] = None
    error_summary: Optional[str] = None
    execution_metadata: Optional[Any] = None
    finished_at: Optional[str] = None

# --- Endpoints ---

@router.get("/schedules/due")
def get_due_schedules(db: Session = Depends(get_db)):
    """Fetch all schedules that are enabled, due, and not currently running."""
    try:
        sql = text("""
            SELECT s.*, w.status as workflow_status 
            FROM automation_workflows_schedule s 
            JOIN automation_workflows w ON s.automation_workflow_id = w.id 
            WHERE s.enabled = 1 
              AND w.status = 'active'
              AND (s.next_run_at IS NOT NULL AND s.next_run_at <= NOW())
              AND s.is_running = 0
        """)
        # Note: table names might differ slightly, checking models.py
        # AutomationWorkflowScheduleORM table name is "automation_workflow_schedule" (singular based on recent view? No, explicit table names usually plural or singular check models.py)
        # Checking models.py again in memory:
        # AutomationWorkflowScheduleORM -> "automation_workflow_schedule"
        # AutomationWorkflowORM -> "automation_workflow"
        
        # models.py earlier view:
        # class AutomationWorkflowScheduleORM(Base): __tablename__ = "automation_workflow_schedule"
        # class AutomationWorkflowORM(Base): __tablename__ = "automation_workflow"
        
        # Double check table names from models.py before finalizing SQL.
        # Actually in models.py it was "automation_workflows_schedule" and "automation_workflows".
        # Let's verify models.py content again to be safe.
        
        result = db.execute(sql).mappings().all()
        schedules = []
        for r in result:
            d = dict(r)
            d["status"] = d.get("workflow_status")
            d["workflow_id"] = d.get("automation_workflow_id")
            schedules.append(d)
        return schedules
    except Exception as e:
        logger.error(f"Error fetching due schedules: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/schedules/{schedule_id}/lock")
def lock_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Atomically lock a schedule."""
    try:
         # Use table name based on best guess then fix if needed
        sql = text("UPDATE automation_workflows_schedule SET is_running = 1 WHERE id = :id AND is_running = 0")
        result = db.execute(sql, {"id": schedule_id})
        db.commit()
        if result.rowcount > 0:
            return {"success": True}
        return {"success": False}
    except Exception as e:
        db.rollback()
        logger.error(f"Error locking schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/schedules/{schedule_id}")
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Fetch a single schedule by ID with workflow status."""
    try:
        sql = text("""
            SELECT s.*, w.status as workflow_status 
            FROM automation_workflows_schedule s 
            JOIN automation_workflows w ON s.automation_workflow_id = w.id 
            WHERE s.id = :id
        """)
        result = db.execute(sql, {"id": schedule_id}).mappings().first()
        if not result:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        # Merge workflow_status as status for the client if needed, 
        # but let's just return the full mapping.
        data = dict(result)
        # Aliases for Outreach Service compatibility
        data["status"] = data.get("workflow_status")
        data["workflow_id"] = data.get("automation_workflow_id")
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/schedules/{schedule_id}")
def update_schedule(schedule_id: int, updates: Dict[str, Any], db: Session = Depends(get_db)):
    try:
        # Dynamic update
        set_clauses = []
        params = {"id": schedule_id}
        for k, v in updates.items():
            set_clauses.append(f"{k} = :{k}")
            params[k] = v
        
        if not set_clauses:
             return {"success": True}
             
        sql = text(f"UPDATE automation_workflows_schedule SET {', '.join(set_clauses)} WHERE id = :id")
        db.execute(sql, params)
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workflows/key/{key}")
def get_workflow_by_key(key: str, db: Session = Depends(get_db)):
    wf = db.query(AutomationWorkflowORM).filter(AutomationWorkflowORM.workflow_key == key).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf

@router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: int, db: Session = Depends(get_db)):
    wf = db.query(AutomationWorkflowORM).filter(AutomationWorkflowORM.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf

@router.put("/workflows/{workflow_id}")
def update_workflow(workflow_id: int, updates: Dict[str, Any], db: Session = Depends(get_db)):
    try:
        wf = db.query(AutomationWorkflowORM).filter(AutomationWorkflowORM.id == workflow_id).first()
        if not wf:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        for k, v in updates.items():
            if hasattr(wf, k):
                setattr(wf, k, v)
        
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/workflows/{workflow_id}/execute-recipient-sql")
def execute_recipient_sql(workflow_id: int, req: SqlExecutionRequest, db: Session = Depends(get_db)):
    """Execute the SELECT query to find recipients. RESTRICTED: Only SELECT allowed."""
    query = req.sql_query.strip().lower()
    if not query.startswith("select"):
        raise HTTPException(status_code=400, detail="Only SELECT queries allowed for recipient resolution.")
    
    try:
        result = db.execute(text(req.sql_query), req.parameters).mappings().all()
        return [dict(r) for r in result]
    except Exception as e:
        logger.error(f"SQL execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/workflows/{workflow_id}/execute-reset-sql")
def execute_reset_sql(workflow_id: int, req: SqlExecutionRequest, db: Session = Depends(get_db)):
    """Execute the UPDATE query to reset flags. RESTRICTED: Only UPDATE allowed."""
    query = req.sql_query.strip().lower()
    if not query.startswith("update"):
        raise HTTPException(status_code=400, detail="Only UPDATE queries allowed for reset.")

    try:
        db.execute(text(req.sql_query), req.parameters)
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        logger.error(f"SQL execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/candidate-credentials/{candidate_id}")
def get_candidate_credentials(candidate_id: int, db: Session = Depends(get_db)):
    # Join CandidateMarketing with Candidate to get full name and linkedin url
    res = db.query(
        CandidateMarketingORM.email,
        CandidateMarketingORM.password,
        CandidateMarketingORM.imap_password,
        CandidateMarketingORM.start_date,
        CandidateORM.full_name,
        CandidateORM.linkedin_id
    ).join(
        CandidateORM, CandidateORM.id == CandidateMarketingORM.candidate_id
    ).filter(
        CandidateMarketingORM.candidate_id == candidate_id, 
        CandidateMarketingORM.status == 'active'
    ).first()

    if not res:
        raise HTTPException(status_code=404, detail="Active marketing record not found")
    
    return {
        "email": res.email,
        "password": res.password,
        "imap_password": res.imap_password,
        "start_date": str(res.start_date) if res.start_date else None,
        "candidate_name": res.full_name,
        "linkedin_url": res.linkedin_id
    }

@router.get("/delivery-engine/{engine_id}")
def get_engine(engine_id: int, db: Session = Depends(get_db)):
    engine = db.query(DeliveryEngineORM).filter(DeliveryEngineORM.id == engine_id).first()
    if not engine:
        raise HTTPException(status_code=404, detail="Engine not found")
    return engine

@router.get("/email-template/{template_id}")
def get_template(template_id: int, db: Session = Depends(get_db)):
    tpl = db.query(EmailTemplateORM).filter(EmailTemplateORM.id == template_id).first()
    if not tpl:
         raise HTTPException(status_code=404, detail="Template not found")
    return tpl

@router.get("/logs")
def list_logs(workflow_id: Optional[int] = None, run_id: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(AutomationWorkflowLogORM)
    if workflow_id:
        query = query.filter(AutomationWorkflowLogORM.workflow_id == workflow_id)
    if run_id:
        query = query.filter(AutomationWorkflowLogORM.run_id == run_id)
    return query.order_by(AutomationWorkflowLogORM.created_at.desc()).limit(100).all()

@router.post("/logs")
def create_log(log: LogCreate, db: Session = Depends(get_db)):
    try:
        new_log = AutomationWorkflowLogORM(
            workflow_id=log.workflow_id,
            schedule_id=log.schedule_id,
            run_id=log.run_id,
            status=log.status,
            started_at=log.started_at,
            parameters_used=log.parameters_used,
            execution_metadata=log.execution_metadata
        )
        db.add(new_log)
        db.commit()
        db.refresh(new_log)
        return {"id": new_log.id}
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating log: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/logs/{log_id}")
def update_log(log_id: int, log: LogUpdate, db: Session = Depends(get_db)):
    try:
        db_log = db.query(AutomationWorkflowLogORM).filter(AutomationWorkflowLogORM.id == log_id).first()
        if not db_log:
            raise HTTPException(status_code=404, detail="Log not found")
        
        updates = log.model_dump(exclude_unset=True)
        for k, v in updates.items():
            setattr(db_log, k, v)
        
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
