"""Validate stored LLM API keys against provider APIs (lightweight ping)."""
from __future__ import annotations

import logging
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

ValidationStatus = str  # active | inactive | invalid

_INVALID_KEY_PHRASES = (
    "invalid api key",
    "invalid key",
    "incorrect api key",
    "authentication",
    "unauthorized",
    "invalid authentication",
    "api key not valid",
)


def _message_indicates_invalid(message: str) -> bool:
    m = (message or "").lower()
    return any(p in m for p in _INVALID_KEY_PHRASES)


def finalize_validation(ok: bool, message: str) -> Tuple[ValidationStatus, str]:
    if ok:
        return "active", message or "Key is active"
    if _message_indicates_invalid(message):
        return "invalid", message or "Invalid API key"
    return "inactive", message or "Key inactive or unreachable"


def validate_openai_api_key(api_key: str) -> Tuple[ValidationStatus, str]:
    key = (api_key or "").strip()
    if not key:
        return "invalid", "No key stored"
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
        if r.status_code == 200:
            return finalize_validation(True, "Key is active")
        detail = r.text[:500]
        try:
            detail = r.json().get("error", {}).get("message") or detail
        except Exception:
            pass
        return finalize_validation(False, str(detail))
    except httpx.RequestError as e:
        logger.warning("OpenAI key validation network error: %s", e)
        return finalize_validation(False, f"Could not reach OpenAI: {e!s}")


def validate_claude_api_key(api_key: str) -> Tuple[ValidationStatus, str]:
    key = (api_key or "").strip()
    if not key:
        return "invalid", "No key stored"
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                },
            )
        if r.status_code == 200:
            return finalize_validation(True, "Key is active")
        detail = r.text[:500]
        try:
            detail = r.json().get("error", {}).get("message") or detail
        except Exception:
            pass
        return finalize_validation(False, str(detail))
    except httpx.RequestError as e:
        return finalize_validation(False, f"Could not reach Claude: {e!s}")


def validate_gemini_api_key(api_key: str) -> Tuple[ValidationStatus, str]:
    key = (api_key or "").strip()
    if not key:
        return "invalid", "No key stored"
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
            )
        if r.status_code == 200:
            return finalize_validation(True, "Key is active")
        detail = r.text[:500]
        try:
            detail = r.json().get("error", {}).get("message") or detail
        except Exception:
            pass
        return finalize_validation(False, str(detail))
    except httpx.RequestError as e:
        return finalize_validation(False, f"Could not reach Gemini: {e!s}")


def validate_mistral_api_key(api_key: str) -> Tuple[ValidationStatus, str]:
    key = (api_key or "").strip()
    if not key:
        return "invalid", "No key stored"
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get(
                "https://api.mistral.ai/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
        if r.status_code == 200:
            return finalize_validation(True, "Key is active")
        detail = r.text[:500]
        try:
            detail = r.json().get("message") or detail
        except Exception:
            pass
        return finalize_validation(False, str(detail))
    except httpx.RequestError as e:
        return finalize_validation(False, f"Could not reach Mistral: {e!s}")


def validate_provider_key(provider_name: str, api_key: str) -> Tuple[ValidationStatus, str]:
    p = (provider_name or "").strip().lower()
    if p in ("openai", "gpt"):
        return validate_openai_api_key(api_key)
    if p in ("claude", "anthropic"):
        return validate_claude_api_key(api_key)
    if p in ("gemini", "google"):
        return validate_gemini_api_key(api_key)
    if p in ("mistral",):
        return validate_mistral_api_key(api_key)
    return "inactive", f"Validation not supported for provider: {provider_name}"


