# =============================================================================
# Core Engine 5: Scores Engine (LLM Response Parser & Validator)
# =============================================================================
# Pure in-memory Python class (Zero DB queries, Zero network calls).
# Responsible for sanitizing raw LLM text, stripping markdown code fences,
# validating schema structure, and verifying checkpoint consistency.
# =============================================================================

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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

    VALID_TECHNICAL_SCORE_BANDS = {
        "EXCELLENT", "GOOD", "MASTERED", "PROFICIENT",
        "AVERAGE", "POOR", "DEVELOPING", "NEEDS_REVISION",
    }

    REQUIRED_HM_PILLARS = [
        "project_ownership",
        "technical_roadblocks",
        "conflict_and_collaboration",
        "trade_offs_and_deadlines",
        "delivery_and_excellence",
    ]

    VALID_HM_OVERALL_RATINGS = {
        "EXCELLENT", "STRONG", "GOOD", "NEEDS_POLISH", "WEAK", "AVERAGE", "POOR",
    }

    VALID_HM_QUESTION_RATINGS = {
        "EXCELLENT", "STRONG", "GOOD", "NEEDS_POLISH", "WEAK", "AVERAGE", "POOR",
    }

    VALID_HM_SCORE_BANDS = {
        "EXCELLENT", "STRONG", "GOOD", "NEEDS_POLISH", "WEAK",
        "AVERAGE", "POOR", "NOT_TESTED",
    }

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
        stripped_str = raw_llm_json_string.strip()
        if stripped_str.startswith("```"):
            stripped_str = re.sub(r"^```(?:json)?\s*", "", stripped_str, flags=re.IGNORECASE)
            stripped_str = re.sub(r"\s*```$", "", stripped_str).strip()

        cleaned_str = self._sanitize_raw_text(raw_llm_json_string)

        # 2. Parse JSON
        parsed_data = None
        try:
            parsed_data = json.loads(cleaned_str, strict=True)
        except json.JSONDecodeError as exc:
            # Resilient fallback: strip trailing commas only after strict parse fails
            # This protects valid transcripts containing [1, 2, ] from quote corruption
            repaired_text = re.sub(r',\s*([}\]])', r'\1', cleaned_str)
            try:
                parsed_data = json.loads(repaired_text, strict=True)
            except json.JSONDecodeError:
                # Heuristic state-machine repair on truncated JSON (preserving tail content via stripped_str)
                parsed_data = (
                    self._attempt_json_repair(stripped_str)
                    or self._attempt_json_repair(cleaned_str)
                    or self._attempt_json_repair(repaired_text)
                )

            if parsed_data is None:
                return {
                    "is_valid": False,
                    "validation_errors": [f"Invalid JSON syntax: {str(exc)}"],
                    "parsed_report": None,
                }
            logger.warning("[ScoresEngine] Successfully repaired anomalous/truncated JSON response.")

        if not isinstance(parsed_data, dict):
            return {
                "is_valid": False,
                "validation_errors": ["Parsed JSON must be an object/dict"],
                "parsed_report": None,
            }

        # 3. Validate Payload (Recruiter, Intro, Hiring Manager, JD Intro, Technical, Audio, Video, or Master Assessment Report)
        if "recruiter_evaluation" in parsed_data:
            self._validate_recruiter_payload(parsed_data["recruiter_evaluation"], errors)
        elif "intro_evaluation" in parsed_data:
            self._validate_intro_payload(parsed_data["intro_evaluation"], errors)
        elif "hiring_manager_evaluation" in parsed_data:
            self._validate_hiring_manager_payload(parsed_data["hiring_manager_evaluation"], errors)
        elif "jd_intro_evaluation" in parsed_data:
            self._validate_jd_intro_payload(parsed_data["jd_intro_evaluation"], errors)
        elif "technical_evaluation" in parsed_data:
            self._validate_technical_payload(parsed_data["technical_evaluation"], errors)
        elif "audio_evaluation" in parsed_data:
            self._validate_audio_payload(parsed_data["audio_evaluation"], errors)
        elif "video_evaluation" in parsed_data:
            self._validate_video_payload(parsed_data["video_evaluation"], errors)
        elif "scores_breakdown_json" in parsed_data:
            self._validate_legacy_report_payload(parsed_data, errors)
        else:
            errors.append(
                "Missing recognized evaluation root key: 'recruiter_evaluation', 'hiring_manager_evaluation', 'intro_evaluation', 'jd_intro_evaluation', 'technical_evaluation', 'audio_evaluation', 'video_evaluation', or 'scores_breakdown_json'"
            )

        is_valid = len(errors) == 0

        return {
            "is_valid": is_valid,
            "validation_errors": errors,
            "parsed_report": parsed_data if is_valid else None,
        }

    def _sanitize_raw_text(self, text: str) -> str:
        """
        Strips markdown code fences, isolates outer JSON braces, and cleans minor syntax anomalies.
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
            stripped = stripped[start_idx : end_idx + 1]

        return stripped

    def _attempt_json_repair(self, s: str) -> Optional[Dict[str, Any]]:
        """
        Attempts robust state-machine repair on truncated JSON (cut off by token limits).
        Closes unclosed string literals and balances open brackets and braces.
        Avoids slicing inside string literals.
        """
        if not s or not isinstance(s, str):
            return None

        clean_text = s.strip()
        first_brace = clean_text.find("{")
        if first_brace != -1:
            clean_text = clean_text[first_brace:]

        def repair_and_close(raw: str) -> Optional[Dict[str, Any]]:
            stack: List[str] = []
            in_str = False
            escaped = False

            for char in raw:
                if escaped:
                    escaped = False
                    continue
                if char == "\\":
                    escaped = True
                    continue
                if char == '"':
                    in_str = not in_str
                    continue
                if not in_str:
                    if char in ("{", "["):
                        stack.append(char)
                    elif char == "}":
                        if stack and stack[-1] == "{":
                            stack.pop()
                    elif char == "]":
                        if stack and stack[-1] == "[":
                            stack.pop()

            candidate = raw
            if in_str:
                candidate += '"'

            candidate = re.sub(r',\s*$', '', candidate)
            candidate = re.sub(r':\s*$', ': null', candidate)
            candidate = re.sub(r',\s*"[^"]*"\s*$', '', candidate)
            candidate = re.sub(r',\s*$', '', candidate)

            # Re-compute stack to close remaining open containers
            final_stack: List[str] = []
            c_in_str = False
            c_escaped = False
            for char in candidate:
                if c_escaped:
                    c_escaped = False
                    continue
                if char == "\\":
                    c_escaped = True
                    continue
                if char == '"':
                    c_in_str = not c_in_str
                    continue
                if not c_in_str:
                    if char in ("{", "["):
                        final_stack.append(char)
                    elif char == "}":
                        if final_stack and final_stack[-1] == "{":
                            final_stack.pop()
                    elif char == "]":
                        if final_stack and final_stack[-1] == "[":
                            final_stack.pop()

            for opener in reversed(final_stack):
                if opener == "{":
                    candidate += "}"
                elif opener == "[":
                    candidate += "]"

            try:
                res = json.loads(candidate)
                if isinstance(res, dict):
                    return res
            except Exception:
                pass

            return None

        # 1. Try direct stack closure
        result = repair_and_close(clean_text)
        if result is not None:
            return result

        # 2. Try trimming back to the last balanced object boundary if needed
        last_obj_close = clean_text.rfind("}")
        if last_obj_close != -1:
            fallback_text = clean_text[: last_obj_close + 1]
            result = repair_and_close(fallback_text)
            if result is not None:
                return result

        return None

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

            # Ensure every technical section has a non-empty, actionable observation.
            # If the LLM returned an empty string, auto-repair using the section's own
            # status and technologies so the content stays dynamic (never hardcoded).
            _TECH_SECTION_KEYS = [
                "agentic_ai",
                "rag_and_retrieval",
                "software_engineering",
                "cloud_and_infrastructure",
                "cicd_and_delivery",
            ]
            for sec_key in _TECH_SECTION_KEYS:
                sec = intro.get(sec_key)
                if isinstance(sec, dict):
                    obs = str(sec.get("observation") or "").strip()
                    if not obs:
                        status_val = str(sec.get("overall_status") or "PARTIAL").capitalize()
                        techs = [t for t in (sec.get("technologies_mentioned") or []) if t]
                        tech_str = f", mentioning {', '.join(techs)}" if techs else ""
                        label = sec_key.replace("_", " ").title()
                        sec["observation"] = (
                            f"{label}: Your performance was evaluated as {status_val}{tech_str}. "
                            "Expand on your production architecture, the operational tradeoffs you "
                            "navigated, and your specific ownership of implementation decisions."
                        )

                    # Ensure key_observations is a non-empty list of actionable bullets.
                    # If the LLM omitted it or returned an empty list, generate a minimal
                    # dynamic fallback so the bullet section is never blank.
                    key_obs = sec.get("key_observations")
                    if not isinstance(key_obs, list) or not any(str(b).strip() for b in key_obs):
                        status_val = str(sec.get("overall_status") or "PARTIAL").capitalize()
                        techs = [t for t in (sec.get("technologies_mentioned") or []) if t]
                        label = sec_key.replace("_", " ").title()
                        bullet_tech = f" You mentioned: {', '.join(techs)}." if techs else ""
                        sec["key_observations"] = [
                            f"{label} was assessed as {status_val}.{bullet_tech}",
                            "Provide specific details on your production architecture, system design decisions, and operational ownership in this area.",
                        ]

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

    def _validate_hiring_manager_payload(
        self, hm: Dict[str, Any], errors: List[str]
    ) -> None:
        """
        Validates the hiring_manager_evaluation structure from hiring_manager_prompt.py.
        Supports both:
          1. V2.8 schema: question_evaluations, pillar_evaluations, overall_assessment (rating: GOOD/AVERAGE/POOR).
          2. Legacy schema: 5 named pillars (project_ownership, etc.), overall_assessment (readiness: STRONG/GOOD/etc.).
        """
        if not isinstance(hm, dict):
            errors.append("hiring_manager_evaluation must be a dictionary")
            return

        # 1. Overall assessment
        overall = hm.get("overall_assessment")
        if not isinstance(overall, dict):
            errors.append("Missing or invalid object 'overall_assessment' in hiring_manager_evaluation")
        else:
            readiness = str(
                overall.get("rating") or overall.get("readiness") or ""
            ).upper().strip()
            if not readiness:
                errors.append("overall_assessment missing 'rating'")
            elif readiness not in self.VALID_HM_OVERALL_RATINGS:
                errors.append(
                    f"overall_assessment.readiness / rating '{readiness}' must be one of: {', '.join(sorted(self.VALID_HM_OVERALL_RATINGS))}"
                )

        # 2. Check if v2.8+/v3.4 schema (question_evaluations present)
        if "question_evaluations" in hm:
            q_evals = hm.get("question_evaluations")
            if not isinstance(q_evals, list):
                errors.append("question_evaluations must be a list")
            elif len(q_evals) == 0:
                errors.append("question_evaluations must not be empty")
            else:
                for idx, q_eval in enumerate(q_evals):
                    if not isinstance(q_eval, dict):
                        errors.append(f"question_evaluations[{idx}] must be an object")
                        continue
                    qid = q_eval.get("question_id") if "question_id" in q_eval else q_eval.get("id")
                    if qid is None:
                        errors.append(f"question_evaluations[{idx}] missing 'question_id'")
                    q_rating = str(q_eval.get("rating", "")).upper().strip()
                    if not q_rating:
                        errors.append(f"question_evaluations[{idx}] missing 'rating'")
                    elif q_rating not in self.VALID_HM_QUESTION_RATINGS:
                        errors.append(
                            f"question_evaluations[{idx}].rating '{q_rating}' must be one of: {', '.join(sorted(self.VALID_HM_QUESTION_RATINGS))}"
                        )

            p_evals = hm.get("competency_evaluations") or hm.get("pillar_evaluations")
            if p_evals is None or not isinstance(p_evals, list) or len(p_evals) == 0:
                errors.append("competency_evaluations must be a non-empty list")
            else:
                for idx, comp in enumerate(p_evals):
                    if not isinstance(comp, dict):
                        errors.append(f"competency_evaluations[{idx}] must be an object")
                        continue
                    c_rating = str(comp.get("rating", "")).upper().strip()
                    if c_rating and c_rating not in self.VALID_HM_SCORE_BANDS:
                        errors.append(
                            f"competency_evaluations[{idx}].rating '{c_rating}' must be one of: {', '.join(sorted(self.VALID_HM_SCORE_BANDS))}"
                        )

        else:
            # Legacy schema: Required 5 core competency pillars
            for pillar_key in self.REQUIRED_HM_PILLARS:
                pillar = hm.get(pillar_key)
                if not isinstance(pillar, dict):
                    errors.append(f"Missing or invalid pillar object '{pillar_key}' in hiring_manager_evaluation")
                    continue

                status = str(pillar.get("status", "")).upper().strip()
                if status not in self.VALID_HM_SCORE_BANDS:
                    errors.append(
                        f"pillar '{pillar_key}'.status must be one of: {', '.join(sorted(self.VALID_HM_SCORE_BANDS))}"
                    )

                # Validate evidence is a list of strings if present
                if "evidence" in pillar and not isinstance(pillar["evidence"], list):
                    errors.append(f"pillar '{pillar_key}'.evidence must be a list of strings")

            # Top-level summary & coaching lists in legacy
            for list_key in ["strongest_points", "critical_gaps", "priority_improvements"]:
                if list_key not in hm or not isinstance(hm[list_key], list):
                    errors.append(f"Missing or invalid list '{list_key}' in hiring_manager_evaluation")

        # Final assessment object (optional)
        if "final_assessment" in hm and not isinstance(hm["final_assessment"], dict):
            errors.append("'final_assessment' must be an object if provided in hiring_manager_evaluation")

    def _validate_jd_intro_payload(
        self, jd_intro: Dict[str, Any], errors: List[str]
    ) -> None:
        """
        Validates the JD Intro Evaluation structure against JD evaluation standards.
        Ensures adherence to the 10 core dimensions, required enum ratings, and bounded lists.
        """
        if not isinstance(jd_intro, dict):
            errors.append("jd_intro_evaluation must be a dictionary")
            return
        # 1. Step 0 Validation: jd_validation
        jd_val = jd_intro.get("jd_validation")
        if not isinstance(jd_val, dict):
            errors.append("Missing or invalid object 'jd_validation' in jd_intro_evaluation")
        else:
            val_status = jd_val.get("status")
            if val_status not in ("VALID", "PARTIAL", "INVALID"):
                errors.append(
                    f"jd_validation.status '{val_status}' must be one of: VALID, PARTIAL, INVALID"
                )
        # 2. Overall Assessment
        overall = jd_intro.get("overall_assessment")
        if not isinstance(overall, dict):
            errors.append("Missing or invalid object 'overall_assessment' in jd_intro_evaluation")
        else:
            readiness = overall.get("readiness")
            if readiness not in ("STRONG", "GOOD", "NEEDS_POLISH", "WEAK"):
                errors.append(
                    f"overall_assessment.readiness '{readiness}' must be one of: STRONG, GOOD, NEEDS_POLISH, WEAK"
                )
            alignment = overall.get("jd_alignment")
            if alignment and alignment not in ("STRONG_FIT", "GOOD_FIT", "PARTIAL_FIT", "WEAK_FIT"):
                errors.append(
                    f"overall_assessment.jd_alignment '{alignment}' must be one of: STRONG_FIT, GOOD_FIT, PARTIAL_FIT, WEAK_FIT"
                )
        # 3. Required Dictionary Blocks (10 Dimensions)
        required_objects = [
            "jd_analysis",
            "role_alignment",
            "career_story",
            "current_role_and_project",
            "technical_alignment",
            "value_proposition",
            "tailoring_quality",
            "introduction_quality",
            "suggested_opening",
            "final_assessment",
        ]
        for key in required_objects:
            if key not in jd_intro or not isinstance(jd_intro[key], dict):
                errors.append(f"Missing or invalid object '{key}' in jd_intro_evaluation")
        # 4. Required Lists
        required_lists = [
            "requirement_coverage",
            "strongest_points",
            "critical_gaps",
            "priority_improvements",
        ]
        for list_key in required_lists:
            if list_key not in jd_intro or not isinstance(jd_intro[list_key], list):
                errors.append(f"Missing or invalid list '{list_key}' in jd_intro_evaluation")
        # 5. Requirement Coverage Item Validation
        req_coverage = jd_intro.get("requirement_coverage")
        if isinstance(req_coverage, list):
            valid_statuses = {"COVERED", "PARTIAL", "NOT_MENTIONED", "NOT_APPLICABLE"}
            for idx, item in enumerate(req_coverage):
                if not isinstance(item, dict):
                    errors.append(f"requirement_coverage[{idx}] must be an object")
                    continue
                if not item.get("requirement"):
                    errors.append(f"requirement_coverage[{idx}] missing 'requirement' name")
                item_status = item.get("status")
                if item_status not in valid_statuses:
                    errors.append(
                        f"requirement_coverage[{idx}].status '{item_status}' must be one of: {', '.join(sorted(valid_statuses))}"
                    )

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
        Validates video_evaluation payload from video_prompt.py.
        Checks top-level sections and the 5 required factor keys inside 'factors'.
        """
        if not isinstance(video, dict):
            errors.append("video_evaluation must be a dictionary")
            return

        for section in ["summary", "factors", "recording_environment_context"]:
            if section not in video or not isinstance(video[section], dict):
                errors.append(f"Missing or invalid object '{section}' in video_evaluation")

        if "key_findings" not in video or not isinstance(video["key_findings"], list):
            errors.append("Missing or invalid list 'key_findings' in video_evaluation")

        # Deep-validate the 5 required factor keys inside 'factors'
        factors = video.get("factors")
        if isinstance(factors, dict):
            required_factor_keys = [
                "camera_framing_centering",
                "camera_angle_gaze_alignment",
                "primary_display_orientation",
                "off_screen_gaze_duration",
                "observable_physical_tension",
            ]
            for key in required_factor_keys:
                if key not in factors or not isinstance(factors[key], dict):
                    errors.append(
                        f"Missing or invalid object '{key}' in video_evaluation.factors"
                    )
                else:
                    factor_status = factors[key].get("status")
                    if factor_status not in (
                        "STRONG", "ADEQUATE", "NEEDS_WORK", "INSUFFICIENT_DATA"
                    ):
                        errors.append(
                            f"video_evaluation.factors.{key}.status must be one of "
                            f"STRONG, ADEQUATE, NEEDS_WORK, INSUFFICIENT_DATA"
                        )

    def _validate_recruiter_payload(
        self, recruiter: Dict[str, Any], errors: List[str]
    ) -> None:
        """
        Validates the clean Recruiter Screening Evaluation structure against screening evaluation standards.
        """
        if not isinstance(recruiter, dict):
            errors.append("recruiter_evaluation must be a dictionary")
            return

        if "overall_assessment" in recruiter:
            overall = recruiter.get("overall_assessment")
            if not isinstance(overall, dict):
                errors.append("overall_assessment must be an object")
            else:
                readiness = overall.get("readiness")
                if readiness and readiness not in ("STRONG", "GOOD", "NEEDS_POLISH", "WEAK"):
                    errors.append(
                        f"overall_assessment.readiness '{readiness}' must be one of: STRONG, GOOD, NEEDS_POLISH, WEAK"
                    )

        for list_key in ["strongest_points", "critical_gaps", "priority_improvements"]:
            if list_key in recruiter and not isinstance(recruiter[list_key], list):
                errors.append(f"Invalid list '{list_key}' in recruiter_evaluation")

    def _validate_technical_payload(
        self, technical: Dict[str, Any], errors: List[str]
    ) -> None:
        """Validates technical_evaluation payload from technical_prompt.py."""
        if not isinstance(technical, dict):
            errors.append("technical_evaluation must be a dictionary")
            return

        for key in ["overall_assessment", "subject_evaluations", "question_evaluations"]:
            if key not in technical:
                errors.append(f"Missing required key '{key}' in technical_evaluation")

        q_evals = technical.get("question_evaluations")
        if q_evals is not None:
            if not isinstance(q_evals, list):
                errors.append("technical_evaluation.question_evaluations must be a list")
            elif len(q_evals) == 0:
                errors.append("technical_evaluation.question_evaluations must not be empty")
            else:
                for idx, qe in enumerate(q_evals):
                    if not isinstance(qe, dict):
                        errors.append(f"technical_evaluation.question_evaluations[{idx}] must be a dictionary")
                        continue
                    if not qe.get("question_id"):
                        errors.append(f"technical_evaluation.question_evaluations[{idx}] missing 'question_id'")
                    band = str(qe.get("rating") or qe.get("score_band") or "").upper()
                    if band not in self.VALID_TECHNICAL_SCORE_BANDS:
                        errors.append(
                            f"technical_evaluation.question_evaluations[{idx}] 'rating' must be one of "
                            f"{', '.join(sorted(self.VALID_TECHNICAL_SCORE_BANDS))}"
                        )

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


# Alias for clarity
LLMOutputValidator = ScoresEngine

__all__ = ["ScoresEngine", "LLMOutputValidator"]

