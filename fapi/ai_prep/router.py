"""
FastAPI HTTP API Router for AIPrep
==================================
Exposes endpoints for AIPrep across both /api/ai-prep and /api/aiprep prefixes.
"""
import os
import logging
from typing import Optional, List, Dict, Any
from fastapi import (
    APIRouter, Depends, HTTPException, UploadFile, File, Form,
    Request, status, BackgroundTasks, Query
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from fapi.ai_prep import crud, schemas, config
from fapi.ai_prep.dependencies import get_current_candidate_id, get_db
from fapi.ai_prep.orchestrator.assessment_orchestrator import assessment_orchestrator, AssessmentOrchestrator
from fapi.ai_prep.services.sse_service import sse_service
from fapi.ai_prep.clients.youtube_client import YouTubeClient

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AIPrep"])


# =====================================================================
# 1. Assessment Lifecycle Endpoints
# =====================================================================
@router.post("/api/ai-prep/assessments", response_model=schemas.AssessmentResponse, status_code=status.HTTP_201_CREATED)
@router.post("/api/aiprep/assessments", response_model=schemas.AssessmentResponse, status_code=status.HTTP_201_CREATED)
def create_assessment(
    payload: schemas.CreateAssessmentRequest,
    request: Request = None,
    candidate_id: int = Depends(get_current_candidate_id),
    db: Session = Depends(get_db),
):
    """Creates/initializes a new assessment session."""
    ip_address = request.client.host if (request and request.client) else None
    user_agent = request.headers.get("user-agent") if request else None

    effective_candidate_id = payload.candidate_id or candidate_id
    assessment = assessment_orchestrator.start_assessment(
        db=db,
        candidate_id=effective_candidate_id,
        payload=payload,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return assessment


@router.get("/api/ai-prep/assessments/{assessment_id}", response_model=schemas.AssessmentResponse)
@router.get("/api/aiprep/assessments/{assessment_id}", response_model=schemas.AssessmentResponse)
def get_assessment(
    assessment_id: int,
    candidate_id: int = Depends(get_current_candidate_id),
    db: Session = Depends(get_db),
):
    """Fetches single assessment session details."""
    assessment = crud.get_assessment_by_id_and_candidate(db, assessment_id, candidate_id)
    if not assessment:
        assessment = crud.get_assessment(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment


@router.get("/api/ai-prep/assessments", response_model=schemas.AssessmentListResponse)
@router.get("/api/aiprep/assessments", response_model=schemas.AssessmentListResponse)
def list_assessments(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    candidate_id: Optional[int] = Query(None),
    current_candidate_id: int = Depends(get_current_candidate_id),
    db: Session = Depends(get_db),
):
    """Lists assessment practice attempts for the candidate."""
    eff_id = candidate_id or current_candidate_id
    items = crud.list_assessments_by_candidate(db, eff_id, limit=limit, offset=offset)
    res_items = [schemas.AssessmentListItem.model_validate(i) for i in items]
    return schemas.AssessmentListResponse(total=len(res_items), items=res_items)


@router.patch("/api/ai-prep/assessments/{assessment_id}/status", response_model=schemas.AssessmentResponse)
@router.patch("/api/aiprep/assessments/{assessment_id}/status", response_model=schemas.AssessmentResponse)
def update_assessment_status(
    assessment_id: int,
    payload: schemas.UpdateAssessmentStatusRequest,
    candidate_id: int = Depends(get_current_candidate_id),
    db: Session = Depends(get_db),
):
    """Transitions assessment status."""
    assessment = crud.get_assessment(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    updated = assessment_orchestrator.transition_status(
        db=db,
        assessment_id=assessment_id,
        target_status=payload.status.value,
    )
    return updated


# =====================================================================
# 2. Media Ingestion & Chunking Endpoints (BE2)
# =====================================================================
@router.post("/api/ai-prep/media/upload-chunk", response_model=schemas.ChunkUploadResponse)
@router.post("/api/aiprep/media/upload-chunk", response_model=schemas.ChunkUploadResponse)
async def upload_media_chunk(
    assessment_id: int = Form(...),
    chunk_number: int = Form(...),
    total_chunks: Optional[int] = Form(None),
    file: UploadFile = File(...),
    candidate_id: int = Depends(get_current_candidate_id),
    db: Session = Depends(get_db),
):
    """Uploads a sequential 30s WebM media chunk into local server storage."""
    assessment = crud.get_assessment_by_id_and_candidate(db, assessment_id, candidate_id)
    if not assessment:
        assessment = crud.get_assessment(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    try:
        content = await file.read()
        res = assessment_orchestrator.handle_chunk_upload(
            candidate_id=candidate_id,
            assessment_id=assessment_id,
            chunk_number=chunk_number,
            file_bytes=content,
            total_chunks=total_chunks,
        )
        return schemas.ChunkUploadResponse(**res)
    except Exception as e:
        logger.error("Failed to upload chunk: %s", str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/ai-prep/media/chunks-status/{assessment_id}", response_model=schemas.ChunksStatusResponse)
@router.get("/api/aiprep/media/chunks-status/{assessment_id}", response_model=schemas.ChunksStatusResponse)
def get_chunks_status(
    assessment_id: int,
    candidate_id: int = Depends(get_current_candidate_id),
    db: Session = Depends(get_db),
):
    """Inspects stored chunks to detect uploaded and missing chunks in sequence."""
    assessment = crud.get_assessment_by_id_and_candidate(db, assessment_id, candidate_id)
    if not assessment:
        assessment = crud.get_assessment(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    status_data = assessment_orchestrator.get_chunk_status(candidate_id, assessment_id)
    return schemas.ChunksStatusResponse(
        assessment_id=assessment_id,
        uploaded_chunks=status_data["uploaded_chunks"],
        missing_chunks=status_data["missing_chunks"],
        total_chunks_expected=status_data.get("total_chunks"),
        is_ready_for_assembly=status_data["is_ready_for_assembly"],
    )


@router.post("/api/ai-prep/media/assemble", response_model=schemas.AssembleMediaResponse, status_code=status.HTTP_202_ACCEPTED)
@router.post("/api/aiprep/media/assemble", response_model=schemas.AssembleMediaResponse, status_code=status.HTTP_202_ACCEPTED)
def assemble_media(
    payload: schemas.AssembleMediaRequest,
    background_tasks: BackgroundTasks,
    candidate_id: int = Depends(get_current_candidate_id),
    db: Session = Depends(get_db),
):
    """
    Validates that all chunks are present, assembles full.webm,
    extracts audio.wav, updates DB, and dispatches background processing pipeline.
    """
    assessment = crud.get_assessment_by_id_and_candidate(db, payload.assessment_id, candidate_id)
    if not assessment:
        assessment = crud.get_assessment(db, payload.assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    try:
        response = assessment_orchestrator.assemble_and_process_media(
            db=db,
            candidate_id=candidate_id,
            assessment_id=payload.assessment_id,
            total_chunks=payload.total_chunks,
            background_tasks=background_tasks,
        )
        return response
    except Exception as e:
        logger.error("Failed to assemble media: %s", str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/ai-prep/assessments/{id}/upload-media", status_code=status.HTTP_200_OK)
@router.post("/api/aiprep/assessments/{id}/upload-media", status_code=status.HTTP_200_OK)
async def upload_media(
    id: int,
    file: UploadFile = File(...),
    bg_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """Saves raw recorded video/audio blob to local disk storage and triggers YouTube upload."""
    assessment = crud.get_assessment_by_id(db, id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    os.makedirs(config.settings.LOCAL_STORAGE_DIR, exist_ok=True)
    local_file_path = os.path.join(config.settings.LOCAL_STORAGE_DIR, f"{id}.webm")

    with open(local_file_path, "wb") as f:
        f.write(await file.read())

    yt_client = YouTubeClient()
    bg_tasks.add_task(yt_client.upload_unlisted_video, id, local_file_path)

    return {
        "assessment_id": id,
        "local_file_path": local_file_path,
        "upload_status": "PROCESSING_YOUTUBE",
    }


# =====================================================================
# 3. Telemetry Submission, Evaluation & Report Endpoints
# =====================================================================
@router.post("/api/ai-prep/assessments/{id}/data", status_code=status.HTTP_200_OK)
@router.post("/api/aiprep/assessments/{id}/data", status_code=status.HTTP_200_OK)
def submit_data(
    id: int,
    payload: schemas.SubmitAssessmentDataRequest,
    db: Session = Depends(get_db),
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


@router.post("/api/ai-prep/assessments/{id}/evaluate", status_code=status.HTTP_202_ACCEPTED)
@router.post("/api/aiprep/assessments/{id}/evaluate", status_code=status.HTTP_202_ACCEPTED)
def trigger_evaluation(
    id: int,
    bg_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Changes assessment status to EVALUATING and triggers the Central Orchestrator."""
    assessment = crud.get_assessment_by_id(db, id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    crud.update_assessment_status(db, id, schemas.AssessmentStatusEnum.EVALUATING)
    orchestrator = AssessmentOrchestrator()
    bg_tasks.add_task(orchestrator.process_assessment_evaluation, id)

    return {"id": id, "status": schemas.AssessmentStatusEnum.EVALUATING}


@router.get("/api/ai-prep/assessments/{assessment_id}/processing-status")
@router.get("/api/aiprep/assessments/{assessment_id}/processing-status")
def get_processing_status(
    assessment_id: int,
    request: Request,
    candidate_id: int = Depends(get_current_candidate_id),
    db: Session = Depends(get_db),
):
    """
    Returns real-time processing status.
    If 'Accept: text/event-stream' header is present, returns an SSE stream.
    Otherwise returns a single JSON snapshot.
    """
    assessment = crud.get_assessment_by_id_and_candidate(db, assessment_id, candidate_id)
    if not assessment:
        assessment = crud.get_assessment(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    accept_header = request.headers.get("accept", "")
    if "text/event-stream" in accept_header:
        return StreamingResponse(
            sse_service.stream_assessment_progress(assessment_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    status_snapshot = sse_service.get_status_snapshot(assessment_id, db)
    return schemas.ProcessingStatusResponse(**status_snapshot)


@router.patch("/api/ai-prep/assessments/{assessment_id}/media", response_model=schemas.AssessmentResponse)
@router.patch("/api/aiprep/assessments/{assessment_id}/media", response_model=schemas.AssessmentResponse)
def update_assessment_media(
    assessment_id: int,
    payload: schemas.UpdateAssessmentMediaRequest,
    candidate_id: int = Depends(get_current_candidate_id),
    db: Session = Depends(get_db),
):
    """Updates the YouTube watch URL for the assessment."""
    assessment = crud.get_assessment_by_id_and_candidate(db, assessment_id, candidate_id)
    if not assessment:
        assessment = crud.get_assessment(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    updated = crud.update_assessment_media_url(db, assessment_id, payload.youtube_url)
    return updated


@router.get("/api/ai-prep/assessments/{assessment_id}/report")
@router.get("/api/aiprep/assessments/{assessment_id}/report")
def get_assessment_report_view(
    assessment_id: int,
    candidate_id: int = Depends(get_current_candidate_id),
    db: Session = Depends(get_db),
):
    """Fetches assessment evaluation report."""
    assessment = crud.get_assessment_by_id_and_candidate(db, assessment_id, candidate_id)
    if not assessment:
        assessment = crud.get_assessment(db, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    data = crud.get_assessment_data(db, assessment_id)
    report = crud.get_assessment_report(db, assessment_id)

    return {
        "id": assessment.id,
        "candidate_id": assessment.candidate_id,
        "assessment_type": assessment.assessment_type,
        "media_type": getattr(assessment, "media_type", "VIDEO"),
        "status": assessment.status,
        "youtube_url": assessment.youtube_url,
        "data": {
            "questions": getattr(data, "questions", None) if data else None,
            "transcript": getattr(data, "transcript", None) if data else None,
            "audio_telemetry": getattr(data, "audio_telemetry", None) if data else None,
            "video_telemetry": getattr(data, "video_telemetry", None) if data else None,
        },
        "report": {
            "audio_evaluation": getattr(report, "audio_evaluation", None) if report else None,
            "video_evaluation": getattr(report, "video_evaluation", None) if report else None,
            "transcript_evaluation": getattr(report, "transcript_evaluation", None) if report else None,
        } if report else None,
    }


# =====================================================================
# 4. Question Bank Endpoints
# =====================================================================
@router.get("/api/ai-prep/questions", response_model=schemas.QuestionListResponse, status_code=status.HTTP_200_OK)
@router.get("/api/aiprep/questions", response_model=schemas.QuestionListResponse, status_code=status.HTTP_200_OK)
def list_questions(
    category: Optional[schemas.AssessmentCategoryEnum] = None,
    difficulty_level: Optional[schemas.DifficultyLevelEnum] = None,
    is_active: Optional[bool] = True,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
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


@router.post("/api/ai-prep/questions", response_model=schemas.QuestionBankResponse, status_code=status.HTTP_201_CREATED)
@router.post("/api/aiprep/questions", response_model=schemas.QuestionBankResponse, status_code=status.HTTP_201_CREATED)
def create_question(
    payload: schemas.QuestionBankCreateRequest,
    db: Session = Depends(get_db),
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


@router.patch("/api/ai-prep/questions/{id}", response_model=schemas.QuestionBankResponse, status_code=status.HTTP_200_OK)
@router.patch("/api/aiprep/questions/{id}", response_model=schemas.QuestionBankResponse, status_code=status.HTTP_200_OK)
def update_question(
    id: int,
    payload: schemas.QuestionBankUpdateRequest,
    db: Session = Depends(get_db),
):
    """Updates fields on an existing question."""
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
