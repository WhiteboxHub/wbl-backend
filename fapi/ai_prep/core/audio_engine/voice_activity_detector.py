"""
Voice Activity Detection (VAD) Engine.
Frame-level Short-Time Energy (STE) implementation using NumPy/SciPy without external heavy dependencies.
"""
import numpy as np
from typing import Dict, Any, List, Tuple
from .config import VAD_CONFIG


class VoiceActivityDetector:
    """
    Computes speech vs. non-speech frames, silence ratios, and sample intervals.
    """

    def __init__(
        self,
        sr: int = 16000,
        frame_ms: int = VAD_CONFIG.FRAME_MS,
        hop_ms: int = VAD_CONFIG.HOP_MS,
        min_speech_ms: int = VAD_CONFIG.MIN_SPEECH_DURATION_MS,
        min_silence_ms: int = VAD_CONFIG.MIN_SILENCE_DURATION_MS,
        energy_percentile: float = VAD_CONFIG.ENERGY_THRESHOLD_PERCENTILE,
    ):
        self.sr = sr
        self.frame_len = int(sr * (frame_ms / 1000.0))
        self.hop_len = int(sr * (hop_ms / 1000.0))
        self.min_speech_frames = max(1, int(min_speech_ms / hop_ms))
        self.min_silence_frames = max(1, int(min_silence_ms / hop_ms))
        self.energy_percentile = energy_percentile

    def process(self, y: np.ndarray) -> Dict[str, Any]:
        """
        Processes audio array and returns speech/silence metrics and boolean mask.
        """
        if y is None or len(y) == 0:
            return {
                "speech_duration_sec": 0.0,
                "silence_duration_sec": 0.0,
                "silence_ratio": 0.0,
                "speech_intervals": [],
                "silence_intervals": [],
                "non_speech_mask": np.array([], dtype=bool),
            }

        total_duration = len(y) / self.sr

        # 1. Compute frame-level Root-Mean-Square (RMS) Energy
        num_frames = max(1, int(np.ceil((len(y) - self.frame_len) / self.hop_len)) + 1)
        pad_len = max(0, (num_frames - 1) * self.hop_len + self.frame_len - len(y))
        y_padded = np.pad(y, (0, pad_len), mode="constant")

        # Vectorized frame extraction
        frames = np.lib.stride_tricks.sliding_window_view(
            y_padded, window_shape=self.frame_len
        )[:: self.hop_len]
        frame_rms = np.sqrt(np.mean(frames**2, axis=1) + 1e-12)

        # 2. Adaptive thresholding
        min_energy = np.min(frame_rms)
        max_energy = np.max(frame_rms)

        if max_energy - min_energy < 1e-6:
            # Completely uniform signal (e.g. digital silence)
            is_speech_frame = np.zeros(len(frame_rms), dtype=bool)
        else:
            dyn_thresh = np.percentile(frame_rms, self.energy_percentile)
            is_speech_frame = frame_rms > dyn_thresh

        # 3. Morphological smoothing
        smoothed_speech = self._smooth_detections(
            is_speech_frame, self.min_speech_frames, self.min_silence_frames
        )

        # 4. Construct intervals
        speech_intervals = self._mask_to_intervals(smoothed_speech, self.hop_len, self.sr)
        silence_intervals = self._mask_to_intervals(~smoothed_speech, self.hop_len, self.sr)

        speech_duration = sum(end - start for start, end in speech_intervals)
        speech_duration = min(total_duration, max(0.0, speech_duration))
        silence_duration = max(0.0, total_duration - speech_duration)
        silence_ratio = round(silence_duration / total_duration, 4) if total_duration > 0 else 0.0

        # 5. Expand frame mask to sample-level non-speech mask
        sample_speech_mask = np.repeat(smoothed_speech, self.hop_len)[: len(y)]
        if len(sample_speech_mask) < len(y):
            sample_speech_mask = np.pad(
                sample_speech_mask, (0, len(y) - len(sample_speech_mask)), mode="edge"
            )
        non_speech_mask = ~sample_speech_mask

        return {
            "speech_duration_sec": round(speech_duration, 3),
            "silence_duration_sec": round(silence_duration, 3),
            "silence_ratio": silence_ratio,
            "speech_intervals": speech_intervals,
            "silence_intervals": silence_intervals,
            "non_speech_mask": non_speech_mask,
        }

    def _smooth_detections(self, mask: np.ndarray, min_speech: int, min_silence: int) -> np.ndarray:
        res = mask.copy()
        n = len(res)
        i = 0
        while i < n:
            val = res[i]
            j = i
            while j < n and res[j] == val:
                j += 1
            length = j - i
            if val and length < min_speech:
                res[i:j] = False
            elif not val and length < min_silence:
                res[i:j] = True
            i = j
        return res

    def _mask_to_intervals(self, mask: np.ndarray, hop_len: int, sr: int) -> List[Tuple[float, float]]:
        intervals = []
        n = len(mask)
        i = 0
        while i < n:
            if mask[i]:
                start_frame = i
                while i < n and mask[i]:
                    i += 1
                end_frame = i
                intervals.append((
                    round((start_frame * hop_len) / sr, 3),
                    round((end_frame * hop_len) / sr, 3),
                ))
            else:
                i += 1
        return intervals
