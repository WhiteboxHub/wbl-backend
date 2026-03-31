"""
Automation Workflow Scheduler Service
Handles periodic execution of scheduled workflows
Integrates with AutomationWorkflowScheduleORM for centralized schedule management

The scheduler auto-starts when this module is imported by the application.
"""
import atexit
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from apscheduler.schedulers.background import BackgroundScheduler
from croniter import croniter
from sqlalchemy.orm import Session

from fapi.db.models import (
    AutomationWorkflowScheduleORM,
    AutomationWorkflowLogORM,
    AutomationWorkflowORM
)
from fapi.utils.dynamic_weekly_report import send_weekly_marketing_report

logger = logging.getLogger(__name__)


# --------------- Scheduler Auto-Start ---------------

def _run_scheduler_job():
    """Background job that checks the DB for due workflows and executes them."""
    from fapi.db.database import SessionLocal
    db = SessionLocal()
    try:
        check_and_execute_due_workflows(db)
    except Exception as e:
        logger.error(f"Error in scheduler job: {e}")
    finally:
        db.close()


# Create and auto-start the scheduler
_scheduler = BackgroundScheduler()
_scheduler.add_job(_run_scheduler_job, 'interval', minutes=5)
_scheduler.start()
logger.info("Automation Workflow Scheduler started (polling every 5 minutes)")

# Auto-shutdown on app exit
atexit.register(lambda: _scheduler.shutdown())


# --------------- Next Run Calculation ---------------

def _calculate_next_run(schedule: AutomationWorkflowScheduleORM) -> Optional[datetime]:
    """
    Calculate the next run time based on the schedule's frequency.
    
    Anchors to the original next_run_at time (not datetime.now()) to prevent
    time drift. E.g. if scheduled for Monday 9:00 AM weekly, next run will
    always be the following Monday 9:00 AM regardless of when the job
    actually executes.
    """
    anchor = schedule.next_run_at or datetime.now()

    if schedule.frequency == "weekly":
        return anchor + timedelta(weeks=1)
    elif schedule.frequency == "daily":
        return anchor + timedelta(days=1)
    elif schedule.frequency == "monthly":
        year = anchor.year
        month = anchor.month + 1
        if month > 12:
            month = 1
            year += 1
        try:
            return anchor.replace(year=year, month=month)
        except ValueError:
            import calendar
            last_day = calendar.monthrange(year, month)[1]
            return anchor.replace(year=year, month=month, day=min(anchor.day, last_day))
    elif schedule.frequency == "custom" and schedule.cron_expression:
        cron = croniter(schedule.cron_expression, anchor)
        return cron.get_next(datetime)
    elif schedule.frequency == "once":
        return None

    return None


# --------------- Workflow Execution ---------------

def execute_scheduled_workflow(db: Session, schedule: AutomationWorkflowScheduleORM) -> Dict[str, Any]:
    """
    Execute a workflow based on its schedule configuration.
    """
    workflow = schedule.workflow
    run_id = f"{workflow.id}_{datetime.now().timestamp()}"
    execution_start = datetime.now()

    log_entry = AutomationWorkflowLogORM(
        workflow_id=workflow.id,
        schedule_id=schedule.id,
        run_id=run_id,
        status='running',
        started_at=execution_start,
        parameters_used=schedule.run_parameters
    )
    db.add(log_entry)
    db.commit()

    try:
        schedule.is_running = True
        schedule.last_run_at = execution_start

        next_run = _calculate_next_run(schedule)
        schedule.next_run_at = next_run

        if schedule.frequency == "once":
            schedule.enabled = False

        db.commit()

        result = None
        if workflow.workflow_key == "weekly_marketing_report":
            result = send_weekly_marketing_report(db)
            logger.info(f"Weekly marketing report sent: {result}")
        else:
            raise ValueError(f"Unknown workflow: {workflow.workflow_key}")

        log_entry.status = 'success'
        log_entry.records_processed = result.get('records_processed', 0)
        log_entry.execution_metadata = {
            'result': str(result),
            'workflow_key': workflow.workflow_key
        }
        log_entry.finished_at = datetime.now()

    except Exception as e:
        logger.error(f"Error executing workflow {workflow.id}: {e}", exc_info=True)
        log_entry.status = 'failed'
        log_entry.error_summary = str(e)[:255]
        log_entry.error_details = str(e)
        log_entry.finished_at = datetime.now()

    finally:
        schedule.is_running = False
        db.add(log_entry)
        db.commit()

    return {
        'workflow_id': workflow.id,
        'schedule_id': schedule.id,
        'run_id': run_id,
        'status': log_entry.status,
        'executed_at': execution_start.isoformat(),
        'next_run_at': schedule.next_run_at.isoformat() if schedule.next_run_at else None
    }


# --------------- Due Workflow Check ---------------

def check_and_execute_due_workflows(db: Session) -> list:
    """
    Check for workflows that are due to run and execute them.
    """
    try:
        now = datetime.now()
        due_schedules = db.query(AutomationWorkflowScheduleORM).filter(
            AutomationWorkflowScheduleORM.enabled == True,
            AutomationWorkflowScheduleORM.is_running == False,
            AutomationWorkflowScheduleORM.next_run_at <= now
        ).all()

        if due_schedules:
            logger.info(f"Found {len(due_schedules)} due workflow(s) to execute")

        executed = []
        for schedule in due_schedules:
            try:
                result = execute_scheduled_workflow(db, schedule)
                executed.append(result)
                logger.info(f"Successfully executed workflow schedule {schedule.id}: {result}")
            except Exception as e:
                logger.error(f"Failed to execute schedule {schedule.id}: {e}")
                continue

        if executed:
            logger.info(f"Executed {len(executed)} workflow(s)")

        return executed

    except Exception as e:
        logger.error(f"Error checking for due workflows: {e}", exc_info=True)
        return []
