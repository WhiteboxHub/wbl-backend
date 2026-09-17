"""FastAPI Routes and API Endpoints for AI Prep Tool.
Delegates business logic to fapi.ai_prep.utils.aiprep_utils following WBL Backend architecture.
Standardized canonical REST endpoints under /api/aiprep with unified JWT authentication.
"""
import logging
from typing import Optional
from fastapi import (
    APIRouter,
    Depends,
    Query,
    UploadFile,
    File,
    Form,
    status,
    Request,
    BackgroundTasks,
    HTTPException,
)
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.utils.auth_dependencies import get_current_user, staff_or_admin_required
from fapi.db.models import AuthUserORM

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
from fapi.ai_prep.utils import aiprep_utils

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Prep Tool"])


# ===========================================================================
# 1. READINESS & PRE-FLIGHT CHECKS
# ===========================================================================

@router.get(
    "/pre-check",
    response_model=PreAssessmentCheckResponse,
    tags=["AI Prep - Readiness"],
    summary="Pre-Flight Readiness Check (Resume & LLM Key)",
)
def candidate_pre_check(
    candidate_id: Optional[int] = Query(None, description="Optional candidate ID for staff inspection"),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verifies both LLM key and resume readiness before starting assessment."""
    return aiprep_utils.candidate_pre_check_logic(db=db, current_user=current_user, candidate_id=candidate_id)


@router.get(
    "/llm-keys",
    response_model=LLMKeyStatusResponse,
    tags=["AI Prep - Readiness"],
    summary="Check LLM Key Status",
)
def candidate_check_llm_keys(
    candidate_id: Optional[int] = Query(None, description="Optional candidate ID for staff inspection"),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Checks configured LLM key status dynamically from DB."""
    return aiprep_utils.candidate_check_llm_keys_logic(db=db, current_user=current_user, candidate_id=candidate_id)


@router.get(
    "/resume-status",
    response_model=ResumeStatusResponse,
    tags=["AI Prep - Readiness"],
    summary="Check Candidate Resume Status",
)
def candidate_check_resume_status(
    candidate_id: Optional[int] = Query(None, description="Optional candidate ID for staff inspection"),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Checks parsed resume status dynamically from DB."""
    return aiprep_utils.candidate_check_resume_status_logic(db=db, current_user=current_user, candidate_id=candidate_id)


# ===========================================================================
# 2. ASSESSMENT CATALOG & TYPES
# ===========================================================================

@router.get(
    "/assessment-types",
    response_model=AssessmentTypeListResponse,
    tags=["AI Prep - Catalog"],
    summary="Catalog: List Available Assessment Types",
)
def list_available_assessment_types(
    current_user: AuthUserORM = Depends(get_current_user),
):
    """Fetches all active assessment types from the catalog."""
    _ = current_user
    return aiprep_utils.list_available_assessment_types_logic()


@router.post(
    "/assessment-types",
    response_model=AssessmentTypeResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["AI Prep - Catalog"],
    summary="Admin: Create Assessment Type",
)
def create_new_assessment_type(
    type_in: AssessmentTypeCreate,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
):
    """Admin endpoint to create a new assessment type in catalog."""
    _ = _staff
    return aiprep_utils.create_new_assessment_type_logic(type_in=type_in)


# ===========================================================================
# 3. ASSESSMENTS LIFECYCLE & EXECUTION
# ===========================================================================

@router.post(
    "/assessments",
    response_model=CreateAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["AI Prep - Assessments"],
    summary="Create & Initialize Assessment Session",
)
def create_assessment(
    payload: CreateAssessmentRequest,
    request: Request,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Validates prerequisites and initializes a new assessment session row in DB."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return aiprep_utils.candidate_create_assessment_logic(
        db=db,
        current_user=current_user,
        payload=payload,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.get(
    "/assessments",
    response_model=AssessmentListResponse,
    tags=["AI Prep - Assessments"],
    summary="List Assessments (Candidate Scoped or Staff Filterable)",
)
def list_assessments(
    candidate_id: Optional[int] = Query(None, description="Staff-only filter for specific candidate"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (e.g. COMPLETED, IN_PROGRESS)"),
    assessment_type: Optional[str] = Query(None, description="Filter by assessment type (e.g. INTRO, TECHNICAL)"),
    media_type: Optional[str] = Query(None, description="Filter by media type (e.g. VIDEO, AUDIO)"),
    search: Optional[str] = Query(None, description="Search filter"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unified assessment listing: auto-scoped to current candidate, or filtered for staff/admin."""
    return aiprep_utils.candidate_list_assessments_logic(
        db=db,
        current_user=current_user,
        candidate_id=candidate_id,
        status_filter=status_filter,
        assessment_type=assessment_type,
        media_type=media_type,
        search=search,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Admin Assessment Lifecycle & Inspection
# ---------------------------------------------------------------------------

@router.get(
    "/assessments/{assessment_id}",
    response_model=AssessmentDetailResponse,
    tags=["AI Prep - Admin Assessments"],
    summary="Admin: Get Assessment Details, Telemetry & Scores",
)
def admin_get_assessment_detail(
    assessment_id: str,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Admin: Fetches full assessment details, telemetry, questions, and evaluation scores."""
    return aiprep_utils.admin_get_assessment_detail_logic(
        db=db,
        assessment_id=assessment_id,
    )


@router.get(
    "/assessments/{assessment_id}/data",
    response_model=AssessmentDataResponse,
    tags=["AI Prep - Admin Assessments"],
    summary="Admin: Get Assessment Telemetry & Questions",
)
def admin_get_assessment_data(
    assessment_id: str,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Admin: Fetches submitted telemetry, transcript, and questions for an assessment."""
    return aiprep_utils.admin_get_assessment_data_logic(
        db=db,
        assessment_id=assessment_id,
    )


@router.post(
    "/assessments/{assessment_id}/data",
    response_model=SubmitAssessmentDataResponse,
    tags=["AI Prep - Admin Assessments"],
    summary="Admin: Submit Assessment Telemetry & Answers",
)
def admin_submit_assessment_data(
    assessment_id: str,
    payload: SubmitAssessmentDataRequest,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Admin: Persists telemetry, transcript, and answers into ai_prep_assessment_data."""
    return aiprep_utils.admin_submit_data_logic(
        db=db,
        assessment_id=assessment_id,
        payload=payload,
    )


@router.get(
    "/assessments/{assessment_id}/report",
    response_model=AssessmentReportResponse,
    tags=["AI Prep - Admin Assessments"],
    summary="Admin: Get Assessment Evaluation Report",
)
def admin_get_assessment_report(
    assessment_id: str,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Admin: Fetches generated evaluation report for an assessment."""
    return aiprep_utils.admin_get_assessment_report_logic(
        db=db,
        assessment_id=assessment_id,
    )


@router.patch(
    "/assessments/{assessment_id}/media",
    response_model=UpdateMediaURLResponse,
    tags=["AI Prep - Admin Assessments"],
    summary="Admin: Update Assessment Media Stream URL",
)
def admin_update_assessment_media_url(
    assessment_id: str,
    payload: UpdateMediaURLRequest,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Admin: Updates media stream URL on assessment in DB."""
    return aiprep_utils.admin_update_media_url_logic(
        db=db,
        assessment_id=assessment_id,
        payload=payload,
    )


@router.post(
    "/assessments/{assessment_id}/evaluate",
    response_model=TriggerEvaluationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["AI Prep - Admin Assessments"],
    summary="Admin: Trigger Assessment Evaluation (POST)",
)
def admin_trigger_assessment_evaluation(
    assessment_id: str,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """Admin: Transitions status to EVALUATING in DB and queues background LLM evaluation."""
    return aiprep_utils.admin_trigger_eval_post_logic(
        db=db,
        assessment_id=assessment_id,
        background_tasks=background_tasks,
    )


@router.put(
    "/assessments/{assessment_id}/evaluate",
    response_model=TriggerEvaluationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["AI Prep - Admin Assessments"],
    summary="Admin: Submit & Evaluate Assessment (PUT)",
)
def admin_submit_and_evaluate_assessment(
    assessment_id: str,
    payload: Optional[SubmitAssessmentRequest] = None,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """Admin: Saves telemetry if provided, transitions status to EVALUATING, and queues evaluation."""
    return aiprep_utils.admin_trigger_eval_put_logic(
        db=db,
        assessment_id=assessment_id,
        payload=payload,
        background_tasks=background_tasks,
    )


# ---------------------------------------------------------------------------
# Candidate Assessment Lifecycle & Execution
# ---------------------------------------------------------------------------

@router.get(
    "/candidate/assessments/{assessment_id}",
    response_model=AssessmentDetailResponse,
    tags=["AI Prep - Candidate Assessments"],
    summary="Candidate: Get Assessment Details & Report",
)
def candidate_get_assessment_detail(
    assessment_id: str,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Candidate: Fetches assessment detail, telemetry, and evaluation scores."""
    return aiprep_utils.candidate_get_assessment_detail_logic(
        db=db,
        current_user=current_user,
        assessment_id=assessment_id,
    )


@router.get(
    "/candidate/assessments/{assessment_id}/data",
    response_model=AssessmentDataResponse,
    tags=["AI Prep - Candidate Assessments"],
    summary="Candidate: Get Assessment Telemetry & Questions",
)
def candidate_get_assessment_data(
    assessment_id: str,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Candidate: Fetches submitted telemetry, transcript, and questions for own assessment."""
    return aiprep_utils.candidate_get_assessment_data_logic(
        db=db,
        current_user=current_user,
        assessment_id=assessment_id,
    )


@router.post(
    "/candidate/assessments/{assessment_id}/data",
    response_model=SubmitAssessmentDataResponse,
    tags=["AI Prep - Candidate Assessments"],
    summary="Candidate: Submit Assessment Telemetry & Answers",
)
def candidate_submit_assessment_data(
    assessment_id: str,
    payload: SubmitAssessmentDataRequest,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Candidate: Persists telemetry, transcript, and answers for own assessment."""
    return aiprep_utils.candidate_submit_data_logic(
        db=db,
        current_user=current_user,
        assessment_id=assessment_id,
        payload=payload,
    )


@router.get(
    "/candidate/assessments/{assessment_id}/report",
    response_model=AssessmentReportResponse,
    tags=["AI Prep - Candidate Assessments"],
    summary="Candidate: Get Assessment Evaluation Report",
)
def candidate_get_assessment_report(
    assessment_id: str,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Candidate: Fetches evaluation report for own evaluated assessment."""
    return aiprep_utils.candidate_get_assessment_report_logic(
        db=db,
        current_user=current_user,
        assessment_id=assessment_id,
    )


@router.patch(
    "/candidate/assessments/{assessment_id}/media",
    response_model=UpdateMediaURLResponse,
    tags=["AI Prep - Candidate Assessments"],
    summary="Candidate: Update Assessment Media Stream URL",
)
def candidate_update_assessment_media_url(
    assessment_id: str,
    payload: UpdateMediaURLRequest,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Candidate: Updates media stream URL on own in-progress assessment."""
    return aiprep_utils.candidate_update_media_url_logic(
        db=db,
        current_user=current_user,
        assessment_id=assessment_id,
        payload=payload,
    )


@router.post(
    "/candidate/assessments/{assessment_id}/evaluate",
    response_model=TriggerEvaluationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["AI Prep - Candidate Assessments"],
    summary="Candidate: Trigger Assessment Evaluation (POST)",
)
def candidate_trigger_assessment_evaluation(
    assessment_id: str,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """Candidate: Transitions status to EVALUATING and queues background LLM evaluation."""
    return aiprep_utils.candidate_trigger_eval_post_logic(
        db=db,
        current_user=current_user,
        assessment_id=assessment_id,
        background_tasks=background_tasks,
    )


@router.put(
    "/candidate/assessments/{assessment_id}/evaluate",
    response_model=TriggerEvaluationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["AI Prep - Candidate Assessments"],
    summary="Candidate: Submit & Evaluate Assessment (PUT)",
)
def candidate_submit_and_evaluate_assessment(
    assessment_id: str,
    payload: Optional[SubmitAssessmentRequest] = None,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """Candidate: Saves telemetry, transitions status to EVALUATING, and queues background LLM evaluation."""
    return aiprep_utils.candidate_trigger_eval_put_logic(
        db=db,
        current_user=current_user,
        assessment_id=assessment_id,
        payload=payload,
        background_tasks=background_tasks,
    )


@router.get(
    "/assessments/{assessment_id}/status",
    response_model=ProcessingStatusResponse,
    tags=["AI Prep - Assessments"],
    summary="Get Assessment Processing Status",
)
def get_assessment_processing_status(
    assessment_id: str,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Polls real-time assessment processing status from Redis."""
    return aiprep_utils.get_assessment_processing_status_logic(db=db, current_user=current_user, assessment_id=assessment_id)


@router.get(
    "/assessments/{assessment_id}/stream",
    tags=["AI Prep - Assessments"],
    summary="SSE Live Stream for Evaluation Progress",
)
async def stream_assessment_processing_sse(
    assessment_id: str,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Server-Sent Events (SSE) endpoint streaming real-time orchestrator stage events."""
    return aiprep_utils.stream_assessment_processing_sse_logic(
        db=db,
        current_user=current_user,
        assessment_id=assessment_id,
    )


# ===========================================================================
# 4. QUESTION BANK MANAGEMENT
# ===========================================================================

@router.get(
    "/questions",
    response_model=QuestionListResponse,
    tags=["AI Prep - Questions"],
    summary="Question Bank: List Questions",
)
def list_questions(
    category: Optional[str] = Query(None, description="Filter by category (e.g. TECHNICAL, GENERAL)"),
    difficulty_level: Optional[str] = Query(None, description="Filter by difficulty (EASY, MEDIUM, HARD)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetches questions dynamically from ai_prep_questions DB table."""
    _ = current_user
    return aiprep_utils.list_questions_from_bank_logic(
        db=db,
        category=category,
        difficulty_level=difficulty_level,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/questions",
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["AI Prep - Questions"],
    summary="Admin: Add Question Bank Item",
)
def add_question(
    payload: QuestionCreateRequest,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Adds a new question to the ai_prep_questions table in DB."""
    return aiprep_utils.add_question_to_bank_logic(db=db, payload=payload)


@router.get(
    "/questions/{question_id}",
    response_model=QuestionResponse,
    tags=["AI Prep - Questions"],
    summary="Question Bank: Get Question by ID",
)
def get_question(
    question_id: int,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetches a specific question by ID from the question bank."""
    _ = current_user
    return aiprep_utils.get_question_from_bank_logic(db=db, question_id=question_id)


@router.patch(
    "/questions/{question_id}",
    response_model=QuestionResponse,
    tags=["AI Prep - Questions"],
    summary="Admin: Update Question Bank Item",
)
def update_question(
    question_id: int,
    payload: QuestionUpdateRequest,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Updates fields on an existing question dynamically in DB."""
    return aiprep_utils.update_question_in_bank_logic(db=db, question_id=question_id, payload=payload)


@router.delete(
    "/questions/{question_id}",
    tags=["AI Prep - Questions"],
    summary="Admin: Deactivate Question Bank Item",
)
def delete_question(
    question_id: int,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Deactivates/deletes a question from the question bank."""
    return aiprep_utils.delete_question_from_bank_logic(db=db, question_id=question_id)


# ===========================================================================
# 5. MEDIA PIPELINE & CHUNKS INGESTION
# ===========================================================================

@router.post(
    "/media/upload",
    response_model=LocalMediaUploadResponse,
    tags=["AI Prep - Media"],
    summary="Media: Direct Video/Audio File Upload",
)
async def upload_raw_media(
    assessment_id: str = Form(...),
    file: UploadFile = File(...),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Accepts full recording file from browser and saves to storage directory."""
    content = await file.read()
    return await aiprep_utils.upload_raw_media_logic(
        db=db,
        current_user=current_user,
        assessment_id=assessment_id,
        filename=file.filename or "recording.webm",
        file_content=content,
    )


@router.post(
    "/media/upload-chunk",
    response_model=ChunkUploadResponse,
    tags=["AI Prep - Media"],
    summary="Media: Upload Sequential Media Chunk",
)
async def upload_media_chunk(
    assessment_id: str = Form(...),
    chunk_number: int = Form(...),
    total_chunks: Optional[int] = Form(None),
    file: UploadFile = File(...),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Uploads sequential media chunk to server storage directory."""
    content = await file.read()
    return await aiprep_utils.upload_media_chunk_logic(
        db=db,
        current_user=current_user,
        assessment_id=assessment_id,
        chunk_number=chunk_number,
        total_chunks=total_chunks,
        file_content=content,
    )


@router.get(
    "/media/chunk-status",
    response_model=ChunkStatusResponse,
    tags=["AI Prep - Media"],
    summary="Media: Query Chunk Upload Progress",
)
def get_chunk_upload_status(
    assessment_id: str = Query(...),
    total_chunks: Optional[int] = Query(None),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns list of already uploaded chunks for an assessment to handle retries."""
    return aiprep_utils.get_chunk_upload_status_logic(
        db=db,
        current_user=current_user,
        assessment_id=assessment_id,
        total_chunks=total_chunks,
    )


@router.post(
    "/media/assemble",
    response_model=AssembleMediaResponse,
    tags=["AI Prep - Media"],
    summary="Media: Assemble Uploaded Chunks",
)
def assemble_media_chunks(
    payload: Optional[AssembleMediaRequest] = None,
    assessment_id: Optional[str] = Query(None, description="Optional assessment ID query param if not in JSON body"),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Merges sequential chunks into final recording file and updates assessment row in DB."""
    target_aid = (payload.assessment_id if payload and payload.assessment_id else None) or assessment_id
    if not target_aid:
        raise HTTPException(status_code=400, detail="assessment_id is required")
    return aiprep_utils.assemble_media_chunks_logic(
        db=db,
        current_user=current_user,
        assessment_id=target_aid,
        payload=payload,
    )


@router.get(
    "/media/storage-info",
    response_model=StorageInfoResponse,
    tags=["AI Prep - Media"],
    summary="Staff: Media Storage Quota & Usage",
)
def get_media_storage_info(
    _staff: AuthUserORM = Depends(staff_or_admin_required),
):
    """Returns real storage directory disk usage and assessment folder count."""
    return aiprep_utils.get_media_storage_info_logic()
