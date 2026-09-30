"""FastAPI Routes and API Endpoints for AI Prep Tool.
Delegates business logic to fapi.ai_prep.utils.aiprep_utils following WBL Backend architecture.
"""
import logging
from typing import Optional, Union, Dict, Any
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
    Body,
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
    UpdateMediaURLRequest,
    UpdateMediaURLResponse,
    AssessmentListResponse,
    MediaChunkUploadResponse,
    ChunkStatusResponse,
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
    CandidateAssessmentDetailResponse,
)
from fapi.ai_prep.utils import aiprep_utils

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Prep Tool"])


# ===========================================================================
# 1. CANDIDATE-FACING ROUTES
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
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Candidate self-check for configured LLM key dynamically from DB."""
    return aiprep_utils.candidate_check_llm_keys_logic(db=db, current_user=current_user)


@router.get(
    "/candidate/resume-status",
    response_model=ResumeStatusResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Check Own Resume Status",
)
@router.get("/resume-status", response_model=ResumeStatusResponse, tags=["AI Prep - Candidate"], summary="Check Own Resume")
@router.get("/resume_status", response_model=ResumeStatusResponse, include_in_schema=False)
def candidate_check_resume_status(
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Candidate self-check for parsed resume status dynamically from DB."""
    return aiprep_utils.candidate_check_resume_status_logic(db=db, current_user=current_user)


@router.get(
    "/candidates/{id}/assessment-readiness-precheck",
    response_model=PreAssessmentCheckResponse,
    tags=["AI Prep - Candidate"],
    summary="Assessment Readiness Pre-Check",
)
def candidate_assessment_readiness_precheck(
    id: Union[int, str],
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Checks whether candidate has active LLM key in 'My LLM Setup' and resume in 'My Resume'.

    Only allows candidate to proceed with assessment if both are ready; otherwise specifies respective setup.
    """
    return aiprep_utils.assessment_readiness_precheck_logic(
        db=db, current_user=current_user, candidate_id=id
    )


@router.post(
    "/candidates/{id}/assessments",
    response_model=CreateAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Create Assessment Session",
)
def candidate_create_assessment(
    id: Union[int, str],
    payload: CreateAssessmentRequest,
    request: Request,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dynamically validates prerequisites and creates a new assessment row in DB."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return aiprep_utils.candidate_create_assessment_logic(
        db=db,
        current_user=current_user,
        candidate_id=id,
        payload=payload,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.get(
    "/candidates/{id}/assessments",
    response_model=AssessmentListResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: List Candidate Assessments",
)
def candidate_list_assessments(
    id: Union[int, str],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists all assessments attempted/completed by a particular candidate using id.

    Authorization:
    - Candidate can only access their own assessments (attempting to access another candidate's id returns 403 Forbidden).
    - Candidate A must not be able to access Candidate B's assessment or any of Candidate B's data.
    - Staff / Admin can view any candidate's assessments.
    """
    return aiprep_utils.candidate_list_assessments_logic(
        db=db,
        current_user=current_user,
        candidate_id=id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/candidates/{id}/assessments/{assessment_id}",
    response_model=CandidateAssessmentDetailResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Get Complete Assessment Detail",
)
def candidate_get_assessment_detail(
    id: Union[int, str],
    assessment_id: Union[int, str],
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the complete details of a specific assessment for the authenticated candidate.

    Authorization:
    - A candidate can only retrieve their own assessment. Passing another candidate's
      `id` or an `assessment_id` that does not belong to them raises HTTP 403.
    - Staff / admin users may use this endpoint to inspect any candidate's assessment.
    """
    return aiprep_utils.candidate_get_assessment_detail_logic(
        db=db,
        current_user=current_user,
        candidate_id=id,
        assessment_id=assessment_id,
    )


@router.put(
    "/candidates/{candidate_id}/assessments/{assessment_id}",
    response_model=Union[CandidateSubmitAssessmentResponse, Dict[str, Any]],
    tags=["AI Prep - Candidate"],
    summary="Candidate: Submit Assessment or Cancel",
)
async def candidate_submit_assessment(
    candidate_id: Union[int, str],
    assessment_id: Union[int, str],
    background_tasks: BackgroundTasks,
    payload: Optional[CandidateSubmitAssessmentRequest] = Body(default=None),
    status: Optional[str] = Query(None, description="Set to 'cancelled' if exiting/cancelling assessment"),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Candidate Submit Assessment:
    - If status == 'cancelled' (e.g. Exit clicked): Changes assessment status to CANCELLED in DB and exits immediately.
    - Otherwise: Notifies backend that recording is complete, stitches media chunks,
      executes Audio Engine (Whisper + audio metrics), evaluates gatekeeper flag
      (insufficient_content) using transcript word count and interview duration,
      and returns assessment details and flag status.
    """
    return await aiprep_utils.candidate_submit_assessment_logic(
        db=db,
        current_user=current_user,
        candidate_id=candidate_id,
        assessment_id=assessment_id,
        payload=payload,
        status=status,
        background_tasks=background_tasks,
    )


@router.patch(
    "/candidate/assessments/{assessment_id}/media",
    response_model=UpdateMediaURLResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Update Media Stream URL",
)
@router.patch("/assessments/{assessment_id}/media", response_model=UpdateMediaURLResponse, tags=["AI Prep - Candidate"], summary="Update Media URL")
def candidate_update_media_url(
    assessment_id: Union[int, str],
    payload: UpdateMediaURLRequest,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Updates YouTube/video playback URL on assessment in DB."""
    return aiprep_utils.candidate_update_media_url_logic(db=db, current_user=current_user, assessment_id=assessment_id, payload=payload)


@router.get(
    "/candidate/assessment-types",
    response_model=AssessmentTypeListResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: List Available Assessment Types",
)
@router.get(
    "/assessment-types",
    response_model=AssessmentTypeListResponse,
    tags=["AI Prep - Admin & Catalog"],
    summary="Catalog: List Assessment Types",
)
@router.get("/assessment_types", response_model=AssessmentTypeListResponse, include_in_schema=False)
def list_available_assessment_types(
    current_user: AuthUserORM = Depends(get_current_user),
):
    """Fetches all active assessment types from the catalog."""
    _ = current_user
    return aiprep_utils.list_available_assessment_types_logic()


# ===========================================================================
# 2. EMPLOYEE & ADMIN ROUTES
# ===========================================================================

@router.get(
    "/employee/candidates/{candidate_id}/llm-keys",
    response_model=LLMKeyStatusResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: Check Candidate LLM Keys",
)
@router.get("/candidates/{candidate_id}/llm-keys", response_model=LLMKeyStatusResponse, tags=["AI Prep - Employee / Admin"], summary="Employee Check LLM Keys")
@router.get("/employee/candidate/{candidate_id}/llm-keys", response_model=LLMKeyStatusResponse, include_in_schema=False)
@router.get("/candidate/{candidate_id}/llm-keys", response_model=LLMKeyStatusResponse, include_in_schema=False)
def employee_check_candidate_llm_keys_route(
    candidate_id: int,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Employee endpoint: inspect LLM key validity for any candidate dynamically from DB."""
    return aiprep_utils.employee_check_candidate_llm_keys_logic(db=db, candidate_id=candidate_id)


@router.get(
    "/employee/candidates/{candidate_id}/resume-status",
    response_model=ResumeStatusResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: Check Candidate Resume Status",
)
@router.get("/candidates/{candidate_id}/resume-status", response_model=ResumeStatusResponse, tags=["AI Prep - Employee / Admin"], summary="Employee Check Resume")
@router.get("/employee/candidate/{candidate_id}/resume-status", response_model=ResumeStatusResponse, include_in_schema=False)
@router.get("/candidate/{candidate_id}/resume-status", response_model=ResumeStatusResponse, include_in_schema=False)
def employee_check_candidate_resume_route(
    candidate_id: int,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Employee endpoint: inspect resume setup for any candidate dynamically from DB."""
    return aiprep_utils.employee_check_candidate_resume_logic(db=db, candidate_id=candidate_id)




@router.get(
    "/employee/assessments",
    response_model=AssessmentListResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: Comprehensive Assessments Table Grid",
)
def employee_list_assessments_table(
    candidate_id: Optional[int] = Query(None, description="Filter by candidate ID"),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Employee/Admin Grid: lists all candidate assessments from DB with filtering."""
    return aiprep_utils.employee_list_assessments_table_logic(
        db=db,
        candidate_id=candidate_id,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/employee/candidates/{candidate_id}/assessments",
    response_model=AssessmentListResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: List Specific Candidate Assessments",
)
@router.get("/employee/candidate/{candidate_id}/assessments", response_model=AssessmentListResponse, include_in_schema=False)
def employee_list_candidate_assessments_route(
    candidate_id: int,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Employee endpoint: view assessment history for any specific candidate ID."""
    return aiprep_utils.employee_list_candidate_assessments_logic(db=db, candidate_id=candidate_id)




@router.get(
    "/employee/media/storage-info",
    response_model=StorageInfoResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: Media Storage Quota & Usage",
)
@router.get("/media/storage-info", response_model=StorageInfoResponse, tags=["AI Prep - Employee / Admin"], summary="Storage Info")
def get_media_storage_info(
    _staff: AuthUserORM = Depends(staff_or_admin_required),
):
    """Returns real storage directory disk usage and assessment folder count."""
    return aiprep_utils.get_media_storage_info_logic()


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
    _staff: AuthUserORM = Depends(staff_or_admin_required),
):
    """Admin endpoint to create a new assessment type in catalog."""
    _ = _staff
    return aiprep_utils.create_new_assessment_type_logic(type_in=type_in)


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
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Fetches questions dynamically from ai_prep_questions DB table."""
    return aiprep_utils.list_questions_from_bank_logic(
        db=db,
        category=category,
        difficulty_level=difficulty_level,
        is_active=is_active,
        limit=limit,
        offset=offset,
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
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Adds a new question to the ai_prep_questions table in DB."""
    return aiprep_utils.add_question_to_bank_logic(db=db, payload=payload)


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
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Updates fields on an existing question dynamically in DB."""
    return aiprep_utils.update_question_in_bank_logic(db=db, question_id=question_id, payload=payload)


@router.get(
    "/employee/questions/{question_id}",
    response_model=QuestionResponse,
    tags=["AI Prep - Admin & Catalog"],
    summary="Admin: Get Question Bank Item by ID",
)
@router.get("/questions/{question_id}", response_model=QuestionResponse, tags=["AI Prep - Admin & Catalog"], summary="Get Question Bank Item by ID")
def get_question_from_bank(
    question_id: int,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Fetches a specific question by ID from the question bank."""
    return aiprep_utils.get_question_from_bank_logic(db=db, question_id=question_id)


@router.delete(
    "/employee/questions/{question_id}",
    tags=["AI Prep - Admin & Catalog"],
    summary="Admin: Deactivate Question Bank Item",
)
@router.delete("/questions/{question_id}", tags=["AI Prep - Admin & Catalog"], summary="Deactivate Question Bank Item")
def delete_question_from_bank(
    question_id: int,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Deactivates/deletes a question from the question bank."""
    return aiprep_utils.delete_question_from_bank_logic(db=db, question_id=question_id)



# ===========================================================================
# 3. MEDIA PIPELINE, CHUNKS & STREAMING
# ===========================================================================

@router.post(
    "/candidates/{candidate_id}/assessments/{assessment_id}/media/chunk",
    response_model=MediaChunkUploadResponse,
    tags=["AI Prep - Media & Streaming"],
    summary="Media: Upload Assessment Chunk",
)
async def upload_candidate_assessment_chunk(
    candidate_id: Union[int, str],
    assessment_id: Union[int, str],
    chunk_index: int = Form(..., ge=0),
    assessment_uuid: Optional[str] = Form(None),
    is_final: bool = Form(False),
    media_file: UploadFile = File(..., description="WebM media chunk file to upload"),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Uploads sequential WebM media chunk for candidate assessment."""
    return await aiprep_utils.upload_candidate_assessment_chunk_logic(
        db=db,
        current_user=current_user,
        candidate_id=candidate_id,
        assessment_id=assessment_id,
        chunk_index=chunk_index,
        file_content=media_file,
        assessment_uuid=assessment_uuid,
        is_final=is_final,
    )


@router.get(
    "/media/chunk-status",
    response_model=ChunkStatusResponse,
    tags=["AI Prep - Media & Streaming"],
    summary="Media: Query Chunk Upload Status",
)
def get_chunk_upload_status(
    assessment_id: Union[int, str] = Query(...),
    total_chunks: Optional[int] = Query(None),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dynamically reads disk storage to check uploaded vs missing chunk numbers."""
    return aiprep_utils.get_chunk_upload_status_logic(
        db=db,
        current_user=current_user,
        assessment_id=assessment_id,
        total_chunks=total_chunks,
    )




@router.post(
    "/media/upload",
    response_model=LocalMediaUploadResponse,
    tags=["AI Prep - Media & Streaming"],
    summary="Media: Direct Single Media Upload",
)
async def upload_raw_media(
    background_tasks: BackgroundTasks,
    assessment_id: Union[int, str] = Form(...),
    media_type: str = Form("VIDEO"),
    file: UploadFile = File(...),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Uploads single binary media file directly to disk storage using streaming."""
    return await aiprep_utils.upload_raw_media_logic(
        db=db,
        current_user=current_user,
        assessment_id=assessment_id,
        media_type=media_type,
        file=file,
        background_tasks=background_tasks,
    )


@router.get(
    "/assessments/{assessment_id}/status",
    response_model=ProcessingStatusResponse,
    tags=["AI Prep - Media & Streaming"],
    summary="Progress: Assessment Processing Status Snapshot",
)
def get_assessment_processing_status(
    assessment_id: Union[int, str],
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns assessment pipeline processing progress snapshot dynamically from DB."""
    return aiprep_utils.get_assessment_processing_status_logic(
        db=db,
        current_user=current_user,
        assessment_id=assessment_id,
    )


@router.get(
    "/assessments/{assessment_id}/stream",
    tags=["AI Prep - Media & Streaming"],
    summary="Progress: Real-Time SSE Status Stream",
)
def stream_assessment_processing_sse(
    assessment_id: Union[int, str],
    request: Request,
    current_user: AuthUserORM = Depends(get_current_user),
):
    """Real-time SSE event stream for live UI progress updates."""
    return aiprep_utils.stream_assessment_processing_sse_logic(
        current_user=current_user,
        assessment_id=assessment_id,
        request=request,
    )


@router.post(
    "/candidate/assessments/{assessment_id}/audio",
    response_model=AudioUploadResponse,
    tags=["AI Prep - Media & Streaming"],
    summary="Candidate: Direct Audio Recording Upload",
)
@router.post(
    "/assessments/{assessment_id}/audio",
    response_model=AudioUploadResponse,
    tags=["AI Prep - Media & Streaming"],
    summary="Direct Audio Recording Upload",
)
async def upload_assessment_audio(
    background_tasks: BackgroundTasks,
    assessment_id: Union[int, str],
    file: UploadFile = File(...),
    mime_type: Optional[str] = Form(None),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Uploads audio recording binary file directly to server storage and queues YouTube upload."""
    return await aiprep_utils.upload_assessment_audio_logic(
        db=db,
        current_user=current_user,
        assessment_id=assessment_id,
        file=file,
        mime_type=mime_type,
        background_tasks=background_tasks,
    )


@router.get(
    "/candidate/assessments/{assessment_id}/audio",
    tags=["AI Prep - Media & Streaming"],
    summary="Candidate: Stream Assessment Audio from Storage",
)
@router.get(
    "/assessments/{assessment_id}/audio",
    tags=["AI Prep - Media & Streaming"],
    summary="Stream Assessment Audio from Storage",
)
def get_assessment_audio(
    assessment_id: Union[int, str],
    request: Request,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves and streams stored audio recording binary from server storage with range seeking support."""
    range_header = request.headers.get("range")
    return aiprep_utils.get_assessment_audio_logic(
        db=db,
        current_user=current_user,
        assessment_id=assessment_id,
        range_header=range_header,
    )


@router.get(
    "/candidate/assessments/{assessment_id}/video",
    tags=["AI Prep - Media & Streaming"],
    summary="Candidate: Stream Assessment Video Recording from Storage",
)
@router.get(
    "/assessments/{assessment_id}/video",
    tags=["AI Prep - Media & Streaming"],
    summary="Stream Assessment Video Recording from Storage",
)
def get_assessment_video(
    assessment_id: Union[int, str],
    request: Request,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves and streams stored video recording from server storage with range seeking support."""
    range_header = request.headers.get("range")
    return aiprep_utils.get_assessment_video_logic(
        db=db,
        current_user=current_user,
        assessment_id=assessment_id,
        range_header=range_header,
    )
# ===========================================================================
# 4. PERFORMANCE TESTING & BENCHMARKING
# ===========================================================================
@router.post(
    "/audio-engine/process",
    tags=["AI Prep - Media & Streaming"],
    summary="Performance: Audio Engine Benchmark & Process",
)
async def process_audio_engine_endpoint(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    audio_path: Optional[str] = Form(None),
    provider: Optional[str] = Form(None),
    model_size: str = Form("base"),
    async_mode: bool = Form(False),
    current_user: AuthUserORM = Depends(staff_or_admin_required),
):
    """
    Performance Testing Endpoint:
    Directly triggers the AudioMetricsEngine pipeline with configurable transcription providers.
    Supports direct audio file upload or a server-side storage path.
    Gated to staff/admin to prevent resource abuse.
    """
    _ = current_user
    return await aiprep_utils.process_audio_engine_logic(
        background_tasks=background_tasks,
        file=file,
        audio_path=audio_path,
        provider=provider,
        model_size=model_size,
        async_mode=async_mode,
    )


