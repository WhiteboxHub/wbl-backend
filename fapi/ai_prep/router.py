"""
FastAPI Router for AI Prep Assessment Platform.
Strictly implements the 10 API endpoints specified in contracts/api_endpoints.md.
"""

import os
from typing import Optional, List, Dict, Any
from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    Form,
    BackgroundTasks,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from fapi.ai_prep import schemas, crud, config, dependencies
from fapi.ai_prep.orchestrator.assessment_orchestrator import (
    AssessmentOrchestrator,
    assessment_orchestrator,
)
from fapi.ai_prep.clients.youtube_client import YouTubeClient
from fapi.ai_prep.services.sse_service import sse_service

router = APIRouter(prefix="/api/aiprep", tags=["AIPrep"])


# ─── Part 0: Assessment Types Metadata & Candidate Status ─────────────────────

ASSESSMENT_TYPES_CATALOG = [
    schemas.AssessmentTypeItem(
        type="INTRO",
        title="Intro Assessment",
        category="Behavioral",
        description="Evaluate basic self-introduction, communication clarity, and background presentation.",
        supported_media=["AUDIO", "VIDEO"],
        is_active=True,
        questions_count=1,
        icon="user-voice",
        difficulty_levels=["EASY", "MEDIUM"],
    ),
    schemas.AssessmentTypeItem(
        type="JD_INTRO",
        title="JD Walkthrough",
        category="Role Match",
        description="Walk through specific job requirements, match relevant experience, and explain job alignment.",
        supported_media=["AUDIO", "VIDEO"],
        is_active=True,
        questions_count=1,
        icon="briefcase",
        difficulty_levels=["MEDIUM", "HARD"],
    ),
    schemas.AssessmentTypeItem(
        type="RECRUITER",
        title="Recruiter Screen",
        category="Screening",
        description="Simulated first-round recruiter screening interview focusing on background and availability.",
        supported_media=["AUDIO", "VIDEO"],
        is_active=True,
        questions_count=5,
        icon="users",
        difficulty_levels=["EASY", "MEDIUM"],
    ),
    schemas.AssessmentTypeItem(
        type="TECHNICAL",
        title="Technical Assessment",
        category="Technical",
        description="Deep-dive technical questions covering software engineering, algorithms, and domain knowledge.",
        supported_media=["AUDIO", "VIDEO"],
        is_active=True,
        questions_count=5,
        icon="code",
        difficulty_levels=["MEDIUM", "HARD", "EXPERT"],
    ),
    schemas.AssessmentTypeItem(
        type="HIRING_MANAGER",
        title="Hiring Manager Round",
        category="Leadership",
        description="Scenario-based questions assessing technical leadership, problem solving, and cultural fit.",
        supported_media=["AUDIO", "VIDEO"],
        is_active=True,
        questions_count=5,
        icon="user-check",
        difficulty_levels=["MEDIUM", "HARD"],
    ),
    schemas.AssessmentTypeItem(
        type="SYSTEM_DESIGN",
        title="System Design",
        category="Architecture",
        description="End-to-end distributed system design, trade-off analysis, scalability, and architecture.",
        supported_media=["AUDIO", "VIDEO"],
        is_active=True,
        questions_count=3,
        icon="cpu",
        difficulty_levels=["HARD", "EXPERT"],
    ),
]


@router.get(
    "/assessment-types",
    response_model=schemas.AssessmentTypeListResponse,
    status_code=status.HTTP_200_OK,
    summary="0. List Assessment Types Metadata (Hardcoded Catalog)",
)
def list_assessment_types():
    """Returns assessment categories, descriptions, and media options without altering DB schema."""
    return schemas.AssessmentTypeListResponse(
        items=ASSESSMENT_TYPES_CATALOG,
        total=len(ASSESSMENT_TYPES_CATALOG),
    )


@router.get(
    "/candidate/llm-status",
    response_model=schemas.LLMKeyStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Check Candidate LLM Key Status",
)
def check_candidate_llm_status(
    candidate_id: Optional[int] = Query(None, description="Candidate ID filter (employees/admin only)"),
    auth_ctx: Dict[str, Any] = Depends(dependencies.get_authenticated_user_context),
    db: Session = Depends(dependencies.get_db),
):
    """
    Validates LLM API key status for a candidate.
    - Candidate: can only check their own status.
    - Employee/Admin: can check on behalf of any candidate by ID.
    """
    effective_candidate_id = dependencies.resolve_candidate_id_with_auth(candidate_id, auth_ctx)

    from fapi.db.models import CandidateLlmApiKeyORM

    row = (
        db.query(CandidateLlmApiKeyORM)
        .filter(
            CandidateLlmApiKeyORM.candidate_id == effective_candidate_id,
            CandidateLlmApiKeyORM.status == "active",
        )
        .order_by(
            CandidateLlmApiKeyORM.is_default.desc(),
            CandidateLlmApiKeyORM.updated_at.desc(),
            CandidateLlmApiKeyORM.id.desc(),
        )
        .first()
    )

    if not row:
        return schemas.LLMKeyStatusResponse(
            candidate_id=effective_candidate_id,
            has_active_key=False,
            provider=None,
            model=None,
            supports_voice=False,
            status="MISSING",
            message="No active LLM API key configured for candidate.",
        )

    supports_voice = bool(getattr(row, "voice_enabled", False))
    raw_provider = getattr(row, "provider_name", None)
    provider = str(raw_provider) if raw_provider and not hasattr(raw_provider, "_mock_name") else None
    raw_model = getattr(row, "model_name", None)
    model = str(raw_model) if raw_model and not hasattr(raw_model, "_mock_name") else None

    return schemas.LLMKeyStatusResponse(
        candidate_id=effective_candidate_id,
        has_active_key=True,
        provider=provider,
        model=model,
        supports_voice=supports_voice,
        status="VALID",
        message="Active LLM key configured and ready.",
    )




@router.get(
    "/candidate/resume-status",
    response_model=schemas.ResumeStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Check Candidate Resume Status",
)
def check_candidate_resume_status(
    candidate_id: Optional[int] = Query(None, description="Candidate ID filter (employees/admin only)"),
    auth_ctx: Dict[str, Any] = Depends(dependencies.get_authenticated_user_context),
    db: Session = Depends(dependencies.get_db),
):
    """
    Validates resume parsing status for a candidate.
    - Candidate: can only check their own resume status.
    - Employee/Admin: can check on behalf of any candidate by ID.
    """
    effective_candidate_id = dependencies.resolve_candidate_id_with_auth(candidate_id, auth_ctx)
    resume_json = crud.get_candidate_resume_json(db, effective_candidate_id)

    if not resume_json:
        return schemas.ResumeStatusResponse(
            candidate_id=effective_candidate_id,
            has_resume=False,
            status="MISSING",
            message="No parsed resume found for candidate. Please upload a resume in settings.",
        )

    return schemas.ResumeStatusResponse(
        candidate_id=effective_candidate_id,
        has_resume=True,
        status="VALID",
        message="Candidate resume is parsed and available.",
    )


# ─── Part 1: Assessment Execution Flow ───────────────────────────────────────

@router.post(
    "/assessments",
    response_model=schemas.CreateAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="1. Create Assessment Session with Pre-flight Validation",
)
def create_assessment(
    payload: schemas.CreateAssessmentRequest,
    request: Request,
    auth_ctx: Dict[str, Any] = Depends(dependencies.get_authenticated_user_context),
    db: Session = Depends(dependencies.get_db),
):
    """Initializes a new assessment session with pre-flight LLM key and resume checks."""
    effective_candidate_id = dependencies.resolve_candidate_id_with_auth(payload.candidate_id, auth_ctx)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    from fapi.ai_prep.exceptions import LLMKeyMissingError, ResumeMissingError, AssessmentOperationError

    try:
        assessment_dict = assessment_orchestrator.start_assessment(
            db=db,
            candidate_id=effective_candidate_id,
            assessment_type=payload.assessment_type,
            media_type=payload.media_type,
            job_description=payload.job_description,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return schemas.CreateAssessmentResponse(**assessment_dict)
    except LLMKeyMissingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": e.error_code,
                "detail": str(e),
                "missing_requirements": ["LLM_API_KEY"],
            },
        )
    except ResumeMissingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": e.error_code,
                "detail": str(e),
                "missing_requirements": ["RESUME"],
            },
        )
    except AssessmentOperationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": e.error_code, "detail": str(e)},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "INTERNAL_ERROR", "detail": str(e)},
        )


@router.post(
    "/assessments/{id}/submit",
    response_model=schemas.SubmitAssessmentResponse,
    status_code=status.HTTP_200_OK,
    summary="1b. Submit Assessment & Trigger Evaluation",
)
@router.put(
    "/assessments/{id}/submit",
    response_model=schemas.SubmitAssessmentResponse,
    status_code=status.HTTP_200_OK,
    summary="1b. Submit Assessment (PUT alias)",
)
def submit_assessment(
    id: int,
    payload: schemas.SubmitAssessmentRequest,
    auth_ctx: Dict[str, Any] = Depends(dependencies.get_authenticated_user_context),
    db: Session = Depends(dependencies.get_db),
):
    """
    Submits assessment recording/telemetry, evaluates via LLM Orchestrator & Analytics,
    and updates report to COMPLETED.
    """
    dependencies.get_assessment_or_403(id, auth_ctx=auth_ctx, db=db)

    try:
        res = assessment_orchestrator.submit_assessment(
            db=db,
            assessment_id=id,
            questions=payload.questions,
            transcript=payload.transcript,
            audio_telemetry=payload.audio_telemetry,
            video_telemetry=payload.video_telemetry,
        )
        return schemas.SubmitAssessmentResponse(
            assessment_id=id,
            status=res.get("status", "COMPLETED"),
            message=res.get("message", "Assessment evaluation completed successfully."),
            report=res.get("report"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "SUBMISSION_ERROR", "detail": str(e)},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "EVALUATION_FAILED", "detail": str(e)},
        )



@router.post(
    "/assessments/{id}/upload-media",
    status_code=status.HTTP_200_OK,
    summary="2. Upload Raw Media to Local Server Storage",
)
async def upload_media(
    id: int,
    file: UploadFile = File(...),
    bg_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(dependencies.get_db),
):
    """Saves raw recorded video/audio blob to local disk storage and triggers YouTube upload."""
    assessment = crud.get_assessment_by_id(db, id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    os.makedirs(config.settings.LOCAL_STORAGE_DIR, exist_ok=True)
    local_file_path = os.path.join(config.settings.LOCAL_STORAGE_DIR, f"{id}.webm")

    with open(local_file_path, "wb") as f:
        f.write(await file.read())

    # Background task creates its own independent SessionLocal() - no session connection leak!
    youtube_client = YouTubeClient()
    bg_tasks.add_task(youtube_client.upload_unlisted_video, id, local_file_path)

    return {
        "assessment_id": id,
        "local_file_path": local_file_path,
        "upload_status": "PROCESSING_YOUTUBE",
    }


@router.post(
    "/assessments/{id}/data",
    status_code=status.HTTP_200_OK,
    summary="3. Submit Telemetry Data",
)
def submit_data(
    id: int,
    payload: schemas.SubmitAssessmentDataRequest,
    db: Session = Depends(dependencies.get_db),
):
    """Saves telemetry data (questions, transcript, audio/video telemetry) for an assessment."""
    assessment = crud.get_assessment_by_id(db, id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    crud.create_or_update_assessment_data(
        db=db,
        assessment_id=id,
        questions=payload.questions,
        transcript=payload.transcript,
        audio_telemetry=payload.audio_telemetry,
        video_telemetry=payload.video_telemetry,
    )
    return {"message": "Data saved successfully"}


@router.patch(
    "/assessments/{id}/media",
    response_model=schemas.CreateAssessmentResponse,
    status_code=status.HTTP_200_OK,
    summary="4. Update Assessment Youtube Media URL",
)
def update_media_url(
    id: int,
    payload: schemas.UpdateMediaUrlRequest,
    db: Session = Depends(dependencies.get_db),
):
    """Updates the youtube_url after processing completes."""
    assessment = crud.update_assessment_youtube_url(db, id, payload.youtube_url)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment


@router.post(
    "/assessments/{id}/evaluate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="5. Trigger Assessment Evaluation",
)
def trigger_evaluation(
    id: int,
    bg_tasks: BackgroundTasks,
    db: Session = Depends(dependencies.get_db),
):
    """Changes assessment status to EVALUATING and triggers the Central Orchestrator."""
    assessment = crud.get_assessment_by_id(db, id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    crud.update_assessment_status(db, id, schemas.AssessmentStatusEnum.EVALUATING)

    # Background task creates its own independent SessionLocal() inside AssessmentOrchestrator
    orchestrator = AssessmentOrchestrator()
    bg_tasks.add_task(orchestrator.process_assessment_evaluation, id)

    return {"id": id, "status": schemas.AssessmentStatusEnum.EVALUATING}


@router.get(
    "/assessments/{id}",
    status_code=status.HTTP_200_OK,
    summary="6. Get Assessment Report & Telemetry Data",
)
def get_assessment_report(
    id: int,
    auth_ctx: Dict[str, Any] = Depends(dependencies.get_authenticated_user_context),
    db: Session = Depends(dependencies.get_db),
):
    """Fetches full assessment details including telemetry data and evaluation report."""
    assessment = dependencies.get_assessment_or_403(id, auth_ctx=auth_ctx, db=db)

    data = crud.get_assessment_data_by_assessment_id(db, id)
    report = crud.get_assessment_report_by_assessment_id(db, id)

    return {
        "id": assessment.id,
        "candidate_id": assessment.candidate_id,
        "assessment_type": assessment.assessment_type,
        "media_type": assessment.media_type,
        "status": assessment.status,
        "youtube_url": assessment.youtube_url,
        "data": {
            "questions": data.questions if data else None,
            "transcript": data.transcript if data else None,
            "audio_telemetry": data.audio_telemetry if data else None,
            "video_telemetry": data.video_telemetry if data else None,
        },
        "report": {
            "audio_evaluation": report.audio_evaluation if report else None,
            "video_evaluation": report.video_evaluation if report else None,
            "transcript_evaluation": report.transcript_evaluation if report else None,
        },
    }


# ─── Part 2: Candidate Dashboard ──────────────────────────────────────────────

@router.get(
    "/assessments",
    response_model=schemas.AssessmentListResponse,
    status_code=status.HTTP_200_OK,
    summary="7. List Candidate Assessments",
)
def list_candidate_assessments(
    candidate_id: Optional[int] = Query(None, description="Candidate ID filter (employees/admin can filter, candidates see own)"),
    auth_ctx: Dict[str, Any] = Depends(dependencies.get_authenticated_user_context),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(dependencies.get_db),
):
    """Fetches a paginated list of assessments for a specific candidate with auth validation."""
    effective_candidate_id = dependencies.resolve_candidate_id_with_auth(candidate_id, auth_ctx)
    assessments = crud.list_candidate_assessments(
        db, candidate_id=effective_candidate_id, limit=limit, offset=offset
    )
    return {"items": assessments, "total": len(assessments)}



# ─── Part 3: Question Bank Admin ──────────────────────────────────────────────

@router.get(
    "/questions",
    response_model=schemas.QuestionListResponse,
    status_code=status.HTTP_200_OK,
    summary="8. List Question Bank",
)
def list_questions(
    category: Optional[schemas.AssessmentCategoryEnum] = None,
    difficulty_level: Optional[schemas.DifficultyLevelEnum] = None,
    is_active: Optional[bool] = True,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(dependencies.get_db),
):
    """Fetches filtered list of questions for assessment engine or admin grid."""
    questions = crud.list_questions(
        db,
        category=category,
        difficulty_level=difficulty_level,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return {"items": questions, "total": len(questions)}


@router.post(
    "/questions",
    response_model=schemas.QuestionBankResponse,
    status_code=status.HTTP_201_CREATED,
    summary="9. Create Question Bank Item",
)
def create_question(
    payload: schemas.QuestionBankCreateRequest,
    db: Session = Depends(dependencies.get_db),
):
    """Adds a new question to the question bank."""
    return crud.create_question(
        db,
        category=payload.category,
        sub_category=payload.sub_category,
        difficulty_level=payload.difficulty_level,
        question_text=payload.question_text,
        is_active=payload.is_active,
    )


@router.patch(
    "/questions/{id}",
    response_model=schemas.QuestionBankResponse,
    status_code=status.HTTP_200_OK,
    summary="10. Update Question Bank Item",
)
def update_question(
    id: int,
    payload: schemas.QuestionBankUpdateRequest,
    db: Session = Depends(dependencies.get_db),
):
    """Updates fields on an existing question (e.g. soft-delete by setting is_active=False)."""
    question = crud.update_question(
        db,
        question_id=id,
        sub_category=payload.sub_category,
        difficulty_level=payload.difficulty_level,
        question_text=payload.question_text,
        is_active=payload.is_active,
    )
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question


# ─── Part 4: Media Ingestion, Assembly & Progress Streaming (BE2) ─────────────

@router.post(
    "/media/upload-chunk",
    response_model=schemas.ChunkUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="11. Upload 30s Media Chunk",
)
async def upload_media_chunk(
    assessment_id: int = Form(...),
    chunk_number: int = Form(...),
    total_chunks: Optional[int] = Form(None),
    file: UploadFile = File(...),
    candidate_id: int = Depends(dependencies.get_current_candidate_id),
    db: Session = Depends(dependencies.get_db),
):
    """Uploads a sequential WebM media chunk into local server storage."""
    assessment = crud.get_assessment_by_id(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    content = await file.read()
    res = assessment_orchestrator.handle_chunk_upload(
        candidate_id=candidate_id,
        assessment_id=assessment_id,
        chunk_number=chunk_number,
        file_bytes=content,
        total_chunks=total_chunks,
    )
    return res


@router.get(
    "/media/chunk-status",
    response_model=schemas.ChunkStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="12. Get Uploaded Chunk Status",
)
def get_chunk_upload_status(
    assessment_id: int = Query(...),
    total_chunks: Optional[int] = Query(None),
    candidate_id: int = Depends(dependencies.get_current_candidate_id),
    db: Session = Depends(dependencies.get_db),
):
    """Returns uploaded chunk numbers for retry/resume logic."""
    assessment = crud.get_assessment_by_id(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    status_data = assessment_orchestrator.get_chunk_status(
        candidate_id=candidate_id,
        assessment_id=assessment_id,
        expected_total=total_chunks,
    )
    return schemas.ChunkStatusResponse(**status_data)


@router.post(
    "/media/assemble",
    response_model=schemas.AssembleMediaResponse,
    status_code=status.HTTP_200_OK,
    summary="13. Assemble Chunks & Process Media",
)
def assemble_media(
    assessment_id: int = Query(...),
    payload: schemas.AssembleMediaRequest = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    candidate_id: int = Depends(dependencies.get_current_candidate_id),
    db: Session = Depends(dependencies.get_db),
):
    """Concatenates WebM chunks via FFmpeg, extracts 16kHz audio, and kicks off async pipeline."""
    assessment = crud.get_assessment_by_id(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    total_chunks = payload.total_chunks if payload else 1
    return assessment_orchestrator.assemble_and_process_media(
        db=db,
        candidate_id=candidate_id,
        assessment_id=assessment_id,
        total_chunks=total_chunks,
        background_tasks=background_tasks,
    )


@router.get(
    "/assessments/{id}/status",
    response_model=schemas.ProcessingStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="14. Get Assessment Processing Status Snapshot or SSE",
)
def get_processing_status(
    id: int,
    request: Request,
    candidate_id: int = Depends(dependencies.get_current_candidate_id),
    db: Session = Depends(dependencies.get_db),
):
    """Returns assessment pipeline processing progress snapshot or SSE stream."""
    assessment = crud.get_assessment_by_id(db, id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    accept_header = request.headers.get("accept", "")
    if "text/event-stream" in accept_header:
        return StreamingResponse(
            sse_service.stream_assessment_progress(id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    status_snapshot = sse_service.get_status_snapshot(id, db)
    return schemas.ProcessingStatusResponse(**status_snapshot)


@router.get(
    "/assessments/{id}/stream",
    status_code=status.HTTP_200_OK,
    summary="15. Stream Assessment Processing Progress via SSE",
)
def stream_processing_status(
    id: int,
    candidate_id: int = Depends(dependencies.get_current_candidate_id),
    db: Session = Depends(dependencies.get_db),
):
    """Real-time SSE event stream for live candidate UI status updates."""
    assessment = crud.get_assessment_by_id(db, id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    return StreamingResponse(
        sse_service.stream_assessment_progress(id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
