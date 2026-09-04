"""
CRUD — Database Access Layer for AI Prep Assessment Platform.

All database queries (db.query) are strictly isolated here.
Engines and Orchestrators must use these functions rather than making raw queries directly.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from fapi.ai_prep.models import (
    AiPrepQuestionBankORM,
    AiPrepAssessmentORM,
    AiPrepAssessmentDataORM,
    AiPrepAssessmentReportORM,
)
from fapi.ai_prep.schemas import (
    AssessmentCategoryEnum,
    DifficultyLevelEnum,
    MediaTypeEnum,
    AssessmentStatusEnum,
)


# ─── Assessment CRUD ──────────────────────────────────────────────────────────

def create_assessment(
    db: Session,
    candidate_id: int,
    assessment_type: AssessmentCategoryEnum,
    media_type: MediaTypeEnum,
    job_description: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AiPrepAssessmentORM:
    """Creates a new assessment record with IN_PROGRESS status."""
    assessment = AiPrepAssessmentORM(
        candidate_id=candidate_id,
        assessment_type=assessment_type,
        media_type=media_type,
        status=AssessmentStatusEnum.IN_PROGRESS,
        job_description=job_description,
        ip_address=ip_address,
        user_agent=user_agent,
        started_at=datetime.utcnow(),
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


def get_assessment_by_id(db: Session, assessment_id: int) -> Optional[AiPrepAssessmentORM]:
    """Retrieves an assessment record by primary key."""
    return db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()


def update_assessment_status(
    db: Session, assessment_id: int, status: AssessmentStatusEnum
) -> Optional[AiPrepAssessmentORM]:
    """Updates the status of an assessment record."""
    assessment = get_assessment_by_id(db, assessment_id)
    if not assessment:
        return None

    assessment.status = status
    if status in (AssessmentStatusEnum.COMPLETED, AssessmentStatusEnum.FAILED):
        assessment.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(assessment)
    return assessment


def update_assessment_youtube_url(
    db: Session, assessment_id: int, youtube_url: str
) -> Optional[AiPrepAssessmentORM]:
    """Updates the youtube_url field on an assessment record."""
    assessment = get_assessment_by_id(db, assessment_id)
    if not assessment:
        return None

    assessment.youtube_url = youtube_url
    db.commit()
    db.refresh(assessment)
    return assessment


def list_candidate_assessments(
    db: Session, candidate_id: int, limit: int = 50, offset: int = 0
) -> List[AiPrepAssessmentORM]:
    """Retrieves a paginated list of assessments for a specific candidate."""
    return (
        db.query(AiPrepAssessmentORM)
        .filter(AiPrepAssessmentORM.candidate_id == candidate_id)
        .order_by(AiPrepAssessmentORM.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


# ─── Assessment Data (Telemetry) CRUD ──────────────────────────────────────────

def create_or_update_assessment_data(
    db: Session,
    assessment_id: int,
    questions: Optional[List[Dict[str, Any]]] = None,
    transcript: Optional[Dict[str, Any]] = None,
    audio_telemetry: Optional[Dict[str, Any]] = None,
    video_telemetry: Optional[Dict[str, Any]] = None,
) -> AiPrepAssessmentDataORM:
    """Creates or updates telemetry assessment data for an assessment session."""
    data_record = (
        db.query(AiPrepAssessmentDataORM)
        .filter(AiPrepAssessmentDataORM.assessment_id == assessment_id)
        .first()
    )

    if not data_record:
        data_record = AiPrepAssessmentDataORM(
            assessment_id=assessment_id,
            questions=questions,
            transcript=transcript,
            audio_telemetry=audio_telemetry,
            video_telemetry=video_telemetry,
        )
        db.add(data_record)
    else:
        if questions is not None:
            data_record.questions = questions
        if transcript is not None:
            data_record.transcript = transcript
        if audio_telemetry is not None:
            data_record.audio_telemetry = audio_telemetry
        if video_telemetry is not None:
            data_record.video_telemetry = video_telemetry

    db.commit()
    db.refresh(data_record)
    return data_record


def get_assessment_data_by_assessment_id(
    db: Session, assessment_id: int
) -> Optional[AiPrepAssessmentDataORM]:
    """Retrieves assessment telemetry data for a given assessment session."""
    return (
        db.query(AiPrepAssessmentDataORM)
        .filter(AiPrepAssessmentDataORM.assessment_id == assessment_id)
        .first()
    )


# ─── Assessment Report CRUD ───────────────────────────────────────────────────

def create_or_update_assessment_report(
    db: Session,
    assessment_id: int,
    audio_evaluation: Optional[Dict[str, Any]] = None,
    video_evaluation: Optional[Dict[str, Any]] = None,
    transcript_evaluation: Optional[Dict[str, Any]] = None,
) -> AiPrepAssessmentReportORM:
    """Creates or updates evaluation report data for an assessment session."""
    report_record = (
        db.query(AiPrepAssessmentReportORM)
        .filter(AiPrepAssessmentReportORM.assessment_id == assessment_id)
        .first()
    )

    if not report_record:
        report_record = AiPrepAssessmentReportORM(
            assessment_id=assessment_id,
            audio_evaluation=audio_evaluation,
            video_evaluation=video_evaluation,
            transcript_evaluation=transcript_evaluation,
        )
        db.add(report_record)
    else:
        if audio_evaluation is not None:
            report_record.audio_evaluation = audio_evaluation
        if video_evaluation is not None:
            report_record.video_evaluation = video_evaluation
        if transcript_evaluation is not None:
            report_record.transcript_evaluation = transcript_evaluation

    db.commit()
    db.refresh(report_record)
    return report_record


def get_assessment_report_by_assessment_id(
    db: Session, assessment_id: int
) -> Optional[AiPrepAssessmentReportORM]:
    """Retrieves evaluation report data for a given assessment session."""
    return (
        db.query(AiPrepAssessmentReportORM)
        .filter(AiPrepAssessmentReportORM.assessment_id == assessment_id)
        .first()
    )


# ─── Question Bank CRUD & Round-Robin ─────────────────────────────────────────

def create_question(
    db: Session,
    category: AssessmentCategoryEnum,
    difficulty_level: DifficultyLevelEnum,
    question_text: str,
    sub_category: Optional[str] = None,
    is_active: bool = True,
) -> AiPrepQuestionBankORM:
    """Adds a new question to the question bank."""
    question = AiPrepQuestionBankORM(
        category=category,
        sub_category=sub_category,
        difficulty_level=difficulty_level,
        question_text=question_text,
        is_active=is_active,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def get_question_by_id(db: Session, question_id: int) -> Optional[AiPrepQuestionBankORM]:
    """Retrieves a question by primary key."""
    return db.query(AiPrepQuestionBankORM).filter(AiPrepQuestionBankORM.id == question_id).first()


def list_questions(
    db: Session,
    category: Optional[AssessmentCategoryEnum] = None,
    difficulty_level: Optional[DifficultyLevelEnum] = None,
    is_active: Optional[bool] = True,
    limit: int = 100,
    offset: int = 0,
) -> List[AiPrepQuestionBankORM]:
    """Retrieves questions with optional filtering by category and difficulty."""
    query = db.query(AiPrepQuestionBankORM)

    if category is not None:
        query = query.filter(AiPrepQuestionBankORM.category == category)
    if difficulty_level is not None:
        query = query.filter(AiPrepQuestionBankORM.difficulty_level == difficulty_level)
    if is_active is not None:
        query = query.filter(AiPrepQuestionBankORM.is_active == is_active)

    return query.order_by(AiPrepQuestionBankORM.id.asc()).offset(offset).limit(limit).all()


def update_question(
    db: Session,
    question_id: int,
    sub_category: Optional[str] = None,
    difficulty_level: Optional[DifficultyLevelEnum] = None,
    question_text: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[AiPrepQuestionBankORM]:
    """Updates fields on an existing question bank record."""
    question = get_question_by_id(db, question_id)
    if not question:
        return None

    if sub_category is not None:
        question.sub_category = sub_category
    if difficulty_level is not None:
        question.difficulty_level = difficulty_level
    if question_text is not None:
        question.question_text = question_text
    if is_active is not None:
        question.is_active = is_active

    db.commit()
    db.refresh(question)
    return question


# Aliases for backwards compatibility across Orchestrator and Router calls
save_assessment_data = create_or_update_assessment_data
get_assessment_data = get_assessment_data_by_assessment_id
save_assessment_report = create_or_update_assessment_report
get_assessment_report = get_assessment_report_by_assessment_id
list_questions_by_category = list_questions
