"""
Central Hub Assessment Orchestrator Layer
=========================================
Coordinates Database (crud.py) <-> Storage Service <-> YouTube Client <-> Media Service.
Maintains stateful media ingestion, server-side assembly, and async task dispatch.
"""
import os
import uuid
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks

from fapi.ai_prep import crud
from fapi.ai_prep.models import AiPrepAssessment, AssessmentStatusEnum
from fapi.ai_prep.schemas import CreateAssessmentRequest, AssembleMediaResponse
from fapi.ai_prep.services.storage_service import storage_service
from fapi.ai_prep.services.youtube_service import youtube_service
from fapi.ai_prep.services.media_service import media_service
from fapi.ai_prep.clients.youtube_client import youtube_client

logger = logging.getLogger(__name__)


class AssessmentOrchestrator:
    """Central Hub Coordinator for AIPrep."""

    def __init__(
        self,
        storage_svc=None,
        yt_client=None,
        media_svc=None,
    ):
        self.storage_service = storage_svc or storage_service
        self.youtube_client = yt_client or youtube_client
        self.media_service = media_svc or media_service

    # ------------------------------------------------------------------
    # 1. Assessment Lifecycle Coordination
    # ------------------------------------------------------------------
    def start_assessment(
        self,
        db: Session,
        candidate_id: int,
        payload: CreateAssessmentRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AiPrepAssessment:
        """Coordinates assessment initialization and device check recording."""
        logger.info("Starting assessment for candidate %s, type: %s", candidate_id, payload.assessment_type)
        assessment = crud.create_assessment(
            db=db,
            candidate_id=candidate_id,
            obj_in=payload,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return assessment

    def transition_status(
        self,
        db: Session,
        assessment_id: int,
        target_status: str,
    ) -> AiPrepAssessment:
        """Updates assessment status."""
        assessment = crud.get_assessment(db, assessment_id)
        if not assessment:
            raise ValueError(f"Assessment {assessment_id} not found")

        updated = crud.update_assessment_status(db, assessment_id, target_status)
        return updated

    # ------------------------------------------------------------------
    # 2. Media Ingestion & Chunk Coordination (BE2)
    # ------------------------------------------------------------------
    def handle_chunk_upload(
        self,
        candidate_id: int,
        assessment_id: int,
        chunk_number: int,
        file_bytes: bytes,
        total_chunks: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Saves media chunk to local server storage."""
        chunk_path, file_size = self.storage_service.save_chunk(
            candidate_id=candidate_id,
            assessment_id=assessment_id,
            chunk_number=chunk_number,
            file_bytes=file_bytes,
        )
        return {
            "chunk_number": chunk_number,
            "status": "uploaded",
            "storage_path": chunk_path,
            "total_chunks": total_chunks,
        }

    def get_chunk_status(self, candidate_id: int, assessment_id: int, expected_total: Optional[int] = None) -> Dict[str, Any]:
        """Returns uploaded and missing chunk numbers for resume/retry logic."""
        return self.storage_service.get_chunk_status(candidate_id, assessment_id, expected_total=expected_total)

    # ------------------------------------------------------------------
    # 3. Server Assembly, Audio Extraction & Task Chain Dispatch (BE2)
    # ------------------------------------------------------------------
    def assemble_and_process_media(
        self,
        db: Session,
        candidate_id: int,
        assessment_id: int,
        total_chunks: int,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> AssembleMediaResponse:
        """
        Coordinates full server-side media assembly:
        1. Validate all chunks exist and assemble full.webm
        2. Extract 16kHz mono audio.wav
        3. Create operational media record in DB
        4. Transition assessment status to EVALUATING / PROCESSING
        5. Dispatch background processing task (via BackgroundTasks or direct execution)
        """
        logger.info("Assembling media for assessment %s (total chunks: %d)", assessment_id, total_chunks)
        video_path = self.storage_service.assemble_chunks(candidate_id, assessment_id, total_chunks)
        audio_path = self.storage_service.extract_audio(video_path)
        file_size = os.path.getsize(video_path) if os.path.exists(video_path) else 0

        # Record operational media record
        crud.create_media_file(
            db=db,
            assessment_id=assessment_id,
            audio_file_path=audio_path,
            video_file_path=video_path,
            file_size_bytes=file_size,
        )

        # Transition status to EVALUATING
        crud.update_assessment_status(db, assessment_id, AssessmentStatusEnum.EVALUATING.value)

        task_id = f"bg_{uuid.uuid4().hex[:12]}"

        # Dispatch background pipeline
        if background_tasks is not None:
            background_tasks.add_task(self.media_service.process_assessment_background, assessment_id)
        else:
            # Direct execution fallback for testing/synchronous contexts
            self.media_service.process_assessment_background(assessment_id)

        return AssembleMediaResponse(
            assessment_id=assessment_id,
            status="PROCESSING",
            task_id=task_id,
            message="Media assembled and evaluation pipeline dispatched",
        )

    # ------------------------------------------------------------------
    # 4. YouTube Upload & Local Storage Cleanup (BE2)
    # ------------------------------------------------------------------
    def upload_to_youtube_and_cleanup(self, db: Session, assessment_id: int) -> Dict[str, Any]:
        """
        Coordinates YouTube Unlisted video upload and deletes local video file from server disk.
        """
        assessment = crud.get_assessment(db, assessment_id)
        if not assessment:
            raise ValueError(f"Assessment {assessment_id} not found")

        video_path = self.storage_service.get_assembled_video_path(assessment.candidate_id, assessment_id)
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Assembled video file not found at: {video_path}")

        # Upload as Unlisted via YouTube Client
        upload_res = self.youtube_client.upload_video_unlisted(
            file_path=video_path,
            title=f"AIPrep Assessment #{assessment_id}",
            description=f"Candidate {assessment.candidate_id} Mock Assessment Response (Unlisted)",
        )
        youtube_url = upload_res["youtube_url"]

        # Update database with YouTube URL
        crud.update_assessment_media_url(db, assessment_id, youtube_url)

        # Delete local video from server disk storage
        self.storage_service.delete_local_file(video_path)
        logger.info("Deleted local server video after YouTube upload for assessment %s", assessment_id)

        return {
            "assessment_id": assessment_id,
            "youtube_url": youtube_url,
            "local_file_deleted": True,
        }


assessment_orchestrator = AssessmentOrchestrator()
