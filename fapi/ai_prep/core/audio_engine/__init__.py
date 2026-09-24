"""
Audio Engine Package Interface.
Exposes acoustic metrics, STT transcript metrics, VAD, transcription providers, and central AudioMetricsEngine.
"""
from .metrics_engine import AudioMetricsEngine
from .providers import (
    BaseTranscriptionProvider,
    WhisperTranscriptionProvider,
    SocketTranscriptionProvider,
    BrowserTranscriptionProvider,
    get_transcription_provider,
    TranscriptionProviderError,
    InvalidProviderConfigError,
)
from .stt import (
    transcribe_audio,
    transcribe_audio_chunk,
    merge_word_timestamps,
    get_whisper_model,
    LiveSTTStore,
)
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
from .config import AUDIO_CONFIG, TRANSCRIPT_CONFIG, VAD_CONFIG, TRANSCRIPTION_CONFIG

__all__ = [
    "AudioMetricsEngine",
    "BaseTranscriptionProvider",
    "WhisperTranscriptionProvider",
    "SocketTranscriptionProvider",
    "BrowserTranscriptionProvider",
    "get_transcription_provider",
    "TranscriptionProviderError",
    "InvalidProviderConfigError",
    "transcribe_audio",
    "transcribe_audio_chunk",
    "merge_word_timestamps",
    "LiveSTTStore",
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
    "TRANSCRIPTION_CONFIG",
]
