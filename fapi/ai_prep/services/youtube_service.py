import os
import logging
from typing import Optional, List
from fapi.ai_prep.config import (
    YOUTUBE_UPLOAD_ENABLED,
    YOUTUBE_CLIENT_ID,
    YOUTUBE_CLIENT_SECRET,
    YOUTUBE_REFRESH_TOKEN,
    YOUTUBE_PRIVACY_STATUS,
    YOUTUBE_CATEGORY_ID,
)

logger = logging.getLogger("wbl.ai_prep.youtube")


class YouTubeQuotaExceededException(Exception):
    """Raised when YouTube API returns 403 quotaExceeded, allowing Celery retry with backoff."""
    pass


class YouTubeService:
    """
    Service adapter for uploading and managing unlisted assessment videos via YouTube Data API v3.
    """

    def __init__(
        self,
        client_id: Optional[str] = YOUTUBE_CLIENT_ID,
        client_secret: Optional[str] = YOUTUBE_CLIENT_SECRET,
        refresh_token: Optional[str] = YOUTUBE_REFRESH_TOKEN,
        privacy_status: str = YOUTUBE_PRIVACY_STATUS,
        category_id: str = YOUTUBE_CATEGORY_ID,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.privacy_status = privacy_status
        self.category_id = category_id
        self._client = None

    def is_configured(self) -> bool:
        """Returns True if YouTube OAuth credentials are configured."""
        return bool(self.client_id and self.client_secret and self.refresh_token)

    def _get_client(self):
        """Initializes and returns the authenticated YouTube Data API client."""
        if self._client is not None:
            return self._client

        if not self.is_configured():
            logger.info("YouTube OAuth credentials not fully configured; operating in mock mode.")
            return None

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            credentials = Credentials(
                token=None,
                refresh_token=self.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]
            )
            self._client = build("youtube", "v3", credentials=credentials, cache_discovery=False)
            return self._client
        except Exception as e:
            logger.error("Failed to build YouTube Data API client: %s", e)
            raise

    def upload_video(
        self,
        file_path: str,
        title: str,
        description: str,
        privacy_status: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """
        Uploads a video file to YouTube as unlisted using resumable upload.
        Returns the YouTube video ID string (e.g. 'dQw4w9WgXcQ').
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Video file to upload not found: {file_path}")

        status_privacy = privacy_status or self.privacy_status
        client = self._get_client()

        if client is None:
            # Mock mode fallback for local test/dev environments without API keys
            import hashlib
            file_hash = hashlib.md5(f"{file_path}_{os.path.getsize(file_path)}".encode()).hexdigest()[:11]
            mock_video_id = f"yt_{file_hash}"
            logger.info("[Mock YouTube Service] Uploaded %s as Unlisted -> Video ID: %s", file_path, mock_video_id)
            return mock_video_id

        try:
            from googleapiclient.http import MediaFileUpload
            from googleapiclient.errors import HttpError

            body = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": tags or ["AIPrep", "PracticeSession"],
                    "categoryId": self.category_id,
                },
                "status": {
                    "privacyStatus": status_privacy,
                    "selfDeclaredMadeForKids": False,
                    "embeddable": True,
                    "publicStatsViewable": False,
                }
            }

            # Resumable upload in 4MB chunks
            media = MediaFileUpload(
                file_path,
                mimetype="video/webm",
                chunksize=4 * 1024 * 1024,
                resumable=True
            )

            request = client.videos().insert(part="snippet,status", body=body, media_body=media)
            response = None

            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.debug("YouTube upload progress: %d%%", int(status.progress() * 100))

            video_id = response.get("id")
            logger.info("Successfully uploaded video to YouTube: https://youtu.be/%s", video_id)
            return video_id

        except Exception as exc:
            err_str = str(exc).lower()
            if "quotaexceeded" in err_str or "403" in err_str:
                logger.error("YouTube API daily quota exceeded: %s", exc)
                raise YouTubeQuotaExceededException(f"YouTube daily upload quota exceeded: {exc}") from exc
            logger.error("YouTube video upload failed: %s", exc)
            raise

    def delete_video(self, youtube_video_id: str) -> bool:
        """
        Deletes a video from YouTube by video ID for GDPR/CCPA compliance or retention expiry.
        """
        if not youtube_video_id:
            return False

        # Extract ID if a full URL was provided
        if "youtube.com" in youtube_video_id or "youtu.be" in youtube_video_id:
            youtube_video_id = youtube_video_id.split("v=")[-1].split("/")[-1].split("?")[0]

        client = self._get_client()
        if client is None:
            logger.info("[Mock YouTube Service] Deleted YouTube video %s", youtube_video_id)
            return True

        try:
            client.videos().delete(id=youtube_video_id).execute()
            logger.info("Deleted video %s from YouTube", youtube_video_id)
            return True
        except Exception as exc:
            logger.error("Failed to delete YouTube video %s: %s", youtube_video_id, exc)
            return False


# Singleton instance
_youtube_instance: Optional[YouTubeService] = None


def get_youtube_service() -> YouTubeService:
    """Returns singleton YouTube service adapter instance."""
    global _youtube_instance
    if _youtube_instance is None:
        _youtube_instance = YouTubeService()
    return _youtube_instance
