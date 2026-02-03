import logging
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.email_orchestrator.scheduler import JobScheduler
from fapi.db.models import JobScheduleORM

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/remote/schedules/due")
def get_due_schedules(db: Session = Depends(get_db)):
    """
    Returns list of enabled schedules due for execution.
    Should differ from internal scheduler? Yes, internal scheduler runs "process_approved_job_requests".
    This one returns schedules for the remote worker to pick up.
    """
    scheduler = JobScheduler(db)
    schedules = scheduler.get_due_schedules()
    return [{"id": s.id, "next_run_at": str(s.next_run_at)} for s in schedules]

@router.get("/remote/schedules/{schedule_id}/context")
def get_schedule_context(schedule_id: int, db: Session = Depends(get_db)):
    """
    Returns the execution context (JobRun ID, candidate data, engine config)
    WITHOUT loading the CSV (since CSV is local to the worker).
    """
    scheduler = JobScheduler(db)
    schedule = db.query(JobScheduleORM).filter(JobScheduleORM.id == schedule_id).first()
    if not schedule:
        raise HTTPException(404, "Schedule not found")
    
    context = scheduler.get_remote_job_context(schedule)
    if not context:
        raise HTTPException(400, "Failed to prepare context (missing definition or engine?)")
    
    return context

@router.post("/remote/schedules/{schedule_id}/complete")
def complete_schedule(schedule_id: int, result: dict = Body(...), db: Session = Depends(get_db)):
    """
    Updates JobRun status and Reschedules the job.
    result: { job_run_id, status, items_succeeded, items_failed, new_offset }
    """
    scheduler = JobScheduler(db)
    job_run_id = result.get("job_run_id")
    
    # 1. Update Job Run Result
    if job_run_id:
        scheduler.update_job_run_result(job_run_id, result)
    
    schedule = db.query(JobScheduleORM).filter(JobScheduleORM.id == schedule_id).first()
    if not schedule:
        raise HTTPException(404, "Schedule not found")

    # 2. Update Offset in Definition (DISABLED - allow re-sending)
    # new_offset = result.get("new_offset")
    # if new_offset is not None:
    #      definition = schedule.definition
    #      try:
    #          config = json.loads(definition.config_json) if isinstance(definition.config_json, str) else definition.config_json
    #      except:
    #          config = definition.config_json or {}
    #      
    #      config["csv_offset"] = new_offset
    #      definition.config_json = json.dumps(config)
    #      logger.info(f"Updated Offset for Schedule {schedule_id} to {new_offset}")
    
    logger.info(f"Offset tracking disabled for Schedule {schedule_id}. Will re-send same batch.")

    # 3. Use Scheduler Logic to update last run and calculate next run
    scheduler.update_schedule_last_run(schedule_id)
    
    # Reload for response
    db.refresh(schedule)
    return {"status": "ok", "next_run": str(schedule.next_run_at)}
