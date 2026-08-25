import os
import tempfile
import logging
from typing import Dict, Any

from fapi.ai_prep.workers.celery_app import celery_app
from fapi.ai_prep.models import RunTypeEnum, RunStatusEnum
from fapi.ai_prep.crud.runs import create_analysis_run, update_analysis_run_status
from fapi.ai_prep.crud.media import get_media_by_assessment_id, update_video_file_path
from fapi.ai_prep.services.storage_service import get_storage_service
from fapi.ai_prep.services.youtube_service import get_youtube_service, YouTubeQuotaExceededException
from fapi.db.database import SessionLocal

logger = logging.getLogger("wbl.ai_prep.workers.youtube")


@celery_app.task(bind=True, max_retries=5, queue="ai_prep")
def upload_video_to_youtube_task(self, assessment_id: int):
    """
    Celery task that uploads the assembled assessment video (full.webm) to YouTube
    as Unlisted, updates the database record with the YouTube URL, and deletes
    the heavy local full.webm and chunks to reclaim server disk space.
    """
    logger.info("Starting YouTube upload task for assessment %s (Retry #%d)", assessment_id, getattr(self.request, "retries", 0))
    db = SessionLocal()
    run = create_analysis_run(db, assessment_id, RunTypeEnum.YOUTUBE_UPLOAD, celery_task_id=getattr(self.request, "id", None))

    temp_download = None
    try:
        media = get_media_by_assessment_id(db, assessment_id)
        if not media or not media.video_file_path:
            raise FileNotFoundError(f"No media or video file recorded for assessment {assessment_id}")

        # Check if already uploaded to YouTube
        if "youtube.com" in media.video_file_path or "youtu.be" in media.video_file_path:
            logger.info("Video for assessment %s is already on YouTube: %s", assessment_id, media.video_file_path)
            update_analysis_run_status(db, run.id, RunStatusEnum.COMPLETED)
            return {"status": "already_uploaded", "youtube_url": media.video_file_path}

        storage = get_storage_service()
        local_path = storage.get_absolute_local_path(media.video_file_path)

        if not local_path or not os.path.isfile(local_path):
            temp_download = tempfile.NamedTemporaryFile(suffix=".webm", delete=False).name
            storage.download_to_file(media.video_file_path, temp_download)
            local_path = temp_download

        youtube = get_youtube_service()
        title = f"AIPrep_Assessment_Session_{assessment_id}"
        description = "Whitebox Learning AIPrep Automated Practice Recording (Unlisted)"

        original_staging_path = media.video_file_path

        # Upload to YouTube as Unlisted
        video_id = youtube.upload_video(
            file_path=local_path,
            title=title,
            description=description,
            privacy_status="unlisted"
        )
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"

        # Update database with YouTube URL
        update_video_file_path(db, assessment_id, youtube_url)
        logger.info("Updated assessment %s media record with YouTube URL: %s", assessment_id, youtube_url)

        # -------------------------------------------------------------
        # LOCAL DISK AUTO-CLEANUP: Reclaim disk space on server
        # -------------------------------------------------------------
        try:
            # 1. Delete original local full.webm
            if original_staging_path:
                storage.delete_file(original_staging_path)
                logger.info("Deleted staging video %s from server disk", original_staging_path)

            # 2. Delete raw 30s chunk files
            candidate_id = media.assessment.candidate_id if hasattr(media, "assessment") and media.assessment else None
            if candidate_id is None and original_staging_path:
                parts = original_staging_path.split("/")
                if len(parts) >= 3 and parts[0] == "ai-prep":
                    candidate_id = parts[1]

            if candidate_id is not None:
                chunks_prefix = f"ai-prep/{candidate_id}/{assessment_id}/chunks"
                deleted_chunks = storage.delete_prefix(chunks_prefix)
                logger.info("Deleted %d raw chunks from server disk for assessment %s", deleted_chunks, assessment_id)
        except Exception as cleanup_err:
            logger.warning("Local storage cleanup encountered non-fatal error: %s", cleanup_err)

        if temp_download and os.path.exists(temp_download):
            os.remove(temp_download)

        update_analysis_run_status(db, run.id, RunStatusEnum.COMPLETED)
        return {
            "status": "completed",
            "youtube_video_id": video_id,
            "youtube_url": youtube_url
        }

    except YouTubeQuotaExceededException as quota_exc:
        retries = getattr(self.request, "retries", 0)
        error_msg = f"YouTube daily quota exceeded: {quota_exc}"
        logger.warning(error_msg)
        if retries >= 5:
            logger.warning("YouTube quota retry limit (5) reached for assessment %s. Retaining local video fallback.", assessment_id)
            update_analysis_run_status(db, run.id, RunStatusEnum.COMPLETED, error_message="Local fallback retained due to YouTube quota limits")
            return {"status": "local_fallback", "detail": "Local video retained"}

        update_analysis_run_status(db, run.id, RunStatusEnum.QUEUED, error_message=error_msg)
        # Retry with 1-hour backoff countdown
        raise self.retry(exc=quota_exc, countdown=3600, max_retries=5)

    except Exception as exc:
        retries = getattr(self.request, "retries", 0)
        error_msg = f"YouTube upload worker failed: {exc}"
        logger.error(error_msg, exc_info=True)
        if retries >= 5:
            update_analysis_run_status(db, run.id, RunStatusEnum.FAILED, error_message=error_msg)
            return {"status": "failed", "detail": error_msg}

        countdown = min(300, (2 ** retries) * 15)
        update_analysis_run_status(db, run.id, RunStatusEnum.QUEUED, error_message=error_msg)
        raise self.retry(exc=exc, countdown=countdown, max_retries=5)

    finally:
        db.close()
