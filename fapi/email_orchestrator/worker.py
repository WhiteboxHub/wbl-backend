import time
import logging
import threading
import os
from datetime import datetime
from fapi.db.database import SessionLocal
from .scheduler import JobScheduler
from .dispatcher import EmailDispatcher
from fapi.utils.job_processor import process_approved_job_requests

# Configurations
# Default to internal email service if not set
EMAIL_SERVICE_URL = os.getenv("EMAIL_SERVICE_URL", "")

CHECK_INTERVAL_SECONDS = 5

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("email_orchestrator")

def run_orchestrator_loop():
    """
    Main loop that checks for due jobs and executes them.
    """
    logger.info("Email Orchestrator Background Worker Started")
    dispatcher = EmailDispatcher(EMAIL_SERVICE_URL)
    
    while True:
        db = SessionLocal()
        try:
            # 0. Process any new APPROVED job requests first
            process_approved_job_requests(db)
            
            scheduler = JobScheduler(db)
            due_schedules = scheduler.get_due_schedules()
            
            if due_schedules:
                logger.info(f"Found {len(due_schedules)} due schedules")
                
                for schedule in due_schedules:
                    result = scheduler.prepare_job_execution(schedule)
                    if not result:
                        continue
                        
                    payload, job_run, schedule_obj = result
                    
                    # Call external Email Service
                    service_response = dispatcher.dispatch_job(payload)
                    
                    if service_response:
                        # Success calling the service, map response to job_run
                        result_data = {
                            "run_status": "SUCCESS",
                            "items_total": service_response.get("items_total", 0),
                            "items_succeeded": service_response.get("items_succeeded", 0),
                            "items_failed": service_response.get("items_failed", 0),
                        }
                    else:
                        # Failed to call service
                        result_data = {
                            "run_status": "FAILED",
                            "items_total": 0,
                            "items_succeeded": 0,
                            "items_failed": 0,
                        }
                    
                    # Update status
                    scheduler.update_job_run_result(job_run.id, result_data)
                    scheduler.update_schedule_last_run(schedule_obj.id)
            
        except Exception as e:
            logger.error(f"Error in orchestrator loop: {e}")
        finally:
            db.close()
            
        # Wait for the next check cycle
        time.sleep(CHECK_INTERVAL_SECONDS)

def start_background_orchestrator():
    """
    Starts the orchestrator in a background thread.
    """
    thread = threading.Thread(target=run_orchestrator_loop, daemon=True)
    thread.start()
    return thread
