"""Business logic and utility functions for AI Prep Tool.
Follows WBL Backend code architecture standards separating routing and logic.
"""
import os
import uuid
import json
import shutil
import logging
import asyncio
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import HTTPException, status, BackgroundTasks, UploadFile, Request
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_

from fapi.db import database as db_database


def SessionLocal():
    """Returns a short-lived SQLAlchemy Session dynamically resolved from database module."""
    return db_database.SessionLocal()


from fapi.ai_prep import crud
from fapi.ai_prep.config import settings
from fapi.ai_prep.orchestrator import assessment_orchestrator, llm_orchestrator
from fapi.ai_prep.core.audio_engine import AudioMetricsEngine, InvalidProviderConfigError
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
    CreateAssessmentData,
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
    MediaChunkUploadResponse,
    MediaChunkUploadData,
    ChunkUploadResponse,
    ChunkStatusResponse,
    AssembleMediaRequest,
    AssembleMediaResponse,
    LocalMediaUploadResponse,
    StorageInfoResponse,
    ProcessingStatusResponse,
    AudioUploadResponse,
    QuestionCreateRequest,
    QuestionUpdateRequest,
    QuestionResponse,
    QuestionListResponse,
    CandidateSubmitAssessmentRequest,
    CandidateSubmitAssessmentResponse,
    CandidateSubmitAssessmentData,
    AssessmentMetaResponse,
    AssessmentTranscriptData,
    AssessmentTelemetryData,
    AssessmentSubmitReportData,
    CandidateAssessmentDetailTranscript,
    CandidateAssessmentDataDetail,
    CandidateAssessmentReportDetail,
    CandidateAssessmentDetailData,
    CandidateAssessmentDetailResponse,
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

def _resolve_candidate_id(
    db: Session,
    current_user: AuthUserORM,
    requested_id: Optional[Union[int, str]] = None,
) -> int:
    """Securely resolves candidate ID and enforces strict multi-tenant authorization."""
    uname = (getattr(current_user, "uname", "") or "").strip().lower()
    role = (getattr(current_user, "role", None) or "").lower()
    is_employee = bool(
        getattr(current_user, "is_employee", False)
        or role in ("admin", "staff", "employee")
        or uname == "admin"
    )

    # 1. Parse requested_id if provided
    req_int: Optional[int] = None
    if requested_id is not None:
        try:
            req_int = int(requested_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid candidate ID format.")

    # 2. Staff / Admin can query any requested candidate ID
    if is_employee:
        if req_int is not None:
            return req_int

    # 3. For Candidates: Authenticate by email (case-insensitive) across primary and secondary emails
    candidate = (
        db.query(CandidateORM)
        .filter(
            or_(
                func.lower(CandidateORM.email) == uname,
                func.lower(CandidateORM.secondaryemail) == uname,
            )
        )
        .first()
    )

    # If no candidate record is bound to this user's login email
    if not candidate:
        if is_employee:
            return req_int if req_int is not None else getattr(current_user, "id", 0)
        raise HTTPException(
            status_code=404,
            detail="No candidate profile is associated with this authenticated account.",
        )

    # 4. Strict Ownership Guard (Candidates can only access their own profile)
    if req_int is not None and req_int != candidate.id:
        raise HTTPException(
            status_code=403, detail="Candidates can only access their own data."
        )

    return candidate.id


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
            "message": "Candidate has not uploaded or synced a resume in 'My Resume'.",
        }

    current_title: Optional[str] = None
    if parsed_json:
        raw_title = parsed_json.get("current_title") or parsed_json.get("title")
        current_title = str(raw_title).strip() if raw_title else None

    return {
        "status": "valid",
        "has_resume": True,
        "has_parsed_json": bool(parsed_json),
        "candidate_name": candidate_name,
        "current_title": current_title,
        "skills": [],
        "message": "Candidate resume is verified and ready in 'My Resume'.",
    }


def _verify_prerequisites(db: Session, candidate_id: int):
    """Enforces prerequisite checks before starting an assessment."""
    llm_status = _check_candidate_llm_db(db, candidate_id)
    resume_status = _check_candidate_resume_db(db, candidate_id)

    errors = []
    if not llm_status["is_configured"]:
        errors.append("Active LLM API Key is missing or invalid in 'My LLM Setup'.")
    if not resume_status["has_resume"] and not resume_status["has_parsed_json"]:
        errors.append("Resume has not been uploaded or parsed in 'My Resume'.")

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
    try:
        candidate_id = _resolve_candidate_id(db, current_user)
        result = _check_candidate_llm_db(db, candidate_id)
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


def candidate_check_resume_status_logic(db: Session, current_user: AuthUserORM) -> ResumeStatusResponse:
    """Candidate self-check for parsed resume status dynamically from DB."""
    try:
        candidate_id = _resolve_candidate_id(db, current_user)
        result = _check_candidate_resume_db(db, candidate_id)
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


def assessment_readiness_precheck_logic(
    db: Session, current_user: AuthUserORM, candidate_id: Union[int, str]
) -> PreAssessmentCheckResponse:
    """Checks whether candidate has active LLM key in 'My LLM Setup' and resume in 'My Resume'.

    Only allows candidate to proceed with assessment if both prerequisites are met;
    otherwise specifies the respective setup required.
    """
    resolved_id = _resolve_candidate_id(db, current_user, requested_id=candidate_id)

    cand = db.query(CandidateORM).filter(CandidateORM.id == resolved_id).first()
    if not cand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with ID {resolved_id} not found.",
        )

    llm_check = _check_candidate_llm_db(db, resolved_id)
    resume_check = _check_candidate_resume_db(db, resolved_id)

    has_active_llm = bool(llm_check.get("is_configured"))
    has_resume = bool(resume_check.get("has_resume") or resume_check.get("has_parsed_json"))
    eligible = bool(has_active_llm and has_resume)
    allowed_to_proceed = eligible

    if eligible:
        message = "Candidate is ready to proceed with assessment."
        action_required = None
    elif not has_active_llm and not has_resume:
        message = "Cannot proceed with assessment. Active LLM key missing in 'My LLM Setup' and resume missing in 'My Resume'."
        action_required = "both"
    elif not has_active_llm:
        message = "Cannot proceed with assessment. Please configure an active LLM key in 'My LLM Setup'."
        action_required = "my-llm-setup"
    else:
        message = "Cannot proceed with assessment. Please upload or sync your resume in 'My Resume'."
        action_required = "my-resume"

    return PreAssessmentCheckResponse(
        eligible=eligible,
        allowed_to_proceed=allowed_to_proceed,
        candidate_id=resolved_id,
        llm_check=LLMKeyStatusResponse(**llm_check),
        resume_check=ResumeStatusResponse(**resume_check),
        message=message,
        action_required=action_required,
    )


def candidate_pre_check_logic(db: Session, current_user: AuthUserORM) -> PreAssessmentCheckResponse:
    """Verifies both LLM key and resume readiness before starting assessment."""
    try:
        candidate_id = _resolve_candidate_id(db, current_user)
        return assessment_readiness_precheck_logic(db, current_user, candidate_id)
    except HTTPException as e:
        if e.status_code == 404:
            cand_name = getattr(current_user, "fullname", None) or getattr(current_user, "uname", "Candidate")
            return PreAssessmentCheckResponse(
                eligible=False,
                allowed_to_proceed=False,
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
                action_required="both",
            )
        raise




def candidate_create_assessment_logic(
    db: Session,
    current_user: AuthUserORM,
    candidate_id: Union[int, str],
    payload: CreateAssessmentRequest,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> CreateAssessmentResponse:
    """Dynamically validates prerequisites and creates a new assessment row in DB."""
    if payload.candidate_id is not None and str(payload.candidate_id) != str(candidate_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"candidate_id in request body ({payload.candidate_id}) does not match candidate id in URL path ({candidate_id}).",
        )
    resolved_candidate_id = _resolve_candidate_id(db, current_user, requested_id=candidate_id)
    _verify_prerequisites(db, resolved_candidate_id)

    assessment_type_str = (
        payload.assessment_type.value
        if hasattr(payload.assessment_type, "value")
        else str(payload.assessment_type)
    ).upper().strip()

    # Step 1: Retrieve the question BEFORE creating the assessment row.
    # If no active question exists for this type the function must fail here
    # without creating any database record.
    try:
        questions_list = assessment_orchestrator.get_questions_for_assessment(
            db=db,
            assessment_type=assessment_type_str,
            candidate_id=resolved_candidate_id,
        )
    except Exception as exc:
        logger.error(
            "Question bank retrieval failed for type '%s': %s",
            assessment_type_str, exc,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The question could not be loaded. Please try again or contact support.",
        )

    if not questions_list:
        logger.warning(
            "No active questions found in the question bank for type '%s'.",
            assessment_type_str,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The question could not be loaded. Please try again or contact support.",
        )

    # Step 2: Question confirmed — now create the assessment record.
    media_type_str = (
        payload.media_type.value
        if hasattr(payload.media_type, "value")
        else str(payload.media_type)
    ).upper().strip()

    db_assessment = crud.create_assessment(
        db=db,
        candidate_id=resolved_candidate_id,
        assessment_type=assessment_type_str,
        media_type=media_type_str,
        job_description=payload.job_description,
        ip_address=ip_address,
        user_agent=user_agent,
        consent=payload.consent,
    )

    # Step 3: Persist the selected question snapshot into ai_prep_assessment_data.
    try:
        crud.save_assessment_data(
            db=db,
            assessment_id=db_assessment.id,
            questions=questions_list,
            transcript={},
            audio_telemetry={},
            video_telemetry={},
        )
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to persist assessment questions into assessment_data: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist assessment questions",
        )

    formatted_questions = []
    for q in questions_list:
        formatted_questions.append({
            "id": q.get("id"),
            "category": q.get("category"),
            "question_text": q.get("question_text"),
            "difficulty_level": q.get("difficulty_level"),
            **({} if q.get("sub_category") is None else {"sub_category": q.get("sub_category")}),
        })

    return CreateAssessmentResponse(
        status="success",
        data=CreateAssessmentData(
            assessment_id=db_assessment.id,
            assessment_uuid=db_assessment.assessment_uuid,
            candidate_id=resolved_candidate_id,
            assessment_type=db_assessment.assessment_type,
            media_type=db_assessment.media_type,
            status=db_assessment.status,
            started_at=db_assessment.started_at,
            questions=formatted_questions,
        ),
    )


def candidate_list_assessments_logic(
    db: Session,
    current_user: AuthUserORM,
    candidate_id: Optional[Union[int, str]] = None,
    limit: Optional[int] = 50,
    offset: int = 0,
) -> AssessmentListResponse:
    """Lists assessments belonging to the candidate dynamically from DB.

    Authorization:
    - Candidates can only access their own assessments; attempting to access another
      candidate's ID raises HTTP 403 Forbidden.
    - Staff / Admin users can view any candidate's assessments.
    """
    resolved_candidate_id = _resolve_candidate_id(db, current_user, requested_id=candidate_id)
    cand = db.query(CandidateORM).filter(CandidateORM.id == resolved_candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    candidate_name = cand.full_name if (cand and cand.full_name) else None
    candidate_email = cand.email if (cand and cand.email) else None

    items, total = crud.list_candidate_assessments(
        db=db,
        candidate_id=resolved_candidate_id,
        limit=limit,
        offset=offset,
    )

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
                consent=a.consent,
                started_at=a.started_at,
                completed_at=a.completed_at,
                cancelled_at=getattr(a, "cancelled_at", None),
                created_at=a.created_at,
            )
            for a in items
        ],
        total=total,
    )



def candidate_get_assessment_detail_logic(
    db: Session,
    current_user: AuthUserORM,
    candidate_id: Union[int, str],
    assessment_id: Union[int, str],
) -> CandidateAssessmentDetailResponse:
    """
    Returns the complete details of a specific assessment for a candidate.

    Authorization:
    - Candidates can only access their own assessments; attempting to access another
      candidate's data raises HTTP 403 at two independent enforcement points:
        1. _resolve_candidate_id() rejects a mismatched candidate_id path param.
        2. An ownership check confirms the fetched assessment belongs to the resolved candidate.
    - Staff / admin users may access any candidate's assessment via the same endpoint.
    """
    # --- Layer 1: Resolve & authorize the candidate_id path parameter ---
    resolved_candidate_id = _resolve_candidate_id(db, current_user, requested_id=candidate_id)

    # --- Fetch assessment (by integer PK or UUID string) ---
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # --- Layer 2: Ownership check — assessment must belong to the resolved candidate ---
    if assessment.candidate_id != resolved_candidate_id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this assessment.",
        )

    # --- Build `assessment` block ---
    assessment_meta = AssessmentMetaResponse(
        id=assessment.id,
        assessment_uuid=assessment.assessment_uuid,
        candidate_id=assessment.candidate_id,
        assessment_type=assessment.assessment_type,
        media_type=assessment.media_type,
        status=assessment.status,
        started_at=assessment.started_at,
        completed_at=assessment.completed_at,
        youtube_url=assessment.youtube_url,
    )

    # --- Build `assessment_data` block (transcript + telemetry) ---
    if assessment.data_record:
        raw_transcript = assessment.data_record.transcript or {}
        transcript_obj = CandidateAssessmentDetailTranscript(
            full_text=raw_transcript.get("full_text", ""),
            word_count=raw_transcript.get("word_count", 0),
            segments=raw_transcript.get("segments", []),
        )
        audio_telemetry = assessment.data_record.audio_telemetry or {}
        video_telemetry = assessment.data_record.video_telemetry or {}
    else:
        transcript_obj = CandidateAssessmentDetailTranscript()
        audio_telemetry: Dict[str, Any] = {}
        video_telemetry: Dict[str, Any] = {}

    assessment_data_obj = CandidateAssessmentDataDetail(
        transcript=transcript_obj,
        audio_telemetry=audio_telemetry,
        video_telemetry=video_telemetry,
    )

    # --- Build `report` block ---
    # insufficient_content=False when a full LLM evaluation report exists.
    # insufficient_content=True when the assessment completed but the LLM evaluation
    # was skipped (e.g. transcript too short) or the report has not been generated yet.
    if assessment.report_record:
        insufficient_content = False
        message = None
        llm_evaluation: Optional[Dict[str, Any]] = {
            "transcript_evaluation": assessment.report_record.transcript_evaluation,
            "audio_evaluation": assessment.report_record.audio_evaluation,
            "video_evaluation": assessment.report_record.video_evaluation,
        }
    else:
        insufficient_content = True
        message = "Evaluation report is not yet available for this assessment."
        llm_evaluation = None

    report_obj = CandidateAssessmentReportDetail(
        insufficient_content=insufficient_content,
        message=message,
        llm_evaluation=llm_evaluation,
    )

    return CandidateAssessmentDetailResponse(
        status="success",
        data=CandidateAssessmentDetailData(
            assessment=assessment_meta,
            assessment_data=assessment_data_obj,
            report=report_obj,
        ),
    )


MIN_TRANSCRIPT_WORDS_THRESHOLD = int(os.getenv("AIPREP_MIN_WORDS_THRESHOLD", "15"))
MIN_INTERVIEW_DURATION_SECONDS = float(os.getenv("AIPREP_MIN_DURATION_SECONDS", "20.0"))


def evaluate_gatekeeper_flag(
    word_count: int,
    duration_seconds: float,
    min_words: int = MIN_TRANSCRIPT_WORDS_THRESHOLD,
    min_duration: float = MIN_INTERVIEW_DURATION_SECONDS,
) -> bool:
    """
    Evaluates gatekeeper flag for assessment content sufficiency.
    Returns True if content is INSUFFICIENT (Flag is ON).

    CRITICAL REQUIREMENTS:
    - Strictly considers ONLY the words of the transcript and interview duration time.
    - Does NOT consider silence percentage or acoustic DSP metrics.
    - If candidate took the whole interview in silence or mute, word_count is 0 (< min_words),
      evaluating to True (insufficient_content: True).
    - If interview duration is less than min_duration seconds, evaluating to True.
    - This flag is evaluated in-memory and is NOT stored in the database.
    """
    if word_count < min_words:
        return True
    if duration_seconds < min_duration:
        return True
    return False


def _stitch_assessment_chunks(
    candidate_id: int,
    assessment_id: int,
    total_chunks_uploaded: Optional[int] = None,
) -> str:
    """Stitches chunks from chunks/ into assembled.webm, or returns existing assembled media."""
    from fapi.ai_prep.core.video_processor_engine import validate_chunk_sequence

    assessment_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment_id))
    video_path = os.path.join(assessment_dir, "assembled.webm")
    audio_path = os.path.join(assessment_dir, "audio.wav")
    chunk_dir = os.path.join(assessment_dir, "chunks")

    if os.path.exists(chunk_dir):
        uploaded = []
        try:
            for fname in os.listdir(chunk_dir):
                if fname.startswith("chunk_") and fname.endswith(".webm"):
                    try:
                        num = int(fname.replace("chunk_", "").replace(".webm", ""))
                        uploaded.append(num)
                    except ValueError:
                        pass
        except (PermissionError, OSError) as err:
            logger.error("Could not read chunk directory %s: %s", chunk_dir, err)
            raise HTTPException(status_code=500, detail="Failed to access chunk storage on server")

        if uploaded:
            uploaded = sorted(list(set(uploaded)))
            total_expected = total_chunks_uploaded if (total_chunks_uploaded and total_chunks_uploaded > 0) else len(uploaded)
            start_index = 0 if (0 in uploaded or (uploaded and min(uploaded) == 0)) else 1

            seq_val = validate_chunk_sequence(existing_chunks=uploaded, total_expected=total_expected, start_index=start_index)
            if not seq_val["is_valid"]:
                logger.warning("Chunk assembly rejected for assessment %s: %s", assessment_id, seq_val["error"])
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Incomplete chunk sequence. {seq_val['error']}",
                )

            chunk_files = []
            for i in range(start_index, start_index + total_expected):
                p1 = os.path.join(chunk_dir, f"chunk_{i}.webm")
                p2 = os.path.join(chunk_dir, f"chunk_{i:04d}.webm")
                if os.path.exists(p1):
                    chunk_files.append(p1)
                elif os.path.exists(p2):
                    chunk_files.append(p2)
                else:
                    chunk_files.append(p1)

            try:
                os.makedirs(assessment_dir, exist_ok=True)
                with open(video_path, "wb") as outfile:
                    for cf in chunk_files:
                        if not os.path.exists(cf):
                            raise FileNotFoundError(f"Chunk file missing: {cf}")
                        with open(cf, "rb") as infile:
                            shutil.copyfileobj(infile, outfile, length=1024 * 1024)
            except Exception as asm_err:
                logger.error("Chunk assembly failed for assessment %s: %s", assessment_id, asm_err)
                raise HTTPException(status_code=500, detail=f"Failed to assemble media chunks: {asm_err}")

    if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
        return video_path
    if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
        return audio_path

    raise HTTPException(status_code=400, detail="No media chunks or recordings found to assemble for this assessment")


def resolve_storage_plan(
    consent: Optional[Dict[str, Any]],
    media_type: Optional[str],
    formatted_transcript: Dict[str, Any],
    formatted_audio_telemetry: Dict[str, Any],
    formatted_video_telemetry: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Centralized resolver that determines candidate consent flags and corresponding
    data payloads to persist in the database, preserving all existing schemas.
    """
    consent_dict = consent if isinstance(consent, dict) else {}
    save_recording = bool(consent_dict.get("save_recording", True))
    save_transcript = bool(consent_dict.get("save_transcript", True))
    video_analytics = bool(consent_dict.get("video_analytics", True))
    if (media_type or "").upper() == "AUDIO":
        video_analytics = False

    transcript_to_persist = formatted_transcript if save_transcript else {
        "full_text": "",
        "word_count": formatted_transcript.get("word_count", 0),
        "segments": [],
        "saved": False,
    }
    audio_telemetry_to_persist = formatted_audio_telemetry if save_recording else {}
    video_telemetry_to_persist = formatted_video_telemetry if video_analytics else {}

    return {
        "save_recording": save_recording,
        "save_transcript": save_transcript,
        "video_analytics": video_analytics,
        "transcript_to_persist": transcript_to_persist,
        "audio_telemetry_to_persist": audio_telemetry_to_persist,
        "video_telemetry_to_persist": video_telemetry_to_persist,
    }


async def candidate_submit_assessment_logic(
    db: Session,
    current_user: AuthUserORM,
    candidate_id: Union[int, str],
    assessment_id: Union[int, str],
    payload: Optional[CandidateSubmitAssessmentRequest] = None,
    status: Optional[str] = None,
    background_tasks: Optional[BackgroundTasks] = None,
) -> Union[CandidateSubmitAssessmentResponse, Dict[str, Any]]:
    """
    Candidate Submit Assessment:
    - If status == 'cancelled' (e.g. Exit button clicked): updates assessment status to CANCELLED in DB
      and immediately returns {"Status": "CANCELLED"}, skipping all other assessment logic.
    - Otherwise:
      1. Validates candidate permissions and assessment existence.
      2. Stitches uploaded media chunks into assembled.webm.
      3. Runs Audio Engine (Whisper STT + acoustic metrics).
      4. Evaluates the gatekeeper flag (insufficient_content) strictly based on transcript word count
         and interview duration (ignores silence percentage; handles full-silence/mute as insufficient).
      5. Saves assessment data into DB.
      6. If flag is ON: updates status to COMPLETED, sets completed_at, skips LLM evaluation.
         If flag is OFF: updates status to EVALUATING, queues background LLM evaluation.
      7. Returns complete assessment metadata, telemetry, and report status.
    """
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    resolved_cand_id = _resolve_candidate_id(
        db, current_user, requested_id=int(candidate_id) if str(candidate_id).isdigit() else None
    )
    if assessment.candidate_id != resolved_cand_id:
        raise HTTPException(status_code=403, detail="Candidates can only submit their own assessments")

    # If candidate clicked Exit button, change status to CANCELLED and return immediately
    status_override = (
        status or (payload.status if payload else None) or ""
    ).strip().upper()

    if status_override == "CANCELLED":
        crud.update_assessment_status(db, assessment.id, "CANCELLED")
        return {
            "Status": "CANCELLED",
            "status": "CANCELLED",
            "assessment_id": assessment.id,
            "assessment_status": "CANCELLED",
            "message": "Assessment cancelled successfully",
            "data": {
                "id": assessment.id,
                "status": "CANCELLED",
                "Status": "CANCELLED",
                "assessment_status": "CANCELLED",
            },
        }

    # Lifecycle State Guard: Disallow resubmitting assessments that are already closed or evaluating
    if assessment.status in ("COMPLETED", "CANCELLED", "FAILED", "EVALUATING"):
        raise HTTPException(
            status_code=409,
            detail=f"Assessment is already {assessment.status}. Cannot resubmit or retake an assessment that is closed or currently evaluating.",
        )

    payload = payload or CandidateSubmitAssessmentRequest()

    total_chunks = payload.total_chunks_uploaded
    if not total_chunks:
        existing_data = crud.get_assessment_data_by_assessment_id(db, assessment.id)
        if existing_data and existing_data.video_telemetry:
            total_chunks = existing_data.video_telemetry.get("total_expected_chunks")

    # 1. Stitch media chunks
    target_media = _stitch_assessment_chunks(
        candidate_id=resolved_cand_id,
        assessment_id=assessment.id,
        total_chunks_uploaded=total_chunks,
    )

    # 2. Run Audio Engine
    try:
        audio_result = await asyncio.to_thread(AudioMetricsEngine.process_audio_file, target_media)
        spoken_content = audio_result.get("spoken_content") or {}
        raw_audio_telemetry = audio_result.get("audio_telemetry") or {}
    except Exception as audio_err:
        logger.warning("Audio Engine execution error for assessment %s: %s", assessment.id, audio_err)
        spoken_content = {"transcript_text": "", "full_text": "", "segments": []}
        raw_audio_telemetry = {
            "speaking_duration_seconds": 0.0,
            "wpm": 0,
            "filler_count": 0,
            "silence_ratio": 1.0,
            "total_audio_duration_seconds": payload.client_duration_seconds or 0.0,
        }

    # 3. Format Transcript
    full_text = (spoken_content.get("full_text") or spoken_content.get("transcript_text") or "").strip()
    words = [w for w in full_text.split() if w]
    word_count = spoken_content.get("word_count")
    if word_count is None:
        word_count = len(words)

    raw_segments = spoken_content.get("segments") or []
    segments = []
    if raw_segments:
        for seg in raw_segments:
            segments.append({
                "start": float(seg.get("start", 0.0)),
                "end": float(seg.get("end", 0.0)),
                "text": str(seg.get("text", "")).strip(),
            })
    elif full_text:
        duration_val = float(payload.client_duration_seconds or raw_audio_telemetry.get("total_audio_duration_seconds") or 0.0)
        segments = [{"start": 0.0, "end": round(duration_val, 1), "text": full_text}]

    formatted_transcript = {
        "full_text": full_text,
        "word_count": word_count,
        "segments": segments,
    }

    # 4. Format Audio Telemetry
    speaking_duration_sec = float(
        raw_audio_telemetry.get("speaking_duration_seconds")
        or raw_audio_telemetry.get("speaking_duration_sec")
        or 0.0
    )
    wpm = int(
        raw_audio_telemetry.get("wpm")
        or raw_audio_telemetry.get("words_per_minute")
        or 0
    )
    filler_count = int(
        raw_audio_telemetry.get("filler_count")
        or raw_audio_telemetry.get("filler_word_count")
        or 0
    )
    silence_ratio = float(raw_audio_telemetry.get("silence_ratio") or 0.0)
    silence_pct = (
        float(raw_audio_telemetry["silence_percentage"])
        if "silence_percentage" in raw_audio_telemetry
        else round(silence_ratio * 100, 1)
    )
    filler_breakdown = raw_audio_telemetry.get("filler_breakdown")
    filler_words = list(filler_breakdown.keys()) if isinstance(filler_breakdown, dict) else raw_audio_telemetry.get("filler_words", [])

    formatted_audio_telemetry = {
        "speaking_duration_sec": round(speaking_duration_sec, 1),
        "words_per_minute": wpm,
        "filler_word_count": filler_count,
        "silence_percentage": silence_pct,
    }
    if filler_words:
        formatted_audio_telemetry["filler_words"] = filler_words
    if "clarity" in raw_audio_telemetry:
        formatted_audio_telemetry["clarity"] = raw_audio_telemetry["clarity"]

    # 5. Format Video Telemetry
    formatted_video_telemetry = payload.video_telemetry or {}

    # 6. Evaluate Gatekeeper Flag
    interview_duration = (
        float(payload.client_duration_seconds)
        if payload.client_duration_seconds is not None and payload.client_duration_seconds > 0
        else float(raw_audio_telemetry.get("total_audio_duration_seconds") or 0.0)
    )

    insufficient_content = evaluate_gatekeeper_flag(
        word_count=word_count,
        duration_seconds=interview_duration,
    )

    # 7. Resolve Candidate Consents & Persist Assessment Data in DB
    plan = resolve_storage_plan(
        consent=assessment.consent,
        media_type=assessment.media_type,
        formatted_transcript=formatted_transcript,
        formatted_audio_telemetry=formatted_audio_telemetry,
        formatted_video_telemetry=formatted_video_telemetry,
    )
    save_recording = plan["save_recording"]
    save_transcript = plan["save_transcript"]
    video_analytics = plan["video_analytics"]

    existing_data = crud.get_assessment_data_by_assessment_id(db, assessment.id)
    existing_questions = existing_data.questions if (existing_data and existing_data.questions) else []

    crud.save_assessment_data(
        db=db,
        assessment_id=assessment.id,
        questions=existing_questions,
        transcript=plan["transcript_to_persist"],
        audio_telemetry=plan["audio_telemetry_to_persist"],
        video_telemetry=plan["video_telemetry_to_persist"],
    )

    # 8. Handle Media Storage & YouTube Upload (Decoupled from Gatekeeper)
    unconsented_media_to_delete: Optional[str] = None
    if save_recording:
        if background_tasks and os.path.exists(target_media):
            background_tasks.add_task(
                _process_youtube_upload_and_cleanup,
                assessment_id=assessment.id,
                media_path=target_media,
                media_type=assessment.media_type or "VIDEO",
                candidate_id=resolved_cand_id,
            )
    else:
        # Candidate opted out of recording: clear youtube_url and schedule media for safe post-eval cleanup
        assessment.youtube_url = None
        unconsented_media_to_delete = target_media

    try:
        # 9. Handle Case 1 vs Case 2
        if insufficient_content:
            # Case A: Flag is ON
            crud.update_assessment_status(db, assessment.id, "COMPLETED")
            assessment.completed_at = datetime.utcnow()
            db.commit()
            db.refresh(assessment)
            # LLM evaluation engine is completely skipped!
            report_dict = {
                "insufficient_content": True,
                "message": "We don't have enough content of transcript and audio to evaluate you.",
                "llm_evaluation": {},
            }
        else:
            # Case B: Flag is OFF
            # The llm_evaluation engine must be triggered and its information present in the response
            crud.update_assessment_status(db, assessment.id, "EVALUATING")
            db.commit()

            # Trigger LLM evaluation engine and await results (passing in-memory full_text & telemetry)
            try:
                eval_result = await assessment_orchestrator.run_full_evaluation(
                    db=db,
                    assessment_id=assessment.id,
                    in_memory_transcript_text=full_text,
                    in_memory_audio_telemetry=formatted_audio_telemetry,
                    in_memory_video_telemetry=formatted_video_telemetry if video_analytics else {},
                )
                llm_report = eval_result.get("report") or {}
                crud.update_assessment_status(db, assessment.id, "COMPLETED")
                assessment.completed_at = datetime.utcnow()
                db.commit()
                db.refresh(assessment)
            except Exception as eval_err:
                logger.exception("LLM Evaluation failed for assessment %s: %s", assessment.id, eval_err)
                try:
                    db.rollback()
                    crud.update_assessment_status(db, assessment.id, "FAILED")
                    db.commit()
                except Exception as rollback_err:
                    logger.error("Failed to mark assessment %s as FAILED: %s", assessment.id, rollback_err)
                raise HTTPException(
                    status_code=502,
                    detail="Evaluation service temporarily unavailable",
                ) from eval_err

            report_dict = {
                "insufficient_content": False,
                "message": None,
                "llm_evaluation": llm_report,
            }
    finally:
        # Failure-safe cleanup: purge unconsented media once evaluation workflow concludes
        if unconsented_media_to_delete and os.path.exists(unconsented_media_to_delete):
            try:
                os.remove(unconsented_media_to_delete)
                logger.info("Successfully purged unconsented media file: %s", unconsented_media_to_delete)
            except Exception as cleanup_err:
                logger.warning("Could not delete unconsented media file %s: %s", unconsented_media_to_delete, cleanup_err)

    meta_assessment = {
        "id": assessment.id,
        "assessment_uuid": str(assessment.assessment_uuid) if assessment.assessment_uuid else None,
        "candidate_id": assessment.candidate_id,
        "assessment_type": assessment.assessment_type,
        "media_type": assessment.media_type,
        "status": assessment.status,
        "started_at": assessment.started_at,
        "completed_at": assessment.completed_at,
        "youtube_url": assessment.youtube_url,
    }

    return CandidateSubmitAssessmentResponse(
        status="success",
        data=CandidateSubmitAssessmentData(
            assessment=AssessmentMetaResponse(**meta_assessment),
            assessment_data=AssessmentTelemetryData(
                transcript=AssessmentTranscriptData(**plan["transcript_to_persist"]),
            ),
            audio_telemetry=plan["audio_telemetry_to_persist"],
            video_telemetry=plan["video_telemetry_to_persist"],
            report=AssessmentSubmitReportData(**report_dict),
        ),
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
            if assessment.status == "COMPLETED":
                logger.info("[LLMOrchestrator Worker] Assessment %s already COMPLETED. Skipping duplicate evaluation.", str(assessment_id))
                return

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
        except Exception as status_err:
            logger.warning(
                "[LLMOrchestrator Worker] Failed to update assessment %s status to FAILED: %s",
                str(assessment_id),
                status_err,
            )




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
    crud.update_assessment_media_url(db, assessment.id, payload.youtube_url)
    return UpdateMediaURLResponse(id=assessment.id, assessment_uuid=assessment.assessment_uuid, youtube_url=payload.youtube_url)




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
    cand = db.query(CandidateORM).filter(CandidateORM.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail=f"Candidate with ID {candidate_id} not found.")
    llm_check = _check_candidate_llm_db(db, candidate_id)
    resume_check = _check_candidate_resume_db(db, candidate_id)
    has_active_llm = bool(llm_check.get("is_configured"))
    has_resume = bool(resume_check.get("has_resume") or resume_check.get("has_parsed_json"))
    eligible = bool(has_active_llm and has_resume)
    return PreAssessmentCheckResponse(
        eligible=eligible,
        allowed_to_proceed=eligible,
        candidate_id=candidate_id,
        llm_check=LLMKeyStatusResponse(**llm_check),
        resume_check=ResumeStatusResponse(**resume_check),
        message="Candidate is eligible to start assessment" if eligible else "Prerequisites missing: setup required",
        action_required=None if eligible else ("both" if not has_active_llm and not has_resume else ("my-llm-setup" if not has_active_llm else "my-resume")),
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
                consent=a.consent,
                started_at=a.started_at,
                completed_at=a.completed_at,
                created_at=a.created_at,
            )
            for a in items
        ],
        total=total,
    )



# ---------------------------------------------------------------------------
# 3. Media Pipeline, Chunks & Streaming Logic
# ---------------------------------------------------------------------------

async def upload_candidate_assessment_chunk_logic(
    db: Session,
    current_user: AuthUserORM,
    candidate_id: Union[int, str],
    assessment_id: Union[int, str],
    chunk_index: int,
    file_content: Union[UploadFile, bytes],
    assessment_uuid: Optional[str] = None,
    is_final: bool = False,
) -> MediaChunkUploadResponse:
    """
    Handles chunk upload for an ongoing candidate assessment.
    Validates chunk size limits, streams chunk bytes directly to candidate/assessment chunk directory,
    and returns exact response specification.
    """
    if file_content is None:
        raise HTTPException(status_code=400, detail="Missing media chunk upload file")

    if chunk_index < 0:
        raise HTTPException(status_code=400, detail="chunk_index must be >= 0")

    # 1. Resolve Assessment
    assessment = None
    if assessment_id is not None:
        assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment and assessment_uuid:
        assessment = crud.get_assessment_by_uuid(db, assessment_uuid)

    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # If both assessment_uuid and assessment were found, ensure UUIDs match if provided
    if assessment_uuid and assessment.assessment_uuid and assessment.assessment_uuid.lower() != str(assessment_uuid).strip().lower():
        raise HTTPException(status_code=400, detail="assessment_uuid does not match the assessment record")

    # Lifecycle State Guard: Disallow uploading to closed or evaluating assessments
    if assessment.status in ("COMPLETED", "CANCELLED", "FAILED", "EVALUATING"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Assessment is already {assessment.status}. Cannot upload further media chunks.",
        )

    # Auto-advance from CREATED to IN_PROGRESS on chunk arrival
    if assessment.status == "CREATED":
        crud.update_assessment_status(db, assessment.id, "IN_PROGRESS")
        assessment.status = "IN_PROGRESS"

    # 2. Resolve & Authorize Candidate
    target_cand_id: Optional[int] = None
    try:
        target_cand_id = int(candidate_id)
    except (ValueError, TypeError):
        target_cand_id = assessment.candidate_id

    resolved_candidate_id = _resolve_candidate_id(db, current_user, target_cand_id)
    if assessment.candidate_id and resolved_candidate_id != assessment.candidate_id:
        uname = (getattr(current_user, "uname", "") or "").lower()
        role = getattr(current_user, "role", None) or ("admin" if uname == "admin" else "candidate")
        is_employee = bool(getattr(current_user, "is_employee", False) or role in ("admin", "staff", "employee") or uname == "admin")
        if not is_employee:
            raise HTTPException(status_code=403, detail="Candidates can only upload chunks to their own assessments")

    # 3. Setup chunk storage directory and file path
    chunk_dir = os.path.join(STORAGE_BASE_DIR, str(assessment.candidate_id or resolved_candidate_id), str(assessment.id), "chunks")
    chunk_path = os.path.join(chunk_dir, f"chunk_{chunk_index}.webm")
    legacy_chunk_path = os.path.join(chunk_dir, f"chunk_{chunk_index:04d}.webm")

    max_chunk_size_bytes = int(getattr(settings, "MAX_CHUNK_SIZE_MB", 50)) * 1024 * 1024
    total_written = 0

    try:
        os.makedirs(chunk_dir, exist_ok=True)
        with open(chunk_path, "wb") as f:
            if isinstance(file_content, bytes):
                total_written = len(file_content)
                if total_written > max_chunk_size_bytes:
                    f.close()
                    if os.path.exists(chunk_path):
                        os.remove(chunk_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Media chunk ({total_written / (1024*1024):.1f}MB) exceeds maximum allowed size ({settings.MAX_CHUNK_SIZE_MB}MB)",
                    )
                f.write(file_content)
            else:
                while True:
                    chunk = await file_content.read(1024 * 1024)
                    if not chunk:
                        break
                    total_written += len(chunk)
                    if total_written > max_chunk_size_bytes:
                        f.close()
                        if os.path.exists(chunk_path):
                            os.remove(chunk_path)
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"Media chunk ({total_written / (1024*1024):.1f}MB) exceeds maximum allowed size ({settings.MAX_CHUNK_SIZE_MB}MB)",
                        )
                    await asyncio.to_thread(f.write, chunk)
    except HTTPException:
        raise
    except (PermissionError, OSError) as err:
        logging.error("Could not write media chunk to disk: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write media chunk to server storage",
        )

    # Record final chunk accounting into assessment_data if is_final=True
    if is_final:
        try:
            data_rec = crud.get_assessment_data_by_assessment_id(db, assessment.id)
            if data_rec:
                video_tel = dict(data_rec.video_telemetry or {})
                video_tel["total_expected_chunks"] = chunk_index + 1
                video_tel["final_chunk_index"] = chunk_index
                crud.save_assessment_data(
                    db=db,
                    assessment_id=assessment.id,
                    questions=data_rec.questions or [],
                    transcript=data_rec.transcript or {},
                    audio_telemetry=data_rec.audio_telemetry or {},
                    video_telemetry=video_tel,
                )
        except Exception as sync_err:
            logger.warning(
                "Could not persist is_final metadata for assessment %s: %s",
                assessment.id,
                sync_err,
            )

    return MediaChunkUploadResponse(
        status="success",
        data=MediaChunkUploadData(
            assessment_uuid=str(assessment.assessment_uuid or assessment_uuid or ""),
            chunk_index=chunk_index,
            bytes_received=total_written,
            saved=True,
        ),
    )


async def upload_media_chunk_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    chunk_number: int,
    total_chunks: Optional[int],
    file_content: Union[UploadFile, bytes],
) -> ChunkUploadResponse:
    """Uploads sequential WebM media chunk to server storage directory using streaming with strict size limits."""
    if file_content is None:
        raise HTTPException(status_code=400, detail="Missing media chunk upload file")

    if chunk_number < 1:
        raise HTTPException(status_code=400, detail="chunk_number must be >= 1")
    if total_chunks is not None and total_chunks < 1:
        raise HTTPException(status_code=400, detail="total_chunks must be >= 1")

    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)
    chunk_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment.id), "chunks")
    chunk_path = os.path.join(chunk_dir, f"chunk_{chunk_number:04d}.webm")

    max_chunk_size_bytes = int(getattr(settings, "MAX_CHUNK_SIZE_MB", 50)) * 1024 * 1024
    total_written = 0

    try:
        os.makedirs(chunk_dir, exist_ok=True)
        with open(chunk_path, "wb") as f:
            if isinstance(file_content, bytes):
                total_written = len(file_content)
                if total_written > max_chunk_size_bytes:
                    f.close()
                    if os.path.exists(chunk_path):
                        os.remove(chunk_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Media chunk ({total_written / (1024*1024):.1f}MB) exceeds maximum allowed size ({settings.MAX_CHUNK_SIZE_MB}MB)",
                    )
                f.write(file_content)
            else:
                while True:
                    chunk = await file_content.read(1024 * 1024)
                    if not chunk:
                        break
                    total_written += len(chunk)
                    if total_written > max_chunk_size_bytes:
                        f.close()
                        if os.path.exists(chunk_path):
                            os.remove(chunk_path)
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"Media chunk ({total_written / (1024*1024):.1f}MB) exceeds maximum allowed size ({settings.MAX_CHUNK_SIZE_MB}MB)",
                        )
                    await asyncio.to_thread(f.write, chunk)
    except HTTPException:
        raise
    except (PermissionError, OSError) as err:
        logging.error("Could not write media chunk to disk: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write media chunk to server storage",
        )

    uploaded = []
    if os.path.exists(chunk_dir):
        try:
            for fname in os.listdir(chunk_dir):
                if fname.startswith("chunk_") and fname.endswith(".webm"):
                    try:
                        num = int(fname.replace("chunk_", "").replace(".webm", ""))
                        uploaded.append(num)
                    except ValueError:
                        pass
        except (PermissionError, OSError):
            pass

    uploaded.sort()
    is_ready = bool(total_chunks and len(uploaded) >= total_chunks)

    return ChunkUploadResponse(
        chunk_number=chunk_number,
        status="uploaded",
        storage_path=chunk_path,
        bytes_written=total_written,
        total_uploaded=len(uploaded),
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
        try:
            for fname in os.listdir(chunk_dir):
                if fname.startswith("chunk_") and fname.endswith(".webm"):
                    try:
                        num = int(fname.replace("chunk_", "").replace(".webm", ""))
                        uploaded.append(num)
                    except ValueError:
                        pass
        except (PermissionError, OSError):
            pass

    uploaded = sorted(list(set(uploaded)))
    start_index = 0 if (0 in uploaded or (uploaded and min(uploaded) == 0)) else 1
    missing = [i for i in range(start_index, start_index + total_chunks) if i not in uploaded] if total_chunks else []
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



async def _process_youtube_upload_and_cleanup(
    assessment_id: int,
    media_path: str,
    media_type: str,
    candidate_id: Optional[int],
) -> Optional[str]:
    """
    Background helper to package media, upload to YouTube as Unlisted, persist URL to DB,
    and safely purge local scratch storage once persistence is confirmed.
    """
    youtube_url = None
    youtube_upload_file = media_path

    # 1. Conversion for YouTube if audio
    if media_type.upper() in {"AUDIO", "AUDIO_ONLY"}:
        try:
            from fapi.ai_prep.core.video_processor_engine import VideoProcessorEngine
            youtube_upload_file = await asyncio.to_thread(
                VideoProcessorEngine.convert_audio_for_youtube,
                media_path,
            )
        except Exception as conv_err:
            logger.warning("Audio-to-video conversion failed for assessment %s: %s", assessment_id, conv_err)
            return None

    # 2. Upload to YouTube
    try:
        from fapi.ai_prep.clients.youtube_client import youtube_client, YouTubeQuotaExceededError
        if not youtube_client.has_live_credentials() and os.getenv("ENV") != "test":
            logger.info("No live YouTube credentials configured. Retaining server storage for local media playback for assessment %s", assessment_id)
            return None

        upload_res = await asyncio.to_thread(
            youtube_client.upload_unlisted_media,
            assessment_id=assessment_id,
            file_path=youtube_upload_file,
            media_type=media_type,
        )
        youtube_url = upload_res.get("youtube_url")
        logger.info("Assessment %s successfully uploaded to YouTube: %s", assessment_id, youtube_url)
    except Exception as yt_err:
        logger.warning("YouTube upload error for assessment %s: %s", assessment_id, yt_err)

    # 3. Persist youtube_url to DB
    youtube_persisted = False
    if youtube_url:
        try:
            with SessionLocal() as db:
                crud.update_assessment_media_url(db, assessment_id, youtube_url)
                youtube_persisted = True
                logger.info("Updated youtube_url in DB for assessment %s", assessment_id)
        except Exception as db_url_err:
            logger.error("DB update youtube_url error for assessment %s: %s", assessment_id, db_url_err)

    # 4. Storage Cleanup: ONLY once uploaded to YouTube and verified persisted in DB
    try:
        from fapi.ai_prep.config import settings
        should_cleanup = getattr(settings, "CLEANUP_STORAGE_AFTER_UPLOAD", True)
        if youtube_persisted and should_cleanup and candidate_id:
            assessment_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment_id))
            if os.path.exists(assessment_dir):
                logger.info("Purging server storage for assessment %s at %s following verified YouTube DB update", assessment_id, assessment_dir)
                shutil.rmtree(assessment_dir, ignore_errors=True)
        elif not youtube_persisted:
            logger.info("Retaining local storage for assessment %s (YouTube URL not persisted in DB)", assessment_id)
    except Exception as clean_err:
        logger.warning("Storage cleanup note for assessment %s: %s", assessment_id, clean_err)

    return youtube_url


async def process_media_and_upload_pipeline(
    assessment_id: int,
    media_path: str,
    media_type: str = "VIDEO",
    candidate_id: Optional[int] = None,
):
    """
    Unified Background Pipeline:
    1. Runs Audio Engine on media_path (works with both audio and video containers).
    2. Saves real transcript + audio/video telemetry to database and updates status to EVALUATING.
    3. If media_type == "AUDIO", converts audio to video format for YouTube ingestion.
    4. Uploads to YouTube as Unlisted using youtube_client.
    5. Persists youtube_url into ai_prep_assessment table.
    6. Storage Cleanup: Once youtube_url is verified and persisted in DB, cleans up local storage.
    7. Triggers LLM evaluation orchestrator.
    If any critical failure occurs, transitions assessment status to 'FAILED'.
    """
    logger.info("Starting media processing & YouTube upload pipeline for assessment %s (type: %s)...", assessment_id, media_type)
    try:
        # 1. Run Audio Engine (STT + Acoustic DSP)
        from fapi.ai_prep.core.audio_engine import AudioMetricsEngine
        try:
            result = await asyncio.to_thread(AudioMetricsEngine.process_audio_file, media_path)
            spoken_content = result.get("spoken_content")
            audio_telemetry = result.get("audio_telemetry")
            if not spoken_content or not audio_telemetry:
                raise ValueError("Audio Engine returned incomplete transcription or telemetry")
        except Exception as err:
            logger.error("Audio Engine execution failed for assessment %s: %s", assessment_id, err, exc_info=True)
            with SessionLocal() as err_db:
                crud.update_assessment_status(err_db, assessment_id, "FAILED")
            return

        # 2. Save Telemetry into DB & Transition Status to EVALUATING
        with SessionLocal() as db:
            assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
            if assessment:
                existing_data = crud.get_assessment_data_by_assessment_id(db, assessment.id)
                existing_questions = existing_data.questions if existing_data and existing_data.questions else []
                crud.save_assessment_data(
                    db=db,
                    assessment_id=assessment.id,
                    questions=existing_questions,
                    transcript=spoken_content,
                    audio_telemetry=audio_telemetry,
                    video_telemetry={"is_video_mode": media_type.upper() == "VIDEO"},
                )
                crud.update_assessment_status(db, assessment.id, "EVALUATING")
                if not candidate_id:
                    candidate_id = assessment.candidate_id
            else:
                logger.error("Assessment %s not found during media processing pipeline", assessment_id)
                return

        # 3. Concurrent Execution: Trigger LLM Evaluation & YouTube Ingestion in Parallel
        eval_coro = assessment_orchestrator.run_full_evaluation(db=None, assessment_id=assessment_id)
        yt_coro = _process_youtube_upload_and_cleanup(
            assessment_id=assessment_id,
            media_path=media_path,
            media_type=media_type,
            candidate_id=candidate_id,
        )

        eval_result, yt_url = await asyncio.gather(eval_coro, yt_coro, return_exceptions=True)

        if isinstance(eval_result, Exception):
            logger.error("LLM evaluation encountered exception for assessment %s: %s", assessment_id, eval_result)
        if isinstance(yt_url, Exception):
            logger.warning("YouTube upload task encountered exception for assessment %s: %s", assessment_id, yt_url)

    except Exception as pipeline_err:
        logger.error(
            "Background media processing & evaluation pipeline failed for assessment %s: %s",
            assessment_id,
            pipeline_err,
            exc_info=True,
        )
        try:
            with SessionLocal() as fallback_db:
                crud.update_assessment_status(fallback_db, assessment_id, "FAILED")
                logger.info("Assessment %s status updated to FAILED", assessment_id)
        except Exception as status_err:
            logger.error("Failed to update assessment %s status to FAILED: %s", assessment_id, status_err)


async def process_audio_and_save_data(
    assessment_id: int,
    audio_path: str,
):
    """
    Background worker for backward compatibility: Runs Audio Engine, persists telemetry,
    converts for YouTube ingestion, and triggers LLM evaluation.
    """
    return await process_media_and_upload_pipeline(
        assessment_id=assessment_id,
        media_path=audio_path,
        media_type="AUDIO",
        candidate_id=None,
    )




async def upload_raw_media_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    media_type: str,
    file: UploadFile,
    background_tasks: Optional[BackgroundTasks] = None,
) -> LocalMediaUploadResponse:
    """Uploads single binary media file directly to disk storage using streaming with size limits."""
    normalized_media = (media_type or "").upper().strip()
    if normalized_media not in {"AUDIO", "VIDEO", "AUDIO_ONLY"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media_type '{media_type}'. Allowed values: AUDIO, VIDEO, AUDIO_ONLY",
        )

    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)

    assessment_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment.id))
    safe_filename = os.path.basename(file.filename or "media.webm")
    dest_path = os.path.join(assessment_dir, f"raw_{safe_filename}")

    max_media_bytes = int(getattr(settings, "MAX_MEDIA_UPLOAD_MB", 500)) * 1024 * 1024
    total_written = 0

    try:
        os.makedirs(assessment_dir, exist_ok=True)
        with open(dest_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total_written += len(chunk)
                if total_written > max_media_bytes:
                    buffer.close()
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"Media file ({total_written / (1024*1024):.1f}MB) exceeds maximum allowed size ({settings.MAX_MEDIA_UPLOAD_MB}MB)",
                    )
                await asyncio.to_thread(buffer.write, chunk)
    except HTTPException:
        raise
    except (PermissionError, OSError) as err:
        logging.error("Could not write raw media file to disk: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write media file to server storage",
        )

    if background_tasks:
        background_tasks.add_task(
            process_media_and_upload_pipeline,
            assessment.id,
            dest_path,
            normalized_media,
            candidate_id,
        )

    return LocalMediaUploadResponse(
        success=True,
        assessment_id=assessment.id,
        file_path=dest_path,
        media_type=normalized_media,
        message="Media uploaded and processing pipeline queued successfully",
    )


AUDIO_MIME_TO_EXTENSION: Dict[str, str] = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/webm": "webm",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/ogg": "ogg",
    "audio/m4a": "m4a",
    "audio/aac": "aac",
    "audio/flac": "flac",
}


async def upload_assessment_audio_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    file: UploadFile,
    mime_type: Optional[str] = None,
    background_tasks: Optional[BackgroundTasks] = None,
) -> AudioUploadResponse:
    """Uploads direct audio recording binary to server storage with extension detection and size limits."""
    from fapi.ai_prep.schemas import AudioUploadResponse
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)

    assessment_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment.id))
    os.makedirs(assessment_dir, exist_ok=True)

    ext = None
    if mime_type and mime_type.lower() in AUDIO_MIME_TO_EXTENSION:
        ext = AUDIO_MIME_TO_EXTENSION[mime_type.lower()]
    elif file.filename and "." in file.filename:
        file_ext = file.filename.rsplit(".", 1)[-1].lower()
        if file_ext in {"wav", "webm", "mp3", "ogg", "m4a", "aac", "flac"}:
            ext = file_ext
    if not ext:
        ext = "webm" if (mime_type and "webm" in mime_type) else "wav"

    dest_path = os.path.join(assessment_dir, f"audio.{ext}")
    max_audio_bytes = int(getattr(settings, "MAX_AUDIO_UPLOAD_MB", 100)) * 1024 * 1024
    total_written = 0

    try:
        with open(dest_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total_written += len(chunk)
                if total_written > max_audio_bytes:
                    buffer.close()
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"Audio file ({total_written / (1024*1024):.1f}MB) exceeds maximum allowed size ({settings.MAX_AUDIO_UPLOAD_MB}MB)",
                    )
                await asyncio.to_thread(buffer.write, chunk)
    except HTTPException:
        raise
    except (PermissionError, OSError) as err:
        logging.error("Could not write audio recording file to disk: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write audio file to server storage",
        )

    if background_tasks:
        background_tasks.add_task(
            process_media_and_upload_pipeline,
            assessment.id,
            dest_path,
            "AUDIO",
            candidate_id,
        )

    return AudioUploadResponse(
        success=True,
        assessment_id=assessment.id,
        message="Audio recording uploaded and processing pipeline queued successfully",
        size_bytes=total_written,
        mime_type=mime_type or f"audio/{ext}",
        file_path=dest_path,
    )


def _auto_assemble_chunks_if_present(assessment_dir: str, total_expected: Optional[int] = None) -> Optional[str]:
    """Auto-assembles sequential WebM chunks from chunks/ into assembled.webm atomically if top-level media is absent."""
    chunk_dir = os.path.join(assessment_dir, "chunks")
    assembled_path = os.path.join(assessment_dir, "assembled.webm")
    if os.path.exists(assembled_path) and os.path.getsize(assembled_path) > 0:
        return assembled_path

    if not os.path.exists(chunk_dir):
        return None
    try:
        chunk_files = sorted(
            [
                os.path.join(chunk_dir, f)
                for f in os.listdir(chunk_dir)
                if f.startswith("chunk_") and f.endswith(".webm")
            ]
        )
        if chunk_files:
            if total_expected and len(chunk_files) < total_expected:
                logger.info("Auto-assemble deferred: received %d chunks but expected %d", len(chunk_files), total_expected)
                return None

            expected_count = total_expected or len(chunk_files)
            # Validate contiguous sequence starting from chunk_0001.webm without gaps
            chunk_names = [os.path.basename(f) for f in chunk_files]
            expected_names = [f"chunk_{i:04d}.webm" for i in range(1, expected_count + 1)]
            if chunk_names != expected_names:
                logger.warning("Auto-assemble skipped: chunk sequence is incomplete or contains gaps (%s)", chunk_names)
                return None

            os.makedirs(assessment_dir, exist_ok=True)
            temp_assembled = os.path.join(assessment_dir, f"assembled_{uuid.uuid4().hex}.tmp")
            try:
                with open(temp_assembled, "wb") as outfile:
                    for cf in chunk_files:
                        with open(cf, "rb") as infile:
                            shutil.copyfileobj(infile, outfile, length=1024 * 1024)
                if os.path.exists(temp_assembled) and os.path.getsize(temp_assembled) > 0:
                    os.replace(temp_assembled, assembled_path)
                    logger.info("Atomically auto-assembled %d chunks into %s", len(chunk_files), assembled_path)
                    return assembled_path
            finally:
                if os.path.exists(temp_assembled):
                    try:
                        os.remove(temp_assembled)
                    except OSError:
                        pass
    except Exception as auto_err:
        logger.warning("Auto-assembling chunks failed: %s", auto_err)
    return None


def get_assessment_audio_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    range_header: Optional[str] = None,
) -> FileResponse:
    """Retrieves and streams stored audio recording binary from server storage with range seeking support."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)

    assessment_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment.id))
    candidate_files = [
        os.path.join(assessment_dir, "audio.wav"),
        os.path.join(assessment_dir, "audio.webm"),
        os.path.join(assessment_dir, "recording.webm"),
        os.path.join(assessment_dir, "audio.mp3"),
        os.path.join(assessment_dir, "audio.ogg"),
        os.path.join(assessment_dir, "assembled.webm"),
    ]
    target_file = None
    for cf in candidate_files:
        if os.path.exists(cf) and os.path.getsize(cf) > 0:
            target_file = cf
            break

    if not target_file and os.path.exists(assessment_dir):
        for fname in os.listdir(assessment_dir):
            fpath = os.path.join(assessment_dir, fname)
            if os.path.isfile(fpath) and os.path.getsize(fpath) > 0 and any(fname.endswith(s) for s in (".wav", ".webm", ".mp3", ".ogg")):
                target_file = fpath
                break

    if not target_file and os.path.exists(assessment_dir):
        target_file = _auto_assemble_chunks_if_present(assessment_dir)

    if not target_file or not os.path.exists(target_file):
        if getattr(assessment, "youtube_url", None):
            raise HTTPException(
                status_code=404,
                detail=f"Local audio recording purged following YouTube ingestion. Media stream available at: {assessment.youtube_url}",
            )
        raise HTTPException(status_code=404, detail="Assessment audio recording not found in server storage")

    mime_type = "audio/wav" if target_file.endswith(".wav") else ("audio/mp3" if target_file.endswith(".mp3") else "audio/webm")

    return FileResponse(
        path=target_file,
        media_type=mime_type,
        filename=os.path.basename(target_file),
        content_disposition_type="inline",
    )


def get_assessment_video_logic(
    db: Session,
    current_user: AuthUserORM,
    assessment_id: Union[int, str],
    range_header: Optional[str] = None,
) -> FileResponse:
    """Retrieves and streams stored video recording from server storage with range seeking support."""
    assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidate_id = _resolve_candidate_id(db, current_user, assessment.candidate_id)

    assessment_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment.id))
    candidate_files = [
        os.path.join(assessment_dir, "assembled.webm"),
        os.path.join(assessment_dir, "video.mp4"),
        os.path.join(assessment_dir, "recording.webm"),
    ]
    target_file = None
    for cf in candidate_files:
        if os.path.exists(cf) and os.path.getsize(cf) > 0:
            target_file = cf
            break

    if not target_file and os.path.exists(assessment_dir):
        for fname in os.listdir(assessment_dir):
            fpath = os.path.join(assessment_dir, fname)
            if os.path.isfile(fpath) and os.path.getsize(fpath) > 0 and (fname.endswith(".webm") or fname.endswith(".mp4") or fname.endswith(".mkv")):
                target_file = fpath
                break

    if not target_file and os.path.exists(assessment_dir):
        target_file = _auto_assemble_chunks_if_present(assessment_dir)

    if not target_file or not os.path.exists(target_file):
        if getattr(assessment, "youtube_url", None):
            raise HTTPException(
                status_code=404,
                detail=f"Local video recording purged following YouTube ingestion. Media stream available at: {assessment.youtube_url}",
            )
        raise HTTPException(status_code=404, detail="Assessment video recording not found in server storage")

    mime_type = "video/webm" if target_file.endswith(".webm") else "video/mp4"

    return FileResponse(
        path=target_file,
        media_type=mime_type,
        filename=os.path.basename(target_file),
        content_disposition_type="inline",
    )


def get_media_storage_info_logic() -> StorageInfoResponse:
    """Returns real storage directory disk usage and assessment folder count across nested candidate partitions."""
    total, used, free = shutil.disk_usage(STORAGE_BASE_DIR if os.path.exists(STORAGE_BASE_DIR) else ".")
    assessment_count = 0
    if os.path.exists(STORAGE_BASE_DIR):
        try:
            for cand_dir in os.listdir(STORAGE_BASE_DIR):
                cand_path = os.path.join(STORAGE_BASE_DIR, cand_dir)
                if os.path.isdir(cand_path):
                    try:
                        valid_assessments = [
                            item for item in os.listdir(cand_path)
                            if os.path.isdir(os.path.join(cand_path, item))
                        ]
                        assessment_count += len(valid_assessments)
                    except (PermissionError, OSError):
                        pass
        except (PermissionError, OSError) as err:
            logger.warning("Error calculating storage assessment count: %s", err)
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

    progress_map = {"IN_PROGRESS": 25.0, "EVALUATING": 70.0, "COMPLETED": 100.0, "FAILED": 0.0}
    active_step = (
        "Evaluation Completed" if status_str == "COMPLETED"
        else ("Processing Failed" if status_str == "FAILED"
        else ("Evaluating Responses with LLM" if status_str == "EVALUATING"
        else "Processing Ingested Media"))
    )
    return ProcessingStatusResponse(
        assessment_id=assessment.id,
        status=status_str,
        progress_percentage=int(progress_map.get(status_str, 50.0)),
        active_step=active_step,
        step=active_step,
        progress_pct=progress_map.get(status_str, 50.0),
        youtube_url=assessment.youtube_url,
        message=f"Assessment is {status_str}",
    )


def _fetch_assessment_status_snapshot(assessment_id: int) -> Optional[Tuple[str, Optional[str]]]:
    """Helper to query assessment status in an isolated short-lived DB session without holding connection pool."""
    try:
        with SessionLocal() as poll_db:
            rec = crud.get_assessment_by_id_or_uuid(poll_db, assessment_id)
            if rec:
                return rec.status or "IN_PROGRESS", rec.youtube_url
    except Exception as exc:
        logger.debug("SSE status poll error for assessment %s: %s", assessment_id, exc)
    return None


def stream_assessment_processing_sse_logic(
    db: Optional[Session] = None,
    current_user: Optional[AuthUserORM] = None,
    assessment_id: Optional[Union[int, str]] = None,
    request: Optional[Request] = None,
) -> StreamingResponse:
    """Real-time SSE event stream for live UI progress updates reflecting true DB state without leaking connection pool."""
    if assessment_id is None:
        raise HTTPException(status_code=400, detail="Missing assessment_id")
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    # One-off validation in a short-lived session
    if db is not None:
        assessment = crud.get_assessment_by_id_or_uuid(db, assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        _resolve_candidate_id(db, current_user, assessment.candidate_id)
        internal_id = assessment.id
    else:
        with SessionLocal() as init_db:
            assessment = crud.get_assessment_by_id_or_uuid(init_db, assessment_id)
            if not assessment:
                raise HTTPException(status_code=404, detail="Assessment not found")
            _resolve_candidate_id(init_db, current_user, assessment.candidate_id)
            internal_id = assessment.id

    ping_interval = float(getattr(settings, "SSE_PING_INTERVAL_SECONDS", 2))

    async def event_generator():
        max_polls = int(getattr(settings, "SSE_MAX_POLLS", 60))  # Prevent infinite hanging connections
        polls = 0
        while polls < max_polls:
            if request and await request.is_disconnected():
                logger.info("SSE client disconnected for assessment %s", internal_id)
                break

            polls += 1
            try:
                snapshot = await asyncio.to_thread(_fetch_assessment_status_snapshot, internal_id)
                if not snapshot:
                    break
                curr_status, yt_url = snapshot
                progress_map = {"IN_PROGRESS": 35, "EVALUATING": 75, "COMPLETED": 100, "FAILED": 0}
                pct = progress_map.get(curr_status, 50)
                active_step = (
                    "Report Generated" if curr_status == "COMPLETED"
                    else ("Processing Failed" if curr_status == "FAILED"
                    else ("LLM Evaluation in Progress" if curr_status == "EVALUATING"
                    else "Media Processing & YouTube Ingestion"))
                )

                data = json.dumps({
                    "assessment_id": internal_id,
                    "status": curr_status,
                    "step": active_step,
                    "progress": pct,
                    "youtube_url": yt_url,
                })
                yield f"data: {data}\n\n"

                if curr_status in {"COMPLETED", "FAILED"}:
                    break

                await asyncio.sleep(min(ping_interval, 2.0))
            except asyncio.CancelledError:
                logger.info("SSE stream cancelled for assessment %s", internal_id)
                break

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

    subject = payload.subject.value if hasattr(payload.subject, "value") else payload.subject
    concept = payload.concept.value if hasattr(payload.concept, "value") else payload.concept
    scope = payload.scope.value if hasattr(payload.scope, "value") else payload.scope
    diff = payload.difficulty_level.value if hasattr(payload.difficulty_level, "value") else str(payload.difficulty_level)

    new_q = AiPrepQuestionORM(
        category=cat,
        subject=subject,
        concept=concept,
        scope=scope,
        difficulty_level=diff,
        time_limit_seconds=payload.time_limit_seconds or 120,
        question_text=payload.question_text,
        ground_truth=payload.ground_truth,
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
        if hasattr(q_row, k):
            setattr(q_row, k, v.value if hasattr(v, "value") else v)

    cat = q_row.category.value if hasattr(q_row.category, "value") else str(q_row.category)
    if cat != "TECHNICAL":
        q_row.subject = None
        q_row.concept = None
        q_row.scope = None

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
    """Deactivates/deletes a question from ai_prep_question_bank."""
    q_row = db.query(AiPrepQuestionORM).filter(AiPrepQuestionORM.id == question_id).first()
    if not q_row:
        raise HTTPException(status_code=404, detail="Question not found")
    q_row.is_active = False
    q_row.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Question deactivated successfully", "id": question_id}

async def run_audio_engine_benchmark(
    audio_path: str,
    provider_name: Optional[str] = None,
    model_size: str = "base"
) -> Dict[str, Any]:
    """Runs AudioMetricsEngine inside an async thread pool to avoid blocking the FastAPI event loop."""
    return await asyncio.to_thread(
        AudioMetricsEngine.process_audio_file,
        audio_path=audio_path,
        model_size=model_size,
        provider_name=provider_name
    )

async def process_audio_engine_logic(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = None,
    audio_path: Optional[str] = None,
    provider: Optional[str] = None,
    model_size: str = "base",
    async_mode: bool = False,
) -> Dict[str, Any]:
    """
    Business logic for AudioMetricsEngine benchmarking and execution.
    Handles temporary file streaming, storage boundary validation, and background processing.
    """
    target_path = None
    temp_dir = None
    task_queued = False
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB limit

    try:
        # 1. Handle direct file upload
        if file:
            temp_dir = tempfile.mkdtemp(prefix="aiprep_perf_")
            safe_filename = "uploaded_audio.webm"
            temp_file_path = os.path.join(temp_dir, safe_filename)
            file_size = 0
            with open(temp_file_path, "wb") as buffer:
                while chunk := file.file.read(1024 * 1024):  # 1MB chunks
                    file_size += len(chunk)
                    if file_size > MAX_FILE_SIZE:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        raise HTTPException(status_code=413, detail="Uploaded file exceeds maximum limit of 100MB.")
                    buffer.write(chunk)

            if file_size == 0:
                raise HTTPException(status_code=400, detail="Uploaded audio file cannot be empty.")
            target_path = temp_file_path

        # 2. Handle server-side audio_path and prevent storage-boundary escapes
        elif audio_path:
            base_dir = Path(STORAGE_BASE_DIR).resolve()
            try:
                resolved_path = Path(audio_path).resolve()
            except (OSError, RuntimeError) as exc:
                logger.warning("Failed to resolve audio_path — invalid format or path characters")
                raise HTTPException(status_code=400, detail="Invalid audio_path format.") from exc

            if not (resolved_path == base_dir or resolved_path.is_relative_to(base_dir)):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid audio_path. Path must reside within the application storage directory."
                )

            if not resolved_path.is_file():
                raise HTTPException(status_code=400, detail="Valid audio file is required.")
        
            if resolved_path.stat().st_size == 0:
                raise HTTPException(status_code=400, detail="Audio file cannot be empty.")
            target_path = str(resolved_path)

        # Validate file existence
        if not target_path or not Path(target_path).is_file():
            raise HTTPException(status_code=400, detail="Valid audio file or storage audio_path is required.")

        if async_mode:
            async def _benchmark_with_cleanup(path: str, prov: Optional[str], sz: str, dir_to_clean: Optional[str]):
                try:
                    await run_audio_engine_benchmark(
                        audio_path=path,
                        provider_name=prov,
                        model_size=sz,
                    )
                finally:
                    if dir_to_clean and os.path.exists(dir_to_clean):
                        shutil.rmtree(dir_to_clean, ignore_errors=True)

            background_tasks.add_task(
                _benchmark_with_cleanup,
                path=target_path,
                prov=provider,
                sz=model_size,
                dir_to_clean=temp_dir,
            )
            task_queued = True

            return {
                "status": "ACCEPTED",
                "message": "Audio processing queued in background",
                "provider": provider or os.getenv("TRANSCRIPTION_PROVIDER", "whisper")
            }
        else:
            result = await run_audio_engine_benchmark(
                audio_path=target_path,
                provider_name=provider,
                model_size=model_size
            )
            return {
                "status": "SUCCESS",
                "data": result
        }       
    except HTTPException:
        raise
    except InvalidProviderConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Audio engine benchmark failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred while processing the audio benchmark.")
    finally:
        if (not async_mode or not task_queued) and temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)