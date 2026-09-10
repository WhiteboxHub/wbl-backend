"""Database CRUD operations for AI Prep Tool.
Strictly matches V134 DDL table structure — 4 tables only.
All DB queries are isolated here; engines and orchestrators must not make raw queries.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc
from sqlalchemy.orm import Session

from fapi.ai_prep.models import (
    AiPrepAssessmentDataORM,
    AiPrepAssessmentORM,
    AiPrepAssessmentReportORM,
    AiPrepQuestionBankORM,
)
from fapi.db.models import (
    CandidateLlmApiKeyORM,
    CandidateMarketingORM,
    CandidateORM,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Assessment Types Catalog (in-memory — no DB table in V134)
# ---------------------------------------------------------------------------

def list_assessment_types() -> List[Dict[str, Any]]:
    """Returns the hardcoded assessment types catalog."""
    return [
        {
            "id": 1, "code": "INTRO", "title": "Intro Assessment",
            "description": "Standard introductory background, soft skills, and career narrative assessment.",
            "category": "GENERAL", "time_estimate_mins": 4, "is_active": True,
        },
        {
            "id": 2, "code": "JD_INTRO", "title": "JD Intro Assessment",
            "description": "Job description-aligned introductory walkthrough.",
            "category": "ROLE_SPECIFIC", "time_estimate_mins": 4, "is_active": True,
        },
        {
            "id": 3, "code": "RECRUITER", "title": "Recruiter Screen",
            "description": "Recruiter-style screening covering motivation, cultural fit, and logistics.",
            "category": "SCREENING", "time_estimate_mins": 10, "is_active": True,
        },
        {
            "id": 4, "code": "HIRING_MANAGER", "title": "Hiring Manager Round",
            "description": "In-depth hiring manager interview exploring project ownership and delivery.",
            "category": "MANAGEMENT", "time_estimate_mins": 15, "is_active": True,
        },
        {
            "id": 5, "code": "SYSTEM_DESIGN", "title": "System Design",
            "description": "Architectural breakdown covering scalability, trade-offs, and GenAI/RAG pipelines.",
            "category": "TECHNICAL", "time_estimate_mins": 25, "is_active": True,
        },
        {
            "id": 6, "code": "TECHNICAL", "title": "Technical Assessment",
            "description": "Deep technical evaluation covering core engineering, frameworks, and algorithms.",
            "category": "TECHNICAL", "time_estimate_mins": 30, "is_active": True,
        },
    ]


def get_assessment_type_by_code(code: str) -> Optional[Dict[str, Any]]:
    for t in list_assessment_types():
        if t["code"].upper() == code.upper():
            return t
    return None


def get_default_questions() -> List[Dict[str, Any]]:
    """Standard fallback questions used when question bank is empty."""
    return [
        {
            "category": "INTRO", "sub_category": None, "difficulty_level": "MEDIUM",
            "question_text": "Tell me about yourself, your background, and your experience building production AI and software systems.",
        },
        {
            "category": "JD_INTRO", "sub_category": None, "difficulty_level": "MEDIUM",
            "question_text": "How does your technical experience match the key requirements and tech stack of this job description?",
        },
        {
            "category": "RECRUITER", "sub_category": None, "difficulty_level": "MEDIUM",
            "question_text": "Walk me through your recent career transitions and what motivates you to pursue this next role.",
        },
        {
            "category": "HIRING_MANAGER", "sub_category": None, "difficulty_level": "HARD",
            "question_text": "Describe a high-stakes project you led where you encountered significant blockers. How did you resolve them?",
        },
        {
            "category": "SYSTEM_DESIGN", "sub_category": None, "difficulty_level": "HARD",
            "question_text": "Design a high-throughput, low-latency RAG pipeline that handles multi-tenant enterprise documents.",
        },
        {
            "category": "TECHNICAL", "sub_category": "Agentic AI", "difficulty_level": "HARD",
            "question_text": "Explain the difference between ReAct patterns and Plan-and-Solve agent frameworks.",
        },
    ]


# ---------------------------------------------------------------------------
# Assessments CRUD
# ---------------------------------------------------------------------------

def create_assessment(
    db: Session,
    candidate_id: int,
    assessment_type: str,
    media_type: str,
    job_description: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AiPrepAssessmentORM:
    """Creates a new assessment record with status IN_PROGRESS."""
    db_obj = AiPrepAssessmentORM(
        candidate_id=candidate_id,
        assessment_type=assessment_type,
        media_type=media_type,
        status="IN_PROGRESS",
        job_description=job_description,
        ip_address=ip_address,
        user_agent=user_agent,
        started_at=datetime.now(timezone.utc),
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_assessment_by_id(db: Session, assessment_id: int) -> Optional[AiPrepAssessmentORM]:
    return db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()


def list_assessments(
    db: Session,
    candidate_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[AiPrepAssessmentORM], int]:
    query = db.query(AiPrepAssessmentORM)
    if candidate_id is not None:
        query = query.filter(AiPrepAssessmentORM.candidate_id == candidate_id)
    if status:
        query = query.filter(AiPrepAssessmentORM.status == status)
    total = query.count()
    items = query.order_by(desc(AiPrepAssessmentORM.created_at)).offset(offset).limit(limit).all()
    return items, total


def list_candidate_assessments(
    db: Session,
    candidate_id: int,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[AiPrepAssessmentORM], int]:
    return list_assessments(db, candidate_id=candidate_id, limit=limit, offset=offset)


def list_assessments_for_employee(
    db: Session,
    candidate_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[AiPrepAssessmentORM], int]:
    return list_assessments(db, candidate_id=candidate_id, status=status, limit=limit, offset=offset)


def update_assessment_media_url(db: Session, assessment_id: int, youtube_url: str) -> Optional[AiPrepAssessmentORM]:
    assessment = get_assessment_by_id(db, assessment_id)
    if not assessment:
        return None
    assessment.youtube_url = youtube_url
    db.commit()
    db.refresh(assessment)
    return assessment


# Alias
update_assessment_youtube_url = update_assessment_media_url


def update_assessment_status(db: Session, assessment_id: int, status: str) -> Optional[AiPrepAssessmentORM]:
    assessment = get_assessment_by_id(db, assessment_id)
    if not assessment:
        return None
    assessment.status = status
    if status in ("COMPLETED", "FAILED"):
        assessment.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(assessment)
    return assessment


# ---------------------------------------------------------------------------
# Assessment Data CRUD
# ---------------------------------------------------------------------------

def save_assessment_data(
    db: Session,
    assessment_id: int,
    questions: List[Dict[str, Any]],
    transcript: Dict[str, Any],
    audio_telemetry: Dict[str, Any],
    video_telemetry: Dict[str, Any],
) -> AiPrepAssessmentDataORM:
    existing = (
        db.query(AiPrepAssessmentDataORM)
        .filter(AiPrepAssessmentDataORM.assessment_id == assessment_id)
        .first()
    )
    if existing:
        existing.questions = questions
        existing.transcript = transcript
        existing.audio_telemetry = audio_telemetry
        existing.video_telemetry = video_telemetry
        db_obj = existing
    else:
        db_obj = AiPrepAssessmentDataORM(
            assessment_id=assessment_id,
            questions=questions,
            transcript=transcript,
            audio_telemetry=audio_telemetry,
            video_telemetry=video_telemetry,
        )
        db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


# Alias
create_or_update_assessment_data = save_assessment_data


def get_assessment_data_by_assessment_id(db: Session, assessment_id: int) -> Optional[AiPrepAssessmentDataORM]:
    return (
        db.query(AiPrepAssessmentDataORM)
        .filter(AiPrepAssessmentDataORM.assessment_id == assessment_id)
        .first()
    )


# ---------------------------------------------------------------------------
# Assessment Report CRUD
# ---------------------------------------------------------------------------

def save_assessment_report(
    db: Session,
    assessment_id: int,
    parsed_report: Dict[str, Any],
) -> AiPrepAssessmentReportORM:
    """Creates or updates the evaluation report for an assessment.
    NOTE: The V134 DDL report table has only 3 JSON eval columns (no overall_score, no report_data).
    """
    existing = (
        db.query(AiPrepAssessmentReportORM)
        .filter(AiPrepAssessmentReportORM.assessment_id == assessment_id)
        .first()
    )
    audio_eval = parsed_report.get("audio_evaluation")
    video_eval = parsed_report.get("video_evaluation")
    transcript_eval = parsed_report.get("transcript_evaluation")

    if existing:
        existing.audio_evaluation = audio_eval
        existing.video_evaluation = video_eval
        existing.transcript_evaluation = transcript_eval
        db_obj = existing
    else:
        db_obj = AiPrepAssessmentReportORM(
            assessment_id=assessment_id,
            audio_evaluation=audio_eval,
            video_evaluation=video_eval,
            transcript_evaluation=transcript_eval,
        )
        db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


# Alias
create_or_update_assessment_report = save_assessment_report


def get_assessment_report_by_assessment_id(db: Session, assessment_id: int) -> Optional[AiPrepAssessmentReportORM]:
    return (
        db.query(AiPrepAssessmentReportORM)
        .filter(AiPrepAssessmentReportORM.assessment_id == assessment_id)
        .first()
    )


# ---------------------------------------------------------------------------
# Question Bank CRUD (table: ai_prep_question_bank)
# ---------------------------------------------------------------------------

def seed_default_questions(db: Session) -> List[AiPrepQuestionBankORM]:
    """Seeds default question bank entries if the table is empty."""
    created = []
    for item in get_default_questions():
        existing = (
            db.query(AiPrepQuestionBankORM)
            .filter(
                AiPrepQuestionBankORM.category == item["category"],
                AiPrepQuestionBankORM.question_text == item["question_text"],
            )
            .first()
        )
        if not existing:
            q = AiPrepQuestionBankORM(
                category=item["category"],
                sub_category=item.get("sub_category"),
                difficulty_level=item["difficulty_level"],
                question_text=item["question_text"],
                is_active=True,
            )
            db.add(q)
            created.append(q)
    if created:
        try:
            db.commit()
            for obj in created:
                db.refresh(obj)
        except Exception as exc:
            db.rollback()
            logger.warning("Error seeding default questions: %s", exc)
    return db.query(AiPrepQuestionBankORM).filter(AiPrepQuestionBankORM.is_active == True).all()  # noqa: E712


def list_questions(
    db: Session,
    category: Optional[str] = None,
    difficulty_level: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[AiPrepQuestionBankORM], int]:
    query = db.query(AiPrepQuestionBankORM)
    if category:
        query = query.filter(AiPrepQuestionBankORM.category == category)
    if difficulty_level:
        query = query.filter(AiPrepQuestionBankORM.difficulty_level == difficulty_level)
    if is_active is not None:
        query = query.filter(AiPrepQuestionBankORM.is_active == is_active)

    total = query.count()
    if total == 0:
        seed_default_questions(db)
        # Re-query after seeding
        query = db.query(AiPrepQuestionBankORM)
        if category:
            query = query.filter(AiPrepQuestionBankORM.category == category)
        if difficulty_level:
            query = query.filter(AiPrepQuestionBankORM.difficulty_level == difficulty_level)
        if is_active is not None:
            query = query.filter(AiPrepQuestionBankORM.is_active == is_active)
        total = query.count()

    items = query.order_by(desc(AiPrepQuestionBankORM.id)).offset(offset).limit(limit).all()
    return items, total


def get_question_by_id(db: Session, question_id: int) -> Optional[AiPrepQuestionBankORM]:
    return db.query(AiPrepQuestionBankORM).filter(AiPrepQuestionBankORM.id == question_id).first()


def create_question(db: Session, question_in: Dict[str, Any]) -> AiPrepQuestionBankORM:
    db_obj = AiPrepQuestionBankORM(**question_in)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_question(db: Session, question_id: int, question_in: Dict[str, Any]) -> Optional[AiPrepQuestionBankORM]:
    q = db.query(AiPrepQuestionBankORM).filter(AiPrepQuestionBankORM.id == question_id).first()
    if not q:
        return None
    for field, val in question_in.items():
        if val is not None and hasattr(q, field):
            setattr(q, field, val)
    db.commit()
    db.refresh(q)
    return q


# ---------------------------------------------------------------------------
# Pre-assessment Candidate Checks (LLM Keys & Resume)
# ---------------------------------------------------------------------------

def check_candidate_llm_key(db: Session, candidate_id: int) -> Dict[str, Any]:
    """Checks whether the candidate has a configured, active LLM key."""
    key_row = (
        db.query(CandidateLlmApiKeyORM)
        .filter(CandidateLlmApiKeyORM.candidate_id == candidate_id)
        .order_by(desc(CandidateLlmApiKeyORM.is_default), desc(CandidateLlmApiKeyORM.id))
        .first()
    )

    if not key_row or not key_row.api_key:
        return {
            "status": "failure",
            "is_configured": False,
            "provider": None,
            "model": None,
            "voice_enabled": False,
            "message": "No active LLM API key found for this candidate. Please configure an OpenAI or Gemini API key first.",
            "available_models": [],
        }

    return {
        "status": "valid",
        "is_configured": True,
        "provider": key_row.provider_name or "openai",
        "model": key_row.model_name or "gpt-4o",
        "voice_enabled": bool(key_row.voice_enabled),
        "message": "LLM API Key is configured and valid.",
        "available_models": [key_row.model_name or "gpt-4o"],
    }


# Alias
get_candidate_llm_config = check_candidate_llm_key


def check_candidate_resume(db: Session, candidate_id: int) -> Dict[str, Any]:
    """Checks whether the candidate has an uploaded and parsed resume."""
    candidate = db.query(CandidateORM).filter(CandidateORM.id == candidate_id).first()
    if not candidate:
        return {
            "status": "failure",
            "has_resume": False,
            "has_parsed_json": False,
            "candidate_name": None,
            "current_title": None,
            "skills": [],
            "message": f"Candidate with ID {candidate_id} not found.",
        }

    mktg = (
        db.query(CandidateMarketingORM)
        .filter(CandidateMarketingORM.candidate_id == candidate_id)
        .order_by(desc(CandidateMarketingORM.id))
        .first()
    )

    candidate_name = (candidate.full_name or "").strip() or candidate.email
    has_resume = bool(mktg and mktg.resume_url)
    parsed_json = mktg.candidate_json if mktg and isinstance(mktg.candidate_json, dict) else None

    if not has_resume and not parsed_json:
        return {
            "status": "failure",
            "has_resume": False,
            "has_parsed_json": False,
            "candidate_name": candidate_name,
            "current_title": None,
            "skills": [],
            "message": "Candidate has not uploaded or synced a resume. Please complete resume setup before starting.",
        }

    skills = []
    current_title = None
    if parsed_json:
        skills = parsed_json.get("skills", [])
        if not skills and isinstance(parsed_json.get("personal"), dict):
            skills = parsed_json.get("personal", {}).get("skills", [])
        current_title = parsed_json.get("current_title") or parsed_json.get("title")

    return {
        "status": "valid",
        "has_resume": True,
        "has_parsed_json": bool(parsed_json),
        "candidate_name": candidate_name,
        "current_title": current_title,
        "skills": skills if isinstance(skills, list) else [],
        "message": "Candidate resume is verified and ready.",
    }


# Alias for backward compatibility
check_candidate_resume_status = check_candidate_resume


def get_candidate_resume_json(db: Session, candidate_id: int) -> Optional[Dict[str, Any]]:
    mktg = (
        db.query(CandidateMarketingORM)
        .filter(CandidateMarketingORM.candidate_id == candidate_id)
        .order_by(desc(CandidateMarketingORM.id))
        .first()
    )
    return mktg.candidate_json if mktg and isinstance(mktg.candidate_json, dict) else None


def save_candidate_resume_json(db: Session, candidate_id: int, resume_data: Dict[str, Any]) -> bool:
    mktg = (
        db.query(CandidateMarketingORM)
        .filter(CandidateMarketingORM.candidate_id == candidate_id)
        .order_by(desc(CandidateMarketingORM.id))
        .first()
    )
    if mktg:
        mktg.candidate_json = resume_data
        db.commit()
        return True
    return False
