from sqlalchemy.orm import Session
from fapi.db.models import JobRequestORM, JobDefinitionORM, JobScheduleORM, EmailSenderEngineORM
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

def process_approved_job_requests(db: Session):
    """
    Finds APPROVED job requests and converts them into Job Definition and Job Schedule.
    """
    approved_requests = db.query(JobRequestORM).filter(JobRequestORM.status == "APPROVED").all()
    
    if not approved_requests:
        return

    logger.info(f"Processing {len(approved_requests)} approved job requests")
    
    for req in approved_requests:
        try:
            # 1. Check if a Job Definition already exists for this candidate/type
            # We might want to update or skip if it exists. 
            # For simplicity, let's create a new one if it doesn't exist.
            
            existing_def = db.query(JobDefinitionORM).filter(
                JobDefinitionORM.candidate_marketing_id == req.candidate_marketing_id,
                JobDefinitionORM.job_type == req.job_type
            ).first()
            
            if existing_def:
                logger.info(f"Job Definition already exists for request {req.id}, skipping creation.")
                req.status = "PROCESSED"
                req.processed_at = datetime.now()
                db.commit()
                continue
            
            # 2. Pick a Default Engine (highest priority active)
            engine = db.query(EmailSenderEngineORM).filter(
                EmailSenderEngineORM.is_active == True
            ).order_by(EmailSenderEngineORM.priority.asc()).first()
            
            if not engine:
                logger.error(f"Cannot process JobRequest {req.id}: No active Email Sender Engine found.")
                continue

            # 3. Create Job Definition
            config = {
                "csv_filename": "vendors.csv" if req.job_type == "MASS_EMAIL" else "leads.csv",
                "batch_size": 200,
                "csv_offset": 0
            }
            
            new_def = JobDefinitionORM(
                job_type=req.job_type,
                candidate_marketing_id=req.candidate_marketing_id,
                status="ACTIVE",
                email_engine_id=engine.id,
                config_json=json.dumps(config)
            )
            db.add(new_def)
            db.flush() # Get ID
            
            # 4. Create Job Schedule (Default: DAILY, starting now)
            new_schedule = JobScheduleORM(
                job_definition_id=new_def.id,
                frequency="DAILY",
                interval_value=1,
                next_run_at=datetime.now(),
                enabled=True
                # manually_triggered removed - column doesn't exist in DB
            )
            db.add(new_schedule)
            
            # 5. Mark request as processed
            req.status = "PROCESSED"
            req.processed_at = datetime.now()
            
            db.commit()
            logger.info(f"Successfully converted JobRequest {req.id} to Definition and DAILY Schedule")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error processing JobRequest {req.id}: {e}")
