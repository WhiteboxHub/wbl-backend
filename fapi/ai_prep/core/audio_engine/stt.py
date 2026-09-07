"""
Speech-to-Text module using faster-whisper.
Extracts verbatim text and word-level timestamps with start, end, and confidence scores.
"""
import os
import logging
from typing import Dict, Any, List
from faster_whisper import WhisperModel

logger = logging.getLogger("wbl.ai_prep.audio_engine.stt")

_WHISPER_MODEL = None


def get_whisper_model(model_size: str = "base", device: str = "cpu", compute_type: str = "int8") -> WhisperModel:
    """Returns singleton cached instance of WhisperModel."""
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        logger.info(f"Loading faster-whisper model '{model_size}' on {device} ({compute_type})...")
        _WHISPER_MODEL = WhisperModel(model_size, device=device, compute_type=compute_type)
    return _WHISPER_MODEL


def transcribe_audio(
    audio_path: str,
    model_size: str = "base",
    device: str = "cpu",
    compute_type: str = "int8",
) -> Dict[str, Any]:
    """
    Transcribes audio file to text with word-level timestamps.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found at path: {audio_path}")

    model = get_whisper_model(model_size=model_size, device=device, compute_type=compute_type)

    segments, info = model.transcribe(
        audio_path,
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    full_transcript_parts = []
    word_timestamps: List[Dict[str, Any]] = []

    for segment in segments:
        full_transcript_parts.append(segment.text.strip())
        if segment.words:
            for w in segment.words:
                word_timestamps.append({
                    "word": w.word.strip(),
                    "start": round(w.start, 2),
                    "end": round(w.end, 2),
                    "probability": round(w.probability, 2),
                })

    transcript_text = " ".join(full_transcript_parts).strip()

    return {
        "transcript_text": transcript_text,
        "word_timestamps": word_timestamps,
        "language": info.language,
        "language_probability": round(info.language_probability, 2),
        "duration": round(info.duration, 2),
    }
