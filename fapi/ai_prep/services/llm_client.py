"""Provider-aware LLM client for the AIPrep coaching report generator.

Calls OpenAI or Anthropic based on the candidate's stored provider_name.
Returns the raw JSON string content of the model's response.

Rules enforced here:
- No FastAPI routes.
- No DB writes.
- No report schema logic.
- Never logs the API key (decrypted or otherwise).
- NoCandidateLLMKeyError / UnsupportedProviderError propagate as-is.
- SDK auth errors are re-raised as CandidateLLMKeyError.
- Transient errors (429, 500, timeouts) rely on SDK max_retries=3.

"""
from __future__ import annotations

import logging
from typing import Optional


from openai import AuthenticationError as OpenAIAuthenticationError
from openai import OpenAI
from openai import PermissionDeniedError as OpenAIPermissionDeniedError
from sqlalchemy.orm import Session

from fapi.ai_prep.exceptions import (
    CandidateLLMKeyError,
    NoCandidateLLMKeyError,
    UnsupportedProviderError,
)
from fapi.ai_prep.services.candidate_llm_key_service import (
    CandidateLLMKey,
    get_candidate_llm_key,
)

logger = logging.getLogger("aiprep.llm")

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_MODEL_OPENAI = "gpt-4o"
# Matches the default used in the existing codebase for Anthropic
# (see coderpad_openai_key.py _DEFAULT_MODEL_BY_PROVIDER and
#  llm_provider_registry.py AnthropicProvider.fallback_models[0]).
_DEFAULT_MODEL_ANTHROPIC = "claude-3-7-sonnet-20250219"

_PROVIDER_CONFIGS: dict[str, dict[str, Optional[str]]] = {
    "openai": {
        "base_url": None,
        "default_model": "gpt-4o",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.0-flash",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "default_model": "mistral-large-latest",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o",
    },
    "xai": {
        "base_url": "https://api.x.ai/v1",
        "default_model": "grok-2-latest",
    },
}

_JSON_SYSTEM_ADDENDUM = (
    "\n\nRespond with ONLY valid JSON, no markdown fences, no preamble text."
)


# ---------------------------------------------------------------------------
# Internal provider calls
# ---------------------------------------------------------------------------


def _call_openai_compatible(
    key: CandidateLLMKey,
    system_prompt: str,
    user_prompt: str,
    assessment_id: int,
    candidate_id: int,
    base_url: Optional[str] = None,
    default_model: str = _DEFAULT_MODEL_OPENAI,
) -> tuple[str, int, int, int]:
    """Returns (content, prompt_tokens, completion_tokens, total_tokens) for OpenAI-compatible APIs."""
    model = (key.model_name or "").strip() or default_model
    client = OpenAI(api_key=key.api_key, base_url=base_url, max_retries=3)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=4000,
        )
    except (OpenAIAuthenticationError, OpenAIPermissionDeniedError) as exc:
        raise CandidateLLMKeyError(
            candidate_id=candidate_id,
            provider_name=key.provider_name,
            original_message=str(exc),
        ) from exc

    usage = response.usage
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    total_tokens = usage.total_tokens if usage else 0
    content = response.choices[0].message.content or ""
    return content, prompt_tokens, completion_tokens, total_tokens


def _call_openai(
    key: CandidateLLMKey,
    system_prompt: str,
    user_prompt: str,
    assessment_id: int,
    candidate_id: int,
) -> tuple[str, int, int, int]:
    """Backward-compatible helper for OpenAI provider."""
    return _call_openai_compatible(
        key=key,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        assessment_id=assessment_id,
        candidate_id=candidate_id,
        base_url=None,
        default_model=_DEFAULT_MODEL_OPENAI,
    )


def _call_anthropic(
    key: CandidateLLMKey,
    system_prompt: str,
    user_prompt: str,
    assessment_id: int,
    candidate_id: int,
) -> tuple[str, int, int, int]:
    """Returns (content, prompt_tokens, completion_tokens, total_tokens).

    Requires ``anthropic`` package — see module docstring.
    """
    try:
        import anthropic as anthropic_sdk
    except ImportError as exc:
        raise ImportError(
            "The 'anthropic' package is not installed. "
            "Add 'anthropic>=0.26.0' to requirements.txt and reinstall."
        ) from exc

    # Claude does not support response_format=json_object, so we inject the
    # JSON instruction into the system prompt instead.
    augmented_system = system_prompt + _JSON_SYSTEM_ADDENDUM

    model = (key.model_name or "").strip() or _DEFAULT_MODEL_ANTHROPIC
    client = anthropic_sdk.Anthropic(api_key=key.api_key, max_retries=3)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            system=augmented_system,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic_sdk.AuthenticationError as exc:
        raise CandidateLLMKeyError(
            candidate_id=candidate_id,
            provider_name="anthropic",
            original_message=str(exc),
        ) from exc
    except anthropic_sdk.PermissionDeniedError as exc:
        raise CandidateLLMKeyError(
            candidate_id=candidate_id,
            provider_name="anthropic",
            original_message=str(exc),
        ) from exc

    usage = response.usage
    # Anthropic SDK field names: input_tokens, output_tokens
    prompt_tokens = getattr(usage, "input_tokens", 0) or 0
    completion_tokens = getattr(usage, "output_tokens", 0) or 0
    total_tokens = prompt_tokens + completion_tokens

    content = ""
    for block in response.content:
        if hasattr(block, "text"):
            content = block.text
            break
    return content, prompt_tokens, completion_tokens, total_tokens


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def call_llm(
    db: Session,
    system_prompt: str,
    user_prompt: str,
    assessment_id: int,
    candidate_id: int,
) -> str:
    """Call the candidate's configured LLM and return the raw JSON string response.

    Args:
        db:             SQLAlchemy session (read-only in this function).
        system_prompt:  Fully assembled system prompt (from prompt templates).
        user_prompt:    Fully assembled user prompt (from prompt templates).
        assessment_id:  Used only for structured logging; no DB writes here.
        candidate_id:   Used to look up the API key and for logging.

    Returns:
        Raw JSON string from the model.  Callers are responsible for parsing.

    Raises:
        NoCandidateLLMKeyError:   Candidate hasn't configured a key yet.
        UnsupportedProviderError: The stored provider is not supported.
        CandidateLLMKeyError:     The provider SDK rejected the key (auth error).
        ImportError:              ``anthropic`` package missing (Anthropic path).
    """
    key: CandidateLLMKey = get_candidate_llm_key(db, candidate_id)

    provider = key.provider_name  # already normalised to lowercase

    try:
        if provider == "anthropic":
            content, pt, ct, tt = _call_anthropic(
                key, system_prompt, user_prompt, assessment_id, candidate_id
            )
        elif provider in _PROVIDER_CONFIGS:
            config = _PROVIDER_CONFIGS[provider]
            content, pt, ct, tt = _call_openai_compatible(
                key=key,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                assessment_id=assessment_id,
                candidate_id=candidate_id,
                base_url=config["base_url"],
                default_model=config["default_model"] or _DEFAULT_MODEL_OPENAI,
            )
        else:
            raise UnsupportedProviderError(provider)
    except CandidateLLMKeyError as exc:
        logger.warning(
            "aiprep.llm: API key rejected by provider",
            extra={
                "assessment_id": assessment_id,
                "candidate_id": candidate_id,
                "provider_name": provider,
                "error": exc.original_message,
            },
        )
        raise

    logger.info(
        "aiprep.llm: LLM call succeeded",
        extra={
            "assessment_id": assessment_id,
            "candidate_id": candidate_id,
            "provider_name": provider,
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_tokens": tt,
        },
    )
    return content

