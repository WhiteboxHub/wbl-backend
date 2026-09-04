"""
YouTube Client Layer (BE2 Production)
=====================================
Handles:
- Resumable Unlisted video uploads via Google YouTube Data API v3
- Sequential account pool rotation (Account 1 -> Account 2 -> Account 3)
- Catching 403 Quota Exceeded and performing immediate sequential failover
- Raising AllYouTubeQuotasExhaustedError when all account quotas are exhausted
- Generating YouTube watch URLs
- Deleting videos on YouTube (for GDPR requests)
"""
import os
import logging
from typing import Dict, Any, Optional

from fapi.ai_prep.config import settings
from fapi.ai_prep.exceptions import YouTubeUploadError, AllYouTubeQuotasExhaustedError
from fapi.ai_prep.clients.youtube_account_manager import youtube_account_pool, YouTubeAccount

logger = logging.getLogger(__name__)


class YouTubeClient:
    """Production client for uploading and managing unlisted videos with sequential account pool rotation."""

    def __init__(self, pool=None):
        self.privacy_status = settings.YOUTUBE_PRIVACY_STATUS
        self.pool = pool or youtube_account_pool

    def has_live_credentials(self) -> bool:
        """Checks if any configured account in the pool has valid credentials."""
        for acc in self.pool._accounts:
            if acc.has_credentials():
                return True
        return False

    def upload_video_unlisted(
        self,
        file_path: str,
        title: str = "AIPrep Assessment",
        description: str = "Candidate practice assessment session (Unlisted)",
    ) -> Dict[str, Any]:
        """
        Uploads an assessment recording to YouTube as Unlisted using sequential account rotation.
        - Sequentially uses Account 1 until 6 videos uploaded or 403 quota exceeded.
        - Fails over to Account 2, Account 3, etc.
        - Raises AllYouTubeQuotasExhaustedError if all accounts are exhausted for today.
        """
        if not os.path.exists(file_path):
            raise YouTubeUploadError(f"Video file not found at: {file_path}")

        if not self.has_live_credentials():
            raise YouTubeUploadError("YouTube upload failed: No YouTube account credentials configured in settings.")

        # Sequential Account Failover Loop
        while True:
            account = self.pool.get_next_active_account()
            if not account:
                # All configured accounts in the pool are exhausted for today
                seconds_to_reset = self.pool.get_seconds_until_next_reset()
                total_accounts = len(self.pool._accounts)
                logger.warning(
                    "All %d YouTube account quotas exhausted. Upload deferred until reset in %d seconds.",
                    total_accounts, seconds_to_reset
                )
                raise AllYouTubeQuotasExhaustedError(
                    seconds_until_reset=seconds_to_reset,
                    total_accounts=total_accounts,
                )

            logger.info(
                "Attempting YouTube upload with account %s (%d/%d used today).",
                account.account_id, account.upload_count_today, account.daily_limit
            )

            try:
                result = self._upload_live_api(account, file_path, title, description)
                self.pool.record_successful_upload(account.account_id)
                return result
            except Exception as e:
                err_str = str(e).lower()
                is_quota_error = (
                    "quotaexceeded" in err_str or
                    "uploadlimitexceeded" in err_str or
                    "quota" in err_str or
                    "403" in err_str and "limit" in err_str
                )
                if is_quota_error:
                    logger.warning(
                        "Account %s exceeded Google YouTube upload quota. Marking exhausted and failing over sequentially. Error: %s",
                        account.account_id, str(e)
                    )
                    self.pool.mark_account_exhausted(account.account_id, reason=str(e))
                    # Continue while loop to try next account sequentially
                    continue
                else:
                    logger.error("Live YouTube upload failed for account %s: %s", account.account_id, str(e))
                    raise YouTubeUploadError(f"Live YouTube upload failed: {str(e)}")

    def _upload_live_api(self, account: YouTubeAccount, file_path: str, title: str, description: str) -> Dict[str, Any]:
        """Executes actual Google YouTube Data API v3 upload using specified account credentials."""
        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            from google.oauth2.credentials import Credentials

            creds = None
            if account.refresh_token and account.client_id and account.client_secret:
                creds = Credentials(
                    None,
                    refresh_token=account.refresh_token,
                    token_uri=settings.YOUTUBE_TOKEN_URI,
                    client_id=account.client_id,
                    client_secret=account.client_secret,
                )

            youtube = build("youtube", "v3", credentials=creds)
            body = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": ["AIPrep", "PracticeAssessment"],
                    "categoryId": "27",
                },
                "status": {
                    "privacyStatus": self.privacy_status,
                    "selfDeclaredMadeForKids": False,
                },
            }

            media = MediaFileUpload(
                file_path,
                chunksize=1024 * 1024 * 5,
                resumable=True,
                mimetype="video/webm",
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
                    logger.info(
                        "YouTube Upload Progress (Account %s): %d%%",
                        account.account_id, int(status.progress() * 100)
                    )

            video_id = response.get("id")
            youtube_url = f"https://youtube.com/watch?v={video_id}"
            logger.info("Successfully uploaded unlisted video to YouTube via account %s: %s", account.account_id, youtube_url)
            return {
                "video_id": video_id,
                "youtube_url": youtube_url,
                "status": self.privacy_status,
                "account_id": account.account_id,
            }
        except ImportError:
            raise YouTubeUploadError("google-api-python-client is not installed on server.")
        except Exception as e:
            # Propagate exception up to failover handler
            raise e

    def delete_video(self, video_id: str) -> bool:
        """Deletes a video from YouTube (GDPR compliance)."""
        if not video_id:
            return False

        logger.info("Requested deletion of YouTube video %s", video_id)
        account = self.pool.get_next_active_account()
        if not account or not account.has_credentials():
            # Try any account in pool with credentials
            account = next((acc for acc in self.pool._accounts if acc.has_credentials()), None)

        if not account:
            logger.warning("Cannot delete YouTube video %s: No live credentials configured", video_id)
            return False

        try:
            from googleapiclient.discovery import build
            from google.oauth2.credentials import Credentials

            creds = Credentials(
                None,
                refresh_token=account.refresh_token,
                token_uri=settings.YOUTUBE_TOKEN_URI,
                client_id=account.client_id,
                client_secret=account.client_secret,
            )
            youtube = build("youtube", "v3", credentials=creds)
            youtube.videos().delete(id=video_id).execute()
            logger.info("Deleted YouTube video %s successfully", video_id)
            return True
        except Exception as e:
            logger.warning("Failed to delete YouTube video %s via API: %s", video_id, str(e))
            return False


youtube_client = YouTubeClient()


