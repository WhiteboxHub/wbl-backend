"""
Exhaustive Unit Tests for Core Engines (AnalyticsEngine, AssessmentEngine).
Includes edge cases, missing payload keys, non-numeric values, deduplication logic,
and pure unit tests for AssessmentEngine core business logic.
"""

import unittest
import pytest

from typing import Any, Dict, List, Optional, Set

from fapi.ai_prep.core.analytics_engine.engine import AnalyticsEngine
from fapi.ai_prep.core.assessment_engine.engine import AssessmentEngine
from fapi.ai_prep.core.scores_engine import ScoresEngine


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
                "subject": "AI Engineering" if cat == "TECHNICAL" else None,
                "concept": "Python & Data Manipulation" if cat == "TECHNICAL" else None,
                "scope": "BROAD" if cat == "TECHNICAL" else None,
                "difficulty_level": "HARD",
                "time_limit_seconds": 120,
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



# =============================================================================
# AssessmentEngine — Recruiter Timed Question Selection
# =============================================================================


class TestRecruiterTimedQuestionSelection:

    def setup_method(self):
        self.engine = AssessmentEngine()

    def _make_recruiter_questions(self, count: int, time_limit: Optional[int] = 120) -> list:
        return [
            {
                "id": i + 1,
                "category": "RECRUITER",
                "subject": None,
                "concept": None,
                "scope": None,
                "difficulty_level": "MEDIUM",
                "time_limit_seconds": time_limit,
                "question_text": f"Recruiter question {i + 1}",
                "is_active": True,
            }
            for i in range(count)
        ]

    def test_recruiter_default_question_time(self):
        """Rule 1: If time_limit_seconds is missing, None, or non-positive, default to 120s."""
        questions = [
            {"id": 1, "category": "RECRUITER", "is_active": True, "time_limit_seconds": None},
            {"id": 2, "category": "RECRUITER", "is_active": True, "time_limit_seconds": 0},
            {"id": 3, "category": "RECRUITER", "is_active": True},
        ]
        result = self.engine.select_recruiter_timed_questions(questions, target_seconds=600)
        assert len(result) == 3
        for q in result:
            assert q["time_limit_seconds"] == 120

    def test_recruiter_total_time_cap_never_exceeds_600s(self):
        """Rule 3: Total estimated time must never exceed 600s (10 min)."""
        questions = self._make_recruiter_questions(10, time_limit=120)  # Total 1200s available
        result = self.engine.select_recruiter_timed_questions(questions, target_seconds=600)
        total_time = sum(q["time_limit_seconds"] for q in result)
        assert len(result) == 5
        assert total_time == 600
        assert total_time <= 600

    def test_recruiter_variable_question_times_never_exceeds_600s(self):
        """Rule 3: Variable question times fit within 600s without exceeding."""
        questions = [
            {"id": 1, "category": "RECRUITER", "is_active": True, "time_limit_seconds": 150},
            {"id": 2, "category": "RECRUITER", "is_active": True, "time_limit_seconds": 180},
            {"id": 3, "category": "RECRUITER", "is_active": True, "time_limit_seconds": 200},
            {"id": 4, "category": "RECRUITER", "is_active": True, "time_limit_seconds": 120},
            {"id": 5, "category": "RECRUITER", "is_active": True, "time_limit_seconds": 90},
        ]
        result = self.engine.select_recruiter_timed_questions(questions, target_seconds=600)
        total_time = sum(q["time_limit_seconds"] for q in result)
        assert total_time <= 600

    def test_recruiter_independent_of_subject_concept_difficulty_scope(self):
        """Rule 2: Selection does not depend on subject, concept, difficulty, or scope."""
        questions = [
            {"id": 1, "category": "RECRUITER", "subject": None, "concept": None, "scope": None, "difficulty_level": None, "is_active": True, "time_limit_seconds": 120},
            {"id": 2, "category": "RECRUITER", "subject": "AI", "concept": "NLP", "scope": "BROAD", "difficulty_level": "HARD", "is_active": True, "time_limit_seconds": 120},
            {"id": 3, "category": "RECRUITER", "subject": "SE", "concept": "Design", "scope": "SPECIFIC", "difficulty_level": "EASY", "is_active": True, "time_limit_seconds": 120},
        ]
        result = self.engine.select_recruiter_timed_questions(questions, target_seconds=600)
        assert len(result) == 3

    def test_recruiter_no_duplicate_questions(self):
        """Rule 4: Never include duplicate questions within the same assessment."""
        questions = self._make_recruiter_questions(15, time_limit=120)
        result = self.engine.select_recruiter_timed_questions(questions, target_seconds=600)
        ids = [q["id"] for q in result]
        assert len(ids) == len(set(ids))

    def test_recruiter_prioritizes_fresh_questions(self):
        """Rule 5: Exclude previously completed questions when fresh questions are available."""
        questions = self._make_recruiter_questions(10, time_limit=120)
        previously_asked = {1, 2, 3, 4, 5}
        result = self.engine.select_recruiter_timed_questions(
            questions, target_seconds=600, previously_asked_ids=previously_asked
        )
        selected_ids = {q["id"] for q in result}
        assert len(result) == 5
        # Must only pick from 6, 7, 8, 9, 10
        assert selected_ids == {6, 7, 8, 9, 10}
        assert not selected_ids.intersection(previously_asked)

    def test_recruiter_exhaustion_reuses_previously_asked(self):
        """Rule 6: If all questions are previously asked, randomly reuse them up to 600s without duplicates."""
        questions = self._make_recruiter_questions(6, time_limit=120)
        all_asked = {1, 2, 3, 4, 5, 6}
        result = self.engine.select_recruiter_timed_questions(
            questions, target_seconds=600, previously_asked_ids=all_asked
        )
        assert len(result) == 5
        ids = [q["id"] for q in result]
        assert len(ids) == len(set(ids))
        assert sum(q["time_limit_seconds"] for q in result) == 600

    def test_recruiter_partial_exhaustion_backfills_from_previously_asked(self):
        """Rule 6: If fresh questions are insufficient, backfill from previously asked up to 600s."""
        questions = self._make_recruiter_questions(6, time_limit=120)
        # Questions 1-5 already asked; only question 6 is fresh
        previously_asked = {1, 2, 3, 4, 5}
        result = self.engine.select_recruiter_timed_questions(
            questions, target_seconds=600, previously_asked_ids=previously_asked
        )
        assert len(result) == 5
        ids = [q["id"] for q in result]
        assert 6 in ids  # Fresh question guaranteed to be picked
        assert len(ids) == len(set(ids))  # No duplicates

    def test_recruiter_explicit_limit_respected(self):
        """Rule: Explicit limit caps the number of selected questions."""
        questions = self._make_recruiter_questions(10, time_limit=120)
        result = self.engine.select_recruiter_timed_questions(questions, target_seconds=600, limit=2)
        assert len(result) == 2

    def test_recruiter_inactive_questions_excluded(self):
        """Rule: Inactive questions are never selected."""
        questions = self._make_recruiter_questions(5, time_limit=120)
        questions[0]["is_active"] = False
        result = self.engine.select_recruiter_timed_questions(questions, target_seconds=600)
        assert len(result) == 4
        assert 1 not in [q["id"] for q in result]

    def test_other_assessment_types_unaffected(self):
        """Rule 7: Other assessment types remain completely unchanged."""
        tech_q = [
            {"id": 1, "category": "TECHNICAL", "subject": "AI Engineering", "concept": "NLP", "scope": "BROAD", "difficulty_level": "HARD", "time_limit_seconds": 120, "is_active": True},
            {"id": 2, "category": "TECHNICAL", "subject": "Software Engineering", "concept": "API", "scope": "SPECIFIC", "difficulty_level": "MEDIUM", "time_limit_seconds": 120, "is_active": True},
        ]
        intro_q = [
            {"id": 10, "category": "INTRO", "is_active": True, "time_limit_seconds": 120},
            {"id": 11, "category": "INTRO", "is_active": True, "time_limit_seconds": 120},
        ]
        tech_res = self.engine.select_questions_for_assessment("TECHNICAL", tech_q, sanitize=False)
        assert len(tech_res) == 2
        intro_res = self.engine.select_questions_for_assessment("INTRO", intro_q, sanitize=False)
        assert len(intro_res) == 1


# =============================================================================
# ScoresEngine — Truncated JSON Repair Tests
# =============================================================================


class TestScoresEngineJsonRepair:

    def setup_method(self):
        self.engine = ScoresEngine()

    def test_repair_truncated_json_string(self):
        truncated = '{"technical_evaluation": {"overall_assessment": {"rating": "GOOD"}, "subject_evaluations": [], "question_evaluations": [{"question_id": 1, "rating": "GOOD", "feedback": "Good depth'
        result = self.engine.validate_and_parse(truncated)
        assert result["is_valid"] is True
        assert result["parsed_report"]["technical_evaluation"]["question_evaluations"][0]["feedback"] == "Good depth"

    def test_repair_truncated_json_trailing_comma(self):
        truncated = '{"technical_evaluation": {"overall_assessment": {"rating": "GOOD"}, "subject_evaluations": [], "question_evaluations": [{"question_id": 1, "rating": "GOOD"}, '
        result = self.engine.validate_and_parse(truncated)
        assert result["is_valid"] is True
        assert len(result["parsed_report"]["technical_evaluation"]["question_evaluations"]) == 1

    def test_repair_string_with_commas_not_sliced(self):
        """Verify naive rfind(',') does not slice inside string literals."""
        truncated = '{"technical_evaluation": {"overall_assessment": {"rating": "GOOD"}, "subject_evaluations": [], "question_evaluations": [{"question_id": 1, "rating": "GOOD", "feedback": "Good depth, clear examples, but miss'
        result = self.engine.validate_and_parse(truncated)
        assert result["is_valid"] is True
        assert result["parsed_report"]["technical_evaluation"]["question_evaluations"][0]["feedback"] == "Good depth, clear examples, but miss"

    def test_repair_with_prompt_ordering_preserves_overall_assessment(self):
        """Verify prompt order where overall_assessment and subject_evaluations are emitted first."""
        truncated = (
            '{"technical_evaluation": {'
            '"overall_assessment": {"rating": "EXCELLENT", "executive_summary": "Strong candidate"}, '
            '"subject_evaluations": [{"subject": "Software Engineering", "rating": "EXCELLENT"}], '
            '"difficulty_analysis": {"easy": "Well done", "medium": "Solid", "hard": "Partial"}, '
            '"question_evaluations": [{"question_id": 1, "rating": "EXCELLENT", "observation": "Great understanding, precise explanation'
        )
        result = self.engine.validate_and_parse(truncated)
        assert result["is_valid"] is True
        tech = result["parsed_report"]["technical_evaluation"]
        assert tech["overall_assessment"]["rating"] == "EXCELLENT"
        assert len(tech["subject_evaluations"]) == 1
        assert tech["question_evaluations"][0]["observation"] == "Great understanding, precise explanation"


if __name__ == "__main__":
    unittest.main()
