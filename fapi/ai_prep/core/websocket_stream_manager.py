"""
WebSocket Media Stream Manager for AI Prep.

Handles binary frame sequencing, disk buffering, ACK protocol, missing-frame
resend audits, and deterministic audio/video finalization without loading
full media files into server RAM.
"""

import os
import struct
import wave
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("wbl.ai_prep.websocket_stream_manager")

DEFAULT_SCRATCH_ROOT = Path(
    os.getenv(
        "AIPREP_SCRATCH_ROOT",
        os.path.join(os.getenv("AIPREP_LOCAL_STORAGE_DIR", "./storage/aiprep"), "scratch")
    )
)


class MissingFramesError(Exception):
    """Raised when finalize is invoked but some frames in the sequence are missing."""
    def __init__(self, missing_indices: List[int]):
        super().__init__(f"Cannot finalize media: missing {len(missing_indices)} frames: {missing_indices[:20]}...")
        self.missing_indices = missing_indices


class MediaTypeMismatchError(Exception):
    """Raised when client sends media format incompatible with DB configuration."""
    pass


class WebSocketStreamSession:
    """
    Manages an active real-time media ingestion session for an assessment.
    Directly writes individual frames to disk to maintain flat memory usage.
    """

    def __init__(
        self,
        candidate_id: Union[int, str],
        assessment_id: Union[int, str],
        expected_media_type: str,
        base_scratch_dir: Optional[Path] = None,
    ):
        self.candidate_id = int(candidate_id)
        self.assessment_id = int(assessment_id)
        self.expected_media_type = (expected_media_type or "VIDEO").upper().strip()

        scratch_root = base_scratch_dir or DEFAULT_SCRATCH_ROOT
        self.session_dir = scratch_root / f"assessment_{self.assessment_id}"
        self.frames_dir = self.session_dir / "frames"
        self.frames_dir.mkdir(parents=True, exist_ok=True)

        self.received_frames: Set[int] = set()
        self.total_bytes: int = 0
        self.is_finalized: bool = False
        self.final_media_path: Optional[str] = None

    def _frame_path(self, frame_idx: int) -> Path:
        return self.frames_dir / f"frame_{frame_idx:06d}.raw"

    def write_frame(self, frame_idx: int, data: bytes) -> int:
        """
        Appends or writes a single raw binary frame to disk.
        Thread-safe at file-level per sequence ID.
        """
        if frame_idx < 0:
            raise ValueError(f"Invalid negative frame index: {frame_idx}")
        if not data:
            return 0

        target_file = self._frame_path(frame_idx)
        with open(target_file, "wb") as f:
            f.write(data)

        self.received_frames.add(frame_idx)
        self.total_bytes += len(data)
        return len(data)

    def audit_frames(self, total_frames: int) -> List[int]:
        """
        Scans frames 0 to total_frames - 1.
        Returns a list of any missing frame sequence numbers.
        """
        missing: List[int] = []
        for idx in range(total_frames):
            if idx not in self.received_frames:
                target_file = self._frame_path(idx)
                if not target_file.exists():
                    missing.append(idx)
                else:
                    self.received_frames.add(idx)
        return missing

    def finalize(
        self,
        total_frames: int,
        audio_channels: int = 1,
        audio_sample_rate: int = 16000,
        audio_sample_width: int = 2,  # 16-bit PCM = 2 bytes
    ) -> str:
        """
        Concatenates all raw frames in sequence (0..total_frames-1) into final media file:
        - If AUDIO: Assembles standard 16kHz mono 16-bit WAV (audio.wav).
        - If VIDEO: Concatenates WebM slices into video.webm.
        """
        if total_frames <= 0:
            raise ValueError("total_frames must be greater than zero to finalize")

        missing = self.audit_frames(total_frames)
        if missing:
            raise MissingFramesError(missing)

        if self.expected_media_type == "AUDIO":
            output_file = self.session_dir / "audio.wav"
            logger.info("Finalizing %d audio frames into 16kHz WAV: %s", total_frames, output_file)
            with wave.open(str(output_file), "wb") as wf:
                wf.setnchannels(audio_channels)
                wf.setsampwidth(audio_sample_width)
                wf.setframerate(audio_sample_rate)
                for idx in range(total_frames):
                    frame_path = self._frame_path(idx)
                    with open(frame_path, "rb") as rf:
                        wf.writeframes(rf.read())
        else:
            output_file = self.session_dir / "video.webm"
            logger.info("Finalizing %d video frames into WebM: %s", total_frames, output_file)
            with open(output_file, "wb") as out_f:
                for idx in range(total_frames):
                    frame_path = self._frame_path(idx)
                    with open(frame_path, "rb") as rf:
                        shutil.copyfileobj(rf, out_f)

        self.final_media_path = str(output_file)
        self.is_finalized = True

        # Clean individual chunk files to save local disk space
        self.cleanup_frames()
        return self.final_media_path

    def cleanup_frames(self) -> None:
        """Removes individual raw frame files after stitching."""
        if self.frames_dir.exists():
            shutil.rmtree(self.frames_dir, ignore_errors=True)

    def cleanup_all(self) -> None:
        """Purges the entire scratch folder for this assessment."""
        if self.session_dir.exists():
            shutil.rmtree(self.session_dir, ignore_errors=True)


# Global active sessions lookup
_ACTIVE_SESSIONS: Dict[int, WebSocketStreamSession] = {}


def get_or_create_stream_session(
    candidate_id: Union[int, str],
    assessment_id: Union[int, str],
    expected_media_type: str,
    base_scratch_dir: Optional[Path] = None,
) -> WebSocketStreamSession:
    """Retrieves or instantiates the singleton stream session for an assessment."""
    ass_id_int = int(assessment_id)
    if ass_id_int not in _ACTIVE_SESSIONS:
        _ACTIVE_SESSIONS[ass_id_int] = WebSocketStreamSession(
            candidate_id=candidate_id,
            assessment_id=ass_id_int,
            expected_media_type=expected_media_type,
            base_scratch_dir=base_scratch_dir,
        )
    return _ACTIVE_SESSIONS[ass_id_int]


def get_stream_session(assessment_id: Union[int, str]) -> Optional[WebSocketStreamSession]:
    """Retrieves an existing stream session if active."""
    return _ACTIVE_SESSIONS.get(int(assessment_id))


def remove_stream_session(assessment_id: Union[int, str]) -> None:
    """Removes session reference upon completion."""
    _ACTIVE_SESSIONS.pop(int(assessment_id), None)


def get_preassembled_media_path(assessment_id: Union[int, str], expected_media_type: str = "VIDEO") -> Optional[str]:
    """
    Checks if a pre-assembled audio.wav or video.webm file exists on disk
    from a finished WebSocket stream session.
    """
    ass_id_int = int(assessment_id)
    session = _ACTIVE_SESSIONS.get(ass_id_int)
    if session and session.final_media_path and os.path.exists(session.final_media_path):
        return session.final_media_path

    target_dir = DEFAULT_SCRATCH_ROOT / f"assessment_{ass_id_int}"
    if expected_media_type.upper() in {"AUDIO", "AUDIO_ONLY"}:
        cand = target_dir / "audio.wav"
    else:
        cand = target_dir / "video.webm"

    if cand.exists() and cand.stat().st_size > 0:
        return str(cand)
    return None


def parse_binary_frame(packet: bytes) -> Tuple[int, bytes]:
    """
    Parses a binary frame formatted as [4-byte big-endian sequence number] + [media payload].
    Raises ValueError if packet is shorter than 4 bytes.
    """
    if len(packet) < 4:
        raise ValueError(f"Packet too short for binary frame header: {len(packet)} bytes (expected >= 4)")
    frame_idx = struct.unpack(">I", packet[:4])[0]
    payload = packet[4:]
    return frame_idx, payload
