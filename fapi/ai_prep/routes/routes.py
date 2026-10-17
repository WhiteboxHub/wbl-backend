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
    PreAssessmentCheckResponse,
    CreateAssessmentRequest,
    CreateAssessmentResponse,
    AssessmentListResponse,
    MediaChunkUploadResponse,
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
    limit: Optional[int] = Query(50, ge=1, le=100),
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
    request: Request,
    status: Optional[str] = Query(None, description="Set to 'cancelled' if exiting/cancelling assessment"),
    stream: bool = Query(False, description="Set to true to stream real-time SSE progress updates directly over the submission request"),
    current_user: AuthUserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Candidate Submit Assessment:
    - Supports both multipart/form-data (direct audio file upload + assessment_data JSON)
      and application/json (legacy chunk submissions).
    - If status == 'cancelled' (e.g. Exit clicked): Changes assessment status to CANCELLED in DB and exits immediately.
    - Otherwise: Processes audio/media, runs Audio Engine (Whisper + audio metrics), evaluates gatekeeper flag
      (insufficient_content) using transcript word count and interview duration,
      and returns assessment details and flag status.
    - If stream=true or Accept: text/event-stream: streams real-time progress events directly over the PUT connection.
    """
    return await aiprep_utils.candidate_submit_assessment_logic(
        db=db,
        current_user=current_user,
        candidate_id=candidate_id,
        assessment_id=assessment_id,
        payload=None,
        status=status,
        background_tasks=background_tasks,
        request=request,
        stream=stream,
    )


# ===========================================================================
# 2. EMPLOYEE & ADMIN ROUTES
# ===========================================================================




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
    "/questions",
    response_model=QuestionListResponse,
    tags=["AI Prep - Admin & Catalog"],
    summary="Question Bank: List Questions",
)
def list_questions_from_bank(
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    category: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    concept: Optional[str] = Query(None),
    difficulty_level: Optional[str] = Query(None),
    scope: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Fetches questions dynamically from ai_prep_questions DB table for authorized staff."""
    _ = _staff
    return aiprep_utils.list_questions_from_bank_logic(
        db=db,
        category=category,
        subject=subject,
        concept=concept,
        difficulty_level=difficulty_level,
        scope=scope,
        is_active=is_active,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.post("/questions", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED, tags=["AI Prep - Admin & Catalog"], summary="Add Question Bank Item")
def add_question_to_bank(
    payload: QuestionCreateRequest,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Adds a new question to the question bank for authorized staff."""
    _ = _staff
    return aiprep_utils.add_question_to_bank_logic(db=db, payload=payload)


@router.get("/questions/{question_id}", response_model=QuestionResponse, tags=["AI Prep - Admin & Catalog"], summary="Get Question Bank Item")
def get_question_from_bank(
    question_id: int,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Retrieves an existing question by ID for authorized staff."""
    _ = _staff
    return aiprep_utils.get_question_from_bank_logic(db=db, question_id=question_id)


@router.patch("/questions/{question_id}", response_model=QuestionResponse, tags=["AI Prep - Admin & Catalog"], summary="Update Question Bank Item")
def update_question_in_bank(
    question_id: int,
    payload: QuestionUpdateRequest,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Updates an existing question for authorized staff."""
    _ = _staff
    return aiprep_utils.update_question_in_bank_logic(db=db, question_id=question_id, payload=payload)


@router.delete("/questions/{question_id}", tags=["AI Prep - Admin & Catalog"], summary="Deactivate Question Bank Item")
def delete_question_from_bank(
    question_id: int,
    _staff: AuthUserORM = Depends(staff_or_admin_required),
    db: Session = Depends(get_db),
):
    """Deactivates a question for authorized staff to preserve assessment history."""
    _ = _staff
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


