"""
Assessment Engine — Pure Business Logic Coordinator.

Architecture Rules (MUST NOT VIOLATE):
  - ZERO database calls (no SQLAlchemy sessions, no ORM imports).
  - ZERO network/HTTP calls (no LLM API calls, no external services).
  - ZERO imports from fapi.ai_prep.crud, fapi.db, or any orchestrator layer.
  - All data enters and exits via plain Python dicts and primitives.
  - The ONLY way to communicate with this engine is through the Assessment Orchestrator.

Responsibilities:
  1. Question selection — filter, cap, and prepare questions for a given assessment type.
     INTRO and JD_INTRO types are capped at 1 question by design.
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

    # Default max for all other assessment types
    MAX_QUESTIONS_PER_ASSESSMENT: int = 5

    # Valid status transitions allowed by business rules
    VALID_TRANSITIONS: Dict[str, List[str]] = {
        "IN_PROGRESS": ["EVALUATING", "ABANDONED", "FAILED"],
        "EVALUATING":  ["COMPLETED", "FAILED"],
        "COMPLETED":   [],
        "FAILED":      [],
        "ABANDONED":   [],
    }

    def __init__(self) -> None:
        pass

    # =========================================================================
    # 1. QUESTION SELECTION
    # =========================================================================

    def select_questions_for_assessment(
        self,
        assessment_type: str,
        available_questions: List[Dict[str, Any]],
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Selects and sanitizes questions for a given assessment type.

        INTRO and JD_INTRO types are always capped at 1 question.
        All other types use `limit` or MAX_QUESTIONS_PER_ASSESSMENT.

        Args:
            assessment_type:     Category code (e.g. "INTRO", "JD_INTRO", "TECHNICAL").
            available_questions: Raw list of question dicts from CRUD layer.
            limit:               Explicit cap (ignored for INTRO/JD_INTRO — always 1).

        Returns:
            List of candidate-safe question dicts (no internal columns exposed).
        """
        normalized_type = assessment_type.upper().strip()

        # INTRO and JD_INTRO always get exactly 1 question
        if normalized_type in self.SINGLE_QUESTION_TYPES:
            max_q = 1
        else:
            max_q = limit or self.MAX_QUESTIONS_PER_ASSESSMENT

        # Filter to matching category and active only
        matched = [
            q for q in available_questions
            if str(q.get("category", "")).upper() == normalized_type
            and q.get("is_active", True)
        ]

        # Fall back to all active questions if no category match
        if not matched:
            logger.warning(
                "[AssessmentEngine] No questions found for type '%s'. Using all active questions.",
                normalized_type,
            )
            matched = [q for q in available_questions if q.get("is_active", True)]

        # Sort by difficulty: EXPERT > HARD > MEDIUM > EASY
        difficulty_order = {"EXPERT": 0, "HARD": 1, "MEDIUM": 2, "EASY": 3}
        matched.sort(
            key=lambda q: difficulty_order.get(str(q.get("difficulty_level", "MEDIUM")).upper(), 2)
        )

        selected = matched[:max_q]

        logger.info(
            "[AssessmentEngine] Selected %d question(s) for type '%s' (from %d available).",
            len(selected), normalized_type, len(available_questions),
        )

        return [self._sanitize_question_for_candidate(q) for q in selected]

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

    def extract_overall_score(self, evaluation_result: Dict[str, Any]) -> Optional[float]:
        """
        Extracts the overall numerical score from an evaluation result dict.
        Supports both new schema ('overall_assessment' -> 'score') and legacy schemas.
        Coerces string scores to float. Returns None if unparseable.
        """
        if not evaluation_result or not isinstance(evaluation_result, dict):
            return None

        t_eval = evaluation_result.get("transcript_evaluation")
        if not t_eval or not isinstance(t_eval, dict):
            return None

        # Check new schema: overall_assessment -> score
        overall_obj = t_eval.get("overall_assessment")
        raw_score = None
        if isinstance(overall_obj, dict):
            raw_score = overall_obj.get("score")

        # Check legacy/fallback schemas
        if raw_score is None:
            raw_score = t_eval.get("overall_score")
        if raw_score is None:
            raw_score = t_eval.get("score")

        if raw_score is None:
            return None

        try:
            return float(raw_score)
        except (ValueError, TypeError):
            return None

    # =========================================================================
    # 3. ELIGIBILITY CHECKS (pure logic, no DB)
    # =========================================================================

    def is_candidate_eligible(
        self,
        llm_check: Dict[str, Any],
        resume_check: Dict[str, Any],
    ) -> bool:
        """
        Pure business rule: candidate is eligible only if both LLM key
        and resume are configured and valid.

        Args:
            llm_check:    Result dict from crud.check_candidate_llm_key().
            resume_check: Result dict from crud.check_candidate_resume().

        Returns:
            True if candidate passes all prerequisite checks.
        """
        llm_ok = bool(llm_check.get("is_configured")) and llm_check.get("status") == "valid"
        resume_ok = bool(resume_check.get("has_resume")) and resume_check.get("status") == "valid"
        return llm_ok and resume_ok

    def compute_eligibility_message(
        self,
        llm_check: Dict[str, Any],
        resume_check: Dict[str, Any],
    ) -> str:
        """
        Generates a human-readable eligibility summary message.
        """
        issues = []
        if not llm_check.get("is_configured"):
            issues.append("LLM API key not configured")
        if not resume_check.get("has_resume"):
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
          IN_PROGRESS  → EVALUATING | ABANDONED | FAILED
          EVALUATING   → COMPLETED  | FAILED
          COMPLETED    → (terminal — no transitions)
          FAILED       → (terminal — no transitions)
          ABANDONED    → (terminal — no transitions)
        """
        allowed = self.VALID_TRANSITIONS.get(current_status.upper(), [])
        return target_status.upper() in allowed

    def resolve_question_limit(self, assessment_type: str) -> int:
        """
        Returns the correct question limit for a given assessment type.
        INTRO and JD_INTRO → 1.  All others → MAX_QUESTIONS_PER_ASSESSMENT.
        """
        if assessment_type.upper() in self.SINGLE_QUESTION_TYPES:
            return 1
        return self.MAX_QUESTIONS_PER_ASSESSMENT


# Module-level alias for compatibility with orchestrator imports
AssessmentBusinessEngine = AssessmentEngine

__all__ = ["AssessmentEngine", "AssessmentBusinessEngine"]
