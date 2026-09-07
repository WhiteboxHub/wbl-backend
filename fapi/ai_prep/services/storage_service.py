"""
Local Disk Storage Management Service
======================================
Zero hardcoded paths: uses settings.LOCAL_STORAGE_BASE_PATH.
Manages:
- Saving sequential chunks: storage/ai_prep/{candidate_id}/{assessment_id}/chunks/{chunk_number}.webm
- Chunk validation and status detection
- Sequential assembly into full.webm
- 16kHz mono audio.wav extraction via ffmpeg
- Deletion of local files post-YouTube upload
- GDPR purge and 24-hour abandoned chunk cleanup
"""
import os
import shutil
import logging
import subprocess
import time
from typing import List, Dict, Any, Optional, Tuple

from fapi.ai_prep.config import settings
from fapi.ai_prep.exceptions import (
    ChunkValidationError,
    MissingChunksError,
    MediaAssemblyError,
    AudioExtractionError,
    MediaStorageError,
)

logger = logging.getLogger(__name__)


class StorageService:
    """Manages filesystem storage for media chunks and assembled files."""

    def __init__(self, base_path: Optional[str] = None):
        self.base_path = base_path or settings.LOCAL_STORAGE_BASE_PATH
        os.makedirs(self.base_path, exist_ok=True)

    def get_assessment_dir(self, candidate_id: int, assessment_id: int) -> str:
        """Returns root storage directory for a specific assessment."""
        path = os.path.join(self.base_path, str(candidate_id), str(assessment_id))
        os.makedirs(path, exist_ok=True)
        return path

    def get_chunks_dir(self, candidate_id: int, assessment_id: int) -> str:
        """Returns directory path where 30s WebM chunks are stored."""
        path = os.path.join(self.get_assessment_dir(candidate_id, assessment_id), "chunks")
        os.makedirs(path, exist_ok=True)
        return path

    def get_chunk_file_path(self, candidate_id: int, assessment_id: int, chunk_number: int) -> str:
        """Returns deterministic file path for a chunk."""
        return os.path.join(self.get_chunks_dir(candidate_id, assessment_id), f"{chunk_number}.webm")

    def get_assembled_video_path(self, candidate_id: int, assessment_id: int) -> str:
        """Returns path for assembled full.webm video."""
        return os.path.join(self.get_assessment_dir(candidate_id, assessment_id), "full.webm")

    def get_audio_path(self, candidate_id: int, assessment_id: int) -> str:
        """Returns path for extracted 16kHz mono audio.wav."""
        return os.path.join(self.get_assessment_dir(candidate_id, assessment_id), "audio.wav")

    def save_chunk(
        self,
        candidate_id: int,
        assessment_id: int,
        chunk_number: int,
        file_bytes: bytes,
    ) -> Tuple[str, int]:
        """
        Saves a chunk to disk. Idempotent on retry.
        Validates chunk size limits.
        """
        if chunk_number < 0:
            raise ChunkValidationError(f"Invalid chunk number: {chunk_number}. Must be >= 0.")

        max_bytes = settings.MAX_CHUNK_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise ChunkValidationError(
                f"Chunk size ({len(file_bytes)} bytes) exceeds max limit of {settings.MAX_CHUNK_SIZE_MB}MB"
            )

        try:
            chunk_path = self.get_chunk_file_path(candidate_id, assessment_id, chunk_number)
            with open(chunk_path, "wb") as f:
                f.write(file_bytes)

            file_size = len(file_bytes)
            logger.info("Saved chunk %s for assessment %s (size: %s bytes)", chunk_number, assessment_id, file_size)
            return chunk_path, file_size
        except Exception as e:
            logger.error("Failed to save chunk %s for assessment %s: %s", chunk_number, assessment_id, str(e))
            raise MediaStorageError(f"Failed to save chunk: {str(e)}")

    def get_chunk_status(
        self,
        candidate_id: int,
        assessment_id: int,
        expected_total: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Inspects stored chunks to detect uploaded and missing chunks in sequence."""
        chunks_dir = self.get_chunks_dir(candidate_id, assessment_id)
        uploaded_chunks: List[int] = []

        if os.path.exists(chunks_dir):
            for filename in os.listdir(chunks_dir):
                if filename.endswith(".webm"):
                    try:
                        c_num = int(os.path.splitext(filename)[0])
                        uploaded_chunks.append(c_num)
                    except ValueError:
                        continue

        uploaded_chunks.sort()
        missing_chunks: List[int] = []

        if expected_total is not None and expected_total > 0:
            all_expected = set(range(expected_total))
            uploaded_set = set(uploaded_chunks)
            missing_chunks = sorted(list(all_expected - uploaded_set))
            is_ready = len(missing_chunks) == 0 and len(uploaded_chunks) == expected_total
        else:
            if uploaded_chunks:
                max_chunk = max(uploaded_chunks)
                full_range = set(range(max_chunk + 1))
                missing_chunks = sorted(list(full_range - set(uploaded_chunks)))
            is_ready = len(missing_chunks) == 0 and len(uploaded_chunks) > 0

        return {
            "assessment_id": assessment_id,
            "uploaded_chunks": uploaded_chunks,
            "missing_chunks": missing_chunks,
            "total_chunks": expected_total or len(uploaded_chunks),
            "is_ready_for_assembly": is_ready,
        }

    def assemble_chunks(
        self,
        candidate_id: int,
        assessment_id: int,
        total_chunks: int,
    ) -> str:
        """
        Sequentially concatenates all chunks into full.webm.
        Validates all chunks are present before assembling.
        """
        if total_chunks <= 0:
            raise MediaAssemblyError("total_chunks must be greater than 0")

        status = self.get_chunk_status(candidate_id, assessment_id, expected_total=total_chunks)
        if status["missing_chunks"]:
            raise MissingChunksError(
                missing_chunks=status["missing_chunks"],
                total_chunks=total_chunks,
            )

        assembled_path = self.get_assembled_video_path(candidate_id, assessment_id)

        try:
            with open(assembled_path, "wb") as outfile:
                for i in range(total_chunks):
                    chunk_path = self.get_chunk_file_path(candidate_id, assessment_id, i)
                    if not os.path.exists(chunk_path):
                        raise MissingChunksError(missing_chunks=[i], total_chunks=total_chunks)
                    with open(chunk_path, "rb") as infile:
                        shutil.copyfileobj(infile, outfile)

            assembled_size = os.path.getsize(assembled_path)
            logger.info(
                "Successfully assembled %s chunks for assessment %s -> %s (%s bytes)",
                total_chunks, assessment_id, assembled_path, assembled_size
            )
            return assembled_path
        except MissingChunksError:
            raise
        except Exception as e:
            logger.error("Error assembling chunks for assessment %s: %s", assessment_id, str(e))
            raise MediaAssemblyError(f"Failed to assemble media chunks: {str(e)}")

    def extract_audio(
        self,
        video_path: str,
        output_audio_path: Optional[str] = None,
    ) -> str:
        """
        Extracts 16kHz mono audio.wav from the assembled video using ffmpeg.
        Raises AudioExtractionError if ffmpeg fails or video is invalid.
        """
        if not os.path.exists(video_path):
            raise AudioExtractionError(f"Source video path not found: {video_path}")

        if output_audio_path is None:
            dir_name = os.path.dirname(video_path)
            output_audio_path = os.path.join(dir_name, "audio.wav")

        ffmpeg_cmd = [
            settings.FFMPEG_PATH,
            "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", str(settings.AUDIO_SAMPLE_RATE),
            "-ac", str(settings.AUDIO_CHANNELS),
            output_audio_path,
        ]

        try:
            result = subprocess.run(
                ffmpeg_cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            logger.info("Successfully extracted audio via ffmpeg: %s", output_audio_path)
            return output_audio_path
        except Exception as e:
            logger.error("FFmpeg audio extraction failed: %s", str(e))
            raise AudioExtractionError(f"FFmpeg audio extraction failed: {str(e)}")

    def delete_local_file(self, file_path: str) -> bool:
        """Deletes a local file safely."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info("Deleted local file: %s", file_path)
                return True
            return False
        except Exception as e:
            logger.error("Failed to delete local file %s: %s", file_path, str(e))
            return False

    def delete_assessment_media(self, candidate_id: int, assessment_id: int) -> bool:
        """Deletes all local files and directories for an assessment."""
        try:
            assessment_dir = self.get_assessment_dir(candidate_id, assessment_id)
            if os.path.exists(assessment_dir):
                shutil.rmtree(assessment_dir)
                logger.info("Purged all local media for assessment %s", assessment_id)
                return True
            return False
        except Exception as e:
            logger.error("Failed to purge media for assessment %s: %s", assessment_id, str(e))
            return False

    def purge_candidate_data_gdpr(self, candidate_id: int) -> bool:
        """Purges entire candidate directory across all assessments (GDPR compliance)."""
        try:
            candidate_dir = os.path.join(self.base_path, str(candidate_id))
            if os.path.exists(candidate_dir):
                shutil.rmtree(candidate_dir)
                logger.info("GDPR Purge: Cleared all local media for candidate %s", candidate_id)
                return True
            return False
        except Exception as e:
            logger.error("Failed to perform GDPR purge for candidate %s: %s", candidate_id, str(e))
            return False

    def cleanup_abandoned_chunks(self, ttl_hours: Optional[int] = None) -> int:
        """Purges orphan chunk files older than TTL hours (default 24h)."""
        ttl = ttl_hours or settings.ABANDONED_CHUNK_TTL_HOURS
        cutoff_time = time.time() - (ttl * 3600)
        purged_count = 0

        if not os.path.exists(self.base_path):
            return 0

        for root, dirs, files in os.walk(self.base_path):
            if os.path.basename(root) == "chunks":
                for f in files:
                    file_path = os.path.join(root, f)
                    try:
                        if os.path.getmtime(file_path) < cutoff_time:
                            os.remove(file_path)
                            purged_count += 1
                    except Exception as e:
                        logger.warning("Error cleaning abandoned chunk %s: %s", file_path, str(e))

        logger.info("Pruned %s abandoned media chunks older than %s hours", purged_count, ttl)
        return purged_count


storage_service = StorageService()
