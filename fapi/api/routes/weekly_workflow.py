from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
try:
    from croniter import croniter
except ImportError:
    croniter = None

from fapi.db.database import get_db
from fapi.db.models import CandidateMarketingORM, AutomationWorkflowScheduleORM
from fapi.utils.permission_gate import enforce_access

router = APIRouter()

SCHEDULE_ID = 7  # automation_workflows_schedule.id for weekly_automation_application_engine


def _compute_next_run(schedule: AutomationWorkflowScheduleORM) -> datetime | None:
    """Compute next_run_at from the schedule's own cron or frequency settings."""
    now = datetime.utcnow()

    if schedule.cron_expression and croniter:
        try:
            return croniter(schedule.cron_expression, now).get_next(datetime)
        except Exception:
            pass

    freq_map = {
        "daily":   timedelta(days=schedule.interval_value or 1),
        "weekly":  timedelta(weeks=schedule.interval_value or 1),
        "monthly": timedelta(days=(schedule.interval_value or 1) * 30),
        "custom":  timedelta(days=schedule.interval_value or 1),
    }
    delta = freq_map.get((schedule.frequency or "").lower())
    return (now + delta) if delta else None


@router.get("/trigger-run")
def trigger_run(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Single atomic endpoint for the Job Application Engine (1 API call, no follow-up).

    In one DB transaction:
      1. JOIN candidate_marketing + automation_workflows_schedule (id=SCHEDULE_ID)
      2. Copy  candidate_json → schedule.run_parameters
      3. Set   schedule.last_run_at = NOW()
      4. Set   schedule.next_run_at = computed from schedule's own cron / frequency
      5. Reset candidate_marketing.run_weekly_workflow = 0
      6. Return run_parameters → engine starts immediately

    Returns {} if no triggered candidate found — engine exits cleanly.
    """
    # Fetch the first active candidate without relying on a strict inner join
    candidate = db.query(CandidateMarketingORM).filter(CandidateMarketingORM.run_weekly_workflow == 1).first()

    if not candidate:
        return {}

    # Update the schedule if it exists
    schedule = db.query(AutomationWorkflowScheduleORM).filter(AutomationWorkflowScheduleORM.id == SCHEDULE_ID).first()
    if schedule:
        schedule.last_run_at = datetime.utcnow()
        schedule.next_run_at = _compute_next_run(schedule)
    
    # Reset candidate workflow so it doesn't loop
    candidate.run_weekly_workflow = 0
    db.commit()

    # Return the full flat dictionary so the Python Engine's run_parameters_builder can use it!
    return {
        "candidate_id": getattr(candidate, "candidate_id", ""),
        "email": getattr(candidate, "email", ""),
        "password": getattr(candidate, "password", ""),
        "resume_url": getattr(candidate, "resume_url", ""),
        "google_voice_number": getattr(candidate, "google_voice_number", ""),
        "linkedin_username": getattr(candidate, "linkedin_username", ""),
        "linkedin_passwd": getattr(candidate, "linkedin_passwd", ""),
        "candidate_intro": getattr(candidate, "candidate_intro", ""),
    }


@router.get("/eligible-candidates", dependencies=[Depends(enforce_access)])
def get_eligible_candidates(db: Session = Depends(get_db)):
    """Fetch candidates where run_weekly_workflow = 1 (UI / manual use)."""
    return db.query(CandidateMarketingORM).filter(
        CandidateMarketingORM.run_weekly_workflow == 1
    ).all()


@router.post("/reset/{candidate_id}", dependencies=[Depends(enforce_access)])
def reset_candidate_workflow(candidate_id: int, db: Session = Depends(get_db)):
    """Manually reset run_weekly_workflow = 0 for a candidate."""
    candidate = db.query(CandidateMarketingORM).filter(
        CandidateMarketingORM.candidate_id == candidate_id
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate marketing record not found")
    candidate.run_weekly_workflow = 0
    db.commit()
    return {"message": f"Reset run_weekly_workflow=0 for candidate_id={candidate_id}"}