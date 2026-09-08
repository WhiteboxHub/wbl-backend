"""
Chunk Sequence & Integrity Validator (BE2 Core Engine)
======================================================
Validates:
- Sequential continuity of uploaded video chunks (1..N)
- Detection and enumeration of missing chunks
- Non-empty byte verification and minimum chunk size limits
"""
import os
import logging
from typing import List, Dict, Any, Tuple, Optional
from fapi.ai_prep.core.video_processor_engine.config import MIN_CHUNK_SIZE_BYTES

logger = logging.getLogger(__name__)


def validate_chunk_sequence(
    existing_chunks: List[int],
    total_expected: int,
    start_index: int = 1,
) -> Dict[str, Any]:
    """
    Validates that a sequence of uploaded chunks is complete from `start_index`
    to `total_expected` (inclusive for start_index=1, e.g. 1..N).

    :param existing_chunks: List of uploaded chunk integer indices.
    :param total_expected: Total expected number of chunks.
    :param start_index: Starting chunk index (default 1).
    :return: Dictionary containing validation status and missing chunk indices.
    """
    if total_expected < 1:
        return {
            "is_valid": False,
            "total_expected": total_expected,
            "uploaded_count": len(existing_chunks),
            "missing_chunks": [],
            "error": f"Invalid total_expected ({total_expected}). Must be >= 1.",
        }

    # Normalize uploaded chunks
    existing_set = set(existing_chunks)
    expected_range = list(range(start_index, start_index + total_expected))
    missing_chunks = [idx for idx in expected_range if idx not in existing_set]

    is_valid = len(missing_chunks) == 0

    return {
        "is_valid": is_valid,
        "total_expected": total_expected,
        "uploaded_count": len(existing_set),
        "missing_chunks": missing_chunks,
        "error": None if is_valid else f"Missing {len(missing_chunks)} chunks: {missing_chunks}",
    }


def validate_chunk_file(
    chunk_path: str,
    min_size_bytes: int = MIN_CHUNK_SIZE_BYTES,
) -> Dict[str, Any]:
    """
    Validates that an individual chunk file on disk is present, readable,
    and meets the minimum byte size threshold.

    :param chunk_path: Absolute or relative path to chunk file.
    :param min_size_bytes: Minimum acceptable byte size.
    :return: Diagnostic dictionary.
    """
    if not os.path.exists(chunk_path):
        return {
            "is_valid": False,
            "path": chunk_path,
            "file_size_bytes": 0,
            "error": f"Chunk file not found: {chunk_path}",
        }

    try:
        size = os.path.getsize(chunk_path)
        if size < min_size_bytes:
            return {
                "is_valid": False,
                "path": chunk_path,
                "file_size_bytes": size,
                "error": f"Chunk size ({size} bytes) below minimum threshold ({min_size_bytes} bytes).",
            }

        return {
            "is_valid": True,
            "path": chunk_path,
            "file_size_bytes": size,
            "error": None,
        }
    except Exception as exc:
        return {
            "is_valid": False,
            "path": chunk_path,
            "file_size_bytes": 0,
            "error": f"Error inspecting chunk file: {str(exc)}",
        }
