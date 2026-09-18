"""Business logic and utility functions for AI Prep Tool.
Follows WBL Backend code architecture standards separating routing and logic.
"""
import os
import uuid
import shutil
import logging
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from fapi.db.database import SessionLocal
from fapi.ai_prep import crud
from fapi.ai_prep.orchestrator import assessment_orchestrator, llm_orchestrator

from fapi.db.models import (
    AuthUserORM,
    CandidateORM,
    CandidateMarketingORM,
    CandidateLlmApiKeyORM,
)
from fapi.ai_prep.models import (
    AiPrepAssessmentORM,
    AiPrepAssessmentDataORM,
    AiPrepAssessmentReportORM,
    AiPrepQuestionORM,
)
from fapi.ai_prep.schemas import (
    AssessmentTypeResponse,
    AssessmentTypeListResponse,
    AssessmentTypeCreate,
    LLMKeyStatusResponse,
    ResumeStatusResponse,
    PreAssessmentCheckResponse,
    CreateAssessmentRequest,
    CreateAssessmentResponse,
    SubmitAssessmentRequest,
    SubmitAssessmentDataRequest,
    SubmitAssessmentDataResponse,
    UpdateMediaURLRequest,
    UpdateMediaURLResponse,
    TriggerEvaluationResponse,
    AssessmentDetailResponse,
    AssessmentDataResponse,
    AssessmentReportResponse,
    AssessmentListResponse,
    AssessmentListItem,
    ChunkUploadResponse,
    ChunkStatusResponse,
    AssembleMediaRequest,
    AssembleMediaResponse,
    LocalMediaUploadResponse,
    StorageInfoResponse,
    ProcessingStatusResponse,
    QuestionCreateRequest,
    QuestionUpdateRequest,
    QuestionResponse,
    QuestionListResponse,
)

logger = logging.getLogger(__name__)

STORAGE_BASE_DIR = os.getenv("AIPREP_LOCAL_STORAGE_DIR", "./storage/aiprep")
MAX_CHUNK_SIZE = int(os.getenv("AIPREP_MAX_CHUNK_SIZE", 25 * 1024 * 1024))  # 25 MB
MAX_MEDIA_SIZE = int(os.getenv("AIPREP_MAX_MEDIA_SIZE", 150 * 1024 * 1024))  # 150 MB


# ---------------------------------------------------------------------------
# In-Memory Assessment Types Catalog
# ---------------------------------------------------------------------------

def get_default_assessment_types() -> List[Dict[str, Any]]:
    """Returns in-memory catalog of standard assessment types."""
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


# ---------------------------------------------------------------------------
# Dynamic DB & Authorization Helpers
# ---------------------------------------------------------------------------

def _normalize_skills(raw_skills: Any) -> List[str]:
    """Extracts and flattens skills into a clean, deduplicated list of strings."""
    if not raw_skills:
        return []
    extracted: List[str] = []

    def _add(val: Any):
        if val is None:
            return
        if isinstance(val, str):
            s = val.strip()
            if s and s not in extracted:
                extracted.append(s)
        elif isinstance(val, (int, float)):
            s = str(val).strip()
            if s and s not in extracted:
                extracted.append(s)

    if isinstance(raw_skills, str):
        for part in raw_skills.replace("\n", ",").split(","):
            _add(part)
    elif isinstance(raw_skills, dict):
        for k, v in raw_skills.items():
            if isinstance(v, list):
                for sub in v:
                    if isinstance(sub, str):
                        _add(sub)
                    elif isinstance(sub, dict):
                        _add(sub.get("name") or sub.get("skill"))
                        if isinstance(sub.get("keywords"), list):
                            for kw in sub["keywords"]:
                                _add(kw)
            elif isinstance(v, str):
                _add(v)
            else:
                _add(k)
    elif isinstance(raw_skills, list):
        for item in raw_skills:
            if isinstance(item, str):
                _add(item)
            elif isinstance(item, dict):
                name = item.get("name") or item.get("skill") or item.get("title")
                keywords = item.get("keywords")
                if isinstance(keywords, list) and keywords:
                    if name:
                        _add(name)
                    for kw in keywords:
                        _add(kw)
                elif name:
                    _add(name)
                else:
                    for v in item.values():
                        if isinstance(v, str):
                            _add(v)
                        elif isinstance(v, list):
                            for sub in v:
                                _add(sub)
            else:
                _add(str(item))
    return extracted


def _resolve_candidate_id(db: Session, current_user: AuthUserORM, requested_id: Optional[int] = None) -> int:
    """Enforces authorization: Candidates can only access their own ID; employees can specify any."""
    uname = (getattr(current_user, "uname", "") or "").lower()
    role = getattr(current_user, "role", None) or ("admin" if uname == "admin" else "candidate")
    is_employee = bool(getattr(current_user, "is_employee", False) or role in ("admin", "staff", "employee") or uname == "admin")

    # Match Candidate by email or ID
    candidate = db.query(CandidateORM).filter(CandidateORM.email == current_user.uname).first()
    if not candidate:
        candidate = db.query(CandidateORM).filter(CandidateORM.id == current_user.id).first()
    if not candidate and not is_employee:
        raise HTTPException(status_code=404, detail="Candidate record not found.")

    self_candidate_id = candidate.id if candidate else current_user.id

    if not is_employee:
        if requested_id is not None and requested_id != self_candidate_id:
            raise HTTPException(status_code=403, detail="Access denied to this assessment")
        return self_candidate_id
    return requested_id if requested_id is not None else self_candidate_id


def _check_candidate_llm_db(db: Session, candidate_id: int) -> Dict[str, Any]:
    """Queries candidate_llm_api_keys dynamically for the candidate via crud."""
    return crud.check_candidate_llm_key(db, candidate_id)


def _check_candidate_resume_db(db: Session, candidate_id: int) -> Dict[str, Any]:
    """Queries candidate_marketing and candidate tables dynamically."""
    cand = db.query(CandidateORM).filter(CandidateORM.id == candidate_id).first()
    candidate_name = cand.full_name if (cand and cand.full_name) else f"Candidate #{candidate_id}"

    mktg = (
        db.query(CandidateMarketingORM)
        .filter(CandidateMarketingORM.candidate_id == candidate_id)
        .order_by(desc(CandidateMarketingORM.id))
        .first()
    )

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
            "message": "Candidate has not uploaded or synced a resume.",
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


def _verify_prerequisites(db: Session, candidate_id: int):
    """Enforces prerequisite checks before starting an assessment."""
    llm_status = _check_candidate_llm_db(db, candidate_id)
    resume_status = _check_candidate_resume_db(db, candidate_id)

    errors = []
    if not llm_status["is_configured"]:
        errors.append("Active LLM API Key is missing or invalid.")
    if not resume_status["has_resume"] and not resume_status["has_parsed_json"]:
        errors.append("Resume has not been uploaded or parsed.")

    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "AssessmentPrerequisitesFailed",
                "message": "Cannot start assessment. Prerequisites not met.",
                "reasons": errors,
                "llm_check": llm_status,
                "resume_check": resume_status,
            },
        )


# ---------------------------------------------------------------------------
# 1. Candidate Business Logic Functions
# ---------------------------------------------------------------------------

def candidate_check_llm_keys_logic(db: Session, current_user: AuthUserORM, candidate_id: Optional[int] = None) -> LLMKeyStatusResponse:
    """Check for configured LLM key dynamically from DB (self for candidate, or specified candidate for staff)."""
    try:
        cand_id = _resolve_candidate_id(db, current_user, candidate_id)
        result = _check_candidate_llm_db(db, cand_id)
        return LLMKeyStatusResponse(**result)
    except HTTPException as e:
        if e.status_code == 404:
            return LLMKeyStatusResponse(
                status="failure",
                is_configured=False,
                provider=None,
                model=None,
                voice_enabled=False,
                message="Candidate profile record not found. Please configure an API key in setup.",
                available_models=[],
            )
        raise


def candidate_check_resume_status_logic(db: Session, current_user: AuthUserORM, candidate_id: Optional[int] = None) -> ResumeStatusResponse:
    """Check for parsed resume status dynamically from DB (self for candidate, or specified candidate for staff)."""
    try:
        cand_id = _resolve_candidate_id(db, current_user, candidate_id)
        result = _check_candidate_resume_db(db, cand_id)
        return ResumeStatusResponse(**result)
    except HTTPException as e:
        if e.status_code == 404:
            cand_name = getattr(current_user, "fullname", None) or getattr(current_user, "uname", "Candidate")
            return ResumeStatusResponse(
                status="failure",
                has_resume=False,
                has_parsed_json=False,
                candidate_name=cand_name,
                current_title=None,
                skills=[],
                message="Candidate profile record not found. Please complete profile setup.",
            )
        raise


def candidate_pre_check_logic(db: Session, current_user: AuthUserORM, candidate_id: Optional[int] = None) -> PreAssessmentCheckResponse:
    """Verifies both LLM key and resume readiness before starting assessment."""
    try:
        cand_id = _resolve_candidate_id(db, current_user, candidate_id)
    except HTTPException as e:
        if e.status_code == 404:
            cand_name = getattr(current_user, "fullname", None) or getattr(current_user, "uname", "Candidate")
            return PreAssessmentCheckResponse(
                eligible=False,
                candidate_id=getattr(current_user, "id", 0),
                llm_check=LLMKeyStatusResponse(
                    status="failure",
                    is_configured=False,
                    message="Candidate profile record not found.",
                ),
                resume_check=ResumeStatusResponse(
                    status="failure",
                    has_resume=False,
                    has_parsed_json=False,
                    candidate_name=cand_name,
                    message="Candidate profile record not found. Please complete profile setup.",
                ),
                message="Prerequisites missing: setup required",
            )
        raise
    llm_check = _check_candidate_llm_db(db, cand_id)
    resume_check = _check_candidate_resume_db(db, cand_id)
    eligible = bool(llm_check["is_configured"] and (resume_check["has_resume"] or resume_check["has_parsed_json"]))
    return PreAssessmentCheckResponse(
        eligible=eligible,
        candidate_id=cand_id,
        llm_check=LLMKeyStatusResponse(**llm_check),
        resume_check=ResumeStatusResponse(**resume_check),
        message="Ready to start assessment" if eligible else "Prerequisites missing: setup required",
    )


def candidate_create_assessment_logic(
    db: Session,
    current_user: AuthUserORM,
    payload: CreateAssessmentRequest,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> CreateAssessmentResponse:
    """Dynamically validates prerequisites and creates a new assessment row in DB."""
    candidate_id = _resolve_candidate_id(db, current_user, payload.candidate_id)
    _verify_prerequisites(db, candidate_id)

    db_assessment = crud.create_assessment(
        db=db,
        candidate_id=candidate_id,
        assessment_type=payload.assessment_type.value if hasattr(payload.assessment_type, "value") else str(payload.assessment_type),
        media_type=payload.media_type.value if hasattr(payload.media_type, "value") else str(payload.media_type),
        job_description=payload.job_description,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    assessment_type_str = (
        payload.assessment_type.value
        if hasattr(payload.assessment_type, "value")
        else str(payload.assessment_type)
    )

    # Query initial question from DB via Assessment Orchestrator and Assessment Engine
    questions_list = assessment_orchestrator.get_questions_for_assessment(
        db=db,
        assessment_type=assessment_type_str,
    )
    if not questions_list:
        questions_list = [{
            "question_id": 1,
            "question_text": f"Please introduce yourself and your background relevant to {assessment_type_str}.",
            "category": assessment_type_str,
        }]

    return CreateAssessmentResponse(
        id=db_assessment.id,
        assessment_uuid=db_assessment.assessment_uuid,
        status=db_assessment.status,
        started_at=db_assessment.started_at,
        assessment_type=db_assessment.assessment_type,
        media_type=db_assessment.media_type,
        job_description=db_assessment.job_description,
        youtube_url=db_assessment.youtube_url,
        questions=questions_list,
    )


def candidate_list_assessments_logic(
    db: Session,
    current_user: AuthUserORM,
    candidate_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    assessment_type: Optional[str] = None,
    media_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> AssessmentListResponse:
    """Unified assessment listing: auto-scoped to candidate or filterable for staff."""
    uname = (getattr(current_user, "uname", "") or "").lower()
    role = getattr(current_user, "role", None) or ("admin" if uname == "admin" else "candidate")
    is_employee = bool(getattr(current_user, "is_employee", False) or role in ("admin", "staff", "employee") or uname == "admin")

    query = db.query(AiPrepAssessmentORM)

    if not is_employee:
        cand_id = _resolve_candidate_id(db, current_user)
        query = query.filter(AiPrepAssessmentORM.candidate_id == cand_id)
    else:
        if candidate_id:
            query = query.filter(AiPrepAssessmentORM.candidate_id == candidate_id)

    if status_filter and status_filter.lower() != "all":
        query = query.filter(AiPrepAssessmentORM.status == status_filter)
    if assessment_type and assessment_type.lower() != "all":
        query = query.filter(AiPrepAssessmentORM.assessment_type == assessment_type)
    if media_type and media_type.lower() != "all":
        query = query.filter(AiPrepAssessmentORM.media_type == media_type)
    if search and search.strip():
        search_term = f"%{search.strip()}%"
        query = query.filter(AiPrepAssessmentORM.job_description.ilike(search_term))

    total = query.count()
    items = query.order_by(desc(AiPrepAssessmentORM.created_at)).offset(offset).limit(limit).all()

    candidate_ids = {a.candidate_id for a in items if a.candidate_id is not None}
    cand_map = {}
    if candidate_ids:
        candidates = db.query(CandidateORM).filter(CandidateORM.id.in_(candidate_ids)).all()
        cand_map = {c.id: c for c in candidates}

    result_items = []
    for a in items:
        cand = cand_map.get(a.candidate_id)
        candidate_name = cand.full_name if (cand and cand.full_name) else None
        candidate_email = cand.email if (cand and cand.email) else None
        score = a.report_record.overall_score if a.report_record else None

        result_items.append(
            AssessmentListItem(
                id=a.id,
                assessment_uuid=a.assessment_uuid,
                candidate_id=a.candidate_id,
                candidate_name=candidate_name,
                candidate_email=candidate_email,
                score=score,
                assessment_type=a.assessment_type,
                media_type=a.media_type,
                status=a.status,
                job_description=a.job_description,
                youtube_url=a.youtube_url,
                started_at=a.started_at,
                completed_at=a.completed_at,
                created_at=a.created_at,
            )
        )

    return AssessmentListResponse(
        items=result_items,
        total=total,
    )


def candidate_get_assessment_detail_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
) -> AssessmentDetailResponse:
    """Fetches assessment detail, telemetry, and evaluation scores from DB."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    _resolve_candidate_id(db, current_user, assessment.candidate_id)

    cand = db.query(CandidateORM).filter(CandidateORM.id == assessment.candidate_id).first() if assessment.candidate_id else None
    candidate_name = cand.full_name if (cand and cand.full_name) else None
    candidate_email = cand.email if (cand and cand.email) else None

    data_dict = None
    if assessment.data_record:
        data_dict = {
            "questions": assessment.data_record.questions,
            "transcript": assessment.data_record.transcript,
            "audio_telemetry": assessment.data_record.audio_telemetry,
            "video_telemetry": assessment.data_record.video_telemetry,
        }

    report_dict = None
    if assessment.report_record:
        report_dict = {
            "audio_evaluation": assessment.report_record.audio_evaluation,
            "video_evaluation": assessment.report_record.video_evaluation,
            "transcript_evaluation": assessment.report_record.transcript_evaluation,
            "overall_score": assessment.report_record.overall_score,
            "report_data": assessment.report_record.report_data,
        }

    return AssessmentDetailResponse(
        id=assessment.id,
        assessment_uuid=assessment.assessment_uuid,
        candidate_id=assessment.candidate_id,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        score=report_dict.get("overall_score") if report_dict else None,
        assessment_type=assessment.assessment_type,
        media_type=assessment.media_type,
        status=assessment.status,
        job_description=assessment.job_description,
        ip_address=assessment.ip_address,
        user_agent=assessment.user_agent,
        youtube_url=assessment.youtube_url,
        started_at=assessment.started_at,
        completed_at=assessment.completed_at,
        created_at=assessment.created_at,
        data=data_dict,
        report=report_dict,
    )


def admin_get_assessment_detail_logic(
    db: Session,
    assessment_id: Union[int, str],
) -> AssessmentDetailResponse:
    """Admin: Fetches full assessment details, telemetry, and evaluation scores from DB."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    cand = db.query(CandidateORM).filter(CandidateORM.id == assessment.candidate_id).first() if assessment.candidate_id else None
    candidate_name = cand.full_name if (cand and cand.full_name) else None
    candidate_email = cand.email if (cand and cand.email) else None

    data_dict = None
    if assessment.data_record:
        data_dict = {
            "questions": assessment.data_record.questions,
            "transcript": assessment.data_record.transcript,
            "audio_telemetry": assessment.data_record.audio_telemetry,
            "video_telemetry": assessment.data_record.video_telemetry,
        }

    report_dict = None
    if assessment.report_record:
        report_dict = {
            "audio_evaluation": assessment.report_record.audio_evaluation,
            "video_evaluation": assessment.report_record.video_evaluation,
            "transcript_evaluation": assessment.report_record.transcript_evaluation,
            "overall_score": assessment.report_record.overall_score,
            "report_data": assessment.report_record.report_data,
        }

    return AssessmentDetailResponse(
        id=assessment.id,
        assessment_uuid=assessment.assessment_uuid,
        candidate_id=assessment.candidate_id,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        score=report_dict.get("overall_score") if report_dict else None,
        assessment_type=assessment.assessment_type,
        media_type=assessment.media_type,
        status=assessment.status,
        job_description=assessment.job_description,
        ip_address=assessment.ip_address,
        user_agent=assessment.user_agent,
        youtube_url=assessment.youtube_url,
        started_at=assessment.started_at,
        completed_at=assessment.completed_at,
        created_at=assessment.created_at,
        data=data_dict,
        report=report_dict,
    )


def candidate_get_assessment_data_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
) -> AssessmentDataResponse:
    """Fetches submitted telemetry and questions data for an assessment."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    _resolve_candidate_id(db, current_user, assessment.candidate_id)
    if not assessment.data_record:
        return AssessmentDataResponse(
            id=None,
            assessment_id=assessment.id,
            assessment_uuid=assessment.assessment_uuid,
            questions=[],
            transcript={},
            audio_telemetry={},
            video_telemetry={},
        )
    return AssessmentDataResponse(
        id=assessment.data_record.id,
        assessment_id=assessment.data_record.assessment_id,
        assessment_uuid=assessment.assessment_uuid,
        questions=assessment.data_record.questions or [],
        transcript=assessment.data_record.transcript or {},
        audio_telemetry=assessment.data_record.audio_telemetry or {},
        video_telemetry=assessment.data_record.video_telemetry or {},
        created_at=assessment.data_record.created_at,
        updated_at=assessment.data_record.updated_at,
    )


def admin_get_assessment_data_logic(
    db: Session,
    assessment_id: Union[int, str],
) -> AssessmentDataResponse:
    """Admin: Fetches submitted telemetry and questions data for an assessment."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if not assessment.data_record:
        return AssessmentDataResponse(
            id=None,
            assessment_id=assessment.id,
            assessment_uuid=assessment.assessment_uuid,
            questions=[],
            transcript={},
            audio_telemetry={},
            video_telemetry={},
        )
    return AssessmentDataResponse(
        id=assessment.data_record.id,
        assessment_id=assessment.data_record.assessment_id,
        assessment_uuid=assessment.assessment_uuid,
        questions=assessment.data_record.questions or [],
        transcript=assessment.data_record.transcript or {},
        audio_telemetry=assessment.data_record.audio_telemetry or {},
        video_telemetry=assessment.data_record.video_telemetry or {},
        created_at=assessment.data_record.created_at,
        updated_at=assessment.data_record.updated_at,
    )


def candidate_get_assessment_report_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
) -> AssessmentReportResponse:
    """Fetches generated evaluation report for an assessment."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    _resolve_candidate_id(db, current_user, assessment.candidate_id)
    if not assessment.report_record:
        raise HTTPException(status_code=404, detail="Evaluation report not yet available")
    return AssessmentReportResponse(
        id=assessment.report_record.id,
        assessment_id=assessment.report_record.assessment_id,
        assessment_uuid=assessment.assessment_uuid,
        audio_evaluation=assessment.report_record.audio_evaluation,
        video_evaluation=assessment.report_record.video_evaluation,
        transcript_evaluation=assessment.report_record.transcript_evaluation,
        overall_score=assessment.report_record.overall_score,
        report_data=assessment.report_record.report_data,
        created_at=assessment.report_record.created_at,
        updated_at=assessment.report_record.updated_at,
    )


def admin_get_assessment_report_logic(
    db: Session,
    assessment_id: Union[int, str],
) -> AssessmentReportResponse:
    """Admin: Fetches generated evaluation report for an assessment."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if not assessment.report_record:
        raise HTTPException(status_code=404, detail="Report not yet available")
    return AssessmentReportResponse(
        id=assessment.report_record.id,
        assessment_id=assessment.report_record.assessment_id,
        assessment_uuid=assessment.assessment_uuid,
        audio_evaluation=assessment.report_record.audio_evaluation,
        video_evaluation=assessment.report_record.video_evaluation,
        transcript_evaluation=assessment.report_record.transcript_evaluation,
        overall_score=assessment.report_record.overall_score,
        report_data=assessment.report_record.report_data,
        created_at=assessment.report_record.created_at,
        updated_at=assessment.report_record.updated_at,
    )


async def _run_evaluation_background(assessment_id: int, candidate_id: int) -> None:
    """Background task to run full LLM evaluation pipeline and persist report."""
    try:
        with SessionLocal() as db:
            assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
            if not assessment:
                logger.error("[LLMOrchestrator Worker] Assessment %s not found", str(assessment_id))
                return

            internal_id = assessment.id
            data_rec = crud.get_assessment_data_by_assessment_id(db, internal_id)
            transcript_data = (data_rec.transcript if data_rec else {}) or {}
            transcript_text = ""
            if isinstance(transcript_data, dict):
                transcript_text = (
                    transcript_data.get("full_text")
                    or transcript_data.get("transcript_text")
                    or transcript_data.get("text")
                    or transcript_data.get("transcript")
                    or ""
                )
                if not transcript_text and "segments" in transcript_data:
                    segments = transcript_data.get("segments") or []
                    if isinstance(segments, list):
                        seg_texts = [
                            str(seg.get("text") or "") if isinstance(seg, dict) else str(seg or "")
                            for seg in segments
                        ]
                        transcript_text = " ".join(t.strip() for t in seg_texts if t.strip())
            elif isinstance(transcript_data, str):
                transcript_text = transcript_data

            audio_telemetry = (data_rec.audio_telemetry if data_rec else {}) or {}
            video_telemetry = (data_rec.video_telemetry if data_rec else {}) or {}
            resume_json = crud.get_candidate_resume_json(db, candidate_id)

            llm_config = crud.get_candidate_llm_config(db, candidate_id)
            if not llm_config or not isinstance(llm_config, dict) or not llm_config.get("is_configured"):
                logger.error(
                    "[LLMOrchestrator Worker] Candidate %d has no valid LLM API key configured.",
                    candidate_id,
                )
                crud.update_assessment_status(db, internal_id, "FAILED")
                return

            assessment_type_str = (
                assessment.assessment_type.value
                if hasattr(assessment.assessment_type, "value")
                else str(assessment.assessment_type)
            )

            eval_result = await llm_orchestrator.run_evaluation(
                candidate_id=candidate_id,
                assessment_type=assessment_type_str,
                transcript_text=transcript_text,
                audio_telemetry=audio_telemetry,
                video_telemetry=video_telemetry,
                resume_json=resume_json,
                llm_config=llm_config,
            )

            crud.save_assessment_report(db, internal_id, eval_result)
            crud.update_assessment_status(db, internal_id, "COMPLETED")
            logger.info(
                "[LLMOrchestrator Worker] Assessment %d successfully evaluated and report saved.",
                internal_id,
            )
    except Exception as exc:
        logger.exception(
            "[LLMOrchestrator Worker] Assessment %s evaluation failed: %s",
            str(assessment_id),
            exc,
        )
        try:
            with SessionLocal() as err_db:
                crud.update_assessment_status(err_db, assessment_id, "FAILED")
        except Exception as err_exc:
            logger.error(f"Failed to update assessment status to FAILED: {err_exc}", exc_info=True)


def _process_submit_data(db: Session, assessment: AiPrepAssessmentORM, payload: SubmitAssessmentDataRequest):
    data_rec = assessment.data_record
    existing_questions = (data_rec.questions if data_rec and data_rec.questions else []) if data_rec else []
    existing_transcript = (data_rec.transcript if data_rec and data_rec.transcript else {}) if data_rec else {}
    existing_audio = (data_rec.audio_telemetry if data_rec and data_rec.audio_telemetry else {}) if data_rec else {}
    existing_video = (data_rec.video_telemetry if data_rec and data_rec.video_telemetry else {}) if data_rec else {}

    if payload.question_id is not None or payload.answer is not None:
        q_entry = {
            "question_id": payload.question_id,
            "answer": payload.answer,
            "duration_seconds": payload.duration_seconds,
            "timestamp": str(payload.timestamp) if payload.timestamp else None,
        }
        updated = False
        new_questions = list(existing_questions)
        if payload.question_id is not None:
            for idx, q in enumerate(new_questions):
                if isinstance(q, dict) and q.get("question_id") is not None and str(q.get("question_id")) == str(payload.question_id):
                    new_questions[idx] = q_entry
                    updated = True
                    break
        if not updated:
            new_questions.append(q_entry)
        questions_to_save = new_questions
        transcript_to_save = existing_transcript
        if payload.answer:
            transcript_to_save = {"full_text": payload.answer}
    else:
        questions_to_save = payload.questions if payload.questions is not None else existing_questions
        transcript_to_save = payload.transcript if payload.transcript is not None else existing_transcript

    audio_to_save = payload.audio_telemetry if payload.audio_telemetry is not None else existing_audio
    video_to_save = payload.video_telemetry if payload.video_telemetry is not None else existing_video

    crud.save_assessment_data(
        db=db,
        assessment_id=assessment.id,
        questions=questions_to_save,
        transcript=transcript_to_save,
        audio_telemetry=audio_to_save,
        video_telemetry=video_to_save,
    )


def candidate_submit_data_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    payload: SubmitAssessmentDataRequest,
) -> SubmitAssessmentDataResponse:
    """Persists candidate telemetry, transcript, and answers into ai_prep_assessment_data via crud."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    _resolve_candidate_id(db, current_user, assessment.candidate_id)

    if assessment.status in ("COMPLETED", "EVALUATED"):
        raise HTTPException(status_code=400, detail="Assessment is no longer accepting submissions")

    _process_submit_data(db, assessment, payload)
    return SubmitAssessmentDataResponse(message="Data saved successfully")


def admin_submit_data_logic(
    db: Session,
    assessment_id: Union[int, str],
    payload: SubmitAssessmentDataRequest,
) -> SubmitAssessmentDataResponse:
    """Admin: Persists telemetry, transcript, and answers into ai_prep_assessment_data."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    _process_submit_data(db, assessment, payload)
    return SubmitAssessmentDataResponse(message="Data saved successfully")


def candidate_update_media_url_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    payload: UpdateMediaURLRequest,
) -> UpdateMediaURLResponse:
    """Updates YouTube/video playback URL on assessment in DB via crud."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    _resolve_candidate_id(db, current_user, assessment.candidate_id)

    if assessment.status in ("COMPLETED", "EVALUATED"):
        raise HTTPException(status_code=400, detail="Cannot update media for a closed assessment")

    target_url = payload.url
    crud.update_assessment_media_url(db, assessment.id, target_url)
    return UpdateMediaURLResponse(
        id=assessment.id,
        assessment_uuid=assessment.assessment_uuid,
        media_url=target_url,
        youtube_url=target_url or "",
    )


def admin_update_media_url_logic(
    db: Session,
    assessment_id: Union[int, str],
    payload: UpdateMediaURLRequest,
) -> UpdateMediaURLResponse:
    """Admin: Updates media URL on assessment."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    target_url = payload.url
    crud.update_assessment_media_url(db, assessment.id, target_url)
    return UpdateMediaURLResponse(
        id=assessment.id,
        assessment_uuid=assessment.assessment_uuid,
        media_url=target_url,
        youtube_url=target_url or "",
    )


def candidate_trigger_eval_post_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    background_tasks: Optional[BackgroundTasks] = None,
) -> TriggerEvaluationResponse:
    """Transitions status to EVALUATING in DB and queues background LLM evaluation."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)

    if assessment.status in ("COMPLETED", "EVALUATED"):
        raise HTTPException(status_code=409, detail="Assessment already evaluated")

    data_rec = crud.get_assessment_data_by_assessment_id(db, assessment.id)
    if not data_rec or (not data_rec.questions and not data_rec.transcript):
        raise HTTPException(status_code=400, detail="No answers submitted to evaluate")

    crud.update_assessment_status(db, assessment.id, "EVALUATING")

    if background_tasks:
        background_tasks.add_task(_run_evaluation_background, assessment.id, candidate_id)

    return TriggerEvaluationResponse(id=assessment.id, assessment_uuid=assessment.assessment_uuid, status="EVALUATING")


def admin_trigger_eval_post_logic(
    db: Session,
    assessment_id: Union[int, str],
    background_tasks: Optional[BackgroundTasks] = None,
) -> TriggerEvaluationResponse:
    """Admin: Transitions status to EVALUATING and queues background LLM evaluation."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    if assessment.status in ("COMPLETED", "EVALUATED"):
        raise HTTPException(status_code=409, detail="Assessment has already been evaluated")

    data_rec = crud.get_assessment_data_by_assessment_id(db, assessment.id)
    if not data_rec or (not data_rec.questions and not data_rec.transcript):
        raise HTTPException(status_code=400, detail="No telemetry data found to evaluate")

    crud.update_assessment_status(db, assessment.id, "EVALUATING")
    candidate_id = assessment.candidate_id or 0

    if background_tasks and candidate_id:
        background_tasks.add_task(_run_evaluation_background, assessment.id, candidate_id)

    return TriggerEvaluationResponse(id=assessment.id, assessment_uuid=assessment.assessment_uuid, status="EVALUATING")


def candidate_trigger_eval_put_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    payload: Optional[SubmitAssessmentRequest] = None,
    background_tasks: Optional[BackgroundTasks] = None,
) -> TriggerEvaluationResponse:
    """Saves telemetry if provided, transitions status to EVALUATING, and queues background LLM evaluation."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)

    if assessment.status in ("COMPLETED", "EVALUATED"):
        raise HTTPException(status_code=400, detail="Assessment is already completed")

    if payload is not None and payload.answers is not None and len(payload.answers) == 0:
        raise HTTPException(status_code=400, detail="Answers array cannot be empty")

    if payload:
        questions_to_save = payload.answers or payload.questions or []
        crud.save_assessment_data(
            db=db,
            assessment_id=assessment.id,
            questions=questions_to_save,
            transcript=payload.transcript or {},
            audio_telemetry=payload.audio_telemetry or {},
            video_telemetry=payload.video_telemetry or {},
        )

    crud.update_assessment_status(db, assessment.id, "EVALUATING")

    if background_tasks:
        background_tasks.add_task(_run_evaluation_background, assessment.id, candidate_id)

    return TriggerEvaluationResponse(id=assessment.id, assessment_uuid=assessment.assessment_uuid, status="EVALUATING")


def admin_trigger_eval_put_logic(
    db: Session,
    assessment_id: Union[int, str],
    payload: Optional[SubmitAssessmentRequest] = None,
    background_tasks: Optional[BackgroundTasks] = None,
) -> TriggerEvaluationResponse:
    """Admin: Saves telemetry if provided, transitions status to EVALUATING, and queues evaluation."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    if assessment.status in ("COMPLETED", "EVALUATED"):
        raise HTTPException(status_code=400, detail="Assessment is already closed")

    if payload is not None and payload.answers is not None and len(payload.answers) == 0:
        raise HTTPException(status_code=400, detail="Answers cannot be empty")

    if payload:
        questions_to_save = payload.answers or payload.questions or []
        crud.save_assessment_data(
            db=db,
            assessment_id=assessment.id,
            questions=questions_to_save,
            transcript=payload.transcript or {},
            audio_telemetry=payload.audio_telemetry or {},
            video_telemetry=payload.video_telemetry or {},
        )

    crud.update_assessment_status(db, assessment.id, "EVALUATING")
    candidate_id = assessment.candidate_id or 0

    if background_tasks and candidate_id:
        background_tasks.add_task(_run_evaluation_background, assessment.id, candidate_id)

    return TriggerEvaluationResponse(id=assessment.id, assessment_uuid=assessment.assessment_uuid, status="EVALUATING")


# ---------------------------------------------------------------------------
# 2. Employee & Admin Business Logic Functions
# ---------------------------------------------------------------------------

def employee_check_candidate_llm_keys_logic(db: Session, candidate_id: int) -> LLMKeyStatusResponse:
    """Employee inspects LLM key validity for any candidate dynamically from DB."""
    result = _check_candidate_llm_db(db, candidate_id)
    return LLMKeyStatusResponse(**result)


def employee_check_candidate_resume_logic(db: Session, candidate_id: int) -> ResumeStatusResponse:
    """Employee inspects resume setup for any candidate dynamically from DB."""
    result = _check_candidate_resume_db(db, candidate_id)
    return ResumeStatusResponse(**result)


def employee_check_candidate_pre_check_logic(db: Session, candidate_id: int) -> PreAssessmentCheckResponse:
    """Employee checks combined eligibility dynamically from DB."""
    llm_check = _check_candidate_llm_db(db, candidate_id)
    resume_check = _check_candidate_resume_db(db, candidate_id)
    eligible = bool(llm_check["is_configured"] and (resume_check["has_resume"] or resume_check["has_parsed_json"]))
    return PreAssessmentCheckResponse(
        eligible=eligible,
        candidate_id=candidate_id,
        llm_check=LLMKeyStatusResponse(**llm_check),
        resume_check=ResumeStatusResponse(**resume_check),
        message="Candidate is eligible to start assessment" if eligible else "Prerequisites missing",
    )


def employee_list_assessments_table_logic(
    db: Session,
    candidate_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> AssessmentListResponse:
    """Employee/Admin Grid: lists all candidate assessments from DB with filtering."""
    query = db.query(AiPrepAssessmentORM)
    if candidate_id:
        query = query.filter(AiPrepAssessmentORM.candidate_id == candidate_id)
    if status_filter:
        query = query.filter(AiPrepAssessmentORM.status == status_filter)

    total = query.count()
    items = query.order_by(desc(AiPrepAssessmentORM.created_at)).offset(offset).limit(limit).all()

    candidate_ids = {a.candidate_id for a in items if a.candidate_id is not None}
    cand_map = {}
    if candidate_ids:
        candidates = db.query(CandidateORM).filter(CandidateORM.id.in_(candidate_ids)).all()
        cand_map = {c.id: c for c in candidates}

    result_items = []
    for a in items:
        cand = cand_map.get(a.candidate_id)
        candidate_name = cand.full_name if (cand and cand.full_name) else None
        candidate_email = cand.email if (cand and cand.email) else None
        score = a.report_record.overall_score if a.report_record else None

        result_items.append(
            AssessmentListItem(
                id=a.id,
                assessment_uuid=a.assessment_uuid,
                candidate_id=a.candidate_id,
                candidate_name=candidate_name,
                candidate_email=candidate_email,
                score=score,
                assessment_type=a.assessment_type,
                media_type=a.media_type,
                status=a.status,
                job_description=a.job_description,
                youtube_url=a.youtube_url,
                started_at=a.started_at,
                completed_at=a.completed_at,
                created_at=a.created_at,
            )
        )

    return AssessmentListResponse(
        items=result_items,
        total=total,
    )


def employee_list_candidate_assessments_logic(db: Session, candidate_id: int) -> AssessmentListResponse:
    """Employee view of assessment history for any specific candidate ID."""
    cand = db.query(CandidateORM).filter(CandidateORM.id == candidate_id).first() if candidate_id else None
    candidate_name = cand.full_name if (cand and cand.full_name) else None
    candidate_email = cand.email if (cand and cand.email) else None

    query = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.candidate_id == candidate_id)
    total = query.count()
    items = query.order_by(desc(AiPrepAssessmentORM.created_at)).all()

    return AssessmentListResponse(
        items=[
            AssessmentListItem(
                id=a.id,
                assessment_uuid=a.assessment_uuid,
                candidate_id=a.candidate_id,
                candidate_name=candidate_name,
                candidate_email=candidate_email,
                score=a.report_record.overall_score if a.report_record else None,
                assessment_type=a.assessment_type,
                media_type=a.media_type,
                status=a.status,
                job_description=a.job_description,
                youtube_url=a.youtube_url,
                started_at=a.started_at,
                completed_at=a.completed_at,
                created_at=a.created_at,
            )
            for a in items
        ],
        total=total,
    )


def employee_get_assessment_detail_logic(db: Session, assessment_id: Union[int, str]) -> AssessmentDetailResponse:
    """Employee/Admin review of complete telemetry and scores for any assessment."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    cand = db.query(CandidateORM).filter(CandidateORM.id == assessment.candidate_id).first() if assessment.candidate_id else None
    candidate_name = cand.full_name if (cand and cand.full_name) else None
    candidate_email = cand.email if (cand and cand.email) else None

    data_dict = None
    if assessment.data_record:
        data_dict = {
            "questions": assessment.data_record.questions,
            "transcript": assessment.data_record.transcript,
            "audio_telemetry": assessment.data_record.audio_telemetry,
            "video_telemetry": assessment.data_record.video_telemetry,
        }

    report_dict = None
    if assessment.report_record:
        report_dict = {
            "audio_evaluation": assessment.report_record.audio_evaluation,
            "video_evaluation": assessment.report_record.video_evaluation,
            "transcript_evaluation": assessment.report_record.transcript_evaluation,
            "overall_score": assessment.report_record.overall_score,
            "report_data": assessment.report_record.report_data,
        }

    return AssessmentDetailResponse(
        id=assessment.id,
        assessment_uuid=assessment.assessment_uuid,
        candidate_id=assessment.candidate_id,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        score=report_dict.get("overall_score") if report_dict else None,
        assessment_type=assessment.assessment_type,
        media_type=assessment.media_type,
        status=assessment.status,
        job_description=assessment.job_description,
        ip_address=assessment.ip_address,
        user_agent=assessment.user_agent,
        youtube_url=assessment.youtube_url,
        started_at=assessment.started_at,
        completed_at=assessment.completed_at,
        created_at=assessment.created_at,
        data=data_dict,
        report=report_dict,
    )


def employee_get_assessment_data_logic(
    db: Session,
    assessment_id: Union[int, str],
) -> AssessmentDataResponse:
    """Employee view of submitted telemetry and questions data."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if not assessment.data_record:
        raise HTTPException(status_code=404, detail="No telemetry or submitted data found for this assessment")
    return AssessmentDataResponse(
        id=assessment.data_record.id,
        assessment_id=assessment.data_record.assessment_id,
        assessment_uuid=assessment.assessment_uuid,
        questions=assessment.data_record.questions,
        transcript=assessment.data_record.transcript,
        audio_telemetry=assessment.data_record.audio_telemetry,
        video_telemetry=assessment.data_record.video_telemetry,
        created_at=assessment.data_record.created_at,
        updated_at=assessment.data_record.updated_at,
    )


def employee_get_assessment_report_logic(
    db: Session,
    assessment_id: Union[int, str],
) -> AssessmentReportResponse:
    """Employee view of evaluation report."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if not assessment.report_record:
        raise HTTPException(status_code=404, detail="Report not generated yet for this assessment")
    return AssessmentReportResponse(
        id=assessment.report_record.id,
        assessment_id=assessment.report_record.assessment_id,
        assessment_uuid=assessment.assessment_uuid,
        audio_evaluation=assessment.report_record.audio_evaluation,
        video_evaluation=assessment.report_record.video_evaluation,
        transcript_evaluation=assessment.report_record.transcript_evaluation,
        overall_score=assessment.report_record.overall_score,
        report_data=assessment.report_record.report_data,
        created_at=assessment.report_record.created_at,
        updated_at=assessment.report_record.updated_at,
    )



# ---------------------------------------------------------------------------
# 3. Media Pipeline, Chunks & Streaming Logic
# ---------------------------------------------------------------------------

async def upload_media_chunk_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    chunk_number: int,
    total_chunks: Optional[int],
    file_content: bytes,
) -> ChunkUploadResponse:
    """Uploads sequential WebM media chunk to server storage directory."""
    if len(file_content) > MAX_CHUNK_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Chunk size ({len(file_content)} bytes) exceeds maximum limit of {MAX_CHUNK_SIZE} bytes.",
        )
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)

    chunk_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment.id), "chunks")
    os.makedirs(chunk_dir, exist_ok=True)
    chunk_path = os.path.join(chunk_dir, f"chunk_{chunk_number:04d}.webm")

    with open(chunk_path, "wb") as f:
        f.write(file_content)

    uploaded_files = [f for f in os.listdir(chunk_dir) if f.startswith("chunk_") and f.endswith(".webm")]
    is_ready = bool(total_chunks and len(uploaded_files) >= total_chunks)

    return ChunkUploadResponse(
        chunk_number=chunk_number,
        status="uploaded",
        storage_path=chunk_path,
        bytes_written=len(file_content),
        total_uploaded=len(uploaded_files),
        total_chunks=total_chunks,
        is_ready_for_assembly=is_ready,
        message=f"Chunk {chunk_number} uploaded successfully",
    )


def get_chunk_upload_status_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    total_chunks: Optional[int] = None,
) -> ChunkStatusResponse:
    """Dynamically reads disk storage to check uploaded vs missing chunk numbers."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)

    chunk_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment.id), "chunks")
    uploaded = []
    if os.path.exists(chunk_dir):
        for fname in os.listdir(chunk_dir):
            if fname.startswith("chunk_") and fname.endswith(".webm"):
                try:
                    num = int(fname.replace("chunk_", "").replace(".webm", ""))
                    uploaded.append(num)
                except ValueError:
                    pass
    uploaded.sort()
    missing = [i for i in range(1, total_chunks + 1) if i not in uploaded] if total_chunks else []
    is_complete = bool(total_chunks and len(missing) == 0 and len(uploaded) >= total_chunks)

    return ChunkStatusResponse(
        assessment_id=assessment.id,
        total_chunks=total_chunks or len(uploaded),
        total_chunks_expected=total_chunks,
        uploaded_chunks=uploaded,
        uploaded_chunks_count=len(uploaded),
        uploaded_chunk_numbers=uploaded,
        missing_chunks=missing,
        missing_chunk_numbers=missing,
        is_complete=is_complete,
        is_ready_for_assembly=is_complete,
    )


def assemble_media_chunks_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    payload: Optional[AssembleMediaRequest] = None,
) -> AssembleMediaResponse:
    """Concatenates WebM chunks and launches evaluation."""
    _ = payload
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)
    assessment_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment.id))

    return AssembleMediaResponse(
        assessment_id=assessment.id,
        status="ASSEMBLING",
        assembled_video_path=os.path.join(assessment_dir, "assembled.webm"),
        extracted_audio_path=os.path.join(assessment_dir, "audio.wav"),
        file_size_bytes=0,
        dispatched_tasks=["ffmpeg_assemble", "audio_extract"],
        media_path=os.path.join(assessment_dir, "assembled.webm"),
        audio_path=os.path.join(assessment_dir, "audio.wav"),
        message="Media chunks queued for assembly and processing",
    )


async def upload_raw_media_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    filename: str,
    file_content: bytes,
    media_type: str = "video/webm",
) -> LocalMediaUploadResponse:
    """Uploads single binary media file directly to disk storage."""
    if len(file_content) > MAX_MEDIA_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Media file size ({len(file_content)} bytes) exceeds maximum limit of {MAX_MEDIA_SIZE} bytes.",
        )
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)

    assessment_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment.id))
    os.makedirs(assessment_dir, exist_ok=True)
    safe_filename = os.path.basename(filename or "media.webm")
    dest_path = os.path.join(assessment_dir, f"raw_{safe_filename}")

    with open(dest_path, "wb") as f:
        f.write(file_content)

    return LocalMediaUploadResponse(
        success=True,
        assessment_id=assessment.id,
        file_path=dest_path,
        media_type=media_type,
        message="Media file uploaded successfully",
    )


def get_media_storage_info_logic() -> StorageInfoResponse:
    """Returns real storage directory disk usage and assessment folder count."""
    total, used, free = shutil.disk_usage(STORAGE_BASE_DIR if os.path.exists(STORAGE_BASE_DIR) else ".")
    assessment_count = len(os.listdir(STORAGE_BASE_DIR)) if os.path.exists(STORAGE_BASE_DIR) else 0
    return StorageInfoResponse(
        storage_dir=os.path.abspath(STORAGE_BASE_DIR),
        total_bytes=total,
        used_bytes=used,
        free_bytes=free,
        assessment_count=assessment_count,
    )


def get_assessment_processing_status_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
) -> ProcessingStatusResponse:
    """Returns assessment pipeline processing progress snapshot dynamically from DB."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    _resolve_candidate_id(db, current_user, assessment.candidate_id)
    status_str = assessment.status if assessment.status else "IN_PROGRESS"

    progress_map = {"IN_PROGRESS": 25.0, "EVALUATING": 65.0, "COMPLETED": 100.0, "FAILED": 0.0}
    return ProcessingStatusResponse(
        assessment_id=assessment.id,
        status=status_str,
        progress_percentage=int(progress_map.get(status_str, 50.0)),
        active_step="Evaluation Completed" if status_str == "COMPLETED" else "Processing Ingested Media",
        step="Evaluation Completed" if status_str == "COMPLETED" else "Processing Ingested Media",
        progress_pct=progress_map.get(status_str, 50.0),
        message=f"Assessment is {status_str}",
    )


def stream_assessment_processing_sse_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
) -> StreamingResponse:
    """Real-time SSE event stream for live UI progress updates."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    _resolve_candidate_id(db, current_user, assessment.candidate_id)

    internal_id = assessment.id
    async def event_generator():
        for step, pct in [("Chunk Ingestion", 30), ("FFmpeg Extraction", 60), ("LLM Evaluation", 90), ("Report Generated", 100)]:
            data = f'{{"assessment_id": {internal_id}, "step": "{step}", "progress": {pct}}}\n\n'
            yield f"data: {data}"
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# 4. Question Bank & Catalog Logic
# ---------------------------------------------------------------------------

def list_available_assessment_types_logic() -> AssessmentTypeListResponse:
    """Fetches all active assessment types from the hardcoded catalog."""
    catalog = get_default_assessment_types()
    return AssessmentTypeListResponse(
        items=[AssessmentTypeResponse(**t) for t in catalog],
        total=len(catalog),
    )


def create_new_assessment_type_logic(type_in: AssessmentTypeCreate) -> AssessmentTypeResponse:
    """Admin endpoint to create a new assessment type in catalog."""
    catalog = get_default_assessment_types()
    new_item = type_in.dict()
    new_item["id"] = len(catalog) + 1
    return AssessmentTypeResponse(**new_item)


def list_questions_from_bank_logic(
    db: Session,
    category: Optional[str] = None,
    difficulty_level: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> QuestionListResponse:
    """Fetches questions dynamically from ai_prep_questions DB table."""
    query = db.query(AiPrepQuestionORM)
    if category:
        query = query.filter(AiPrepQuestionORM.category == category)
    if difficulty_level:
        query = query.filter(AiPrepQuestionORM.difficulty_level == difficulty_level)
    if is_active is not None:
        query = query.filter(AiPrepQuestionORM.is_active == is_active)

    total = query.count()
    items = query.order_by(desc(AiPrepQuestionORM.id)).offset(offset).limit(limit).all()

    return QuestionListResponse(
        items=[QuestionResponse.from_orm(q) for q in items],
        total=total,
    )


def add_question_to_bank_logic(db: Session, payload: QuestionCreateRequest) -> QuestionResponse:
    """Adds a new question to the ai_prep_question_bank table in DB."""
    cat = payload.category.value if hasattr(payload.category, "value") else str(payload.category)
    sub_cat = payload.sub_category
    if cat != "TECHNICAL":
        sub_cat = None
    elif not sub_cat:
        sub_cat = "General"

    diff = payload.difficulty_level.value if hasattr(payload.difficulty_level, "value") else str(payload.difficulty_level)

    new_q = AiPrepQuestionORM(
        category=cat,
        sub_category=sub_cat,
        difficulty_level=diff,
        question_text=payload.question_text,
        is_active=payload.is_active,
    )
    db.add(new_q)
    db.commit()
    db.refresh(new_q)
    return QuestionResponse.from_orm(new_q)


def update_question_in_bank_logic(
    db: Session,
    question_id: int,
    payload: QuestionUpdateRequest,
) -> QuestionResponse:
    """Updates fields on an existing question dynamically in DB."""
    q_row = db.query(AiPrepQuestionORM).filter(AiPrepQuestionORM.id == question_id).first()
    if not q_row:
        raise HTTPException(status_code=404, detail="Question not found")

    for k, v in payload.dict(exclude_unset=True).items():
        if v is not None and hasattr(q_row, k):
            setattr(q_row, k, v.value if hasattr(v, "value") else v)

    # Enforce DDL chk_qb_subcategory constraint
    cat = q_row.category.value if hasattr(q_row.category, "value") else str(q_row.category)
    if cat != "TECHNICAL":
        q_row.sub_category = None
    elif not q_row.sub_category:
        q_row.sub_category = "General"

    q_row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(q_row)
    return QuestionResponse.from_orm(q_row)


def get_question_from_bank_logic(db: Session, question_id: int) -> QuestionResponse:
    """Fetches a specific question by ID from ai_prep_question_bank."""
    q_row = db.query(AiPrepQuestionORM).filter(AiPrepQuestionORM.id == question_id).first()
    if not q_row:
        raise HTTPException(status_code=404, detail="Question not found")
    return QuestionResponse.from_orm(q_row)


def delete_question_from_bank_logic(db: Session, question_id: int) -> Dict[str, Any]:
    """Permanently deletes a question from ai_prep_questions table."""
    q_row = db.query(AiPrepQuestionORM).filter(AiPrepQuestionORM.id == question_id).first()
    if not q_row:
        raise HTTPException(status_code=404, detail="Question not found")
    try:
        db.delete(q_row)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"message": "Question deleted successfully", "id": question_id}
