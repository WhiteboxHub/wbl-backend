"""
Assessment Orchestrator — Top-Level Evaluation Pipeline Coordinator.

Architecture Rules (MUST NOT VIOLATE):
  - This layer owns ALL communication: DB reads/writes, engine calls, orchestrator calls.
  - ZERO business logic lives here — all decisions are delegated to engines.
  - Routes call this orchestrator; this orchestrator never calls routes.
  - The Assessment Orchestrator is the ONLY entry point for triggering evaluation.

Responsibilities:
  1. DB: Load assessment, telemetry data, and candidate config via CRUD.
  2. Engine: Delegate context building to AssessmentEngine (pure logic).
  3. LLM: Dispatch evaluation via LLMOrchestrator (handles API calls).
  4. DB: Persist report and update assessment status via CRUD.
  5. Return: Structured result dict ready for the route response.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from fapi.ai_prep import crud
from fapi.ai_prep.core.assessment_engine import AssessmentEngine
from fapi.ai_prep.orchestrator import llm_orchestrator

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# =============================================================================
# SECTION 1 — Assessment Data Loading (DB → plain dicts)
# =============================================================================


def _load_assessment_context(
    db: "Session",
    assessment_id: int,
) -> Dict[str, Any]:
    """
    Loads all data required for evaluation from the database via CRUD.
    Returns a flat dict of plain Python objects — no ORM objects passed further.

    Raises:
        ValueError: If the assessment or candidate cannot be found, or data is missing.
    """
    assessment = crud.get_assessment_by_id(db, assessment_id)
    if not assessment:
        raise ValueError(f"Assessment ID {assessment_id} not found.")

    candidate_id = assessment.candidate_id
    assessment_type = str(assessment.assessment_type or "INTRO").upper()
    media_type = str(assessment.media_type or "VIDEO").upper()
    job_description = assessment.job_description

    # Load telemetry data
    data_record = crud.get_assessment_data_by_assessment_id(db, assessment_id)
    questions: List[Dict[str, Any]] = []
    transcript: Dict[str, Any] = {}
    audio_telemetry: Dict[str, Any] = {}
    video_telemetry: Dict[str, Any] = {}

    if data_record:
        questions = data_record.questions or []
        transcript = data_record.transcript or {}
        audio_telemetry = data_record.audio_telemetry or {}
        video_telemetry = data_record.video_telemetry or {}

    # Set is_video_mode flag on video_telemetry for engines
    if "is_video_mode" not in video_telemetry:
        video_telemetry["is_video_mode"] = (media_type == "VIDEO")

    # Load candidate LLM config
    llm_config = crud.get_candidate_llm_config(db, candidate_id)

    # Load resume JSON for context enrichment
    resume_json = crud.get_candidate_resume_json(db, candidate_id)

    return {
        "assessment_id": assessment_id,
        "candidate_id": candidate_id,
        "assessment_type": assessment_type,
        "media_type": media_type,
        "job_description": job_description,
        "questions": questions,
        "transcript": transcript,
        "audio_telemetry": audio_telemetry,
        "video_telemetry": video_telemetry,
        "llm_config": llm_config,
        "resume_json": resume_json,
    }


# =============================================================================
# SECTION 2 — Core Evaluation Runner (main entry point)
# =============================================================================


async def run_full_evaluation(
    db: "Session",
    assessment_id: int,
) -> Dict[str, Any]:
    """
    Full async evaluation pipeline: load → build contexts → LLM eval → save report.

    This is the primary entry point called by routes after the candidate submits
    and triggers evaluation.

    Args:
        db:            SQLAlchemy session (provided by route dependency).
        assessment_id: The assessment to evaluate.

    Returns:
        Dict with keys: assessment_id, status, report (audio, video, transcript evals).

    Raises:
        ValueError: If assessment not found or LLM config is missing.
        Exception:  Propagates any unrecoverable LLM or network error.
    """
    logger.info("[AssessmentOrchestrator] Starting full evaluation: assessment_id=%d", assessment_id)

    # Step 1: Load all context from DB
    ctx = _load_assessment_context(db, assessment_id)
    candidate_id = ctx["candidate_id"]
    assessment_type = ctx["assessment_type"]

    logger.info(
        "[AssessmentOrchestrator] Context loaded: candidate=%d type=%s media=%s",
        candidate_id, assessment_type, ctx["media_type"],
    )

    # Step 2: Validate LLM config is available
    llm_config = ctx["llm_config"]
    if not llm_config.get("is_configured") or not llm_config.get("api_key"):
        # Update status to FAILED and raise
        crud.update_assessment_status(db, assessment_id, "FAILED")
        raise ValueError(
            f"Candidate {candidate_id} has no active LLM API key configured. "
            "Cannot run evaluation."
        )

    # Step 3: Build transcript text from transcript dict
    transcript_text = _extract_transcript_text(ctx["transcript"])

    logger.info(
        "[AssessmentOrchestrator] Dispatching LLM evaluation: candidate=%d type=%s",
        candidate_id, assessment_type,
    )

    # Step 4: Dispatch concurrent LLM evaluation via LLMOrchestrator
    try:
        evaluation_result = await llm_orchestrator.run_evaluation(
            candidate_id=candidate_id,
            assessment_type=assessment_type,
            transcript_text=transcript_text,
            audio_telemetry=ctx["audio_telemetry"],
            video_telemetry=ctx["video_telemetry"],
            resume_json=ctx["resume_json"],
            llm_config=llm_config,
        )
    except Exception as exc:
        logger.error(
            "[AssessmentOrchestrator] LLM evaluation failed: assessment=%d error=%s",
            assessment_id, exc,
        )
        crud.update_assessment_status(db, assessment_id, "FAILED")
        raise

    logger.info(
        "[AssessmentOrchestrator] LLM evaluation complete. Persisting report: assessment=%d",
        assessment_id,
    )

    # Step 5: Extract overall score from AssessmentEngine (pure logic)
    engine = AssessmentEngine()
    overall_score = engine.extract_overall_score(evaluation_result)

    # Build the parsed report dict for CRUD
    parsed_report = {
        "transcript_evaluation": evaluation_result.get("transcript_evaluation"),
        "audio_evaluation": evaluation_result.get("audio_evaluation"),
        "video_evaluation": evaluation_result.get("video_evaluation"),
        "overall_score": overall_score,
    }

    # Step 6: Persist report to DB
    crud.save_assessment_report(db, assessment_id, parsed_report)

    # Step 7: Mark assessment as COMPLETED
    crud.update_assessment_status(db, assessment_id, "COMPLETED")

    logger.info(
        "[AssessmentOrchestrator] Evaluation pipeline complete: assessment=%d score=%s",
        assessment_id, overall_score,
    )

    return {
        "assessment_id": assessment_id,
        "status": "COMPLETED",
        "overall_score": overall_score,
        "report": parsed_report,
    }


# =============================================================================
# SECTION 3 — Question Selection (DB + Engine coordination)
# =============================================================================


def get_questions_for_assessment(
    db: "Session",
    assessment_type: str,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Fetches questions from DB and delegates selection + sanitization to AssessmentEngine.

    This is called by routes when creating a new assessment session, so the candidate
    receives their question set at the start.

    Args:
        db:              Database session.
        assessment_type: The category code (e.g. "TECHNICAL", "INTRO").
        limit:           Optional cap on number of questions returned.

    Returns:
        List of candidate-safe question dicts (rubric stripped).
    """
    # Load all active questions for this type
    items, _ = crud.list_questions(db, category=assessment_type, is_active=True, limit=100)
    available = [
        {
            "id": q.id,
            "category": q.category,
            "sub_category": q.sub_category,
            "difficulty_level": q.difficulty_level,
            "question_text": q.question_text,
            "is_active": q.is_active,
        }
        for q in items
    ]

    engine = AssessmentEngine()
    return engine.select_questions_for_assessment(
        assessment_type=assessment_type,
        available_questions=available,
        limit=limit,
    )


# =============================================================================
# SECTION 4 — Eligibility Check (DB + Engine coordination)
# =============================================================================


def check_candidate_eligibility(
    db: "Session",
    candidate_id: int,
) -> Dict[str, Any]:
    """
    Checks whether a candidate meets all prerequisites to start an assessment.
    Delegates pure eligibility logic to AssessmentEngine.

    Args:
        db:           Database session.
        candidate_id: The candidate's ID.

    Returns:
        Dict with keys: eligible, candidate_id, llm_check, resume_check, message.
    """
    llm_check = crud.check_candidate_llm_key(db, candidate_id)
    resume_check = crud.check_candidate_resume(db, candidate_id)

    engine = AssessmentEngine()
    eligible = engine.is_candidate_eligible(llm_check, resume_check)
    message = engine.compute_eligibility_message(llm_check, resume_check)

    return {
        "eligible": eligible,
        "candidate_id": candidate_id,
        "llm_check": llm_check,
        "resume_check": resume_check,
        "message": message,
    }


# =============================================================================
# SECTION 5 — Helpers
# =============================================================================


def _extract_transcript_text(transcript: Dict[str, Any]) -> str:
    """
    Safely extracts full transcript text from a transcript dict.
    Handles multiple known field name variants.
    """
    if not transcript or not isinstance(transcript, dict):
        return ""

    return (
        transcript.get("full_text")
        or transcript.get("text")
        or transcript.get("transcript_text")
        or ""
    ).strip()
