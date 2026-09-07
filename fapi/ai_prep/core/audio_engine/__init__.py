"""
Audio Engine Package Interface.
Exposes acoustic metrics, STT transcript metrics, VAD, and central AudioMetricsEngine.
"""
from .metrics_engine import AudioMetricsEngine
from .stt import transcribe_audio, get_whisper_model
from .audio_metrics import (
    calculate_avg_volume_db,
    calculate_mean_pitch_hz,
    calculate_silence_ratio,
    calculate_background_noise_level,
    detect_clipping,
    calculate_audio_metrics,
)
from .transcript_metrics import (
    calculate_speaking_duration_seconds,
    calculate_wpm,
    calculate_pause_count,
    calculate_filler_rate_per_min,
    calculate_transcript_metrics,
)
from .voice_activity_detector import VoiceActivityDetector
from .config import AUDIO_CONFIG, TRANSCRIPT_CONFIG, VAD_CONFIG

__all__ = [
    "AudioMetricsEngine",
    "transcribe_audio",
    "get_whisper_model",
    "calculate_avg_volume_db",
    "calculate_mean_pitch_hz",
    "calculate_silence_ratio",
    "calculate_background_noise_level",
    "detect_clipping",
    "calculate_audio_metrics",
    "calculate_speaking_duration_seconds",
    "calculate_wpm",
    "calculate_pause_count",
    "calculate_filler_rate_per_min",
    "calculate_transcript_metrics",
    "VoiceActivityDetector",
    "AUDIO_CONFIG",
    "TRANSCRIPT_CONFIG",
    "VAD_CONFIG",
]
