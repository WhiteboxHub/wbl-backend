from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from fapi.ai_prep.models import AiPrepAnalysisRunORM, RunTypeEnum, RunStatusEnum


def create_analysis_run(
    db: Session,
    assessment_id: int,
    run_type: RunTypeEnum,
    celery_task_id: Optional[str] = None,
    status: RunStatusEnum = RunStatusEnum.RUNNING
) -> AiPrepAnalysisRunORM:
    """Create a new analysis run record for tracking a processing stage."""
    run = AiPrepAnalysisRunORM(
        assessment_id=assessment_id,
        run_type=run_type,
        status=status,
        started_at=datetime.utcnow(),
        celery_task_id=celery_task_id
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def update_analysis_run_status(
    db: Session,
    run_id: int,
    status: RunStatusEnum,
    error_message: Optional[str] = None
) -> Optional[AiPrepAnalysisRunORM]:
    """Update status and completion timestamp for an analysis run."""
    run = db.query(AiPrepAnalysisRunORM).filter(AiPrepAnalysisRunORM.id == run_id).first()
    if run:
        run.status = status
        if status in [RunStatusEnum.COMPLETED, RunStatusEnum.FAILED]:
            run.completed_at = datetime.utcnow()
        if error_message:
            run.error_message = error_message
        db.commit()
        db.refresh(run)
    return run


def get_runs_by_assessment_id(db: Session, assessment_id: int) -> List[AiPrepAnalysisRunORM]:
    """Get all analysis runs for an assessment ordered by created_at."""
    return db.query(AiPrepAnalysisRunORM).filter(
        AiPrepAnalysisRunORM.assessment_id == assessment_id
    ).order_by(AiPrepAnalysisRunORM.created_at.asc()).all()


def get_latest_run_by_type(
    db: Session,
    assessment_id: int,
    run_type: RunTypeEnum
) -> Optional[AiPrepAnalysisRunORM]:
    """Get the latest analysis run for a specific run_type."""
    return db.query(AiPrepAnalysisRunORM).filter(
        AiPrepAnalysisRunORM.assessment_id == assessment_id,
        AiPrepAnalysisRunORM.run_type == run_type
    ).order_by(AiPrepAnalysisRunORM.id.desc()).first()
