import time
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from fapi.db.models import AuthUserORM, CandidateLlmApiKeyORM
from fapi.utils.llm_providers import get_adapter, _default_model_for_provider
from fapi.utils.coderpad_openai_key import (
    _candidate_id_for_user,
    _default_llm_key_row,
    _row_secret,
    ensure_default_llm_key_for_candidate,
    _set_default_key_for_candidate,
)

logger = logging.getLogger(__name__)


def execute_llm_request_with_failover(
    db: Session,
    current_user: AuthUserORM,
    system_prompt: Optional[str],
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 2000,
) -> Dict[str, Any]:
    """
    Executes an LLM request using the user's default key.
    If execution fails due to credit/quota exhaustion or an invalid key,
    it marks the key's status in the database, unsets its default status,
    selects the next eligible active key, sets it as default, and retries the request.
    If all eligible keys are exhausted, raises an HTTP 400 with ALL_LLM_KEYS_UNAVAILABLE.
    """
    candidate_id = _candidate_id_for_user(db, current_user)
    attempted_key_ids: Set[int] = set()

    while True:
        ensure_default_llm_key_for_candidate(db, candidate_id, commit=True)
        default_row = _default_llm_key_row(db, candidate_id)

        if not default_row:
            logger.warning(f"No LLM keys configured for candidate {candidate_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ALL_LLM_KEYS_UNAVAILABLE",
            )

        key_id = int(default_row.id)
        if key_id in attempted_key_ids:
            logger.warning(f"Infinite loop prevented. All LLM keys exhausted for candidate {candidate_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ALL_LLM_KEYS_UNAVAILABLE",
            )

        attempted_key_ids.add(key_id)

        secret = _row_secret(default_row)
        if not secret:
            logger.warning(f"Default key row {key_id} has no secret key. Failing over.")
            default_row.status = "invalid"
            default_row.is_default = False
            db.commit()
            continue

        adapter = get_adapter(default_row.provider_name)
        if not adapter:
            logger.warning(f"Unsupported provider {default_row.provider_name} for key {key_id}. Failing over.")
            default_row.status = "inactive"
            default_row.is_default = False
            db.commit()
            continue

        model = default_row.model_name or _default_model_for_provider(default_row.provider_name)
        logger.info(f"Attempting LLM request using key {key_id} ({default_row.provider_name}, model={model})")

        content, error_msg, status_code = adapter.execute_request(
            api_key=secret,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if error_msg is None:
            # SUCCESS
            default_row.status = "active"
            default_row.failure_reason = None
            default_row.failure_code = None
            default_row.last_used_at = datetime.now(timezone.utc)
            default_row.last_validated_at = datetime.now(timezone.utc)
            db.commit()
            return {"content": content}

        # Handle failure and classification
        classification = adapter.classify_error(error_msg, status_code)
        logger.warning(f"LLM request failed on key {key_id}. Classification={classification}, Error={error_msg}")

        if classification == "RATE_LIMITED":
            # Retry with a quick backoff once
            logger.info("Rate limited. Sleeping 1.5 seconds and retrying once.")
            time.sleep(1.5)
            content, error_msg, status_code = adapter.execute_request(
                api_key=secret,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if error_msg is None:
                default_row.status = "active"
                default_row.failure_reason = None
                default_row.failure_code = None
                default_row.last_used_at = datetime.now(timezone.utc)
                default_row.last_validated_at = datetime.now(timezone.utc)
                db.commit()
                return {"content": content}
            classification = adapter.classify_error(error_msg, status_code)

        # Trigger failover for permanent errors
        if classification == "CREDITS_EXHAUSTED":
            default_row.status = "credits_exhausted"
            default_row.failure_reason = error_msg
            default_row.failure_code = "CREDITS_EXHAUSTED"
            default_row.is_default = False
            db.commit()
            _promote_next_active_key(db, candidate_id, key_id)
            continue
        elif classification in ("INVALID_KEY", "REVOKED_KEY"):
            default_row.status = "invalid"
            default_row.failure_reason = error_msg
            default_row.failure_code = "INVALID_KEY"
            default_row.is_default = False
            db.commit()
            _promote_next_active_key(db, candidate_id, key_id)
            continue
        else:
            # Temporary errors (rate limits after retry, timeouts, network issues, HTTP 5xx)
            # do NOT demote the key or unset its default status. Just raise HTTPException.
            logger.error(f"Temporary error occurred: {error_msg}. Not demoting the key.")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Temporary LLM error: {error_msg}",
            )


def _promote_next_active_key(db: Session, candidate_id: int, current_key_id: int) -> None:
    """Find the next eligible active key and set it as default."""
    eligible = (
        db.query(CandidateLlmApiKeyORM)
        .filter(
            CandidateLlmApiKeyORM.candidate_id == candidate_id,
            CandidateLlmApiKeyORM.status == "active",
            CandidateLlmApiKeyORM.id != current_key_id,
        )
        .order_by(CandidateLlmApiKeyORM.id.desc())
        .first()
    )
    if eligible:
        _set_default_key_for_candidate(db, candidate_id, int(eligible.id))
        db.commit()
