"""
FastAPI HTTP API Router for AIPrep
==================================
Exposes the fixed 10 endpoints for AIPrep:
1. POST  /api/ai-prep/assessments
2. GET   /api/ai-prep/assessments/{id}
3. GET   /api/ai-prep/assessments
4. PATCH /api/ai-prep/assessments/{id}/status
5. POST  /api/ai-prep/media/upload-chunk
6. GET   /api/ai-prep/media/chunks-status/{assessment_id}
7. POST  /api/ai-prep/media/assemble
8. GET   /api/ai-prep/assessments/{id}/processing-status
9. PATCH /api/ai-prep/assessments/{id}/media
10. GET  /api/ai-prep/assessments/{id}/report

Zero DB queries directly in router — all database calls go through crud.py / assessment_orchestrator.
"""
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.ai_prep import crud
from fapi.ai_prep.dependencies import get_current_candidate_id
from fapi.ai_prep.orchestrator.assessment_orchestrator import assessment_orchestrator
from fapi.ai_prep.services.sse_service import sse_service
from fapi.ai_prep.schemas import (
    CreateAssessmentRequest,
    AssessmentResponse,
    AssessmentListResponse,
    UpdateAssessmentStatusRequest,
    UpdateAssessmentMediaRequest,
    ChunkUploadResponse,
    ChunksStatusResponse,
    AssembleMediaRequest,
    AssembleMediaResponse,
    ProcessingStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai-prep", tags=["AIPrep"])


# =====================================================================
# 1. Assessment Lifecycle Endpoints
# =====================================================================
@router.post("/assessments", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
def create_assessment(
    request: Request,
    payload: CreateAssessmentRequest,
    candidate_id: int = Depends(get_current_candidate_id),
    db: Session = Depends(get_db),
):
    """Creates/initializes a new assessment session."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    assessment = assessment_orchestrator.start_assessment(
        db=db,
        candidate_id=candidate_id,
        payload=payload,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return assessment


@router.get("/assessments/{assessment_id}", response_model=AssessmentResponse)
def get_assessment(
    assessment_id: int,
    candidate_id: int = Depends(get_current_candidate_id),
    db: Session = Depends(get_db),
):
    """Fetches single assessment session details."""
    assessment = crud.get_assessment_by_id_and_candidate(db, assessment_id, candidate_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment


@router.get("/assessments", response_model=AssessmentListResponse)
def list_assessments(
    limit: int = 50,
    offset: int = 0,
    candidate_id: int = Depends(get_current_candidate_id),
    db: Session = Depends(get_db),
):
    """Lists all assessment practice attempts for the authenticated candidate."""
    items = crud.list_assessments_by_candidate(db, candidate_id, limit=limit, offset=offset)
    return AssessmentListResponse(total=len(items), items=items)


@router.patch("/assessments/{assessment_id}/status", response_model=AssessmentResponse)
def update_assessment_status(
    assessment_id: int,
    payload: UpdateAssessmentStatusRequest,
    candidate_id: int = Depends(get_current_candidate_id),
    db: Session = Depends(get_db),
):
    """Transitions assessment status."""
    assessment = crud.get_assessment_by_id_and_candidate(db, assessment_id, candidate_id)
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
@router.post("/media/upload-chunk", response_model=ChunkUploadResponse)
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
        return ChunkUploadResponse(**res)
    except Exception as e:
        logger.error("Failed to upload chunk: %s", str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/media/chunks-status/{assessment_id}", response_model=ChunksStatusResponse)
def get_chunks_status(
    assessment_id: int,
    candidate_id: int = Depends(get_current_candidate_id),
    db: Session = Depends(get_db),
):
    """Inspects stored chunks to detect uploaded and missing chunks in sequence."""
    assessment = crud.get_assessment_by_id_and_candidate(db, assessment_id, candidate_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    status_data = assessment_orchestrator.get_chunk_status(candidate_id, assessment_id)
    return ChunksStatusResponse(
        assessment_id=assessment_id,
        uploaded_chunks=status_data["uploaded_chunks"],
        missing_chunks=status_data["missing_chunks"],
        total_chunks_expected=status_data.get("total_chunks"),
        is_ready_for_assembly=status_data["is_ready_for_assembly"],
    )


@router.post("/media/assemble", response_model=AssembleMediaResponse, status_code=status.HTTP_202_ACCEPTED)
def assemble_media(
    payload: AssembleMediaRequest,
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


# =====================================================================
# 3. Processing Status & YouTube Updates (BE2)
# =====================================================================
@router.get("/assessments/{assessment_id}/processing-status")
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
    return ProcessingStatusResponse(**status_snapshot)


@router.patch("/assessments/{assessment_id}/media", response_model=AssessmentResponse)
def update_assessment_media(
    assessment_id: int,
    payload: UpdateAssessmentMediaRequest,
    candidate_id: int = Depends(get_current_candidate_id),
    db: Session = Depends(get_db),
):
    """Updates the YouTube watch URL for the assessment."""
    assessment = crud.get_assessment_by_id_and_candidate(db, assessment_id, candidate_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    updated = crud.update_assessment_media_url(db, assessment_id, payload.youtube_url)
    return updated

