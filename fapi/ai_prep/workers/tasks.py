import logging
try:
    from celery import chain
except ImportError:
    chain = None

from fapi.ai_prep.workers.celery_app import celery_app
from fapi.ai_prep.workers.stt_worker import stt_task
from fapi.ai_prep.workers.audio_worker import audio_analysis_task
from fapi.ai_prep.workers.vision_worker import vision_task
from fapi.ai_prep.workers.llm_worker import llm_analysis_task
from fapi.ai_prep.workers.youtube_worker import upload_video_to_youtube_task
from fapi.ai_prep.workers.finalize_worker import finalize_task
from fapi.ai_prep.services.media_service import MediaService

logger = logging.getLogger("wbl.ai_prep.workers.tasks")


@celery_app.task(bind=True, max_retries=3, queue="ai_prep")
def process_assessment(self, assessment_id: int):
    """
    Main Celery entry point triggered after media chunk assembly.
    Orchestrates the 5-step ML pipeline chain and dispatches the async YouTube upload worker.
    """
    logger.info("Triggering assessment processing pipeline for assessment %s", assessment_id)
    try:
        if chain is None:
            raise ImportError("Celery library not installed")
        ml_pipeline = chain(
            stt_task.si(assessment_id),
            audio_analysis_task.si(assessment_id),
            vision_task.si(assessment_id),
            llm_analysis_task.si(assessment_id),
            finalize_task.si(assessment_id),
        )
        ml_pipeline.apply_async()

        # Enqueue YouTube upload in parallel
        upload_video_to_youtube_task.delay(assessment_id)
        return {"assessment_id": assessment_id, "status": "PIPELINE_ENQUEUED"}

    except Exception as exc:
        logger.warning("Celery chain dispatch failed (%s). Executing synchronous runner.", exc)
        return run_assessment_pipeline_sync(assessment_id)


@celery_app.task(bind=True, max_retries=3, queue="ai_prep")
def cleanup_expired_media_task(self, retention_days: int = 90, orphan_chunk_hours: int = 24):
    """
    Celery periodic maintenance task running nightly to purge orphaned chunks
    and 90-day expired session media files from server storage.
    """
    logger.info("Starting periodic media lifecycle cleanup (Retention: %d days, Orphan: %d hours)", retention_days, orphan_chunk_hours)
    media_service = MediaService()
    result = media_service.cleanup_expired_media(
        retention_days=retention_days,
        orphan_chunk_hours=orphan_chunk_hours
    )
    logger.info("Periodic media cleanup completed: %s", result)
    return result


def run_assessment_pipeline_sync(assessment_id: int):
    """
    Synchronous fallback execution runner for unit tests or offline environments.
    Executes STT -> Audio -> Vision -> LLM -> YouTube -> Finalize.
    """
    logger.info("Executing synchronous assessment processing pipeline for %s", assessment_id)
    stt_task(assessment_id)
    audio_analysis_task(assessment_id)
    vision_task(assessment_id)
    llm_analysis_task(assessment_id)
    try:
        upload_video_to_youtube_task(assessment_id)
    except Exception as yt_err:
        logger.warning("Synchronous YouTube upload encountered non-fatal error: %s", yt_err)
    finalize_task(assessment_id)
    return {"assessment_id": assessment_id, "status": "COMPLETED"}
