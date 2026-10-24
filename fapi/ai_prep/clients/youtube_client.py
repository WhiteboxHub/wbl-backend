"""
YouTube Data API v3 Client
==========================
Handles uploading candidate assessment recordings to YouTube as Unlisted using a single YouTube account.
Works with both video recordings and audio recordings (packaged as video).
Provides proactive daily quota inspection, usage tracking, and mock fallback for test/dev environments.
Zero hardcoded keys: uses AiPrepSettings / environment variables.
"""
import os
import logging
from typing import Dict, Any, Optional

from fapi.ai_prep.config import settings
from fapi.ai_prep.clients.youtube_quota_manager import youtube_quota_manager, YouTubeQuotaManager

logger = logging.getLogger(__name__)


class YouTubeUploadError(Exception):
    """Raised when YouTube upload fails."""
    pass


class YouTubeQuotaExceededError(YouTubeUploadError):
    """Raised when YouTube daily API quota is exceeded or insufficient."""
    pass


class YouTubeClient:
    """Production YouTube Data API v3 upload client for a single configured account."""

    def __init__(self, quota_manager: Optional[YouTubeQuotaManager] = None):
        self.privacy_status = getattr(settings, "YOUTUBE_PRIVACY_STATUS", "unlisted")
        self.quota_mgr = quota_manager or youtube_quota_manager

    def _should_use_mock(self) -> bool:
        """Determines whether to bypass live Google YouTube API and return mock responses."""
        return not self.has_live_credentials() or os.getenv("ENV") == "test"

    def has_live_credentials(self) -> bool:
        """Checks if configured single YouTube account has credentials."""
        refresh_tok = getattr(settings, "YOUTUBE_REFRESH_TOKEN", None)
        client_id = getattr(settings, "YOUTUBE_CLIENT_ID", None)
        client_secret = getattr(settings, "YOUTUBE_CLIENT_SECRET", None)
        creds_file = getattr(settings, "YOUTUBE_CREDENTIALS_FILE", None)
        return bool(
            (refresh_tok and client_id and client_secret)
            or (creds_file and os.path.exists(creds_file))
        )

    def _get_credentials(self):
        """Loads and returns Google OAuth2 Credentials from file or environment settings."""
        from google.oauth2.credentials import Credentials

        creds_file = getattr(settings, "YOUTUBE_CREDENTIALS_FILE", None)
        if creds_file and os.path.exists(creds_file):
            try:
                return Credentials.from_authorized_user_file(
                    creds_file,
                    scopes=[getattr(settings, "YOUTUBE_API_SCOPE", "https://www.googleapis.com/auth/youtube.upload")],
                )
            except Exception as e:
                logger.warning("Failed to load credentials from %s: %s", creds_file, e)

        refresh_tok = getattr(settings, "YOUTUBE_REFRESH_TOKEN", None)
        client_id = getattr(settings, "YOUTUBE_CLIENT_ID", None)
        client_secret = getattr(settings, "YOUTUBE_CLIENT_SECRET", None)

        if refresh_tok and client_id and client_secret:
            return Credentials(
                None,
                refresh_token=refresh_tok,
                token_uri=getattr(settings, "YOUTUBE_TOKEN_URI", "https://oauth2.googleapis.com/token"),
                client_id=client_id,
                client_secret=client_secret,
            )

        return None

    def get_quota_status(self) -> Dict[str, Any]:
        """Returns real-time YouTube Data API quota metrics."""
        return self.quota_mgr.get_quota_status()

    def upload_unlisted_media(
        self,
        assessment_id: int,
        file_path: str,
        media_type: str = "VIDEO",
        title: Optional[str] = None,
        description: Optional[str] = None,
        quota_cost: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Uploads a video or packaged audio recording to YouTube as Unlisted.
        If live credentials are not set or in test mode, returns a deterministic mock YouTube URL without consuming quota.
        Atomically reserves daily quota before starting live upload.
        """
        if not os.path.exists(file_path):
            raise YouTubeUploadError(f"Media file not found at: {file_path}")

        default_title = f"AIPrep Assessment #{assessment_id} ({media_type.capitalize()})"
        default_desc = f"Candidate practice assessment #{assessment_id} ({media_type.capitalize()}) - Unlisted recording"
        target_title = title or default_title
        target_desc = description or default_desc

        # 1. Fast Mock / Test Check: Never touch quota in test/mock mode
        if self._should_use_mock():
            logger.info("No live YouTube credentials or test mode active. Using generated YouTube URL for assessment %s", assessment_id)
            mock_id = f"aiprep_rec_{assessment_id}"
            mock_url = f"https://youtube.com/watch?v={mock_id}"
            return {
                "video_id": mock_id,
                "youtube_url": mock_url,
                "status": self.privacy_status,
            }

        # 2. Live API Quota Reservation
        reservation_token = self.quota_mgr.reserve_quota(cost=quota_cost)
        if not reservation_token:
            status = self.quota_mgr.get_quota_status()
            logger.warning(
                "YouTube upload aborted for assessment %s: daily quota limit reached (%d/%d units used).",
                assessment_id,
                status.get("units_used", 0),
                status.get("daily_limit_units", 0),
            )
            raise YouTubeQuotaExceededError(
                f"YouTube upload quota exceeded for today ({status.get('units_used')}/{status.get('daily_limit_units')} units used). "
                f"Estimated reset at midnight Pacific Time."
            )

        try:
            res = self._upload_live_api(file_path, target_title, target_desc)
            # Commit quota reservation on success
            self.quota_mgr.commit_quota(reservation_token=reservation_token, cost=quota_cost)
            return res
        except Exception as e:
            err_str = str(e)
            if "quotaExceeded" in err_str or "dailyLimitExceeded" in err_str or "uploadLimitExceeded" in err_str:
                self.quota_mgr.mark_quota_exceeded()
                self.quota_mgr.release_quota(reservation_token, cost=quota_cost)
                logger.error("Live YouTube upload failed due to quota limit for assessment %s: %s", assessment_id, err_str)
                raise YouTubeQuotaExceededError(f"Live YouTube upload failed due to quota limit: {err_str}") from e
            # Rollback reservation on any other failure before quota is burnt
            self.quota_mgr.release_quota(reservation_token, cost=quota_cost)
            logger.error("Live YouTube upload failed for assessment %s: %s", assessment_id, err_str)
            raise YouTubeUploadError(f"Live YouTube upload failed: {err_str}") from e

    def _upload_live_api(
        self,
        file_path: str,
        title: str,
        description: str,
    ) -> Dict[str, Any]:
        """Executes actual Google YouTube Data API v3 upload using OAuth credentials."""
        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            creds = self._get_credentials()
            if not creds:
                raise YouTubeUploadError("No valid YouTube OAuth credentials configured.")

            category_id = str(getattr(settings, "YOUTUBE_CATEGORY_ID", "27"))
            default_tags = list(getattr(settings, "AIPREP_YOUTUBE_DEFAULT_TAGS", ["AIPrep", "WhiteboxLearning", "PracticeAssessment"]))
            upload_chunk_size = int(getattr(settings, "YOUTUBE_UPLOAD_CHUNK_SIZE_BYTES", 5 * 1024 * 1024))

            youtube = build("youtube", "v3", credentials=creds)
            body = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": default_tags,
                    "categoryId": category_id,
                },
                "status": {
                    "privacyStatus": self.privacy_status,
                    "selfDeclaredMadeForKids": False,
                },
            }

            mimetype = "video/webm" if file_path.endswith(".webm") else "video/mp4"
            media = MediaFileUpload(
                file_path,
                chunksize=upload_chunk_size,
                resumable=True,
                mimetype=mimetype,
            )

            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.info("YouTube Upload Progress: %d%%", int(status.progress() * 100))

            video_id = response.get("id")
            youtube_url = f"https://youtube.com/watch?v={video_id}"
            logger.info("Successfully uploaded unlisted video to YouTube: %s", youtube_url)
            return {
                "video_id": video_id,
                "youtube_url": youtube_url,
                "status": self.privacy_status,
            }
        except ImportError:
            raise YouTubeUploadError("google-api-python-client is not installed on server.")
        except Exception as e:
            raise e

    def delete_video(self, video_id: str) -> bool:
        """Deletes a video from YouTube (GDPR/retention compliance)."""
        if not video_id or self._should_use_mock():
            return False

        try:
            from googleapiclient.discovery import build

            creds = self._get_credentials()
            if not creds:
                return False

            youtube = build("youtube", "v3", credentials=creds)
            youtube.videos().delete(id=video_id).execute()
            logger.info("Deleted YouTube video %s successfully", video_id)
            return True
        except Exception as e:
            logger.warning("Failed to delete YouTube video %s: %s", video_id, str(e))
            return False


youtube_client = YouTubeClient()

