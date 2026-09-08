"""
YouTube Upload Pre-Flight Inspector (BE2 Core Engine)
=====================================================
Performs essential pre-flight verification before YouTube Data API v3 upload:
- Confirms assembled video file exists, is non-empty, and has valid container headers
- Validates and sanitizes YouTube upload metadata (Title, Description, Privacy)
- Prevents wasting daily quota units (1,600 units/upload) on invalid media files
"""
import os
import logging
from typing import Dict, Any, Optional
from fapi.ai_prep.core.video_processor_engine.config import (
    MAX_YOUTUBE_TITLE_LENGTH,
    MAX_YOUTUBE_DESC_LENGTH,
)
from fapi.ai_prep.core.video_processor_engine.media_verifier import verify_assembled_video

logger = logging.getLogger(__name__)


def inspect_youtube_upload_readiness(
    video_path: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    assessment_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Executes comprehensive pre-flight inspection prior to executing YouTube upload.

    :param video_path: Path to video file on local disk.
    :param title: Target YouTube video title.
    :param description: Target YouTube video description.
    :param assessment_id: Optional assessment identifier for metadata fallback.
    :return: Pre-flight validation report.
    """
    # 1. Inspect media file integrity
    media_check = verify_assembled_video(video_path)
    if not media_check["is_valid"]:
        logger.warning(
            "YouTube upload preflight failed for '%s': %s",
            video_path,
            media_check.get("error"),
        )
        return {
            "ready_for_upload": False,
            "video_path": video_path,
            "file_size_bytes": media_check.get("file_size_bytes", 0),
            "media_check": media_check,
            "sanitized_title": None,
            "sanitized_description": None,
            "error": f"Preflight media check failed: {media_check.get('error')}",
        }

    # 2. Sanitize and validate title
    default_title = f"AIPrep Assessment #{assessment_id}" if assessment_id else "AIPrep Assessment Video"
    clean_title = (title.strip() if title else default_title)[:MAX_YOUTUBE_TITLE_LENGTH]

    # 3. Sanitize description
    clean_desc = (description.strip() if description else "")[:MAX_YOUTUBE_DESC_LENGTH]

    return {
        "ready_for_upload": True,
        "video_path": video_path,
        "file_size_bytes": media_check["file_size_bytes"],
        "media_check": media_check,
        "sanitized_title": clean_title,
        "sanitized_description": clean_desc,
        "error": None,
    }
