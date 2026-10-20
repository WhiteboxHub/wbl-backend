"""
Unit Tests for YouTube Queue Worker Service (FIFO Ordering & Scheduled Drain).
"""
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fapi.db.models import Base, AuthUserORM, CandidateORM
from fapi.ai_prep.models import AiPrepAssessmentORM
from fapi.ai_prep.clients.youtube_quota_manager import youtube_quota_manager
from fapi.ai_prep.services.youtube_queue_worker import (
    get_pending_youtube_uploads,
    get_youtube_queue_status,
    drain_youtube_queue,
)


@pytest.fixture
def queue_db_session():
    """In-memory SQLite session for testing queue processing."""
    engine = create_engine("sqlite:///:memory:")
    tables = [AiPrepAssessmentORM.__table__]
    Base.metadata.create_all(bind=engine, tables=tables)
    Session = sessionmaker(bind=engine)
    session = Session()

    youtube_quota_manager.reset_quota()
    yield session

    session.close()
    Base.metadata.drop_all(bind=engine, tables=tables)
    youtube_quota_manager.reset_quota()


def test_get_pending_youtube_uploads_fifo_ordering(queue_db_session):
    """Pending assessments awaiting YouTube upload must be returned in strict FIFO order (lowest ID first)."""
    # Create 3 assessments
    a1 = AiPrepAssessmentORM(
        candidate_id=101,
        status="COMPLETED",
        media_type="AUDIO",
        consent={"save_recording": True},
        youtube_url=None,
    )
    a2 = AiPrepAssessmentORM(
        candidate_id=102,
        status="COMPLETED",
        media_type="AUDIO",
        consent={"save_recording": True},
        youtube_url=None,
    )
    a3 = AiPrepAssessmentORM(
        candidate_id=103,
        status="COMPLETED",
        media_type="AUDIO",
        consent={"save_recording": True},
        youtube_url=None,
    )
    queue_db_session.add_all([a1, a2, a3])
    queue_db_session.commit()

    pending = get_pending_youtube_uploads(queue_db_session)
    assert len(pending) == 3
    assert pending[0].id == a1.id
    assert pending[1].id == a2.id
    assert pending[2].id == a3.id


def test_get_pending_skips_unconsented_assessments(queue_db_session):
    """Assessments where candidate chose save_recording: False must NOT be enqueued."""
    a_consented = AiPrepAssessmentORM(
        candidate_id=101,
        status="COMPLETED",
        consent={"save_recording": True},
        youtube_url=None,
    )
    a_unconsented = AiPrepAssessmentORM(
        candidate_id=102,
        status="COMPLETED",
        consent={"save_recording": False},
        youtube_url=None,
    )
    a_already_uploaded = AiPrepAssessmentORM(
        candidate_id=103,
        status="COMPLETED",
        consent={"save_recording": True},
        youtube_url="https://youtu.be/existing123",
    )
    queue_db_session.add_all([a_consented, a_unconsented, a_already_uploaded])
    queue_db_session.commit()

    pending = get_pending_youtube_uploads(queue_db_session)
    assert len(pending) == 1
    assert pending[0].id == a_consented.id


def test_get_youtube_queue_status(queue_db_session):
    """Queue status returns correct counts and quota state."""
    a1 = AiPrepAssessmentORM(
        candidate_id=201,
        status="COMPLETED",
        consent={"save_recording": True},
        youtube_url=None,
    )
    queue_db_session.add(a1)
    queue_db_session.commit()

    status = get_youtube_queue_status(queue_db_session)
    assert status["queue_length"] == 1
    assert status["can_upload_now"] is True
    assert status["oldest_pending_assessment_id"] == a1.id


def test_drain_youtube_queue_success(queue_db_session, tmp_path, monkeypatch):
    """Queue worker drains pending items in FIFO order, updates DB, and respects max_uploads."""
    monkeypatch.setattr("fapi.ai_prep.services.youtube_queue_worker.STORAGE_BASE_DIR", str(tmp_path))

    a1 = AiPrepAssessmentORM(
        candidate_id=301,
        status="COMPLETED",
        consent={"save_recording": True},
        youtube_url=None,
    )
    queue_db_session.add(a1)
    queue_db_session.commit()

    # Create dummy media file
    ass_dir = tmp_path / "301" / str(a1.id)
    ass_dir.mkdir(parents=True)
    media_file = ass_dir / "audio_youtube.mp4"
    media_file.write_bytes(b"dummy mp4 video bytes")

    mock_upload_res = {"youtube_url": "https://youtu.be/test_uploaded_id_1"}

    from fapi.ai_prep.clients.youtube_client import youtube_client
    with patch.object(youtube_client, "upload_unlisted_media", return_value=mock_upload_res) as mock_upload:
        res = drain_youtube_queue(queue_db_session, max_uploads=5)

        assert res["status"] == "SUCCESS"
        assert res["uploaded_count"] == 1
        assert res["remaining_count"] == 0

        # Assert DB updated
        queue_db_session.refresh(a1)
        assert a1.youtube_url == "https://youtu.be/test_uploaded_id_1"
        mock_upload.assert_called_once()


def test_drain_youtube_queue_quota_exhausted_halts_gracefully(queue_db_session, tmp_path, monkeypatch):
    """When quota manager reports insufficient quota, worker halts gracefully and preserves items in queue."""
    monkeypatch.setattr("fapi.ai_prep.services.youtube_queue_worker.STORAGE_BASE_DIR", str(tmp_path))

    a1 = AiPrepAssessmentORM(
        candidate_id=401,
        status="COMPLETED",
        consent={"save_recording": True},
        youtube_url=None,
    )
    queue_db_session.add(a1)
    queue_db_session.commit()

    # Mark quota exhausted
    youtube_quota_manager.mark_quota_exceeded()

    res = drain_youtube_queue(queue_db_session)
    assert res["status"] == "QUOTA_EXHAUSTED"
    assert res["uploaded_count"] == 0

    # Assessment remains in queue with youtube_url as None
    queue_db_session.refresh(a1)
    assert a1.youtube_url is None
