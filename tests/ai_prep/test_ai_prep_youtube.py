"""
Unit Tests for AIPrep YouTube Integration Service & Client
==========================================================
Tests:
- Unlisted video upload with API mock
- YouTube watch URL generation
- YouTube upload and immediate local disk cleanup
- GDPR YouTube deletion
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from fapi.ai_prep.services.youtube_service import youtube_service
from fapi.ai_prep.services.media_service import media_service
from fapi.ai_prep.services.storage_service import storage_service
from fapi.ai_prep.clients.youtube_client import youtube_client
from fapi.ai_prep.models import AiPrepAssessment
from fapi.ai_prep.exceptions import YouTubeUploadError


class TestYouTubeService:

    def test_upload_video_file_not_found(self):
        with pytest.raises(YouTubeUploadError):
            youtube_service.upload_video("/non/existent/video.webm", "Title")

    def test_upload_video_missing_credentials_raises_error(self, monkeypatch):
        monkeypatch.setattr(youtube_client, "has_live_credentials", lambda: False)
        temp_video = os.path.join(storage_service.base_path, "test_nocreds.webm")
        with open(temp_video, "wb") as f:
            f.write(b"Test_Video_Data")

        try:
            with pytest.raises(YouTubeUploadError, match="credentials"):
                youtube_client.upload_video_unlisted(temp_video, "Test")
        finally:
            if os.path.exists(temp_video):
                os.remove(temp_video)

    def test_upload_video_unlisted_api_call(self, monkeypatch):
        temp_video = os.path.join(storage_service.base_path, "test_sim.webm")
        with open(temp_video, "wb") as f:
            f.write(b"Test_Video_Data")

        # Mock YouTube live API response
        mock_upload = MagicMock(return_value={
            "video_id": "mock_yt_vid123",
            "youtube_url": "https://youtube.com/watch?v=mock_yt_vid123",
            "status": "unlisted",
        })
        monkeypatch.setattr(youtube_client, "has_live_credentials", lambda: True)
        monkeypatch.setattr(youtube_client, "_upload_live_api", mock_upload)

        try:
            res = youtube_service.upload_video(
                video_path=temp_video,
                title="Test Upload",
                assessment_id=123,
            )
            assert res["video_id"] == "mock_yt_vid123"
            assert res["youtube_url"] == "https://youtube.com/watch?v=mock_yt_vid123"
            assert res["status"] == "unlisted"
            mock_upload.assert_called_once()
        finally:
            if os.path.exists(temp_video):
                os.remove(temp_video)

    def test_youtube_upload_and_local_file_cleanup(self, db_session, monkeypatch):
        candidate_id = 777
        assessment = AiPrepAssessment(
            candidate_id=candidate_id,
            assessment_type="TECHNICAL",
            assessment_mode="VIDEO",
            status="IN_PROGRESS",
        )
        db_session.add(assessment)
        db_session.commit()
        db_session.refresh(assessment)
        aid = assessment.id

        video_path = storage_service.get_assembled_video_path(candidate_id, aid)
        with open(video_path, "wb") as f:
            f.write(b"Simulated_Assembled_Video_Bytes")

        assert os.path.exists(video_path)

        monkeypatch.setattr(youtube_client, "has_live_credentials", lambda: True)
        monkeypatch.setattr(youtube_client, "_upload_live_api", lambda account, file_path, title, description: {
            "video_id": f"yt_mock_{aid}",
            "youtube_url": f"https://youtube.com/watch?v=yt_mock_{aid}",
            "status": "unlisted",
        })

        try:
            result = media_service.execute_youtube_upload_and_cleanup(aid, db_session)
            assert result["local_file_deleted"] is True
            assert f"https://youtube.com/watch?v=yt_mock_{aid}" in result["youtube_url"]

            # Verify local video deleted
            assert not os.path.exists(video_path)

            # Verify database updated
            db_session.refresh(assessment)
            assert assessment.youtube_url == result["youtube_url"]
        finally:
            storage_service.delete_assessment_media(candidate_id, aid)

    def test_delete_youtube_video_gdpr(self, monkeypatch):
        monkeypatch.setattr(youtube_client, "has_live_credentials", lambda: True)
        monkeypatch.setattr(youtube_client, "delete_video", lambda vid: True)
        deleted = youtube_service.delete_video("mock_video_id_123")
        assert deleted is True

    def test_sequential_account_exhaustion_failover(self, monkeypatch):
        from fapi.ai_prep.clients.youtube_account_manager import YouTubeAccountPool, YouTubeAccount
        from fapi.ai_prep.clients.youtube_client import YouTubeClient

        pool = YouTubeAccountPool()
        acc1 = YouTubeAccount(account_id="acc_1", refresh_token="tok1", daily_limit=2)
        acc2 = YouTubeAccount(account_id="acc_2", refresh_token="tok2", daily_limit=2)
        pool._accounts = [acc1, acc2]

        client = YouTubeClient(pool=pool)

        temp_video = os.path.join(storage_service.base_path, "test_seq.webm")
        with open(temp_video, "wb") as f:
            f.write(b"Sequential_Test_Data")

        def mock_upload(account, file_path, title, description):
            return {
                "video_id": f"vid_{account.account_id}_{account.upload_count_today + 1}",
                "youtube_url": f"https://youtube.com/watch?v=vid_{account.account_id}",
                "status": "unlisted",
                "account_id": account.account_id,
            }

        monkeypatch.setattr(client, "_upload_live_api", mock_upload)

        try:
            # Upload 1 -> Uses acc_1
            res1 = client.upload_video_unlisted(temp_video, "Vid 1")
            assert res1["account_id"] == "acc_1"
            assert acc1.upload_count_today == 1
            assert not acc1.is_exhausted

            # Upload 2 -> Uses acc_1 (limit reached: 2/2)
            res2 = client.upload_video_unlisted(temp_video, "Vid 2")
            assert res2["account_id"] == "acc_1"
            assert acc1.upload_count_today == 2
            assert acc1.is_exhausted

            # Upload 3 -> Automatically fails over sequentially to acc_2!
            res3 = client.upload_video_unlisted(temp_video, "Vid 3")
            assert res3["account_id"] == "acc_2"
            assert acc2.upload_count_today == 1
            assert not acc2.is_exhausted

            # Upload 4 -> Uses acc_2 (limit reached: 2/2)
            res4 = client.upload_video_unlisted(temp_video, "Vid 4")
            assert res4["account_id"] == "acc_2"
            assert acc2.upload_count_today == 2
            assert acc2.is_exhausted

            # Upload 5 -> Both accounts exhausted! Must raise AllYouTubeQuotasExhaustedError
            from fapi.ai_prep.exceptions import AllYouTubeQuotasExhaustedError
            with pytest.raises(AllYouTubeQuotasExhaustedError) as exc_info:
                client.upload_video_unlisted(temp_video, "Vid 5")
            assert exc_info.value.total_accounts == 2
            assert exc_info.value.seconds_until_reset > 0
        finally:
            if os.path.exists(temp_video):
                os.remove(temp_video)

    def test_google_403_quota_exceeded_triggers_immediate_sequential_failover(self, monkeypatch):
        from fapi.ai_prep.clients.youtube_account_manager import YouTubeAccountPool, YouTubeAccount
        from fapi.ai_prep.clients.youtube_client import YouTubeClient

        pool = YouTubeAccountPool()
        acc1 = YouTubeAccount(account_id="acc_1", refresh_token="tok1", daily_limit=6)
        acc2 = YouTubeAccount(account_id="acc_2", refresh_token="tok2", daily_limit=6)
        pool._accounts = [acc1, acc2]

        client = YouTubeClient(pool=pool)

        temp_video = os.path.join(storage_service.base_path, "test_403.webm")
        with open(temp_video, "wb") as f:
            f.write(b"Quota_403_Test_Data")

        def mock_upload_with_403(account, file_path, title, description):
            if account.account_id == "acc_1":
                raise Exception("<HttpError 403 when requesting: The user has exceeded uploadLimitExceeded quota>")
            return {
                "video_id": "vid_acc2_success",
                "youtube_url": "https://youtube.com/watch?v=vid_acc2_success",
                "status": "unlisted",
                "account_id": account.account_id,
            }

        monkeypatch.setattr(client, "_upload_live_api", mock_upload_with_403)

        try:
            # Upload should fail on acc_1 with 403, mark acc_1 exhausted, and succeed on acc_2!
            res = client.upload_video_unlisted(temp_video, "403 Test")
            assert res["account_id"] == "acc_2"
            assert acc1.is_exhausted is True
            assert acc2.upload_count_today == 1
        finally:
            if os.path.exists(temp_video):
                os.remove(temp_video)


