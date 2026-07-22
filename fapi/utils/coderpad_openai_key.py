"""Resolve LLM API keys for CoderPad and My LLM keys UI.

DB lookup: ``authuser.uname`` (email) → ``candidate.id`` via ``candidate.email``,
then ``candidate_llm_api_keys.candidate_id`` = that ``candidate.id``.

CoderPad OpenAI calls use the row marked **default** in My LLM keys when that row is
OpenAI; otherwise the latest OpenAI row. If only one key exists for a candidate, it
is promoted to default automatically.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from fapi.db.models import AuthUserORM, CandidateLlmApiKeyORM
from fapi.utils.db_queries import fetch_candidate_id_and_status_by_email
from fapi.utils.encryption_utils import decrypt_api_key, encrypt_api_key

CODERPAD_MISSING_OPENAI_KEY_MSG = (
    "No OpenAI API key available. Add an OpenAI key under My LLM keys and set it as "
    "default (or mark it default when it is your only key), or paste a key in the "
    "optional override field if you are staff."
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


def _provider_is_openai(provider_name: Optional[str]) -> bool:
    p = (provider_name or "").strip().lower()
    return p in ("openai", "gpt")


def _keys_for_candidate_id(
    db: Session,
    candidate_id: int,
) -> List[CandidateLlmApiKeyORM]:
    return (
        db.query(CandidateLlmApiKeyORM)
        .filter(CandidateLlmApiKeyORM.candidate_id == candidate_id)
        .order_by(CandidateLlmApiKeyORM.id.desc())
        .all()
    )


def ensure_default_llm_key_for_candidate(
    db: Session,
    candidate_id: int,
    *,
    commit: bool = False,
) -> None:
    """
    Ensure that exactly one eligible active key is marked as default in the database.
    If an active key is already marked as default, do nothing and ensure other keys are NOT default.
    Otherwise, clear default status on any ineligible keys, find the first active key, and promote it to default.
    """
    if not _llm_has_column(db, "is_default"):
        return

    # Check if we already have a valid default key
    default_row = _default_llm_key_row(db, candidate_id)
    if default_row:
        # Guarantee that no other key has default=True
        db.query(CandidateLlmApiKeyORM).filter(
            CandidateLlmApiKeyORM.candidate_id == candidate_id,
            CandidateLlmApiKeyORM.id != default_row.id,
        ).update({CandidateLlmApiKeyORM.is_default: False}, synchronize_session="fetch")
        if commit:
            db.commit()
        return

    # No valid default exists. Clear is_default on all keys for this candidate
    db.query(CandidateLlmApiKeyORM).filter(
        CandidateLlmApiKeyORM.candidate_id == candidate_id
    ).update({CandidateLlmApiKeyORM.is_default: False}, synchronize_session="fetch")

    # Find the newest/first active key to promote
    rows = _keys_for_candidate_id(db, candidate_id)
    active_rows = [r for r in rows if getattr(r, "status", "inactive") == "active"]
    if active_rows:
        active_rows[0].is_default = True
        if commit:
            db.commit()


def _default_llm_key_row(
    db: Session,
    candidate_id: int,
) -> Optional[CandidateLlmApiKeyORM]:
    """Row marked default in the database with active status."""
    if _llm_has_column(db, "is_default"):
        return (
            db.query(CandidateLlmApiKeyORM)
            .filter(
                CandidateLlmApiKeyORM.candidate_id == candidate_id,
                CandidateLlmApiKeyORM.is_default.is_(True),
                CandidateLlmApiKeyORM.status == "active",
            )
            .order_by(CandidateLlmApiKeyORM.id.desc())
            .first()
        )
    return None


def _openai_key_for_candidate_id(db: Session, candidate_id: int) -> Optional[str]:
    """Default My LLM key when OpenAI, else latest OpenAI row."""
    ensure_default_llm_key_for_candidate(db, candidate_id, commit=True)
    default_row = _default_llm_key_row(db, candidate_id)
    if default_row and _provider_is_openai(default_row.provider_name):
        secret = _row_secret(default_row)
        if secret:
            return secret
    r = (
        db.query(CandidateLlmApiKeyORM)
        .filter(
            CandidateLlmApiKeyORM.candidate_id == candidate_id,
            func.lower(CandidateLlmApiKeyORM.provider_name) == "openai",
        )
        .order_by(CandidateLlmApiKeyORM.id.desc())
        .first()
    )
    if not r:
        return None
    return _row_secret(r)


def mask_openai_api_key(secret: str) -> str:
    """Short masked hint (never returns full key)."""
    s = (secret or "").strip()
    if not s:
        return ""
    return "••••••••••••••••"


def openai_key_db_preview_for_user(
    db: Session,
    current_user: AuthUserORM,
) -> tuple[bool, Optional[str], Optional[int]]:
    """Whether an OpenAI key row exists for ``candidate.id``, masked hint, and row id."""
    uname = (getattr(current_user, "uname", None) or "").strip()
    if not uname:
        return False, None, None
    cand = fetch_candidate_id_and_status_by_email(db, uname)
    if not cand or cand.candidateid is None:
        return False, None, None
    candidate_id = int(cand.candidateid)
    ensure_default_llm_key_for_candidate(db, candidate_id, commit=True)
    default_row = _default_llm_key_row(db, candidate_id)
    r = default_row
    if r and not _provider_is_openai(r.provider_name):
        r = (
            db.query(CandidateLlmApiKeyORM)
            .filter(
                CandidateLlmApiKeyORM.candidate_id == candidate_id,
                func.lower(CandidateLlmApiKeyORM.provider_name) == "openai",
            )
            .order_by(CandidateLlmApiKeyORM.id.desc())
            .first()
        )
    if not r:
        return False, None, None
    secret = _row_secret(r)
    if not secret:
        return False, None, None
    return True, mask_openai_api_key(secret), int(r.id)


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


def _voice_enabled_by_provider_from_api_keys(
    db: Session,
    candidate_id: int,
) -> Dict[str, bool]:
    """``candidate_api_keys.voice_enabled`` keyed by lowercased provider name."""
    try:
        # candidate_api_keys has no ORM model; all values are parameterized (safe). # nosec B608
        rows = db.execute(
            text(
                """
                SELECT LOWER(provider_name) AS p, voice_enabled
                FROM candidate_api_keys
                WHERE candidate_id = :cid
                """
            ),
            {"cid": candidate_id},
        ).fetchall()
        return {str(r[0]): bool(r[1]) for r in rows if r[0]}
    except Exception:
        return {}


def _resolve_voice_enabled(
    row: CandidateLlmApiKeyORM,
    api_keys_voice: Dict[str, bool],
) -> bool:
    """Speech flag from ``candidate_api_keys.voice_enabled``, else ``candidate_llm_api_keys``."""
    p = (row.provider_name or "").strip().lower()
    if p in api_keys_voice:
        return api_keys_voice[p]
    return bool(row.voice_enabled)


def _llm_key_db_columns(db: Session) -> set[str]:
    """Cached set of physical columns on ``candidate_llm_api_keys``."""
    cached = db.info.get("llm_key_columns")
    if cached is not None:
        return cached

    # SQLite inspection for test environments
    if db.bind and db.bind.dialect.name == "sqlite":
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.connection())
            cached = {c["name"].lower() for c in inspector.get_columns("candidate_llm_api_keys")}
            db.info["llm_key_columns"] = cached
            return cached
        except Exception:
            pass

    try:
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(db.get_bind())
        cached = {c["name"].lower() for c in inspector.get_columns("candidate_llm_api_keys")}
    except Exception:
        cached = {
            "id",
            "candidate_id",
            "provider_name",
            "api_key",
            "model_name",
            "voice_enabled",
            "created_at",
            "is_default",
            "status",
            "failure_reason",
            "failure_code",
            "last_validated_at",
        }
    db.info["llm_key_columns"] = cached
    return cached


def _llm_has_column(db: Session, column_name: str) -> bool:
    return column_name.lower() in _llm_key_db_columns(db)


def _default_flags_for_keys(
    db: Session,
    candidate_id: int,
    key_ids: List[int],
) -> Dict[int, bool]:
    if not key_ids:
        return {}
    if not _llm_has_column(db, "is_default"):
        return {key_ids[0]: True} if key_ids else {}
    try:
        wanted = {int(i) for i in key_ids}
        rows = (
            db.query(CandidateLlmApiKeyORM.id, CandidateLlmApiKeyORM.is_default)
            .filter(
                CandidateLlmApiKeyORM.candidate_id == candidate_id,
                CandidateLlmApiKeyORM.id.in_(wanted),
            )
            .all()
        )
        return {int(r.id): bool(r.is_default) for r in rows}
    except Exception:
        return {}


def _has_default_key(db: Session, candidate_id: int) -> bool:
    if not _llm_has_column(db, "is_default"):
        return False
    try:
        exists = (
            db.query(CandidateLlmApiKeyORM.id)
            .filter(
                CandidateLlmApiKeyORM.candidate_id == candidate_id,
                CandidateLlmApiKeyORM.is_default.is_(True),
            )
            .first()
        )
        return exists is not None
    except Exception:
        return False


def _set_default_key_for_candidate(
    db: Session,
    candidate_id: int,
    key_id: int,
) -> None:
    """Mark one row as default and clear default on all other keys for this candidate."""
    if not _llm_has_column(db, "is_default"):
        return
    try:
        db.query(CandidateLlmApiKeyORM).filter(
            CandidateLlmApiKeyORM.candidate_id == candidate_id,
            CandidateLlmApiKeyORM.id != key_id,
        ).update({CandidateLlmApiKeyORM.is_default: False}, synchronize_session="fetch")
        db.query(CandidateLlmApiKeyORM).filter(
            CandidateLlmApiKeyORM.candidate_id == candidate_id,
            CandidateLlmApiKeyORM.id == key_id,
        ).update({CandidateLlmApiKeyORM.is_default: True}, synchronize_session="fetch")
        db.flush()
    except Exception:
        pass


def _is_key_default(db: Session, candidate_id: int, key_id: int) -> bool:
    rows = _keys_for_candidate_id(db, candidate_id)
    if len(rows) == 1:
        return int(rows[0].id) == key_id
    if not _llm_has_column(db, "is_default"):
        return False
    try:
        row = (
            db.query(CandidateLlmApiKeyORM.is_default)
            .filter(
                CandidateLlmApiKeyORM.candidate_id == candidate_id,
                CandidateLlmApiKeyORM.id == key_id,
            )
            .first()
        )
        return bool(row.is_default) if row else False
    except Exception:
        return False


def _ensure_candidate_has_default_key(db: Session, candidate_id: int) -> None:
    """If no default is set, promote the newest key (used after delete)."""
    ensure_default_llm_key_for_candidate(db, candidate_id, commit=False)


def _sync_voice_enabled_to_api_keys(
    db: Session,
    candidate_id: int,
    provider_name: str,
    voice_enabled: bool,
) -> None:
    """Keep ``candidate_api_keys.voice_enabled`` aligned when that row exists."""
    p = (provider_name or "OpenAI").strip()
    try:
        # candidate_api_keys has no ORM model; all values are parameterized (safe). # nosec B608
        db.execute(
            text(
                """
                UPDATE candidate_api_keys
                SET voice_enabled = :ve
                WHERE candidate_id = :cid
                  AND LOWER(provider_name) = LOWER(:p)
                """
            ),
            {"ve": bool(voice_enabled), "cid": candidate_id, "p": p},
        )
    except Exception:
        pass


from fapi.utils.llm_providers import normalize_llm_provider_name, _default_model_for_provider


def _find_key_row_for_provider(
    db: Session,
    candidate_id: int,
    provider_name: str,
    *,
    exclude_key_id: Optional[int] = None,
) -> Optional[CandidateLlmApiKeyORM]:
    """Latest row for this candidate + provider (canonical name), optionally excluding one id."""
    provider = normalize_llm_provider_name(provider_name)
    q = db.query(CandidateLlmApiKeyORM).filter(
        CandidateLlmApiKeyORM.candidate_id == candidate_id,
        func.lower(CandidateLlmApiKeyORM.provider_name) == provider.lower(),
    )
    if exclude_key_id is not None:
        q = q.filter(CandidateLlmApiKeyORM.id != exclude_key_id)
    return q.order_by(CandidateLlmApiKeyORM.id.desc()).first()


def create_candidate_llm_key_to_db(
    db: Session,
    current_user: AuthUserORM,
    provider_name: str,
    api_key: str,
    model_name: Optional[str] = None,
    voice_enabled: bool = False,
    status: Optional[str] = "inactive",
) -> int:
    """Insert a new LLM key row (never deletes or replaces existing keys)."""
    key = (api_key or "").strip()
    if not key:
        raise ValueError("API key is required")
    provider = normalize_llm_provider_name(provider_name)
    candidate_id = _candidate_id_for_user(db, current_user)
    m = (model_name or _default_model_for_provider(provider)).strip()
    ve = bool(voice_enabled)
    encrypted_key = encrypt_api_key(key)

    # Resolve actual status to write
    status_val = (status or "inactive").strip().lower()
    failure_reason = None

    if status_val == "active":
        # Enforce server-side re-validation
        from fapi.utils.llm_providers import get_adapter
        adapter = get_adapter(provider)
        if adapter:
            v_status, message = adapter.validate_key(key)
        else:
            v_status, message = "inactive", "Validation not supported"

        if v_status != "active":
            if v_status == "credits_exhausted":
                raise ValueError("Your API key is valid, but there are no available credits or quota. Please add credits and validate the key again.")
            elif v_status == "invalid":
                raise ValueError("Invalid API key. Please enter a valid API key.")
            else:
                raise ValueError(message or "API key validation failed. Please try again.")
        status_val = "active"
    elif status_val in ("invalid", "credits_exhausted"):
        status_val = status_val
        failure_reason = "Pre-validated as " + status_val
    else:
        status_val = "inactive"

    # Unvalidated or invalid keys cannot be marked default automatically.
    # Only ACTIVE keys can be default.
    make_default = False
    if status_val == "active":
        has_active_default = (
            db.query(CandidateLlmApiKeyORM)
            .filter(
                CandidateLlmApiKeyORM.candidate_id == candidate_id,
                CandidateLlmApiKeyORM.is_default == True,
                CandidateLlmApiKeyORM.status == "active",
            )
            .first()
            is not None
        )
        make_default = not has_active_default

    row_kwargs: Dict[str, Any] = {
        "candidate_id": candidate_id,
        "provider_name": provider,
        "api_key": encrypted_key,
        "model_name": m,
        "status": status_val,
        "failure_reason": failure_reason,
        "last_validated_at": datetime.now(timezone.utc) if status_val != "inactive" else None,
    }
    if _llm_has_column(db, "voice_enabled"):
        row_kwargs["voice_enabled"] = ve
    if _llm_has_column(db, "created_at"):
        row_kwargs["created_at"] = datetime.now(timezone.utc)
    if _llm_has_column(db, "is_default"):
        row_kwargs["is_default"] = make_default
    row = CandidateLlmApiKeyORM(**row_kwargs)
    db.add(row)
    db.flush()
    row_id = int(row.id)
    _sync_voice_enabled_to_api_keys(db, candidate_id, provider, ve)
    db.commit()

    if make_default:
        _set_default_key_for_candidate(db, candidate_id, row_id)
        db.commit()

    return row_id


def update_candidate_llm_key_to_db(
    db: Session,
    current_user: AuthUserORM,
    key_id: int,
    provider_name: str,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    voice_enabled: bool = False,
    status: Optional[str] = "inactive",
) -> None:
    """Update an existing LLM key row (API key optional — keeps current when omitted)."""
    provider = normalize_llm_provider_name(provider_name)
    candidate_id = _candidate_id_for_user(db, current_user)
    r = (
        db.query(CandidateLlmApiKeyORM)
        .filter(
            CandidateLlmApiKeyORM.id == key_id,
            CandidateLlmApiKeyORM.candidate_id == candidate_id,
        )
        .first()
    )
    if not r:
        raise LookupError("Key not found")
    
    key = (api_key or "").strip()
    status_updated = False
    
    if key:
        r.api_key = encrypt_api_key(key)
        status_val = (status or "inactive").strip().lower()
        failure_reason = None

        if status_val == "active":
            from fapi.utils.llm_providers import get_adapter
            adapter = get_adapter(provider)
            if adapter:
                v_status, message = adapter.validate_key(key)
            else:
                v_status, message = "inactive", "Validation not supported"

            if v_status != "active":
                if v_status == "credits_exhausted":
                    raise ValueError("Your API key is valid, but there are no available credits or quota. Please add credits and validate the key again.")
                elif v_status == "invalid":
                    raise ValueError("Invalid API key. Please enter a valid API key.")
                else:
                    raise ValueError(message or "API key validation failed. Please try again.")
            status_val = "active"
        elif status_val in ("invalid", "credits_exhausted"):
            status_val = status_val
            failure_reason = "Pre-validated as " + status_val
        else:
            status_val = "inactive"

        if r.status != status_val:
            r.status = status_val
            status_updated = True
        r.failure_reason = failure_reason
        r.last_validated_at = datetime.now(timezone.utc) if status_val != "inactive" else None
        
        # If the key is updated to inactive/invalid, it can no longer be default
        if status_val != "active":
            r.is_default = False
    elif not _row_secret(r):
        raise ValueError("API key is required")
    elif status is not None:
        status_val = status.strip().lower()
        if status_val not in ("active", "inactive", "invalid", "credits_exhausted"):
            status_val = "inactive"
        if r.status != status_val:
            r.status = status_val
            status_updated = True
            if status_val != "active":
                r.is_default = False

    r.provider_name = provider
    r.model_name = (model_name or r.model_name or _default_model_for_provider(provider)).strip()
    if _llm_has_column(db, "voice_enabled"):
        r.voice_enabled = bool(voice_enabled)

    _sync_voice_enabled_to_api_keys(db, candidate_id, provider, bool(voice_enabled))
    db.commit()

    if status_updated and r.status == "active":
        # Check if there is currently a working active default key
        has_active_default = (
            db.query(CandidateLlmApiKeyORM)
            .filter(
                CandidateLlmApiKeyORM.candidate_id == candidate_id,
                CandidateLlmApiKeyORM.is_default == True,
                CandidateLlmApiKeyORM.status == "active",
                CandidateLlmApiKeyORM.id != key_id
            )
            .first()
            is not None
        )
        if not has_active_default:
            _set_default_key_for_candidate(db, candidate_id, key_id)
            db.commit()
    elif status_updated and r.status != "active":
        # If it was default, clear it and try to promote the next active key
        _ensure_candidate_has_default_key(db, candidate_id)
        db.commit()


def save_candidate_openai_key_to_db(
    db: Session,
    current_user: AuthUserORM,
    api_key: str,
    model_name: Optional[str] = None,
    voice_enabled: bool = False,
) -> None:
    """Legacy OpenAI save: update the latest OpenAI row in place, or insert if none (no deletes)."""
    key = (api_key or "").strip()
    if not key:
        raise ValueError("API key is required")
    candidate_id = _candidate_id_for_user(db, current_user)
    existing = _find_key_row_for_provider(db, candidate_id, "OpenAI")
    if existing:
        update_candidate_llm_key_to_db(
            db,
            current_user,
            int(existing.id),
            "OpenAI",
            key,
            model_name,
            voice_enabled,
        )
    else:
        create_candidate_llm_key_to_db(
            db,
            current_user,
            "OpenAI",
            key,
            model_name,
            voice_enabled,
        )


def _candidate_id_for_user(db: Session, current_user: AuthUserORM) -> int:
    uname = (getattr(current_user, "uname", None) or "").strip()
    if not uname:
        raise LookupError("User session has no username")
    row = fetch_candidate_id_and_status_by_email(db, uname)
    if not row or row.candidateid is None:
        raise LookupError("No candidate profile linked to this account")
    return int(row.candidateid)


def _plaintext_api_key(raw: str) -> str:
    """Return usable API key text (plain or decrypted from Fernet storage)."""
    s = (raw or "").strip()
    if not s:
        return ""
    if s.startswith(("sk-", "sk-ant-", "sk-proj-", "AIzaSy")):
        return s
    dec = decrypt_api_key(s)
    if dec and dec != "DECRYPTION_FAILED":
        return dec.strip()
    return s


def _row_secret(row: CandidateLlmApiKeyORM) -> Optional[str]:
    if row.api_key is None:
        return None
    s = _plaintext_api_key(str(row.api_key))
    return s or None


def get_stored_key_for_candidate_provider(
    db: Session,
    candidate_id: int,
    provider_name: str,
) -> Optional[str]:
    p = (provider_name or "").strip().lower()
    r = (
        db.query(CandidateLlmApiKeyORM)
        .filter(
            CandidateLlmApiKeyORM.candidate_id == candidate_id,
            func.lower(CandidateLlmApiKeyORM.provider_name) == p,
        )
        .order_by(CandidateLlmApiKeyORM.id.desc())
        .first()
    )
    if not r:
        return None
    return _row_secret(r)


def get_stored_key_for_validation(
    db: Session,
    candidate_id: int,
    key_id: int,
    provider_name: str,
) -> Optional[str]:
    """Resolve secret from ``candidate_llm_api_keys`` by id, then provider name."""
    if key_id > 0:
        r = (
            db.query(CandidateLlmApiKeyORM)
            .filter(
                CandidateLlmApiKeyORM.id == key_id,
                CandidateLlmApiKeyORM.candidate_id == candidate_id,
            )
            .first()
        )
        if r:
            secret = _row_secret(r)
            if secret:
                return secret
    return get_stored_key_for_candidate_provider(db, candidate_id, provider_name)


def list_candidate_llm_keys_for_user(
    db: Session,
    current_user: AuthUserORM,
) -> List[Dict[str, Any]]:
    """
    Masked rows from ``candidate_llm_api_keys`` where ``candidate_id`` matches
    ``candidate.id`` for the authenticated user's email (``authuser.uname``).
    """
    candidate_id = _candidate_id_for_user(db, current_user)
    api_keys_voice = _voice_enabled_by_provider_from_api_keys(db, candidate_id)
    ensure_default_llm_key_for_candidate(db, candidate_id, commit=True)
    rows = _keys_for_candidate_id(db, candidate_id)
    key_ids = [int(r.id) for r in rows]
    if _llm_has_column(db, "is_default"):
        default_by_id = {int(r.id): bool(r.is_default) for r in rows}
    elif rows and len(rows) == 1:
        default_by_id = {key_ids[0]: True}
    else:
        default_by_id = _default_flags_for_keys(db, candidate_id, key_ids)

    out: List[Dict[str, Any]] = []
    for r in rows:
        secret = _row_secret(r)
        masked = mask_openai_api_key(secret) if secret else ""
        entry = getattr(r, "created_at", None)
        rid = int(r.id)
        out.append(
            {
                "id": rid,
                "provider_name": str(r.provider_name or "Unknown"),
                "masked_key": masked or "••••••••••••••••",
                "model_name": r.model_name,
                "entry_date": entry,
                "voice_enabled": _resolve_voice_enabled(r, api_keys_voice),
                "is_default": bool(default_by_id.get(rid, False)),
                "status": getattr(r, "status", "inactive") or "inactive",
                "validation_message": getattr(r, "failure_reason", None),
            }
        )
    return out


def reveal_candidate_llm_key_by_id(
    db: Session,
    current_user: AuthUserORM,
    key_id: int,
) -> str:
    candidate_id = _candidate_id_for_user(db, current_user)
    r = (
        db.query(CandidateLlmApiKeyORM)
        .filter(
            CandidateLlmApiKeyORM.id == key_id,
            CandidateLlmApiKeyORM.candidate_id == candidate_id,
        )
        .first()
    )
    if not r:
        raise LookupError("Key not found")
    secret = _row_secret(r)
    if not secret:
        raise LookupError("Key not found")
    return secret


def update_candidate_llm_key_voice_enabled(
    db: Session,
    current_user: AuthUserORM,
    key_id: int,
    voice_enabled: bool,
) -> None:
    """Update ``voice_enabled`` on ``candidate_llm_api_keys`` and sync ``candidate_api_keys``."""
    candidate_id = _candidate_id_for_user(db, current_user)
    r = (
        db.query(CandidateLlmApiKeyORM)
        .filter(
            CandidateLlmApiKeyORM.id == key_id,
            CandidateLlmApiKeyORM.candidate_id == candidate_id,
        )
        .first()
    )
    if not r:
        raise LookupError("Key not found")
    ve = bool(voice_enabled)
    if _llm_has_column(db, "voice_enabled"):
        r.voice_enabled = ve
    _sync_voice_enabled_to_api_keys(db, candidate_id, r.provider_name or "OpenAI", ve)
    db.commit()


def update_candidate_llm_key_is_default(
    db: Session,
    current_user: AuthUserORM,
    key_id: int,
    is_default: bool,
) -> None:
    candidate_id = _candidate_id_for_user(db, current_user)
    r = (
        db.query(CandidateLlmApiKeyORM)
        .filter(
            CandidateLlmApiKeyORM.id == key_id,
            CandidateLlmApiKeyORM.candidate_id == candidate_id,
        )
        .first()
    )
    if not r:
        raise LookupError("Key not found")
    if is_default:
        _set_default_key_for_candidate(db, candidate_id, key_id)
    elif _is_key_default(db, candidate_id, key_id):
        raise ValueError(
            "Cannot unset the default key. Set another key as default first."
        )
    db.commit()


def delete_candidate_llm_key_for_user(
    db: Session,
    current_user: AuthUserORM,
    key_id: int,
) -> None:
    candidate_id = _candidate_id_for_user(db, current_user)
    r = (
        db.query(CandidateLlmApiKeyORM)
        .filter(
            CandidateLlmApiKeyORM.id == key_id,
            CandidateLlmApiKeyORM.candidate_id == candidate_id,
        )
        .first()
    )
    if not r:
        raise LookupError("Key not found")
    db.delete(r)
    db.flush()
    ensure_default_llm_key_for_candidate(db, candidate_id, commit=False)
    db.commit()


def validate_llm_key_batch_for_user(
    db: Session,
    current_user: AuthUserORM,
    keys: List[Dict[str, Any]],
    session_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    from fapi.utils.llm_providers import get_adapter

    del session_id  # unused; validation reads from DB
    candidate_id = _candidate_id_for_user(db, current_user)
    results: List[Dict[str, Any]] = []
    for item in keys:
        key_id = int(item.get("id", 0))
        provider = str(item.get("provider_name") or "")
        source = str(item.get("source") or "wbl").lower()
        raw = get_stored_key_for_validation(db, candidate_id, key_id, provider)
        if not raw:
            status, message = "inactive", "Key not found"
        else:
            adapter = get_adapter(provider)
            if adapter:
                status, message = adapter.validate_key(raw)
            else:
                from fapi.utils.llm_key_validation_utils import validate_provider_key
                status, message = validate_provider_key(provider, raw)
            
            # Save to database
            if key_id > 0:
                r = (
                    db.query(CandidateLlmApiKeyORM)
                    .filter(
                        CandidateLlmApiKeyORM.id == key_id,
                        CandidateLlmApiKeyORM.candidate_id == candidate_id,
                    )
                    .first()
                )
                print(f"DEBUG: key_id={key_id}, candidate_id={candidate_id}, r_found={r is not None}", flush=True)
                if r:
                    print(f"DEBUG: updating r.status from {r.status} to {status}", flush=True)
                    r.status = status
                    r.failure_reason = message if status != "active" else None
                    r.failure_code = "CREDITS_EXHAUSTED" if status == "credits_exhausted" else ("INVALID_KEY" if status == "invalid" else None)
                    r.last_validated_at = datetime.now(timezone.utc)
                    if status != "active":
                        r.is_default = False
                    print(f"DEBUG: before flush, is_modified={db.is_modified(r)}, dirty={db.dirty}", flush=True)
                    db.flush()
                    print(f"DEBUG: after flush, is_modified={db.is_modified(r)}, dirty={db.dirty}", flush=True)

            # Automatic promoter on recovery:
            if status == "active":
                has_active_default = (
                    db.query(CandidateLlmApiKeyORM)
                    .filter(
                        CandidateLlmApiKeyORM.candidate_id == candidate_id,
                        CandidateLlmApiKeyORM.is_default == True,
                        CandidateLlmApiKeyORM.status == "active",
                    )
                    .first()
                    is not None
                )
                if not has_active_default:
                    _set_default_key_for_candidate(db, candidate_id, key_id)
                    db.flush()

        results.append(
            {
                "id": key_id,
                "source": source,
                "status": status,
                "message": message,
            }
        )
    db.commit()
    db_check = db.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.id == key_id).first() if key_id > 0 else None
    if db_check:
        print(f"DEBUG: right after commit, status in DB is {db_check.status}", flush=True)
    return results


def finish_setup_for_user(
    db: Session,
    current_user: AuthUserORM,
) -> Dict[str, Any]:
    from fapi.utils.llm_key_validation_utils import validate_provider_key
    candidate_id = _candidate_id_for_user(db, current_user)
    ensure_default_llm_key_for_candidate(db, candidate_id, commit=True)
    default_row = _default_llm_key_row(db, candidate_id)
    
    if not default_row:
        return {"setup_complete": False, "error": "NO_USABLE_LLM_KEY"}
    
    secret = _row_secret(default_row)
    if not secret:
        return {"setup_complete": False, "error": "NO_USABLE_LLM_KEY"}
        
    status, message = validate_provider_key(default_row.provider_name or "", secret)
    
    if status == "active":
        return {"setup_complete": True}
    else:
        return {"setup_complete": False, "error": "NO_USABLE_LLM_KEY"}
