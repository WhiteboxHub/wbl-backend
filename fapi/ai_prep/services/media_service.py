"""
AIPrep Media Service
====================
Coordinates:
- Storage operations (chunks, assembly, audio extraction)
- YouTube unlisted upload workflow with local storage cleanup
- Background media processing & evaluation pipeline
- GDPR media purges
"""
import os
import uuid
import logging
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from fapi.db.database import SessionLocal
from fapi.ai_prep import crud
from fapi.ai_prep.services.storage_service import storage_service
from fapi.ai_prep.services.youtube_service import youtube_service
from fapi.ai_prep.models import AiPrepAssessment, AiPrepMediaFile, AssessmentStatusEnum, AnalysisRunStatusEnum
from fapi.ai_prep.exceptions import AssessmentNotFoundError, MediaAssemblyError, AllYouTubeQuotasExhaustedError

logger = logging.getLogger(__name__)


class MediaService:
    """Business logic orchestrator for candidate media pipeline."""

    def __init__(self):
        self.storage = storage_service
        self.youtube = youtube_service

    def upload_chunk(
        self,
        candidate_id: int,
        assessment_id: int,
        chunk_number: int,
        file_bytes: bytes,
        total_chunks: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Saves a chunk to disk."""
        chunk_path, file_size = self.storage.save_chunk(
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

    def get_chunk_status(
        self,
        candidate_id: int,
        assessment_id: int,
        expected_total: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Returns uploaded and missing chunks for resume tracking."""
        return self.storage.get_chunk_status(
            candidate_id=candidate_id,
            assessment_id=assessment_id,
            expected_total=expected_total,
        )

    def assemble_and_extract_audio(
        self,
        candidate_id: int,
        assessment_id: int,
        total_chunks: int,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Assembles all uploaded chunks into full.webm, extracts audio.wav,
        records media file in database, and updates assessment status to EVALUATING.
        """
        # 1. Sequential concatenation of all chunks
        assembled_video_path = self.storage.assemble_chunks(
            candidate_id=candidate_id,
            assessment_id=assessment_id,
            total_chunks=total_chunks,
        )

        # 2. Extract 16kHz mono audio.wav
        audio_path = self.storage.extract_audio(assembled_video_path)

        # 3. Record in database
        file_size = os.path.getsize(assembled_video_path) if os.path.exists(assembled_video_path) else 0
        media_record = db.query(AiPrepMediaFile).filter(AiPrepMediaFile.assessment_id == assessment_id).first()
        if not media_record:
            media_record = AiPrepMediaFile(
                assessment_id=assessment_id,
                audio_file_path=audio_path,
                video_file_path=assembled_video_path,
                file_size_bytes=file_size,
            )
            db.add(media_record)
        else:
            media_record.audio_file_path = audio_path
            media_record.video_file_path = assembled_video_path
            media_record.file_size_bytes = file_size

        # 4. Update assessment status to EVALUATING
        assessment = db.query(AiPrepAssessment).filter(AiPrepAssessment.id == assessment_id).first()
        if assessment:
            assessment.status = AssessmentStatusEnum.EVALUATING.value

        db.commit()

        task_id = f"bg_{uuid.uuid4().hex[:12]}"

        return {
            "assessment_id": assessment_id,
            "status": AssessmentStatusEnum.PROCESSING.value,
            "task_id": task_id,
            "video_path": assembled_video_path,
            "audio_path": audio_path,
            "file_size_bytes": file_size,
            "message": "Media assembled and evaluation pipeline dispatched",
        }

    def execute_youtube_upload_and_cleanup(
        self,
        assessment_id: int,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Uploads assembled video to YouTube as Unlisted, sets youtube_url in DB,
        and deletes local full.webm from server storage.
        """
        assessment = db.query(AiPrepAssessment).filter(AiPrepAssessment.id == assessment_id).first()
        if not assessment:
            raise AssessmentNotFoundError(f"Assessment {assessment_id} not found")

        video_path = self.storage.get_assembled_video_path(assessment.candidate_id, assessment_id)
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Assembled video file not found at: {video_path}")

        # Upload to YouTube
        upload_result = self.youtube.upload_video(
            video_path=video_path,
            title=f"AIPrep Assessment #{assessment_id}",
            description=f"Candidate {assessment.candidate_id} Practice Assessment",
            assessment_id=assessment_id,
        )

        youtube_url = upload_result["youtube_url"]

        # Save YouTube URL to assessment record
        assessment.youtube_url = youtube_url
        db.commit()
        db.refresh(assessment)

        # Delete local server file
        self.storage.delete_local_file(video_path)
        logger.info("Deleted local server video file after YouTube upload for assessment %s", assessment_id)

        return {
            "assessment_id": assessment_id,
            "youtube_url": youtube_url,
            "video_id": upload_result.get("video_id"),
            "local_file_deleted": True,
        }

    def process_assessment_background(self, assessment_id: int) -> Dict[str, Any]:
        """
        Executes asynchronous media processing chain natively:
        YouTube Unlisted Upload -> Local Storage Cleanup -> Finalize Assessment Status.
        Designed to run directly via FastAPI BackgroundTasks.
        """
        logger.info("Starting background assessment processing for assessment %s", assessment_id)
        db = SessionLocal()
        run = crud.create_analysis_run(
            db=db,
            assessment_id=assessment_id,
            run_type="YOUTUBE_UPLOAD",
            status=AnalysisRunStatusEnum.RUNNING.value,
        )

        try:
            result = self.execute_youtube_upload_and_cleanup(assessment_id, db)
            crud.update_analysis_run_status(db, run.id, AnalysisRunStatusEnum.COMPLETED.value)

            # Mark assessment as COMPLETED
            assessment = db.query(AiPrepAssessment).filter(AiPrepAssessment.id == assessment_id).first()
            if assessment:
                assessment.status = AssessmentStatusEnum.COMPLETED.value
                db.commit()

            logger.info("Successfully completed background processing for assessment %s", assessment_id)
            return {"assessment_id": assessment_id, "status": "COMPLETED", "result": result}
        except AllYouTubeQuotasExhaustedError as quota_exc:
            msg = f"All YouTube account quotas exhausted. Upload queued until quota reset: {str(quota_exc)}"
            logger.warning("Assessment %s: %s", assessment_id, msg)
            crud.update_analysis_run_status(db, run.id, AnalysisRunStatusEnum.PENDING.value, error_message=msg)
            return {"assessment_id": assessment_id, "status": "PENDING", "error": msg}
        except Exception as exc:
            error_msg = f"Background media pipeline error: {str(exc)}"
            logger.error("Failed background processing for assessment %s: %s", assessment_id, error_msg)
            crud.update_analysis_run_status(db, run.id, AnalysisRunStatusEnum.FAILED.value, error_message=error_msg)
            assessment = db.query(AiPrepAssessment).filter(AiPrepAssessment.id == assessment_id).first()
            if assessment:
                assessment.status = AssessmentStatusEnum.FAILED.value
                db.commit()
            return {"assessment_id": assessment_id, "status": "FAILED", "error": error_msg}
        finally:
            db.close()

    def cleanup_abandoned_chunks(self) -> Dict[str, Any]:
        """Cleans up abandoned chunk directories older than configured TTL."""
        deleted_count = self.storage.cleanup_abandoned_chunks()
        logger.info("Cleaned up %d abandoned chunk directories", deleted_count)
        return {"deleted_directories": deleted_count}

    def purge_all_media_for_candidate(self, candidate_id: int, db: Session) -> bool:
        """Purges local folders and deletes YouTube recordings for candidate."""
        # Find all candidate assessments with youtube URLs
        assessments = db.query(AiPrepAssessment).filter(AiPrepAssessment.candidate_id == candidate_id).all()
        for ass in assessments:
            if ass.youtube_url and "watch?v=" in ass.youtube_url:
                vid_id = ass.youtube_url.split("watch?v=")[-1]
                self.youtube.delete_video(vid_id)

        # Purge local filesystem
        return self.storage.purge_candidate_data_gdpr(candidate_id)


media_service = MediaService()
