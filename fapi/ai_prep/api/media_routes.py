import os
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException, Request, status
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.utils.auth_dependencies import get_current_user
from fapi.ai_prep.dependencies import get_assessment_or_403, get_candidate_id_for_user
from fapi.ai_prep.models import AssessmentStatusEnum, AiPrepAssessmentORM
from fapi.ai_prep.schemas import (
    ChunkUploadResponse,
    ChunksStatusResponse,
    AssembleMediaRequest,
    AssembleMediaResponse,
    MediaFileOut,
)
from fapi.ai_prep.services.media_service import MediaService, MissingChunksException
from fapi.ai_prep.crud.media import get_media_by_assessment_id

logger = logging.getLogger("wbl.ai_prep.api.media")
router = APIRouter(prefix="/media", tags=["AIPrep Media"])


@router.post("/upload-chunk", response_model=ChunkUploadResponse, status_code=status.HTTP_200_OK)
async def upload_chunk(
    assessment_id: int = Form(...),
    chunk_number: int = Form(...),
    total_chunks: int = Form(-1),
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Uploads a single 30-second WebM media chunk.
    Enforces candidate ownership and validates assessment status is TESTING or IN_PROGRESS.
    Overwrites chunk cleanly if retried.
    """
    assessment = await get_assessment_or_403(assessment_id, current_user, db)

    # Validate assessment state
    if assessment.status not in [AssessmentStatusEnum.TESTING, AssessmentStatusEnum.IN_PROGRESS]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot upload chunk for assessment in status {assessment.status.value}"
        )

    if chunk_number < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="chunk_number must be non-negative (0-indexed)"
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded chunk file is empty"
        )

    media_service = MediaService()
    try:
        result = media_service.upload_chunk(
            candidate_id=assessment.candidate_id,
            assessment_id=assessment_id,
            chunk_number=chunk_number,
            file_bytes=file_bytes
        )
        return ChunkUploadResponse(
            chunk_number=result["chunk_number"],
            storage_path=result["storage_path"]
        )
    except Exception as exc:
        logger.error("Failed to upload chunk %d for assessment %d: %s", chunk_number, assessment_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store chunk: {str(exc)}"
        )


@router.get("/{assessment_id}/chunks-status", response_model=ChunksStatusResponse)
async def get_chunks_status(
    assessment_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns received chunk numbers, highest chunk received, and missing gap indices
    to allow the client to resume interrupted recordings without losing progress.
    """
    assessment = await get_assessment_or_403(assessment_id, current_user, db)
    media_service = MediaService()
    status_data = media_service.get_chunks_status(
        candidate_id=assessment.candidate_id,
        assessment_id=assessment_id
    )
    return ChunksStatusResponse(**status_data)


@router.post("/assemble", response_model=AssembleMediaResponse, status_code=status.HTTP_202_ACCEPTED)
async def assemble_media(
    request_data: AssembleMediaRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Assembles uploaded 30s WebM chunks into full.webm, extracts 16kHz audio.wav,
    transitions status to PROCESSING, and dispatches the Celery ML pipeline + async YouTube upload task.
    """
    assessment = await get_assessment_or_403(request_data.assessment_id, current_user, db)

    # Validate assessment state
    if assessment.status not in [AssessmentStatusEnum.TESTING, AssessmentStatusEnum.IN_PROGRESS]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot assemble media for assessment in status {assessment.status.value}"
        )

    media_service = MediaService()
    try:
        result = media_service.assemble_chunks(
            candidate_id=assessment.candidate_id,
            assessment_id=request_data.assessment_id,
            total_chunks=request_data.total_chunks,
            db=db
        )
        return AssembleMediaResponse(
            assessment_id=result["assessment_id"],
            status=result["status"],
            task_id=result.get("task_id")
        )
    except MissingChunksException as missing_err:
        logger.warning("Missing chunks during assembly for assessment %d: %s", request_data.assessment_id, missing_err.missing_chunks)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": str(missing_err),
                "missing_chunks": missing_err.missing_chunks
            }
        )
    except ValueError as val_err:
        logger.warning("Assembly validation error for assessment %d: %s", request_data.assessment_id, val_err)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as exc:
        logger.error("Assembly failed for assessment %d: %s", request_data.assessment_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Assembly processing failed: {str(exc)}"
        )


@router.get("/{assessment_id}", response_model=MediaFileOut)
async def get_media_details(
    assessment_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves media metadata and access URLs (YouTube embed or signed local stream) for an assessment.
    """
    await get_assessment_or_403(assessment_id, current_user, db)
    media = get_media_by_assessment_id(db, assessment_id)
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No media recorded for assessment {assessment_id}"
        )

    media_service = MediaService()
    video_url = media_service.get_signed_url(media.video_file_path)
    audio_url = media_service.get_signed_url(media.audio_file_path)

    is_youtube = bool(media.video_file_path and ("youtube.com" in media.video_file_path or "youtu.be" in media.video_file_path))
    youtube_id = None
    if is_youtube:
        youtube_id = media.video_file_path.split("v=")[-1].split("/")[-1].split("?")[0]

    return MediaFileOut(
        id=media.id,
        assessment_id=media.assessment_id,
        audio_file_path=media.audio_file_path,
        video_file_path=media.video_file_path,
        video_url=video_url,
        audio_url=audio_url,
        is_youtube=is_youtube,
        youtube_video_id=youtube_id,
        duration_seconds=media.duration_seconds,
        file_size_bytes=media.file_size_bytes,
        created_at=media.created_at
    )


@router.get("/stream/{assessment_id}")
async def stream_local_video(
    assessment_id: int,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Streams local server video using HTTP 206 Partial Content (Range requests) for smooth playback and seeking.
    """
    assessment = await get_assessment_or_403(assessment_id, current_user, db)
    media = get_media_by_assessment_id(db, assessment_id)
    if not media or not media.video_file_path:
        raise HTTPException(status_code=404, detail="Video file not found")

    media_service = MediaService()
    local_path = media_service.storage.get_absolute_local_path(media.video_file_path)

    if not local_path or not os.path.isfile(local_path):
        # If migrated to YouTube, redirect to YouTube watch URL
        if media.video_file_path and ("youtube.com" in media.video_file_path or "youtu.be" in media.video_file_path):
            from fastapi.responses import RedirectResponse
            return RedirectResponse(media.video_file_path)
        raise HTTPException(status_code=404, detail="Local video file not found")

    file_size = os.path.getsize(local_path)
    range_header = request.headers.get("Range")

    if range_header:
        byte1, byte2 = 0, None
        match = range_header.replace("bytes=", "").split("-")
        byte1 = int(match[0])
        if match[1]:
            byte2 = int(match[1])

        length = (byte2 - byte1 + 1) if byte2 is not None else (file_size - byte1)

        def iterfile():
            with open(local_path, "rb") as f:
                f.seek(byte1)
                yield f.read(length)

        headers = {
            "Content-Range": f"bytes {byte1}-{byte2 or (file_size - 1)}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Content-Type": "video/webm",
        }
        return StreamingResponse(iterfile(), status_code=206, headers=headers)

    def iterfile_full():
        with open(local_path, "rb") as f:
            while chunk := f.read(64 * 1024):
                yield chunk

    return StreamingResponse(
        iterfile_full(),
        headers={"Content-Length": str(file_size), "Content-Type": "video/webm"}
    )


@router.delete("/candidate/{candidate_id}")
async def delete_candidate_media(
    candidate_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Purges all media files for a candidate (local files + remote YouTube unlisted videos)
    for GDPR/CCPA compliance and data deletion requests.
    """
    resolved_cid = get_candidate_id_for_user(current_user, db)
    is_admin = getattr(current_user, "is_admin", False) or getattr(current_user, "role", "") == "admin"

    if not is_admin and resolved_cid != candidate_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete media for another candidate"
        )

    media_service = MediaService()
    result = media_service.delete_all_media(candidate_id, db)
    return {
        "status": "success",
        "detail": f"Purged media for candidate {candidate_id}",
        **result
    }


@router.post("/cleanup-expired")
async def trigger_cleanup_expired_media(
    retention_days: int = 90,
    orphan_chunk_hours: int = 24,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Admin-gated endpoint to manually trigger the 90-day retention cleanup
    and purge orphaned chunks older than 24 hours.
    """
    is_admin = getattr(current_user, "is_admin", False) or getattr(current_user, "role", "") == "admin"
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can trigger storage retention cleanup"
        )

    media_service = MediaService()
    result = media_service.cleanup_expired_media(
        retention_days=retention_days,
        orphan_chunk_hours=orphan_chunk_hours,
        db=db
    )
    return result
