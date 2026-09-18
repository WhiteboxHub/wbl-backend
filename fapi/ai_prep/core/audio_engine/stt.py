"""
Speech-to-Text module using faster-whisper.
Extracts verbatim text and word-level timestamps with start, end, and confidence scores.
Supports full-file transcription, live chunked streaming, global timestamp alignment,
and deterministic overlap deduplication.
"""
import os
import string
import tempfile
import threading
import logging
import time
from typing import Dict, Any, List, Optional, Tuple, Union
import numpy as np
from faster_whisper import WhisperModel

logger = logging.getLogger("wbl.ai_prep.audio_engine.stt")

_WHISPER_MODELS: Dict[Tuple[str, str, str], WhisperModel] = {}
_MODEL_LOCK = threading.Lock()


def get_whisper_model(
    model_size: str = "base",
    device: str = "cpu",
    compute_type: str = "int8",
) -> WhisperModel:
    """Returns singleton cached instance of WhisperModel keyed by configuration."""
    key = (model_size, device, compute_type)
    with _MODEL_LOCK:
        if key not in _WHISPER_MODELS:
            logger.info(f"Loading faster-whisper model '{model_size}' on {device} ({compute_type})...")
            _WHISPER_MODELS[key] = WhisperModel(model_size, device=device, compute_type=compute_type)
        return _WHISPER_MODELS[key]


def _clean_word_token(word: str) -> str:
    """Normalizes word string for matching by removing punctuation and converting to lowercase."""
    if not word:
        return ""
    return word.lower().strip(string.punctuation + " \t\n\r")


def merge_word_timestamps(
    existing_words: List[Dict[str, Any]],
    new_chunk_words: List[Dict[str, Any]],
    overlap_window_sec: float = 3.0,
) -> List[Dict[str, Any]]:
    """
    Deterministically merges two sets of global word timestamps from overlapping audio chunks.
    Uses suffix-prefix sequence alignment within the temporal overlap window.
    """
    if not existing_words:
        return [dict(w) for w in (new_chunk_words or [])]
    if not new_chunk_words:
        return [dict(w) for w in existing_words]

    def _is_valid(w):
        return isinstance(w, dict) and "word" in w and "start" in w and "end" in w and w["end"] >= w["start"]

    existing = [dict(w) for w in existing_words if _is_valid(w)]
    incoming = [dict(w) for w in new_chunk_words if _is_valid(w)]

    if not existing:
        return incoming
    if not incoming:
        return existing

    existing.sort(key=lambda x: x["start"])
    incoming.sort(key=lambda x: x["start"])

    first_incoming_start = incoming[0]["start"]
    last_existing_end = existing[-1]["end"]

    # If incoming chunk starts after existing audio with no overlap, append directly
    if first_incoming_start >= last_existing_end:
        return existing + incoming

    # Identify candidate overlap region
    overlap_threshold = max(0.0, first_incoming_start - 0.5)
    suffix_start_idx = len(existing)
    for idx in range(len(existing) - 1, -1, -1):
        if existing[idx]["start"] >= overlap_threshold or (last_existing_end - existing[idx]["end"]) <= overlap_window_sec:
            suffix_start_idx = idx
        else:
            break

    existing_suffix = existing[suffix_start_idx:]
    
    prefix_end_idx = 0
    for idx, w in enumerate(incoming):
        if w["start"] <= (last_existing_end + 0.5):
            prefix_end_idx = idx + 1
        else:
            break
    incoming_prefix = incoming[:prefix_end_idx] if prefix_end_idx > 0 else incoming

    clean_suffix = [_clean_word_token(w["word"]) for w in existing_suffix]
    clean_prefix = [_clean_word_token(w["word"]) for w in incoming_prefix]

    # Find longest matching sequence between suffix of existing and prefix of incoming
    best_match_len = 0
    best_suffix_offset = len(clean_suffix)
    best_prefix_offset = 0

    max_possible = min(len(clean_suffix), len(clean_prefix))
    for match_len in range(max_possible, 0, -1):
        for s_idx in range(len(clean_suffix) - match_len + 1):
            if clean_suffix[s_idx:s_idx + match_len] == clean_prefix[:match_len]:
                best_match_len = match_len
                best_suffix_offset = s_idx
                best_prefix_offset = match_len
                break
        if best_match_len > 0:
            break

    if best_match_len > 0:
        matched_existing_start = suffix_start_idx + best_suffix_offset
        result = existing[:matched_existing_start]

        # For overlapping words, pick the higher-confidence timestamp
        for i in range(best_match_len):
            ex_w = existing[matched_existing_start + i]
            inc_w = incoming[i]
            chosen = inc_w if inc_w.get("probability", 0.0) >= ex_w.get("probability", 0.0) else ex_w
            result.append(chosen)

        result.extend(incoming[best_prefix_offset:])
        return result
    else:
        # Non-conflicting timeline fallback
        cutoff_time = existing[-1]["start"] + 0.05
        filtered_incoming = [w for w in incoming if w["start"] >= cutoff_time]
        return existing + filtered_incoming


def transcribe_audio_chunk(
    audio_input: Union[str, bytes, np.ndarray],
    chunk_start_time: float = 0.0,
    model_size: str = "base",
    device: str = "cpu",
    compute_type: str = "int8",
) -> Dict[str, Any]:
    """Transcribes a single audio chunk and maps word timestamps to the global recording timeline."""
    model = get_whisper_model(model_size=model_size, device=device, compute_type=compute_type)

    temp_file = None
    audio_target = audio_input

    if isinstance(audio_input, bytes):
        suffix = ".webm" if audio_input[:4] == b"\x1a\x45\xdf\xa3" else ".wav"
        temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        temp_file.write(audio_input)
        temp_file.flush()
        temp_file.close()
        audio_target = temp_file.name
    elif isinstance(audio_input, np.ndarray):
        audio_target = audio_input.astype(np.float32)

    try:
        segments, info = model.transcribe(
            audio_target,
            beam_size=5,
            temperature=0.0,
            condition_on_previous_text=False,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        full_transcript_parts = []
        global_word_timestamps: List[Dict[str, Any]] = []

        for segment in segments:
            full_transcript_parts.append(segment.text.strip())
            if segment.words:
                for w in segment.words:
                    word_str = w.word.strip()
                    if word_str:
                        global_word_timestamps.append({
                            "word": word_str,
                            "start": round(chunk_start_time + w.start, 2),
                            "end": round(chunk_start_time + w.end, 2),
                            "probability": round(w.probability, 2),
                        })

        chunk_transcript = " ".join(full_transcript_parts).strip()

        return {
            "transcript_text": chunk_transcript,
            "word_timestamps": global_word_timestamps,
            "language": getattr(info, "language", "en"),
            "language_probability": round(getattr(info, "language_probability", 1.0), 2),
            "duration": round(getattr(info, "duration", 0.0), 2),
            "chunk_start_time": chunk_start_time,
        }
    finally:
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.remove(temp_file.name)
            except OSError:
                pass


def transcribe_audio(
    audio_path: str,
    model_size: str = "base",
    device: str = "cpu",
    compute_type: str = "int8",
) -> Dict[str, Any]:
    """Transcribes complete audio file to text with word-level timestamps."""
    return transcribe_audio_chunk(
        audio_input=audio_path,
        chunk_start_time=0.0,
        model_size=model_size,
        device=device,
        compute_type=compute_type,
    )
class LiveSTTStore:
    """Thread-safe in-memory session manager for live chunked STT streams with TTL auto-cleanup."""
    _lock = threading.Lock()
    _sessions: Dict[Union[int, str], Dict[str, Any]] = {}
    SESSION_TTL_SECONDS: float = 3600.0  # 1 hour auto-expiration
    @classmethod
    def _cleanup_expired_sessions_locked(cls) -> None:
        """Evicts sessions that have been inactive for more than SESSION_TTL_SECONDS."""
        now = time.time()
        expired = [
            sid for sid, data in cls._sessions.items()
            if now - data.get("last_updated", now) > cls.SESSION_TTL_SECONDS
        ]
        for sid in expired:
            del cls._sessions[sid]
    @classmethod
    def add_chunk(
        cls,
        session_id: Union[int, str],
        audio_input: Union[str, bytes, np.ndarray],
        chunk_start_time: float = 0.0,
        chunk_index: Optional[int] = None,
        model_size: str = "base",
    ) -> Dict[str, Any]:
        chunk_result = transcribe_audio_chunk(
            audio_input=audio_input,
            chunk_start_time=chunk_start_time,
            model_size=model_size,
        )
        with cls._lock:
            # Auto-purge abandoned sessions
            cls._cleanup_expired_sessions_locked()
            if session_id not in cls._sessions:
                cls._sessions[session_id] = {
                    "word_timestamps": [],
                    "chunks_count": 0,
                    "last_chunk_start": 0.0,
                    "last_updated": time.time(),
                }
            session = cls._sessions[session_id]
            merged_words = merge_word_timestamps(
                existing_words=session["word_timestamps"],
                new_chunk_words=chunk_result["word_timestamps"],
            )
            session["word_timestamps"] = merged_words
            session["chunks_count"] += 1
            session["last_chunk_start"] = chunk_start_time
            session["last_updated"] = time.time()
            live_transcript = " ".join(w["word"] for w in merged_words).strip()
            session["live_transcript"] = live_transcript
        return {
            "session_id": session_id,
            "chunk_index": chunk_index,
            "chunk_transcript": chunk_result["transcript_text"],
            "live_transcript": live_transcript,
            "words_count": len(merged_words),
            "chunk_words_count": len(chunk_result["word_timestamps"]),
        }

    @classmethod
    def get_live_transcript(cls, session_id: Union[int, str]) -> str:
        with cls._lock:
            session = cls._sessions.get(session_id)
            return session.get("live_transcript", "") if session else ""

    @classmethod
    def get_temporary_word_timestamps(cls, session_id: Union[int, str]) -> List[Dict[str, Any]]:
        with cls._lock:
            session = cls._sessions.get(session_id)
            return list(session.get("word_timestamps", [])) if session else []

    @classmethod
    def finalize_session(cls, session_id: Union[int, str]) -> Tuple[str, List[Dict[str, Any]]]:
        with cls._lock:
            session = cls._sessions.get(session_id)
            if not session:
                return "", []
            return session.get("live_transcript", ""), list(session.get("word_timestamps", []))

    @classmethod
    def clear_session(cls, session_id: Union[int, str]) -> None:
        """Purges word timestamps and releases session memory."""
        with cls._lock:
            if session_id in cls._sessions:
                del cls._sessions[session_id]
