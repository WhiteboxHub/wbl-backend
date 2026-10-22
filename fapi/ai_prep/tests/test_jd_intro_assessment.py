"""
Unit and Regression Tests for Job Description (JD) Intro Assessment.

Covers:
1. EvalEngine prompt compilation and {jd_text} injection.
2. ScoresEngine output validation across the 10 diagnostic dimensions.
3. build_assessment_eval_dict response serialization.
4. Non-regression on existing INTRO and TECHNICAL assessments.
"""

import json
from pathlib import Path
import sys
import unittest
import pytest

# Ensure repository root is in sys.path
BASE_DIR = Path(__file__).resolve().parents[3]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fapi.ai_prep.core.llm_evaluation import EvalEngine
from fapi.ai_prep.core.scores_engine import ScoresEngine
from fapi.ai_prep.utils.aiprep_utils import build_assessment_eval_dict


def get_sample_valid_jd_payload() -> dict:
    """Helper returning a standard 10-dimension evaluation payload."""
    return {
        "jd_intro_evaluation": {
            "jd_validation": {
                "status": "VALID",
                "reason": "Clear Senior Backend role description",
            },
            "overall_assessment": {
                "jd_alignment": "STRONG_FIT",
                "readiness": "STRONG",
                "summary": "Strong alignment with FastAPI and distributed systems requirements.",
                "strongest_signal": "5 years of hands-on production microservices experience.",
                "biggest_gap": "Did not mention vector databases.",
            },
            "jd_analysis": {
                "role_title": "Senior AI & Backend Engineer",
                "seniority_level": "SENIOR",
                "domain": "Enterprise AI",
                "core_responsibilities": ["Build high-throughput APIs", "Design RAG workflows"],
                "must_have_requirements": ["Python", "FastAPI", "PostgreSQL"],
                "nice_to_have_requirements": ["Docker", "Kubernetes"],
                "tech_stack": {
                    "languages": ["Python", "SQL"],
                    "frameworks": ["FastAPI"],
                    "ai_ml": ["RAG", "Embeddings"],
                    "data": ["PostgreSQL", "Redis"],
                    "cloud": ["AWS"],
                    "devops_cicd": ["Docker"],
                    "tools": ["Git"],
                },
                "soft_skills_and_ownership": ["End-to-end ownership"],
            },
            "requirement_coverage": [
                {
                    "requirement": "Python & FastAPI Architecture",
                    "category": "TECHNICAL",
                    "importance": "MUST_HAVE",
                    "status": "COVERED",
                    "match_type": "EXACT",
                    "evidence": "I have spent 5 years building microservices with FastAPI.",
                    "note": "Excellently covered with ownership.",
                }
            ],
            "role_alignment": {
                "overall_status": "COVERED",
                "role_relevance": "COVERED",
                "responsibilities_alignment": "COVERED",
                "seniority_match": "MATCHES",
                "domain_fit": "COVERED",
                "observation": "Senior level presentation matches requirements.",
                "evidence": ["I have spent 5 years building microservices"],
            },
            "career_story": {
                "overall_status": "COVERED",
                "timeline": "COVERED",
                "roles": "COVERED",
                "career_transitions": "NOT_APPLICABLE",
                "leads_logically_to_target_role": "COVERED",
                "transitions_identified": [],
                "observation": "Clear career trajectory.",
                "evidence": [],
            },
            "current_role_and_project": {
                "overall_status": "COVERED",
                "current_role": "COVERED",
                "project_explained": "COVERED",
                "application_purpose": "COVERED",
                "users_or_customers": "COVERED",
                "business_problem": "COVERED",
                "personal_ownership": "COVERED",
                "relevance_to_jd": "COVERED",
                "observation": "Clear project context and business impact.",
                "evidence": [],
            },
            "technical_alignment": {
                "overall_status": "COVERED",
                "core_stack_alignment": "COVERED",
                "architecture_and_design_depth": "COVERED",
                "production_and_deployment": "COVERED",
                "scale_and_performance": "COVERED",
                "technologies_matching_jd": ["Python", "FastAPI", "PostgreSQL"],
                "equivalent_technologies": [],
                "jd_technologies_not_mentioned": ["Docker"],
                "other_technologies_mentioned": ["Redis"],
                "observation": "Core backend stack is aligned.",
                "evidence": [],
            },
            "value_proposition": {
                "overall_status": "COVERED",
                "why_this_role": "COVERED",
                "impact_and_outcomes": "COVERED",
                "differentiators": ["FastAPI microservices at scale"],
                "observation": "Good articulation of value.",
                "evidence": [],
            },
            "tailoring_quality": {
                "tailored_to_role": "STRONG",
                "relevant_experience_prioritized": "STRONG",
                "irrelevant_content_ratio": "LOW",
                "gap_bridging": "COVERED",
                "observation": "Spoke directly to role needs.",
                "evidence": [],
            },
            "introduction_quality": {
                "clarity": "STRONG",
                "coherence": "STRONG",
                "technical_depth": "STRONG",
                "business_context": "STRONG",
                "personal_ownership": "STRONG",
                "buzzword_density": "LOW",
                "length_appropriateness": "APPROPRIATE",
                "observation": "Clear spoken delivery.",
            },
            "strongest_points": ["FastAPI production background"],
            "critical_gaps": [],
            "priority_improvements": [
                {
                    "priority": 1,
                    "topic": "Mention containerization",
                    "guidance": "State your Docker deployment experience.",
                    "example": "We deployed all microservices on Docker containers.",
                }
            ],
            "suggested_opening": {
                "note": "Opening example built only from facts the candidate actually said.",
                "example": "Hi, I am a senior backend engineer with 5 years building FastAPI microservices.",
            },
            "final_assessment": {
                "jd_fit_summary": "Strong fit for the senior backend role.",
                "career_story_relevance": "High",
                "current_project_clarity": "High",
                "technical_alignment_depth": "High",
                "seniority_match": "High",
                "most_important_improvement": "Mention Docker and container orchestration.",
            },
        }
    }


class TestJDIntroPromptCompilation(unittest.TestCase):
    """Verifies prompt construction and variable injection in EvalEngine."""

    def setUp(self):
        self.engine = EvalEngine()

    def test_jd_intro_prompt_compilation_with_jd_text(self):
        """Rule 1: Injects jd_text, transcript, and resume cleanly into USER_PROMPT_TEMPLATE."""
        res = self.engine.build_prompt(
            assessment_type="JD_INTRO",
            transcript_text="I have 5 years building FastAPI microservices.",
            resume_json={"skills": ["Python", "FastAPI"]},
            jd_text="Seeking Senior AI Engineer with Python and FastAPI experience.",
        )
        self.assertIn("system_prompt", res)
        self.assertIn("user_prompt", res)
        self.assertIn("Seeking Senior AI Engineer with Python and FastAPI experience.", res["user_prompt"])
        self.assertIn("I have 5 years building FastAPI microservices.", res["user_prompt"])
        self.assertIn("You are an expert Interview Introduction Evaluator", res["system_prompt"])

    def test_jd_intro_prompt_fallback_when_jd_is_none(self):
        """Rule 2: When jd_text is None, safely defaults to placeholder text without crashing."""
        res = self.engine.build_prompt(
            assessment_type="JD_INTRO",
            transcript_text="Testing transcript without JD.",
            jd_text=None,
        )
        self.assertIn("[No Job Description provided by candidate]", res["user_prompt"])

    def test_jd_intro_exempt_from_role_header_prepending(self):
        """Rule 3: jd_intro has its own self-contained header and must not duplicate role titles."""
        res = self.engine.build_prompt(
            assessment_type="JD_INTRO",
            transcript_text="Testing header exemption.",
            jd_text="Some role text",
        )
        self.assertNotIn("You are an expert Jd Intro interview evaluator", res["system_prompt"])

    def test_regression_intro_and_technical_prompts(self):
        """Rule 4: Non-regression check ensuring standard INTRO and TECHNICAL compilation is untouched."""
        intro_res = self.engine.build_prompt(
            assessment_type="INTRO",
            transcript_text="Standard intro walkthrough.",
        )
        self.assertIn("You are an expert AI Engineer Interview Introduction Evaluator", intro_res["system_prompt"])
        self.assertNotIn("Jd Intro", intro_res["system_prompt"])

        tech_res = self.engine.build_prompt(
            assessment_type="TECHNICAL",
            transcript_text="Technical answer.",
        )
        self.assertIn("You are an expert Technical interview evaluator", tech_res["system_prompt"])


class TestJDIntroOutputValidation(unittest.TestCase):
    """Verifies ScoresEngine validation rules for JD Intro payloads."""

    def setUp(self):
        self.validator = ScoresEngine()

    def test_valid_jd_intro_payload_passes_validation(self):
        """Rule 1: A well-formed 10-dimension JD payload must pass validation with 0 errors."""
        payload = get_sample_valid_jd_payload()
        res = self.validator.validate_and_parse(json.dumps(payload))
        self.assertTrue(res["is_valid"], f"Validation failed: {res.get('validation_errors')}")
        self.assertEqual(len(res["validation_errors"]), 0)
        self.assertIsNotNone(res["parsed_report"])
        self.assertIn("jd_intro_evaluation", res["parsed_report"])

    def test_missing_required_dimension_fails_validation(self):
        """Rule 2: Omitting any required diagnostic block must trigger validation errors."""
        payload = get_sample_valid_jd_payload()
        del payload["jd_intro_evaluation"]["technical_alignment"]

        res = self.validator.validate_and_parse(json.dumps(payload))
        self.assertFalse(res["is_valid"])
        self.assertTrue(
            any("technical_alignment" in err for err in res["validation_errors"]),
            f"Expected error for missing 'technical_alignment', got: {res['validation_errors']}"
        )

    def test_invalid_readiness_enum_fails_validation(self):
        """Rule 3: Non-standard readiness values must fail enum validation."""
        payload = get_sample_valid_jd_payload()
        payload["jd_intro_evaluation"]["overall_assessment"]["readiness"] = "INVALID_READINESS"

        res = self.validator.validate_and_parse(json.dumps(payload))
        self.assertFalse(res["is_valid"])
        self.assertTrue(
            any("readiness" in err for err in res["validation_errors"]),
            f"Expected error for invalid readiness enum, got: {res['validation_errors']}"
        )

    def test_invalid_jd_status_enum_fails_validation(self):
        """Rule 4: Step 0 status outside VALID/PARTIAL/INVALID must fail validation."""
        payload = get_sample_valid_jd_payload()
        payload["jd_intro_evaluation"]["jd_validation"]["status"] = "CORRUPT_STATUS"

        res = self.validator.validate_and_parse(json.dumps(payload))
        self.assertFalse(res["is_valid"])
        self.assertTrue(
            any("jd_validation.status" in err for err in res["validation_errors"]),
            f"Expected error for jd_validation.status, got: {res['validation_errors']}"
        )


class TestJDIntroReportSerialization(unittest.TestCase):
    """Verifies build_assessment_eval_dict response serialization."""

    def test_build_assessment_eval_dict_for_jd_intro(self):
        """Rule 1: Correctly unpacks jd_intro_evaluation into unified API response structure."""
        payload = get_sample_valid_jd_payload()
        eval_dict = build_assessment_eval_dict(transcript_eval=payload)

        self.assertFalse(eval_dict["insufficient_content"])
        self.assertEqual(eval_dict["readiness"], "STRONG")
        self.assertIn("FastAPI", eval_dict["summary"])
        self.assertIn("5 years", eval_dict["strongest_signal"])
        self.assertIn("vector", eval_dict["biggest_gap"])
        self.assertIn("jd_intro_evaluation", eval_dict)
        self.assertIn("general", eval_dict)
        self.assertEqual(eval_dict["general"]["jd_validation"]["status"], "VALID")
        self.assertEqual(len(eval_dict["general"]["requirement_coverage"]), 1)
        self.assertIn("suggested_opening", eval_dict["general"])
