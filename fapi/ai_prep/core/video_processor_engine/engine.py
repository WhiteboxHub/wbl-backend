"""
Video Processor Engine (BE2 Core Engine)
=========================================
Central domain engine for:
- Video chunk validation and continuity checking
- Assembled video container integrity & codec verification
- Extracted audio verification
- Pre-flight upload inspection for YouTube ingestion
"""
import logging
from typing import List, Dict, Any, Optional

from fapi.ai_prep.core.video_processor_engine.chunk_validator import (
    validate_chunk_sequence,
    validate_chunk_file,
)
from fapi.ai_prep.core.video_processor_engine.media_verifier import (
    verify_assembled_video,
    verify_audio_file,
    detect_container_format,
)
from fapi.ai_prep.core.video_processor_engine.preflight_checker import (
    inspect_youtube_upload_readiness,
)
from fapi.ai_prep.core.video_processor_engine.config import (
    VIDEO_ENGINE_CONFIG,
    MIN_CHUNK_SIZE_BYTES,
    MIN_ASSEMBLED_VIDEO_BYTES,
    MIN_AUDIO_FILE_BYTES,
)

logger = logging.getLogger(__name__)


class VideoProcessorEngine:
    """
    Core Engine for validating video streams, chunks, and YouTube media ingestion.
    Pure business logic without direct database or external network side-effects.
    """

    @staticmethod
    def validate_chunks(
        existing_chunks: List[int],
        total_expected: int,
        start_index: int = 1,
    ) -> Dict[str, Any]:
        """Validates sequential chunk indices and detects missing chunks."""
        return validate_chunk_sequence(
            existing_chunks=existing_chunks,
            total_expected=total_expected,
            start_index=start_index,
        )

    @staticmethod
    def validate_chunk_file(
        chunk_path: str,
        min_size_bytes: int = MIN_CHUNK_SIZE_BYTES,
    ) -> Dict[str, Any]:
        """Validates that a chunk file on disk is non-empty and readable."""
        return validate_chunk_file(chunk_path=chunk_path, min_size_bytes=min_size_bytes)

    @staticmethod
    def verify_assembled_video(
        video_path: str,
        min_size_bytes: int = MIN_ASSEMBLED_VIDEO_BYTES,
    ) -> Dict[str, Any]:
        """Verifies assembled video file header integrity and file size."""
        return verify_assembled_video(video_path=video_path, min_size_bytes=min_size_bytes)

    @staticmethod
    def verify_audio_file(
        audio_path: str,
        min_size_bytes: int = MIN_AUDIO_FILE_BYTES,
    ) -> Dict[str, Any]:
        """Verifies extracted audio file header integrity and file size."""
        return verify_audio_file(audio_path=audio_path, min_size_bytes=min_size_bytes)

    @staticmethod
    def inspect_youtube_upload(
        video_path: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        assessment_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Executes pre-flight inspection before triggering YouTube upload."""
        return inspect_youtube_upload_readiness(
            video_path=video_path,
            title=title,
            description=description,
            assessment_id=assessment_id,
        )

    @staticmethod
    def get_engine_config() -> Dict[str, Any]:
        """Returns engine configuration constants."""
        return VIDEO_ENGINE_CONFIG


# Global singleton instance
video_processor_engine = VideoProcessorEngine()
