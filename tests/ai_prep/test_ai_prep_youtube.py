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
import unittest
from unittest.mock import patch, MagicMock

from fapi.ai_prep.services.youtube_service import youtube_service
from fapi.ai_prep.services.media_service import media_service
from fapi.ai_prep.services.storage_service import storage_service
from fapi.ai_prep.clients.youtube_client import youtube_client
from fapi.ai_prep.models import AiPrepAssessment
from fapi.ai_prep.exceptions import YouTubeUploadError


class TestYouTubeService(unittest.TestCase):

    def setUp(self):
        from tests.conftest import TestingSessionLocal, engine
        from fapi.db.models import Base
        from fapi.ai_prep.clients.youtube_account_manager import youtube_account_pool, YouTubeAccount

        seen_indexes = {}
        for table in Base.metadata.tables.values():
            for index in list(table.indexes):
                if index.name:
                    if index.name in seen_indexes:
                        index.name = f"{index.name}_{table.name}"
                    else:
                        seen_indexes[index.name] = table.name
        Base.metadata.create_all(bind=engine)
        self.db_session = TestingSessionLocal()

        self.mock_acc = YouTubeAccount(
            account_id="test_mock_account",
            refresh_token="mock_refresh_token",
            client_id="mock_client_id",
            client_secret="mock_client_secret",
            daily_limit=9999,
        )
        youtube_account_pool._accounts = [self.mock_acc]

    def tearDown(self):
        self.db_session.close()


    def test_upload_video_file_not_found(self):
        with self.assertRaises(YouTubeUploadError):
            youtube_service.upload_video("/non/existent/video.webm", "Title")

    @patch.object(youtube_client, "has_live_credentials", return_value=False)
    def test_upload_video_missing_credentials_raises_error(self, mock_has_creds):
        temp_video = os.path.join(storage_service.base_path, "test_nocreds.webm")
        with open(temp_video, "wb") as f:
            f.write(b"Test_Video_Data")

        try:
            with self.assertRaises(YouTubeUploadError) as cm:
                youtube_client.upload_video_unlisted(temp_video, "Test")
            self.assertIn("credentials", str(cm.exception))
        finally:
            if os.path.exists(temp_video):
                os.remove(temp_video)

    @patch.object(youtube_client, "has_live_credentials", return_value=True)
    def test_upload_video_unlisted_api_call(self, mock_has_creds):
        temp_video = os.path.join(storage_service.base_path, "test_sim.webm")
        with open(temp_video, "wb") as f:
            f.write(b"Test_Video_Data")

        # Mock YouTube live API response
        mock_upload = MagicMock(return_value={
            "video_id": "mock_yt_vid123",
            "youtube_url": "https://youtube.com/watch?v=mock_yt_vid123",
            "status": "unlisted",
        })

        with patch.object(youtube_client, "_upload_live_api", mock_upload):
            try:
                res = youtube_service.upload_video(
                    video_path=temp_video,
                    title="Test Upload",
                    assessment_id=123,
                )
                self.assertEqual(res["video_id"], "mock_yt_vid123")
                self.assertEqual(res["youtube_url"], "https://youtube.com/watch?v=mock_yt_vid123")
                self.assertEqual(res["status"], "unlisted")
                mock_upload.assert_called_once()
            finally:
                if os.path.exists(temp_video):
                    os.remove(temp_video)

    @patch.object(youtube_client, "has_live_credentials", return_value=True)
    def test_youtube_upload_and_local_file_cleanup(self, mock_has_creds):
        db_session = self.db_session
        candidate_id = 777
        assessment = AiPrepAssessment(
            candidate_id=candidate_id,
            assessment_type="TECHNICAL",
            media_type="VIDEO",
            status="IN_PROGRESS",
        )
        db_session.add(assessment)
        db_session.commit()
        db_session.refresh(assessment)
        aid = assessment.id

        video_path = storage_service.get_assembled_video_path(candidate_id, aid)
        with open(video_path, "wb") as f:
            f.write(b"\x1a\x45\xdf\xa3" + b"Simulated_Assembled_Video_Bytes" * 20)

        self.assertTrue(os.path.exists(video_path))

        fake_upload = lambda account, file_path, title, description: {
            "video_id": f"yt_mock_{aid}",
            "youtube_url": f"https://youtube.com/watch?v=yt_mock_{aid}",
            "status": "unlisted",
        }

        with patch.object(youtube_client, "_upload_live_api", fake_upload):
            try:
                result = media_service.execute_youtube_upload_and_cleanup(aid, db_session)
                self.assertTrue(result["local_file_deleted"])
                self.assertIn(f"https://youtube.com/watch?v=yt_mock_{aid}", result["youtube_url"])

                # Verify local video deleted
                self.assertFalse(os.path.exists(video_path))

                # Verify database updated
                db_session.refresh(assessment)
                self.assertEqual(assessment.youtube_url, result["youtube_url"])
            finally:
                storage_service.delete_assessment_media(candidate_id, aid)

    @patch.object(youtube_client, "has_live_credentials", return_value=True)
    @patch.object(youtube_client, "delete_video", return_value=True)
    def test_delete_youtube_video_gdpr(self, mock_del, mock_has_creds):
        deleted = youtube_service.delete_video("mock_video_id_123")
        self.assertTrue(deleted)

    def test_sequential_account_exhaustion_failover(self):
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

        with patch.object(client, "_upload_live_api", mock_upload):
            try:
                # Upload 1 -> Uses acc_1
                res1 = client.upload_video_unlisted(temp_video, "Vid 1")
                self.assertEqual(res1["account_id"], "acc_1")
                self.assertEqual(acc1.upload_count_today, 1)
                self.assertFalse(acc1.is_exhausted)

                # Upload 2 -> Uses acc_1 (limit reached: 2/2)
                res2 = client.upload_video_unlisted(temp_video, "Vid 2")
                self.assertEqual(res2["account_id"], "acc_1")
                self.assertEqual(acc1.upload_count_today, 2)
                self.assertTrue(acc1.is_exhausted)

                # Upload 3 -> Automatically fails over sequentially to acc_2!
                res3 = client.upload_video_unlisted(temp_video, "Vid 3")
                self.assertEqual(res3["account_id"], "acc_2")
                self.assertEqual(acc2.upload_count_today, 1)
                self.assertFalse(acc2.is_exhausted)

                # Upload 4 -> Uses acc_2 (limit reached: 2/2)
                res4 = client.upload_video_unlisted(temp_video, "Vid 4")
                self.assertEqual(res4["account_id"], "acc_2")
                self.assertEqual(acc2.upload_count_today, 2)
                self.assertTrue(acc2.is_exhausted)

                # Upload 5 -> Both accounts exhausted! Must raise AllYouTubeQuotasExhaustedError
                from fapi.ai_prep.exceptions import AllYouTubeQuotasExhaustedError
                with self.assertRaises(AllYouTubeQuotasExhaustedError) as cm:
                    client.upload_video_unlisted(temp_video, "Vid 5")
                self.assertEqual(cm.exception.total_accounts, 2)
                self.assertGreater(cm.exception.seconds_until_reset, 0)
            finally:
                if os.path.exists(temp_video):
                    os.remove(temp_video)

    def test_google_403_quota_exceeded_triggers_immediate_sequential_failover(self):
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

        with patch.object(client, "_upload_live_api", mock_upload_with_403):
            try:
                # Upload should fail on acc_1 with 403, mark acc_1 exhausted, and succeed on acc_2!
                res = client.upload_video_unlisted(temp_video, "403 Test")
                self.assertEqual(res["account_id"], "acc_2")
                self.assertTrue(acc1.is_exhausted)
                self.assertEqual(acc2.upload_count_today, 1)
            finally:
                if os.path.exists(temp_video):
                    os.remove(temp_video)


if __name__ == "__main__":
    unittest.main()



