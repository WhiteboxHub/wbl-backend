"""
Unit Tests for Video Processor Engine (BE2)
===========================================
Tests:
- Sequential chunk continuity & missing chunk detection
- Chunk file byte validation
- Container header inspection (EBML WebM, RIFF WAV)
- YouTube pre-flight checks and quota safeguarding
"""
import os
import pytest
from fapi.ai_prep.core.video_processor_engine import (
    VideoProcessorEngine,
    video_processor_engine,
    validate_chunk_sequence,
    validate_chunk_file,
    verify_assembled_video,
    verify_audio_file,
    inspect_youtube_upload_readiness,
)
from fapi.ai_prep.core.video_processor_engine.config import (
    CONTAINER_SIGNATURES,
    MIN_CHUNK_SIZE_BYTES,
    MIN_ASSEMBLED_VIDEO_BYTES,
    MIN_AUDIO_FILE_BYTES,
)


class TestChunkValidation:
    """Tests chunk sequence continuity and file-level checks."""

    def test_complete_chunk_sequence(self):
        result = validate_chunk_sequence(existing_chunks=[1, 2, 3, 4, 5], total_expected=5)
        assert result["is_valid"] is True
        assert result["missing_chunks"] == []
        assert result["uploaded_count"] == 5
        assert result["error"] is None

    def test_missing_chunks_detected(self):
        result = validate_chunk_sequence(existing_chunks=[1, 3, 5], total_expected=5)
        assert result["is_valid"] is False
        assert result["missing_chunks"] == [2, 4]
        assert "Missing 2 chunks" in result["error"]

    def test_invalid_total_expected(self):
        result = validate_chunk_sequence(existing_chunks=[], total_expected=0)
        assert result["is_valid"] is False
        assert "Must be >= 1" in result["error"]

    def test_chunk_file_validation_missing(self, tmp_path):
        fake_path = str(tmp_path / "non_existent.webm")
        res = validate_chunk_file(fake_path)
        assert res["is_valid"] is False
        assert "not found" in res["error"]

    def test_chunk_file_validation_too_small(self, tmp_path):
        tiny_file = tmp_path / "tiny.webm"
        tiny_file.write_bytes(b"short")
        res = validate_chunk_file(str(tiny_file), min_size_bytes=MIN_CHUNK_SIZE_BYTES)
        assert res["is_valid"] is False
        assert "below minimum threshold" in res["error"]

    def test_chunk_file_validation_valid(self, tmp_path):
        valid_file = tmp_path / "valid.webm"
        valid_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"\x00" * 200)
        res = validate_chunk_file(str(valid_file), min_size_bytes=MIN_CHUNK_SIZE_BYTES)
        assert res["is_valid"] is True
        assert res["file_size_bytes"] == 204
        assert res["error"] is None


class TestMediaVerification:
    """Tests container magic bytes and stream integrity checks."""

    def test_verify_assembled_video_missing(self):
        res = verify_assembled_video("/path/does/not/exist/full.webm")
        assert res["is_valid"] is False
        assert res["file_size_bytes"] == 0

    def test_verify_assembled_video_valid_webm(self, tmp_path):
        webm_file = tmp_path / "full.webm"
        # Write valid EBML magic bytes + padding
        webm_content = CONTAINER_SIGNATURES["webm"] + b"\x00" * (MIN_ASSEMBLED_VIDEO_BYTES + 100)
        webm_file.write_bytes(webm_content)

        res = verify_assembled_video(str(webm_file))
        assert res["is_valid"] is True
        assert res["detected_format"] == "webm"
        assert res["header_valid"] is True
        assert res["error"] is None

    def test_verify_assembled_video_invalid_header(self, tmp_path):
        corrupt_file = tmp_path / "corrupt.webm"
        corrupt_file.write_bytes(b"NOT_A_WEBM_CONTAINER" + b"\x00" * (MIN_ASSEMBLED_VIDEO_BYTES + 50))

        res = verify_assembled_video(str(corrupt_file))
        assert res["is_valid"] is False
        assert res["header_valid"] is False

    def test_verify_audio_file_valid_wav(self, tmp_path):
        wav_file = tmp_path / "audio.wav"
        wav_content = CONTAINER_SIGNATURES["wav"] + b"\x00" * (MIN_AUDIO_FILE_BYTES + 100)
        wav_file.write_bytes(wav_content)

        res = verify_audio_file(str(wav_file))
        assert res["is_valid"] is True
        assert res["detected_format"] == "wav"
        assert res["header_valid"] is True


class TestPreflightInspection:
    """Tests YouTube upload pre-flight inspection and quota safeguarding."""

    def test_preflight_fails_on_missing_or_corrupt_video(self):
        res = inspect_youtube_upload_readiness("/non/existent/video.webm", title="Test Title")
        assert res["ready_for_upload"] is False
        assert "Preflight media check failed" in res["error"]

    def test_preflight_succeeds_and_sanitizes_metadata(self, tmp_path):
        webm_file = tmp_path / "full.webm"
        webm_content = CONTAINER_SIGNATURES["webm"] + b"\x00" * (MIN_ASSEMBLED_VIDEO_BYTES + 200)
        webm_file.write_bytes(webm_content)

        long_title = "A" * 150
        res = inspect_youtube_upload_readiness(
            video_path=str(webm_file),
            title=long_title,
            description="Test Description",
            assessment_id=999,
        )

        assert res["ready_for_upload"] is True
        assert len(res["sanitized_title"]) <= 100
        assert res["sanitized_description"] == "Test Description"
        assert res["file_size_bytes"] > 0
        assert res["error"] is None


class TestEngineFacade:
    """Tests VideoProcessorEngine class and singleton instance."""

    def test_engine_singleton(self):
        config = video_processor_engine.get_engine_config()
        assert "min_chunk_bytes" in config
        assert "min_assembled_video_bytes" in config
        assert "supported_video_formats" in config
