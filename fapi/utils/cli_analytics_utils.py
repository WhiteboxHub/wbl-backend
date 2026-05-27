"""WboxCLI usage analytics persistence and reporting."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from fapi.db.models import CliUsageEventORM
from fapi.db.schemas import (
    CliUsageEventBulkResponse,
    CliUsageEventIn,
    CliUsageAnalyticsSummary,
    CliUsageUserSummary,
    CliUsageUserRow,
    PaginatedCliUsageEvents,
    PaginatedCliUsageUsers,
    CliUsageEventOut,
)

logger = logging.getLogger(__name__)

_SENSITIVE_SUBSTRINGS = (
    "password",
    "token",
    "api_key",
    "resume",
    "secret",
)


def _parse_event_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass
    return datetime.utcnow()


def _sanitize_metadata(metadata: Optional[dict]) -> Optional[dict]:
    if not metadata or not isinstance(metadata, dict):
        return metadata
    return {
        k: v
        for k, v in metadata.items()
        if not any(s in k.lower() for s in _SENSITIVE_SUBSTRINGS)
    }


def _event_from_input(data: CliUsageEventIn) -> CliUsageEventORM:
    return CliUsageEventORM(
        user_id=(data.user_id or "").strip()[:255],
        event_name=(data.event_name or "").strip()[:100],
        command=(data.command or None),
        result=(data.result or None),
        event_ts=_parse_event_ts(data.event_ts),
        duration_ms=data.duration_ms,
        jobs_attempted_count=data.jobs_attempted_count,
        jobs_submitted_count=data.jobs_submitted_count,
        jobs_failed_count=data.jobs_failed_count,
        event_metadata=_sanitize_metadata(data.metadata),
    )


def insert_usage_events_bulk(
    db: Session,
    events: List[CliUsageEventIn],
) -> CliUsageEventBulkResponse:
    ingested = 0
    failed = 0
    failed_events: List[dict] = []

    for item in events:
        try:
            if not (item.user_id or "").strip() or not (item.event_name or "").strip():
                raise ValueError("user_id and event_name are required")
            db.add(_event_from_input(item))
            ingested += 1
            if ingested % 50 == 0:
                db.flush()
        except Exception as exc:
            failed += 1
            failed_events.append({"user_id": item.user_id, "reason": str(exc)})
            logger.warning("CLI usage event rejected: %s", exc)

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("CLI usage bulk commit failed: %s", exc)
        raise

    return CliUsageEventBulkResponse(
        ingested=ingested,
        failed=failed,
        total=len(events),
        failed_events=failed_events,
    )


def get_global_summary(db: Session) -> CliUsageAnalyticsSummary:
    since_7d = datetime.utcnow() - timedelta(days=7)
    total_events = db.query(func.count(CliUsageEventORM.id)).scalar() or 0
    total_users = db.query(func.count(func.distinct(CliUsageEventORM.user_id))).scalar() or 0
    active_users_7d = (
        db.query(func.count(func.distinct(CliUsageEventORM.user_id)))
        .filter(CliUsageEventORM.event_ts >= since_7d)
        .scalar()
        or 0
    )
    total_jobs_attempted = (
        db.query(func.coalesce(func.sum(CliUsageEventORM.jobs_attempted_count), 0)).scalar() or 0
    )
    total_jobs_submitted = (
        db.query(func.coalesce(func.sum(CliUsageEventORM.jobs_submitted_count), 0)).scalar() or 0
    )
    total_jobs_failed = (
        db.query(func.coalesce(func.sum(CliUsageEventORM.jobs_failed_count), 0)).scalar() or 0
    )

    command_rows = (
        db.query(CliUsageEventORM.command, func.count(CliUsageEventORM.id))
        .filter(CliUsageEventORM.command.isnot(None))
        .group_by(CliUsageEventORM.command)
        .all()
    )
    command_counts = {row[0]: int(row[1]) for row in command_rows if row[0]}

    return CliUsageAnalyticsSummary(
        total_events=int(total_events),
        total_users=int(total_users),
        active_users_7d=int(active_users_7d),
        total_jobs_attempted=int(total_jobs_attempted),
        total_jobs_submitted=int(total_jobs_submitted),
        total_jobs_failed=int(total_jobs_failed),
        command_counts=command_counts,
    )


def get_user_summary(db: Session, user_id: str) -> CliUsageUserSummary:
    rows = (
        db.query(CliUsageEventORM)
        .filter(CliUsageEventORM.user_id == user_id)
        .order_by(CliUsageEventORM.event_ts.desc())
        .all()
    )
    last_ts = rows[0].event_ts if rows else None
    return CliUsageUserSummary(
        user_id=user_id,
        events=len(rows),
        jobs_attempted=sum(int(r.jobs_attempted_count or 0) for r in rows),
        jobs_submitted=sum(int(r.jobs_submitted_count or 0) for r in rows),
        jobs_failed=sum(int(r.jobs_failed_count or 0) for r in rows),
        last_event_at=last_ts,
    )


def get_paginated_users(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
    user_id: Optional[str] = None,
) -> PaginatedCliUsageUsers:
    """Aggregate usage metrics to one row per user."""
    page = max(1, page)
    page_size = max(1, min(page_size, 500))

    base = db.query(
        CliUsageEventORM.user_id.label("user_id"),
        func.coalesce(func.sum(CliUsageEventORM.jobs_attempted_count), 0).label(
            "jobs_attempted"
        ),
        func.coalesce(func.sum(CliUsageEventORM.jobs_submitted_count), 0).label(
            "jobs_submitted"
        ),
        func.coalesce(func.sum(CliUsageEventORM.jobs_failed_count), 0).label(
            "jobs_failed"
        ),
        func.max(CliUsageEventORM.event_ts).label("last_event_at"),
    )
    if user_id:
        base = base.filter(CliUsageEventORM.user_id.ilike(f"%{user_id.strip()}%"))

    grouped = base.group_by(CliUsageEventORM.user_id).subquery()
    total = db.query(func.count()).select_from(grouped).scalar() or 0

    rows = (
        db.query(grouped)
        .order_by(grouped.c.last_event_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    user_ids = [row.user_id for row in rows]
    apply_history_by_user: Dict[str, List[dict]] = {uid: [] for uid in user_ids}
    if user_ids:
        apply_rows = (
            db.query(
                CliUsageEventORM.user_id,
                CliUsageEventORM.event_ts,
                CliUsageEventORM.event_metadata,
            )
            .filter(
                CliUsageEventORM.user_id.in_(user_ids),
                CliUsageEventORM.command == "apply",
            )
            .order_by(CliUsageEventORM.user_id.asc(), CliUsageEventORM.event_ts.asc())
            .all()
        )
        for uid, event_ts, meta in apply_rows:
            if not isinstance(meta, dict):
                continue
            entry = meta.get("apply_run_log")
            if not isinstance(entry, dict):
                entry = meta.get("apply_summary")
            if not isinstance(entry, dict):
                continue
            if "run_ended_at" not in entry and "timestamp" not in entry:
                entry = {
                    **entry,
                    "timestamp": entry.get("applied_at") or event_ts.isoformat(),
                }
            apply_history_by_user.setdefault(uid, []).append(entry)

    users: List[CliUsageUserRow] = []
    for row in rows:
        users.append(
            CliUsageUserRow(
                user_id=row.user_id,
                jobs_attempted=int(row.jobs_attempted or 0),
                jobs_submitted=int(row.jobs_submitted or 0),
                jobs_failed=int(row.jobs_failed or 0),
                last_event_at=row.last_event_at,
                apply_log_history=apply_history_by_user.get(row.user_id, []),
            )
        )

    return PaginatedCliUsageUsers(
        total=int(total),
        page=page,
        page_size=page_size,
        users=users,
    )


def get_paginated_events(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
    user_id: Optional[str] = None,
) -> PaginatedCliUsageEvents:
    page = max(1, page)
    page_size = max(1, min(page_size, 500))
    query = db.query(CliUsageEventORM)
    if user_id:
        query = query.filter(CliUsageEventORM.user_id == user_id)
    total = query.count()
    rows = (
        query.order_by(CliUsageEventORM.event_ts.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedCliUsageEvents(
        total=total,
        page=page,
        page_size=page_size,
        events=[CliUsageEventOut.model_validate(r) for r in rows],
    )
