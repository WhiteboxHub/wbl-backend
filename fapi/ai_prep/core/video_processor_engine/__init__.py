"""
Video Processor Engine Module
=============================
Domain engine for video chunk validation, media format verification,
audio-to-video packaging, and YouTube upload preflight checks.
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
from fapi.ai_prep.core.video_processor_engine.audio_to_video import (
    convert_audio_to_youtube_video,
    MediaConversionError,
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
    "convert_audio_to_youtube_video",
    "MediaConversionError",
]
