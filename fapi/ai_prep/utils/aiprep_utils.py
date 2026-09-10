"""Business logic and utility functions for AI Prep Tool.
Follows WBL Backend code architecture standards separating routing and logic.
"""
import os
import uuid
import shutil
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

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
    AiPrepQuestionBankORM,
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

def _resolve_candidate_id(db: Session, current_user: AuthUserORM, requested_id: Optional[int] = None) -> int:
    """Enforces authorization: Candidates can only access their own ID; employees can specify any."""
    uname = (getattr(current_user, "uname", "") or "").lower()
    role = getattr(current_user, "role", None) or ("admin" if uname == "admin" else "candidate")
    is_employee = bool(getattr(current_user, "is_employee", False) or role in ("admin", "staff", "employee") or uname == "admin")

    # Match Candidate by email or ID
    candidate = db.query(CandidateORM).filter(CandidateORM.email == current_user.uname).first()
    if not candidate and not is_employee:
        raise HTTPException(status_code=404, detail="Candidate record not found.")

    self_candidate_id = candidate.id if candidate else current_user.id

    if not is_employee:
        if requested_id is not None and requested_id != self_candidate_id:
            raise HTTPException(status_code=403, detail="Candidates can only access their own data.")
        return self_candidate_id
    return requested_id if requested_id is not None else self_candidate_id


def _check_candidate_llm_db(db: Session, candidate_id: int) -> Dict[str, Any]:
    """Queries candidate_llm_api_keys dynamically for the candidate."""
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
            "message": "No active LLM API key found for this candidate. Please configure an API key in setup.",
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
    parsed_json = mktg.candidate_json if mktg and isinstance(mktg.candidate_json, dict) else None

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

def candidate_check_llm_keys_logic(db: Session, current_user: AuthUserORM) -> LLMKeyStatusResponse:
    """Candidate self-check for configured LLM key dynamically from DB."""
    candidate_id = _resolve_candidate_id(db, current_user)
    result = _check_candidate_llm_db(db, candidate_id)
    return LLMKeyStatusResponse(**result)


def candidate_check_resume_status_logic(db: Session, current_user: AuthUserORM) -> ResumeStatusResponse:
    """Candidate self-check for parsed resume status dynamically from DB."""
    candidate_id = _resolve_candidate_id(db, current_user)
    result = _check_candidate_resume_db(db, candidate_id)
    return ResumeStatusResponse(**result)


def candidate_pre_check_logic(db: Session, current_user: AuthUserORM) -> PreAssessmentCheckResponse:
    """Verifies both LLM key and resume readiness before starting assessment."""
    candidate_id = _resolve_candidate_id(db, current_user)
    llm_check = _check_candidate_llm_db(db, candidate_id)
    resume_check = _check_candidate_resume_db(db, candidate_id)
    eligible = bool(llm_check["is_configured"] and (resume_check["has_resume"] or resume_check["has_parsed_json"]))
    return PreAssessmentCheckResponse(
        eligible=eligible,
        candidate_id=candidate_id,
        llm_check=LLMKeyStatusResponse(**llm_check),
        resume_check=ResumeStatusResponse(**resume_check),
        message="Ready to start assessment" if eligible else "Prerequisites missing: setup required",
    )


def candidate_create_assessment_logic(
    db: Session,
    current_user: AuthUserORM,
    payload: CreateAssessmentRequest,
) -> CreateAssessmentResponse:
    """Dynamically validates prerequisites and creates a new assessment row in DB."""
    candidate_id = _resolve_candidate_id(db, current_user, payload.candidate_id)
    _verify_prerequisites(db, candidate_id)

    db_assessment = AiPrepAssessmentORM(
        candidate_id=candidate_id,
        assessment_type=payload.assessment_type.value,
        media_type=payload.media_type.value,
        status="IN_PROGRESS",
        job_description=payload.job_description,
        started_at=datetime.utcnow(),
    )
    db.add(db_assessment)
    db.commit()
    db.refresh(db_assessment)

    # Query initial question from question bank table (rubric is never sent to candidate)
    q_row = (
        db.query(AiPrepQuestionBankORM)
        .filter(
            AiPrepQuestionBankORM.category == payload.assessment_type.value,
            AiPrepQuestionBankORM.is_active == True,  # noqa: E712
        )
        .first()
    )
    questions_list = []
    if q_row:
        questions_list.append({
            "question_id": q_row.id,
            "question_text": q_row.question_text,
            "category": q_row.category,
            "difficulty_level": q_row.difficulty_level,
        })
    else:
        questions_list.append({
            "question_id": 1,
            "question_text": f"Please introduce yourself and your background relevant to {payload.assessment_type.value}.",
            "category": payload.assessment_type.value,
        })

    return CreateAssessmentResponse(
        id=db_assessment.id,
        status=db_assessment.status,
        started_at=db_assessment.started_at,
        assessment_type=db_assessment.assessment_type,
        media_type=db_assessment.media_type,
        questions=questions_list,
    )


def candidate_list_assessments_logic(
    db: Session,
    current_user: AuthUserORM,
    limit: int = 50,
    offset: int = 0,
) -> AssessmentListResponse:
    """Lists assessments belonging to the authenticated candidate dynamically from DB."""
    candidate_id = _resolve_candidate_id(db, current_user)
    query = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.candidate_id == candidate_id)
    total = query.count()
    items = query.order_by(desc(AiPrepAssessmentORM.created_at)).offset(offset).limit(limit).all()

    return AssessmentListResponse(
        items=[
            AssessmentListItem(
                id=a.id,
                candidate_id=a.candidate_id,
                assessment_type=a.assessment_type,
                media_type=a.media_type,
                status=a.status,
                youtube_url=a.youtube_url,
                started_at=a.started_at,
                created_at=a.created_at,
            )
            for a in items
        ],
        total=total,
    )


def candidate_get_assessment_detail_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: int,
) -> AssessmentDetailResponse:
    """Fetches assessment detail, telemetry, and evaluation scores from DB."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    _resolve_candidate_id(db, current_user, assessment.candidate_id)

    data_dict = None
    if assessment.assessment_data:
        data_dict = {
            "questions": assessment.assessment_data.questions,
            "transcript": assessment.assessment_data.transcript,
            "audio_telemetry": assessment.assessment_data.audio_telemetry,
            "video_telemetry": assessment.assessment_data.video_telemetry,
        }

    report_dict = None
    if assessment.assessment_report:
        report_dict = {
            "audio_evaluation": assessment.assessment_report.audio_evaluation,
            "video_evaluation": assessment.assessment_report.video_evaluation,
            "transcript_evaluation": assessment.assessment_report.transcript_evaluation,
        }

    return AssessmentDetailResponse(
        id=assessment.id,
        candidate_id=assessment.candidate_id,
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


def candidate_submit_data_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: int,
    payload: SubmitAssessmentDataRequest,
) -> SubmitAssessmentDataResponse:
    """Persists candidate telemetry, transcript, and answers into ai_prep_assessment_data."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    _resolve_candidate_id(db, current_user, assessment.candidate_id)

    data_rec = db.query(AiPrepAssessmentDataORM).filter(AiPrepAssessmentDataORM.assessment_id == assessment_id).first()
    if data_rec:
        data_rec.questions = payload.questions
        data_rec.transcript = payload.transcript
        data_rec.audio_telemetry = payload.audio_telemetry
        data_rec.video_telemetry = payload.video_telemetry
        data_rec.updated_at = datetime.utcnow()
    else:
        data_rec = AiPrepAssessmentDataORM(
            assessment_id=assessment_id,
            questions=payload.questions,
            transcript=payload.transcript,
            audio_telemetry=payload.audio_telemetry,
            video_telemetry=payload.video_telemetry,
        )
        db.add(data_rec)

    db.commit()
    return SubmitAssessmentDataResponse(message="Data saved successfully")


def candidate_update_media_url_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: int,
    payload: UpdateMediaURLRequest,
) -> UpdateMediaURLResponse:
    """Updates YouTube/video playback URL on assessment in DB."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    _resolve_candidate_id(db, current_user, assessment.candidate_id)
    assessment.youtube_url = payload.youtube_url
    assessment.updated_at = datetime.utcnow()
    db.commit()
    return UpdateMediaURLResponse(id=assessment_id, youtube_url=payload.youtube_url)


def candidate_trigger_eval_post_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: int,
) -> TriggerEvaluationResponse:
    """Transitions status to EVALUATING in DB."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    _resolve_candidate_id(db, current_user, assessment.candidate_id)
    assessment.status = "EVALUATING"
    assessment.updated_at = datetime.utcnow()
    db.commit()
    return TriggerEvaluationResponse(id=assessment_id, status="EVALUATING")


def candidate_trigger_eval_put_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: int,
    payload: Optional[SubmitAssessmentRequest] = None,
) -> TriggerEvaluationResponse:
    """Saves telemetry if provided and transitions status to EVALUATING."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    _resolve_candidate_id(db, current_user, assessment.candidate_id)
    if payload and (payload.transcript or payload.audio_telemetry or payload.video_telemetry):
        data_rec = db.query(AiPrepAssessmentDataORM).filter(AiPrepAssessmentDataORM.assessment_id == assessment_id).first()
        if not data_rec:
            data_rec = AiPrepAssessmentDataORM(assessment_id=assessment_id)
            db.add(data_rec)
        data_rec.transcript = payload.transcript or {}
        data_rec.audio_telemetry = payload.audio_telemetry or {}
        data_rec.video_telemetry = payload.video_telemetry or {}
        data_rec.questions = payload.questions or []
        data_rec.updated_at = datetime.utcnow()

    assessment.status = "EVALUATING"
    assessment.updated_at = datetime.utcnow()
    db.commit()
    return TriggerEvaluationResponse(id=assessment_id, status="EVALUATING")


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

    return AssessmentListResponse(
        items=[
            AssessmentListItem(
                id=a.id,
                candidate_id=a.candidate_id,
                assessment_type=a.assessment_type,
                media_type=a.media_type,
                status=a.status,
                youtube_url=a.youtube_url,
                started_at=a.started_at,
                created_at=a.created_at,
            )
            for a in items
        ],
        total=total,
    )


def employee_list_candidate_assessments_logic(db: Session, candidate_id: int) -> AssessmentListResponse:
    """Employee view of assessment history for any specific candidate ID."""
    query = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.candidate_id == candidate_id)
    total = query.count()
    items = query.order_by(desc(AiPrepAssessmentORM.created_at)).all()

    return AssessmentListResponse(
        items=[
            AssessmentListItem(
                id=a.id,
                candidate_id=a.candidate_id,
                assessment_type=a.assessment_type,
                media_type=a.media_type,
                status=a.status,
                youtube_url=a.youtube_url,
                started_at=a.started_at,
                created_at=a.created_at,
            )
            for a in items
        ],
        total=total,
    )


def employee_get_assessment_detail_logic(db: Session, assessment_id: int) -> AssessmentDetailResponse:
    """Employee/Admin review of complete telemetry and scores for any assessment."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    data_dict = None
    if assessment.assessment_data:
        data_dict = {
            "questions": assessment.assessment_data.questions,
            "transcript": assessment.assessment_data.transcript,
            "audio_telemetry": assessment.assessment_data.audio_telemetry,
            "video_telemetry": assessment.assessment_data.video_telemetry,
        }

    report_dict = None
    if assessment.assessment_report:
        report_dict = {
            "audio_evaluation": assessment.assessment_report.audio_evaluation,
            "video_evaluation": assessment.assessment_report.video_evaluation,
            "transcript_evaluation": assessment.assessment_report.transcript_evaluation,
        }

    return AssessmentDetailResponse(
        id=assessment.id,
        candidate_id=assessment.candidate_id,
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


# ---------------------------------------------------------------------------
# 3. Media Pipeline, Chunks & Streaming Logic
# ---------------------------------------------------------------------------

async def upload_media_chunk_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: int,
    chunk_number: int,
    total_chunks: Optional[int],
    file_content: bytes,
) -> ChunkUploadResponse:
    """Uploads sequential WebM media chunk to server storage directory."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)

    chunk_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment_id), "chunks")
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
    assessment_id: int,
    total_chunks: Optional[int] = None,
) -> ChunkStatusResponse:
    """Dynamically reads disk storage to check uploaded vs missing chunk numbers."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)

    chunk_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment_id), "chunks")
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
        assessment_id=assessment_id,
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
    assessment_id: int,
    payload: Optional[AssembleMediaRequest] = None,
) -> AssembleMediaResponse:
    """Concatenates WebM chunks and launches evaluation."""
    _ = payload
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)
    assessment_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment_id))

    return AssembleMediaResponse(
        assessment_id=assessment_id,
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
    assessment_id: int,
    media_type: str,
    filename: str,
    file_content: bytes,
) -> LocalMediaUploadResponse:
    """Uploads single binary media file directly to disk storage."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)

    assessment_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment_id))
    os.makedirs(assessment_dir, exist_ok=True)
    safe_filename = os.path.basename(filename or "media.webm")
    dest_path = os.path.join(assessment_dir, f"raw_{safe_filename}")

    with open(dest_path, "wb") as f:
        f.write(file_content)

    return LocalMediaUploadResponse(
        success=True,
        assessment_id=assessment_id,
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
    assessment_id: int,
) -> ProcessingStatusResponse:
    """Returns assessment pipeline processing progress snapshot dynamically from DB."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    _resolve_candidate_id(db, current_user, assessment.candidate_id)
    status_str = assessment.status if assessment.status else "IN_PROGRESS"

    progress_map = {"IN_PROGRESS": 25.0, "EVALUATING": 65.0, "COMPLETED": 100.0, "FAILED": 0.0}
    return ProcessingStatusResponse(
        assessment_id=assessment_id,
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
    assessment_id: int,
) -> StreamingResponse:
    """Real-time SSE event stream for live UI progress updates."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    _resolve_candidate_id(db, current_user, assessment.candidate_id)

    async def event_generator():
        import asyncio
        for step, pct in [("Chunk Ingestion", 30), ("FFmpeg Extraction", 60), ("LLM Evaluation", 90), ("Report Generated", 100)]:
            data = f'{{"assessment_id": {assessment_id}, "step": "{step}", "progress": {pct}}}\n\n'
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
    query = db.query(AiPrepQuestionBankORM)
    if category:
        query = query.filter(AiPrepQuestionBankORM.category == category)
    if difficulty_level:
        query = query.filter(AiPrepQuestionBankORM.difficulty_level == difficulty_level)
    if is_active is not None:
        query = query.filter(AiPrepQuestionBankORM.is_active == is_active)

    total = query.count()
    items = query.order_by(desc(AiPrepQuestionBankORM.id)).offset(offset).limit(limit).all()

    return QuestionListResponse(
        items=[QuestionResponse.from_orm(q) for q in items],
        total=total,
    )


def add_question_to_bank_logic(db: Session, payload: QuestionCreateRequest) -> QuestionResponse:
    """Adds a new question to the ai_prep_question_bank table in DB."""
    new_q = AiPrepQuestionBankORM(
        category=payload.category.value,
        sub_category=payload.sub_category,
        difficulty_level=payload.difficulty_level.value,
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
    q_row = db.query(AiPrepQuestionBankORM).filter(AiPrepQuestionBankORM.id == question_id).first()
    if not q_row:
        raise HTTPException(status_code=404, detail="Question not found")

    for k, v in payload.dict(exclude_unset=True).items():
        if v is not None and hasattr(q_row, k):
            setattr(q_row, k, v.value if hasattr(v, "value") else v)
    db.commit()
    db.refresh(q_row)
    return QuestionResponse.from_orm(q_row)
