"""Key retrieval service for the AIPrep coaching report generator.

Fetches and decrypts the active LLM API key for a given candidate from the
``candidate_llm_api_keys`` table (which already exists in production).

Selection rule (matches existing ``ensure_default_llm_key_for_candidate``
logic in coderpad_openai_key.py):
  1. status = 'active' rows only.
  2. Prefer the row where is_default = 1.
  3. If no default, use the row with the most-recent last_validated_at.

Decryption uses the same Fernet setup as the rest of the codebase
(``fapi/utils/encryption_utils.py``).  Plaintext keys (data-quality
pre-existing issue) are handled gracefully with a WARNING log — we never
crash on a non-Fernet token.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from cryptography.fernet import InvalidToken
from sqlalchemy.orm import Session

from fapi.ai_prep.exceptions import NoCandidateLLMKeyError
from fapi.db.models import CandidateLlmApiKeyORM
from fapi.utils.encryption_utils import get_fernet

logger = logging.getLogger("aiprep.llm")

# ---------------------------------------------------------------------------
# Provider normalisation
# ---------------------------------------------------------------------------

# Canonical internal names (lowercase) used by call_llm for branching.
_PROVIDER_NORM: dict[str, str] = {
    "openai": "openai",
    "gpt": "openai",
    "anthropic": "anthropic",
    "claude": "anthropic",  # treat "claude" as an alias for anthropic
}


def _normalize_provider(raw: Optional[str]) -> str:
    """Return lowercase canonical provider name ('openai' | 'anthropic' | raw lower)."""
    key = (raw or "").strip().lower()
    return _PROVIDER_NORM.get(key, key)


# ---------------------------------------------------------------------------
# Data model returned by this service
# ---------------------------------------------------------------------------


@dataclass
class CandidateLLMKey:
    """Lightweight value object — just enough for call_llm to make the API call."""

    provider_name: str       # normalised to lowercase, e.g. "openai" / "anthropic"
    api_key: str             # decrypted plaintext key — NEVER log this value
    model_name: Optional[str]  # None means caller should use its own default


# ---------------------------------------------------------------------------
# Decryption helper
# ---------------------------------------------------------------------------


def _decrypt_key(raw: str) -> str:
    """Decrypt a Fernet-encrypted API key, or pass through plaintext keys.

    Behaviour:
    - If ``raw`` is a valid Fernet token (prefix ``gAAAAA``…), decrypt it.
    - If Fernet decryption fails with ``InvalidToken`` (pre-existing plaintext
      rows), log a WARNING and return the raw value — do NOT crash.
    - We intentionally do NOT log the decrypted value at any level.
    """
    s = (raw or "").strip()
    if not s:
        return ""

    # Fast path: known plaintext key prefixes — skip Fernet entirely.
    _PLAINTEXT_PREFIXES = (
        "sk-",       # OpenAI
        "sk-ant-",   # Anthropic (more specific, but also caught by sk-)
        "sk-proj-",  # OpenAI project key
        "AIza",      # Google / Gemini
        "gsk_",      # Groq
        "xai-",      # xAI / Grok
        "sk-or-",    # OpenRouter
        "sk-ds-",    # DeepSeek
        "msk-",      # Mistral
    )
    if s.startswith(_PLAINTEXT_PREFIXES):
        return s

    # Attempt Fernet decryption.
    try:
        f = get_fernet()
        return f.decrypt(s.encode()).decode()
    except InvalidToken:
        logger.warning(
            "aiprep.key_service: api_key value is not a valid Fernet token — "
            "treating as plaintext (pre-existing data quality issue). "
            "Row should be re-encrypted on next key update."
        )
        return s
    except Exception as exc:  # pragma: no cover — unexpected Fernet failure
        logger.warning(
            "aiprep.key_service: unexpected decryption error (%s) — "
            "treating stored value as plaintext.",
            type(exc).__name__,
        )
        return s


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_candidate_llm_key(db: Session, candidate_id: int) -> CandidateLLMKey:
    """Return the active LLM key for *candidate_id*, applying the default-preference rule.

    Raises:
        NoCandidateLLMKeyError: when no active key exists for this candidate.
            This is a normal, expected business case — the candidate hasn't
            configured a key yet.
    """
    # Fetch all active rows for this candidate, newest first.
    rows = (
        db.query(CandidateLlmApiKeyORM)
        .filter(
            CandidateLlmApiKeyORM.candidate_id == candidate_id,
            CandidateLlmApiKeyORM.status == "active",
        )
        .order_by(
            CandidateLlmApiKeyORM.is_default.desc(),      # default=True first
            CandidateLlmApiKeyORM.last_validated_at.desc(),  # then newest validated
            CandidateLlmApiKeyORM.id.desc(),              # stable tie-break
        )
        .all()
    )

    if not rows:
        raise NoCandidateLLMKeyError(candidate_id)

    # The ORDER BY above puts the best row first.  We iterate to find the
    # first row whose decrypted key is non-empty (guards against corrupt rows).
    chosen: Optional[CandidateLlmApiKeyORM] = None
    for row in rows:
        raw = str(row.api_key or "").strip()
        if raw:
            chosen = row
            break

    if chosen is None:
        raise NoCandidateLLMKeyError(candidate_id)

    decrypted = _decrypt_key(str(chosen.api_key))
    if not decrypted:
        raise NoCandidateLLMKeyError(candidate_id)

    return CandidateLLMKey(
        provider_name=_normalize_provider(chosen.provider_name),
        api_key=decrypted,           # ← NEVER log this value
        model_name=chosen.model_name or None,
    )
