"""
Unit Tests for Core Engines (AnalyticsEngine, AssessmentEngine, ScoresEngine).
"""

import unittest
from fapi.ai_prep.core.analytics_engine.engine import AnalyticsEngine


class TestAnalyticsEngine(unittest.TestCase):

    def test_analytics_with_empty_history(self):
        result = AnalyticsEngine.calculate_candidate_analytics([])
        self.assertEqual(result["total_assessments"], 0)
        self.assertEqual(result["average_wpm"], 0.0)
        self.assertEqual(result["average_technical_score"], 0.0)
        self.assertEqual(result["score_trends"], [])
        self.assertEqual(result["top_strengths"], [])

    def test_analytics_with_multiple_attempts(self):
        attempts = [
            {
                "assessment_id": 101,
                "created_at": "2026-09-01T10:00:00Z",
                "audio_telemetry": {"words_per_minute": 130, "silence_ratio_pct": 10.0},
                "report": {
                    "transcript_evaluation": {
                        "scores_breakdown": {
                            "ai_engineering": {"score": 80},
                            "core_engineering": {"score": 84},
                            "non_technical": {"score": 85},
                        },
                        "technical_analysis": {
                            "strengths": ["Clear RAG explanation", "Crisp delivery"],
                            "areas_for_improvement": ["Add cost/ROI framing"],
                        },
                    }
                },
            },
            {
                "assessment_id": 102,
                "created_at": "2026-09-03T10:00:00Z",
                "audio_telemetry": {"words_per_minute": 140, "silence_ratio_pct": 8.0},
                "report": {
                    "transcript_evaluation": {
                        "scores_breakdown": {
                            "ai_engineering": {"score": 90},
                            "core_engineering": {"score": 86},
                            "non_technical": {"score": 90},
                        },
                        "technical_analysis": {
                            "strengths": ["Clear RAG explanation", "Great MLOps depth"],
                            "areas_for_improvement": ["Add benchmark metrics"],
                        },
                    }
                },
            },
        ]

        result = AnalyticsEngine.calculate_candidate_analytics(attempts)

        self.assertEqual(result["total_assessments"], 2)
        self.assertEqual(result["average_wpm"], 135.0)
        self.assertEqual(result["average_silence_ratio_pct"], 9.0)
        self.assertEqual(result["average_technical_score"], 85.0)  # ((82 + 88) / 2)
        self.assertEqual(result["average_communication_score"], 87.5)
        self.assertEqual(len(result["score_trends"]), 2)
        self.assertEqual(len(result["wpm_trends"]), 2)

        # Verify deduplication of strengths
        self.assertIn("Clear RAG explanation", result["top_strengths"])
        self.assertIn("Crisp delivery", result["top_strengths"])
        self.assertIn("Great MLOps depth", result["top_strengths"])
        self.assertLessEqual(len(result["top_strengths"]), 5)


if __name__ == "__main__":
    unittest.main()
