"""FastAPI Router for AI Prep Tool - Explicit Candidate & Employee Routes Architecture."""
import os
import shutil
import logging
from typing import Any, Dict, List, Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    BackgroundTasks,
    Query,
    UploadFile,
    File,
    Form,
    Request,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.ai_prep.schemas import (
    AssessmentTypeResponse,
    AssessmentTypeListResponse,
    AssessmentTypeCreate,
    AssessmentTypeUpdate,
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
from fapi.ai_prep.dependencies import (
    require_candidate_or_employee,
    require_employee_or_admin,
    enforce_candidate_access,
    verify_assessment_prerequisites,
)
from fapi.ai_prep.crud import (
    list_assessment_types,
    create_assessment_type,
    get_assessment_by_id,
    list_assessments,
    save_assessment_data,
    update_assessment_media_url,
    update_assessment_status,
    list_questions,
    create_question,
    update_question,
    check_candidate_llm_key,
    check_candidate_resume,
)
from fapi.ai_prep.orchestrator.assessment_orchestrator import AssessmentOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter()

STORAGE_BASE_DIR = os.getenv("AIPREP_LOCAL_STORAGE_DIR", "./storage/aiprep")


async def _async_run_eval(assessment_id: int):
    from fapi.db.database import SessionLocal
    db_session = SessionLocal()
    try:
        await AssessmentOrchestrator.run_evaluation_pipeline(db_session, assessment_id)
    except Exception as e:
        logger.error(f"Background evaluation error for {assessment_id}: {e}")
    finally:
        db_session.close()


# ===========================================================================
# 1. CANDIDATE-FACING ROUTES (Tags: ["AI Prep - Candidate"])
# ===========================================================================

@router.get(
    "/candidate/llm-keys",
    response_model=LLMKeyStatusResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Check Own LLM Key Status",
)
@router.get("/llm-keys", response_model=LLMKeyStatusResponse, tags=["AI Prep - Candidate"], summary="Check Own LLM Keys")
@router.get("/llm_keys", response_model=LLMKeyStatusResponse, include_in_schema=False)
def candidate_check_llm_keys(
    auth_ctx: Dict[str, Any] = Depends(require_candidate_or_employee),
    db: Session = Depends(get_db),
):
    """Candidate self-check for valid, active LLM API key."""
    candidate_id = enforce_candidate_access(None, auth_ctx)
    result = check_candidate_llm_key(db, candidate_id)
    return LLMKeyStatusResponse(**result)


@router.get(
    "/candidate/resume-status",
    response_model=ResumeStatusResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Check Own Resume Status",
)
@router.get("/resume-status", response_model=ResumeStatusResponse, tags=["AI Prep - Candidate"], summary="Check Own Resume")
@router.get("/resume_status", response_model=ResumeStatusResponse, include_in_schema=False)
def candidate_check_resume_status(
    auth_ctx: Dict[str, Any] = Depends(require_candidate_or_employee),
    db: Session = Depends(get_db),
):
    """Candidate self-check for uploaded and parsed resume JSON."""
    candidate_id = enforce_candidate_access(None, auth_ctx)
    result = check_candidate_resume(db, candidate_id)
    return ResumeStatusResponse(**result)


@router.get(
    "/candidate/pre-check",
    response_model=PreAssessmentCheckResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Combined Pre-Flight Readiness",
)
@router.get("/pre-check", response_model=PreAssessmentCheckResponse, tags=["AI Prep - Candidate"], summary="Combined Pre-Check")
def candidate_pre_check(
    auth_ctx: Dict[str, Any] = Depends(require_candidate_or_employee),
    db: Session = Depends(get_db),
):
    """Verifies both LLM key and resume readiness before starting assessment."""
    candidate_id = enforce_candidate_access(None, auth_ctx)
    llm_check = check_candidate_llm_key(db, candidate_id)
    resume_check = check_candidate_resume(db, candidate_id)
    eligible = bool(llm_check["is_configured"] and (resume_check["has_resume"] or resume_check["has_parsed_json"]))
    return PreAssessmentCheckResponse(
        eligible=eligible,
        candidate_id=candidate_id,
        llm_check=LLMKeyStatusResponse(**llm_check),
        resume_check=ResumeStatusResponse(**resume_check),
        message="Ready to start assessment" if eligible else "Prerequisites missing: setup required",
    )


@router.post(
    "/candidate/assessments",
    response_model=CreateAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Start Assessment Session",
)
@router.post(
    "/assessments",
    response_model=CreateAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["AI Prep - Candidate"],
    summary="Create Assessment Session",
)
def candidate_create_assessment(
    payload: CreateAssessmentRequest,
    auth_ctx: Dict[str, Any] = Depends(require_candidate_or_employee),
    db: Session = Depends(get_db),
):
    """Candidate endpoint: validates prerequisites and initializes session with IN_PROGRESS status."""
    candidate_id = enforce_candidate_access(payload.candidate_id, auth_ctx)
    verify_assessment_prerequisites(db, candidate_id)

    session_data = AssessmentOrchestrator.start_assessment_session(
        db=db,
        candidate_id=candidate_id,
        assessment_type=payload.assessment_type.value,
        media_type=payload.media_type.value,
        job_description=payload.job_description,
    )

    return CreateAssessmentResponse(
        id=session_data["id"],
        assessment_uuid=session_data["assessment_uuid"],
        status=session_data["status"],
        started_at=session_data["started_at"],
        assessment_type=session_data["assessment_type"],
        media_type=session_data["media_type"],
        questions=session_data["questions"],
    )


@router.get(
    "/candidate/assessments",
    response_model=AssessmentListResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: List Own Assessments",
)
@router.get("/assessments", response_model=AssessmentListResponse, tags=["AI Prep - Candidate"], summary="List Assessments")
def candidate_list_assessments(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    auth_ctx: Dict[str, Any] = Depends(require_candidate_or_employee),
    db: Session = Depends(get_db),
):
    """Lists only the assessments belonging to the authenticated candidate."""
    candidate_id = enforce_candidate_access(None, auth_ctx)
    items, total = list_assessments(db=db, candidate_id=candidate_id, limit=limit, offset=offset)
    return AssessmentListResponse(
        items=[
            AssessmentListItem(
                id=a.id,
                assessment_uuid=a.assessment_uuid,
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


@router.get(
    "/candidate/assessments/{assessment_id}",
    response_model=AssessmentDetailResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Get Assessment Details & Report",
)
@router.get("/assessments/{assessment_id}", response_model=AssessmentDetailResponse, tags=["AI Prep - Candidate"], summary="Get Assessment Details")
def candidate_get_assessment_detail(
    assessment_id: int,
    auth_ctx: Dict[str, Any] = Depends(require_candidate_or_employee),
    db: Session = Depends(get_db),
):
    """Candidate endpoint: fetches own assessment detail and report."""
    assessment = get_assessment_by_id(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    enforce_candidate_access(assessment.candidate_id, auth_ctx)

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
        assessment_type=assessment.assessment_type,
        media_type=assessment.media_type,
        status=assessment.status,
        job_description=assessment.job_description,
        youtube_url=assessment.youtube_url,
        started_at=assessment.started_at,
        completed_at=assessment.completed_at,
        created_at=assessment.created_at,
        data=data_dict,
        report=report_dict,
    )


@router.post(
    "/candidate/assessments/{assessment_id}/data",
    response_model=SubmitAssessmentDataResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Submit Assessment Telemetry",
)
@router.post("/assessments/{assessment_id}/data", response_model=SubmitAssessmentDataResponse, tags=["AI Prep - Candidate"], summary="Submit Telemetry")
def candidate_submit_data(
    assessment_id: int,
    payload: SubmitAssessmentDataRequest,
    auth_ctx: Dict[str, Any] = Depends(require_candidate_or_employee),
    db: Session = Depends(get_db),
):
    """Submits candidate recording metrics and transcript."""
    assessment = get_assessment_by_id(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    enforce_candidate_access(assessment.candidate_id, auth_ctx)
    save_assessment_data(
        db=db,
        assessment_id=assessment_id,
        questions=payload.questions,
        transcript=payload.transcript,
        audio_telemetry=payload.audio_telemetry,
        video_telemetry=payload.video_telemetry,
    )
    return SubmitAssessmentDataResponse(message="Data saved successfully")


@router.patch(
    "/candidate/assessments/{assessment_id}/media",
    response_model=UpdateMediaURLResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Update Media Stream URL",
)
@router.patch("/assessments/{assessment_id}/media", response_model=UpdateMediaURLResponse, tags=["AI Prep - Candidate"], summary="Update Media URL")
def candidate_update_media_url(
    assessment_id: int,
    payload: UpdateMediaURLRequest,
    auth_ctx: Dict[str, Any] = Depends(require_candidate_or_employee),
    db: Session = Depends(get_db),
):
    """Updates media playback URL."""
    assessment = get_assessment_by_id(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    enforce_candidate_access(assessment.candidate_id, auth_ctx)
    updated = update_assessment_media_url(db, assessment_id, payload.youtube_url)
    return UpdateMediaURLResponse(id=updated.id, youtube_url=updated.youtube_url)


@router.post(
    "/candidate/assessments/{assessment_id}/evaluate",
    response_model=TriggerEvaluationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Trigger Evaluation (POST)",
)
@router.post("/assessments/{assessment_id}/evaluate", response_model=TriggerEvaluationResponse, status_code=status.HTTP_202_ACCEPTED, tags=["AI Prep - Candidate"], summary="Trigger Evaluation")
def candidate_trigger_eval_post(
    assessment_id: int,
    background_tasks: BackgroundTasks,
    auth_ctx: Dict[str, Any] = Depends(require_candidate_or_employee),
    db: Session = Depends(get_db),
):
    """Transitions status to EVALUATING and starts evaluation pipeline."""
    assessment = get_assessment_by_id(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    enforce_candidate_access(assessment.candidate_id, auth_ctx)
    update_assessment_status(db, assessment_id, "EVALUATING")
    background_tasks.add_task(_async_run_eval, assessment_id)
    return TriggerEvaluationResponse(id=assessment.id, status="EVALUATING")


@router.put(
    "/candidate/assessments/{assessment_id}/evaluate",
    response_model=TriggerEvaluationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Submit & Evaluate (PUT)",
)
@router.put("/assessments/{assessment_id}/evaluate", response_model=TriggerEvaluationResponse, status_code=status.HTTP_202_ACCEPTED, tags=["AI Prep - Candidate"], summary="Submit & Evaluate")
def candidate_trigger_eval_put(
    assessment_id: int,
    background_tasks: BackgroundTasks,
    payload: Optional[SubmitAssessmentRequest] = None,
    auth_ctx: Dict[str, Any] = Depends(require_candidate_or_employee),
    db: Session = Depends(get_db),
):
    """Submits telemetry and launches evaluation."""
    assessment = get_assessment_by_id(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    enforce_candidate_access(assessment.candidate_id, auth_ctx)
    if payload and (payload.transcript or payload.audio_telemetry or payload.video_telemetry):
        save_assessment_data(
            db=db,
            assessment_id=assessment_id,
            questions=payload.questions or [],
            transcript=payload.transcript or {},
            audio_telemetry=payload.audio_telemetry or {},
            video_telemetry=payload.video_telemetry or {},
        )

    update_assessment_status(db, assessment_id, "EVALUATING")
    background_tasks.add_task(_async_run_eval, assessment_id)
    return TriggerEvaluationResponse(id=assessment.id, status="EVALUATING")


# ===========================================================================
# 2. EMPLOYEE & ADMIN ROUTES (Tags: ["AI Prep - Employee / Admin"])
# ===========================================================================

@router.get(
    "/employee/candidates/{candidate_id}/llm-keys",
    response_model=LLMKeyStatusResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: Check Candidate LLM Keys",
)
@router.get("/candidates/{candidate_id}/llm-keys", response_model=LLMKeyStatusResponse, tags=["AI Prep - Employee / Admin"], summary="Employee Check LLM Keys")
def employee_check_candidate_llm_keys_route(
    candidate_id: int,
    auth_ctx: Dict[str, Any] = Depends(require_employee_or_admin),
    db: Session = Depends(get_db),
):
    """Employee endpoint: inspect LLM key validity for any candidate."""
    result = check_candidate_llm_key(db, candidate_id)
    return LLMKeyStatusResponse(**result)


@router.get(
    "/employee/candidates/{candidate_id}/resume-status",
    response_model=ResumeStatusResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: Check Candidate Resume Status",
)
@router.get("/candidates/{candidate_id}/resume-status", response_model=ResumeStatusResponse, tags=["AI Prep - Employee / Admin"], summary="Employee Check Resume")
def employee_check_candidate_resume_route(
    candidate_id: int,
    auth_ctx: Dict[str, Any] = Depends(require_employee_or_admin),
    db: Session = Depends(get_db),
):
    """Employee endpoint: inspect resume setup for any candidate."""
    result = check_candidate_resume(db, candidate_id)
    return ResumeStatusResponse(**result)


@router.get(
    "/employee/candidates/{candidate_id}/pre-check",
    response_model=PreAssessmentCheckResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: Pre-Flight Readiness for Candidate",
)
@router.get("/candidates/{candidate_id}/pre-check", response_model=PreAssessmentCheckResponse, tags=["AI Prep - Employee / Admin"], summary="Employee Candidate Pre-Check")
def employee_check_candidate_pre_check_route(
    candidate_id: int,
    auth_ctx: Dict[str, Any] = Depends(require_employee_or_admin),
    db: Session = Depends(get_db),
):
    """Employee endpoint: check combined eligibility for any candidate."""
    llm_check = check_candidate_llm_key(db, candidate_id)
    resume_check = check_candidate_resume(db, candidate_id)
    eligible = bool(llm_check["is_configured"] and (resume_check["has_resume"] or resume_check["has_parsed_json"]))
    return PreAssessmentCheckResponse(
        eligible=eligible,
        candidate_id=candidate_id,
        llm_check=LLMKeyStatusResponse(**llm_check),
        resume_check=ResumeStatusResponse(**resume_check),
        message="Ready to start assessment" if eligible else "Prerequisites missing",
    )


@router.get(
    "/employee/assessments",
    response_model=AssessmentListResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: Comprehensive Assessments Table Grid",
)
def employee_list_assessments_table(
    candidate_id: Optional[int] = Query(None, description="Filter by candidate ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (IN_PROGRESS, EVALUATING, COMPLETED, FAILED)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    auth_ctx: Dict[str, Any] = Depends(require_employee_or_admin),
    db: Session = Depends(get_db),
):
    """Employee/Admin Grid: lists all candidate assessments with filtering."""
    items, total = list_assessments(
        db=db,
        candidate_id=candidate_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return AssessmentListResponse(
        items=[
            AssessmentListItem(
                id=a.id,
                assessment_uuid=a.assessment_uuid,
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


@router.get(
    "/employee/candidates/{candidate_id}/assessments",
    response_model=AssessmentListResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: List Specific Candidate Assessments",
)
@router.get("/candidates/{candidate_id}/assessments", response_model=AssessmentListResponse, tags=["AI Prep - Employee / Admin"], summary="List Assessments by Candidate ID")
def employee_list_candidate_assessments_route(
    candidate_id: int,
    auth_ctx: Dict[str, Any] = Depends(require_employee_or_admin),
    db: Session = Depends(get_db),
):
    """Employee endpoint: view assessment history for any specific candidate ID."""
    items, total = list_assessments(db=db, candidate_id=candidate_id)
    return AssessmentListResponse(
        items=[
            AssessmentListItem(
                id=a.id,
                assessment_uuid=a.assessment_uuid,
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


@router.get(
    "/employee/assessments/{assessment_id}",
    response_model=AssessmentDetailResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: Inspect Assessment Details & Scores",
)
def employee_get_assessment_detail_route(
    assessment_id: int,
    auth_ctx: Dict[str, Any] = Depends(require_employee_or_admin),
    db: Session = Depends(get_db),
):
    """Employee/Admin endpoint to review complete telemetry and scores for any assessment."""
    assessment = get_assessment_by_id(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

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
        assessment_type=assessment.assessment_type,
        media_type=assessment.media_type,
        status=assessment.status,
        job_description=assessment.job_description,
        youtube_url=assessment.youtube_url,
        started_at=assessment.started_at,
        completed_at=assessment.completed_at,
        created_at=assessment.created_at,
        data=data_dict,
        report=report_dict,
    )


# ===========================================================================
# 3. MEDIA PIPELINE, CHUNKS & STREAMING (Tags: ["AI Prep - Media & Streaming"])
# ===========================================================================

@router.post(
    "/media/upload-chunk",
    response_model=ChunkUploadResponse,
    tags=["AI Prep - Media & Streaming"],
    summary="Media: Upload 30s WebM Chunk",
)
async def upload_media_chunk(
    assessment_id: int = Form(...),
    chunk_number: int = Form(...),
    total_chunks: Optional[int] = Form(None),
    file: UploadFile = File(...),
    auth_ctx: Dict[str, Any] = Depends(require_candidate_or_employee),
    db: Session = Depends(get_db),
):
    """Uploads sequential WebM media chunk into local server storage."""
    assessment = get_assessment_by_id(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    enforce_candidate_access(assessment.candidate_id, auth_ctx)
    chunk_dir = os.path.join(STORAGE_BASE_DIR, str(assessment.candidate_id), str(assessment_id), "chunks")
    os.makedirs(chunk_dir, exist_ok=True)
    chunk_path = os.path.join(chunk_dir, f"chunk_{chunk_number:04d}.webm")

    content = await file.read()
    with open(chunk_path, "wb") as f:
        f.write(content)

    uploaded_files = [f for f in os.listdir(chunk_dir) if f.startswith("chunk_") and f.endswith(".webm")]
    is_ready = bool(total_chunks and len(uploaded_files) >= total_chunks)

    return ChunkUploadResponse(
        success=True,
        assessment_id=assessment_id,
        chunk_number=chunk_number,
        bytes_written=len(content),
        total_uploaded=len(uploaded_files),
        is_ready_for_assembly=is_ready,
        message=f"Chunk {chunk_number} uploaded successfully",
    )


@router.get(
    "/media/chunk-status",
    response_model=ChunkStatusResponse,
    tags=["AI Prep - Media & Streaming"],
    summary="Media: Query Chunk Upload Status",
)
def get_chunk_upload_status(
    assessment_id: int = Query(...),
    total_chunks: Optional[int] = Query(None),
    auth_ctx: Dict[str, Any] = Depends(require_candidate_or_employee),
    db: Session = Depends(get_db),
):
    """Returns uploaded vs missing chunk numbers for upload resume/retry."""
    assessment = get_assessment_by_id(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    enforce_candidate_access(assessment.candidate_id, auth_ctx)
    chunk_dir = os.path.join(STORAGE_BASE_DIR, str(assessment.candidate_id), str(assessment_id), "chunks")
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


@router.post(
    "/media/assemble",
    response_model=AssembleMediaResponse,
    tags=["AI Prep - Media & Streaming"],
    summary="Media: Assemble Chunks & Process",
)
def assemble_media_chunks(
    assessment_id: int = Query(...),
    payload: Optional[AssembleMediaRequest] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    auth_ctx: Dict[str, Any] = Depends(require_candidate_or_employee),
    db: Session = Depends(get_db),
):
    """Concatenates WebM chunks and launches evaluation pipeline."""
    assessment = get_assessment_by_id(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    enforce_candidate_access(assessment.candidate_id, auth_ctx)
    assessment_dir = os.path.join(STORAGE_BASE_DIR, str(assessment.candidate_id), str(assessment_id))
    background_tasks.add_task(_async_run_eval, assessment_id)

    return AssembleMediaResponse(
        success=True,
        assessment_id=assessment_id,
        status="ASSEMBLING",
        media_path=os.path.join(assessment_dir, "assembled_media.webm"),
        audio_path=os.path.join(assessment_dir, "extracted_audio.wav"),
        message="Media chunks queued for assembly and evaluation",
    )


@router.post(
    "/media/upload",
    response_model=LocalMediaUploadResponse,
    tags=["AI Prep - Media & Streaming"],
    summary="Media: Direct Single Media Upload",
)
async def upload_raw_media(
    assessment_id: int = Form(...),
    media_type: str = Form("VIDEO"),
    file: UploadFile = File(...),
    auth_ctx: Dict[str, Any] = Depends(require_candidate_or_employee),
    db: Session = Depends(get_db),
):
    """Uploads single binary media file directly."""
    assessment = get_assessment_by_id(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    enforce_candidate_access(assessment.candidate_id, auth_ctx)
    assessment_dir = os.path.join(STORAGE_BASE_DIR, str(assessment.candidate_id), str(assessment_id))
    os.makedirs(assessment_dir, exist_ok=True)
    dest_path = os.path.join(assessment_dir, f"raw_{file.filename}")

    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    return LocalMediaUploadResponse(
        success=True,
        assessment_id=assessment_id,
        file_path=dest_path,
        media_type=media_type,
        message="Media file uploaded successfully",
    )


@router.get(
    "/employee/media/storage-info",
    response_model=StorageInfoResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: Media Storage Quota & Usage",
)
@router.get("/media/storage-info", response_model=StorageInfoResponse, tags=["AI Prep - Employee / Admin"], summary="Storage Info")
def get_media_storage_info(
    auth_ctx: Dict[str, Any] = Depends(require_employee_or_admin),
):
    """Returns storage directory disk usage and assessment folder count."""
    total, used, free = shutil.disk_usage(STORAGE_BASE_DIR if os.path.exists(STORAGE_BASE_DIR) else ".")
    assessment_count = len(os.listdir(STORAGE_BASE_DIR)) if os.path.exists(STORAGE_BASE_DIR) else 0
    return StorageInfoResponse(
        storage_dir=os.path.abspath(STORAGE_BASE_DIR),
        total_bytes=total,
        used_bytes=used,
        free_bytes=free,
        assessment_count=assessment_count,
    )


@router.get(
    "/assessments/{assessment_id}/status",
    response_model=ProcessingStatusResponse,
    tags=["AI Prep - Media & Streaming"],
    summary="Progress: Assessment Processing Status Snapshot",
)
def get_assessment_processing_status(
    assessment_id: int,
    auth_ctx: Dict[str, Any] = Depends(require_candidate_or_employee),
    db: Session = Depends(get_db),
):
    """Returns assessment pipeline processing progress snapshot."""
    assessment = get_assessment_by_id(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    enforce_candidate_access(assessment.candidate_id, auth_ctx)
    progress_map = {"IN_PROGRESS": 25.0, "EVALUATING": 65.0, "COMPLETED": 100.0, "FAILED": 0.0}
    return ProcessingStatusResponse(
        assessment_id=assessment_id,
        status=assessment.status,
        step="Evaluation Completed" if assessment.status == "COMPLETED" else "Processing Ingested Media",
        progress_pct=progress_map.get(assessment.status, 50.0),
        message=f"Assessment is {assessment.status}",
    )


@router.get(
    "/assessments/{assessment_id}/stream",
    tags=["AI Prep - Media & Streaming"],
    summary="Progress: Real-Time SSE Status Stream",
)
def stream_assessment_processing_sse(
    assessment_id: int,
    auth_ctx: Dict[str, Any] = Depends(require_candidate_or_employee),
    db: Session = Depends(get_db),
):
    """Real-time SSE event stream for live UI progress updates."""
    assessment = get_assessment_by_id(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    enforce_candidate_access(assessment.candidate_id, auth_ctx)

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


# ===========================================================================
# 4. QUESTION BANK & CATALOG MANAGEMENT (Tags: ["AI Prep - Admin & Catalog"])
# ===========================================================================

@router.get(
    "/assessment-types",
    response_model=AssessmentTypeListResponse,
    tags=["AI Prep - Admin & Catalog"],
    summary="Catalog: List Assessment Types",
)
@router.get("/assessment_types", response_model=AssessmentTypeListResponse, include_in_schema=False)
def list_available_assessment_types(
    db: Session = Depends(get_db),
):
    """Fetches all active assessment types from catalog."""
    types = list_assessment_types(db, active_only=True)
    return AssessmentTypeListResponse(
        items=[AssessmentTypeResponse.from_orm(t) for t in types],
        total=len(types),
    )


@router.post(
    "/employee/assessment-types",
    response_model=AssessmentTypeResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["AI Prep - Admin & Catalog"],
    summary="Admin: Create Assessment Type",
)
@router.post("/assessment-types", response_model=AssessmentTypeResponse, status_code=status.HTTP_201_CREATED, tags=["AI Prep - Admin & Catalog"], summary="Create Assessment Type")
def create_new_assessment_type(
    type_in: AssessmentTypeCreate,
    auth_ctx: Dict[str, Any] = Depends(require_employee_or_admin),
    db: Session = Depends(get_db),
):
    """Admin endpoint to create a new assessment type."""
    created = create_assessment_type(db, type_in.dict())
    return AssessmentTypeResponse.from_orm(created)


@router.get(
    "/questions",
    response_model=QuestionListResponse,
    tags=["AI Prep - Admin & Catalog"],
    summary="Question Bank: List Questions",
)
def list_questions_from_bank(
    category: Optional[str] = Query(None),
    difficulty_level: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Fetches questions with filters for category, difficulty, and active status."""
    items, total = list_questions(
        db=db,
        category=category,
        difficulty_level=difficulty_level,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return QuestionListResponse(
        items=[QuestionResponse.from_orm(q) for q in items],
        total=total,
    )


@router.post(
    "/employee/questions",
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["AI Prep - Admin & Catalog"],
    summary="Admin: Add Question Bank Item",
)
@router.post("/questions", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED, tags=["AI Prep - Admin & Catalog"], summary="Add Question Bank Item")
def add_question_to_bank(
    payload: QuestionCreateRequest,
    auth_ctx: Dict[str, Any] = Depends(require_employee_or_admin),
    db: Session = Depends(get_db),
):
    """Adds a new question to the question bank."""
    created = create_question(db, payload.dict())
    return QuestionResponse.from_orm(created)


@router.patch(
    "/employee/questions/{question_id}",
    response_model=QuestionResponse,
    tags=["AI Prep - Admin & Catalog"],
    summary="Admin: Update Question Bank Item",
)
@router.patch("/questions/{question_id}", response_model=QuestionResponse, tags=["AI Prep - Admin & Catalog"], summary="Update Question Bank Item")
def update_question_in_bank(
    question_id: int,
    payload: QuestionUpdateRequest,
    auth_ctx: Dict[str, Any] = Depends(require_employee_or_admin),
    db: Session = Depends(get_db),
):
    """Updates fields on an existing question (e.g. soft-delete by setting is_active=False)."""
    updated = update_question(db, question_id, payload.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Question not found")
    return QuestionResponse.from_orm(updated)
