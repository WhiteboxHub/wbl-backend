"""
Media Container & Stream Verifier (BE2 Core Engine)
===================================================
Validates:
- Binary container headers & signatures (EBML for WebM/MKV, RIFF for WAV, ftyp for MP4)
- Assembled video file integrity and minimum file size
- Extracted audio container format and stream readiness
"""
import os
import logging
from typing import Dict, Any, Optional
from fapi.ai_prep.core.video_processor_engine.config import (
    CONTAINER_SIGNATURES,
    MIN_ASSEMBLED_VIDEO_BYTES,
    MIN_AUDIO_FILE_BYTES,
    SUPPORTED_VIDEO_FORMATS,
    SUPPORTED_AUDIO_FORMATS,
)

logger = logging.getLogger(__name__)


def detect_container_format(header_bytes: bytes) -> Optional[str]:
    """
    Detects container format by inspecting the initial byte stream.

    :param header_bytes: First 32 to 64 bytes of the media file.
    :return: Container format string ('webm', 'wav', 'mp4', etc.) or None.
    """
    if len(header_bytes) < 4:
        return None

    # Check EBML (WebM / MKV)
    if header_bytes.startswith(CONTAINER_SIGNATURES["webm"]):
        return "webm"

    # Check WAV (RIFF header)
    if header_bytes.startswith(CONTAINER_SIGNATURES["wav"]):
        return "wav"

    # Check MP4 (ftyp box at offset 4)
    if len(header_bytes) >= 8 and CONTAINER_SIGNATURES["mp4"] in header_bytes[:16]:
        return "mp4"

    return None


def verify_assembled_video(
    video_path: str,
    min_size_bytes: int = MIN_ASSEMBLED_VIDEO_BYTES,
    allowed_formats: Optional[list] = None,
) -> Dict[str, Any]:
    """
    Verifies that the assembled video file is non-empty, exists on disk,
    and has a valid media container header.

    :param video_path: Path to the assembled video file (e.g. full.webm).
    :param min_size_bytes: Minimum acceptable byte size for assembled video.
    :param allowed_formats: List of allowed formats (defaults to config).
    :return: Diagnostic dictionary with validation status.
    """
    allowed = allowed_formats or SUPPORTED_VIDEO_FORMATS

    if not os.path.exists(video_path):
        return {
            "is_valid": False,
            "video_path": video_path,
            "file_size_bytes": 0,
            "detected_format": None,
            "header_valid": False,
            "error": f"Assembled video file not found at: {video_path}",
        }

    try:
        size = os.path.getsize(video_path)
        if size < min_size_bytes:
            return {
                "is_valid": False,
                "video_path": video_path,
                "file_size_bytes": size,
                "detected_format": None,
                "header_valid": False,
                "error": f"Assembled video size ({size} bytes) below minimum threshold ({min_size_bytes} bytes).",
            }

        # Inspect file header
        with open(video_path, "rb") as f:
            header_bytes = f.read(64)

        detected_format = detect_container_format(header_bytes)
        
        # Valid header requires a detected format in allowed formats
        is_header_valid = detected_format in allowed if detected_format else False

        if not is_header_valid:
            return {
                "is_valid": False,
                "video_path": video_path,
                "file_size_bytes": size,
                "detected_format": detected_format,
                "header_valid": False,
                "error": f"Invalid video container header for '{video_path}'. Detected format: {detected_format}",
            }

        return {
            "is_valid": True,
            "video_path": video_path,
            "file_size_bytes": size,
            "detected_format": detected_format,
            "header_valid": True,
            "error": None,
        }
    except Exception as exc:
        logger.error("Failed to verify assembled video '%s': %s", video_path, str(exc))
        return {
            "is_valid": False,
            "video_path": video_path,
            "file_size_bytes": 0,
            "detected_format": None,
            "header_valid": False,
            "error": f"Error reading video file: {str(exc)}",
        }


def verify_audio_file(
    audio_path: str,
    min_size_bytes: int = MIN_AUDIO_FILE_BYTES,
) -> Dict[str, Any]:
    """
    Verifies that the extracted audio file (e.g. audio.wav) exists, meets minimum size,
    and contains a valid audio header (RIFF/WAVE).

    :param audio_path: Path to extracted audio file.
    :param min_size_bytes: Minimum size threshold in bytes.
    :return: Diagnostic dictionary.
    """
    if not os.path.exists(audio_path):
        return {
            "is_valid": False,
            "audio_path": audio_path,
            "file_size_bytes": 0,
            "header_valid": False,
            "error": f"Audio file not found at: {audio_path}",
        }

    try:
        size = os.path.getsize(audio_path)
        if size < min_size_bytes:
            return {
                "is_valid": False,
                "audio_path": audio_path,
                "file_size_bytes": size,
                "header_valid": False,
                "error": f"Audio file size ({size} bytes) below minimum threshold ({min_size_bytes} bytes).",
            }

        with open(audio_path, "rb") as f:
            header_bytes = f.read(32)

        detected_format = detect_container_format(header_bytes)
        is_header_valid = detected_format == "wav" or header_bytes.startswith(b"RIFF")

        return {
            "is_valid": is_header_valid,
            "audio_path": audio_path,
            "file_size_bytes": size,
            "detected_format": detected_format,
            "header_valid": is_header_valid,
            "error": None if is_header_valid else f"Invalid audio header format: {detected_format}",
        }
    except Exception as exc:
        logger.error("Failed to verify audio file '%s': %s", audio_path, str(exc))
        return {
            "is_valid": False,
            "audio_path": audio_path,
            "file_size_bytes": 0,
            "header_valid": False,
            "error": f"Error reading audio file: {str(exc)}",
        }
