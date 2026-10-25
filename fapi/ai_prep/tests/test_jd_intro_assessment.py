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
        self.assertIn("Technical Interview Evaluator", tech_res["system_prompt"])


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

    def test_zero_requirements_covered_calibrates_to_weak(self):
        """Rule 5: When 0 requirements are covered, readiness must auto-calibrate to WEAK and alignment to WEAK_FIT."""
        payload = get_sample_valid_jd_payload()
        # Set all requirements to NOT_MENTIONED
        for req in payload["jd_intro_evaluation"]["requirement_coverage"]:
            req["status"] = "NOT_MENTIONED"
        payload["jd_intro_evaluation"]["overall_assessment"]["readiness"] = "NEEDS_POLISH"
        payload["jd_intro_evaluation"]["overall_assessment"]["jd_alignment"] = "PARTIAL_FIT"

        res = self.validator.validate_and_parse(json.dumps(payload))
        self.assertTrue(res["is_valid"])
        oa = res["parsed_report"]["jd_intro_evaluation"]["overall_assessment"]
        self.assertEqual(oa["readiness"], "WEAK")
        self.assertEqual(oa["jd_alignment"], "WEAK_FIT")

    def test_70_30_weighting_and_banding_calibration(self):
        """Rule 6: 70% must-have + 30% nice-to-have weighting strictly calibrates readiness across brackets:
        >80% -> STRONG, 50-80% -> GOOD, 35-50% -> NEEDS_POLISH, <35% -> WEAK."""
        payload = get_sample_valid_jd_payload()

        # Create 10 must-haves: 6 COVERED, 4 NOT_MENTIONED -> 60% must-have
        # Create 2 nice-to-haves: 1 COVERED, 1 NOT_MENTIONED -> 50% nice-to-have
        # Total weighted = (60 * 0.70) + (50 * 0.30) = 42 + 15 = 57% -> GOOD band
        reqs = []
        for i in range(6):
            reqs.append({
                "requirement": f"Must Req {i}",
                "importance": "MUST_HAVE",
                "status": "COVERED",
                "in_resume": True,
            })
        for i in range(4):
            reqs.append({
                "requirement": f"Missing Must Req {i}",
                "importance": "MUST_HAVE",
                "status": "NOT_MENTIONED",
                "in_resume": True,
            })
        reqs.append({
            "requirement": "Nice Req 1",
            "importance": "NICE_TO_HAVE",
            "status": "COVERED",
            "in_resume": True,
        })
        reqs.append({
            "requirement": "Nice Req 2",
            "importance": "NICE_TO_HAVE",
            "status": "NOT_MENTIONED",
            "in_resume": True,
        })
        payload["jd_intro_evaluation"]["requirement_coverage"] = reqs
        payload["jd_intro_evaluation"]["overall_assessment"]["readiness"] = "STRONG"  # Over-inflated
        payload["jd_intro_evaluation"]["overall_assessment"]["jd_alignment"] = "STRONG_FIT"

        res = self.validator.validate_and_parse(json.dumps(payload))
        self.assertTrue(res["is_valid"])
        oa = res["parsed_report"]["jd_intro_evaluation"]["overall_assessment"]
        self.assertEqual(oa["readiness"], "GOOD")
        self.assertEqual(oa["jd_alignment"], "GOOD_FIT")
        self.assertIn("skill_breakdown", oa)
        self.assertEqual(oa["skill_breakdown"]["must_have_coverage_pct"], 60.0)
        self.assertEqual(oa["skill_breakdown"]["total_weighted_pct"], 57.0)

    def test_resume_verification_unverified_claims_handling(self):
        """Rule 7: Spoken requirements not present in resume (in_resume: false) are flagged and discounted."""
        payload = get_sample_valid_jd_payload()
        # Candidate speaks about 2 must-haves, but neither is on their resume!
        payload["jd_intro_evaluation"]["requirement_coverage"] = [
            {
                "requirement": "Kubernetes Orchestration",
                "importance": "MUST_HAVE",
                "status": "COVERED",
                "in_resume": False,
            },
            {
                "requirement": "Microservices in Go",
                "importance": "MUST_HAVE",
                "status": "COVERED",
                "in_resume": False,
            },
        ]
        # With in_resume=False, each gets 0.5 points -> 50% must-have -> GOOD (cannot be STRONG)
        payload["jd_intro_evaluation"]["overall_assessment"]["readiness"] = "STRONG"

        res = self.validator.validate_and_parse(json.dumps(payload))
        self.assertTrue(res["is_valid"])
        oa = res["parsed_report"]["jd_intro_evaluation"]["overall_assessment"]
        self.assertEqual(oa["readiness"], "GOOD")
        sb = oa.get("skill_breakdown", {})
        self.assertEqual(len(sb.get("unverified_spoken_claims", [])), 2)
        self.assertIn("Kubernetes Orchestration", sb["unverified_spoken_claims"])

    def test_resume_only_skills_earn_zero_credit_unless_spoken(self):
        """Rule 8: Skills present on resume (in_resume: True) award ZERO credit unless verbally spoken in transcript."""
        payload = get_sample_valid_jd_payload()
        # Candidate has 5 requirements on their resume (in_resume: True), but only speaks 1 in their introduction!
        payload["jd_intro_evaluation"]["requirement_coverage"] = [
            {
                "requirement": "Python FastAPI",
                "importance": "MUST_HAVE",
                "status": "COVERED",
                "in_resume": True,
                "evidence": "I build APIs in FastAPI daily.",
            },
            {
                "requirement": "Distributed Kafka",
                "importance": "MUST_HAVE",
                "status": "NOT_MENTIONED",
                "in_resume": True,
                "evidence": None,
            },
            {
                "requirement": "PostgreSQL Optimization",
                "importance": "MUST_HAVE",
                "status": "NOT_MENTIONED",
                "in_resume": True,
                "evidence": None,
            },
            {
                "requirement": "Docker & K8s",
                "importance": "MUST_HAVE",
                "status": "NOT_MENTIONED",
                "in_resume": True,
                "evidence": None,
            },
            {
                "requirement": "AWS Cloud Deployments",
                "importance": "MUST_HAVE",
                "status": "NOT_MENTIONED",
                "in_resume": True,
                "evidence": None,
            },
        ]
        # Only 1 out of 5 covered -> 20% coverage -> MUST calibrate to WEAK / WEAK_FIT
        payload["jd_intro_evaluation"]["overall_assessment"]["readiness"] = "STRONG"
        payload["jd_intro_evaluation"]["overall_assessment"]["jd_alignment"] = "STRONG_FIT"

        res = self.validator.validate_and_parse(json.dumps(payload))
        self.assertTrue(res["is_valid"])
        oa = res["parsed_report"]["jd_intro_evaluation"]["overall_assessment"]
        self.assertEqual(oa["readiness"], "WEAK")
        self.assertEqual(oa["jd_alignment"], "WEAK_FIT")
        self.assertEqual(oa["skill_breakdown"]["must_have_coverage_pct"], 20.0)

        # Also test guard against false positive where LLM hallucinated COVERED with evidence stating not spoken
        payload["jd_intro_evaluation"]["requirement_coverage"][1] = {
            "requirement": "Distributed Kafka",
            "importance": "MUST_HAVE",
            "status": "COVERED",
            "in_resume": True,
            "evidence": "Not mentioned in transcript, but candidate has 3 years on resume.",
        }
        res2 = self.validator.validate_and_parse(json.dumps(payload))
        self.assertTrue(res2["is_valid"])
        cov_item = res2["parsed_report"]["jd_intro_evaluation"]["requirement_coverage"][1]
        self.assertEqual(cov_item["status"], "NOT_MENTIONED")
        self.assertEqual(cov_item["verification_status"], "NOT_MENTIONED")


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
