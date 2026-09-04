"""
AIPrep Pure Database Access Layer (CRUD)
=========================================
Isolates all SQL/ORM database operations for AIPrep.
Zero business logic. Core engines and external clients must never query DB directly.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from fapi.ai_prep.models import (
    AiPrepAssessment,
    AiPrepAssessmentData,
    AiPrepAssessmentReport,
    AiPrepQuestionBank,
    AiPrepMediaFile,
    AiPrepAnalysisRun,
    AssessmentStatusEnum,
    AnalysisRunStatusEnum,
)
from fapi.ai_prep.schemas import CreateAssessmentRequest


# =====================================================================
# 1. Assessment Operations
# =====================================================================
def get_assessment(db: Session, assessment_id: int) -> Optional[AiPrepAssessment]:
    """Fetches single assessment session by ID."""
    return db.query(AiPrepAssessment).filter(AiPrepAssessment.id == assessment_id).first()


def get_assessment_by_id_and_candidate(
    db: Session, assessment_id: int, candidate_id: int
) -> Optional[AiPrepAssessment]:
    """Fetches assessment session verifying candidate ownership."""
    return (
        db.query(AiPrepAssessment)
        .filter(
            AiPrepAssessment.id == assessment_id,
            AiPrepAssessment.candidate_id == candidate_id,
        )
        .first()
    )


def create_assessment(
    db: Session,
    candidate_id: int,
    obj_in: CreateAssessmentRequest,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AiPrepAssessment:
    """Creates a new assessment session."""
    assessment_type_val = (
        obj_in.assessment_type.value
        if hasattr(obj_in.assessment_type, "value")
        else str(obj_in.assessment_type)
    )
    assessment_mode_val = (
        obj_in.assessment_mode.value
        if hasattr(obj_in.assessment_mode, "value")
        else str(obj_in.assessment_mode)
    )
    jd_text = obj_in.job_description or obj_in.job_description_text

    db_obj = AiPrepAssessment(
        candidate_id=candidate_id,
        assessment_type=assessment_type_val,
        assessment_mode=assessment_mode_val,
        status=AssessmentStatusEnum.IN_PROGRESS.value,
        job_description=jd_text,
        ip_address=ip_address,
        user_agent=user_agent,
        started_at=datetime.utcnow(),
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_assessment_status(
    db: Session, assessment_id: int, status: str
) -> Optional[AiPrepAssessment]:
    """Updates status and completed_at timestamp if terminal."""
    assessment = get_assessment(db, assessment_id)
    if not assessment:
        return None

    status_val = status.value if hasattr(status, "value") else str(status)
    assessment.status = status_val
    if status_val in {
        AssessmentStatusEnum.COMPLETED.value,
        AssessmentStatusEnum.FAILED.value,
    }:
        assessment.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(assessment)
    return assessment


def update_assessment_media_url(
    db: Session, assessment_id: int, youtube_url: str
) -> Optional[AiPrepAssessment]:
    """Updates YouTube watch URL for assessment session."""
    assessment = get_assessment(db, assessment_id)
    if not assessment:
        return None

    assessment.youtube_url = youtube_url
    db.commit()
    db.refresh(assessment)
    return assessment


def list_assessments_by_candidate(
    db: Session, candidate_id: int, limit: int = 50, offset: int = 0
) -> List[AiPrepAssessment]:
    """Retrieves paginated assessment history for candidate."""
    return (
        db.query(AiPrepAssessment)
        .filter(AiPrepAssessment.candidate_id == candidate_id)
        .order_by(AiPrepAssessment.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


# =====================================================================
# 2. Media & Analysis Task Runs (BE2 Operational)
# =====================================================================
def create_media_file(
    db: Session,
    assessment_id: int,
    audio_file_path: Optional[str] = None,
    video_file_path: Optional[str] = None,
    file_size_bytes: Optional[int] = None,
) -> AiPrepMediaFile:
    """Creates or updates operational media file record."""
    media = (
        db.query(AiPrepMediaFile)
        .filter(AiPrepMediaFile.assessment_id == assessment_id)
        .first()
    )
    if not media:
        media = AiPrepMediaFile(
            assessment_id=assessment_id,
            audio_file_path=audio_file_path,
            video_file_path=video_file_path,
            file_size_bytes=file_size_bytes,
        )
        db.add(media)
    else:
        if audio_file_path:
            media.audio_file_path = audio_file_path
        if video_file_path:
            media.video_file_path = video_file_path
        if file_size_bytes:
            media.file_size_bytes = file_size_bytes

    db.commit()
    db.refresh(media)
    return media


def get_media_file_by_assessment(
    db: Session, assessment_id: int
) -> Optional[AiPrepMediaFile]:
    """Gets media file record for assessment."""
    return (
        db.query(AiPrepMediaFile)
        .filter(AiPrepMediaFile.assessment_id == assessment_id)
        .first()
    )


def create_analysis_run(
    db: Session,
    assessment_id: int,
    run_type: str,
    status: str = AnalysisRunStatusEnum.PENDING.value,
    celery_task_id: Optional[str] = None,
) -> AiPrepAnalysisRun:
    """Creates a tracking run for an asynchronous worker task."""
    run = AiPrepAnalysisRun(
        assessment_id=assessment_id,
        run_type=run_type,
        status=status,
        celery_task_id=celery_task_id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def update_analysis_run_status(
    db: Session,
    run_id: int,
    status: str,
    error_message: Optional[str] = None,
) -> Optional[AiPrepAnalysisRun]:
    """Updates status and error information on an async task run."""
    run = db.query(AiPrepAnalysisRun).filter(AiPrepAnalysisRun.id == run_id).first()
    if not run:
        return None

    run.status = status
    if error_message:
        run.error_message = error_message
    db.commit()
    db.refresh(run)
    return run


def get_analysis_runs_by_assessment(
    db: Session, assessment_id: int
) -> List[AiPrepAnalysisRun]:
    """Lists all task analysis runs for an assessment."""
    return (
        db.query(AiPrepAnalysisRun)
        .filter(AiPrepAnalysisRun.assessment_id == assessment_id)
        .order_by(AiPrepAnalysisRun.created_at.asc())
        .all()
    )
