"""
YouTube API Integration Service (BE2 Production)
================================================
Handles:
- Uploading assembled assessment videos to YouTube as Unlisted
- Generating YouTube watch URLs
- Deleting videos on YouTube (for GDPR requests)
- Strict error raising (zero mock/simulation fallbacks in production)
"""
import os
import logging
from typing import Dict, Any, Optional

from fapi.ai_prep.config import settings
from fapi.ai_prep.exceptions import YouTubeUploadError
from fapi.ai_prep.clients.youtube_client import youtube_client

logger = logging.getLogger(__name__)


class YouTubeService:
    """Manages YouTube video uploads (unlisted) and deletion."""

    def __init__(self, client=None):
        self.client = client or youtube_client

    def has_live_credentials(self) -> bool:
        """Checks if live YouTube credentials are configured."""
        return self.client.has_live_credentials()

    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str = "AIPrep Assessment Practice Session",
        privacy_status: Optional[str] = None,
        assessment_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Uploads an assessment recording to YouTube as Unlisted.
        Returns video ID and watch URL.
        Raises YouTubeUploadError on failure.
        """
        return self.client.upload_video_unlisted(
            file_path=video_path,
            title=title,
            description=description,
        )

    def delete_video(self, video_id: str) -> bool:
        """Deletes a video from YouTube (for GDPR compliance)."""
        return self.client.delete_video(video_id)


youtube_service = YouTubeService()

