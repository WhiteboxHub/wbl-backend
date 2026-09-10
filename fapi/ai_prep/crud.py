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
    AiPrepMediaFileORM,
    AiPrepMediaTaskRunORM,
)
from fapi.ai_prep.schemas import (
    AssessmentCategoryEnum,
    DifficultyLevelEnum,
    MediaTypeEnum,
    AssessmentStatusEnum,
    MediaTaskStatusEnum,
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


def list_assessments_for_employee(
    db: Session, candidate_id: Optional[int] = None, limit: int = 50, offset: int = 0
) -> List[AiPrepAssessmentORM]:
    """Retrieves all assessments for employee/admin view, optionally filtered by candidate_id."""
    query = db.query(AiPrepAssessmentORM)
    if candidate_id is not None:
        query = query.filter(AiPrepAssessmentORM.candidate_id == candidate_id)
    return query.order_by(AiPrepAssessmentORM.created_at.desc()).offset(offset).limit(limit).all()



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
        report_record.audio_evaluation = audio_evaluation
        report_record.video_evaluation = video_evaluation
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
    category: Optional[AssessmentCategoryEnum] = None,
    sub_category: Optional[str] = None,
    difficulty_level: Optional[DifficultyLevelEnum] = None,
    question_text: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[AiPrepQuestionBankORM]:
    """Updates fields on an existing question bank record while preserving DB CheckConstraints."""
    question = get_question_by_id(db, question_id)
    if not question:
        return None

    if category is not None:
        question.category = category

    effective_cat = question.category
    cat_val = effective_cat.value if hasattr(effective_cat, "value") else str(effective_cat)

    if sub_category is not None:
        if cat_val == "TECHNICAL":
            question.sub_category = sub_category
        else:
            question.sub_category = None
    elif cat_val != "TECHNICAL":
        question.sub_category = None

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
get_assessment = get_assessment_by_id


# ─── Media Files & Media Task Runs CRUD (BE2) ─────────────────────────────────

def create_media_file_record(
    db: Session,
    assessment_id: int,
    video_file_path: Optional[str] = None,
    audio_file_path: Optional[str] = None,
    file_size_bytes: Optional[int] = None,
) -> AiPrepMediaFileORM:
    """Records assembled media file paths for an assessment."""
    rec = (
        db.query(AiPrepMediaFileORM)
        .filter(AiPrepMediaFileORM.assessment_id == assessment_id)
        .first()
    )
    if not rec:
        rec = AiPrepMediaFileORM(
            assessment_id=assessment_id,
            video_file_path=video_file_path,
            audio_file_path=audio_file_path,
            file_size_bytes=file_size_bytes,
        )
        db.add(rec)
    else:
        if video_file_path is not None:
            rec.video_file_path = video_file_path
        if audio_file_path is not None:
            rec.audio_file_path = audio_file_path
        if file_size_bytes is not None:
            rec.file_size_bytes = file_size_bytes
    db.commit()
    db.refresh(rec)
    return rec


create_media_file = create_media_file_record


def get_media_file_by_assessment_id(
    db: Session, assessment_id: int
) -> Optional[AiPrepMediaFileORM]:
    return (
        db.query(AiPrepMediaFileORM)
        .filter(AiPrepMediaFileORM.assessment_id == assessment_id)
        .first()
    )


get_media_file = get_media_file_by_assessment_id


def create_media_task_run(
    db: Session,
    assessment_id: int,
    task_type: str,
    status: str = MediaTaskStatusEnum.PENDING.value,
    celery_task_id: Optional[str] = None,
    error_message: Optional[str] = None,
) -> AiPrepMediaTaskRunORM:
    task_run = AiPrepMediaTaskRunORM(
        assessment_id=assessment_id,
        task_type=task_type,
        status=status,
        celery_task_id=celery_task_id,
        error_message=error_message,
    )
    db.add(task_run)
    db.commit()
    db.refresh(task_run)
    return task_run


create_analysis_run = create_media_task_run


def get_media_task_run(
    db: Session, assessment_id: int, task_type: str
) -> Optional[AiPrepMediaTaskRunORM]:
    return (
        db.query(AiPrepMediaTaskRunORM)
        .filter(
            AiPrepMediaTaskRunORM.assessment_id == assessment_id,
            AiPrepMediaTaskRunORM.task_type == task_type,
        )
        .order_by(AiPrepMediaTaskRunORM.created_at.desc())
        .first()
    )


get_analysis_run = get_media_task_run


def get_media_task_runs_by_assessment_id(
    db: Session, assessment_id: int
) -> List[AiPrepMediaTaskRunORM]:
    return (
        db.query(AiPrepMediaTaskRunORM)
        .filter(AiPrepMediaTaskRunORM.assessment_id == assessment_id)
        .order_by(AiPrepMediaTaskRunORM.created_at.asc())
        .all()
    )


get_analysis_runs = get_media_task_runs_by_assessment_id


def update_media_task_run_status(
    db: Session,
    assessment_id: int,
    task_type: str,
    status: str,
    error_message: Optional[str] = None,
) -> Optional[AiPrepMediaTaskRunORM]:
    task_run = get_media_task_run(db, assessment_id, task_type)
    if not task_run:
        task_run = create_media_task_run(db, assessment_id, task_type, status=status)
    task_run.status = status
    if error_message is not None:
        task_run.error_message = error_message
    db.commit()
    db.refresh(task_run)
    return task_run


update_analysis_run_status = update_media_task_run_status


# ─── Candidate Resume CRUD ────────────────────────────────────────────────────

def get_candidate_resume_json(db: Session, candidate_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetches the parsed resume JSON for a candidate from candidate_marketing.candidate_json.

    The marketing record holds the structured resume (candidate_json) which is the
    primary career reference used by the LLM transcript evaluation prompt.

    Returns:
        The candidate_json dict if found, or None if no marketing record exists.
    """
    from fapi.db.models import CandidateMarketingORM

    row = (
        db.query(CandidateMarketingORM)
        .filter(CandidateMarketingORM.candidate_id == candidate_id)
        .order_by(CandidateMarketingORM.id.desc())
        .first()
    )

    if row is None or row.candidate_json is None:
        return None

    if isinstance(row.candidate_json, str):
        try:
            import json
            return json.loads(row.candidate_json)
        except Exception:
            return None

    return row.candidate_json


def save_candidate_resume_json(
    db: Session, candidate_id: int, resume_json: Dict[str, Any]
) -> Any:
    """Saves or updates candidate_json in CandidateMarketingORM for a candidate."""
    from datetime import datetime
    from fapi.db.models import CandidateMarketingORM

    row = (
        db.query(CandidateMarketingORM)
        .filter(CandidateMarketingORM.candidate_id == candidate_id)
        .order_by(CandidateMarketingORM.id.desc())
        .first()
    )
    if not row:
        row = CandidateMarketingORM(
            candidate_id=candidate_id,
            candidate_json=resume_json,
            start_date=datetime.now(timezone.utc).date(),
            status="active",
        )
        if hasattr(row, "last_mod_datetime"):
            setattr(row, "last_mod_datetime", datetime.now(timezone.utc))
        db.add(row)
    else:
        row.candidate_json = resume_json
        if hasattr(row, "last_mod_datetime"):
            setattr(row, "last_mod_datetime", datetime.now(timezone.utc))
    db.commit()
    db.refresh(row)
    return row


# ─── Candidate LLM Configuration CRUD ─────────────────────────────────────────

def get_candidate_llm_config(db: Session, candidate_id: int) -> Dict[str, Any]:
    """
    Query the candidate_llm_api_keys table for the highest-priority active key.

    Priority order (matching coderpad_openai_key.py pattern):
        is_default DESC → updated_at DESC → id DESC

    Returns:
        {
            "api_key": str,          # plain-text decrypted key
            "provider": str,         # e.g. "openai", "gemini", "anthropic"
            "model": str | None,     # preferred model name, may be None → client uses default
        }

    Raises:
        ValueError: If no active key exists for this candidate.
    """
    from fapi.db.models import CandidateLlmApiKeyORM
    from fapi.utils.encryption_utils import decrypt_api_key

    row = (
        db.query(CandidateLlmApiKeyORM)
        .filter(
            CandidateLlmApiKeyORM.candidate_id == candidate_id,
            CandidateLlmApiKeyORM.status == "active",
        )
        .order_by(
            CandidateLlmApiKeyORM.is_default.desc(),
            CandidateLlmApiKeyORM.updated_at.desc(),
            CandidateLlmApiKeyORM.id.desc(),
        )
        .first()
    )

    if row is None:
        import os
        env_key = os.getenv("OPENAI_API_KEY")
        if env_key:
            return {
                "api_key": env_key,
                "provider": "openai",
                "model": "gpt-4o",
            }
        raise ValueError(
            f"No active LLM API key found for candidate_id={candidate_id}. "
            "Please add a valid API key in the AI Prep settings."
        )

    plain_key = decrypt_api_key(row.api_key)
    return {
        "api_key": plain_key,
        "provider": row.provider_name,
        "model": row.model_name,
    }
