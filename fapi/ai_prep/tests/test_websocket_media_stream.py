"""
Tests for WebSocket media streaming and deterministic media type detection.
"""
import struct
import wave
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from fapi.ai_prep.crud import get_assessment_expected_media_type
from fapi.ai_prep.models import AiPrepAssessmentORM
from fapi.ai_prep.core.websocket_stream_manager import (
    WebSocketStreamSession,
    parse_binary_frame,
    MissingFramesError,
    get_or_create_stream_session,
    remove_stream_session,
    get_preassembled_media_path,
)


def test_get_assessment_expected_media_type_audio():
    mock_db = MagicMock()
    mock_assessment = MagicMock(spec=AiPrepAssessmentORM)
    mock_assessment.media_type = "AUDIO"
    mock_db.query().filter().first.return_value = mock_assessment

    resolved = get_assessment_expected_media_type(mock_db, 101)
    assert resolved == "AUDIO"


def test_get_assessment_expected_media_type_video():
    mock_db = MagicMock()
    mock_assessment = MagicMock(spec=AiPrepAssessmentORM)
    mock_assessment.media_type = "VIDEO"
    mock_db.query().filter().first.return_value = mock_assessment

    resolved = get_assessment_expected_media_type(mock_db, 202)
    assert resolved == "VIDEO"


def test_get_assessment_expected_media_type_not_found():
    mock_db = MagicMock()
    mock_db.query().filter().first.return_value = None

    with pytest.raises(ValueError, match="not found in database"):
        get_assessment_expected_media_type(mock_db, 999)


def test_parse_binary_frame_success():
    seq = 42
    payload = b"\x01\x02\x03\x04\x05"
    packet = struct.pack(">I", seq) + payload
    parsed_seq, parsed_payload = parse_binary_frame(packet)
    assert parsed_seq == 42
    assert parsed_payload == payload


def test_parse_binary_frame_too_short():
    with pytest.raises(ValueError, match="Packet too short"):
        parse_binary_frame(b"\x00\x01")


def test_stream_session_audio_lifecycle(tmp_path: Path):
    session = WebSocketStreamSession(
        candidate_id=1,
        assessment_id=99,
        expected_media_type="AUDIO",
        base_scratch_dir=tmp_path,
    )

    # Write frames 0 and 1 (synthetic 16kHz PCM data: 16000 samples/sec * 2 bytes = 32000 bytes/sec)
    frame0_pcm = b"\x00\x00" * 4096
    frame1_pcm = b"\x10\x00" * 4096

    session.write_frame(0, frame0_pcm)
    session.write_frame(1, frame1_pcm)

    # Audit expecting 3 frames -> frame 2 is missing
    missing = session.audit_frames(3)
    assert missing == [2]

    # Supply missing frame 2
    frame2_pcm = b"\x20\x00" * 4096
    session.write_frame(2, frame2_pcm)

    # Audit expecting 3 frames -> all present
    missing_now = session.audit_frames(3)
    assert missing_now == []

    # Finalize audio into 16kHz WAV
    wav_path = session.finalize(total_frames=3)
    assert Path(wav_path).exists()
    assert wav_path.endswith("audio.wav")

    # Verify generated WAV header
    with wave.open(wav_path, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == 4096 * 3

    # Clean up
    session.cleanup_all()
    assert not Path(wav_path).exists()


def test_stream_session_video_lifecycle(tmp_path: Path):
    session = WebSocketStreamSession(
        candidate_id=2,
        assessment_id=100,
        expected_media_type="VIDEO",
        base_scratch_dir=tmp_path,
    )

    chunk0 = b"WEBM_CHUNK_0"
    chunk1 = b"_CHUNK_1"
    session.write_frame(0, chunk0)
    session.write_frame(1, chunk1)

    video_path = session.finalize(total_frames=2)
    assert Path(video_path).exists()
    assert video_path.endswith("video.webm")

    with open(video_path, "rb") as f:
        content = f.read()
    assert content == b"WEBM_CHUNK_0_CHUNK_1"

    session.cleanup_all()


def test_stream_session_missing_frames_error(tmp_path: Path):
    session = WebSocketStreamSession(
        candidate_id=3,
        assessment_id=101,
        expected_media_type="AUDIO",
        base_scratch_dir=tmp_path,
    )
    session.write_frame(0, b"\x00" * 100)
    # Skipping frame 1 and writing frame 2
    session.write_frame(2, b"\x00" * 100)

    with pytest.raises(MissingFramesError) as exc:
        session.finalize(total_frames=3)
    assert 1 in exc.value.missing_indices
    session.cleanup_all()


def test_websocket_route_audio_full_handshake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from fastapi.testclient import TestClient
    from fapi.main import app
    from fapi.db.database import get_db
    from fapi.ai_prep.core.websocket_stream_manager import _ACTIVE_SESSIONS
    import fapi.ai_prep.core.websocket_stream_manager as wsm

    monkeypatch.setenv("AIPREP_SCRATCH_ROOT", str(tmp_path))
    monkeypatch.setattr(wsm, "DEFAULT_SCRATCH_ROOT", tmp_path)
    _ACTIVE_SESSIONS.pop(999, None)

    mock_db = MagicMock()
    mock_assessment = MagicMock(spec=AiPrepAssessmentORM)
    mock_assessment.media_type = "AUDIO"
    mock_db.query().filter().first.return_value = mock_assessment

    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app)

    try:
        with client.websocket_connect("/api/aiprep/candidates/1/assessments/999/audio/stream") as ws:
            # 1. Server sends initial READY handshake with expected_media_type
            ready_msg = ws.receive_json()
            assert ready_msg["type"] == "READY"
            assert ready_msg["assessment_id"] == 999
            assert ready_msg["expected_media_type"] == "AUDIO"

            # 2. Client sends frame 0
            frame0 = struct.pack(">I", 0) + (b"\x00\x00" * 1024)
            ws.send_bytes(frame0)
            ack0 = ws.receive_json()
            assert ack0 == {"type": "ACK", "seq": 0}

            # 3. Client sends frame 1
            frame1 = struct.pack(">I", 1) + (b"\x10\x00" * 1024)
            ws.send_bytes(frame1)
            ack1 = ws.receive_json()
            assert ack1 == {"type": "ACK", "seq": 1}

            # 4. Client sends EOF
            ws.send_json({"type": "EOF", "total_frames": 2})
            final_msg = ws.receive_json()
            assert final_msg["type"] == "FINALIZED"
            assert final_msg["total_frames"] == 2
            assert final_msg["expected_media_type"] == "AUDIO"
            assert Path(final_msg["media_path"]).exists()

            # Clean up session files
            session = _ACTIVE_SESSIONS.get(999)
            if session:
                session.cleanup_all()
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_websocket_route_resend_missing_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from fastapi.testclient import TestClient
    from fapi.main import app
    from fapi.db.database import get_db
    from fapi.ai_prep.core.websocket_stream_manager import _ACTIVE_SESSIONS
    import fapi.ai_prep.core.websocket_stream_manager as wsm

    monkeypatch.setenv("AIPREP_SCRATCH_ROOT", str(tmp_path))
    monkeypatch.setattr(wsm, "DEFAULT_SCRATCH_ROOT", tmp_path)
    _ACTIVE_SESSIONS.pop(888, None)

    mock_db = MagicMock()
    mock_assessment = MagicMock(spec=AiPrepAssessmentORM)
    mock_assessment.media_type = "AUDIO"
    mock_db.query().filter().first.return_value = mock_assessment

    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app)

    try:
        with client.websocket_connect("/api/aiprep/candidates/1/assessments/888/audio/stream") as ws:
            ready_msg = ws.receive_json()
            assert ready_msg["type"] == "READY"

            # Send frame 0 only
            ws.send_bytes(struct.pack(">I", 0) + (b"\x00\x00" * 512))
            assert ws.receive_json()["type"] == "ACK"

            # Client sends EOF expecting 2 frames -> frame 1 is missing
            ws.send_json({"type": "EOF", "total_frames": 2})
            resend_msg = ws.receive_json()
            assert resend_msg["type"] == "RESEND"
            assert resend_msg["missing"] == [1]

            # Client re-sends frame 1
            ws.send_bytes(struct.pack(">I", 1) + (b"\x10\x00" * 512))
            assert ws.receive_json()["type"] == "ACK"

            # Client sends EOF again -> now all present!
            ws.send_json({"type": "EOF", "total_frames": 2})
            final_msg = ws.receive_json()
            assert final_msg["type"] == "FINALIZED"
            assert final_msg["total_frames"] == 2

            session = _ACTIVE_SESSIONS.get(888)
            if session:
                session.cleanup_all()
    finally:
        app.dependency_overrides.pop(get_db, None)

