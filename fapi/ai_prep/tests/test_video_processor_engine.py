"""
Unit and Integration Tests for Video Processor Engine, Audio-to-Video Packaging,
YouTube Client & Storage Streaming.
"""
import os
import tempfile
import pytest
from fapi.ai_prep.core.video_processor_engine import (
    VideoProcessorEngine,
    video_processor_engine,
    validate_chunk_sequence,
    validate_chunk_file,
    verify_assembled_video,
    verify_audio_file,
    detect_container_format,
    inspect_youtube_upload_readiness,
    convert_audio_to_youtube_video,
)
from fapi.ai_prep.clients.youtube_client import (
    YouTubeClient,
    youtube_client,
    YouTubeUploadError,
)


def test_chunk_sequence_validation():
    # Complete sequence 1..5
    res = validate_chunk_sequence([1, 2, 3, 4, 5], total_expected=5)
    assert res["is_valid"] is True
    assert res["missing_chunks"] == []

    # Missing chunk 3 in 1..5
    res2 = validate_chunk_sequence([1, 2, 4, 5], total_expected=5)
    assert res2["is_valid"] is False
    assert res2["missing_chunks"] == [3]

    # Invalid total_expected
    res3 = validate_chunk_sequence([], total_expected=0)
    assert res3["is_valid"] is False


def test_chunk_file_validation():
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tf:
        tf.write(b"\x1a\x45\xdf\xa3" + b"\x00" * 200)
        chunk_path = tf.name

    try:
        res = validate_chunk_file(chunk_path, min_size_bytes=50)
        assert res["is_valid"] is True
        assert res["file_size_bytes"] > 50

        # File below threshold
        res2 = validate_chunk_file(chunk_path, min_size_bytes=1000)
        assert res2["is_valid"] is False

        # Non-existent file
        res3 = validate_chunk_file("non_existent_file.webm")
        assert res3["is_valid"] is False
    finally:
        if os.path.exists(chunk_path):
            os.remove(chunk_path)


def test_media_verifier():
    # WebM EBML header
    webm_header = b"\x1a\x45\xdf\xa3" + b"\x00" * 30
    assert detect_container_format(webm_header) == "webm"

    # WAV RIFF header
    wav_header = b"RIFF" + b"\x00" * 30
    assert detect_container_format(wav_header) == "wav"

    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tf:
        tf.write(b"\x1a\x45\xdf\xa3" + b"\x00" * 600)
        v_path = tf.name

    try:
        res = verify_assembled_video(v_path, min_size_bytes=100)
        assert res["is_valid"] is True
        assert res["detected_format"] == "webm"

        preflight = inspect_youtube_upload_readiness(
            media_path=v_path,
            title="Test Assessment",
            description="Test Description",
            assessment_id=42,
            media_type="VIDEO",
        )
        assert preflight["ready_for_upload"] is True
        assert preflight["sanitized_title"] == "Test Assessment"
    finally:
        if os.path.exists(v_path):
            os.remove(v_path)


def test_audio_to_video_conversion():
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        tf.write(b"RIFF" + b"\x00" * 300)
        a_path = tf.name

    try:
        # Convert audio for YouTube
        out_v = VideoProcessorEngine.convert_audio_for_youtube(a_path)
        assert out_v is not None
        assert os.path.exists(out_v)
    finally:
        if os.path.exists(a_path):
            os.remove(a_path)


def test_youtube_client_upload():
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tf:
        tf.write(b"\x1a\x45\xdf\xa3" + b"\x00" * 300)
        media_file = tf.name

    try:
        # Video upload
        res = youtube_client.upload_unlisted_media(
            assessment_id=101,
            file_path=media_file,
            media_type="VIDEO",
        )
        assert "youtube_url" in res
        assert "youtube.com" in res["youtube_url"]

        # Audio upload
        res_audio = youtube_client.upload_unlisted_media(
            assessment_id=102,
            file_path=media_file,
            media_type="AUDIO",
        )
        assert "youtube_url" in res_audio
        assert "youtube.com" in res_audio["youtube_url"]
    finally:
        if os.path.exists(media_file):
            os.remove(media_file)


def test_youtube_client_single_account_credentials():
    client = YouTubeClient()
    # Check that client methods function without pool
    assert hasattr(client, "has_live_credentials")
    assert hasattr(client, "upload_unlisted_media")
    assert hasattr(client, "delete_video")
    # Deleting without video id or credentials returns False safely
    assert client.delete_video("") is False

