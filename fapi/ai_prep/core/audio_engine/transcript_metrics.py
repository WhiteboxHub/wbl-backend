"""
Transcript Metrics Module.
Calculates speaking duration, WPM, pauses, and filler words purely from text and STT timestamps.
ZERO librosa or audio library dependencies.
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from .config import TRANSCRIPT_CONFIG


def calculate_speaking_duration_seconds(
    word_timestamps: Optional[List[Dict[str, Any]]],
    total_recording_duration: Optional[float] = None,
    pause_threshold_sec: float = TRANSCRIPT_CONFIG.DEFAULT_PAUSE_THRESHOLD_SEC,
) -> float:
    """
    Calculates active speaking duration excluding pauses >= pause_threshold_sec.
    """
    if not word_timestamps:
        return round(total_recording_duration, 2) if total_recording_duration is not None else 0.0

    valid_words = [
        w for w in word_timestamps
        if isinstance(w, dict) and "start" in w and "end" in w and w["end"] >= w["start"]
    ]

    if not valid_words:
        return round(total_recording_duration, 2) if total_recording_duration is not None else 0.0

    valid_words.sort(key=lambda x: x["start"])

    active_duration = 0.0
    current_segment_start = valid_words[0]["start"]
    current_segment_end = valid_words[0]["end"]

    for i in range(1, len(valid_words)):
        w = valid_words[i]
        gap = w["start"] - current_segment_end

        if gap >= pause_threshold_sec:
            active_duration += current_segment_end - current_segment_start
            current_segment_start = w["start"]
            current_segment_end = w["end"]
        else:
            current_segment_end = max(current_segment_end, w["end"])

    active_duration += current_segment_end - current_segment_start

    if total_recording_duration is not None:
        active_duration = min(active_duration, total_recording_duration)

    return round(max(0.0, active_duration), 2)


def calculate_wpm(word_count: int, speaking_duration_seconds: float) -> int:
    """Calculates speaking pace in words per minute."""
    if speaking_duration_seconds <= 0.0 or word_count <= 0:
        return 0
    wpm = (word_count / speaking_duration_seconds) * 60.0
    return int(round(wpm))


def calculate_pause_count(
    word_timestamps: Optional[List[Dict[str, Any]]],
    pause_threshold_sec: float = TRANSCRIPT_CONFIG.DEFAULT_PAUSE_THRESHOLD_SEC,
) -> int:
    """Counts significant hesitation pauses >= pause_threshold_sec."""
    if not word_timestamps or len(word_timestamps) < 2:
        return 0

    valid_words = [
        w for w in word_timestamps
        if isinstance(w, dict) and "start" in w and "end" in w and w["end"] >= w["start"]
    ]
    valid_words.sort(key=lambda x: x["start"])

    pause_count = 0
    prev_end = valid_words[0]["end"]

    for w in valid_words[1:]:
        gap = w["start"] - prev_end
        if gap >= pause_threshold_sec:
            pause_count += 1
        prev_end = max(prev_end, w["end"])

    return pause_count


def calculate_filler_rate_per_min(
    transcript_text: str,
    speaking_duration_seconds: float,
) -> Tuple[float, int, Dict[str, int]]:
    """
    Detects pure fillers and contextual discourse markers.
    Returns: (filler_rate_per_min, filler_count, filler_breakdown)
    """
    if not transcript_text or not transcript_text.strip():
        return 0.0, 0, {}

    clean_text = transcript_text.lower()
    words = re.findall(r"\b[a-z']+\b", clean_text)
    total_words = len(words)

    if total_words == 0:
        return 0.0, 0, {}

    filler_breakdown: Dict[str, int] = {}
    filler_count = 0

    # 1. Check pure fillers
    for word in words:
        if word in TRANSCRIPT_CONFIG.PURE_FILLERS:
            filler_breakdown[word] = filler_breakdown.get(word, 0) + 1
            filler_count += 1

    # 2. Check contextual multi-word & single-word crutch phrases
    for cm in TRANSCRIPT_CONFIG.CONTEXTUAL_FILLERS:
        pattern = r"\b" + re.escape(cm) + r"\b"
        matches = re.findall(pattern, clean_text)
        if matches:
            count = len(matches)
            if cm == "like":
                # Only count excessive 'like' occurrences as fillers
                if count > 2:
                    filler_breakdown[cm] = count
                    filler_count += count
            else:
                filler_breakdown[cm] = count
                filler_count += count

    minutes = speaking_duration_seconds / 60.0 if speaking_duration_seconds > 0 else 0.0
    filler_rate = round(filler_count / minutes, 2) if minutes > 0 else 0.0

    return filler_rate, filler_count, filler_breakdown


def calculate_transcript_metrics(
    transcript_text: str,
    word_timestamps: Optional[List[Dict[str, Any]]] = None,
    total_recording_duration: Optional[float] = None,
    pause_threshold_sec: float = TRANSCRIPT_CONFIG.DEFAULT_PAUSE_THRESHOLD_SEC,
) -> Dict[str, Any]:
    """
    Unified entry point for transcript & timing metrics.
    """
    tokens = re.findall(r"\b[a-zA-Z0-9']+\b", transcript_text) if transcript_text else []
    word_count = len(tokens)

    speaking_duration_seconds = calculate_speaking_duration_seconds(
        word_timestamps=word_timestamps,
        total_recording_duration=total_recording_duration,
        pause_threshold_sec=pause_threshold_sec,
    )

    if speaking_duration_seconds == 0.0 and total_recording_duration:
        speaking_duration_seconds = round(total_recording_duration, 2)

    wpm = calculate_wpm(word_count, speaking_duration_seconds)
    pause_count = calculate_pause_count(word_timestamps, pause_threshold_sec=pause_threshold_sec)
    filler_rate_per_min, filler_count, filler_breakdown = calculate_filler_rate_per_min(
        transcript_text=transcript_text,
        speaking_duration_seconds=speaking_duration_seconds,
    )

    return {
        "filler_rate_per_min": filler_rate_per_min,
        "filler_count": filler_count,
        "filler_breakdown": filler_breakdown,
        "pause_count": pause_count,
        "wpm": wpm,
        "speaking_duration_seconds": speaking_duration_seconds,
    }
