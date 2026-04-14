import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from fapi.db.models import (
    AutomationWorkflowLogORM,
    AutomationWorkflowORM,
    AutomationWorkflowScheduleORM,
)
from fapi.utils.dynamic_weekly_report import send_weekly_marketing_report as run_weekly_marketing_report_workflow

logger = logging.getLogger(__name__)

WORKFLOW_KEY = "weekly_marketing_report"


def ensure_weekly_marketing_report_workflow(db: Session) -> Dict[str, Any]:
    """
    Ensure the workflow + weekly schedule exist in DB.
    Creates:
      - automation_workflows row (workflow_type=email_sender, status=active)
      - automation_workflows_schedule row (frequency=weekly, enabled=True)

    Returns ids + whether created.
    """
    created_workflow = False
    created_schedule = False

    wf = db.query(AutomationWorkflowORM).filter(AutomationWorkflowORM.workflow_key == WORKFLOW_KEY).first()
    if not wf:
        wf = AutomationWorkflowORM(
            workflow_key=WORKFLOW_KEY,
            name="Weekly Marketing Report",
            description="Generate and email weekly marketing candidate report.",
            workflow_type="email_sender",
            status="active",
            version=1,
        )
        db.add(wf)
        db.commit()
        db.refresh(wf)
        created_workflow = True

    sched = (
        db.query(AutomationWorkflowScheduleORM)
        .filter(AutomationWorkflowScheduleORM.automation_workflow_id == wf.id)
        .first()
    )
    if not sched:
        # Create schedule for 8:00 AM Pacific Time (15:00 UTC or 16:00 UTC)
        now = datetime.now(timezone.utc)
        # 8 AM PT is 15:00 UTC (PDT) or 16:00 UTC (PST)
        # Setting to 15:00 UTC as primary target
        next_run = now.replace(hour=15, minute=0, second=0, microsecond=0)
        if next_run < now:
            next_run += timedelta(days=1)
            
        sched = AutomationWorkflowScheduleORM(
            automation_workflow_id=wf.id,
            timezone="America/Los_Angeles",
            cron_expression=None,
            frequency="daily",
            interval_value=1,
            next_run_at=next_run,
            last_run_at=None,
            run_parameters={"report": WORKFLOW_KEY},
            enabled=True,
            is_running=False,
        )
        db.add(sched)
        db.commit()
        db.refresh(sched)
        created_schedule = True

    return {
        "workflow_id": int(wf.id),
        "schedule_id": int(sched.id),
        "created_workflow": created_workflow,
        "created_schedule": created_schedule,
        "workflow_key": WORKFLOW_KEY,
    }


def _compute_next_run(schedule: AutomationWorkflowScheduleORM, anchor: Optional[datetime] = None) -> Optional[datetime]:
    """
    Compute next_run_at from cron_expression (if present) or frequency/interval_value.
    Anchors to a provided timestamp (usually the previous next_run_at) to prevent drift.
    Stored timestamps are UTC.
    """
    if anchor is None:
        anchor = schedule.next_run_at or datetime.now(timezone.utc)

    # cron_expression support (optional dependency)
    if schedule.cron_expression:
        try:
            from croniter import croniter  # type: ignore

            return croniter(schedule.cron_expression, anchor).get_next(datetime).replace(tzinfo=timezone.utc)
        except Exception:
            # fall back to frequency-based compute
            pass

    freq = (schedule.frequency or "").lower()
    interval = int(schedule.interval_value or 1)

    if freq == "daily":
        return anchor + timedelta(days=interval)
    if freq == "weekly":
        return anchor + timedelta(weeks=interval)
    if freq == "monthly":
        # Simplified monthly (30 days) or logic to handle calendar months
        year = anchor.year
        month = anchor.month + interval
        while month > 12:
            month -= 12
            year += 1
        try:
            return anchor.replace(year=year, month=month)
        except ValueError:
            import calendar
            last_day = calendar.monthrange(year, month)[1]
            return anchor.replace(year=year, month=month, day=min(anchor.day, last_day))
    if freq == "custom":
        return anchor + timedelta(days=interval)
    if freq == "once":
        return None
    return None


def _lock_schedule(db: Session, schedule_id: int) -> bool:
    """
    Acquire a row lock and mark schedule as running.
    """
    sched = (
        db.query(AutomationWorkflowScheduleORM)
        .filter(
            AutomationWorkflowScheduleORM.id == schedule_id,
            AutomationWorkflowScheduleORM.is_running == False,
        )
        .with_for_update()
        .first()
    )
    if sched is None:
        db.rollback()
        return False
    sched.is_running = True
    db.commit()
    return True


def run_weekly_marketing_report_from_schedule(
    db: Session,
    *,
    schedule_id: int,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    The ONLY supported execution path:
    - verify schedule exists and belongs to workflow_key=weekly_marketing_report
    - verify workflow is active
    - verify schedule is enabled and due (next_run_at <= now)
    - lock schedule (is_running=True) to avoid double execution
    - generate + email report (unless dry_run)
    - update schedule last_run_at/next_run_at and unlock
    - write a workflow log entry
    """
    row = (
        db.query(AutomationWorkflowScheduleORM, AutomationWorkflowORM)
        .join(AutomationWorkflowORM, AutomationWorkflowScheduleORM.automation_workflow_id == AutomationWorkflowORM.id)
        .filter(AutomationWorkflowScheduleORM.id == schedule_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")

    sched, wf = row
    if wf.workflow_key != WORKFLOW_KEY:
        raise HTTPException(status_code=400, detail=f"Schedule does not belong to workflow_key='{WORKFLOW_KEY}'")
    if wf.status != "active":
        raise HTTPException(status_code=409, detail="Workflow is not active")
    if not sched.enabled:
        raise HTTPException(status_code=409, detail="Schedule is disabled")

    now = datetime.now(timezone.utc)
    if sched.next_run_at is None or sched.next_run_at > now:
        raise HTTPException(status_code=409, detail="Schedule is not due yet")

    # lock
    if not _lock_schedule(db, int(sched.id)):
        raise HTTPException(status_code=409, detail="Schedule is already running")

    run_id = f"{WORKFLOW_KEY}_{now.strftime('%Y%m%dT%H%M%SZ')}"

    # Create log as running
    log = AutomationWorkflowLogORM(
        workflow_id=wf.id,
        schedule_id=sched.id,
        run_id=run_id,
        status="running",
        started_at=now,
        parameters_used={"dry_run": dry_run},
        execution_metadata={"trigger": "schedule", "workflow_key": WORKFLOW_KEY},
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    try:
        result = run_weekly_marketing_report_workflow(db, dry_run=dry_run)

        finished = datetime.now(timezone.utc)
        # Update schedule timing + unlock
        sched.last_run_at = finished
        sched.next_run_at = _compute_next_run(sched, anchor=sched.next_run_at)
        sched.is_running = False

        # Update log
        log.status = "success" if not dry_run else "success"
        log.finished_at = finished
        log.records_processed = len(result.metrics)
        log.records_failed = 0
        log.execution_metadata = {
            **(log.execution_metadata or {}),
            "recipients": result.recipients,
            "subject": result.subject,
            "date_range": result.date_range,
        }
        db.commit()

        return {
            "run_id": run_id,
            "workflow_id": int(wf.id),
            "schedule_id": int(sched.id),
            "dry_run": dry_run,
            "status": "success",
            "candidates_processed": len(result.metrics),
            "recipients_resolved": result.recipients,
            "subject": result.subject,
            "date_range": result.date_range,
            "next_run_at": sched.next_run_at,
        }
    except Exception as e:
        finished = datetime.now(timezone.utc)
        # Best-effort unlock schedule
        sched.is_running = False
        # Keep next_run_at as-is on failure (so it stays due and can retry) unless user changes it.
        try:
            log.status = "failed"
            log.finished_at = finished
            log.records_failed = 1
            log.error_summary = "weekly_marketing_report failed"
            log.error_details = str(e)
            db.commit()
        except Exception:
            db.rollback()
        logger.error("Weekly marketing report schedule run failed: %s", e, exc_info=True)
        raise

