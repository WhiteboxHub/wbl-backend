"""
Outreach Orchestrator Utils
All database logic for the /orchestrator router.
Pure SQLAlchemy ORM — no raw SQL (except the two intentional execute-sql helpers
which run caller-supplied queries and must stay as text()).
"""
import logging
from datetime import datetime, timedelta, timezone
from croniter import croniter
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload

from fapi.db.models import (
    AutomationWorkflowLogORM,
    AutomationWorkflowORM,
    AutomationWorkflowScheduleORM,
    CandidateMarketingORM,
    CandidateORM,
    DeliveryEngineORM,
    EmailTemplateORM,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowed column sets (whitelist to prevent SQL injection on dynamic updates)
# ---------------------------------------------------------------------------

_SCHEDULE_UPDATABLE_COLS = {
    "enabled",
    "is_running",
    "next_run_at",
    "last_run_at",
    "cron_expression",
    "frequency",
    "interval_value",
    "run_parameters",
    "timezone",
    "updated_at",
}

_WORKFLOW_UPDATABLE_COLS = {
    "name",
    "description",
    "status",
    "workflow_type",
    "email_template_id",
    "delivery_engine_id",
    "recipient_list_sql",
    "credentials_list_sql",
    "parameters_config",
    "version",
    "last_mod_user_id",
    "updated_at",
}

# Workflow keys that the outreach service is allowed to run
_ALLOWED_WORKFLOW_KEYS = {
    "daily_vendor_outreach",
    "weekly_vendor_outreach",
    "weekly_leads_outreach",
    "weekly_potential_leads_outreach",
    "linkedin_non_easy_job_extractor",
    "hiring_cafe_job_extractor",
    "weekly_marketing_report",
}


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------


def get_due_schedules(db: Session) -> List[Dict[str, Any]]:
    """
    Return all schedules that are:
      - enabled = True
      - parent workflow status = 'active'
      - parent workflow type = 'email_sender'
      - parent workflow key is one of the allowed outreach workflow keys
      - next_run_at is not None and <= NOW()
      - is_running = False

    The result dicts expose both ORM column names and legacy aliases
    (status, workflow_id) that the outreach service expects.
    """
    now = datetime.now(timezone.utc)

    rows = (
        db.query(AutomationWorkflowScheduleORM, AutomationWorkflowORM)
        .join(
            AutomationWorkflowORM,
            AutomationWorkflowScheduleORM.automation_workflow_id == AutomationWorkflowORM.id,
        )
        .filter(
            AutomationWorkflowScheduleORM.enabled == True,
            AutomationWorkflowORM.status == "active",
            # Include both email_sender (outreach) AND extractor (job scrapers like hiring_cafe)
            AutomationWorkflowORM.workflow_type.in_(["email_sender", "extractor"]),
            AutomationWorkflowORM.workflow_key.in_(_ALLOWED_WORKFLOW_KEYS),
            AutomationWorkflowScheduleORM.next_run_at != None,
            AutomationWorkflowScheduleORM.next_run_at <= now,
            AutomationWorkflowScheduleORM.is_running == False,
        )
        .all()
    )


    schedules = []
    for sched, wf in rows:
        d = {c.name: getattr(sched, c.name) for c in sched.__table__.columns}
        # Legacy aliases expected by the outreach service client
        d["status"] = wf.status
        d["workflow_id"] = sched.automation_workflow_id
        d["workflow_key"] = wf.workflow_key
        d["workflow_status"] = wf.status
        schedules.append(d)

    return schedules


def lock_schedule(db: Session, schedule_id: int) -> bool:
    """
    Atomically mark a schedule as running.
    Returns True if the lock was acquired, False if it was already locked.
    The check-and-set is done in a single ORM query:
      fetch the schedule WHERE id = schedule_id AND is_running = False,
      then update it — if no row matches, the lock was already held.
    """
    sched = (
        db.query(AutomationWorkflowScheduleORM)
        .filter(
            AutomationWorkflowScheduleORM.id == schedule_id,
            AutomationWorkflowScheduleORM.is_running == False,
        )
        .with_for_update()   # row-level lock for concurrent safety
        .first()
    )
    if sched is None:
        db.rollback()
        return False

    sched.is_running = True
    db.commit()
    return True


def get_schedule(db: Session, schedule_id: int) -> Dict[str, Any]:
    """Return a single schedule joined with its workflow, or raise 404."""
    row = (
        db.query(AutomationWorkflowScheduleORM, AutomationWorkflowORM)
        .join(
            AutomationWorkflowORM,
            AutomationWorkflowScheduleORM.automation_workflow_id == AutomationWorkflowORM.id,
        )
        .filter(AutomationWorkflowScheduleORM.id == schedule_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Schedule not found")

    sched, wf = row
    d = {c.name: getattr(sched, c.name) for c in sched.__table__.columns}
    d["status"] = wf.status
    d["workflow_id"] = sched.automation_workflow_id
    d["workflow_key"] = wf.workflow_key
    d["workflow_status"] = wf.status
    return d


def update_schedule(db: Session, schedule_id: int, updates: Dict[str, Any]) -> None:
    """
    Update fields on an AutomationWorkflowScheduleORM row via ORM setattr.
    Only columns in _SCHEDULE_UPDATABLE_COLS are allowed; unknown keys raise
    a 400 error (replaces the old raw-SQL approach that was vulnerable to
    SQL injection via unvalidated column names).
    """
    unknown = set(updates.keys()) - _SCHEDULE_UPDATABLE_COLS
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown or non-updatable schedule fields: {sorted(unknown)}",
        )

    sched = (
        db.query(AutomationWorkflowScheduleORM)
        .filter(AutomationWorkflowScheduleORM.id == schedule_id)
        .first()
    )
    if sched is None:
        raise HTTPException(status_code=404, detail="Schedule not found")

    for k, v in updates.items():
        setattr(sched, k, v)

    db.commit()


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------


def get_workflow(db: Session, workflow_id: int) -> AutomationWorkflowORM:
    wf = (
        db.query(AutomationWorkflowORM)
        .filter(AutomationWorkflowORM.id == workflow_id)
        .first()
    )
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


def get_workflow_by_key(db: Session, key: str) -> AutomationWorkflowORM:
    wf = (
        db.query(AutomationWorkflowORM)
        .filter(AutomationWorkflowORM.workflow_key == key)
        .first()
    )
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


def update_workflow(db: Session, workflow_id: int, updates: Dict[str, Any]) -> None:
    """
    Update fields on an AutomationWorkflowORM row via ORM setattr.
    Only columns in _WORKFLOW_UPDATABLE_COLS are allowed.
    """
    unknown = set(updates.keys()) - _WORKFLOW_UPDATABLE_COLS
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown or non-updatable workflow fields: {sorted(unknown)}",
        )

    wf = (
        db.query(AutomationWorkflowORM)
        .filter(AutomationWorkflowORM.id == workflow_id)
        .first()
    )
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    for k, v in updates.items():
        setattr(wf, k, v)

    db.commit()


# ---------------------------------------------------------------------------
# Dynamic SQL execution (intentionally kept as text() — these endpoints exist
# specifically to run arbitrary caller-supplied SQL)
# ---------------------------------------------------------------------------


def execute_recipient_sql(
    db: Session, sql_query: str, parameters: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Execute a SELECT query provided by the outreach service to resolve recipients.
    Restricted to SELECT only; raises 400 otherwise.
    """
    if not sql_query.strip().lower().startswith("select"):
        raise HTTPException(
            status_code=400,
            detail="Only SELECT queries allowed for recipient resolution.",
        )
    try:
        result = db.execute(text(sql_query), parameters).mappings().all()
        return [dict(r) for r in result]
    except Exception as e:
        logger.error("Recipient SQL execution failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


def execute_reset_sql(
    db: Session, sql_query: str, parameters: Dict[str, Any]
) -> None:
    """
    Execute an UPDATE query provided by the outreach service to reset flags.
    Restricted to UPDATE only; raises 400 otherwise.
    """
    if not sql_query.strip().lower().startswith("update"):
        raise HTTPException(
            status_code=400,
            detail="Only UPDATE queries allowed for reset.",
        )
    try:
        db.execute(text(sql_query), parameters)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Reset SQL execution failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Candidate credentials
# ---------------------------------------------------------------------------


def get_candidate_credentials(db: Session, candidate_id: int) -> Dict[str, Any]:
    """
    Return SMTP/IMAP credentials and basic profile for an active CandidateMarketing record.
    """
    res = (
        db.query(
            CandidateMarketingORM.email,
            CandidateMarketingORM.password,
            CandidateMarketingORM.imap_password,
            CandidateMarketingORM.start_date,
            CandidateORM.full_name,
            CandidateORM.linkedin_id,
        )
        .join(CandidateORM, CandidateORM.id == CandidateMarketingORM.candidate_id)
        .filter(
            CandidateMarketingORM.candidate_id == candidate_id,
            CandidateMarketingORM.status == "active",
        )
        .first()
    )

    if res is None:
        raise HTTPException(
            status_code=404, detail="Active marketing record not found"
        )

    return {
        "email": res.email,
        "password": res.password,
        "imap_password": res.imap_password,
        "start_date": str(res.start_date) if res.start_date else None,
        "candidate_name": res.full_name,
        "linkedin_url": res.linkedin_id,
    }


# ---------------------------------------------------------------------------
# Delivery engine & email template
# ---------------------------------------------------------------------------


def get_delivery_engine(db: Session, engine_id: int) -> DeliveryEngineORM:
    engine = (
        db.query(DeliveryEngineORM)
        .filter(DeliveryEngineORM.id == engine_id)
        .first()
    )
    if engine is None:
        raise HTTPException(status_code=404, detail="Engine not found")
    return engine


def get_email_template(db: Session, template_id: int) -> EmailTemplateORM:
    tpl = (
        db.query(EmailTemplateORM)
        .filter(EmailTemplateORM.id == template_id)
        .first()
    )
    if tpl is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------


def list_logs(
    db: Session,
    workflow_id: Optional[int] = None,
    run_id: Optional[str] = None,
) -> List[AutomationWorkflowLogORM]:
    q = db.query(AutomationWorkflowLogORM)
    if workflow_id is not None:
        q = q.filter(AutomationWorkflowLogORM.workflow_id == workflow_id)
    if run_id is not None:
        q = q.filter(AutomationWorkflowLogORM.run_id == run_id)
    return q.order_by(AutomationWorkflowLogORM.created_at.desc()).limit(100).all()


def _calculate_next_run(schedule: AutomationWorkflowScheduleORM) -> Optional[datetime]:
    """
    Calculate the next run time based on the schedule's frequency.
    Ensures the next run is always in the future.
    """
    anchor = schedule.next_run_at or datetime.now(timezone.utc)
    now = datetime.now(timezone.utc)

    if schedule.frequency == "weekly":
        next_run = anchor + timedelta(weeks=1)
        while next_run <= now:
            next_run += timedelta(weeks=1)
        return next_run
    elif schedule.frequency == "daily":
        next_run = anchor + timedelta(days=1)
        while next_run <= now:
            next_run += timedelta(days=1)
        return next_run
    elif schedule.frequency == "monthly":
        next_run = anchor
        while next_run <= now:
            year = next_run.year
            month = next_run.month + 1
            if month > 12:
                month = 1
                year += 1
            try:
                next_run = next_run.replace(year=year, month=month)
            except ValueError:
                import calendar
                last_day = calendar.monthrange(year, month)[1]
                next_run = next_run.replace(year=year, month=month, day=min(anchor.day, last_day))
        return next_run
    elif schedule.frequency == "custom" and schedule.cron_expression:
        try:
            cron = croniter(schedule.cron_expression, now)
            return cron.get_next(datetime).replace(tzinfo=timezone.utc)
        except Exception as e:
            logger.error(f"Error parsing cron {schedule.cron_expression}: {e}")
            return None
    elif schedule.frequency == "once":
        return None

    return None


def create_log(db: Session, log_data: Dict[str, Any]) -> AutomationWorkflowLogORM:
    now = datetime.now(timezone.utc)
    status = log_data["status"]
    schedule_id = log_data.get("schedule_id")

    # 1. Create the log entry
    new_log = AutomationWorkflowLogORM(
        workflow_id=log_data["workflow_id"],
        schedule_id=schedule_id,
        run_id=log_data["run_id"],
        status=status,
        started_at=log_data.get("started_at"),
        parameters_used=log_data.get("parameters_used"),
        execution_metadata=log_data.get("execution_metadata"),
        created_at=now,
        updated_at=now,
    )
    db.add(new_log)

    # 2. Update the schedule if one is associated
    if schedule_id:
        schedule = db.query(AutomationWorkflowScheduleORM).filter(
            AutomationWorkflowScheduleORM.id == schedule_id
        ).first()
        
        if schedule:
            if status == "running":
                schedule.is_running = True
            elif status in ["success", "failed", "completed"]:
                schedule.is_running = False
                schedule.last_run_at = now
                
                if schedule.workflow_key in ['daily_marketing_report', 'weekly_marketing_report'] and status == 'success':
                    # Marketing Report specific logic (Update next_run_at and set back to idle)
                    # This ensures it runs exactly once per day and is ready for tomorrow
                    if schedule.next_run_at:
                        schedule.next_run_at = schedule.next_run_at + timedelta(days=1)
                    schedule.state = 'idle'
                    logger.info(f"Marketing report {schedule_id} successfully finished. Rescheduled to {schedule.next_run_at}")
                else:
                    # Update state for all other workflows as normal
                    schedule.state = status
                    
                    # Reschedule only on success or if we want to retry on failure
                    # For now, we reschedule on both success and failure to prevent loops
                    next_run = _calculate_next_run(schedule)
                    schedule.next_run_at = next_run
                    
                    if schedule.frequency == "once":
                        schedule.enabled = False
                    
                    logger.info(f"Schedule {schedule_id} finished with {status}. Next run: {next_run}")

    db.commit()
    db.refresh(new_log)
    return new_log


def update_log(
    db: Session, log_id: int, updates: Dict[str, Any]
) -> AutomationWorkflowLogORM:
    db_log = (
        db.query(AutomationWorkflowLogORM)
        .filter(AutomationWorkflowLogORM.id == log_id)
        .first()
    )
    if db_log is None:
        raise HTTPException(status_code=404, detail="Log not found")

    for k, v in updates.items():
        if hasattr(db_log, k):
            setattr(db_log, k, v)

    db.commit()
    return db_log
