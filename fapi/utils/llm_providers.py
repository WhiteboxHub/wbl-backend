import logging
import httpx
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_PROVIDER_ALIASES: Dict[str, str] = {
    "openai": "OpenAI",
    "gpt": "OpenAI",
    "claude": "Claude",
    "anthropic": "Claude",
    "mistral": "Mistral",
    "gemini": "Gemini",
    "google": "Gemini",
    "groq": "Groq",
    "together": "Together",
    "perplexity": "Perplexity",
    "llama": "Llama",
    "grok": "Grok",
    "deepseek": "DeepSeek",
    "cohere": "Cohere",
    "azureopenai": "AzureOpenAI",
    "awsbedrock": "AWSBedrock",
    "vertexai": "VertexAI",
}

def normalize_llm_provider_name(provider_name: str) -> str:
    k = (provider_name or "").strip().lower()
    for alias, canonical in _PROVIDER_ALIASES.items():
        if alias == k:
            return canonical
    return provider_name.strip()

FALLBACK_MODELS: Dict[str, List[str]] = {
    "OpenAI": ["gpt-4o-mini", "gpt-4o", "o1-mini", "o3-mini"],
    "Claude": ["claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022", "claude-3-opus-20240229"],
    "Gemini": ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
    "Mistral": ["mistral-large-latest", "mistral-small-latest", "codestral-latest"],
    "Groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
    "Together": ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "mistralai/Mixtral-8x7B-Instruct-v0.1"],
    "Perplexity": ["sonar", "sonar-pro", "sonar-reasoning"],
}

def _default_model_for_provider(provider: str) -> str:
    models = FALLBACK_MODELS.get(provider)
    return models[0] if models else "gpt-4o-mini"


_models_cache: Dict[str, Tuple[List[str], datetime]] = {}
_cache_lock = threading.Lock()
CACHE_TTL = timedelta(hours=1)


def get_cached_models(provider_name: str, api_key: str, fetch_func) -> List[str]:
    cache_key = f"{provider_name}_{api_key[:10]}"
    now = datetime.now()
    with _cache_lock:
        if cache_key in _models_cache:
            models, expiry = _models_cache[cache_key]
            if now < expiry:
                return models
    try:
        models = fetch_func(api_key)
        if models:
            with _cache_lock:
                _models_cache[cache_key] = (models, now + CACHE_TTL)
            return models
    except Exception as e:
        logger.warning(f"Error fetching models dynamically for {provider_name}: {e}")
    return []


def execute_request_openai_like(
    url: str,
    headers: dict,
    model: str,
    system_prompt: Optional[str],
    user_prompt: str,
    temperature: float,
    max_tokens: int,
) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    try:
        with httpx.Client(timeout=90.0) as client:
            resp = client.post(url, headers=headers, json=payload)
        if resp.status_code == 200:
            content = resp.json().get("choices", [{}])[0].get("message", {}).get("content")
            return content, None, resp.status_code
        else:
            return None, resp.text, resp.status_code
    except httpx.RequestError as e:
        return None, f"Network error: {e}", None


class ProviderAdapter:
    def detect(self, api_key: str) -> bool:
        raise NotImplementedError()

    def validate_key(self, api_key: str) -> Tuple[str, str]:
        raise NotImplementedError()

    def list_models(self, api_key: str) -> List[str]:
        raise NotImplementedError()

    def classify_error(self, error_message: str, status_code: Optional[int]) -> str:
        raise NotImplementedError()

    def execute_request(
        self,
        api_key: str,
        model: str,
        system_prompt: Optional[str],
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        raise NotImplementedError()

    def supports_speech(self) -> bool:
        return False


class OpenAIProviderAdapter(ProviderAdapter):
    def detect(self, api_key: str) -> bool:
        k = api_key.strip()
        return k.startswith("sk-proj-") or (k.startswith("sk-") and len(k) >= 48)

    def validate_key(self, api_key: str) -> Tuple[str, str]:
        try:
            with httpx.Client(timeout=20.0) as client:
                r = client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key.strip()}"},
                )
            if r.status_code == 200:
                return "active", "Key is active"
            
            body = r.text
            detail = body[:500]
            try:
                err_data = r.json().get("error", {})
                detail = err_data.get("message") or detail
            except Exception:
                pass
            
            return self._handle_error_response(detail, r.status_code)
        except httpx.RequestError as e:
            return "inactive", f"Could not reach OpenAI: {e}"

    def _handle_error_response(self, detail: str, code: int) -> Tuple[str, str]:
        classification = self.classify_error(detail, code)
        if classification == "CREDITS_EXHAUSTED":
            return "credits_exhausted", f"OpenAI Credits Exhausted: {detail}"
        if classification == "INVALID_KEY":
            return "invalid", f"OpenAI Authentication Failed: {detail}"
        return "inactive", f"OpenAI Inactive: {detail}"

    def list_models(self, api_key: str) -> List[str]:
        def fetch(key):
            with httpx.Client(timeout=20.0) as client:
                r = client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
            if r.status_code == 200:
                data = r.json()
                models = [m["id"] for m in data.get("data", [])]
                chat_models = [m for m in models if m.startswith(("gpt-", "o1", "o3", "o4"))]
                return sorted(chat_models) if chat_models else sorted(models)
            raise Exception("Failed to fetch models")

        cached = get_cached_models("OpenAI", api_key, fetch)
        return cached if cached else FALLBACK_MODELS["OpenAI"]

    def classify_error(self, error_message: str, status_code: Optional[int]) -> str:
        msg = error_message.lower()
        if status_code == 401:
            return "INVALID_KEY"
        if "billing_limit_reached" in msg or "quota" in msg or "exhausted" in msg or (status_code == 429 and "quota" in msg):
            return "CREDITS_EXHAUSTED"
        if status_code == 429:
            return "RATE_LIMITED"
        if status_code and status_code >= 500:
            return "TEMPORARY_PROVIDER_ERROR"
        return "UNKNOWN_ERROR"

    def execute_request(
        self,
        api_key: str,
        model: str,
        system_prompt: Optional[str],
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        return execute_request_openai_like(
            url="https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"},
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )

    def supports_speech(self) -> bool:
        return True


class AnthropicProviderAdapter(ProviderAdapter):
    def detect(self, api_key: str) -> bool:
        return api_key.strip().startswith("sk-ant-")

    def validate_key(self, api_key: str) -> Tuple[str, str]:
        try:
            with httpx.Client(timeout=20.0) as client:
                r = client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": api_key.strip(),
                        "anthropic-version": "2023-06-01",
                    },
                )
            if r.status_code == 200:
                return "active", "Key is active"
            
            body = r.text
            detail = body[:500]
            try:
                err_data = r.json().get("error", {})
                detail = err_data.get("message") or detail
            except Exception:
                pass
            
            classification = self.classify_error(detail, r.status_code)
            if classification == "CREDITS_EXHAUSTED":
                return "credits_exhausted", f"Anthropic Credits Exhausted: {detail}"
            if classification == "INVALID_KEY":
                return "invalid", f"Anthropic Authentication Failed: {detail}"
            return "inactive", f"Anthropic Inactive: {detail}"
        except httpx.RequestError as e:
            return "inactive", f"Could not reach Anthropic: {e}"

    def list_models(self, api_key: str) -> List[str]:
        def fetch(key):
            with httpx.Client(timeout=20.0) as client:
                r = client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": key,
                        "anthropic-version": "2023-06-01",
                    },
                )
            if r.status_code == 200:
                data = r.json()
                models = [m["id"] for m in data.get("data", [])]
                return sorted(models)
            raise Exception("Failed to fetch models")

        cached = get_cached_models("Claude", api_key, fetch)
        return cached if cached else FALLBACK_MODELS["Claude"]

    def classify_error(self, error_message: str, status_code: Optional[int]) -> str:
        msg = error_message.lower()
        if status_code == 401 or status_code == 403:
            return "INVALID_KEY"
        if "quota" in msg or "billing" in msg or "credit" in msg or "exhausted" in msg:
            return "CREDITS_EXHAUSTED"
        if status_code == 429:
            return "RATE_LIMITED"
        if status_code and status_code >= 500:
            return "TEMPORARY_PROVIDER_ERROR"
        return "UNKNOWN_ERROR"

    def execute_request(
        self,
        api_key: str,
        model: str,
        system_prompt: Optional[str],
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        headers = {
            "x-api-key": api_key.strip(),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": user_prompt}]
        }
        if system_prompt:
            payload["system"] = system_prompt
        try:
            with httpx.Client(timeout=90.0) as client:
                resp = client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
            if resp.status_code == 200:
                content = resp.json().get("content", [{}])[0].get("text")
                return content, None, resp.status_code
            else:
                return None, resp.text, resp.status_code
        except httpx.RequestError as e:
            return None, f"Network error: {e}", None


class GeminiProviderAdapter(ProviderAdapter):
    def detect(self, api_key: str) -> bool:
        return api_key.strip().startswith("AIzaSy")

    def validate_key(self, api_key: str) -> Tuple[str, str]:
        try:
            with httpx.Client(timeout=20.0) as client:
                r = client.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key.strip()}",
                )
            if r.status_code == 200:
                return "active", "Key is active"
            
            body = r.text
            detail = body[:500]
            try:
                err_data = r.json().get("error", {})
                detail = err_data.get("message") or detail
            except Exception:
                pass
            
            classification = self.classify_error(detail, r.status_code)
            if classification == "CREDITS_EXHAUSTED":
                return "credits_exhausted", f"Gemini Credits Exhausted: {detail}"
            if classification == "INVALID_KEY":
                return "invalid", f"Gemini Authentication Failed: {detail}"
            return "inactive", f"Gemini Inactive: {detail}"
        except httpx.RequestError as e:
            return "inactive", f"Could not reach Gemini: {e}"

    def list_models(self, api_key: str) -> List[str]:
        def fetch(key):
            with httpx.Client(timeout=20.0) as client:
                r = client.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
                )
            if r.status_code == 200:
                data = r.json()
                models = [m["name"].split("/")[-1] for m in data.get("models", [])]
                chat_models = [m for m in models if m.startswith("gemini-")]
                return sorted(chat_models) if chat_models else sorted(models)
            raise Exception("Failed to fetch models")

        cached = get_cached_models("Gemini", api_key, fetch)
        return cached if cached else FALLBACK_MODELS["Gemini"]

    def classify_error(self, error_message: str, status_code: Optional[int]) -> str:
        msg = error_message.lower()
        if "api_key_invalid" in msg or "invalid key" in msg or status_code == 400:
            return "INVALID_KEY"
        if "quota" in msg or "exhausted" in msg or "billing" in msg or status_code == 429:
            return "CREDITS_EXHAUSTED"
        if status_code and status_code >= 500:
            return "TEMPORARY_PROVIDER_ERROR"
        return "UNKNOWN_ERROR"

    def execute_request(
        self,
        api_key: str,
        model: str,
        system_prompt: Optional[str],
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key.strip()}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": user_prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [
                    {
                        "text": system_prompt
                    }
                ]
            }
        try:
            with httpx.Client(timeout=90.0) as client:
                resp = client.post(url, headers={"Content-Type": "application/json"}, json=payload)
            if resp.status_code == 200:
                try:
                    content = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text")
                    return content, None, resp.status_code
                except Exception as e:
                    return None, f"Failed to parse Gemini response: {e}. Raw: {resp.text}", resp.status_code
            else:
                return None, resp.text, resp.status_code
        except httpx.RequestError as e:
            return None, f"Network error: {e}", None


class GroqProviderAdapter(ProviderAdapter):
    def detect(self, api_key: str) -> bool:
        return api_key.strip().startswith("gsk_")

    def validate_key(self, api_key: str) -> Tuple[str, str]:
        try:
            with httpx.Client(timeout=20.0) as client:
                r = client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {api_key.strip()}"},
                )
            if r.status_code == 200:
                return "active", "Key is active"
            
            body = r.text
            detail = body[:500]
            try:
                err_data = r.json().get("error", {})
                detail = err_data.get("message") or detail
            except Exception:
                pass
            
            classification = self.classify_error(detail, r.status_code)
            if classification == "CREDITS_EXHAUSTED":
                return "credits_exhausted", f"Groq Credits Exhausted: {detail}"
            if classification == "INVALID_KEY":
                return "invalid", f"Groq Authentication Failed: {detail}"
            return "inactive", f"Groq Inactive: {detail}"
        except httpx.RequestError as e:
            return "inactive", f"Could not reach Groq: {e}"

    def list_models(self, api_key: str) -> List[str]:
        def fetch(key):
            with httpx.Client(timeout=20.0) as client:
                r = client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
            if r.status_code == 200:
                data = r.json()
                models = [m["id"] for m in data.get("data", [])]
                return sorted(models)
            raise Exception("Failed to fetch models")

        cached = get_cached_models("Groq", api_key, fetch)
        return cached if cached else FALLBACK_MODELS["Groq"]

    def classify_error(self, error_message: str, status_code: Optional[int]) -> str:
        msg = error_message.lower()
        if status_code == 401:
            return "INVALID_KEY"
        if "quota" in msg or "billing" in msg or "exhausted" in msg or (status_code == 429 and "quota" in msg):
            return "CREDITS_EXHAUSTED"
        if status_code == 429:
            return "RATE_LIMITED"
        if status_code and status_code >= 500:
            return "TEMPORARY_PROVIDER_ERROR"
        return "UNKNOWN_ERROR"

    def execute_request(
        self,
        api_key: str,
        model: str,
        system_prompt: Optional[str],
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        return execute_request_openai_like(
            url="https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"},
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )


class TogetherProviderAdapter(ProviderAdapter):
    def detect(self, api_key: str) -> bool:
        k = api_key.strip()
        if len(k) == 64:
            try:
                int(k, 16)
                return True
            except ValueError:
                pass
        return False

    def validate_key(self, api_key: str) -> Tuple[str, str]:
        try:
            with httpx.Client(timeout=20.0) as client:
                r = client.get(
                    "https://api.together.xyz/v1/models",
                    headers={"Authorization": f"Bearer {api_key.strip()}"},
                )
            if r.status_code == 200:
                return "active", "Key is active"
            
            body = r.text
            detail = body[:500]
            classification = self.classify_error(detail, r.status_code)
            if classification == "CREDITS_EXHAUSTED":
                return "credits_exhausted", f"Together Credits Exhausted: {detail}"
            if classification == "INVALID_KEY":
                return "invalid", f"Together Authentication Failed: {detail}"
            return "inactive", f"Together Inactive: {detail}"
        except httpx.RequestError as e:
            return "inactive", f"Could not reach Together: {e}"

    def list_models(self, api_key: str) -> List[str]:
        def fetch(key):
            with httpx.Client(timeout=20.0) as client:
                r = client.get(
                    "https://api.together.xyz/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
            if r.status_code == 200:
                data = r.json()
                models = [m["id"] for m in data]
                chat_models = [m for m in models if "chat" in m.lower() or "instruct" in m.lower()]
                return sorted(chat_models) if chat_models else sorted(models)
            raise Exception("Failed to fetch models")

        cached = get_cached_models("Together", api_key, fetch)
        return cached if cached else FALLBACK_MODELS["Together"]

    def classify_error(self, error_message: str, status_code: Optional[int]) -> str:
        msg = error_message.lower()
        if status_code == 401:
            return "INVALID_KEY"
        if "quota" in msg or "billing" in msg or "exhausted" in msg:
            return "CREDITS_EXHAUSTED"
        if status_code == 429:
            return "RATE_LIMITED"
        if status_code and status_code >= 500:
            return "TEMPORARY_PROVIDER_ERROR"
        return "UNKNOWN_ERROR"

    def execute_request(
        self,
        api_key: str,
        model: str,
        system_prompt: Optional[str],
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        return execute_request_openai_like(
            url="https://api.together.xyz/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"},
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )


class PerplexityProviderAdapter(ProviderAdapter):
    def detect(self, api_key: str) -> bool:
        return api_key.strip().startswith("pplx-")

    def validate_key(self, api_key: str) -> Tuple[str, str]:
        try:
            with httpx.Client(timeout=20.0) as client:
                r = client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key.strip()}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "sonar",
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                    }
                )
            if r.status_code in (200, 422):
                return "active", "Key is active"
            
            body = r.text
            detail = body[:500]
            classification = self.classify_error(detail, r.status_code)
            if classification == "CREDITS_EXHAUSTED":
                return "credits_exhausted", f"Perplexity Credits Exhausted: {detail}"
            if classification == "INVALID_KEY":
                return "invalid", f"Perplexity Authentication Failed: {detail}"
            return "inactive", f"Perplexity Inactive: {detail}"
        except httpx.RequestError as e:
            return "inactive", f"Could not reach Perplexity: {e}"

    def list_models(self, api_key: str) -> List[str]:
        return FALLBACK_MODELS["Perplexity"]

    def classify_error(self, error_message: str, status_code: Optional[int]) -> str:
        msg = error_message.lower()
        if status_code == 401:
            return "INVALID_KEY"
        if "quota" in msg or "billing" in msg or "exhausted" in msg:
            return "CREDITS_EXHAUSTED"
        if status_code == 429:
            return "RATE_LIMITED"
        if status_code and status_code >= 500:
            return "TEMPORARY_PROVIDER_ERROR"
        return "UNKNOWN_ERROR"

    def execute_request(
        self,
        api_key: str,
        model: str,
        system_prompt: Optional[str],
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        return execute_request_openai_like(
            url="https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"},
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )


class MistralProviderAdapter(ProviderAdapter):
    def detect(self, api_key: str) -> bool:
        k = api_key.strip()
        return len(k) == 32 and k.isalnum()

    def validate_key(self, api_key: str) -> Tuple[str, str]:
        try:
            with httpx.Client(timeout=20.0) as client:
                r = client.get(
                    "https://api.mistral.ai/v1/models",
                    headers={"Authorization": f"Bearer {api_key.strip()}"},
                )
            if r.status_code == 200:
                return "active", "Key is active"
            
            body = r.text
            detail = body[:500]
            try:
                detail = r.json().get("message") or detail
            except Exception:
                pass
            
            classification = self.classify_error(detail, r.status_code)
            if classification == "CREDITS_EXHAUSTED":
                return "credits_exhausted", f"Mistral Credits Exhausted: {detail}"
            if classification == "INVALID_KEY":
                return "invalid", f"Mistral Authentication Failed: {detail}"
            return "inactive", f"Mistral Inactive: {detail}"
        except httpx.RequestError as e:
            return "inactive", f"Could not reach Mistral: {e}"

    def list_models(self, api_key: str) -> List[str]:
        def fetch(key):
            with httpx.Client(timeout=20.0) as client:
                r = client.get(
                    "https://api.mistral.ai/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
            if r.status_code == 200:
                data = r.json()
                models = [m["id"] for m in data.get("data", [])]
                return sorted(models)
            raise Exception("Failed to fetch models")

        cached = get_cached_models("Mistral", api_key, fetch)
        return cached if cached else FALLBACK_MODELS["Mistral"]

    def classify_error(self, error_message: str, status_code: Optional[int]) -> str:
        msg = error_message.lower()
        if status_code == 401:
            return "INVALID_KEY"
        if "quota" in msg or "billing" in msg or "exhausted" in msg:
            return "CREDITS_EXHAUSTED"
        if status_code == 429:
            return "RATE_LIMITED"
        if status_code and status_code >= 500:
            return "TEMPORARY_PROVIDER_ERROR"
        return "UNKNOWN_ERROR"

    def execute_request(
        self,
        api_key: str,
        model: str,
        system_prompt: Optional[str],
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        return execute_request_openai_like(
            url="https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"},
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )


ADAPTERS: Dict[str, ProviderAdapter] = {
    "OpenAI": OpenAIProviderAdapter(),
    "Claude": AnthropicProviderAdapter(),
    "Gemini": GeminiProviderAdapter(),
    "Groq": GroqProviderAdapter(),
    "Together": TogetherProviderAdapter(),
    "Perplexity": PerplexityProviderAdapter(),
    "Mistral": MistralProviderAdapter(),
}

def get_adapter(provider_name: str) -> Optional[ProviderAdapter]:
    normalized = normalize_llm_provider_name(provider_name)
    for canonical_name, adapter in ADAPTERS.items():
        if canonical_name.lower() == normalized.lower():
            return adapter
    return None


def detect_provider(api_key: str) -> Tuple[Optional[str], List[str], str]:
    k = api_key.strip()
    if not k:
        return None, [], "inactive"
    
    matched_providers = []
    for provider_name, adapter in ADAPTERS.items():
        if adapter.detect(k):
            matched_providers.append((provider_name, adapter))
            
    for provider_name, adapter in matched_providers:
        status, msg = adapter.validate_key(k)
        if status in ("active", "credits_exhausted", "rate_limited"):
            try:
                models = adapter.list_models(k)
            except Exception:
                models = FALLBACK_MODELS.get(provider_name, [])
            return provider_name, models, status
            
    for provider_name, adapter in ADAPTERS.items():
        if any(p[0] == provider_name for p in matched_providers):
            continue
        status, msg = adapter.validate_key(k)
        if status in ("active", "credits_exhausted", "rate_limited"):
            try:
                models = adapter.list_models(k)
            except Exception:
                models = FALLBACK_MODELS.get(provider_name, [])
            return provider_name, models, status

    return None, [], "inactive"
