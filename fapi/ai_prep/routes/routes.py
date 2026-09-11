"""FastAPI Routes and API Endpoints for AI Prep Tool.
Delegates business logic to fapi.ai_prep.utils.aiprep_utils following WBL Backend architecture.
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
    "/candidate/pre-check",
    response_model=PreAssessmentCheckResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Combined Pre-Flight Readiness",
)
@router.get("/pre-check", response_model=PreAssessmentCheckResponse, tags=["AI Prep - Candidate"], summary="Combined Pre-Check")
def candidate_pre_check(
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verifies both LLM key and resume readiness before starting assessment."""
    return aiprep_utils.candidate_pre_check_logic(db=db, current_user=current_user)


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
        payload=payload,
        ip_address=ip_address,
        user_agent=user_agent,
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
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists assessments belonging to the authenticated candidate dynamically from DB."""
    return aiprep_utils.candidate_list_assessments_logic(db=db, current_user=current_user, limit=limit, offset=offset)


@router.get(
    "/candidate/assessments/{assessment_id}",
    response_model=AssessmentDetailResponse,
    tags=["AI Prep - Candidate"],
    summary="Candidate: Get Assessment Details & Report",
)
@router.get("/assessments/{assessment_id}", response_model=AssessmentDetailResponse, tags=["AI Prep - Candidate"], summary="Get Assessment Details")
def candidate_get_assessment_detail(
    assessment_id: int,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetches assessment detail, telemetry, and evaluation scores from DB."""
    return aiprep_utils.candidate_get_assessment_detail_logic(db=db, current_user=current_user, assessment_id=assessment_id)


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
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Persists candidate telemetry, transcript, and answers into ai_prep_assessment_data."""
    return aiprep_utils.candidate_submit_data_logic(db=db, current_user=current_user, assessment_id=assessment_id, payload=payload)


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
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Updates YouTube/video playback URL on assessment in DB."""
    return aiprep_utils.candidate_update_media_url_logic(db=db, current_user=current_user, assessment_id=assessment_id, payload=payload)


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
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Transitions status to EVALUATING in DB."""
    return aiprep_utils.candidate_trigger_eval_post_logic(db=db, current_user=current_user, assessment_id=assessment_id)


@router.put(
    "/candidate/assessments/{assessment_id}/evaluate",
    response_model=TriggerEvaluationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Candidate: Submit & Evaluate (PUT)",
)
@router.put("/assessments/{assessment_id}/evaluate", response_model=TriggerEvaluationResponse, status_code=status.HTTP_202_ACCEPTED, tags=["AI Prep - Candidate"], summary="Submit & Evaluate")
def candidate_trigger_eval_put(
    assessment_id: int,
    payload: Optional[SubmitAssessmentRequest] = None,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Saves telemetry if provided and transitions status to EVALUATING."""
    return aiprep_utils.candidate_trigger_eval_put_logic(db=db, current_user=current_user, assessment_id=assessment_id, payload=payload)


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
def employee_check_candidate_resume_route(
    candidate_id: int,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Employee endpoint: inspect resume setup for any candidate dynamically from DB."""
    return aiprep_utils.employee_check_candidate_resume_logic(db=db, candidate_id=candidate_id)


@router.get(
    "/employee/candidates/{candidate_id}/pre-check",
    response_model=PreAssessmentCheckResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: Pre-Flight Readiness for Candidate",
)
@router.get("/candidates/{candidate_id}/pre-check", response_model=PreAssessmentCheckResponse, tags=["AI Prep - Employee / Admin"], summary="Employee Candidate Pre-Check")
def employee_check_candidate_pre_check_route(
    candidate_id: int,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Employee endpoint: check combined eligibility dynamically from DB."""
    return aiprep_utils.employee_check_candidate_pre_check_logic(db=db, candidate_id=candidate_id)


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
@router.get("/candidates/{candidate_id}/assessments", response_model=AssessmentListResponse, tags=["AI Prep - Employee / Admin"], summary="List Assessments by Candidate ID")
def employee_list_candidate_assessments_route(
    candidate_id: int,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Employee endpoint: view assessment history for any specific candidate ID."""
    return aiprep_utils.employee_list_candidate_assessments_logic(db=db, candidate_id=candidate_id)


@router.get(
    "/employee/assessments/{assessment_id}",
    response_model=AssessmentDetailResponse,
    tags=["AI Prep - Employee / Admin"],
    summary="Employee: Inspect Assessment Details & Scores",
)
def employee_get_assessment_detail_route(
    assessment_id: int,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Employee/Admin endpoint to review complete telemetry and scores for any assessment."""
    return aiprep_utils.employee_get_assessment_detail_logic(db=db, assessment_id=assessment_id)


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


# ===========================================================================
# 3. MEDIA PIPELINE, CHUNKS & STREAMING
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
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Uploads sequential WebM media chunk to server storage directory."""
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
    tags=["AI Prep - Media & Streaming"],
    summary="Media: Query Chunk Upload Status",
)
def get_chunk_upload_status(
    assessment_id: int = Query(...),
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
    "/media/assemble",
    response_model=AssembleMediaResponse,
    tags=["AI Prep - Media & Streaming"],
    summary="Media: Assemble Chunks & Process",
)
def assemble_media_chunks(
    assessment_id: int = Query(...),
    payload: Optional[AssembleMediaRequest] = None,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Concatenates WebM chunks and launches evaluation."""
    return aiprep_utils.assemble_media_chunks_logic(
        db=db,
        current_user=current_user,
        assessment_id=assessment_id,
        payload=payload,
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
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Uploads single binary media file directly to disk storage."""
    content = await file.read()
    return await aiprep_utils.upload_raw_media_logic(
        db=db,
        current_user=current_user,
        assessment_id=assessment_id,
        media_type=media_type,
        filename=file.filename,
        file_content=content,
    )


@router.get(
    "/assessments/{assessment_id}/status",
    response_model=ProcessingStatusResponse,
    tags=["AI Prep - Media & Streaming"],
    summary="Progress: Assessment Processing Status Snapshot",
)
def get_assessment_processing_status(
    assessment_id: int,
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
    assessment_id: int,
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Real-time SSE event stream for live UI progress updates."""
    return aiprep_utils.stream_assessment_processing_sse_logic(
        db=db,
        current_user=current_user,
        assessment_id=assessment_id,
    )
