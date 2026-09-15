"""Database CRUD operations for AI Prep Tool.
Fully validated and interoperable with aiprep-backend branch.
"""
import uuid
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import desc

from fapi.ai_prep.models import (
    AiPrepAssessmentORM,
    AiPrepAssessmentDataORM,
    AiPrepAssessmentReportORM,
    AiPrepQuestionORM,
)
from fapi.db.models import (
    CandidateORM,
    CandidateMarketingORM,
    CandidateLlmApiKeyORM,
    AuthUserORM,
)
from fapi.utils.coderpad_openai_key import _plaintext_api_key

logger = logging.getLogger(__name__)

def list_assessment_types() -> List[Dict[str, Any]]:
    """Returns the hardcoded assessment types catalog."""
    return [
        {
            "id": 1,
            "code": "INTRO",
            "title": "Intro Assessment",
            "description": "Standard introductory background, soft skills, and career narrative assessment.",
            "category": "GENERAL",
            "time_estimate_mins": 4,
            "is_active": True,
        },
        {
            "id": 2,
            "code": "JD_INTRO",
            "title": "JD Intro Assessment",
            "description": "Job description-aligned introductory walkthrough focusing on specific tech stack and role requirements.",
            "category": "ROLE_SPECIFIC",
            "time_estimate_mins": 4,
            "is_active": True,
        },
        {
            "id": 3,
            "code": "RECRUITER",
            "title": "Recruiter Screen",
            "description": "Recruiter-style screening covering motivation, cultural fit, transitions, and logistics.",
            "category": "SCREENING",
            "time_estimate_mins": 10,
            "is_active": True,
        },
        {
            "id": 4,
            "code": "HIRING_MANAGER",
            "title": "Hiring Manager Round",
            "description": "In-depth hiring manager interview exploring project ownership, delivery, accountability, and problem-solving.",
            "category": "MANAGEMENT",
            "time_estimate_mins": 15,
            "is_active": True,
        },
        {
            "id": 5,
            "code": "SYSTEM_DESIGN",
            "title": "System Design",
            "description": "Architectural breakdown covering high-level architecture, scalability, trade-offs, and GenAI/RAG pipelines.",
            "category": "TECHNICAL",
            "time_estimate_mins": 25,
            "is_active": True,
        },
        {
            "id": 6,
            "code": "TECHNICAL",
            "title": "Technical Assessment",
            "description": "Deep technical evaluation covering core engineering, frameworks, databases, and algorithms.",
            "category": "TECHNICAL",
            "time_estimate_mins": 30,
            "is_active": True,
        },
    ]


def get_default_questions() -> List[Dict[str, Any]]:
    """Standard introductory fallback questions."""
    return [
        {
            "category": "INTRO",
            "sub_category": None,
            "difficulty_level": "MEDIUM",
            "question_text": "Tell me about yourself, your background, and your experience building production AI and software systems.",
        },
        {
            "category": "JD_INTRO",
            "sub_category": None,
            "difficulty_level": "MEDIUM",
            "question_text": "How does your technical experience match the key requirements and tech stack of this job description?",
        },
        {
            "category": "RECRUITER",
            "sub_category": None,
            "difficulty_level": "MEDIUM",
            "question_text": "Walk me through your recent career transitions and what motivates you to pursue this next role.",
        },
        {
            "category": "HIRING_MANAGER",
            "sub_category": None,
            "difficulty_level": "HARD",
            "question_text": "Describe a high-stakes project you led where you encountered significant blockers. How did you resolve them?",
        },
        {
            "category": "SYSTEM_DESIGN",
            "sub_category": None,
            "difficulty_level": "HARD",
            "question_text": "Design a high-throughput, low-latency RAG pipeline that handles multi-tenant enterprise documents with semantic caching and guardrails.",
        },
        {
            "category": "TECHNICAL",
            "sub_category": "Agentic AI",
            "difficulty_level": "HARD",
            "question_text": "Explain the difference between ReAct patterns and Plan-and-Solve agent frameworks. When would you choose one over the other?",
        },
    ]


def get_assessment_type_by_code(code: str) -> Optional[Dict[str, Any]]:
    for t in list_assessment_types():
        if t["code"].upper() == code.upper():
            return t
    return None


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
    assessment_uuid = str(uuid.uuid4())
    db_obj = AiPrepAssessmentORM(
        assessment_uuid=assessment_uuid,
        candidate_id=candidate_id,
        assessment_type=assessment_type,
        media_type=media_type,
        status="IN_PROGRESS",
        job_description=job_description,
        ip_address=ip_address,
        user_agent=user_agent,
        started_at=datetime.utcnow(),
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_assessment_by_id(db: Session, assessment_id: int) -> Optional[AiPrepAssessmentORM]:
    return db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()


def get_assessment_by_uuid(db: Session, assessment_uuid: str) -> Optional[AiPrepAssessmentORM]:
    """Compatibility lookup: looks up by numeric ID if valid integer, otherwise None."""
    try:
        aid = int(assessment_uuid)
        return get_assessment_by_id(db, aid)
    except (ValueError, TypeError):
        return None


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


def save_assessment_data(
    db: Session,
    assessment_id: int,
    questions: List[Dict[str, Any]],
    transcript: Dict[str, Any],
    audio_telemetry: Dict[str, Any],
    video_telemetry: Dict[str, Any],
) -> AiPrepAssessmentDataORM:
    existing = db.query(AiPrepAssessmentDataORM).filter(AiPrepAssessmentDataORM.assessment_id == assessment_id).first()
    if existing:
        existing.questions = questions
        existing.transcript = transcript
        existing.audio_telemetry = audio_telemetry
        existing.video_telemetry = video_telemetry
        existing.updated_at = datetime.utcnow()
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


def create_or_update_assessment_data(
    db: Session,
    assessment_id: int,
    questions: List[Dict[str, Any]],
    transcript: Dict[str, Any],
    audio_telemetry: Dict[str, Any],
    video_telemetry: Dict[str, Any],
) -> AiPrepAssessmentDataORM:
    return save_assessment_data(db, assessment_id, questions, transcript, audio_telemetry, video_telemetry)


def get_assessment_data_by_assessment_id(db: Session, assessment_id: int) -> Optional[AiPrepAssessmentDataORM]:
    return db.query(AiPrepAssessmentDataORM).filter(AiPrepAssessmentDataORM.assessment_id == assessment_id).first()


def update_assessment_media_url(db: Session, assessment_id: int, youtube_url: str) -> Optional[AiPrepAssessmentORM]:
    assessment = get_assessment_by_id(db, assessment_id)
    if not assessment:
        return None
    assessment.youtube_url = youtube_url
    assessment.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(assessment)
    return assessment


def update_assessment_youtube_url(db: Session, assessment_id: int, youtube_url: str) -> Optional[AiPrepAssessmentORM]:
    return update_assessment_media_url(db, assessment_id, youtube_url)


def update_assessment_status(db: Session, assessment_id: int, status: str) -> Optional[AiPrepAssessmentORM]:
    assessment = get_assessment_by_id(db, assessment_id)
    if not assessment:
        return None
    assessment.status = status
    if status in ("COMPLETED", "FAILED"):
        assessment.completed_at = datetime.utcnow()
    assessment.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(assessment)
    return assessment


def save_assessment_report(
    db: Session,
    assessment_id: int,
    parsed_report: Dict[str, Any],
) -> AiPrepAssessmentReportORM:
    existing = db.query(AiPrepAssessmentReportORM).filter(AiPrepAssessmentReportORM.assessment_id == assessment_id).first()
    
    audio_eval = parsed_report.get("audio_evaluation")
    video_eval = parsed_report.get("video_evaluation")
    transcript_eval = parsed_report.get("transcript_evaluation")
    overall_score = parsed_report.get("overall_score")

    if overall_score is None and isinstance(transcript_eval, dict):
        # Extract from nested evaluation objects if present (scores_breakdown_json, intro_evaluation, or top-level)
        inner_eval = (
            transcript_eval.get("scores_breakdown_json")
            or transcript_eval.get("intro_evaluation")
            or transcript_eval
        )
        if isinstance(inner_eval, dict):
            overall_score = inner_eval.get("overall_score") or inner_eval.get("score")
            if overall_score is None and isinstance(inner_eval.get("overall_assessment"), dict):
                oa = inner_eval["overall_assessment"]
                overall_score = oa.get("overall_score") or oa.get("score")

    if overall_score is not None and isinstance(transcript_eval, dict):
        transcript_eval["overall_score"] = overall_score


    if existing:
        existing.audio_evaluation = audio_eval
        existing.video_evaluation = video_eval
        existing.transcript_evaluation = transcript_eval
        existing.overall_score = overall_score
        existing.report_data = parsed_report
        existing.updated_at = datetime.utcnow()
        db_obj = existing
    else:
        db_obj = AiPrepAssessmentReportORM(
            assessment_id=assessment_id,
            audio_evaluation=audio_eval,
            video_evaluation=video_eval,
            transcript_evaluation=transcript_eval,
            overall_score=overall_score,
            report_data=parsed_report,
        )
        db.add(db_obj)

    db.commit()
    db.refresh(db_obj)
    return db_obj


def create_or_update_assessment_report(db: Session, assessment_id: int, parsed_report: Dict[str, Any]) -> AiPrepAssessmentReportORM:
    return save_assessment_report(db, assessment_id, parsed_report)


def get_assessment_report_by_assessment_id(db: Session, assessment_id: int) -> Optional[AiPrepAssessmentReportORM]:
    return db.query(AiPrepAssessmentReportORM).filter(AiPrepAssessmentReportORM.assessment_id == assessment_id).first()


# ---------------------------------------------------------------------------
# Questions Bank CRUD
# ---------------------------------------------------------------------------

def seed_default_questions(db: Session) -> List[AiPrepQuestionORM]:
    created = []
    for item in get_default_questions():
        existing = db.query(AiPrepQuestionORM).filter(
            AiPrepQuestionORM.category == item["category"],
            AiPrepQuestionORM.question_text == item["question_text"]
        ).first()
        if not existing:
            q = AiPrepQuestionORM(
                category=item["category"],
                sub_category=item["sub_category"],
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
        except Exception as e:
            db.rollback()
            logger.warning(f"Error seeding default questions: {e}")
    return db.query(AiPrepQuestionORM).filter(AiPrepQuestionORM.is_active == True).all()


def list_questions(
    db: Session,
    category: Optional[str] = None,
    difficulty_level: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[AiPrepQuestionORM], int]:
    query = db.query(AiPrepQuestionORM)
    if category:
        query = query.filter(AiPrepQuestionORM.category == category)
    if difficulty_level:
        query = query.filter(AiPrepQuestionORM.difficulty_level == difficulty_level)
    if is_active is not None:
        query = query.filter(AiPrepQuestionORM.is_active == is_active)

    total = query.count()
    if total == 0:
        seed_default_questions(db)
        query = db.query(AiPrepQuestionORM)
        if category:
            query = query.filter(AiPrepQuestionORM.category == category)
        if difficulty_level:
            query = query.filter(AiPrepQuestionORM.difficulty_level == difficulty_level)
        if is_active is not None:
            query = query.filter(AiPrepQuestionORM.is_active == is_active)
        total = query.count()

    items = query.order_by(desc(AiPrepQuestionORM.id)).offset(offset).limit(limit).all()
    return items, total


def get_question_by_id(db: Session, question_id: int) -> Optional[AiPrepQuestionORM]:
    return db.query(AiPrepQuestionORM).filter(AiPrepQuestionORM.id == question_id).first()


def create_question(db: Session, question_in: Dict[str, Any]) -> AiPrepQuestionORM:
    data = dict(question_in)
    cat = data.get("category")
    if cat and str(cat).upper() != "TECHNICAL":
        data["sub_category"] = None
    elif cat and str(cat).upper() == "TECHNICAL" and not data.get("sub_category"):
        data["sub_category"] = "General"
    db_obj = AiPrepQuestionORM(**data)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_question(db: Session, question_id: int, question_in: Dict[str, Any]) -> Optional[AiPrepQuestionORM]:
    q = db.query(AiPrepQuestionORM).filter(AiPrepQuestionORM.id == question_id).first()
    if not q:
        return None
    data = dict(question_in)
    target_cat = data.get("category", q.category)
    if target_cat and str(target_cat).upper() != "TECHNICAL":
        data["sub_category"] = None
    elif target_cat and str(target_cat).upper() == "TECHNICAL" and not data.get("sub_category", q.sub_category):
        data["sub_category"] = "General"
    for field, val in data.items():
        if val is not None and hasattr(q, field):
            setattr(q, field, val)
    q.updated_at = datetime.utcnow()
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


def get_candidate_llm_config(db: Session, candidate_id: int) -> Dict[str, Any]:
    cfg = check_candidate_llm_key(db, candidate_id)
    if cfg.get("is_configured"):
        key_row = (
            db.query(CandidateLlmApiKeyORM)
            .filter(CandidateLlmApiKeyORM.candidate_id == candidate_id)
            .order_by(desc(CandidateLlmApiKeyORM.is_default), desc(CandidateLlmApiKeyORM.id))
            .first()
        )
        if key_row and key_row.api_key:
            cfg["api_key"] = _plaintext_api_key(str(key_row.api_key))
    return cfg


def check_candidate_resume(db: Session, candidate_id: int) -> Dict[str, Any]:
    """Checks whether the candidate has an uploaded and parsed resume."""
    from fapi.ai_prep.utils.aiprep_utils import _normalize_skills

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
    parsed_json = None
    if mktg and mktg.candidate_json:
        if isinstance(mktg.candidate_json, dict):
            parsed_json = mktg.candidate_json
        elif isinstance(mktg.candidate_json, str):
            try:
                import json
                parsed_json = json.loads(mktg.candidate_json)
            except Exception:
                parsed_json = None

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

    skills: List[str] = []
    current_title: Optional[str] = None
    if parsed_json:
        raw_skills = parsed_json.get("skills")
        if not raw_skills and isinstance(parsed_json.get("personal"), dict):
            raw_skills = parsed_json.get("personal", {}).get("skills")
        skills = _normalize_skills(raw_skills)
        raw_title = parsed_json.get("current_title") or parsed_json.get("title")
        current_title = str(raw_title).strip() if raw_title else None

    return {
        "status": "valid",
        "has_resume": True,
        "has_parsed_json": bool(parsed_json),
        "candidate_name": candidate_name,
        "current_title": current_title,
        "skills": skills,
        "message": "Candidate resume is verified and ready.",
    }


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
        mktg.last_mod_datetime = datetime.utcnow()
        db.commit()
        return True
    return False
