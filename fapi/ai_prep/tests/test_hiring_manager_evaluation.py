"""
Unit Tests for Hiring Manager Assessment Evaluation, Prompt Compilation & Validation.
=====================================================================================
Covers:
1. EvalEngine Hiring Manager prompt compilation & ground-truth formatting (v2.8.0).
2. ScoresEngine validation for both v2.8 multi-question schema and legacy pillar schema.
3. Resilient JSON sanitization (unescaped internal quotes, trailing commas).
4. AssessmentEngine timed question budget selection & adaptive difficulty for Hiring Manager.
"""

import json
import unittest
from typing import Any, Dict


# =============================================================================
# EvalEngine — Hiring Manager Prompt Compilation
# =============================================================================


class TestEvalEngineHiringManagerPrompt(unittest.TestCase):

    def test_hiring_manager_prompt_loads_without_fallback(self):
        """Rule: EvalEngine loads hiring_manager_prompt directly without falling back to intro_prompt."""
        from fapi.ai_prep.core.llm_evaluation.engine import EvalEngine
        from fapi.ai_prep.core.llm_evaluation.prompts import hiring_manager_prompt

        engine = EvalEngine()
        res = engine.build_prompt(
            assessment_type="HIRING_MANAGER",
            transcript_text="I owned the redesign of our real-time streaming pipeline.",
            qa_context="Q1: Tell me about a blocker.\nA1: We faced latency spikes.",
            resume_json={"skills": ["Python", "FastAPI", "Kafka"]},
        )

        assert res["response_format"] == "json_object"
        assert "5 CORE LEADERSHIP COMPETENCIES" in res["system_prompt"]
        assert "Engineering Director" in res["system_prompt"]
        assert "PROJECT OWNERSHIP" in res["system_prompt"]
        assert "TECHNICAL ROADBLOCKS" in res["system_prompt"]
        assert "CONFLICT & COLLABORATION" in res["system_prompt"]
        assert "TRADE-OFFS & DEADLINES" in res["system_prompt"]
        assert "DELIVERY & EXCELLENCE" in res["system_prompt"]
        assert "Q1: Tell me about a blocker." in res["user_prompt"]
        assert hiring_manager_prompt.PROMPT_VERSION == "3.1.0"


# =============================================================================
# ScoresEngine — Hiring Manager Validator Tests
# =============================================================================


class TestScoresEngineHiringManagerValidator(unittest.TestCase):

    def setUp(self):
        from fapi.ai_prep.core.scores_engine.llm_output_validator import ScoresEngine
        self.validator = ScoresEngine()

    def _sample_valid_hm_payload(self) -> Dict[str, Any]:
        return {
            "hiring_manager_evaluation": {
                "project_ownership": {
                    "status": "STRONG",
                    "evidence": ["Led the distributed database migration personally."],
                    "feedback": "Outstanding end-to-end agency and delivery accountability.",
                },
                "technical_roadblocks": {
                    "status": "GOOD",
                    "evidence": ["Identified query bottlenecks and indexed key columns."],
                    "feedback": "Methodical root cause diagnosis under high load.",
                },
                "conflict_and_collaboration": {
                    "status": "GOOD",
                    "evidence": ["Aligned product and engineering on realistic scope."],
                    "feedback": "Collaborated effectively with stakeholders.",
                },
                "trade_offs_and_deadlines": {
                    "status": "STRONG",
                    "evidence": ["Decided against microservices in early MVP phase."],
                    "feedback": "Pragmatic engineering trade-off judgment.",
                },
                "delivery_and_excellence": {
                    "status": "STRONG",
                    "evidence": ["Instrumented Datadog metrics and alerting."],
                    "feedback": "High production standards and operational rigor.",
                },
                "overall_assessment": {
                    "readiness": "STRONG",
                    "summary": "Proven senior engineering lead with strong technical ownership.",
                },
                "strongest_points": ["Deep personal agency", "Clear system-level trade-offs"],
                "critical_gaps": [],
                "priority_improvements": ["Elaborate on quantitative business outcomes."],
            }
        }

    def test_valid_legacy_hiring_manager_payload_passes(self):
        raw = json.dumps(self._sample_valid_hm_payload())
        res = self.validator.validate_and_parse(raw)
        assert res["is_valid"] is True
        assert len(res["validation_errors"]) == 0
        assert res["parsed_report"] is not None
        assert "hiring_manager_evaluation" in res["parsed_report"]

    def test_missing_pillar_triggers_validation_error(self):
        payload = self._sample_valid_hm_payload()
        del payload["hiring_manager_evaluation"]["delivery_and_excellence"]
        raw = json.dumps(payload)
        res = self.validator.validate_and_parse(raw)
        assert res["is_valid"] is False
        assert any("delivery_and_excellence" in err for err in res["validation_errors"])

    def test_invalid_readiness_triggers_validation_error(self):
        payload = self._sample_valid_hm_payload()
        payload["hiring_manager_evaluation"]["overall_assessment"]["readiness"] = "SUPERB"
        raw = json.dumps(payload)
        res = self.validator.validate_and_parse(raw)
        assert res["is_valid"] is False
        assert any("overall_assessment.readiness" in err for err in res["validation_errors"])

    def test_valid_v28_hiring_manager_payload_passes(self):
        v28_payload = {
            "hiring_manager_evaluation": {
                "question_evaluations": [
                    {
                        "question_id": 101,
                        "question_text": "Tell me about a difficult technical roadblock.",
                        "pillar": "Technical Roadblocks",
                        "difficulty_level": "MEDIUM",
                        "response_state": "ANSWERED",
                        "rating": "GOOD",
                        "covered_points": [{"id": "P1", "description": "Identified root cause", "required": True}],
                        "missed_points": [],
                        "leadership_signals_demonstrated": ["Ownership", "Root cause focus"],
                        "leadership_signals_missing": [],
                        "critical_failure_triggered": None,
                        "evidence": [{"point_id": "P1", "quote": "I analyzed the latency spike in p99 metrics."}],
                        "observation": "Demonstrated solid technical leadership.",
                        "top_fix": "Add business impact metric.",
                        "coaching": None,
                    }
                ],
                "pillar_evaluations": [
                    {
                        "pillar": "Technical Roadblocks",
                        "rating": "GOOD",
                        "summary": "Effectively isolates issues.",
                        "strengths": ["Calm problem solver"],
                        "gaps": [],
                        "what_to_work_on": "Quantify cost impact.",
                    }
                ],
                "overall_assessment": {
                    "rating": "GOOD",
                    "executive_summary": "Strong engineering leader with deep ownership.",
                    "top_strengths": ["Root-cause analysis", "Decisiveness"],
                    "priority_improvements": ["Mention business ROI earlier"],
                    "next_practice_focus": "Executive stakeholder communication",
                },
                "behavioral_delivery_analysis": {
                    "directness": "Direct",
                    "structured_storytelling": "STAR structured",
                    "authenticity_and_poise": "Poised",
                    "conciseness_and_pacing": "Well paced",
                    "observation": "Clear, concise communication.",
                },
            }
        }
        res = self.validator.validate_and_parse(json.dumps(v28_payload))
        assert res["is_valid"] is True
        assert len(res["validation_errors"]) == 0
        assert res["parsed_report"] is not None

    def test_handles_unescaped_internal_quotes_gracefully(self):
        payload = self._sample_valid_hm_payload()
        serialized = json.dumps(payload)
        # Introduce unescaped internal quote into evidence
        bad_json = serialized.replace(
            "I profiled slow queries using pg_stat_statements.",
            'I said "we must optimize queries" to the team.'
        )
        res = self.validator.validate_and_parse(bad_json)
        assert res["is_valid"] is True
        assert res["parsed_report"] is not None

    def test_handles_trailing_commas_gracefully(self):
        payload = self._sample_valid_hm_payload()
        serialized = json.dumps(payload)
        # Introduce trailing comma
        bad_json = serialized.replace('["Composure under pressure"]', '["Composure under pressure", ]')
        res = self.validator.validate_and_parse(bad_json)
        assert res["is_valid"] is True
        assert res["parsed_report"] is not None

    def test_valid_v31_hiring_manager_payload_with_star_and_reality_locked_coaching(self):
        v31_payload = {
            "hiring_manager_evaluation": {
                "question_evaluations": [
                    {
                        "question_id": 101,
                        "question_text": "Tell me about a production roadblock and how you resolved it.",
                        "pillar": "Technical Roadblocks",
                        "difficulty_level": "HARD",
                        "response_state": "ANSWERED",
                        "rating": "STRONG",
                        "personal_agency": "STRONG",
                        "star_framework": {
                            "situation": {"present": True, "detail": "High-traffic checkout API suffering p99 timeouts.", "quote": "Our checkout service began dropping 15% of requests at peak."},
                            "task": {"present": True, "detail": "Lead the task force to eliminate p99 spikes.", "quote": "I took full responsibility to isolate the bottleneck within 24 hours."},
                            "action": {"present": True, "detail": "Instrumented distributed tracing and redesigned connection pooling.", "quote": "I rewrote the database connection pool configuration and added Redis read-replicas."},
                            "result": {"present": True, "detail": "Latency reduced from 2.4s to 45ms.", "quote": "p99 dropped from 2400ms to 45ms, eliminating all dropoffs."}
                        },
                        "rubric_points_evaluated": {
                            "covered_points": [{"id": 1, "description": "Diagnosed bottleneck with telemetry", "core": True}],
                            "partially_covered_points": [],
                            "missed_points": []
                        },
                        "leadership_signals_demonstrated": ["Extreme Ownership", "Deep Technical Rigor"],
                        "leadership_signals_missing": [],
                        "critical_failure_triggered": None,
                        "evidence": [{"point_id": 1, "quote": "I analyzed the telemetry and saw connection exhaustion."}],
                        "observation": "Exemplary senior engineering leadership with strong personal agency.",
                        "top_fix": "Quantify cost savings alongside latency drops.",
                        "coaching": None,
                        "reality_locked_coaching": {
                            "identified_pattern": "STRONG_TECHNICAL_DELIVERY",
                            "reality_anchor": "Demonstrated full end-to-end agency and metrics-driven resolution.",
                            "recommended_action": "Carry this level of rigor into executive strategy meetings."
                        },
                        "flags": []
                    }
                ],
                "pillar_evaluations": [
                    {
                        "pillar": "Technical Roadblocks",
                        "rating": "STRONG",
                        "summary": "Demonstrated master-level root-cause problem solving.",
                        "strengths": ["Decisive under pressure", "Metrics-driven"],
                        "gaps": [],
                        "what_to_work_on": "Share post-mortem across teams."
                    }
                ],
                "final_assessment": {
                    "leadership_readiness": "STRONG",
                    "technical_depth_and_rigor": "STRONG",
                    "culture_and_collaboration": "ADEQUATE",
                    "delivery_execution": "STRONG"
                },
                "overall_assessment": {
                    "rating": "STRONG",
                    "executive_summary": "Exceptional senior engineering candidate with proven technical ownership and high agency.",
                    "top_strengths": ["End-to-end accountability", "Root-cause diagnosis"],
                    "priority_improvements": ["Highlight business ROI metrics"],
                    "next_practice_focus": "Cross-functional stakeholder alignment"
                },
                "behavioral_delivery_analysis": {
                    "directness": "Direct",
                    "structured_storytelling": "STAR structured",
                    "authenticity_and_poise": "Poised",
                    "conciseness_and_pacing": "Well paced",
                    "observation": "Clear, direct, and structured communication."
                }
            }
        }
        res = self.validator.validate_and_parse(json.dumps(v31_payload))
        assert res["is_valid"] is True
        assert len(res["validation_errors"]) == 0
        assert res["parsed_report"] is not None
        assert res["parsed_report"]["hiring_manager_evaluation"]["question_evaluations"][0]["rating"] == "STRONG"
        assert res["parsed_report"]["hiring_manager_evaluation"]["final_assessment"]["culture_and_collaboration"] == "ADEQUATE"


# =============================================================================
# AssessmentEngine — Hiring Manager Question Selection Tests
# =============================================================================


class TestAssessmentEngineHiringManagerQuestions(unittest.TestCase):

    def test_selects_timed_questions_for_15_minute_budget(self):
        """Rule: For 15 minutes (900s), candidate receives as many questions as fit the time budget (not a fixed 5)."""
        from fapi.ai_prep.core.assessment_engine.engine import AssessmentEngine
        engine = AssessmentEngine()
        # Questions with 150s each -> 900s / 150s = 6 questions
        available = [
            {
                "id": i,
                "category": "HIRING_MANAGER",
                "is_active": True,
                "question_text": f"HM Question {i}",
                "difficulty_level": "MEDIUM",
                "time_limit_seconds": 150,
            }
            for i in range(1, 15)
        ]
        selected = engine.select_questions_for_assessment("HIRING_MANAGER", available, limit=6)
        total_time = sum(q.get("time_limit_seconds", 120) for q in selected)
        # Should select 6 questions (6 * 150s = 900s)
        assert len(selected) == 6
        assert total_time == 900
        assert all(q["category"] == "HIRING_MANAGER" for q in selected)

    def test_respects_explicit_limit_when_provided(self):
        """Rule: If an explicit limit is provided, it respects the limit."""
        from fapi.ai_prep.core.assessment_engine.engine import AssessmentEngine
        engine = AssessmentEngine()
        available = [
            {
                "id": i,
                "category": "HIRING_MANAGER",
                "is_active": True,
                "question_text": f"HM Question {i}",
                "difficulty_level": "MEDIUM",
                "time_limit_seconds": 90,
            }
            for i in range(1, 15)
        ]
        selected = engine.select_questions_for_assessment("HIRING_MANAGER", available, limit=4)
        assert len(selected) == 4

    def test_adaptive_difficulty_prioritizes_harder_for_strong_candidates(self):
        """Rule: Strong candidates get prioritized HARD and MEDIUM questions."""
        from fapi.ai_prep.core.assessment_engine.engine import AssessmentEngine
        engine = AssessmentEngine()
        available = [
            {"id": 1, "category": "HIRING_MANAGER", "difficulty_level": "EASY", "time_limit_seconds": 150, "is_active": True},
            {"id": 2, "category": "HIRING_MANAGER", "difficulty_level": "EASY", "time_limit_seconds": 150, "is_active": True},
            {"id": 3, "category": "HIRING_MANAGER", "difficulty_level": "MEDIUM", "time_limit_seconds": 150, "is_active": True},
            {"id": 4, "category": "HIRING_MANAGER", "difficulty_level": "MEDIUM", "time_limit_seconds": 150, "is_active": True},
            {"id": 5, "category": "HIRING_MANAGER", "difficulty_level": "HARD", "time_limit_seconds": 150, "is_active": True},
            {"id": 6, "category": "HIRING_MANAGER", "difficulty_level": "HARD", "time_limit_seconds": 150, "is_active": True},
        ]
        selected_strong = engine.select_questions_for_assessment(
            "HIRING_MANAGER", available, limit=2, previous_readiness="STRONG"
        )
        diffs = [q["difficulty_level"] for q in selected_strong]
        assert "HARD" in diffs


class TestBuildHiringManagerEvalDict(unittest.TestCase):
    """Tests for _build_hiring_manager_eval_dict and dispatching in build_assessment_eval_dict."""

    def test_hiring_manager_eval_dict_extraction(self):
        from fapi.ai_prep.utils.aiprep_utils import (
            _build_hiring_manager_eval_dict,
            build_assessment_eval_dict,
        )

        hm_payload = {
            "overall_assessment": {
                "rating": "GOOD",
                "executive_summary": "Demonstrated solid technical leadership and ownership.",
                "strongest_signal": "Ownership",
                "biggest_gap": "Deadlines",
                "top_strengths": ["Ownership", "Cross-team communication"],
                "priority_improvements": ["Deadlines under pressure"],
            },
            "competency_evaluations": [
                {
                    "competency": "Project Ownership",
                    "rating": "GOOD",
                    "summary": "Clear accountability.",
                }
            ],
            "question_evaluations": [
                {
                    "question_id": "hm-1",
                    "question_text": "Tell me about a project roadblock.",
                    "rating": "GOOD",
                }
            ],
            "behavioral_delivery_analysis": {
                "confidence": "HIGH",
            },
        }

        # Direct helper call
        direct_result = _build_hiring_manager_eval_dict(hm_payload)
        self.assertFalse(direct_result["insufficient_content"])
        self.assertEqual(direct_result["readiness"], "GOOD")
        self.assertEqual(
            direct_result["summary"],
            "Demonstrated solid technical leadership and ownership.",
        )
        self.assertEqual(direct_result["strongest_signal"], "Ownership")
        self.assertEqual(direct_result["biggest_gap"], "Deadlines")
        self.assertIn("hiring_manager_evaluation", direct_result)
        self.assertEqual(
            len(direct_result["general"]["competency_evaluations"]), 1
        )
        self.assertEqual(
            len(direct_result["general"]["question_evaluations"]), 1
        )

        # Dispatcher call via build_assessment_eval_dict
        dispatch_result = build_assessment_eval_dict(
            transcript_eval={"hiring_manager_evaluation": hm_payload}
        )
        self.assertEqual(dispatch_result["readiness"], "GOOD")
        self.assertEqual(
            dispatch_result["summary"],
            "Demonstrated solid technical leadership and ownership.",
        )
        self.assertIn("hiring_manager_evaluation", dispatch_result)


if __name__ == "__main__":
    unittest.main()



