"""LLM Provider Registry & Automated Key Detection / Model Discovery Service.

Provides an extensible, modular interface for LLM providers.
Supports auto-detection by API key pattern, live endpoint validation,
dynamic model fetching via provider APIs (GET /v1/models), and default model selection.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

ValidationStatus = str  # "active" | "inactive" | "invalid"

_INVALID_KEY_PHRASES = (
    "invalid api key",
    "invalid key",
    "incorrect api key",
    "authentication",
    "unauthorized",
    "invalid authentication",
    "api key not valid",
    "invalid_api_key",
    "unauthenticated",
)


def _is_invalid_phrase(message: str) -> bool:
    m = (message or "").lower()
    return any(p in m for p in _INVALID_KEY_PHRASES)


class BaseLLMProvider:
    """Base interface for all LLM providers."""

    provider_id: str
    display_name: str
    key_prefixes: List[str]
    key_pattern: Optional[re.Pattern] = None

    def matches_key(self, api_key: str) -> bool:
        k = (api_key or "").strip()
        if not k:
            return False
        for prefix in self.key_prefixes:
            if k.startswith(prefix):
                return True
        if self.key_pattern and self.key_pattern.search(k):
            return True
        return False

    def validate_and_fetch_models(self, api_key: str) -> Tuple[ValidationStatus, str, List[str], Optional[str]]:
        raise NotImplementedError


class OpenAIProvider(BaseLLMProvider):
    provider_id = "OpenAI"
    display_name = "OpenAI"
    key_prefixes = ["sk-proj-", "sk-admin-", "sk-svcacct-"]
    key_pattern = re.compile(r"^sk-[a-zA-Z0-9_-]{30,}$")

    def matches_key(self, api_key: str) -> bool:
        k = (api_key or "").strip()
        if k.startswith("sk-ant-") or k.startswith("sk-or-") or k.startswith("gsk_") or k.startswith("xai-") or k.startswith("pplx-"):
            return False
        return super().matches_key(api_key)

    def validate_and_fetch_models(self, api_key: str) -> Tuple[ValidationStatus, str, List[str], Optional[str]]:
        key = api_key.strip()
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key}"})
            if r.status_code == 200:
                data = r.json().get("data", [])
                raw_ids = [m.get("id") for m in data if isinstance(m, dict) and m.get("id")]
                # Filter for chat completion models
                filtered = [
                    m for m in raw_ids
                    if (m.startswith("gpt-") or m.startswith("o1") or m.startswith("o3") or m.startswith("chatgpt-"))
                    and not any(x in m for x in ("realtime", "audio", "transcribe", "tts", "whisper", "instruct", "search"))
                ]
                filtered.sort(reverse=True)
                models = filtered if filtered else ["gpt-4o", "gpt-4o-mini", "o3-mini", "o1-mini"]
                default_model = "gpt-4o" if "gpt-4o" in models else models[0]
                return "active", "Key is active", models, default_model

            detail = r.text[:500]
            try:
                detail = r.json().get("error", {}).get("message") or detail
            except Exception:
                pass
            status = "invalid" if _is_invalid_phrase(str(detail)) else "inactive"
            return status, str(detail), ["gpt-4o", "gpt-4o-mini"], "gpt-4o"
        except Exception as e:
            return "inactive", f"Could not reach OpenAI: {e!s}", ["gpt-4o", "gpt-4o-mini"], "gpt-4o"


class AnthropicProvider(BaseLLMProvider):
    provider_id = "Claude"
    display_name = "Anthropic (Claude)"
    key_prefixes = ["sk-ant-"]
    key_pattern = re.compile(r"^sk-ant-api03-[a-zA-Z0-9_-]{40,}$")

    def validate_and_fetch_models(self, api_key: str) -> Tuple[ValidationStatus, str, List[str], Optional[str]]:
        key = api_key.strip()
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                )
            fallback_models = [
                "claude-3-7-sonnet-20250219",
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
            ]
            if r.status_code == 200:
                data = r.json().get("data", [])
                raw_ids = [m.get("id") for m in data if isinstance(m, dict) and m.get("id")]
                models = raw_ids if raw_ids else fallback_models
                default_model = models[0] if models else "claude-3-5-sonnet-20241022"
                return "active", "Key is active", models, default_model

            detail = r.text[:500]
            try:
                detail = r.json().get("error", {}).get("message") or detail
            except Exception:
                pass
            status = "invalid" if _is_invalid_phrase(str(detail)) else "inactive"
            return status, str(detail), fallback_models, "claude-3-5-sonnet-20241022"
        except Exception as e:
            return "inactive", f"Could not reach Anthropic: {e!s}", ["claude-3-5-sonnet-20241022"], "claude-3-5-sonnet-20241022"


class GeminiProvider(BaseLLMProvider):
    provider_id = "Gemini"
    display_name = "Google Gemini"
    key_prefixes = ["AIzaSy", "AIza", "AQ.", "AQ"]

    def validate_and_fetch_models(self, api_key: str) -> Tuple[ValidationStatus, str, List[str], Optional[str]]:
        key = api_key.strip()
        fallback_models = ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}")
            if r.status_code == 200:
                data = r.json().get("models", [])
                raw_names = []
                for m in data:
                    name = m.get("name", "").replace("models/", "")
                    methods = m.get("supportedGenerationMethods", [])
                    if "generateContent" in methods and (name.startswith("gemini-") or name.startswith("gemma-")):
                        raw_names.append(name)
                models = raw_names if raw_names else fallback_models
                default_model = "gemini-2.0-flash" if "gemini-2.0-flash" in models else models[0]
                return "active", "Key is active", models, default_model

            detail = r.text[:500]
            try:
                detail = r.json().get("error", {}).get("message") or detail
            except Exception:
                pass
            status = "invalid" if _is_invalid_phrase(str(detail)) else "inactive"
            return status, str(detail), fallback_models, "gemini-2.0-flash"
        except Exception as e:
            return "inactive", f"Could not reach Gemini: {e!s}", fallback_models, "gemini-2.0-flash"


class GroqProvider(BaseLLMProvider):
    provider_id = "Groq"
    display_name = "Groq"
    key_prefixes = ["gsk_"]

    def validate_and_fetch_models(self, api_key: str) -> Tuple[ValidationStatus, str, List[str], Optional[str]]:
        key = api_key.strip()
        fallback_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "deepseek-r1-distill-llama-70b"]
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key}"})
            if r.status_code == 200:
                data = r.json().get("data", [])
                raw_ids = [m.get("id") for m in data if isinstance(m, dict) and m.get("id") and m.get("active", True)]
                models = raw_ids if raw_ids else fallback_models
                default_model = "llama-3.3-70b-versatile" if "llama-3.3-70b-versatile" in models else models[0]
                return "active", "Key is active", models, default_model

            detail = r.text[:500]
            try:
                detail = r.json().get("error", {}).get("message") or detail
            except Exception:
                pass
            status = "invalid" if _is_invalid_phrase(str(detail)) else "inactive"
            return status, str(detail), fallback_models, "llama-3.3-70b-versatile"
        except Exception as e:
            return "inactive", f"Could not reach Groq: {e!s}", fallback_models, "llama-3.3-70b-versatile"


class MistralProvider(BaseLLMProvider):
    provider_id = "Mistral"
    display_name = "Mistral AI"
    key_prefixes = ["msk-"]

    def validate_and_fetch_models(self, api_key: str) -> Tuple[ValidationStatus, str, List[str], Optional[str]]:
        key = api_key.strip()
        fallback_models = ["mistral-large-latest", "codestral-latest", "mistral-small-latest"]
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get("https://api.mistral.ai/v1/models", headers={"Authorization": f"Bearer {key}"})
            if r.status_code == 200:
                data = r.json().get("data", [])
                raw_ids = [m.get("id") for m in data if isinstance(m, dict) and m.get("id")]
                models = raw_ids if raw_ids else fallback_models
                default_model = "mistral-large-latest" if "mistral-large-latest" in models else models[0]
                return "active", "Key is active", models, default_model

            detail = r.text[:500]
            try:
                detail = r.json().get("message") or detail
            except Exception:
                pass
            status = "invalid" if _is_invalid_phrase(str(detail)) else "inactive"
            return status, str(detail), fallback_models, "mistral-large-latest"
        except Exception as e:
            return "inactive", f"Could not reach Mistral: {e!s}", fallback_models, "mistral-large-latest"


class DeepSeekProvider(BaseLLMProvider):
    provider_id = "DeepSeek"
    display_name = "DeepSeek"
    key_prefixes = ["sk-ds-"]

    def validate_and_fetch_models(self, api_key: str) -> Tuple[ValidationStatus, str, List[str], Optional[str]]:
        key = api_key.strip()
        fallback_models = ["deepseek-chat", "deepseek-reasoner"]
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get("https://api.deepseek.com/v1/models", headers={"Authorization": f"Bearer {key}"})
            if r.status_code == 200:
                data = r.json().get("data", [])
                raw_ids = [m.get("id") for m in data if isinstance(m, dict) and m.get("id")]
                models = raw_ids if raw_ids else fallback_models
                return "active", "Key is active", models, "deepseek-chat"

            detail = r.text[:500]
            status = "invalid" if _is_invalid_phrase(str(detail)) else "inactive"
            return status, str(detail), fallback_models, "deepseek-chat"
        except Exception as e:
            return "inactive", f"Could not reach DeepSeek: {e!s}", fallback_models, "deepseek-chat"


class OpenRouterProvider(BaseLLMProvider):
    provider_id = "OpenRouter"
    display_name = "OpenRouter"
    key_prefixes = ["sk-or-v1-", "sk-or-"]

    def validate_and_fetch_models(self, api_key: str) -> Tuple[ValidationStatus, str, List[str], Optional[str]]:
        key = api_key.strip()
        fallback_models = ["openai/gpt-4o", "anthropic/claude-3.5-sonnet", "google/gemini-2.0-flash-001", "deepseek/deepseek-r1"]
        try:
            with httpx.Client(timeout=15.0) as client:
                # OpenRouter /api/v1/models is public; MUST use /api/v1/auth/key to verify authentication
                r_auth = client.get("https://openrouter.ai/api/v1/auth/key", headers={"Authorization": f"Bearer {key}"})
            if r_auth.status_code == 200:
                try:
                    with httpx.Client(timeout=15.0) as client:
                        r_models = client.get("https://openrouter.ai/api/v1/models")
                    if r_models.status_code == 200:
                        data = r_models.json().get("data", [])
                        raw_ids = [m.get("id") for m in data if isinstance(m, dict) and m.get("id")]
                        models = raw_ids[:30] if raw_ids else fallback_models
                        return "active", "Key is active", models, models[0]
                except Exception:
                    pass
                return "active", "Key is active", fallback_models, fallback_models[0]

            detail = r_auth.text[:500]
            try:
                detail = r_auth.json().get("error", {}).get("message") or detail
            except Exception:
                pass
            status = "invalid" if _is_invalid_phrase(str(detail)) else "inactive"
            return status, str(detail), fallback_models, fallback_models[0]
        except Exception as e:
            return "inactive", f"Could not reach OpenRouter: {e!s}", fallback_models, fallback_models[0]


class GrokProvider(BaseLLMProvider):
    provider_id = "Grok"
    display_name = "xAI (Grok)"
    key_prefixes = ["xai-"]

    def validate_and_fetch_models(self, api_key: str) -> Tuple[ValidationStatus, str, List[str], Optional[str]]:
        key = api_key.strip()
        fallback_models = ["grok-2-latest", "grok-2-vision-latest", "grok-beta"]
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get("https://api.x.ai/v1/models", headers={"Authorization": f"Bearer {key}"})
            if r.status_code == 200:
                data = r.json().get("data", [])
                raw_ids = [m.get("id") for m in data if isinstance(m, dict) and m.get("id")]
                models = raw_ids if raw_ids else fallback_models
                return "active", "Key is active", models, models[0]

            detail = r.text[:500]
            status = "invalid" if _is_invalid_phrase(str(detail)) else "inactive"
            return status, str(detail), fallback_models, fallback_models[0]
        except Exception as e:
            return "inactive", f"Could not reach xAI: {e!s}", fallback_models, fallback_models[0]


class PerplexityProvider(BaseLLMProvider):
    provider_id = "Perplexity"
    display_name = "Perplexity AI"
    key_prefixes = ["pplx-"]
    def validate_and_fetch_models(self, api_key: str) -> Tuple[ValidationStatus, str, List[str], Optional[str]]:
        key = api_key.strip()
        fallback_models = ["sonar-pro", "sonar", "sonar-reasoning"]
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get("https://api.perplexity.ai/models", headers={"Authorization": f"Bearer {key}"})
            if r.status_code == 200:
                data = r.json().get("data", [])
                raw_ids = [m.get("id") for m in data if isinstance(m, dict) and m.get("id")]
                models = raw_ids if raw_ids else fallback_models
                return "active", "Key is active", models, models[0]
            detail = r.text[:500]
            status = "invalid" if _is_invalid_phrase(str(detail)) else "inactive"
            return status, str(detail), fallback_models, fallback_models[0]
        except Exception as e:
            return "inactive", f"Could not reach Perplexity: {e!s}", fallback_models, fallback_models[0]


class CohereProvider(BaseLLMProvider):
    provider_id = "Cohere"
    display_name = "Cohere"
    key_prefixes = ["co-"]

    def validate_and_fetch_models(self, api_key: str) -> Tuple[ValidationStatus, str, List[str], Optional[str]]:
        key = api_key.strip()
        fallback_models = ["command-r-plus", "command-r", "command-light"]
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get("https://api.cohere.com/v1/models", headers={"Authorization": f"Bearer {key}"})
            if r.status_code == 200:
                data = r.json().get("models", [])
                raw_ids = [m.get("name") for m in data if isinstance(m, dict) and m.get("name")]
                models = raw_ids if raw_ids else fallback_models
                return "active", "Key is active", models, models[0]
            detail = r.text[:500]
            status = "invalid" if _is_invalid_phrase(str(detail)) else "inactive"
            return status, str(detail), fallback_models, fallback_models[0]
        except Exception as e:
            return "inactive", f"Could not reach Cohere: {e!s}", fallback_models, fallback_models[0]


class HuggingFaceProvider(BaseLLMProvider):
    provider_id = "HuggingFace"
    display_name = "Hugging Face"
    key_prefixes = ["hf_"]

    def validate_and_fetch_models(self, api_key: str) -> Tuple[ValidationStatus, str, List[str], Optional[str]]:
        key = api_key.strip()
        fallback_models = ["meta-llama/Llama-3.3-70B-Instruct", "deepseek-ai/DeepSeek-R1", "mistralai/Mistral-7B-Instruct-v0.3"]
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get("https://huggingface.co/api/whoami-v2", headers={"Authorization": f"Bearer {key}"})
            if r.status_code == 200:
                return "active", "Key is active", fallback_models, fallback_models[0]
            detail = r.text[:500]
            status = "invalid" if _is_invalid_phrase(str(detail)) else "inactive"
            return status, str(detail), fallback_models, fallback_models[0]
        except Exception as e:
            return "inactive", f"Could not reach HuggingFace: {e!s}", fallback_models, fallback_models[0]


class FireworksProvider(BaseLLMProvider):
    provider_id = "Fireworks"
    display_name = "Fireworks AI"
    key_prefixes = ["fw-"]

    def validate_and_fetch_models(self, api_key: str) -> Tuple[ValidationStatus, str, List[str], Optional[str]]:
        key = api_key.strip()
        fallback_models = ["accounts/fireworks/models/llama-v3p3-70b-instruct", "accounts/fireworks/models/deepseek-r1"]
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get("https://api.fireworks.ai/inference/v1/models", headers={"Authorization": f"Bearer {key}"})
            if r.status_code == 200:
                data = r.json().get("data", [])
                raw_ids = [m.get("id") for m in data if isinstance(m, dict) and m.get("id")]
                models = raw_ids if raw_ids else fallback_models
                return "active", "Key is active", models, models[0]
            detail = r.text[:500]
            status = "invalid" if _is_invalid_phrase(str(detail)) else "inactive"
            return status, str(detail), fallback_models, fallback_models[0]
        except Exception as e:
            return "inactive", f"Could not reach Fireworks: {e!s}", fallback_models, fallback_models[0]


class GenericOpenAICompatibleProvider(BaseLLMProvider):
    provider_id = "OpenAICompatible"
    display_name = "OpenAI Compatible Provider"
    key_prefixes = []

    OPENAI_ENDPOINTS = [
        ("Together", "https://api.together.xyz/v1/models"),
        ("DeepInfra", "https://api.deepinfra.com/v1/openai/models"),
        ("Novita", "https://api.novita.ai/v3/openai/models"),
        ("SambaNova", "https://api.sambanova.ai/v1/models"),
        ("Cerebras", "https://api.cerebras.ai/v1/models"),
        ("Hyperbolic", "https://api.hyperbolic.xyz/v1/models"),
    ]

    def validate_and_fetch_models(self, api_key: str) -> Tuple[ValidationStatus, str, List[str], Optional[str]]:
        key = api_key.strip()
        for prov_id, url in self.OPENAI_ENDPOINTS:
            try:
                with httpx.Client(timeout=10.0) as client:
                    r = client.get(url, headers={"Authorization": f"Bearer {key}"})
                if r.status_code == 200:
                    data = r.json().get("data", [])
                    raw_ids = [m.get("id") for m in data if isinstance(m, dict) and m.get("id")]
                    if raw_ids:
                        return "active", f"Key is active on {prov_id}", raw_ids[:30], raw_ids[0]
            except Exception:
                continue
        return "inactive", "Could not authenticate with any OpenAI-compatible provider", ["default"], "default"


class LLMProviderRegistry:
    """Central registry of LLM providers."""

    def __init__(self) -> None:
        self._providers: Dict[str, BaseLLMProvider] = {}
        # Register standard providers
        for p in [
            OpenAIProvider(),
            AnthropicProvider(),
            GeminiProvider(),
            GroqProvider(),
            MistralProvider(),
            DeepSeekProvider(),
            OpenRouterProvider(),
            GrokProvider(),
            PerplexityProvider(),
            CohereProvider(),
            HuggingFaceProvider(),
            FireworksProvider(),
            GenericOpenAICompatibleProvider(),
        ]:
            self.register(p)

    def register(self, provider: BaseLLMProvider) -> None:
        self._providers[provider.provider_id.lower()] = provider

    def get_provider_by_id(self, provider_id: str) -> Optional[BaseLLMProvider]:
        pid = (provider_id or "").strip().lower()
        if pid in self._providers:
            return self._providers[pid]
        # Soft matching
        for k, p in self._providers.items():
            if k in pid or pid in k or p.display_name.lower() in pid:
                return p
        return None

    def detect_provider(self, api_key: str) -> Optional[BaseLLMProvider]:
        key = (api_key or "").strip()
        if not key:
            return None
        # 1. Exact prefix matching FIRST
        for p in self._providers.values():
            for prefix in p.key_prefixes:
                if key.startswith(prefix):
                    return p
        # 2. Regex pattern matching SECOND
        for p in self._providers.values():
            if p.matches_key(key):
                return p
        return None

    def detect_and_validate(self, api_key: str, override_provider_id: Optional[str] = None) -> Dict[str, Any]:
        key = (api_key or "").strip()
        if not key:
            return {
                "detected_provider": None,
                "status": "invalid",
                "message": "No API key provided",
                "available_models": [],
                "default_model": None,
            }

        # 1. If validating for a specific provider (e.g. existing row validation)
        if override_provider_id:
            p_override = self.get_provider_by_id(override_provider_id)
            if p_override:
                st, msg, models, default_m = p_override.validate_and_fetch_models(key)
                return {
                    "detected_provider": p_override.provider_id,
                    "display_name": p_override.display_name,
                    "status": st,
                    "message": msg,
                    "available_models": models if models else ["default"],
                    "default_model": default_m or (models[0] if models else "default"),
                }

        # 2. Otherwise auto-detect provider for a new key
        candidate_providers = []
        p_hint = self.detect_provider(key)
        if p_hint:
            candidate_providers.append(p_hint)

        for p in self._providers.values():
            if p not in candidate_providers:
                candidate_providers.append(p)

        best_result = None
        for p in candidate_providers:
            try:
                st, msg, models, default_m = p.validate_and_fetch_models(key)
                res = {
                    "detected_provider": p.provider_id,
                    "display_name": p.display_name,
                    "status": st,
                    "message": msg,
                    "available_models": models if models else ["default"],
                    "default_model": default_m or (models[0] if models else "default"),
                }
                if st == "active":
                    return res
                if best_result is None or p_hint == p:
                    best_result = res
            except Exception:
                continue

        return best_result or {
            "detected_provider": "Unknown",
            "status": "invalid",
            "message": "Could not validate API key with any provider",
            "available_models": [],
            "default_model": None,
        }

    def list_providers_metadata(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": p.provider_id,
                "label": p.display_name,
                "key_prefixes": p.key_prefixes,
            }
            for p in self._providers.values()
        ]


# Singleton instance
provider_registry = LLMProviderRegistry()
