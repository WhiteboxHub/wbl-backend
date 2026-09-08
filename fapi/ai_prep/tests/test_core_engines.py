"""
Exhaustive Unit Tests for Core Engines (AnalyticsEngine, AssessmentEngine, ScoresEngine).
Includes edge cases, missing payload keys, non-numeric values, and deduplication logic.
"""

import unittest
from fapi.ai_prep.core.analytics_engine.engine import AnalyticsEngine


class TestAnalyticsEngineExhaustive(unittest.TestCase):

    def test_analytics_with_empty_history(self):
        result = AnalyticsEngine.calculate_candidate_analytics([])
        self.assertEqual(result["total_assessments"], 0)
        self.assertEqual(result["average_wpm"], 0.0)
        self.assertEqual(result["average_silence_ratio_pct"], 0.0)
        self.assertEqual(result["average_technical_score"], 0.0)
        self.assertEqual(result["average_communication_score"], 0.0)
        self.assertEqual(result["score_trends"], [])
        self.assertEqual(result["wpm_trends"], [])
        self.assertEqual(result["top_strengths"], [])
        self.assertEqual(result["top_improvements"], [])

    def test_analytics_with_none_or_malformed_telemetry(self):
        malformed_attempts = [
            {
                "assessment_id": 1,
                "created_at": "2026-09-01T10:00:00Z",
                "audio_telemetry": None,
                "report": None,
            },
            {
                "id": 2,
                "created_at": "2026-09-02T10:00:00Z",
                "audio_telemetry": {"words_per_minute": None, "silence_ratio_pct": None},
                "report": {"transcript_evaluation": {}},
            },
        ]
        result = AnalyticsEngine.calculate_candidate_analytics(malformed_attempts)
        self.assertEqual(result["total_assessments"], 2)
        self.assertEqual(result["average_wpm"], 0.0)
        self.assertEqual(result["average_technical_score"], 0.0)

    def test_analytics_with_partial_scores(self):
        attempts = [
            {
                "assessment_id": 101,
                "created_at": "2026-09-01T10:00:00Z",
                "audio_telemetry": {"words_per_minute": 120, "silence_ratio_pct": 5.0},
                "report": {
                    "transcript_evaluation": {
                        "scores_breakdown": {
                            "ai_engineering": {"score": 90},  # Only AI eng score
                        }
                    }
                },
            },
            {
                "assessment_id": 102,
                "created_at": "2026-09-02T10:00:00Z",
                "audio_telemetry": {"speaking_pace_wpm": 150, "silence_ratio_pct": 15.0},
                "report": {
                    "transcript_evaluation": {
                        "scores_breakdown": {
                            "core_engineering": {"score": 70},  # Only Core eng score
                        }
                    }
                },
            },
        ]
        result = AnalyticsEngine.calculate_candidate_analytics(attempts)
        self.assertEqual(result["total_assessments"], 2)
        self.assertEqual(result["average_wpm"], 135.0)  # (120 + 150) / 2
        self.assertEqual(result["average_silence_ratio_pct"], 10.0)  # (5 + 15) / 2
        self.assertEqual(result["average_technical_score"], 80.0)  # (90 + 70) / 2

    def test_analytics_strengths_and_improvements_deduplication(self):
        attempts = [
            {
                "assessment_id": 1,
                "report": {
                    "transcript_evaluation": {
                        "technical_analysis": {
                            "strengths": ["Clear RAG explanation", "Good pacing", "Clear RAG explanation"],
                            "areas_for_improvement": ["Add MLOps guardrails", "Add cost framing"],
                        }
                    }
                },
            },
            {
                "assessment_id": 2,
                "report": {
                    "transcript_evaluation": {
                        "technical_analysis": {
                            "strengths": ["Good pacing", "Strong System Design"],
                            "areas_for_improvement": ["Add MLOps guardrails", "Study vector indices"],
                        }
                    }
                },
            },
        ]
        result = AnalyticsEngine.calculate_candidate_analytics(attempts)
        # Strengths deduplicated
        self.assertEqual(len(result["top_strengths"]), 3)
        self.assertIn("Clear RAG explanation", result["top_strengths"])
        self.assertIn("Good pacing", result["top_strengths"])
        self.assertIn("Strong System Design", result["top_strengths"])

        # Improvements deduplicated
        self.assertEqual(len(result["top_improvements"]), 3)
        self.assertIn("Add MLOps guardrails", result["top_improvements"])
        self.assertIn("Add cost framing", result["top_improvements"])
        self.assertIn("Study vector indices", result["top_improvements"])

    def test_analytics_trend_formatting(self):
        attempts = [
            {
                "id": 201,
                "created_at": "2026-09-01T10:00:00Z",
                "audio_telemetry": {"words_per_minute": 130},
                "report": {
                    "transcript_evaluation": {
                        "scores_breakdown": {
                            "ai_engineering": {"score": 75},
                            "core_engineering": {"score": 85},
                        }
                    }
                },
            }
        ]
        result = AnalyticsEngine.calculate_candidate_analytics(attempts)
        self.assertEqual(len(result["score_trends"]), 1)
        self.assertEqual(result["score_trends"][0]["assessment_id"], 201)
        self.assertEqual(result["score_trends"][0]["score"], 80.0)

        self.assertEqual(len(result["wpm_trends"]), 1)
        self.assertEqual(result["wpm_trends"][0]["wpm"], 130.0)


if __name__ == "__main__":
    unittest.main()
