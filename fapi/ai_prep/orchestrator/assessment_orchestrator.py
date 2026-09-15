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
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Session
from fapi.db.database import SessionLocal
from fapi.ai_prep import crud
from fapi.ai_prep.core.assessment_engine import AssessmentEngine
from fapi.ai_prep.orchestrator import llm_orchestrator

logger = logging.getLogger(__name__)


@contextmanager
def _get_worker_db(db: Optional[Session] = None):
    """
    Context manager for thread pool worker database operations.
    If db is provided and is NOT a real SQLAlchemy Session (e.g. MagicMock in tests),
    yields db directly. Otherwise, creates a worker-scoped SessionLocal() instance.
    """
    if db is not None and not isinstance(db, Session):
        yield db
    else:
        session = SessionLocal()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


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

    def _load_ctx_worker():
        with _get_worker_db(db) as worker_db:
            return _load_assessment_context(worker_db, assessment_id)

    def _update_status_worker(status: str):
        with _get_worker_db(db) as worker_db:
            crud.update_assessment_status(worker_db, assessment_id, status)

    def _save_report_worker(report: Dict[str, Any]):
        with _get_worker_db(db) as worker_db:
            crud.save_assessment_report(worker_db, assessment_id, report)

    # Step 1: Load all context from DB (offloaded to thread pool)
    ctx = await asyncio.to_thread(_load_ctx_worker)
    candidate_id = ctx["candidate_id"]
    assessment_type = ctx["assessment_type"]

    logger.info(
        "[AssessmentOrchestrator] Context loaded: candidate=%d type=%s media=%s",
        candidate_id, assessment_type, ctx["media_type"],
    )

    # Step 2: Validate LLM config is available
    llm_config = ctx.get("llm_config")
    if (
        not llm_config
        or not isinstance(llm_config, dict)
        or not llm_config.get("is_configured")
        or not llm_config.get("api_key")
    ):
        await asyncio.to_thread(_update_status_worker, "FAILED")
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

    # Step 4: Dispatch evaluation, save report, and mark COMPLETED
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

        logger.info(
            "[AssessmentOrchestrator] LLM evaluation complete. Persisting report: assessment=%d",
            assessment_id,
        )

        parsed_report = {
            "transcript_evaluation": evaluation_result.get("transcript_evaluation"),
            "audio_evaluation": evaluation_result.get("audio_evaluation"),
            "video_evaluation": evaluation_result.get("video_evaluation"),
        }

        # Step 5: Persist report to DB (offloaded to thread pool)
        await asyncio.to_thread(_save_report_worker, parsed_report)

        # Step 6: Mark assessment as COMPLETED (offloaded to thread pool)
        await asyncio.to_thread(_update_status_worker, "COMPLETED")

    except Exception as exc:
        logger.error(
            "[AssessmentOrchestrator] Evaluation pipeline failed for assessment=%d: %s",
            assessment_id, exc,
        )
        try:
            await asyncio.to_thread(_update_status_worker, "FAILED")
        except Exception as status_exc:
            logger.error(
                "[AssessmentOrchestrator] Failed to update status to FAILED for assessment=%d: %s",
                assessment_id, status_exc,
            )
        raise

    logger.info(
        "[AssessmentOrchestrator] Evaluation pipeline complete: assessment=%d",
        assessment_id,
    )

    return {
        "assessment_id": assessment_id,
        "status": "COMPLETED",
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
        List of candidate-safe question dicts.
    """
    # Normalize assessment_type before querying the database
    normalized_type = (assessment_type or "").upper().strip()

    # Load all active questions for this normalized type
    items, _ = crud.list_questions(db, category=normalized_type, is_active=True, limit=100)
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
        assessment_type=normalized_type,
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
