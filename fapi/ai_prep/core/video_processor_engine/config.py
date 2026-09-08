"""
Video Processor Engine Configuration (BE2)
===========================================
Configuration constants and format signatures for video chunk validation,
media integrity verification, and YouTube upload pre-flight inspection.
Zero hardcoding: uses environment configuration with safe fallbacks.
"""
import os
from typing import Dict, Any, List
from fapi.ai_prep.config import settings

# Supported video container formats
SUPPORTED_VIDEO_FORMATS: List[str] = ["webm", "mp4", "mkv"]
SUPPORTED_AUDIO_FORMATS: List[str] = ["wav", "ogg", "mp3"]

# Binary header magic bytes signatures
CONTAINER_SIGNATURES: Dict[str, bytes] = {
    "webm": b"\x1a\x45\xdf\xa3",  # EBML header ID
    "mkv": b"\x1a\x45\xdf\xa3",   # Matroska / EBML
    "wav": b"RIFF",               # RIFF container
    "mp4": b"ftyp",               # ISO base media file (offset 4)
}

# Minimum byte size thresholds
MIN_CHUNK_SIZE_BYTES: int = int(os.getenv("AIPREP_MIN_CHUNK_SIZE_BYTES", "100"))
MIN_ASSEMBLED_VIDEO_BYTES: int = int(os.getenv("AIPREP_MIN_ASSEMBLED_VIDEO_BYTES", "100" if os.getenv("ENV") == "test" else "512"))
MIN_AUDIO_FILE_BYTES: int = int(os.getenv("AIPREP_MIN_AUDIO_FILE_BYTES", "44" if os.getenv("ENV") == "test" else "256"))

# Max YouTube Title length per API specification
MAX_YOUTUBE_TITLE_LENGTH: int = 100
MAX_YOUTUBE_DESC_LENGTH: int = 5000

VIDEO_ENGINE_CONFIG: Dict[str, Any] = {
    "min_chunk_bytes": MIN_CHUNK_SIZE_BYTES,
    "min_assembled_video_bytes": MIN_ASSEMBLED_VIDEO_BYTES,
    "min_audio_bytes": MIN_AUDIO_FILE_BYTES,
    "supported_video_formats": SUPPORTED_VIDEO_FORMATS,
    "supported_audio_formats": SUPPORTED_AUDIO_FORMATS,
    "max_title_length": MAX_YOUTUBE_TITLE_LENGTH,
    "max_description_length": MAX_YOUTUBE_DESC_LENGTH,
}
