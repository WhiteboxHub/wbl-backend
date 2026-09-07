"""
LLM Orchestrator — Evaluation Pipeline Coordinator.

Responsibilities:
  1. DB: Fetch and decrypt the candidate's active LLM API key.
  2. Prompt: Use EvalEngine to compile system + user prompts for each evaluation type.
  3. Execute: Dispatch concurrent async LLM calls via asyncio.gather().
  4. Validate: Parse and validate each LLM response with ScoresEngine.
  5. Return: Structured evaluation dicts ready for crud.save_assessment_report().

Architecture rule:
  - This layer owns ALL DB reads related to LLM config (zero DB inside llm_client.py).
  - llm_client.py receives a plain decrypted API key — it never queries the DB.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# =============================================================================
# SECTION 1 — DB: Fetch and Decrypt Candidate LLM API Key
# =============================================================================


def get_candidate_llm_config(db: Any, candidate_id: int) -> Dict[str, Any]:
    """
    Fetches the decrypted candidate LLM configuration via the crud layer.
    Isolates orchestrator from raw DB queries according to system architecture rules.
    """
    from fapi.ai_prep import crud
    return crud.get_candidate_llm_config(db, candidate_id)



# =============================================================================
# SECTION 2 — Single LLM call wrapper (prompt → raw JSON string)
# =============================================================================


async def _invoke_llm(
    *,
    call_label: str,
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    provider: Optional[str],
    model: Optional[str],
) -> str:
    """
    Fire one LLM request and return the raw response string.

    Args:
        call_label:    Human-readable label for logging (e.g. "audio_eval").
        system_prompt: System instruction block.
        user_prompt:   Candidate-specific user message.
        api_key:       Plain-text decrypted API key.
        provider:      Provider hint (e.g. "openai"). None → auto-detected from key prefix.
        model:         Model override. None → llm_client uses provider default.

    Returns:
        Raw LLM text response string.
    """
    from fapi.ai_prep.clients.llm_client import call_llm

    logger.info(
        "[LLMOrchestrator] Invoking LLM: call=%s provider=%s model=%s",
        call_label, provider, model,
    )

    response_text = await call_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        api_key=api_key,
        provider=provider,
        model=model,
    )

    logger.info(
        "[LLMOrchestrator] LLM responded: call=%s chars=%d",
        call_label, len(response_text),
    )
    return response_text


# =============================================================================
# SECTION 3 — Validate one LLM response through ScoresEngine
# =============================================================================


def _validate_response(call_label: str, raw_text: str) -> Dict[str, Any]:
    """
    Parse and validate a raw LLM text response through ScoresEngine.

    Returns:
        The parsed_report dict on success.

    Raises:
        ValueError: If ScoresEngine flags validation errors.
    """
    from fapi.ai_prep.core.scores_engine import ScoresEngine

    scores_engine = ScoresEngine()
    result = scores_engine.validate_and_parse(raw_text)

    if not result["is_valid"]:
        errors = "; ".join(result.get("validation_errors", []))
        logger.error(
            "[LLMOrchestrator] Validation failed: call=%s errors=%s",
            call_label, errors,
        )
        raise ValueError(
            f"LLM response validation failed for '{call_label}': {errors}"
        )

    logger.info("[LLMOrchestrator] Validation passed: call=%s", call_label)
    return result["parsed_report"]


# =============================================================================
# SECTION 4 — Core Async Evaluation Runner
# =============================================================================


async def run_evaluation(
    *,
    candidate_id: int,
    assessment_type: str,
    transcript_text: str,
    audio_telemetry: Dict[str, Any],
    video_telemetry: Dict[str, Any],
    resume_json: Optional[Any] = None,
    llm_config: Dict[str, Any],
    db: Any,
) -> Dict[str, Any]:
    """
    Core async orchestration: compile prompts → concurrent LLM calls → validate → return.

    Args:
        candidate_id:     Candidate DB ID (for logging/tracing).
        assessment_type:  Assessment category string (e.g. "INTRO", "TECHNICAL").
        transcript_text:  Full candidate speech transcript.
        audio_telemetry:  Acoustic metrics dict (9 fields).
        video_telemetry:  Visual metrics dict — must contain "is_video_mode" boolean key.
        resume_json:      Candidate resume/timeline forwarded into the transcript prompt.
        llm_config:       Output of get_candidate_llm_config() — {api_key, provider, model}.
        db:               SQLAlchemy session (passed through for future use).

    Returns:
        {
            "transcript_evaluation": dict,
            "audio_evaluation": dict,
            "video_evaluation": dict | None,   # None when audio-only session
        }

    Raises:
        ValueError:      If any LLM response fails ScoresEngine validation.
        LLMClientError:  Propagated from llm_client on auth / rate-limit / timeout errors.
    """
    from fapi.ai_prep.core.llm_evaluation import EvalEngine

    eval_engine = EvalEngine()

    api_key: str = llm_config["api_key"]
    provider: Optional[str] = llm_config.get("provider")
    model: Optional[str] = llm_config.get("model")

    is_video_mode: bool = bool(video_telemetry.get("is_video_mode", False))

    # ── 1. Compile all prompts (pure in-memory, zero I/O) ────────────────────

    logger.info(
        "[LLMOrchestrator] Building prompts: candidate=%d type=%s video_mode=%s",
        candidate_id, assessment_type, is_video_mode,
    )

    transcript_prompt = eval_engine.build_prompt(
        assessment_type=assessment_type,
        transcript_text=transcript_text,
        resume_json=resume_json,
    )
    audio_prompt = eval_engine.build_audio_prompt(audio_telemetry)

    video_prompt: Optional[Dict[str, str]] = None
    if is_video_mode:
        video_prompt = eval_engine.build_video_prompt(video_telemetry)

    # ── 2. Dispatch concurrent LLM calls ─────────────────────────────────────

    num_calls = 3 if is_video_mode else 2
    logger.info("[LLMOrchestrator] Dispatching %d concurrent LLM call(s).", num_calls)

    if is_video_mode:
        # 3 parallel calls: transcript + audio + video
        transcript_raw, audio_raw, video_raw = await asyncio.gather(
            _invoke_llm(
                call_label="transcript_eval",
                system_prompt=transcript_prompt["system_prompt"],
                user_prompt=transcript_prompt["user_prompt"],
                api_key=api_key,
                provider=provider,
                model=model,
            ),
            _invoke_llm(
                call_label="audio_eval",
                system_prompt=audio_prompt["system_prompt"],
                user_prompt=audio_prompt["user_prompt"],
                api_key=api_key,
                provider=provider,
                model=model,
            ),
            _invoke_llm(
                call_label="video_eval",
                system_prompt=video_prompt["system_prompt"],
                user_prompt=video_prompt["user_prompt"],
                api_key=api_key,
                provider=provider,
                model=model,
            ),
        )
    else:
        # 2 parallel calls: transcript + audio (video skipped for audio-only sessions)
        transcript_raw, audio_raw = await asyncio.gather(
            _invoke_llm(
                call_label="transcript_eval",
                system_prompt=transcript_prompt["system_prompt"],
                user_prompt=transcript_prompt["user_prompt"],
                api_key=api_key,
                provider=provider,
                model=model,
            ),
            _invoke_llm(
                call_label="audio_eval",
                system_prompt=audio_prompt["system_prompt"],
                user_prompt=audio_prompt["user_prompt"],
                api_key=api_key,
                provider=provider,
                model=model,
            ),
        )
        video_raw = None

    # ── 3. Validate all responses ─────────────────────────────────────────────

    logger.info("[LLMOrchestrator] Validating LLM responses...")

    transcript_eval = _validate_response("transcript_eval", transcript_raw)
    audio_eval = _validate_response("audio_eval", audio_raw)
    video_eval = (
        _validate_response("video_eval", video_raw)
        if video_raw is not None
        else None
    )

    logger.info(
        "[LLMOrchestrator] All responses validated. candidate=%d", candidate_id
    )

    return {
        "transcript_evaluation": transcript_eval,
        "audio_evaluation": audio_eval,
        "video_evaluation": video_eval,
    }
