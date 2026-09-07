"""
Acoustic Signal Processing Metrics Module.
Calculates waveform loudness, outlier-rejected pitch, VAD silence ratio, and background noise level.
Does NOT import or depend on Whisper / STT / transcript data.
"""
import logging
import math
import numpy as np
import librosa
import soundfile as sf
from typing import Dict, Any, Optional, Union
from .config import AUDIO_CONFIG
from .voice_activity_detector import VoiceActivityDetector

logger = logging.getLogger("wbl.ai_prep.audio_engine.audio_metrics")


def calculate_avg_volume_db(y: np.ndarray) -> float:
    """
    Calculates average audio loudness/volume in RMS dBFS.
    Deterministic, handles silence safely, never returns NaN or Inf.
    """
    if y is None or len(y) == 0:
        return AUDIO_CONFIG.MIN_DBFS

    rms = np.sqrt(np.mean(y.astype(np.float64) ** 2))
    if rms < 1e-5:
        return AUDIO_CONFIG.MIN_DBFS

    db = 20.0 * math.log10(rms)
    return round(float(np.clip(db, AUDIO_CONFIG.MIN_DBFS, 0.0)), 2)


def calculate_mean_pitch_hz(
    y: np.ndarray,
    sr: int = AUDIO_CONFIG.SAMPLE_RATE,
    fmin: float = AUDIO_CONFIG.PITCH_FMIN_HZ,
    fmax: float = AUDIO_CONFIG.PITCH_FMAX_HZ,
) -> Optional[float]:
    """
    Calculates fundamental pitch (F0) using librosa.pyin with IQR outlier rejection.
    Returns None if voiced speech duration is insufficient or unvoiced.
    """
    if y is None or len(y) < int(sr * AUDIO_CONFIG.MIN_VOICED_DURATION_SEC):
        return None

    try:
        f0, voiced_flag, voiced_probs = librosa.pyin(
            y,
            fmin=fmin,
            fmax=fmax,
            sr=sr,
            hop_length=AUDIO_CONFIG.PITCH_HOP_LENGTH,
        )

        valid_f0 = f0[voiced_flag & (voiced_probs >= AUDIO_CONFIG.VOICING_THRESHOLD) & ~np.isnan(f0) & (f0 >= fmin) & (f0 <= fmax)]
        if len(valid_f0) == 0:
            return None

        # Voiced duration check (use raw voiced_flag, not filtered valid_f0,
        # to avoid falsely rejecting long speech where strict filtering reduces frame count)
        hop_length = AUDIO_CONFIG.PITCH_HOP_LENGTH
        voiced_duration = (int(np.sum(voiced_flag)) * hop_length) / sr
        if voiced_duration < AUDIO_CONFIG.MIN_VOICED_DURATION_SEC:
            return None

        # Outlier rejection via Interquartile Range (IQR)
        q25, q75 = np.percentile(valid_f0, [25, 75])
        iqr = q75 - q25
        lower_bound = q25 - (AUDIO_CONFIG.IQR_MULTIPLIER * iqr)
        upper_bound = q75 + (AUDIO_CONFIG.IQR_MULTIPLIER * iqr)

        filtered_f0 = valid_f0[(valid_f0 >= lower_bound) & (valid_f0 <= upper_bound)]
        if len(filtered_f0) == 0:
            filtered_f0 = valid_f0

        return round(float(np.mean(filtered_f0)), 1)
    except Exception as e:
        logger.warning(f"Error calculating pitch: {e}")
        return None


def calculate_silence_ratio(y: np.ndarray, sr: int = AUDIO_CONFIG.SAMPLE_RATE) -> float:
    """
    Calculates proportion of recording that is silence (0.0 - 1.0) using VAD.
    """
    if y is None or len(y) == 0:
        return 1.0

    vad = VoiceActivityDetector(sr=sr)
    res = vad.process(y)
    return float(res["silence_ratio"])


def calculate_background_noise_level(
    y: np.ndarray,
    sr: int = AUDIO_CONFIG.SAMPLE_RATE,
    vad_res: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Estimates background noise floor level from non-speech regions.
    Returns: 'LOW', 'MEDIUM', or 'HIGH'.
    """
    if y is None or len(y) == 0:
        return "LOW"

    if vad_res is None:
        vad = VoiceActivityDetector(sr=sr)
        vad_res = vad.process(y)

    non_speech_mask = vad_res.get("non_speech_mask")
    if non_speech_mask is not None and np.sum(non_speech_mask) > int(sr * 0.1):
        noise_samples = y[non_speech_mask]
        noise_db = calculate_avg_volume_db(noise_samples)
    else:
        sorted_sq = np.sort(y**2)
        bottom_10_pct = sorted_sq[: max(1, int(len(sorted_sq) * 0.1))]
        rms = np.sqrt(np.mean(bottom_10_pct) + 1e-12)
        noise_db = 20.0 * math.log10(rms) if rms > 1e-5 else AUDIO_CONFIG.MIN_DBFS

    if noise_db < AUDIO_CONFIG.NOISE_FLOOR_LOW_MAX_DB:
        return "LOW"
    elif noise_db < AUDIO_CONFIG.NOISE_FLOOR_MED_MAX_DB:
        return "MEDIUM"
    else:
        return "HIGH"


def detect_clipping(y: np.ndarray, threshold: float = AUDIO_CONFIG.CLIPPING_THRESHOLD) -> bool:
    """Detects peak sample saturation clipping."""
    if y is None or len(y) == 0:
        return False
    return bool(np.max(np.abs(y)) >= threshold)


def calculate_audio_metrics(
    audio_input: Union[str, np.ndarray],
    sr: int = AUDIO_CONFIG.SAMPLE_RATE,
) -> Dict[str, Any]:
    """
    Unified entry point for pure acoustic waveform metrics.
    """
    if isinstance(audio_input, str):
        try:
            y, file_sr = sf.read(audio_input, dtype="float32")
            if y.ndim > 1:
                y = np.mean(y, axis=1)
            if file_sr != sr:
                y = librosa.resample(y, orig_sr=file_sr, target_sr=sr)
        except Exception:
            y, _ = librosa.load(audio_input, sr=sr, mono=True)
    else:
        y = audio_input.astype(np.float32)

    total_duration = len(y) / sr if sr > 0 else 0.0

    vad = VoiceActivityDetector(sr=sr)
    vad_res = vad.process(y)

    avg_volume_db = calculate_avg_volume_db(y)
    mean_pitch_hz = calculate_mean_pitch_hz(y, sr=sr)
    silence_ratio = vad_res["silence_ratio"]
    background_noise_level = calculate_background_noise_level(y, sr=sr, vad_res=vad_res)
    clipping_detected = detect_clipping(y)

    return {
        "avg_volume_db": avg_volume_db,
        "mean_pitch_hz": mean_pitch_hz,
        "silence_ratio": silence_ratio,
        "background_noise_level": background_noise_level,
        "clipping_detected": clipping_detected,
        "total_audio_duration_seconds": round(total_duration, 2),
    }
