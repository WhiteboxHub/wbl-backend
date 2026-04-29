"""
Reusable OpenAI Chat Completions client.

Call :func:`openai_chat_with_prompts` with system + user strings, or
:func:`openai_chat_completions` with a full ``messages`` list.

API key must be supplied by the caller (env resolution happens in routes / services).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"


@dataclass
class OpenAiLlmResult:
    """Result of a chat completion request."""

    content: Optional[str] = None
    """Assistant message text, or None on failure."""
    error: Optional[str] = None
    """Human-readable error when the call fails or response is unusable."""
    status_code: Optional[int] = None
    """HTTP status from OpenAI when available."""
    raw_body_preview: Optional[str] = None
    """Truncated response body on non-200 for debugging (not logged by default)."""


def openai_chat_completions(
    *,
    messages: List[Dict[str, str]],
    api_key: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    max_tokens: int = 2000,
    timeout: float = 90.0,
) -> OpenAiLlmResult:
    """
    Low-level: POST to OpenAI Chat Completions with arbitrary ``messages``.

    Each message must include ``role`` (system | user | assistant) and ``content``.
    """
    key = (api_key or "").strip()
    if not key:
        return OpenAiLlmResult(error="OpenAI API key is required")

    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(OPENAI_CHAT_URL, headers=headers, json=payload)
    except httpx.RequestError as e:
        logger.warning("OpenAI request failed: %s", e)
        return OpenAiLlmResult(error=f"Network error calling OpenAI: {e!s}")

    preview = (resp.text or "")[:2000]
    if resp.status_code != 200:
        detail = preview
        try:
            err_json = resp.json()
            detail = err_json.get("error", {}).get("message") or detail
        except Exception:
            pass
        return OpenAiLlmResult(
            error=f"OpenAI error ({resp.status_code}): {detail}",
            status_code=resp.status_code,
            raw_body_preview=preview,
        )

    try:
        data = resp.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content")
        )
        if content is None:
            return OpenAiLlmResult(
                error="OpenAI response missing message content",
                status_code=resp.status_code,
                raw_body_preview=preview,
            )
        return OpenAiLlmResult(content=str(content).strip() or None, status_code=resp.status_code)
    except Exception as e:
        return OpenAiLlmResult(
            error=f"Invalid OpenAI response: {e!s}",
            status_code=getattr(resp, "status_code", None),
            raw_body_preview=preview,
        )


def openai_chat_with_prompts(
    *,
    user_prompt: str,
    system_prompt: Optional[str] = None,
    api_key: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    max_tokens: int = 2000,
    timeout: float = 90.0,
) -> OpenAiLlmResult:
    """
    High-level: single user turn, optional system prompt.

    Example::

        r = openai_chat_with_prompts(
            system_prompt="You are a helpful assistant.",
            user_prompt="Summarize: ...",
            api_key=key,
        )
        if r.error:
            ...
        text = r.content
    """
    messages: List[Dict[str, str]] = []
    if system_prompt is not None and str(system_prompt).strip():
        messages.append({"role": "system", "content": str(system_prompt).strip()})
    messages.append({"role": "user", "content": (user_prompt or "").strip()})

    return openai_chat_completions(
        messages=messages,
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )
