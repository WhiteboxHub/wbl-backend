"""
Centralized Configuration for Audio & Speech Telemetry Engine.
Defines constants, thresholds, and lexicons for acoustic processing, VAD, and STT metrics.
"""
from dataclasses import dataclass, field
from typing import Set


@dataclass(frozen=True)
class AudioConfig:
    """Acoustic waveform analysis parameters."""
    SAMPLE_RATE: int = 16000
    MIN_DBFS: float = -100.0
    CLIPPING_THRESHOLD: float = 0.99
    
    # Pitch (pYIN) settings
    PITCH_FMIN_HZ: float = 65.0
    PITCH_FMAX_HZ: float = 400.0
    PITCH_HOP_LENGTH: int = 1024          # librosa.pyin hop_length (optimized for vocal pitch speed)
    VOICING_THRESHOLD: float = 0.5
    MIN_VOICED_DURATION_SEC: float = 0.3
    IQR_MULTIPLIER: float = 1.5
    
    # Background Noise Classification (dBFS)
    NOISE_FLOOR_LOW_MAX_DB: float = -45.0
    NOISE_FLOOR_MED_MAX_DB: float = -30.0


@dataclass(frozen=True)
class VADConfig:
    """Voice Activity Detection parameters."""
    FRAME_MS: int = 30
    HOP_MS: int = 10
    MIN_SPEECH_DURATION_MS: int = 100
    MIN_SILENCE_DURATION_MS: int = 200
    ENERGY_THRESHOLD_PERCENTILE: float = 35.0


@dataclass(frozen=True)
class TranscriptConfig:
    """Transcript linguistic and timing metrics parameters."""
    DEFAULT_PAUSE_THRESHOLD_SEC: float = 0.8
    MIN_WORD_DURATION_SEC: float = 0.05
    
    # Pure filler words (always counted as fillers)
    PURE_FILLERS: Set[str] = field(default_factory=lambda: {
        "um", "uh", "er", "ah", "hmm", "uhm", "umm", "erm"
    })
    
    # Contextual discourse markers / crutch phrases
    CONTEXTUAL_FILLERS: Set[str] = field(default_factory=lambda: {
        "like", "actually", "basically", "literally", "you know",
        "i mean", "right", "sort of", "kind of", "to be honest"
    })


AUDIO_CONFIG = AudioConfig()
VAD_CONFIG = VADConfig()
TRANSCRIPT_CONFIG = TranscriptConfig()
