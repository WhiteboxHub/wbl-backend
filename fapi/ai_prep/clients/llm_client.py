"""
Universal Asynchronous Multi-Provider LLM Client for AI Prep Platform.
Supports OpenAI, Google Gemini, Anthropic Claude, Groq, DeepSeek, OpenRouter,
Mistral AI, xAI (Grok), Together AI, and Perplexity.
Features automatic key-prefix provider detection and zero database dependencies.
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================


class LLMClientError(Exception):
    """Base exception for all LLM client failures."""

    def __init__(self, message: str, provider: str = "", status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class LLMAuthenticationError(LLMClientError):
    """Raised on HTTP 401 / 403 authentication or invalid API key errors."""
    pass


class LLMRateLimitError(LLMClientError):
    """Raised on HTTP 429 rate limit or quota exceeded errors."""
    pass


class LLMTimeoutError(LLMClientError):
    """Raised when the LLM API request times out."""
    pass


class LLMResponseFormatError(LLMClientError):
    """Raised when the LLM response is empty or cannot be parsed."""
    pass


# =============================================================================
# PROVIDER CONFIGURATION & DEFAULTS
# =============================================================================

# Default models for each supported provider
DEFAULT_MODELS: Dict[str, str] = {
    "openai": "gpt-4o",
    "gemini": "gemini-2.0-flash",
    "anthropic": "claude-3-5-sonnet-latest",
    "groq": "llama-3.3-70b-versatile",
    "deepseek": "deepseek-chat",
    "openrouter": "openai/gpt-4o",
    "mistral": "mistral-large-latest",
    "xai": "grok-2",
    "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "perplexity": "sonar-pro",
}

# Endpoints for OpenAI-compatible chat completion APIs
OPENAI_COMPATIBLE_ENDPOINTS: Dict[str, str] = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "deepseek": "https://api.deepseek.com/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "mistral": "https://api.mistral.ai/v1/chat/completions",
    "xai": "https://api.x.ai/v1/chat/completions",
    "together": "https://api.together.xyz/v1/chat/completions",
    "perplexity": "https://api.perplexity.ai/chat/completions",
}

GEMINI_BASE_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
ANTHROPIC_MESSAGES_ENDPOINT = "https://api.anthropic.com/v1/messages"


# =============================================================================
# AUTO-DETECTION HELPER
# =============================================================================


def detect_provider_from_key(api_key: str) -> str:
    """
    Infers the LLM provider automatically from known API key prefixes.
    Fallback default is 'openai'.
    """
    key = (api_key or "").strip()
    if not key:
        return "openai"

    if key.startswith("sk-ant-"):
        return "anthropic"
    if key.startswith(("AIzaSy", "AIza", "AQ.", "AQ")):
        return "gemini"
    if key.startswith("gsk_"):
        return "groq"
    if key.startswith(("sk-or-v1-", "sk-or-")):
        return "openrouter"
    if key.startswith("sk-ds-"):
        return "deepseek"
    if key.startswith("msk-"):
        return "mistral"
    if key.startswith("xai-"):
        return "xai"
    if key.startswith("pplx-"):
        return "perplexity"
    if key.startswith("sk-"):
        return "openai"

    return "openai"


# =============================================================================
# MAIN CLIENT API
# =============================================================================


async def call_llm(
    *,
    api_key: str,
    provider: Optional[str] = None,
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    response_format: str = "json_object",
    temperature: float = 0.2,
    max_tokens: int = 4000,
    timeout_seconds: float = 60.0,
) -> str:
    """
    Executes an async LLM completion request and returns the raw response string.

    Args:
        api_key: The candidate or system API key.
        provider: Optional provider name (auto-detected if omitted or set to 'auto').
                  Supported: openai, gemini, anthropic, groq, deepseek, openrouter,
                  mistral, xai, together, perplexity.
        system_prompt: System persona and evaluation instructions.
        user_prompt: Injected user prompt content.
        model: Optional provider model name (defaults to standard production model).
        response_format: Output format constraint (defaults to 'json_object').
        temperature: Sampling temperature (default 0.2 for deterministic evaluation).
        max_tokens: Maximum token completion length.
        timeout_seconds: Network request timeout in seconds.

    Returns:
        Raw unverified LLM text response (typically a JSON string).
    """
    clean_key = (api_key or "").strip()
    if not clean_key:
        raise LLMAuthenticationError("API key cannot be empty", provider=provider or "unknown")

    # Resolve provider
    raw_provider = (provider or "").strip().lower()
    if not raw_provider or raw_provider in ("auto", "detect"):
        resolved_provider = detect_provider_from_key(clean_key)
    else:
        # Normalize common aliases
        alias_map = {
            "gpt": "openai",
            "google": "gemini",
            "claude": "anthropic",
            "grok": "xai",
        }
        resolved_provider = alias_map.get(raw_provider, raw_provider)

    selected_model = model or DEFAULT_MODELS.get(resolved_provider, "")

    # 1. Google Gemini
    if resolved_provider == "gemini":
        return await _call_gemini(
            api_key=clean_key,
            model=selected_model or DEFAULT_MODELS["gemini"],
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
        )

    # 2. Anthropic Claude
    if resolved_provider == "anthropic":
        return await _call_anthropic(
            api_key=clean_key,
            model=selected_model or DEFAULT_MODELS["anthropic"],
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
        )

    # 3. OpenAI-Compatible Providers (OpenAI, Groq, DeepSeek, OpenRouter, Mistral, xAI, Together, Perplexity)
    if resolved_provider in OPENAI_COMPATIBLE_ENDPOINTS:
        endpoint = OPENAI_COMPATIBLE_ENDPOINTS[resolved_provider]
        return await _call_openai_compatible(
            api_key=clean_key,
            endpoint=endpoint,
            provider=resolved_provider,
            model=selected_model or DEFAULT_MODELS[resolved_provider],
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
        )

    raise LLMClientError(
        f"Unsupported provider '{provider}'. Supported: {sorted(list(DEFAULT_MODELS.keys()))}",
        provider=resolved_provider,
    )


# =============================================================================
# OPENAI-COMPATIBLE ADAPTER (Groq, DeepSeek, OpenRouter, Mistral, xAI, etc.)
# =============================================================================


async def _call_openai_compatible(
    *,
    api_key: str,
    endpoint: str,
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    response_format: str,
    temperature: float,
    max_tokens: int,
    timeout_seconds: float,
) -> str:
    """Dispatches request to any OpenAI-compatible Chat Completions endpoint."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    # Only attach response_format for providers that support the json_object type flag
    if response_format == "json_object" and provider not in ("perplexity",):
        payload["response_format"] = {"type": "json_object"}

    headers: Dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "AIPrep-Backend/2.0",
    }

    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://wbl.com"
        headers["X-Title"] = "AIPrep Evaluation Engine"

    response_json, _ = await _execute_http_post(
        url=endpoint,
        headers=headers,
        payload=payload,
        timeout_seconds=timeout_seconds,
        provider=provider,
    )

    try:
        choices = response_json.get("choices")
        if not choices or not isinstance(choices, list):
            raise LLMResponseFormatError(f"{provider} response missing 'choices' array", provider=provider)
        content = choices[0].get("message", {}).get("content", "")
        if not content:
            raise LLMResponseFormatError(f"{provider} response message content is empty", provider=provider)
        return content
    except (KeyError, IndexError) as err:
        raise LLMResponseFormatError(
            f"Failed to extract message content from {provider} response: {err}",
            provider=provider,
        ) from err


# =============================================================================
# GOOGLE GEMINI ADAPTER
# =============================================================================


async def _call_gemini(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    response_format: str,
    temperature: float,
    max_tokens: int,
    timeout_seconds: float,
) -> str:
    """Dispatches completion request to Google Gemini API."""
    url = f"{GEMINI_BASE_ENDPOINT.format(model=model)}?key={api_key}"

    generation_config: Dict[str, Any] = {
        "temperature": temperature,
        "maxOutputTokens": max_tokens,
    }
    if response_format == "json_object":
        generation_config["responseMimeType"] = "application/json"

    payload: Dict[str, Any] = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}],
            }
        ],
        "systemInstruction": {
            "parts": [{"text": system_prompt}],
        },
        "generationConfig": generation_config,
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "AIPrep-Backend/2.0",
    }

    response_json, _ = await _execute_http_post(
        url=url,
        headers=headers,
        payload=payload,
        timeout_seconds=timeout_seconds,
        provider="gemini",
    )

    try:
        candidates = response_json.get("candidates")
        if not candidates or not isinstance(candidates, list):
            raise LLMResponseFormatError("Gemini response missing 'candidates' array", provider="gemini")
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts or not isinstance(parts, list):
            raise LLMResponseFormatError("Gemini candidate missing 'parts' list", provider="gemini")
        text = parts[0].get("text", "")
        if not text:
            raise LLMResponseFormatError("Gemini text part is empty", provider="gemini")
        return text
    except (KeyError, IndexError) as err:
        raise LLMResponseFormatError(
            f"Failed to extract text from Gemini response: {err}",
            provider="gemini",
        ) from err


# =============================================================================
# ANTHROPIC CLAUDE ADAPTER
# =============================================================================


async def _call_anthropic(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    response_format: str,
    temperature: float,
    max_tokens: int,
    timeout_seconds: float,
) -> str:
    """Dispatches completion request to Anthropic Messages API."""
    enhanced_system = system_prompt
    if response_format == "json_object" and "json" not in system_prompt.lower():
        enhanced_system += "\n\nCRITICAL: Return your response strictly as valid JSON without any markdown formatting or commentary."

    payload: Dict[str, Any] = {
        "model": model,
        "system": enhanced_system,
        "messages": [{"role": "user", "content": user_prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
        "User-Agent": "AIPrep-Backend/2.0",
    }

    response_json, _ = await _execute_http_post(
        url=ANTHROPIC_MESSAGES_ENDPOINT,
        headers=headers,
        payload=payload,
        timeout_seconds=timeout_seconds,
        provider="anthropic",
    )

    try:
        content_parts = response_json.get("content", [])
        if not content_parts or not isinstance(content_parts, list):
            raise LLMResponseFormatError("Anthropic response missing 'content' array", provider="anthropic")
        text = content_parts[0].get("text", "")
        if not text:
            raise LLMResponseFormatError("Anthropic response text is empty", provider="anthropic")
        return text
    except (KeyError, IndexError) as err:
        raise LLMResponseFormatError(
            f"Failed to extract text from Anthropic response: {err}",
            provider="anthropic",
        ) from err


# =============================================================================
# CONNECTION & TOKEN QUOTA DIAGNOSTIC PROBE
# =============================================================================


async def test_llm_connection(
    api_key: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    timeout_seconds: float = 30.0,
) -> Dict[str, Any]:
    """
    Tests live connection to the LLM provider and extracts detailed token usage,
    leftover rate-limit token quotas, remaining request allocations, and account credits.

    Returns:
        Dict containing:
        - success: bool
        - provider: str
        - model: str
        - response_snippet: str
        - tokens_used: {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
        - tokens_remaining: Optional[int] (from HTTP rate limit headers)
        - tokens_limit: Optional[int]
        - requests_remaining: Optional[int]
        - rate_limit_reset: Optional[str]
        - account_credits: Optional[Dict[str, Any]] (for OpenRouter)
    """
    clean_key = (api_key or "").strip()
    if not clean_key:
        raise LLMAuthenticationError("API key cannot be empty")

    raw_provider = (provider or "").strip().lower()
    if not raw_provider or raw_provider in ("auto", "detect"):
        resolved_provider = detect_provider_from_key(clean_key)
    else:
        alias_map = {"gpt": "openai", "google": "gemini", "claude": "anthropic", "grok": "xai"}
        resolved_provider = alias_map.get(raw_provider, raw_provider)

    selected_model = model or DEFAULT_MODELS.get(resolved_provider, "")

    test_system = "You are a test assistant. Return ONLY a valid JSON object: {\"status\": \"ok\", \"connection\": \"verified\"}"
    test_user = "Ping test"

    response_json: Dict[str, Any] = {}
    headers_dict: Dict[str, str] = {}
    response_text = ""

    if resolved_provider == "gemini":
        url = f"{GEMINI_BASE_ENDPOINT.format(model=selected_model)}?key={clean_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": test_user}]}],
            "systemInstruction": {"parts": [{"text": test_system}]},
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 100, "responseMimeType": "application/json"},
        }
        response_json, headers_dict = await _execute_http_post(
            url=url, headers={"Content-Type": "application/json"}, payload=payload, timeout_seconds=timeout_seconds, provider="gemini"
        )
        candidates = response_json.get("candidates", [])
        if candidates:
            response_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")

    elif resolved_provider == "anthropic":
        payload = {
            "model": selected_model,
            "system": test_system,
            "messages": [{"role": "user", "content": test_user}],
            "max_tokens": 100,
            "temperature": 0.1,
        }
        response_json, headers_dict = await _execute_http_post(
            url=ANTHROPIC_MESSAGES_ENDPOINT,
            headers={"x-api-key": clean_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            payload=payload,
            timeout_seconds=timeout_seconds,
            provider="anthropic",
        )
        content_parts = response_json.get("content", [])
        if content_parts:
            response_text = content_parts[0].get("text", "")

    elif resolved_provider in OPENAI_COMPATIBLE_ENDPOINTS:
        endpoint = OPENAI_COMPATIBLE_ENDPOINTS[resolved_provider]
        payload = {
            "model": selected_model,
            "messages": [{"role": "system", "content": test_system}, {"role": "user", "content": test_user}],
            "temperature": 0.1,
            "max_tokens": 100,
        }
        if resolved_provider not in ("perplexity",):
            payload["response_format"] = {"type": "json_object"}

        hdrs = {"Authorization": f"Bearer {clean_key}", "Content-Type": "application/json"}
        if resolved_provider == "openrouter":
            hdrs["HTTP-Referer"] = "https://wbl.com"
            hdrs["X-Title"] = "AIPrep Evaluation"

        response_json, headers_dict = await _execute_http_post(
            url=endpoint, headers=hdrs, payload=payload, timeout_seconds=timeout_seconds, provider=resolved_provider
        )
        choices = response_json.get("choices", [])
        if choices:
            response_text = choices[0].get("message", {}).get("content", "")

    else:
        raise LLMClientError(f"Unsupported provider '{resolved_provider}'", provider=resolved_provider)

    # 1. Extract Token Usage from Body
    tokens_used = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    if "usage" in response_json:
        u = response_json["usage"]
        p = u.get("prompt_tokens") or u.get("input_tokens") or 0
        c = u.get("completion_tokens") or u.get("output_tokens") or 0
        t = u.get("total_tokens") or (p + c)
        tokens_used = {"prompt_tokens": int(p), "completion_tokens": int(c), "total_tokens": int(t)}
    elif "usageMetadata" in response_json:
        u = response_json["usageMetadata"]
        p = u.get("promptTokenCount", 0)
        c = u.get("candidatesTokenCount", 0)
        t = u.get("totalTokenCount", p + c)
        tokens_used = {"prompt_tokens": int(p), "completion_tokens": int(c), "total_tokens": int(t)}

    # 2. Extract Remaining Token Limits from HTTP Response Headers
    def _int_or_none(v: Optional[str]) -> Optional[int]:
        if v is None:
            return None
        try:
            return int(v.replace(",", "").strip())
        except ValueError:
            return None

    tokens_remaining = _int_or_none(
        headers_dict.get("x-ratelimit-remaining-tokens")
        or headers_dict.get("anthropic-ratelimit-tokens-remaining")
    )
    tokens_limit = _int_or_none(
        headers_dict.get("x-ratelimit-limit-tokens")
        or headers_dict.get("anthropic-ratelimit-tokens-limit")
    )
    requests_remaining = _int_or_none(
        headers_dict.get("x-ratelimit-remaining-requests")
        or headers_dict.get("anthropic-ratelimit-requests-remaining")
    )
    rate_limit_reset = (
        headers_dict.get("x-ratelimit-reset-tokens")
        or headers_dict.get("anthropic-ratelimit-tokens-reset")
        or headers_dict.get("x-ratelimit-reset-requests")
    )

    # 3. Special account check for OpenRouter (fetches dollar balance)
    account_credits: Optional[Dict[str, Any]] = None
    if resolved_provider == "openrouter":
        try:
            def _check_openrouter_auth():
                req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/auth/key",
                    headers={"Authorization": f"Bearer {clean_key}"},
                )
                with urllib.request.urlopen(req, timeout=10.0) as r:
                    return json.loads(r.read().decode("utf-8"))
            auth_data = await asyncio.to_thread(_check_openrouter_auth)
            data_field = auth_data.get("data", {})
            limit = data_field.get("limit")
            usage = data_field.get("usage", 0.0)
            account_credits = {
                "credit_limit_usd": limit,
                "usage_usd": round(float(usage), 4),
                "credits_remaining_usd": round(float(limit - usage), 4) if limit is not None else "Unlimited",
                "is_free_tier": data_field.get("is_free_tier", False),
            }
        except Exception as e:
            logger.debug(f"Could not fetch OpenRouter balance: {e}")

    return {
        "success": True,
        "provider": resolved_provider,
        "model": selected_model,
        "response_text": response_text.strip(),
        "tokens_used_this_call": tokens_used,
        "tokens_remaining": tokens_remaining,
        "tokens_limit": tokens_limit,
        "requests_remaining": requests_remaining,
        "rate_limit_reset": rate_limit_reset,
        "account_credits": account_credits,
    }


# =============================================================================
# SYNCHRONOUS NETWORK PRIMITIVE (EXECUTED ON ASYNCIO WORKER THREAD)
# =============================================================================


async def _execute_http_post(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout_seconds: float,
    provider: str,
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Executes an HTTP POST request asynchronously without blocking the event loop.
    Returns a tuple of (parsed_response_json, lowercase_headers_dict).
    Uses standard library urllib wrapped in asyncio.to_thread for maximum portability.
    """
    def _sync_request() -> Tuple[Dict[str, Any], Dict[str, str]]:
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                raw_body = resp.read().decode("utf-8")
                resp_headers = {k.lower(): str(v) for k, v in resp.headers.items()}
                return json.loads(raw_body), resp_headers
        except urllib.error.HTTPError as http_err:
            status = http_err.code
            try:
                error_body = http_err.read().decode("utf-8")
            except Exception:
                error_body = str(http_err)

            if status in (401, 403):
                raise LLMAuthenticationError(
                    f"Authentication failed ({status}) for {provider}: {error_body}",
                    provider=provider,
                    status_code=status,
                ) from http_err
            elif status == 429:
                raise LLMRateLimitError(
                    f"Rate limit exceeded ({status}) for {provider}: {error_body}",
                    provider=provider,
                    status_code=status,
                ) from http_err
            else:
                raise LLMClientError(
                    f"HTTP error {status} from {provider}: {error_body}",
                    provider=provider,
                    status_code=status,
                ) from http_err
        except urllib.error.URLError as url_err:
            reason = str(url_err.reason)
            if "timed out" in reason.lower():
                raise LLMTimeoutError(
                    f"Request timed out after {timeout_seconds}s connecting to {provider}: {reason}",
                    provider=provider,
                ) from url_err
            raise LLMClientError(
                f"Network connection failed for {provider}: {reason}",
                provider=provider,
            ) from url_err
        except TimeoutError as to_err:
            raise LLMTimeoutError(
                f"Request timed out after {timeout_seconds}s connecting to {provider}",
                provider=provider,
            ) from to_err
        except json.JSONDecodeError as json_err:
            raise LLMResponseFormatError(
                f"Failed to decode provider JSON response from {provider}: {json_err}",
                provider=provider,
            ) from json_err

    return await asyncio.to_thread(_sync_request)
