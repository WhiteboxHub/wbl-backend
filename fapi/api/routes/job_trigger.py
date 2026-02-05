from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.db.models import JobScheduleORM
from fapi.email_orchestrator.scheduler import JobScheduler
from fapi.email_orchestrator.dispatcher import EmailDispatcher
import threading
import logging
import os

router = APIRouter()
logger = logging.getLogger(__name__)

# Configurations
EMAIL_SERVICE_URL = os.getenv("EMAIL_SERVICE_URL", "")

def execute_job_task(schedule_id: int, db_session_factory):
    """Background task to run the job immediately"""
    db = db_session_factory()
    try:
        scheduler = JobScheduler(db)
        dispatcher = EmailDispatcher(EMAIL_SERVICE_URL)
        
        schedule = db.query(JobScheduleORM).get(schedule_id)
        if not schedule:
            return

        logger.info(f"Manual trigger started for Schedule {schedule_id}")
        
        prep = scheduler.prepare_job_execution(schedule)
        if prep:
            payload, job_run, schedule_ref = prep
            
            # Call external Email Service
            service_response = dispatcher.dispatch_job(payload)
            
            if service_response:
                result_data = {
                    "run_status": "SUCCESS",
                    "items_total": service_response.get("items_total", 0),
                    "items_succeeded": service_response.get("items_succeeded", 0),
                    "items_failed": service_response.get("items_failed", 0),
                }
            else:
                result_data = {
                    "run_status": "FAILED",
                    "items_total": 0,
                    "items_succeeded": 0,
                    "items_failed": 0,
                }

            scheduler.update_job_run_result(job_run.id, result_data)
            scheduler.update_schedule_last_run(schedule.id)
            logger.info(f"Manual trigger finished for Schedule {schedule_id}. Result: {result_data.get('run_status')}")
    except Exception as e:
        logger.error(f"Error in manual trigger for Schedule {schedule_id}: {e}")
    finally:
        db.close()

@router.post("/job-schedule/{schedule_id}/run-now")
def run_job_now(schedule_id: int, db: Session = Depends(get_db)):
    """API endpoint to arm a job for immediate execution by the worker"""
    schedule = db.query(JobScheduleORM).get(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    from datetime import datetime
    schedule.manually_triggered = True
    schedule.next_run_at = datetime.now()
    db.commit()
    
    logger.info(f"Schedule {schedule_id} armed for manual execution by worker")
    return {"message": "Job armed for execution. The background worker will pick it up shortly.", "status": "armed"}
