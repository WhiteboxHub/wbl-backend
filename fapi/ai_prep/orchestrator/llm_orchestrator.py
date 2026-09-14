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
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from fapi.ai_prep import crud
from fapi.ai_prep.clients.llm_client import call_llm
from fapi.ai_prep.core.llm_evaluation import EvalEngine
from fapi.ai_prep.core.scores_engine import ScoresEngine

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


def _prepare_prompts(
    eval_engine: Any,
    assessment_type: str,
    transcript_text: str,
    resume_json: Optional[Any],
    audio_telemetry: Dict[str, Any],
    video_telemetry: Dict[str, Any],
    is_video_mode: bool,
    can_eval_audio: bool,
) -> Tuple[Dict[str, str], Optional[Dict[str, str]], Optional[Dict[str, str]]]:
    """Prepares and compiles prompts for transcript, audio, and video evaluation."""
    transcript_prompt = eval_engine.build_prompt(
        assessment_type=assessment_type,
        transcript_text=transcript_text,
        resume_json=resume_json,
    )
    audio_prompt = eval_engine.build_audio_prompt(audio_telemetry) if can_eval_audio else None
    video_prompt = eval_engine.build_video_prompt(video_telemetry) if is_video_mode else None
    return transcript_prompt, audio_prompt, video_prompt


def _assemble_evaluation_results(
    results_map: Dict[str, Any],
    can_eval_audio: bool,
    audio_telemetry: Dict[str, Any],
    is_video_mode: bool,
    eval_engine: Any,
) -> Dict[str, Any]:
    """Validates raw LLM responses and falls back cleanly for partial telemetry failures."""
    # 1. Transcript evaluation (primary required component)
    transcript_res = results_map.get("transcript_eval")
    if isinstance(transcript_res, Exception):
        raise transcript_res
    transcript_eval = _validate_response("transcript_eval", transcript_res)

    # 2. Audio evaluation (graceful fallback if LLM call or validation failed)
    audio_res = results_map.get("audio_eval")
    audio_eval = None
    if can_eval_audio and audio_res and not isinstance(audio_res, Exception):
        try:
            audio_eval = _validate_response("audio_eval", audio_res)
        except Exception as err:
            logger.warning("[LLMOrchestrator] Audio eval validation failed: %s. Using fallback.", err)

    if audio_eval is None:
        duration = 0.0
        if audio_telemetry and isinstance(audio_telemetry, dict):
            raw_dur = (
                audio_telemetry.get("speaking_duration_seconds")
                or audio_telemetry.get("duration")
                or 0.0
            )
            try:
                duration = float(raw_dur)
            except (ValueError, TypeError):
                duration = 0.0
        audio_eval = eval_engine.build_insufficient_audio_evaluation(speaking_duration=duration)

    # 3. Video evaluation (optional component)
    video_eval = None
    if is_video_mode and "video_eval" in results_map:
        video_res = results_map.get("video_eval")
        if video_res and not isinstance(video_res, Exception):
            try:
                video_eval = _validate_response("video_eval", video_res)
            except Exception as err:
                logger.warning("[LLMOrchestrator] Video eval validation failed: %s. Setting to None.", err)

    return {
        "transcript_evaluation": transcript_eval,
        "audio_evaluation": audio_eval,
        "video_evaluation": video_eval,
    }


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
) -> Dict[str, Any]:
    """
    Core async orchestration: compile prompts → concurrent LLM calls → validate → return.

    Note: llm_config must be pre-fetched by the caller via get_candidate_llm_config()
    before invoking this function. This function performs no DB access.
    """
    eval_engine = EvalEngine()

    api_key: str = llm_config["api_key"]
    provider: Optional[str] = llm_config.get("provider")
    model: Optional[str] = llm_config.get("model")
    is_video_mode: bool = bool(video_telemetry.get("is_video_mode", False))

    logger.info(
        "[LLMOrchestrator] Building prompts: candidate=%d type=%s video_mode=%s",
        candidate_id, assessment_type, is_video_mode,
    )

    can_eval_audio: bool = eval_engine.has_evaluable_audio(audio_telemetry)
    transcript_prompt, audio_prompt, video_prompt = _prepare_prompts(
        eval_engine, assessment_type, transcript_text, resume_json,
        audio_telemetry, video_telemetry, is_video_mode, can_eval_audio,
    )

    call_labels: List[str] = ["transcript_eval"]
    coroutines = [
        _invoke_llm(
            call_label="transcript_eval",
            system_prompt=transcript_prompt["system_prompt"],
            user_prompt=transcript_prompt["user_prompt"],
            api_key=api_key,
            provider=provider,
            model=model,
        )
    ]

    if can_eval_audio and audio_prompt:
        call_labels.append("audio_eval")
        coroutines.append(
            _invoke_llm(
                call_label="audio_eval",
                system_prompt=audio_prompt["system_prompt"],
                user_prompt=audio_prompt["user_prompt"],
                api_key=api_key,
                provider=provider,
                model=model,
            )
        )
    else:
        logger.info(
            "[LLMOrchestrator] Candidate=%d: No audio speech recorded or duration <= 0s. Skipping audio call.",
            candidate_id,
        )

    if is_video_mode and video_prompt:
        call_labels.append("video_eval")
        coroutines.append(
            _invoke_llm(
                call_label="video_eval",
                system_prompt=video_prompt["system_prompt"],
                user_prompt=video_prompt["user_prompt"],
                api_key=api_key,
                provider=provider,
                model=model,
            )
        )

    logger.info("[LLMOrchestrator] Dispatching %d concurrent LLM call(s): %s", len(coroutines), call_labels)
    raw_results = await asyncio.gather(*coroutines, return_exceptions=True)
    results_map: Dict[str, Any] = dict(zip(call_labels, raw_results))

    logger.info("[LLMOrchestrator] Validating LLM responses for candidate=%d...", candidate_id)
    return _assemble_evaluation_results(
        results_map=results_map,
        can_eval_audio=can_eval_audio,
        audio_telemetry=audio_telemetry,
        is_video_mode=is_video_mode,
        eval_engine=eval_engine,
    )
