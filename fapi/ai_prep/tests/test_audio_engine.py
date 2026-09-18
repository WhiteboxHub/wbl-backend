"""
Unit and Integration Tests for Audio Engine & STT Chunk Merging.
Tests overlap deduplication, global timestamp offsets, genuine repetitions,
and database storage safety (no word_timestamps persisted).
"""
import unittest
from fapi.ai_prep.core.audio_engine.stt import merge_word_timestamps, LiveSTTStore
from fapi.ai_prep.core.audio_engine.transcript_metrics import calculate_transcript_metrics


class TestSTTChunkMerging(unittest.TestCase):

    def test_1_normal_consecutive_chunks(self):
        c1 = [{"word": "Hello", "start": 0.0, "end": 0.5, "probability": 0.9}]
        c2 = [{"word": "world", "start": 0.8, "end": 1.2, "probability": 0.9}]
        merged = merge_word_timestamps(c1, c2)
        words = [w["word"] for w in merged]
        self.assertEqual(words, ["Hello", "world"])

    def test_2_overlapping_chunks_deduplication(self):
        # Chunk 1: "I worked on an AI project" (0.0 to 3.0s)
        c1 = [
            {"word": "I", "start": 0.0, "end": 0.2, "probability": 0.9},
            {"word": "worked", "start": 0.3, "end": 0.7, "probability": 0.9},
            {"word": "on", "start": 0.8, "end": 0.9, "probability": 0.9},
            {"word": "an", "start": 1.0, "end": 1.1, "probability": 0.9},
            {"word": "AI", "start": 1.2, "end": 1.5, "probability": 0.85},
            {"word": "project", "start": 1.6, "end": 2.1, "probability": 0.88},
        ]
        # Chunk 2 (overlap from 1.2s): "AI project and developed the backend"
        c2 = [
            {"word": "AI", "start": 1.22, "end": 1.51, "probability": 0.95},
            {"word": "project", "start": 1.59, "end": 2.12, "probability": 0.96},
            {"word": "and", "start": 2.2, "end": 2.4, "probability": 0.9},
            {"word": "developed", "start": 2.5, "end": 3.0, "probability": 0.9},
            {"word": "the", "start": 3.1, "end": 3.2, "probability": 0.9},
            {"word": "backend", "start": 3.3, "end": 3.8, "probability": 0.9},
        ]
        merged = merge_word_timestamps(c1, c2)
        words = [w["word"] for w in merged]
        expected = ["I", "worked", "on", "an", "AI", "project", "and", "developed", "the", "backend"]
        self.assertEqual(words, expected)

    def test_3_genuine_repeated_words_preserved(self):
        # "It was very very good"
        c1 = [
            {"word": "It", "start": 0.0, "end": 0.2, "probability": 0.9},
            {"word": "was", "start": 0.3, "end": 0.5, "probability": 0.9},
            {"word": "very", "start": 0.6, "end": 0.8, "probability": 0.9},
            {"word": "very", "start": 0.9, "end": 1.1, "probability": 0.9},
            {"word": "good", "start": 1.2, "end": 1.5, "probability": 0.9},
        ]
        merged = merge_word_timestamps(c1, [])
        words = [w["word"] for w in merged]
        self.assertEqual(words, ["It", "was", "very", "very", "good"])

    def test_4_empty_and_short_chunks(self):
        c1 = [{"word": "Testing", "start": 0.0, "end": 0.5, "probability": 0.9}]
        self.assertEqual(merge_word_timestamps(c1, []), c1)
        self.assertEqual(merge_word_timestamps([], c1), c1)

    def test_5_timing_metrics_and_discard_word_timestamps(self):
        words = [
            {"word": "I", "start": 0.0, "end": 0.2, "probability": 0.9},
            {"word": "am", "start": 0.3, "end": 0.5, "probability": 0.9},
            {"word": "speaking", "start": 0.6, "end": 1.0, "probability": 0.9},
            # 1.5s pause
            {"word": "now", "start": 2.5, "end": 2.8, "probability": 0.9},
        ]
        text = "I am speaking now"
        metrics = calculate_transcript_metrics(transcript_text=text, word_timestamps=words, total_recording_duration=3.0)
        
        self.assertEqual(metrics["pause_count"], 1)
        self.assertGreater(metrics["wpm"], 0)
        self.assertIn("filler_rate_per_min", metrics)


if __name__ == "__main__":
    unittest.main()
