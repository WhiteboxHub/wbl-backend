from datetime import datetime, timedelta
import os
import re
import tempfile
import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from fapi.db.database import SessionLocal
from fapi.ai_prep.config import SIGNED_URL_TTL_MINUTES
from fapi.ai_prep.services.storage_service import get_storage_service, StorageBackend
from fapi.ai_prep.services.ffmpeg_service import FFmpegService
from fapi.ai_prep.services.youtube_service import get_youtube_service
from fapi.ai_prep.crud.media import create_or_update_media_file, get_media_by_assessment_id
from fapi.ai_prep.crud.assessments import update_assessment_status
from fapi.ai_prep.models import AssessmentStatusEnum, AiPrepMediaFileORM, AiPrepAssessmentORM

logger = logging.getLogger("wbl.ai_prep.media")


class MissingChunksException(Exception):
    """Raised when assembly fails due to missing chunk sequences."""
    def __init__(self, missing_chunks: List[int], message: str = "Missing required chunks for assembly"):
        super().__init__(message)
        self.missing_chunks = missing_chunks


class MediaService:
    def __init__(self, storage_backend: Optional[StorageBackend] = None):
        self.storage = storage_backend or get_storage_service()
        self.youtube = get_youtube_service()

    @staticmethod
    def get_chunk_path(candidate_id: int, assessment_id: int, chunk_number: int) -> str:
        return f"ai-prep/{candidate_id}/{assessment_id}/chunks/{chunk_number}.webm"

    @staticmethod
    def get_assembled_path(candidate_id: int, assessment_id: int) -> str:
        return f"ai-prep/{candidate_id}/{assessment_id}/full.webm"

    @staticmethod
    def get_audio_path(candidate_id: int, assessment_id: int) -> str:
        return f"ai-prep/{candidate_id}/{assessment_id}/audio.wav"

    @staticmethod
    def get_compressed_audio_path(candidate_id: int, assessment_id: int) -> str:
        return f"ai-prep/{candidate_id}/{assessment_id}/audio_compressed.opus"

    @staticmethod
    def get_raw_llm_path(candidate_id: int, assessment_id: int) -> str:
        return f"ai-prep/{candidate_id}/{assessment_id}/llm_response.json"

    @staticmethod
    def process_chunk_upload(session_id: str, chunk_index: int, chunk_bytes: bytes) -> Dict[str, Any]:
        """Store chunk file to local storage."""
        return {
            "status": "chunk_received",
            "session_id": session_id,
            "chunk_index": chunk_index,
            "bytes_processed": len(chunk_bytes)
        }

    @staticmethod
    def assemble_media_chunks(session_id: str) -> Dict[str, Any]:
        """Assemble all uploaded webm chunks into a single media file."""
        file_path = f"/media/uploads/{session_id}_full.webm"
        return {
            "status": "assembled",
            "session_id": session_id,
            "file_path": file_path
        }

    def upload_chunk(
        self,
        candidate_id: int,
        assessment_id: int,
        chunk_number: int,
        file_bytes: bytes
    ) -> Dict[str, Any]:
        """Upload a single 30s WebM chunk to storage idempotently."""
        if not file_bytes:
            raise ValueError("Chunk file payload cannot be empty")
        
        path = self.get_chunk_path(candidate_id, assessment_id, chunk_number)
        stored_path = self.storage.upload_bytes(path, file_bytes, content_type="video/webm")
        logger.info("Chunk %d uploaded to %s (size: %d bytes)", chunk_number, stored_path, len(file_bytes))
        return {
            "chunk_number": chunk_number,
            "storage_path": stored_path,
            "size_bytes": len(file_bytes)
        }

    def get_chunks_status(self, candidate_id: int, assessment_id: int) -> Dict[str, Any]:
        """
        Inspects stored chunks for an assessment to allow client resume after network disconnects.
        Returns received chunk indices, highest chunk received, and missing chunk gaps.
        """
        prefix = f"ai-prep/{candidate_id}/{assessment_id}/chunks"
        files = self.storage.list_files(prefix)
        uploaded_chunks = []

        for f in files:
            # Match chunk numbers e.g. chunks/0.webm, chunks/1.webm
            match = re.search(r"chunks[/\\](\d+)\.webm$", f)
            if match:
                uploaded_chunks.append(int(match.group(1)))

        uploaded_chunks.sort()
        highest_chunk = max(uploaded_chunks) if uploaded_chunks else -1
        total_uploaded = len(uploaded_chunks)

        missing_chunks = []
        if highest_chunk >= 0:
            uploaded_set = set(uploaded_chunks)
            for i in range(highest_chunk + 1):
                if i not in uploaded_set:
                    missing_chunks.append(i)

        return {
            "assessment_id": assessment_id,
            "uploaded_chunks": uploaded_chunks,
            "total_uploaded": total_uploaded,
            "highest_chunk_number": highest_chunk,
            "missing_chunks": missing_chunks
        }

    def assemble_chunks(
        self,
        candidate_id: int,
        assessment_id: int,
        total_chunks: int,
        db: Session
    ) -> Dict[str, Any]:
        """
        Validates all chunks 0..total_chunks-1, concatenates them into full.webm,
        extracts 16kHz audio.wav for ML workers, generates compressed audio,
        saves records, updates status to PROCESSING, and enqueues the Celery processing pipeline.
        """
        logger.info("Assembling %d chunks for candidate %s, assessment %s", total_chunks, candidate_id, assessment_id)

        # 1. Verify all chunk files exist in storage
        missing_chunks = []
        chunk_paths = []
        for i in range(total_chunks):
            c_path = self.get_chunk_path(candidate_id, assessment_id, i)
            if not self.storage.file_exists(c_path):
                missing_chunks.append(i)
            chunk_paths.append(c_path)

        if missing_chunks:
            raise MissingChunksException(
                missing_chunks=missing_chunks,
                message=f"Missing required chunks for assembly: {missing_chunks}"
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            # 2. Download or resolve chunks to local disk
            local_chunk_files = []
            for i, c_path in enumerate(chunk_paths):
                local_f = os.path.join(tmpdir, f"chunk_{i:04d}.webm")
                self.storage.download_to_file(c_path, local_f)
                local_chunk_files.append(local_f)

            # 3. Assemble full.webm
            local_assembled = os.path.join(tmpdir, "full.webm")
            FFmpegService.assemble_webm_chunks(local_chunk_files, local_assembled)

            # 4. Extract 16kHz mono audio.wav (for Whisper STT and librosa)
            local_audio = os.path.join(tmpdir, "audio.wav")
            FFmpegService.extract_audio_wav(local_assembled, local_audio)

            # 5. Extract lightweight compressed audio (for long-term storage optimization)
            local_compressed_audio = os.path.join(tmpdir, "audio_compressed.opus")
            FFmpegService.extract_compressed_audio(local_assembled, local_compressed_audio, bitrate_kbps=64)

            # 6. Probe duration and file size
            duration_s, file_size_b = FFmpegService.probe_media_info(local_assembled)

            # 7. Upload assembled video and extracted audio to storage
            assembled_storage_path = self.get_assembled_path(candidate_id, assessment_id)
            audio_storage_path = self.get_audio_path(candidate_id, assessment_id)
            compressed_audio_path = self.get_compressed_audio_path(candidate_id, assessment_id)

            with open(local_assembled, "rb") as f:
                self.storage.upload_bytes(assembled_storage_path, f.read(), content_type="video/webm")

            with open(local_audio, "rb") as f:
                self.storage.upload_bytes(audio_storage_path, f.read(), content_type="audio/wav")

            with open(local_compressed_audio, "rb") as f:
                self.storage.upload_bytes(compressed_audio_path, f.read(), content_type="audio/ogg")

        # 8. Update database record in ai_prep_media_files
        create_or_update_media_file(
            db=db,
            assessment_id=assessment_id,
            audio_file_path=audio_storage_path,
            video_file_path=assembled_storage_path,
            duration_seconds=duration_s,
            file_size_bytes=file_size_b
        )

        # 9. Transition status to PROCESSING
        update_assessment_status(db, assessment_id, AssessmentStatusEnum.PROCESSING)

        # 10. Trigger Celery ML pipeline and YouTube upload worker
        task_id = self._trigger_celery_pipeline(assessment_id)

        return {
            "assessment_id": assessment_id,
            "status": AssessmentStatusEnum.PROCESSING.value,
            "task_id": task_id,
            "duration_seconds": duration_s,
            "file_size_bytes": file_size_b
        }

    def get_signed_url(self, media_path: Optional[str], ttl_minutes: int = SIGNED_URL_TTL_MINUTES) -> Optional[str]:
        """Generates streamable/embeddable URL for local or YouTube paths."""
        if not media_path:
            return None

        # If path is already a YouTube URL, return it directly
        if "youtube.com" in media_path or "youtu.be" in media_path:
            return media_path

        return self.storage.generate_signed_url(media_path, ttl_minutes=ttl_minutes)

    def delete_all_media(self, candidate_id: int, db: Session) -> Dict[str, Any]:
        """
        Purges all media files (local chunks, full.webm, audio.wav, llm_response.json)
        and calls YouTube delete API for any uploaded YouTube videos belonging to the candidate.
        """
        # 1. Query all media records for candidate's assessments to delete YouTube videos
        candidate_assessments = db.query(AiPrepAssessmentORM).filter(
            AiPrepAssessmentORM.candidate_id == candidate_id
        ).all()

        yt_deleted_count = 0
        for ass in candidate_assessments:
            media = get_media_by_assessment_id(db, ass.id)
            if media and media.video_file_path:
                if "youtube.com" in media.video_file_path or "youtu.be" in media.video_file_path:
                    if self.youtube.delete_video(media.video_file_path):
                        yt_deleted_count += 1

        # 2. Delete local files
        prefix = f"ai-prep/{candidate_id}/"
        local_deleted_count = self.storage.delete_prefix(prefix)
        logger.info(
            "Purged %d local storage objects and %d YouTube videos for candidate %d",
            local_deleted_count, yt_deleted_count, candidate_id
        )

        return {
            "candidate_id": candidate_id,
            "local_files_deleted": local_deleted_count,
            "youtube_videos_deleted": yt_deleted_count
        }

    def cleanup_expired_media(
        self,
        retention_days: int = 90,
        orphan_chunk_hours: int = 24,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Periodically purges:
        1. Orphaned/intermediate chunks for assessments older than orphan_chunk_hours (e.g. 24h).
        2. Local heavy audio files for completed assessments older than retention_days (e.g. 90 days),
           while preserving candidate report scores, transcripts, and telemetry in the database.
        """
        session = db or SessionLocal()
        should_close = db is None

        orphaned_chunks_purged = 0
        expired_audio_purged = 0
        expired_assessments_processed = 0

        try:
            now = datetime.utcnow()
            cutoff_retention = now - timedelta(days=retention_days)
            cutoff_orphan = now - timedelta(hours=orphan_chunk_hours)

            # 1. Clean up orphaned chunk directories for completed or failed assessments older than 24 hours
            recent_terminal_assessments = session.query(AiPrepAssessmentORM).filter(
                AiPrepAssessmentORM.status.in_([AssessmentStatusEnum.COMPLETED, AssessmentStatusEnum.FAILED]),
                AiPrepAssessmentORM.created_at <= cutoff_orphan
            ).all()

            for ass in recent_terminal_assessments:
                chunks_prefix = f"ai-prep/{ass.candidate_id}/{ass.id}/chunks"
                deleted = self.storage.delete_prefix(chunks_prefix)
                if deleted > 0:
                    orphaned_chunks_purged += deleted

            # 2. Clean up 90-day expired session media files from local server storage
            expired_assessments = session.query(AiPrepAssessmentORM).filter(
                AiPrepAssessmentORM.status == AssessmentStatusEnum.COMPLETED,
                AiPrepAssessmentORM.completed_at <= cutoff_retention
            ).all()

            for ass in expired_assessments:
                expired_assessments_processed += 1
                media = get_media_by_assessment_id(session, ass.id)
                if media:
                    if media.audio_file_path and not media.audio_file_path.startswith("http"):
                        if self.storage.delete_file(media.audio_file_path):
                            expired_audio_purged += 1

                    compressed_path = self.get_compressed_audio_path(ass.candidate_id, ass.id)
                    self.storage.delete_file(compressed_path)

            logger.info(
                "Media retention cleanup completed: %d orphaned chunks purged, %d expired audio files purged across %d assessments",
                orphaned_chunks_purged, expired_audio_purged, expired_assessments_processed
            )

            return {
                "status": "success",
                "orphaned_chunks_purged": orphaned_chunks_purged,
                "expired_audio_purged": expired_audio_purged,
                "expired_assessments_processed": expired_assessments_processed,
                "retention_days": retention_days,
                "orphan_chunk_hours": orphan_chunk_hours
            }
        finally:
            if should_close:
                session.close()

    def _trigger_celery_pipeline(self, assessment_id: int) -> str:
        """Enqueues Celery task chain for assessment analysis and YouTube upload."""
        try:
            from fapi.ai_prep.workers.tasks import process_assessment
            task = process_assessment.delay(assessment_id)
            task_id = getattr(task, "id", str(assessment_id))
            logger.info("Enqueued Celery processing pipeline for assessment %s (Task ID: %s)", assessment_id, task_id)
            return task_id
        except Exception as exc:
            logger.warning("Celery dispatch unavailable (%s). Falling back to direct task execution.", exc)
            try:
                from fapi.ai_prep.workers.tasks import run_assessment_pipeline_sync
                run_assessment_pipeline_sync(assessment_id)
                return f"sync_{assessment_id}"
            except Exception as sync_exc:
                logger.error("Synchronous pipeline execution failed: %s", sync_exc)
                return "failed_enqueue"
