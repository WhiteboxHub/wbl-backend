import logging
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fapi.db.models import (
    JobScheduleORM, JobDefinitionORM, JobRunORM, 
    CandidateMarketingORM, EmailSenderEngineORM, OutreachContactORM
)
from sqlalchemy import func, or_
import base64
import os

logger = logging.getLogger(__name__)

class JobScheduler:
    def __init__(self, db: Session):
        self.db = db

    def get_due_schedules(self):
        """
        Query for enabled schedules where next_run_at is in the past.
        """
        now = datetime.now()
        schedules = self.db.query(JobScheduleORM).filter(
            or_(
                (JobScheduleORM.manually_triggered == True),
                (JobScheduleORM.enabled == True) & (JobScheduleORM.next_run_at <= now)
            )
        ).all()
        
        if schedules:
            logger.info(f"Worker found {len(schedules)} enabled schedules due for execution at {now}")
        return schedules

    def prepare_job_execution(self, schedule: JobScheduleORM):
        """
        Prepares everything needed for a job run.
        1. Create job_run entry
        2. Fetch associated data
        3. Returns a payload for the dispatcher
        """
        try:
            # 1. Fetch Job Definition
            definition = self.db.query(JobDefinitionORM).filter(
                JobDefinitionORM.id == schedule.job_definition_id
            ).first()
            
            if not definition:
                logger.error(f"[Prep] FAILED: Job Definition {schedule.job_definition_id} not found for schedule {schedule.id}")
                return None
            
            logger.info(f"[Prep] Found Definition: {definition.job_type} for Candidate ID {definition.candidate_marketing_id}")

            # 2. Fetch Job Data & Config
            job_type = definition.job_type
            
            # --- MASS_EMAIL / VENDOR Logic ---
            if job_type in ["MASS_EMAIL", "VENDOR_OUTREACH"]:
                marketing = self.db.query(CandidateMarketingORM).filter(
                    CandidateMarketingORM.id == definition.candidate_marketing_id
                ).first()
                
                if not marketing:
                    logger.error(f"[Prep] FAILED: Candidate Marketing {definition.candidate_marketing_id} not found for job {definition.id}")
                    return None
                
                logger.info(f"[Prep] Marketing Data Loaded for candidate: {marketing.email}")
                
                candidate_info = {
                    "full_name": marketing.candidate.full_name if marketing.candidate else "Candidate",
                    "reply_to_email": marketing.email,
                    "candidate_email": marketing.email,
                    "candidate_intro": marketing.candidate_intro,
                    "linkedin_id": marketing.linkedin_username,
                }
            
            # --- LEADS Logic ---
            else:
                marketing = None
                # For Leads, we don't rely on candidate marketing data
                candidate_info = {}
                logger.info(f"[Prep] Leads/Outreach Job. Skipping candidate marketing lookup.")

            # 3. Parse Config JSON 
            try:
                job_config = json.loads(definition.config_json) if isinstance(definition.config_json, str) else definition.config_json
            except:
                job_config = definition.config_json or {}

            # 4. Fetch Email Engine
            engine = None
            
            # Priority 0: Direct DB Field (NEW)
            if definition.email_engine_id:
                 engine = self.db.query(EmailSenderEngineORM).filter(
                    EmailSenderEngineORM.id == definition.email_engine_id,
                    EmailSenderEngineORM.is_active == True
                ).first()

            engine_id = job_config.get("engine_id")
            email_engine_name = job_config.get("email_engine")
            
            # Priority 1: Explicit Engine ID in config (Legacy fallback)
            if not engine and engine_id:
                engine = self.db.query(EmailSenderEngineORM).filter(
                    EmailSenderEngineORM.id == engine_id,
                    EmailSenderEngineORM.is_active == True
                ).first()
                if not engine:
                     logger.warning(f"[Prep] Requested Engine ID {engine_id} not found or inactive. Falling back to name/default.")

            # Priority 2: Explicit Engine Name in config
            if not engine and email_engine_name:
                engine = self.db.query(EmailSenderEngineORM).filter(
                    EmailSenderEngineORM.provider == email_engine_name.lower(),
                    EmailSenderEngineORM.is_active == True
                ).first()
                if not engine:
                     logger.warning(f"[Prep] Requested Engine Name '{email_engine_name}' not found or inactive. Falling back to default.")

            # Priority 3: Default (Lowest priority number = Highest preference)
            if not engine:
                engine = self.db.query(EmailSenderEngineORM).filter(
                    EmailSenderEngineORM.is_active == True
                ).order_by(EmailSenderEngineORM.priority.asc()).first()
            
            if not engine:
                logger.error("[Prep] FAILED: No active Email Sender Engine found")
                return None
            
            logger.info(f"[Prep] Engine Selected: {engine.provider} (ID: {engine.id})")

            # 5. Determine Capacity
            batch_size = job_config.get("batch_size", 200)
            if batch_size == 0:
                batch_size = 999999
                logger.info("[Prep] Batch Size: Unlimited")
            else:
                logger.info(f"[Prep] Batch Size: {batch_size}")

            # 6. Load CSV
            # STRICT separation of CSVs
            if job_type in ["MASS_EMAIL", "VENDOR_OUTREACH"]:
                csv_file = "vendors.csv"
            else:
                csv_file = "leads.csv"
                
            # Use absolute path based on file location
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            csv_path = os.path.join(base_dir, "email_program", csv_file)
            
            logger.info(f"[Prep] Attempting to load CSV from: {csv_path}")
            
            if not os.path.exists(csv_path):
                logger.error(f"[Prep] FAILED: CSV file not found at {csv_path}")
                return None

            import csv
            all_emails = []
            try:
                with open(csv_path, mode='r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        email = row.get('Email') or row.get('email')
                        unsub = str(row.get('unsubscribe_flag', '0')).strip()
                        bounce = str(row.get('bounce_flag', '0')).strip()
                        complaint = str(row.get('complaint_flag', '0')).strip()
                        
                        if email:
                            email_clean = email.strip().lower()
                            if unsub == '1' or bounce == '1' or complaint == '1':
                                continue
                            all_emails.append(email_clean)
                logger.info(f"[Prep] Loaded {len(all_emails)} emails from CSV {csv_file}")
            except Exception as e:
                logger.error(f"[Prep] FAILED: Error reading CSV: {e}")
                return None


            # Get current offset (ALWAYS RESET TO 0 - send same batch every time)
            current_offset = 0  # job_config.get("csv_offset", 0)
            logger.info(f"[Prep] CSV {csv_file} loaded: {len(all_emails)} emails. Offset locked at 0 (re-send enabled)")

            # 7. Check Suppression (DB)
            suppressed = self.db.query(OutreachContactORM).filter(
                (OutreachContactORM.unsubscribe_flag == True) | 
                (OutreachContactORM.bounce_flag == True) | 
                (OutreachContactORM.complaint_flag == True)
            ).all()
            suppressed_emails = {c.email_lc for c in suppressed}

            # 8. Build Batch
            recipients_payload = []
            base_url = os.getenv("PUBLIC_API_URL", "")
            
            idx = current_offset
            processed_in_this_run = 0
            
            while len(recipients_payload) < batch_size and idx < len(all_emails):
                email = all_emails[idx]
                idx += 1
                
                if email in suppressed_emails:
                    continue
                
                recipients_payload.append({
                    "email": email
                })

            if not recipients_payload:
                logger.warning("[Prep] No eligible recipients found in this batch.")
                job_config["csv_offset"] = idx
                definition.config_json = json.dumps(job_config)
                self.db.commit()
                return None

            # 8.5 Mark Leads as Sent in DB (if source is LEADS_DB)
            if recipient_source == "LEADS_DB":
                target_emails = [r["email"] for r in recipients_payload]
                if target_emails:
                    self.db.query(LeadORM).filter(LeadORM.email.in_(target_emails)).update(
                        {LeadORM.massemail_email_sent: True}, synchronize_session=False
                    )
                    logger.info(f"[Prep] Marked {len(target_emails)} leads as sent in database")

            # 9. Create Job Run
            job_run = JobRunORM(
                job_definition_id=definition.id,
                job_schedule_id=schedule.id,
                run_status="RUNNING",
                started_at=func.now()
            )
            self.db.add(job_run)
            self.db.flush()

            # 10. Build Payload
            try:
                engine_creds = json.loads(engine.credentials_json) if isinstance(engine.credentials_json, str) else engine.credentials_json
            except:
                engine_creds = engine.credentials_json or {}

            payload = {
                "job_run_id": job_run.id,
                "job_type": definition.job_type,
                "candidate_info": candidate_info,
                "recipients": recipients_payload,
                "engine": {
                    "provider": engine.provider,
                    "credentials_json": engine_creds
                },
                "config_json": job_config
            }

            # OFFSET TRACKING DISABLED - Always send to same batch
            # This allows re-sending emails to the same recipients with different candidates
            # job_config["csv_offset"] = idx
            # definition.config_json = json.dumps(job_config)
            # self.db.commit()
            
            logger.info(f"[Prep] Offset tracking disabled. Will re-use same batch on next run.")
            self.db.commit()

            return payload, job_run, schedule
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error preparing job execution for schedule {schedule.id}: {e}")
            return None

    def get_remote_job_context(self, schedule: JobScheduleORM):
        """
        Prepares context for a Remote Worker.
        Does NOT load CSV. Creates JobRun.
        """
        try:
            # 1. Fetch Job Definition
            definition = self.db.query(JobDefinitionORM).filter(
                JobDefinitionORM.id == schedule.job_definition_id
            ).first()
            if not definition: return None
            
            # 2. Fetch Job Data (Marketing)
            job_type = definition.job_type
            candidate_info = {}
            
            if job_type in ["MASS_EMAIL", "VENDOR_OUTREACH"]:
                marketing = self.db.query(CandidateMarketingORM).filter(
                    CandidateMarketingORM.id == definition.candidate_marketing_id
                ).first()
                if marketing:
                    candidate_info = {
                        "full_name": marketing.candidate.full_name if marketing.candidate else "Candidate",
                        "reply_to_email": marketing.email,
                        "candidate_email": marketing.email,
                        "candidate_intro": marketing.candidate_intro,
                        "linkedin_id": marketing.linkedin_username,
                    }
            
            # 3. Config
            try:
                job_config = json.loads(definition.config_json) if isinstance(definition.config_json, str) else definition.config_json
            except:
                job_config = definition.config_json or {}

            # 4. Engine
            engine_id = job_config.get("engine_id")
            email_engine_name = job_config.get("email_engine")
            engine = None
            if engine_id:
                engine = self.db.query(EmailSenderEngineORM).filter(EmailSenderEngineORM.id == engine_id).first()
            if not engine and email_engine_name:
                engine = self.db.query(EmailSenderEngineORM).filter(EmailSenderEngineORM.provider == email_engine_name.lower()).first()
            if not engine:
                 engine = self.db.query(EmailSenderEngineORM).filter(EmailSenderEngineORM.is_active == True).order_by(EmailSenderEngineORM.priority.asc()).first()
            
            if not engine: return None

            # 5. Handle Recipient Source (NEW FEATURE)
            recipient_source = job_config.get("recipient_source", "CSV").upper()
            dynamic_recipients = []
            
            if recipient_source == "OUTREACH_DB":
                date_filter = job_config.get("date_filter", "ALL_ACTIVE").upper()
                lookback_days = int(job_config.get("lookback_days", 0))
                
                query = self.db.query(OutreachContactORM).filter(
                    OutreachContactORM.unsubscribe_flag == False,
                    OutreachContactORM.bounce_flag == False
                )
                
                if date_filter == "TODAY":
                    query = query.filter(
                        or_(
                            func.date(OutreachContactORM.created_at) == func.current_date(),
                            func.date(OutreachContactORM.updated_at) == func.current_date()
                        )
                    )
                elif date_filter == "LAST_N_DAYS" and lookback_days > 0:
                    delta = datetime.now() - timedelta(days=lookback_days)
                    query = query.filter(
                        or_(
                            OutreachContactORM.created_at >= delta,
                            OutreachContactORM.updated_at >= delta
                        )
                    )
                
                # Fetch recipients (limit by batch size to avoid massive payloads)
                batch_size = job_config.get("batch_size", 200)
                contacts = query.limit(batch_size).all()
                dynamic_recipients = [c.email for c in contacts if c.email]
                logger.info(f"Loaded {len(dynamic_recipients)} recipients from OUTREACH_DB (Filter: {date_filter})")

            # 6. Create Job Run
            job_run = JobRunORM(
                job_definition_id=definition.id,
                job_schedule_id=schedule.id,
                run_status="RUNNING",
                started_at=func.now()
            )
            self.db.add(job_run)
            self.db.flush() # Get ID
            
            # 7. Build Context Payload
            try:
                engine_creds = json.loads(engine.credentials_json) if isinstance(engine.credentials_json, str) else engine.credentials_json
            except:
                engine_creds = engine.credentials_json or {}

            context = {
                "job_run_id": job_run.id,
                "job_type": job_type,
                "candidate_info": candidate_info,
                "engine": {
                    "provider": engine.provider,
                    "credentials_json": engine_creds
                },
                "config_json": job_config,
                "db_recipients": dynamic_recipients # Provided if source is DB
            }
            # Commit job run creation
            self.db.commit()
            return context

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error preparing remote context: {e}")
            return None

    def update_job_run_result(self, job_run_id, result_data):
        """
        Updates job_run with results from email service.
        """
        try:
            job_run = self.db.query(JobRunORM).get(job_run_id)
            if job_run:
                job_run.run_status = result_data.get("run_status", "SUCCESS")
                job_run.items_total = result_data.get("items_total", 0)
                job_run.items_succeeded = result_data.get("items_succeeded", 0)
                job_run.items_failed = result_data.get("items_failed", 0)
                job_run.finished_at = func.now()
                self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating job run {job_run_id}: {e}")

    def update_schedule_last_run(self, schedule_id):
        """
        Updates last_run_at and calculates the next scheduled time.
        """
        try:
            schedule = self.db.query(JobScheduleORM).get(schedule_id)
            if schedule:
                schedule.last_run_at = func.now()
                schedule.manually_triggered = False
                
                # Calculate next run time
                freq = (schedule.frequency or "DAILY").upper()
                interval = schedule.interval_value or 1
                current_next = schedule.next_run_at or datetime.now()
                
                if freq == "ONCE":
                    schedule.enabled = False
                    logger.info(f"Schedule {schedule_id} is ONCE-only. Disabling after execution.")
                elif freq in ["MINUTELY", "MINUTES"]:
                    schedule.next_run_at = current_next + timedelta(minutes=interval)
                elif freq == "HOURLY":
                    schedule.next_run_at = current_next + timedelta(hours=interval)
                elif freq == "DAILY":
                    schedule.next_run_at = current_next + timedelta(days=interval)
                elif freq == "WEEKLY":
                    schedule.next_run_at = current_next + timedelta(weeks=interval)
                elif freq == "MONTHLY":
                    schedule.next_run_at = current_next + timedelta(days=30 * interval)
                else:
                    schedule.next_run_at = current_next + timedelta(days=1)
                
                # Safety catch-up: If the calculated next_run_at is STILL in the past, update it to future
                if schedule.next_run_at < datetime.now():
                     delta = datetime.now() - schedule.next_run_at
                     if delta.total_seconds() > 60:
                         schedule.next_run_at = datetime.now() + timedelta(minutes=1) 
                
                logger.info(f"Schedule {schedule_id} updated. Frequency: {freq}, Interval: {interval}. Next run at: {schedule.next_run_at}")
                self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating schedule {schedule_id}: {e}")
