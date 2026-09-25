"""
Exhaustive Unit Tests for Core Engines (AnalyticsEngine, AssessmentEngine).
Includes edge cases, missing payload keys, non-numeric values, deduplication logic,
and pure unit tests for AssessmentEngine core business logic.
"""

import unittest
import pytest

from fapi.ai_prep.core.analytics_engine.engine import AnalyticsEngine
from fapi.ai_prep.core.assessment_engine.engine import AssessmentEngine


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

    def test_analytics_with_real_intro_and_audio_evaluation_payloads(self):
        """Validates that AnalyticsEngine correctly parses modern LLM intro_evaluation and audio_evaluation."""
        attempts = [
            {
                "assessment_id": 501,
                "created_at": "2026-09-17T12:00:00Z",
                "audio_telemetry": {},  # empty raw telemetry
                "report": {
                    "audio_evaluation": {
                        "factors": {
                            "pace": {"wpm_recorded": 178, "status": "ADEQUATE"},
                            "fluency": {"silence_ratio_pct": 12.0, "status": "GOOD"},
                        }
                    },
                    "transcript_evaluation": {
                        "intro_evaluation": {
                            "overall_assessment": {
                                "overall_score": 88.0,
                                "readiness": "GOOD",
                            },
                            "introduction_quality": {
                                "score": 82.0,
                            },
                            "strongest_points": [
                                "End-to-end talent screen production RAG experience",
                                "Strong agentic AI architecture with LangGraph",
                            ],
                            "priority_improvements": [
                                "Mention explicit latency and throughput metrics",
                            ],
                            "critical_gaps": [
                                "Elaborate more on CI/CD test automation",
                            ],
                        }
                    },
                },
            }
        ]

        result = AnalyticsEngine.calculate_candidate_analytics(attempts)
        self.assertEqual(result["total_assessments"], 1)
        self.assertEqual(result["average_wpm"], 178.0)
        self.assertEqual(result["average_silence_ratio_pct"], 12.0)
        self.assertEqual(result["average_technical_score"], 88.0)
        self.assertEqual(result["average_communication_score"], 82.0)
        self.assertEqual(len(result["score_trends"]), 1)
        self.assertEqual(result["score_trends"][0]["score"], 88.0)
        self.assertEqual(len(result["wpm_trends"]), 1)
        self.assertEqual(result["wpm_trends"][0]["wpm"], 178.0)
        self.assertIn("End-to-end talent screen production RAG experience", result["top_strengths"])
        self.assertIn("Mention explicit latency and throughput metrics", result["top_improvements"])
        self.assertIn("Elaborate more on CI/CD test automation", result["top_improvements"])

    def test_analytics_with_report_overall_score_and_wpm_fallback(self):
        """Validates that AnalyticsEngine falls back to top-level overall_score and alternative wpm keys."""
        attempts = [
            {
                "id": 601,
                "created_at": "2026-09-17T15:00:00Z",
                "audio_telemetry": {"wpm": 142.5, "silence_ratio": 9.2},
                "report": {
                    "overall_score": 91.0,
                    "strengths": ["Clear communication"],
                    "improvements": ["More detail on indexing"],
                },
            }
        ]

        result = AnalyticsEngine.calculate_candidate_analytics(attempts)
        self.assertEqual(result["average_wpm"], 142.5)
        self.assertEqual(result["average_silence_ratio_pct"], 9.2)
        self.assertEqual(result["average_technical_score"], 91.0)
        self.assertIn("Clear communication", result["top_strengths"])
        self.assertIn("More detail on indexing", result["top_improvements"])


# =============================================================================
# AssessmentEngine — Question Selection
# =============================================================================


class TestAssessmentEngineQuestionSelection:

    def setup_method(self):
        self.engine = AssessmentEngine()

    def _make_questions(self, categories: list) -> list:
        return [
            {
                "id": i + 1,
                "category": cat,
                "sub_category": "General" if cat == "TECHNICAL" else None,
                "difficulty_level": "HARD",
                "question_text": f"Question {i + 1} about {cat}",
                "is_active": True,
            }
            for i, cat in enumerate(categories)
        ]

    def test_select_matching_category_questions(self):
        questions = self._make_questions(["TECHNICAL", "TECHNICAL", "INTRO"])
        result = self.engine.select_questions_for_assessment("TECHNICAL", questions)
        assert len(result) == 2
        for q in result:
            assert q["category"] == "TECHNICAL"

    def test_sanitized_candidate_question_schema(self):
        """Candidate question payload contains only public candidate-facing fields."""
        questions = self._make_questions(["TECHNICAL"])
        result = self.engine.select_questions_for_assessment("TECHNICAL", questions)
        assert len(result) == 1
        assert "question_text" in result[0]
        assert "category" in result[0]
        assert "ideal_answer_rubric" not in result[0]

    def test_no_questions_returned_when_category_has_no_matches(self):
        """When requesting TECHNICAL and only INTRO + RECRUITER exist, return [] (no cross-category fallback)."""
        questions = self._make_questions(["INTRO", "RECRUITER"])
        result = self.engine.select_questions_for_assessment("TECHNICAL", questions)
        assert result == []

    def test_limit_respected(self):
        questions = self._make_questions(["TECHNICAL"] * 10)
        result = self.engine.select_questions_for_assessment("TECHNICAL", questions, limit=3)
        assert len(result) == 3

    def test_inactive_questions_excluded(self):
        questions = self._make_questions(["TECHNICAL", "TECHNICAL"])
        questions[0]["is_active"] = False
        result = self.engine.select_questions_for_assessment("TECHNICAL", questions)
        assert len(result) == 1

    def test_empty_available_questions_returns_empty(self):
        result = self.engine.select_questions_for_assessment("TECHNICAL", [])
        assert result == []

    def test_case_insensitive_type_matching(self):
        questions = self._make_questions(["TECHNICAL"])
        result_lower = self.engine.select_questions_for_assessment("technical", questions)
        result_upper = self.engine.select_questions_for_assessment("TECHNICAL", questions)
        assert len(result_lower) == len(result_upper) == 1

    def test_sanitized_question_has_required_fields(self):
        questions = self._make_questions(["INTRO"])
        result = self.engine.select_questions_for_assessment("INTRO", questions)
        q = result[0]
        assert "question_id" in q
        assert "question_text" in q
        assert "category" in q
        assert "difficulty_level" in q

    def test_explicit_limit_cap(self):
        """Should respect explicit limit parameter when passed."""
        questions = self._make_questions(["TECHNICAL"] * 20)
        result = self.engine.select_questions_for_assessment("TECHNICAL", questions, limit=3)
        assert len(result) == 3


# =============================================================================
# AssessmentEngine — Context Building
# =============================================================================


class TestAssessmentEngineContextBuilding:

    def setup_method(self):
        self.engine = AssessmentEngine()

    def test_build_qa_context_includes_question_and_transcript(self):
        questions = [{"question_text": "Explain RAG pipelines."}]
        transcript = {"full_text": "RAG stands for Retrieval-Augmented Generation..."}
        ctx = self.engine.build_qa_context(questions, transcript)
        assert "Explain RAG" in ctx
        assert "Retrieval-Augmented Generation" in ctx

    def test_build_qa_context_empty_transcript_shows_placeholder(self):
        questions = [{"question_text": "Tell me about yourself."}]
        ctx = self.engine.build_qa_context(questions, {})
        assert "Tell me about yourself" in ctx
        assert "[No transcript provided]" in ctx

    def test_build_qa_context_handles_no_questions(self):
        ctx = self.engine.build_qa_context([], {"full_text": "My answer"})
        assert "My answer" in ctx

    def test_build_qa_context_handles_alternate_transcript_keys(self):
        """Transcript dict may use 'text' instead of 'full_text'."""
        questions = []
        ctx = self.engine.build_qa_context(questions, {"text": "Alternate key transcript"})
        assert "Alternate key transcript" in ctx

    def test_build_audio_context_with_full_telemetry(self):
        telemetry = {
            "speaking_pace_wpm": 130,
            "silence_ratio_pct": 15.0,
            "speaking_duration_seconds": 300.0,
            "filler_rate_per_min": 2.5,
            "pause_count": 8,
            "avg_volume_db": -18.0,
            "background_noise_level": "LOW",
            "clipping_detected": False,
        }
        ctx = self.engine.build_audio_context(telemetry)
        assert "130 WPM" in ctx
        assert "15.0%" in ctx
        assert "300.0s" in ctx
        assert "LOW" in ctx

    def test_build_audio_context_empty_returns_unavailable(self):
        ctx = self.engine.build_audio_context({})
        assert "Not available" in ctx

    def test_build_audio_context_none_returns_unavailable(self):
        ctx = self.engine.build_audio_context(None)
        assert "Not available" in ctx

    def test_build_audio_context_alias_fields(self):
        """Should handle words_per_minute alias for speaking_pace_wpm."""
        telemetry = {"words_per_minute": 110, "speaking_duration_seconds": 60.0}
        ctx = self.engine.build_audio_context(telemetry)
        assert "110 WPM" in ctx

    def test_build_video_context_video_mode(self):
        telemetry = {
            "is_video_mode": True,
            "face_visible_pct": 95.0,
            "eye_contact_pct": 88.0,
            "screen_attention_pct": 92.0,
            "distraction_level_pct": 8.0,
            "stress_level": "Low",
            "head_nods_count": 12,
        }
        ctx = self.engine.build_video_context(telemetry)
        assert "95.0%" in ctx
        assert "88.0%" in ctx

    def test_build_video_context_audio_only_session(self):
        ctx = self.engine.build_video_context({"is_video_mode": False})
        assert "audio-only" in ctx.lower() or "Audio-only" in ctx

    def test_build_video_context_no_data_returns_unavailable(self):
        ctx = self.engine.build_video_context(None)
        assert "Not available" in ctx

    def test_build_video_context_empty_dict_returns_unavailable(self):
        ctx = self.engine.build_video_context({})
        assert "Not available" in ctx


# =============================================================================
# AssessmentEngine — Eligibility Logic
# =============================================================================


class TestAssessmentEngineEligibility:

    def setup_method(self):
        self.engine = AssessmentEngine()

    def test_eligible_when_both_llm_and_resume_configured(self):
        llm = {"status": "valid", "is_configured": True}
        resume = {"status": "valid", "has_resume": True}
        assert self.engine.is_candidate_eligible(llm, resume) is True

    def test_not_eligible_when_llm_missing(self):
        llm = {"status": "failure", "is_configured": False}
        resume = {"status": "valid", "has_resume": True}
        assert self.engine.is_candidate_eligible(llm, resume) is False

    def test_not_eligible_when_resume_missing(self):
        llm = {"status": "valid", "is_configured": True}
        resume = {"status": "failure", "has_resume": False}
        assert self.engine.is_candidate_eligible(llm, resume) is False

    def test_not_eligible_when_both_missing(self):
        llm = {"status": "failure", "is_configured": False}
        resume = {"status": "failure", "has_resume": False}
        assert self.engine.is_candidate_eligible(llm, resume) is False

    def test_not_eligible_when_llm_check_is_none(self):
        """Rule: llm_check=None returns False cleanly without raising AttributeError."""
        resume = {"status": "valid", "has_resume": True}
        assert self.engine.is_candidate_eligible(None, resume) is False

    def test_not_eligible_when_resume_check_is_none(self):
        """Rule: resume_check=None returns False cleanly without raising AttributeError."""
        llm = {"status": "valid", "is_configured": True}
        assert self.engine.is_candidate_eligible(llm, None) is False

    def test_not_eligible_when_both_checks_are_none(self):
        """Rule: both llm_check=None and resume_check=None returns False cleanly."""
        assert self.engine.is_candidate_eligible(None, None) is False

    def test_eligibility_message_when_ready(self):
        llm = {"status": "valid", "is_configured": True}
        resume = {"status": "valid", "has_resume": True}
        msg = self.engine.compute_eligibility_message(llm, resume)
        assert "Ready" in msg or "prerequisites" in msg

    def test_eligibility_message_lists_missing_llm(self):
        llm = {"status": "failure", "is_configured": False}
        resume = {"status": "valid", "has_resume": True}
        msg = self.engine.compute_eligibility_message(llm, resume)
        assert "LLM" in msg

    def test_eligibility_message_lists_missing_resume(self):
        llm = {"status": "valid", "is_configured": True}
        resume = {"status": "failure", "has_resume": False}
        msg = self.engine.compute_eligibility_message(llm, resume)
        assert "Resume" in msg or "resume" in msg.lower()

    def test_eligibility_message_lists_both_issues(self):
        llm = {"status": "failure", "is_configured": False}
        resume = {"status": "failure", "has_resume": False}
        msg = self.engine.compute_eligibility_message(llm, resume)
        assert "LLM" in msg
        assert "Resume" in msg or "resume" in msg.lower()

    def test_eligibility_message_handles_none_inputs_safely(self):
        """Rule: compute_eligibility_message handles None inputs safely without raising AttributeError."""
        msg_llm_none = self.engine.compute_eligibility_message(None, {"status": "valid", "has_resume": True})
        assert "LLM" in msg_llm_none

        msg_resume_none = self.engine.compute_eligibility_message({"status": "valid", "is_configured": True}, None)
        assert "Resume" in msg_resume_none or "resume" in msg_resume_none.lower()

        msg_both_none = self.engine.compute_eligibility_message(None, None)
        assert "LLM" in msg_both_none
        assert "Resume" in msg_both_none or "resume" in msg_both_none.lower()


# =============================================================================
# AssessmentEngine — State Validation
# =============================================================================


class TestAssessmentEngineStateValidation:

    def setup_method(self):
        self.engine = AssessmentEngine()

    def test_valid_in_progress_transitions(self):
        assert self.engine.is_valid_transition("IN_PROGRESS", "EVALUATING") is True
        assert self.engine.is_valid_transition("IN_PROGRESS", "FAILED") is True

    def test_valid_evaluating_transitions(self):
        assert self.engine.is_valid_transition("EVALUATING", "COMPLETED") is True
        assert self.engine.is_valid_transition("EVALUATING", "FAILED") is True

    def test_abandoned_status_rejected(self):
        """ABANDONED is not part of the status contract and must be rejected."""
        assert self.engine.is_valid_transition("IN_PROGRESS", "ABANDONED") is False
        assert self.engine.is_valid_transition("EVALUATING", "ABANDONED") is False

    def test_terminal_states_reject_transitions(self):
        assert self.engine.is_valid_transition("COMPLETED", "IN_PROGRESS") is False
        assert self.engine.is_valid_transition("FAILED", "IN_PROGRESS") is False


if __name__ == "__main__":
    unittest.main()
