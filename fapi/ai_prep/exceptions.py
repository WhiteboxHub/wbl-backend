"""Custom exceptions for the AIPrep coaching report pipeline."""
from __future__ import annotations


class NoCandidateLLMKeyError(Exception):
    """Raised when a candidate has no active LLM API key configured.

    This is an *expected* business case (candidate hasn't set up a key yet),
    not a system failure.  Callers should surface a user-friendly "please add
    a valid API key" message rather than treating this as a 500.
    """

    def __init__(self, candidate_id: int) -> None:
        self.candidate_id = candidate_id
        super().__init__(
            f"No active LLM API key found for candidate_id={candidate_id}. "
            "Candidate must add a key under 'My LLM Keys'."
        )


class UnsupportedProviderError(Exception):
    """Raised when the stored provider_name is not handled by call_llm.

    We never silently fall back to a default provider — the caller must know
    which provider is in use so it can surface the right error message.
    """

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        super().__init__(
            f"LLM provider '{provider_name}' is not supported by the AIPrep "
            "report generator. Supported providers: openai, anthropic, gemini, "
            "groq, deepseek, mistral, openrouter, xai."
        )


class CandidateLLMKeyError(Exception):
    """Raised when the provider SDK rejects the candidate's API key (auth / permission error).

    This wraps provider-specific auth exceptions so callers do not need to
    import SDK-specific error classes.  The original SDK message is preserved
    in ``original_message``.  The raw key is *never* stored here.
    """

    def __init__(
        self,
        candidate_id: int,
        provider_name: str,
        original_message: str,
    ) -> None:
        self.candidate_id = candidate_id
        self.provider_name = provider_name
        self.original_message = original_message
        super().__init__(
            f"API key for candidate_id={candidate_id} (provider={provider_name}) "
            f"was rejected by the provider: {original_message}"
        )
class ParseError(Exception):
    """Raised when LLM output JSON validation against Contract 3 schema fails.

    This wraps json parsing and Pydantic validation errors so that the LLM pipeline
    can intercept schema mismatches gracefully.
    """

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        self.message = message
        self.original_error = original_error
        super().__init__(message)