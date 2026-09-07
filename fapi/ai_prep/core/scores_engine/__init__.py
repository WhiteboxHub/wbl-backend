# =============================================================================
# Core Engine 5: Scores Engine (LLM Response Parser & Validator)
# =============================================================================
# Pure in-memory Python class (Zero DB queries, Zero network calls).
# Responsible for sanitizing raw LLM text, stripping markdown code fences,
# validating schema structure, and verifying checkpoint consistency.
# =============================================================================

import json
import re
from typing import Any, Dict, List, Optional


class ScoresEngine:
    """
    Core Engine 5: In-memory parser and schema validator for LLM output.
    Validates evaluation reports against the 11-point evaluation checklist and contract specifications.
    """

    AI_ENG_INTRO_CHECKPOINTS = [
        "introduced_self",
        "career_timeline_alignment",
        "career_transitions_explained",
        "rag_production_architecture",
        "agentic_ai_and_mcp",
        "technical_ownership_and_scale",
    ]

    LEGACY_INTRO_CHECKPOINTS = [
        "introduced_self",
        "career_transitions_covered",
        "current_role_and_ownership",
        "technical_depth_and_architecture",
        "data_and_ai_workflows",
        "tools_and_frameworks_articulation",
        "team_and_company_scope",
        "system_impact_and_scale",
    ]

    # Default alias
    MANDATORY_INTRO_CHECKPOINTS = AI_ENG_INTRO_CHECKPOINTS

    def __init__(self) -> None:
        pass

    def validate_and_parse(self, raw_llm_json_string: str) -> Dict[str, Any]:
        """
        Parses raw unverified LLM text output, strips code fences, validates structure,
        and returns a validated report conforming to Contract 6 (Scores_Engine_Output).

        Args:
            raw_llm_json_string: Untrusted raw text returned by the LLM.

        Returns:
            Dict conforming to Scores_Engine_Output:
            {
                "is_valid": bool,
                "validation_errors": List[str],
                "parsed_report": Optional[Dict[str, Any]]
            }
        """
        errors: List[str] = []

        if not raw_llm_json_string or not isinstance(raw_llm_json_string, str):
            return {
                "is_valid": False,
                "validation_errors": ["raw_llm_json_string must be a non-empty string"],
                "parsed_report": None,
            }

        # 1. Sanitize & extract clean JSON string
        cleaned_str = self._sanitize_raw_text(raw_llm_json_string)

        # 2. Parse JSON
        try:
            parsed_data = json.loads(cleaned_str)
        except json.JSONDecodeError as exc:
            return {
                "is_valid": False,
                "validation_errors": [f"Invalid JSON syntax: {str(exc)}"],
                "parsed_report": None,
            }

        if not isinstance(parsed_data, dict):
            return {
                "is_valid": False,
                "validation_errors": ["Parsed JSON must be an object/dict"],
                "parsed_report": None,
            }

        # 3. Validate Payload (Intro Evaluation, Audio, Video, or Master Assessment Report)
        if "intro_evaluation" in parsed_data:
            self._validate_intro_payload(parsed_data["intro_evaluation"], errors)
        elif "audio_evaluation" in parsed_data:
            self._validate_audio_payload(parsed_data["audio_evaluation"], errors)
        elif "video_evaluation" in parsed_data:
            self._validate_video_payload(parsed_data["video_evaluation"], errors)
        elif "scores_breakdown_json" in parsed_data:
            self._validate_legacy_report_payload(parsed_data, errors)
        else:
            errors.append(
                "Missing recognized evaluation root key: 'intro_evaluation', 'audio_evaluation', 'video_evaluation', or 'scores_breakdown_json'"
            )

        is_valid = len(errors) == 0

        return {
            "is_valid": is_valid,
            "validation_errors": errors,
            "parsed_report": parsed_data if is_valid else None,
        }

    def _sanitize_raw_text(self, text: str) -> str:
        """
        Strips markdown code fences (```json ... ```) and isolates outer JSON braces.
        """
        stripped = text.strip()

        # Remove markdown code fences
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
            stripped = re.sub(r"\s*```$", "", stripped)

        stripped = stripped.strip()

        # Extract first '{' to last '}' if extra text is present
        start_idx = stripped.find("{")
        end_idx = stripped.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            return stripped[start_idx : end_idx + 1]

        return stripped

    def _validate_intro_payload(
        self, intro: Dict[str, Any], errors: List[str]
    ) -> None:
        """
        Validates the clean Intro Evaluation structure against AI Engineering evaluation standards.
        Supports both the new intro.py schema and legacy checkpoint schema.
        """
        if not isinstance(intro, dict):
            errors.append("intro_evaluation must be a dictionary")
            return

        # Check if new AI Engineer intro prompt schema
        if "overall_assessment" in intro:
            overall = intro.get("overall_assessment")
            if not isinstance(overall, dict):
                errors.append("overall_assessment must be an object")
            else:
                readiness = overall.get("readiness")
                if readiness not in ("STRONG", "GOOD", "NEEDS_POLISH", "WEAK"):
                    errors.append(
                        f"overall_assessment.readiness '{readiness}' must be one of: STRONG, GOOD, NEEDS_POLISH, WEAK"
                    )

            for key in ["career_story", "current_role", "current_project", "introduction_quality", "technology_inventory", "final_assessment"]:
                if key not in intro or not isinstance(intro[key], dict):
                    errors.append(f"Missing or invalid object '{key}' in intro_evaluation")

            for list_key in ["strongest_points", "critical_gaps", "priority_improvements"]:
                if list_key not in intro or not isinstance(intro[list_key], list):
                    errors.append(f"Missing or invalid list '{list_key}' in intro_evaluation")
            return

        # Fallback: legacy checkpoint-based schema
        timeline_analysis = (
            intro.get("career_timeline_analysis")
            or intro.get("career_narrative_analysis")
            or intro.get("timeline_arc_analysis")
            or intro.get("timeline_analysis")
        )
        if not isinstance(timeline_analysis, dict):
            errors.append("Missing 'career_timeline_analysis' in intro_evaluation")

        timeline_check = (
            intro.get("timeline_verification")
            or intro.get("resume_claim_verification")
            or intro.get("timeline_vs_background_alignment")
        )
        if not isinstance(timeline_check, dict):
            errors.append("Missing 'timeline_verification' in intro_evaluation")

        checkpoints = intro.get("checkpoints")
        if not isinstance(checkpoints, dict):
            errors.append("Missing 'checkpoints' dictionary in intro_evaluation")
        else:
            if "career_timeline_alignment" in checkpoints:
                expected_checkpoints = self.AI_ENG_INTRO_CHECKPOINTS
            else:
                expected_checkpoints = self.LEGACY_INTRO_CHECKPOINTS

            passed_count = 0
            for cp_key in expected_checkpoints:
                if cp_key not in checkpoints:
                    errors.append(f"Missing mandatory checkpoint: '{cp_key}'")
                else:
                    cp_val = checkpoints[cp_key]
                    if not isinstance(cp_val, dict):
                        errors.append(f"Checkpoint '{cp_key}' must be an object")
                    else:
                        status = cp_val.get("status")
                        if status not in ("PASSED", "FAILED"):
                            errors.append(
                                f"Checkpoint '{cp_key}' status must be 'PASSED' or 'FAILED'"
                            )
                        if cp_val.get("covered") is True or status == "PASSED":
                            passed_count += 1

            summary = intro.get("checks_summary")
            total_expected = len(expected_checkpoints)
            if isinstance(summary, dict):
                summary["total_checks"] = total_expected
                summary["passed_checks"] = passed_count
                summary["failed_checks"] = total_expected - passed_count
                pass_ratio = passed_count / total_expected
                if pass_ratio >= 0.75:
                    summary["readiness_level"] = "READY"
                elif pass_ratio >= 0.5:
                    summary["readiness_level"] = "NEEDS_POLISH"
                else:
                    summary["readiness_level"] = "NOT_READY"

        improvements = (
            intro.get("priority_improvements")
            or intro.get("mistakes_identified")
            or intro.get("areas_for_improvement")
        )
        if improvements is not None and not isinstance(improvements, list):
            errors.append("'priority_improvements' must be a list if provided")

    def _validate_audio_payload(
        self, audio: Dict[str, Any], errors: List[str]
    ) -> None:
        """
        Validates audio_evaluation payload from audio_eval.py.
        """
        if not isinstance(audio, dict):
            errors.append("audio_evaluation must be a dictionary")
            return

        for section in ["summary", "factors", "recording_environment_context"]:
            if section not in audio or not isinstance(audio[section], dict):
                errors.append(f"Missing or invalid object '{section}' in audio_evaluation")

        if "key_findings" not in audio or not isinstance(audio["key_findings"], list):
            errors.append("Missing or invalid list 'key_findings' in audio_evaluation")

    def _validate_video_payload(
        self, video: Dict[str, Any], errors: List[str]
    ) -> None:
        """
        Validates video_evaluation payload from video_eval.py.
        """
        if not isinstance(video, dict):
            errors.append("video_evaluation must be a dictionary")
            return

        for section in ["summary", "factors", "recording_environment_context"]:
            if section not in video or not isinstance(video[section], dict):
                errors.append(f"Missing or invalid object '{section}' in video_evaluation")

        if "key_findings" not in video or not isinstance(video["key_findings"], list):
            errors.append("Missing or invalid list 'key_findings' in video_evaluation")

    def _validate_legacy_report_payload(
        self, report: Dict[str, Any], errors: List[str]
    ) -> None:
        """
        Validates full report payload if legacy 4-tier rubric is evaluated.
        """
        scores = report.get("scores_breakdown_json")
        if not isinstance(scores, dict):
            errors.append("Missing 'scores_breakdown_json'")
            return

        for dim in ["ai_engineering", "core_engineering", "non_technical", "business_acumen"]:
            if dim not in scores or not isinstance(scores[dim], dict):
                errors.append(f"Missing dimension '{dim}' in scores_breakdown_json")
            else:
                score_val = scores[dim].get("score")
                if not isinstance(score_val, (int, float)) or not (0 <= score_val <= 100):
                    errors.append(f"Dimension '{dim}' score must be between 0 and 100")
