"""
YouTube Upload Pre-Flight Inspector
====================================
Performs essential pre-flight verification before YouTube Data API v3 upload:
- Confirms media file exists, is non-empty, and has valid container headers
- Validates and sanitizes YouTube upload metadata (Title, Description, Privacy)
- Prevents wasting daily API quota on invalid media files
"""
import os
import logging
from typing import Dict, Any, Optional
from fapi.ai_prep.core.video_processor_engine.config import (
    MAX_YOUTUBE_TITLE_LENGTH,
    MAX_YOUTUBE_DESC_LENGTH,
)
from fapi.ai_prep.core.video_processor_engine.media_verifier import (
    verify_assembled_video,
    verify_audio_file,
)

logger = logging.getLogger(__name__)


def inspect_youtube_upload_readiness(
    media_path: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    assessment_id: Optional[int] = None,
    media_type: str = "VIDEO",
) -> Dict[str, Any]:
    """
    Executes comprehensive pre-flight inspection prior to executing YouTube upload.

    :param media_path: Path to video or audio file on local disk.
    :param title: Target YouTube video title.
    :param description: Target YouTube video description.
    :param assessment_id: Optional assessment identifier for metadata fallback.
    :param media_type: "VIDEO" or "AUDIO".
    :return: Pre-flight validation report.
    """
    if not os.path.exists(media_path):
        return {
            "ready_for_upload": False,
            "media_path": media_path,
            "file_size_bytes": 0,
            "sanitized_title": None,
            "sanitized_description": None,
            "error": f"Media file not found at: {media_path}",
        }

    # 1. Inspect media file integrity
    if media_type.upper() == "AUDIO":
        media_check = verify_audio_file(media_path)
    else:
        media_check = verify_assembled_video(media_path)

    if not media_check.get("is_valid"):
        logger.warning(
            "YouTube upload preflight failed for '%s': %s",
            media_path,
            media_check.get("error"),
        )
        return {
            "ready_for_upload": False,
            "media_path": media_path,
            "file_size_bytes": media_check.get("file_size_bytes", 0),
            "media_check": media_check,
            "sanitized_title": None,
            "sanitized_description": None,
            "error": f"Preflight media check failed: {media_check.get('error')}",
        }

    # 2. Sanitize and validate title
    default_title = (
        f"AIPrep Assessment #{assessment_id} ({media_type.capitalize()})"
        if assessment_id
        else f"AIPrep Assessment Recording ({media_type.capitalize()})"
    )
    clean_title = (title.strip() if title else default_title)[:MAX_YOUTUBE_TITLE_LENGTH]

    # 3. Sanitize description
    clean_desc = (description.strip() if description else "")[:MAX_YOUTUBE_DESC_LENGTH]

    # 4. Check Quota Readiness
    quota_status = None
    try:
        from fapi.ai_prep.clients.youtube_quota_manager import youtube_quota_manager
        quota_status = youtube_quota_manager.get_quota_status()
    except Exception as q_err:
        logger.warning("Could not fetch YouTube quota status during preflight: %s", q_err)

    is_quota_ready = quota_status.get("can_upload", True) if quota_status else True

    return {
        "ready_for_upload": is_quota_ready,
        "media_path": media_path,
        "file_size_bytes": media_check["file_size_bytes"],
        "media_check": media_check,
        "sanitized_title": clean_title,
        "sanitized_description": clean_desc,
        "quota_status": quota_status,
        "error": None if is_quota_ready else "YouTube daily API upload quota is exceeded or insufficient",
    }
