"""
Video Processor Engine Package Interface (BE2)
==============================================
Exposes VideoProcessorEngine, chunk validators, container verifiers, and preflight checkers.
"""
from fapi.ai_prep.core.video_processor_engine.engine import (
    VideoProcessorEngine,
    video_processor_engine,
)
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
    SUPPORTED_VIDEO_FORMATS,
    SUPPORTED_AUDIO_FORMATS,
)

__all__ = [
    "VideoProcessorEngine",
    "video_processor_engine",
    "validate_chunk_sequence",
    "validate_chunk_file",
    "verify_assembled_video",
    "verify_audio_file",
    "detect_container_format",
    "inspect_youtube_upload_readiness",
    "VIDEO_ENGINE_CONFIG",
    "SUPPORTED_VIDEO_FORMATS",
    "SUPPORTED_AUDIO_FORMATS",
]
