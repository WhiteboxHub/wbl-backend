"""
Comprehensive Unit Test Suite for AIPrep Audio Engine.
Covers:
- Acoustic metrics (volume, pitch with IQR outlier rejection, VAD silence ratio, background noise, clipping)
- Transcript metrics (speaking duration, WPM, pause count, filler word detection)
- VoiceActivityDetector (speech/silence intervals and masks)
- AudioMetricsEngine orchestration pipeline
"""
import unittest
from unittest.mock import patch, MagicMock
import numpy as np

from fapi.ai_prep.core.audio_engine.config import AUDIO_CONFIG, TRANSCRIPT_CONFIG
from fapi.ai_prep.core.audio_engine.voice_activity_detector import VoiceActivityDetector
from fapi.ai_prep.core.audio_engine.audio_metrics import (
    calculate_avg_volume_db,
    calculate_mean_pitch_hz,
    calculate_silence_ratio,
    calculate_background_noise_level,
    detect_clipping,
    calculate_audio_metrics,
)
from fapi.ai_prep.core.audio_engine.transcript_metrics import (
    calculate_speaking_duration_seconds,
    calculate_wpm,
    calculate_pause_count,
    calculate_filler_rate_per_min,
    calculate_transcript_metrics,
)
from fapi.ai_prep.core.audio_engine.metrics_engine import AudioMetricsEngine


class TestAudioMetrics(unittest.TestCase):
    """Test suite for acoustic signal processing (audio_metrics.py)."""

    def setUp(self):
        self.sr = 16000

    def test_volume_silence_and_empty(self):
        """Volume of empty or zero signal should be clamped to MIN_DBFS (-100.0)."""
        self.assertEqual(calculate_avg_volume_db(np.array([])), -100.0)
        self.assertEqual(calculate_avg_volume_db(np.zeros(16000)), -100.0)

    def test_volume_normal_sine(self):
        """Volume of 0.5 peak sine wave should be around -9 dBFS."""
        t = np.linspace(0, 1.0, self.sr, endpoint=False)
        sine = 0.5 * np.sin(2 * np.pi * 440 * t)
        vol = calculate_avg_volume_db(sine)
        self.assertAlmostEqual(vol, -9.03, delta=1.0)

    def test_clipping_detection(self):
        """Clipping should be True if peak sample reaches >= 0.99."""
        clean = np.array([0.1, 0.5, -0.8, 0.95], dtype=np.float32)
        clipped = np.array([0.1, 0.5, -1.0, 0.95], dtype=np.float32)
        self.assertFalse(detect_clipping(clean))
        self.assertTrue(detect_clipping(clipped))

    def test_pitch_sine_wave(self):
        """Pitch calculation of 200 Hz pure tone should be ~200 Hz."""
        t = np.linspace(0, 1.0, self.sr, endpoint=False)
        sine = 0.8 * np.sin(2 * np.pi * 200 * t)
        pitch = calculate_mean_pitch_hz(sine, sr=self.sr)
        self.assertIsNotNone(pitch)
        self.assertAlmostEqual(pitch, 200.0, delta=10.0)

    def test_pitch_silent_or_short(self):
        """Silent or very short audio should return None for pitch."""
        self.assertIsNone(calculate_mean_pitch_hz(np.zeros(16000), sr=self.sr))
        self.assertIsNone(calculate_mean_pitch_hz(np.array([0.1, 0.2]), sr=self.sr))

    def test_silence_ratio_pure_silence(self):
        """Pure silence should yield silence_ratio of 1.0."""
        silence = np.zeros(16000 * 2)
        ratio = calculate_silence_ratio(silence, sr=self.sr)
        self.assertAlmostEqual(ratio, 1.0, delta=0.1)

    def test_background_noise_classification(self):
        """Loud noise should classify as HIGH, gentle noise as LOW."""
        loud_noise = np.random.normal(0, 0.2, 16000 * 2)  # ~ -14 dBFS
        low_noise = np.random.normal(0, 0.001, 16000 * 2)  # ~ -60 dBFS
        self.assertEqual(calculate_background_noise_level(loud_noise, sr=self.sr), "HIGH")
        self.assertEqual(calculate_background_noise_level(low_noise, sr=self.sr), "LOW")


class TestVAD(unittest.TestCase):
    """Test suite for VoiceActivityDetector (voice_activity_detector.py)."""

    def setUp(self):
        self.sr = 16000
        self.vad = VoiceActivityDetector(sr=self.sr)

    def test_speech_and_silence_segmentation(self):
        """1s speech followed by 1s silence should detect both intervals."""
        t = np.linspace(0, 1.0, self.sr, endpoint=False)
        speech = 0.5 * np.sin(2 * np.pi * 300 * t)
        silence = np.zeros(self.sr)
        combined = np.concatenate([speech, silence])

        res = self.vad.process(combined)
        self.assertGreater(res["speech_duration_sec"], 0.5)
        self.assertGreater(res["silence_duration_sec"], 0.5)
        self.assertAlmostEqual(res["silence_ratio"], 0.5, delta=0.2)


class TestTranscriptMetrics(unittest.TestCase):
    """Test suite for speech & linguistic metrics (transcript_metrics.py)."""

    def test_wpm_calculation(self):
        """150 words in 60 seconds should be 150 WPM."""
        self.assertEqual(calculate_wpm(150, 60.0), 150)
        self.assertEqual(calculate_wpm(0, 60.0), 0)
        self.assertEqual(calculate_wpm(100, 0.0), 0)

    def test_speaking_duration(self):
        """Word timestamps spanning 0.0-2.0 and 3.0-5.0 with 1.0s gap should exclude pause."""
        word_timestamps = [
            {"word": "Hello", "start": 0.0, "end": 1.0},
            {"word": "world", "start": 1.0, "end": 2.0},
            {"word": "again", "start": 3.0, "end": 5.0},
        ]
        duration = calculate_speaking_duration_seconds(word_timestamps, total_recording_duration=5.0)
        self.assertAlmostEqual(duration, 4.0, delta=0.1)

    def test_empty_transcript(self):
        """Empty transcript should return zeroed metrics."""
        res = calculate_transcript_metrics(transcript_text="", word_timestamps=[])
        self.assertEqual(res["wpm"], 0)
        self.assertEqual(res["filler_count"], 0)
        self.assertEqual(res["pause_count"], 0)

    def test_filler_word_detection(self):
        """Pure fillers like 'um', 'uh' and contextual markers should be detected."""
        text = "Um I think uh we should basically build this like system."
        res = calculate_filler_rate_per_min(text, speaking_duration_seconds=30.0)
        filler_rate, count, breakdown = res
        self.assertGreater(count, 0)
        self.assertIn("um", breakdown)
        self.assertIn("uh", breakdown)
        self.assertIn("basically", breakdown)

    def test_pause_count(self):
        """Gap >= 0.8s should increment pause count."""
        word_timestamps = [
            {"word": "One", "start": 0.0, "end": 0.5},
            {"word": "Two", "start": 1.5, "end": 2.0},  # 1.0s gap -> pause
            {"word": "Three", "start": 2.2, "end": 2.6},  # 0.2s gap -> no pause
        ]
        pauses = calculate_pause_count(word_timestamps, pause_threshold_sec=0.8)
        self.assertEqual(pauses, 1)


class TestAudioMetricsEngine(unittest.TestCase):
    """Test suite for master AudioMetricsEngine pipeline."""

    @patch("fapi.ai_prep.core.audio_engine.metrics_engine.transcribe_audio")
    @patch("fapi.ai_prep.core.audio_engine.metrics_engine.calculate_audio_metrics")
    def test_process_audio_file_mocked(self, mock_audio_metrics, mock_transcribe):
        """Verifies process_audio_file coordinates STT and audio telemetry properly."""
        mock_transcribe.return_value = {
            "transcript_text": "Hello world.",
            "word_timestamps": [
                {"word": "Hello", "start": 0.0, "end": 0.5, "probability": 0.99},
                {"word": "world.", "start": 0.6, "end": 1.0, "probability": 0.99},
            ],
            "duration": 2.0,
        }
        mock_audio_metrics.return_value = {
            "avg_volume_db": -20.0,
            "mean_pitch_hz": 150.0,
            "silence_ratio": 0.2,
            "background_noise_level": "LOW",
            "clipping_detected": False,
            "total_audio_duration_seconds": 2.0,
        }

        with patch("os.path.exists", return_value=True):
            res = AudioMetricsEngine.process_audio_file("dummy.wav")

        self.assertIn("spoken_content", res)
        self.assertIn("audio_telemetry", res)
        self.assertEqual(res["audio_telemetry"]["avg_volume_db"], -20.0)
        self.assertEqual(res["audio_telemetry"]["wpm"], 120)

if __name__ == "__main__":
    unittest.main()
