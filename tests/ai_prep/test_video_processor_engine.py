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
import unittest
import tempfile
from pathlib import Path

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


class TestChunkValidation(unittest.TestCase):
    """Tests chunk sequence continuity and file-level checks."""

    def test_complete_chunk_sequence(self):
        result = validate_chunk_sequence(existing_chunks=[1, 2, 3, 4, 5], total_expected=5)
        self.assertTrue(result["is_valid"])
        self.assertEqual(result["missing_chunks"], [])
        self.assertEqual(result["uploaded_count"], 5)
        self.assertIsNone(result["error"])

    def test_missing_chunks_detected(self):
        result = validate_chunk_sequence(existing_chunks=[1, 3, 5], total_expected=5)
        self.assertFalse(result["is_valid"])
        self.assertEqual(result["missing_chunks"], [2, 4])
        self.assertIn("Missing 2 chunks", result["error"])

    def test_invalid_total_expected(self):
        result = validate_chunk_sequence(existing_chunks=[], total_expected=0)
        self.assertFalse(result["is_valid"])
        self.assertIn("Must be >= 1", result["error"])

    def test_chunk_file_validation_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_path = os.path.join(tmp_dir, "non_existent.webm")
            res = validate_chunk_file(fake_path)
            self.assertFalse(res["is_valid"])
            self.assertIn("not found", res["error"])

    def test_chunk_file_validation_too_small(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tiny_file = os.path.join(tmp_dir, "tiny.webm")
            with open(tiny_file, "wb") as f:
                f.write(b"short")
            res = validate_chunk_file(tiny_file, min_size_bytes=MIN_CHUNK_SIZE_BYTES)
            self.assertFalse(res["is_valid"])
            self.assertIn("below minimum threshold", res["error"])

    def test_chunk_file_validation_valid(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            valid_file = os.path.join(tmp_dir, "valid.webm")
            with open(valid_file, "wb") as f:
                f.write(b"\x1a\x45\xdf\xa3" + b"\x00" * 200)
            res = validate_chunk_file(valid_file, min_size_bytes=MIN_CHUNK_SIZE_BYTES)
            self.assertTrue(res["is_valid"])
            self.assertEqual(res["file_size_bytes"], 204)
            self.assertIsNone(res["error"])


class TestMediaVerification(unittest.TestCase):
    """Tests container magic bytes and stream integrity checks."""

    def test_verify_assembled_video_missing(self):
        res = verify_assembled_video("/path/does/not/exist/full.webm")
        self.assertFalse(res["is_valid"])
        self.assertEqual(res["file_size_bytes"], 0)

    def test_verify_assembled_video_valid_webm(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            webm_file = os.path.join(tmp_dir, "full.webm")
            webm_content = CONTAINER_SIGNATURES["webm"] + b"\x00" * (MIN_ASSEMBLED_VIDEO_BYTES + 100)
            with open(webm_file, "wb") as f:
                f.write(webm_content)

            res = verify_assembled_video(webm_file)
            self.assertTrue(res["is_valid"])
            self.assertEqual(res["detected_format"], "webm")
            self.assertTrue(res["header_valid"])
            self.assertIsNone(res["error"])

    def test_verify_assembled_video_invalid_header(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            corrupt_file = os.path.join(tmp_dir, "corrupt.webm")
            with open(corrupt_file, "wb") as f:
                f.write(b"NOT_A_WEBM_CONTAINER" + b"\x00" * (MIN_ASSEMBLED_VIDEO_BYTES + 50))

            res = verify_assembled_video(corrupt_file)
            self.assertFalse(res["is_valid"])
            self.assertFalse(res["header_valid"])

    def test_verify_audio_file_valid_wav(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            wav_file = os.path.join(tmp_dir, "audio.wav")
            wav_content = CONTAINER_SIGNATURES["wav"] + b"\x00" * (MIN_AUDIO_FILE_BYTES + 100)
            with open(wav_file, "wb") as f:
                f.write(wav_content)

            res = verify_audio_file(wav_file)
            self.assertTrue(res["is_valid"])
            self.assertEqual(res["detected_format"], "wav")
            self.assertTrue(res["header_valid"])


class TestPreflightInspection(unittest.TestCase):
    """Tests YouTube upload pre-flight inspection and quota safeguarding."""

    def test_preflight_fails_on_missing_or_corrupt_video(self):
        res = inspect_youtube_upload_readiness("/non/existent/video.webm", title="Test Title")
        self.assertFalse(res["ready_for_upload"])
        self.assertIn("Preflight media check failed", res["error"])

    def test_preflight_succeeds_and_sanitizes_metadata(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            webm_file = os.path.join(tmp_dir, "full.webm")
            webm_content = CONTAINER_SIGNATURES["webm"] + b"\x00" * (MIN_ASSEMBLED_VIDEO_BYTES + 200)
            with open(webm_file, "wb") as f:
                f.write(webm_content)

            long_title = "A" * 150
            res = inspect_youtube_upload_readiness(
                video_path=webm_file,
                title=long_title,
                description="Test Description",
                assessment_id=999,
            )

            self.assertTrue(res["ready_for_upload"])
            self.assertLessEqual(len(res["sanitized_title"]), 100)
            self.assertEqual(res["sanitized_description"], "Test Description")
            self.assertGreater(res["file_size_bytes"], 0)
            self.assertIsNone(res["error"])


class TestEngineFacade(unittest.TestCase):
    """Tests VideoProcessorEngine class and singleton instance."""

    def test_engine_singleton(self):
        config = video_processor_engine.get_engine_config()
        self.assertIn("min_chunk_bytes", config)
        self.assertIn("min_assembled_video_bytes", config)
        self.assertIn("supported_video_formats", config)


if __name__ == "__main__":
    unittest.main()
