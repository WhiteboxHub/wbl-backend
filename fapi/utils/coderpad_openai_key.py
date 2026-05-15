"""Resolve OpenAI API key for CoderPad LLM calls (header → DB → env).

DB lookup: ``authuser.uname`` (email) → ``candidate.id`` via ``candidate.email``,
then ``candidate_llm_api_keys.candidate_id`` = that ``candidate.id``.
"""
from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from fapi.db.models import AuthUserORM, CandidateLlmApiKeyORM
from fapi.utils.db_queries import fetch_candidate_id_and_status_by_email

CODERPAD_MISSING_OPENAI_KEY_MSG = (
    "No OpenAI API key available. Add an OpenAI key in your WBL account setup "
    "(API keys step), or paste a key in the optional override field if you are staff."
)


def resolve_coderpad_openai_api_key(
    db: Session,
    current_user: AuthUserORM,
    header_key: Optional[str],
) -> str:
    h = (header_key or "").strip()
    if h:
        return h
    uname = (getattr(current_user, "uname", None) or "").strip()
    if uname:
        row = fetch_candidate_id_and_status_by_email(db, uname)
        if row and row.candidateid is not None:
            db_key = _openai_key_for_candidate_id(db, int(row.candidateid))
            if db_key:
                return db_key
    return (os.getenv("CODERPAD_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()


def _openai_key_for_candidate_id(db: Session, candidate_id: int) -> Optional[str]:
    r = (
        db.query(CandidateLlmApiKeyORM)
        .filter(
            CandidateLlmApiKeyORM.candidate_id == candidate_id,
            func.lower(CandidateLlmApiKeyORM.provider_name) == "openai",
        )
        .order_by(CandidateLlmApiKeyORM.id.desc())
        .first()
    )
    if not r or r.api_key is None:
        return None
    s = str(r.api_key).strip()
    return s or None


def mask_openai_api_key(secret: str) -> str:
    """Short masked hint (never returns full key)."""
    s = (secret or "").strip()
    if not s:
        return ""
    if len(s) <= 12:
        return "•" * len(s)
    return f"{s[:7]}…{s[-4:]}"


def openai_key_db_preview_for_user(
    db: Session,
    current_user: AuthUserORM,
) -> tuple[bool, Optional[str]]:
    """Whether an OpenAI key row exists for ``candidate.id``, and a masked hint for display."""
    uname = (getattr(current_user, "uname", None) or "").strip()
    if not uname:
        return False, None
    row = fetch_candidate_id_and_status_by_email(db, uname)
    if not row or row.candidateid is None:
        return False, None
    raw = _openai_key_for_candidate_id(db, int(row.candidateid))
    if not raw:
        return False, None
    return True, mask_openai_api_key(raw)


def get_stored_openai_key_for_owner(db: Session, current_user: AuthUserORM) -> Optional[str]:
    """Full OpenAI API key from ``candidate_llm_api_keys`` for this user's ``candidate.id``."""
    uname = (getattr(current_user, "uname", None) or "").strip()
    if not uname:
        return None
    row = fetch_candidate_id_and_status_by_email(db, uname)
    if not row or row.candidateid is None:
        return None
    return _openai_key_for_candidate_id(db, int(row.candidateid))


def candidate_has_openai_key_in_db(db: Session, current_user: AuthUserORM) -> bool:
    """True if ``candidate_llm_api_keys`` has a non-empty OpenAI row for this user's ``candidate.id``."""
    uname = (getattr(current_user, "uname", None) or "").strip()
    if not uname:
        return False
    row = fetch_candidate_id_and_status_by_email(db, uname)
    if not row or row.candidateid is None:
        return False
    raw = _openai_key_for_candidate_id(db, int(row.candidateid))
    return bool(raw and str(raw).strip())


def openai_key_configured_for_user(db: Session, current_user: AuthUserORM) -> bool:
    """Whether LLM calls can proceed without the client sending X-OpenAI-Api-Key."""
    return bool(resolve_coderpad_openai_api_key(db, current_user, None).strip())


def save_candidate_openai_key_to_db(
    db: Session,
    current_user: AuthUserORM,
    api_key: str,
    model_name: Optional[str] = None,
) -> None:
    """Insert or update OpenAI row in ``candidate_llm_api_keys`` for ``candidate.id`` from ``candidate`` table (via email)."""
    key = (api_key or "").strip()
    if not key:
        raise ValueError("API key is required")
    uname = (getattr(current_user, "uname", None) or "").strip()
    if not uname:
        raise LookupError("User session has no username")
    row = fetch_candidate_id_and_status_by_email(db, uname)
    if not row or row.candidateid is None:
        raise LookupError("No candidate profile linked to this account")
    candidate_id = int(row.candidateid)
    existing = (
        db.query(CandidateLlmApiKeyORM)
        .filter(
            CandidateLlmApiKeyORM.candidate_id == candidate_id,
            func.lower(CandidateLlmApiKeyORM.provider_name) == "openai",
        )
        .order_by(CandidateLlmApiKeyORM.id.desc())
        .first()
    )
    m = (model_name or "gpt-4o-mini").strip() or "gpt-4o-mini"
    if existing:
        existing.api_key = key
        existing.model_name = m
    else:
        db.add(
            CandidateLlmApiKeyORM(
                candidate_id=candidate_id,
                provider_name="OpenAI",
                api_key=key,
                model_name=m,
            )
        )
    db.commit()
