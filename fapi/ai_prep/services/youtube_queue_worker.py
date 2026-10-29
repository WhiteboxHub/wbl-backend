"""
YouTube Queue Worker Service
============================
Hybrid FIFO Queue and Automated Quota-Reset Ingestion Engine for AI Prep media.

Key Features:
1. First-Come, First-Served (FIFO) queue ordering by assessment creation time/ID.
2. Dual Trigger Mechanism:
   - Immediate Event: Attempt upload upon assessment completion if quota is available.
   - Scheduled Background Trigger: Periodically drains the queue (and automatically upon daily quota reset).
3. Graceful Quota Handling: If YouTube API daily limits (10,000 units / ~6 uploads) are reached,
   media remains safely preserved on server disk for instant candidate playback without failing assessments.
4. Strict Privacy & Consent: Skips assessments where save_recording consent was denied.
"""

import asyncio
import logging
import os
import shutil
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from fapi.ai_prep.config import settings
from fapi.ai_prep.models import AiPrepAssessmentORM
from fapi.ai_prep.clients.youtube_client import youtube_client, YouTubeQuotaExceededError
from fapi.ai_prep.clients.youtube_quota_manager import youtube_quota_manager
from fapi.ai_prep.core.video_processor_engine import VideoProcessorEngine
from fapi.db.database import SessionLocal

logger = logging.getLogger(__name__)

STORAGE_BASE_DIR = getattr(
    settings,
    "LOCAL_MEDIA_STORAGE_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage"),
)


def get_pending_youtube_uploads(
    db: Session,
    limit: Optional[int] = None,
) -> List[AiPrepAssessmentORM]:
    """
    Retrieves pending assessments awaiting YouTube upload in strict FIFO order (oldest first).
    Only includes assessments where recording consent was granted.
    """
    query = (
        db.query(AiPrepAssessmentORM)
        .filter(
            AiPrepAssessmentORM.status.in_(["COMPLETED", "EVALUATING"]),
            AiPrepAssessmentORM.youtube_url.is_(None),
        )
        .order_by(AiPrepAssessmentORM.id.asc())  # Strict FIFO: oldest assessment first
    )

    all_pending = query.all()
    valid_pending: List[AiPrepAssessmentORM] = []

    for assessment in all_pending:
        consent = assessment.consent or {}
        # Skip if candidate explicitly opted out of saving recording
        if consent.get("save_recording") is False:
            continue
        valid_pending.append(assessment)
        if limit and len(valid_pending) >= limit:
            break

    return valid_pending


def get_youtube_queue_status(db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Returns current queue health, pending video count, and YouTube daily quota status.
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        quota_status = youtube_quota_manager.get_quota_status()
        pending = get_pending_youtube_uploads(db)
        
        return {
            "queue_length": len(pending),
            "can_upload_now": quota_status.get("can_upload", True),
            "quota_units_used": quota_status.get("units_used", 0),
            "quota_units_remaining": quota_status.get("units_remaining", 10000),
            "daily_limit_units": quota_status.get("daily_limit_units", 10000),
            "estimated_uploads_remaining_today": max(0, quota_status.get("units_remaining", 10000) // 1600),
            "oldest_pending_assessment_id": pending[0].id if pending else None,
            "pending_assessment_ids": [a.id for a in pending[:20]],
        }
    finally:
        if should_close:
            db.close()


def find_assessment_media_for_youtube(candidate_id: int, assessment_id: int) -> Optional[str]:
    """
    Finds existing media file on disk for an assessment, converting audio to video if needed.
    """
    assessment_dir = os.path.join(STORAGE_BASE_DIR, str(candidate_id), str(assessment_id))
    if not os.path.exists(assessment_dir):
        return None

    # Priority 1: Ready-to-upload YouTube MP4
    yt_mp4 = os.path.join(assessment_dir, "audio_youtube.mp4")
    if os.path.exists(yt_mp4) and os.path.getsize(yt_mp4) > 0:
        return yt_mp4

    # Priority 2: Assembled or raw video file
    for vname in ("assembled.webm", "recording.webm", "video.mp4", "media.webm"):
        vpath = os.path.join(assessment_dir, vname)
        if os.path.exists(vpath) and os.path.getsize(vpath) > 0:
            return vpath

    # Priority 3: Raw audio file (convert for YouTube)
    for aname in ("audio.webm", "audio.wav", "audio.mp3", "audio.ogg"):
        apath = os.path.join(assessment_dir, aname)
        if os.path.exists(apath) and os.path.getsize(apath) > 0:
            try:
                converted = VideoProcessorEngine.convert_audio_for_youtube(apath)
                if converted and os.path.exists(converted):
                    return converted
            except Exception as conv_err:
                logger.warning(
                    "Could not convert audio for YouTube for assessment %s: %s",
                    assessment_id,
                    conv_err,
                )

    return None


def drain_youtube_queue(
    db: Optional[Session] = None,
    max_uploads: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Drains the pending YouTube queue in strict FIFO order until daily quota limit is reached.
    Thread-safe and resilient.
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    uploaded_count = 0
    failed_count = 0
    skipped_count = 0
    quota_exhausted = False

    try:
        if not youtube_quota_manager.has_sufficient_quota():
            logger.info("[YouTubeQueueWorker] Daily quota limit reached. Queue drain deferred.")
            return {
                "status": "QUOTA_EXHAUSTED",
                "uploaded_count": 0,
                "pending_count": len(get_pending_youtube_uploads(db)),
                "message": "Daily YouTube API quota exhausted. Retrying after midnight Pacific Time rollover.",
            }

        pending = get_pending_youtube_uploads(db, limit=max_uploads)
        logger.info("[YouTubeQueueWorker] Starting FIFO queue drain. Pending assessments: %d", len(pending))

        for assessment in pending:
            # Check quota before each candidate upload
            if not youtube_quota_manager.has_sufficient_quota():
                logger.info(
                    "[YouTubeQueueWorker] Quota exhausted mid-drain. Stopped at assessment %s.",
                    assessment.id,
                )
                quota_exhausted = True
                break

            media_file = find_assessment_media_for_youtube(assessment.candidate_id, assessment.id)
            if not media_file:
                logger.warning(
                    "[YouTubeQueueWorker] No media found on disk for assessment %s. Skipping.",
                    assessment.id,
                )
                skipped_count += 1
                continue

            try:
                logger.info(
                    "[YouTubeQueueWorker] Uploading assessment %s (candidate: %s) to YouTube in FIFO order...",
                    assessment.id,
                    assessment.candidate_id,
                )
                res = youtube_client.upload_unlisted_media(
                    assessment_id=assessment.id,
                    file_path=media_file,
                    media_type=str(assessment.media_type or "VIDEO"),
                )
                yt_url = res.get("youtube_url")
                if yt_url:
                    assessment.youtube_url = yt_url
                    db.commit()
                    uploaded_count += 1
                    logger.info(
                        "[YouTubeQueueWorker] Successfully uploaded assessment %s: %s",
                        assessment.id,
                        yt_url,
                    )

                    # Storage purge: 5-minute grace period before purging to allow active candidate viewers to finish watching
                    if getattr(settings, "CLEANUP_STORAGE_AFTER_UPLOAD", True):
                        assessment_dir = os.path.join(
                            STORAGE_BASE_DIR, str(assessment.candidate_id), str(assessment.id)
                        )
                        if os.path.exists(assessment_dir):
                            import threading
                            import time
                            def _delayed_worker_purge(target_dir: str, a_id: int):
                                try:
                                    time.sleep(300)  # 5-minute grace period
                                    if os.path.exists(target_dir):
                                        shutil.rmtree(target_dir, ignore_errors=True)
                                        logger.info("[YouTubeQueueWorker] Purged server storage for assessment %s after 5-minute grace period", a_id)
                                except Exception as w_err:
                                    logger.warning("[YouTubeQueueWorker] Delayed purge error for %s: %s", a_id, w_err)

                            threading.Thread(target=_delayed_worker_purge, args=(assessment_dir, assessment.id), daemon=True).start()
                            logger.info("[YouTubeQueueWorker] Scheduled 5-minute delayed purge for assessment %s", assessment.id)
            except YouTubeQuotaExceededError as q_err:
                logger.warning(
                    "[YouTubeQueueWorker] Quota exceeded while uploading assessment %s: %s",
                    assessment.id,
                    q_err,
                )
                quota_exhausted = True
                break
            except Exception as upload_err:
                logger.error(
                    "[YouTubeQueueWorker] Failed to upload assessment %s to YouTube: %s",
                    assessment.id,
                    upload_err,
                )
                failed_count += 1

        remaining = len(get_pending_youtube_uploads(db))
        return {
            "status": "QUOTA_EXHAUSTED" if quota_exhausted else "SUCCESS",
            "uploaded_count": uploaded_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "remaining_count": remaining,
        }
    finally:
        if should_close:
            db.close()


def run_scheduled_youtube_queue_job() -> None:
    """Scheduled task invoked by APScheduler to process the YouTube queue."""
    logger.info("[YouTubeQueueScheduler] Checking YouTube upload queue...")
    try:
        result = drain_youtube_queue()
        logger.info("[YouTubeQueueScheduler] Queue run complete: %s", result)
    except Exception as exc:
        logger.error("[YouTubeQueueScheduler] Error running YouTube queue worker: %s", exc, exc_info=True)
