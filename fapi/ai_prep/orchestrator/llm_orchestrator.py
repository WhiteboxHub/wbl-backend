"""LLM Orchestrator for managing LLM connections, prompt generation, and evaluation tasks."""
import logging
from typing import Any, Dict, Optional
from fapi.utils.llm_service import call_llm_with_context

logger = logging.getLogger(__name__)


class LLMOrchestrator:
    """Orchestrates model inference calls, prompt formatting, and fallback strategies."""

    @classmethod
    def call_eval_model(
        cls,
        api_key: str,
        provider: str,
        system_prompt: str,
        user_prompt: str,
        response_format: str = "json_object",
    ) -> str:
        return call_llm_with_context(
            api_key=api_key,
            provider=provider,
            prompt=user_prompt,
            system_prompt=system_prompt,
            response_format=response_format,
        )
