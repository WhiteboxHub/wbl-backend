"""
AIPrep Pure Database Access Layer (CRUD)
=========================================
Isolates all SQL/ORM database operations for AIPrep.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from fapi.ai_prep.models import (
    AiPrepAssessment,
    AiPrepAssessmentORM,
    AiPrepAssessmentData,
    AiPrepAssessmentDataORM,
    AiPrepAssessmentReport,
    AiPrepAssessmentReportORM,
    AiPrepQuestionBank,
    AiPrepQuestionBankORM,
    AiPrepMediaFile,
    AiPrepAnalysisRun,
    AssessmentStatusEnum,
    AssessmentCategoryEnum,
    DifficultyLevelEnum,
    MediaTypeEnum,
    AnalysisRunStatusEnum,
)
from fapi.ai_prep.schemas import CreateAssessmentRequest


# =====================================================================
# 1. Assessment Operations
# =====================================================================
def get_assessment(db: Session, assessment_id: int) -> Optional[AiPrepAssessment]:
    """Fetches single assessment session by ID."""
    return db.query(AiPrepAssessment).filter(AiPrepAssessment.id == assessment_id).first()


get_assessment_by_id = get_assessment


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
    obj_in: Optional[Any] = None,
    assessment_type: Optional[Any] = None,
    media_type: Optional[Any] = None,
    assessment_mode: Optional[Any] = None,
    job_description: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AiPrepAssessment:
    """Creates a new assessment session."""
    if obj_in is not None:
        if isinstance(obj_in, CreateAssessmentRequest) or hasattr(obj_in, "assessment_type"):
            assessment_type_val = (
                obj_in.assessment_type.value
                if hasattr(obj_in.assessment_type, "value")
                else str(obj_in.assessment_type)
            )
            mode = getattr(obj_in, "assessment_mode", None) or getattr(obj_in, "media_type", None) or "VIDEO"
            assessment_mode_val = mode.value if hasattr(mode, "value") else str(mode)
            jd_text = getattr(obj_in, "job_description", None) or getattr(obj_in, "job_description_text", None)
        elif isinstance(obj_in, dict):
            assessment_type_val = obj_in.get("assessment_type", "TECHNICAL")
            assessment_mode_val = obj_in.get("assessment_mode") or obj_in.get("media_type") or "VIDEO"
            jd_text = obj_in.get("job_description") or obj_in.get("job_description_text")
        else:
            assessment_type_val = str(obj_in)
            assessment_mode_val = "VIDEO"
            jd_text = job_description
    else:
        type_val = assessment_type or "TECHNICAL"
        assessment_type_val = type_val.value if hasattr(type_val, "value") else str(type_val)
        mode = media_type or assessment_mode or "VIDEO"
        assessment_mode_val = mode.value if hasattr(mode, "value") else str(mode)
        jd_text = job_description

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
    db: Session, assessment_id: int, status: Any
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
        "COMPLETED",
        "FAILED",
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


update_assessment_youtube_url = update_assessment_media_url


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


list_candidate_assessments = list_assessments_by_candidate


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


# =====================================================================
# 3. Assessment Data (Telemetry) CRUD
# =====================================================================
def create_or_update_assessment_data(
    db: Session,
    assessment_id: int,
    questions: Optional[List[Dict[str, Any]]] = None,
    transcript: Optional[Any] = None,
    audio_telemetry: Optional[Dict[str, Any]] = None,
    video_telemetry: Optional[Dict[str, Any]] = None,
) -> AiPrepAssessmentData:
    """Creates or updates telemetry assessment data for an assessment session."""
    data_record = (
        db.query(AiPrepAssessmentData)
        .filter(AiPrepAssessmentData.assessment_id == assessment_id)
        .first()
    )

    if not data_record:
        data_record = AiPrepAssessmentData(
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


save_assessment_data = create_or_update_assessment_data


def get_assessment_data_by_assessment_id(
    db: Session, assessment_id: int
) -> Optional[AiPrepAssessmentData]:
    """Retrieves assessment telemetry data for a given assessment session."""
    return (
        db.query(AiPrepAssessmentData)
        .filter(AiPrepAssessmentData.assessment_id == assessment_id)
        .first()
    )


get_assessment_data = get_assessment_data_by_assessment_id


# =====================================================================
# 4. Assessment Report CRUD
# =====================================================================
def create_or_update_assessment_report(
    db: Session,
    assessment_id: int,
    audio_evaluation: Optional[Dict[str, Any]] = None,
    video_evaluation: Optional[Dict[str, Any]] = None,
    transcript_evaluation: Optional[Dict[str, Any]] = None,
    composite_score: Optional[float] = None,
) -> AiPrepAssessmentReport:
    """Creates or updates evaluation report data for an assessment session."""
    report_record = (
        db.query(AiPrepAssessmentReport)
        .filter(AiPrepAssessmentReport.assessment_id == assessment_id)
        .first()
    )

    if not report_record:
        report_record = AiPrepAssessmentReport(
            assessment_id=assessment_id,
            audio_evaluation=audio_evaluation,
            video_evaluation=video_evaluation,
            transcript_evaluation=transcript_evaluation,
            composite_score=composite_score,
        )
        db.add(report_record)
    else:
        if audio_evaluation is not None:
            report_record.audio_evaluation = audio_evaluation
        if video_evaluation is not None:
            report_record.video_evaluation = video_evaluation
        if transcript_evaluation is not None:
            report_record.transcript_evaluation = transcript_evaluation
        if composite_score is not None:
            report_record.composite_score = composite_score

    db.commit()
    db.refresh(report_record)
    return report_record


save_assessment_report = create_or_update_assessment_report


def get_assessment_report_by_assessment_id(
    db: Session, assessment_id: int
) -> Optional[AiPrepAssessmentReport]:
    """Retrieves evaluation report data for a given assessment session."""
    return (
        db.query(AiPrepAssessmentReport)
        .filter(AiPrepAssessmentReport.assessment_id == assessment_id)
        .first()
    )


get_assessment_report = get_assessment_report_by_assessment_id


# =====================================================================
# 5. Question Bank CRUD & Filtering
# =====================================================================
def create_question(
    db: Session,
    category: Any,
    difficulty_level: Any = DifficultyLevelEnum.MEDIUM,
    question_text: str = "",
    sub_category: Optional[str] = None,
    is_active: bool = True,
) -> AiPrepQuestionBank:
    """Adds a new question to the question bank."""
    cat_val = category.value if hasattr(category, "value") else str(category)
    diff_val = difficulty_level.value if hasattr(difficulty_level, "value") else str(difficulty_level)
    question = AiPrepQuestionBank(
        category=cat_val,
        subcategory=sub_category,
        difficulty_level=diff_val,
        question_text=question_text,
        is_active=is_active,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def get_question_by_id(db: Session, question_id: int) -> Optional[AiPrepQuestionBank]:
    """Retrieves a question by primary key."""
    return db.query(AiPrepQuestionBank).filter(AiPrepQuestionBank.id == question_id).first()


def list_questions(
    db: Session,
    category: Optional[Any] = None,
    difficulty_level: Optional[Any] = None,
    is_active: Optional[bool] = True,
    limit: int = 100,
    offset: int = 0,
) -> List[AiPrepQuestionBank]:
    """Retrieves questions with optional filtering by category and difficulty."""
    query = db.query(AiPrepQuestionBank)

    if category is not None:
        cat_val = category.value if hasattr(category, "value") else str(category)
        query = query.filter(AiPrepQuestionBank.category == cat_val)
    if difficulty_level is not None:
        diff_val = difficulty_level.value if hasattr(difficulty_level, "value") else str(difficulty_level)
        query = query.filter(AiPrepQuestionBank.difficulty_level == diff_val)
    if is_active is not None:
        query = query.filter(AiPrepQuestionBank.is_active == is_active)

    return query.order_by(AiPrepQuestionBank.id.asc()).offset(offset).limit(limit).all()


list_questions_by_category = list_questions


def update_question(
    db: Session,
    question_id: int,
    sub_category: Optional[str] = None,
    difficulty_level: Optional[Any] = None,
    question_text: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[AiPrepQuestionBank]:
    """Updates fields on an existing question bank record."""
    question = get_question_by_id(db, question_id)
    if not question:
        return None

    if sub_category is not None:
        question.subcategory = sub_category
    if difficulty_level is not None:
        diff_val = difficulty_level.value if hasattr(difficulty_level, "value") else str(difficulty_level)
        question.difficulty_level = diff_val
    if question_text is not None:
        question.question_text = question_text
    if is_active is not None:
        question.is_active = is_active

    db.commit()
    db.refresh(question)
    return question
