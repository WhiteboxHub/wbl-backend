"""
Assessment Engine — Pure Business Logic Coordinator.

Architecture Rules (MUST NOT VIOLATE):
  - ZERO database calls (no SQLAlchemy sessions, no ORM imports).
  - ZERO network/HTTP calls (no LLM API calls, no external services).
  - ZERO imports from fapi.ai_prep.crud, fapi.db, or any orchestrator layer.
  - All data enters and exits via plain Python dicts and primitives.
  - The ONLY way to communicate with this engine is through the Assessment Orchestrator.

Responsibilities:
  1. Question selection — filter and prepare questions for a given assessment type.
     INTRO and JD_INTRO types always receive exactly 1 question.
  2. Context building — transform raw telemetry/transcript dicts into structured text
     contexts that the LLMEvaluationEngine (Srimanth) can consume.
  3. Candidate eligibility — pure pre-flight rule checks before an assessment starts.
  4. State validation — determine valid state transitions (pure logic, no DB).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AssessmentEngine:
    """
    Core Engine: Pure in-memory business logic coordinator for AI Prep assessments.

    This class contains no side effects. Every method is a pure transformation:
    given input data → returns output data. No DB, no HTTP, no external state.
    """

    # Assessment types that serve exactly 1 question (intro/jd-intro scope)
    SINGLE_QUESTION_TYPES: set = {"INTRO", "JD_INTRO"}

    # Valid status transitions allowed by business rules
    VALID_TRANSITIONS: Dict[str, List[str]] = {
        "IN_PROGRESS": ["EVALUATING", "FAILED"],
        "EVALUATING":  ["COMPLETED", "FAILED"],
        "COMPLETED":   [],
        "FAILED":      [],
    }
    
    # Number of questions for multi-question assessment types
    MULTI_QUESTION_LIMIT: int = 10

    # Difficulty distribution target counts keyed by readiness band
    DIFFICULTY_DISTRIBUTION: Dict[str, Dict[str, int]] = {
        "STRONG":       {"EXPERT": 3, "HARD": 4, "MEDIUM": 3, "EASY": 0},
        "GOOD":         {"EXPERT": 1, "HARD": 2, "MEDIUM": 6, "EASY": 1},
        "NEEDS_POLISH": {"EXPERT": 0, "HARD": 1, "MEDIUM": 4, "EASY": 5},
        "WEAK":         {"EXPERT": 0, "HARD": 0, "MEDIUM": 4, "EASY": 6},
        "DEFAULT":      {"EXPERT": 0, "HARD": 2, "MEDIUM": 5, "EASY": 3},
    }

    def __init__(self) -> None:
        pass

    # =========================================================================
    # 1. QUESTION SELECTION & ROUND-ROBIN
    # =========================================================================

    def select_questions_for_assessment(
        self,
        assessment_type: str,
        available_questions: List[Dict[str, Any]],
        limit: Optional[int] = None,
        previous_readiness: Optional[str] = None,
        previously_asked_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """Selects questions for an assessment type using adaptive distribution."""
        normalized_type = assessment_type.upper().strip()
        excluded_ids = set(previously_asked_ids or [])

        # INTRO and JD_INTRO are single-question assessments
        if normalized_type in self.SINGLE_QUESTION_TYPES:
            return self._select_single_intro_question(
                available_questions, normalized_type, excluded_ids
            )

        max_q = limit if limit is not None else self.MULTI_QUESTION_LIMIT
        matched = [
            q for q in available_questions
            if str(q.get("category", "")).upper() == normalized_type
            and q.get("is_active", True)
            and q.get("id") not in excluded_ids
        ] or [
            q for q in available_questions
            if str(q.get("category", "")).upper() == normalized_type
            and q.get("is_active", True)
        ]

        if not matched:
            logger.warning("[AssessmentEngine] No questions found for type '%s'.", normalized_type)
            return []

        selected = self._select_adaptive_questions(matched, previous_readiness, max_q)
        return [self._sanitize_question_for_candidate(q) for q in selected]

    def _select_single_intro_question(
        self, questions: List[Dict[str, Any]], category: str, excluded: set
    ) -> List[Dict[str, Any]]:
        """Handles single-question selection for INTRO / JD_INTRO."""
        matched = [
            q for q in questions
            if str(q.get("category", "")).upper() == category
            and q.get("is_active", True)
            and q.get("id") not in excluded
        ]
        if matched:
            selected = matched[:1]
        else:
            selected = [
                q for q in questions
                if str(q.get("category", "")).upper() == category
                and q.get("is_active", True)
            ][:1]
        return [self._sanitize_question_for_candidate(q) for q in selected]

    def _select_adaptive_questions(
        self, matched: List[Dict[str, Any]], readiness: Optional[str], max_q: int
    ) -> List[Dict[str, Any]]:
        """Applies adaptive difficulty and round-robin subcategory selection."""
        import random
        from collections import defaultdict

        dist = self.DIFFICULTY_DISTRIBUTION.get(
            (readiness or "").upper(), self.DIFFICULTY_DISTRIBUTION["DEFAULT"]
        )

        pools: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        for q in matched:
            diff = str(q.get("difficulty_level", "MEDIUM")).upper()
            pools[diff][q.get("sub_category") or "General"].append(q)

        for diff_dict in pools.values():
            for q_list in diff_dict.values():
                random.shuffle(q_list)

        selected: List[Dict[str, Any]] = []
        selected_ids: set = set()

        for diff, target_count in dist.items():
            picked = self._round_robin_pick(pools[diff], target_count, selected_ids)
            selected.extend(picked)

        if len(selected) < max_q:
            remaining = [q for q in matched if q.get("id") not in selected_ids]
            random.shuffle(remaining)
            selected.extend(remaining[: max_q - len(selected)])

        return selected[:max_q]

    def _round_robin_pick(
        self,
        subcat_pools: Dict[str, List[Dict[str, Any]]],
        target_count: int,
        selected_ids: set,
    ) -> List[Dict[str, Any]]:
        """Picks up to target_count questions rotating fairly across sub-categories."""
        import random
        sub_cats = list(subcat_pools.keys())
        if not sub_cats:
            return []

        random.shuffle(sub_cats)
        picked: List[Dict[str, Any]] = []
        cat_idx = 0

        while len(picked) < target_count:
            progress = False
            for _ in range(len(sub_cats)):
                cat = sub_cats[cat_idx % len(sub_cats)]
                cat_idx += 1
                pool = subcat_pools[cat]

                while pool:
                    q = pool.pop(0)
                    if q.get("id") not in selected_ids:
                        picked.append(q)
                        selected_ids.add(q.get("id"))
                        progress = True
                        break

                if len(picked) >= target_count:
                    break

            if not progress:
                break

        return picked

    def _sanitize_question_for_candidate(self, question: Dict[str, Any]) -> Dict[str, Any]:
        """
        Returns only the candidate-facing fields from a question dict.
        Internal/admin columns (rubric, evaluation hints, etc.) are excluded.
        """
        return {
            "question_id": question.get("id"),
            "question_text": question.get("question_text", ""),
            "category": question.get("category"),
            "sub_category": question.get("sub_category"),
            "difficulty_level": question.get("difficulty_level"),
        }

    # =========================================================================
    # 2. CONTEXT BUILDING
    # =========================================================================

    def build_qa_context(
        self,
        questions: List[Dict[str, Any]],
        transcript: Dict[str, Any],
    ) -> str:
        """
        Builds a structured Q&A context string from submitted questions and transcript.

        Used by the LLMEvaluationEngine to construct the transcript evaluation prompt.

        Args:
            questions:   List of question dicts (from assessment data record).
            transcript:  Transcript dict with 'full_text' (or 'text') key.

        Returns:
            Formatted multi-line string combining questions and transcript text.
        """
        lines: List[str] = []

        if questions:
            lines.append("=== Interview Questions ===")
            for idx, q in enumerate(questions, start=1):
                q_text = q.get("question_text") or q.get("text") or f"Question {idx}"
                lines.append(f"Q{idx}: {q_text}")
            lines.append("")

        full_text = ""
        if isinstance(transcript, dict):
            full_text = (
                transcript.get("full_text")
                or transcript.get("text")
                or transcript.get("transcript_text")
                or ""
            )

        lines.append("=== Candidate Transcript ===")
        lines.append(full_text.strip() if full_text else "[No transcript provided]")

        return "\n".join(lines)

    def build_audio_context(self, audio_telemetry: Dict[str, Any]) -> str:
        """
        Converts raw audio telemetry dict into a human-readable context string.
        Used by the LLMEvaluationEngine for audio prompt building.

        Args:
            audio_telemetry: Dict with fields like words_per_minute, silence_ratio_pct, etc.

        Returns:
            Formatted audio telemetry summary string.
        """
        if not audio_telemetry or not isinstance(audio_telemetry, dict):
            return "Audio telemetry: [Not available]"

        wpm = (
            audio_telemetry.get("speaking_pace_wpm")
            or audio_telemetry.get("words_per_minute")
            or audio_telemetry.get("wpm")
            or 0
        )
        silence = audio_telemetry.get("silence_ratio_pct", audio_telemetry.get("silence_ratio", 0))
        duration = audio_telemetry.get("speaking_duration_seconds", 0)
        filler_rate = audio_telemetry.get("filler_rate_per_min", audio_telemetry.get("filler_rate", 0))
        pause_count = audio_telemetry.get("pause_count", audio_telemetry.get("pauses", 0))
        avg_volume = audio_telemetry.get("avg_volume_db", -20.0)
        noise_level = audio_telemetry.get("background_noise_level", "LOW")
        clipping = audio_telemetry.get("clipping_detected", False)

        return (
            f"Audio Telemetry Summary:\n"
            f"  Speaking Pace:      {wpm} WPM\n"
            f"  Speaking Duration:  {duration}s\n"
            f"  Silence Ratio:      {silence}%\n"
            f"  Filler Rate:        {filler_rate} per minute\n"
            f"  Pause Count:        {pause_count}\n"
            f"  Average Volume:     {avg_volume} dB\n"
            f"  Background Noise:   {noise_level}\n"
            f"  Clipping Detected:  {clipping}"
        )

    def build_video_context(self, video_telemetry: Dict[str, Any]) -> str:
        """
        Converts raw video telemetry dict into a human-readable context string.
        Used by the LLMEvaluationEngine for video prompt building.

        Args:
            video_telemetry: Dict with fields like face_visible_pct, eye_contact_pct, etc.

        Returns:
            Formatted video telemetry summary string.
        """
        if not video_telemetry or not isinstance(video_telemetry, dict):
            return "Video telemetry: [Not available]"

        is_video = video_telemetry.get("is_video_mode", False)
        if not is_video:
            return "Video telemetry: [Audio-only session — no video data]"

        face_pct = video_telemetry.get("face_visible_pct", video_telemetry.get("face_detection_pct", 0))
        eye_contact = video_telemetry.get("eye_contact_pct", 0)
        screen_attention = video_telemetry.get("screen_attention_pct", 0)
        distraction = video_telemetry.get("distraction_level_pct", 0)
        stress = video_telemetry.get("stress_level", "Normal")
        head_nods = video_telemetry.get("head_nods_count", 0)

        return (
            f"Video Telemetry Summary:\n"
            f"  Face Visibility:    {face_pct}%\n"
            f"  Eye Contact:        {eye_contact}%\n"
            f"  Screen Attention:   {screen_attention}%\n"
            f"  Distraction Level:  {distraction}%\n"
            f"  Stress Level:       {stress}\n"
            f"  Head Nods:          {head_nods}"
        )

    # =========================================================================
    # 3. ELIGIBILITY CHECKS (pure logic, no DB)
    # =========================================================================

    def is_candidate_eligible(
        self,
        llm_check: Optional[Dict[str, Any]],
        resume_check: Optional[Dict[str, Any]],
    ) -> bool:
        """
        Pure business rule: candidate is eligible only if both LLM key
        and resume are configured and valid. Safely handles None inputs.

        Args:
            llm_check:    Result dict from crud.check_candidate_llm_key() (or None).
            resume_check: Result dict from crud.check_candidate_resume() (or None).

        Returns:
            True if candidate passes all prerequisite checks.
        """
        llm_dict = llm_check or {}
        resume_dict = resume_check or {}

        llm_ok = bool(llm_dict.get("is_configured")) and llm_dict.get("status") == "valid"
        resume_ok = bool(resume_dict.get("has_resume")) and resume_dict.get("status") == "valid"
        return llm_ok and resume_ok

    def compute_eligibility_message(
        self,
        llm_check: Optional[Dict[str, Any]],
        resume_check: Optional[Dict[str, Any]],
    ) -> str:
        """
        Generates a human-readable eligibility summary message. Safely handles None inputs.
        """
        llm_dict = llm_check or {}
        resume_dict = resume_check or {}

        issues = []
        if not llm_dict.get("is_configured"):
            issues.append("LLM API key not configured")
        if not resume_dict.get("has_resume"):
            issues.append("Resume not uploaded")

        if not issues:
            return "Candidate meets all prerequisites. Ready to start assessment."
        return "Candidate is not ready: " + "; ".join(issues) + "."

    # =========================================================================
    # 4. STATE VALIDATION (pure logic, no DB)
    # =========================================================================

    def is_valid_transition(self, current_status: str, target_status: str) -> bool:
        """
        Returns True if transitioning from current_status → target_status is allowed.

        Valid transitions:
          IN_PROGRESS  → EVALUATING | FAILED
          EVALUATING   → COMPLETED  | FAILED
          COMPLETED    → (terminal — no transitions)
          FAILED       → (terminal — no transitions)
        """
        allowed = self.VALID_TRANSITIONS.get(current_status.upper(), [])
        return target_status.upper() in allowed



# Module-level alias for compatibility with orchestrator imports
AssessmentBusinessEngine = AssessmentEngine

__all__ = ["AssessmentEngine", "AssessmentBusinessEngine"]
