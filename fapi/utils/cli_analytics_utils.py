"""WboxCLI usage analytics persistence and reporting."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from fapi.db.models import CliUsageEventORM, WboxcliApplyAnalyticsORM
from fapi.db.schemas import (
    CliApplyRunJobOut,
    CliApplyRunLatestOut,
    CliUsageEventBulkResponse,
    CliUsageEventIn,
    CliUsageAnalyticsSummary,
    CliUsageUserSummary,
    CliUsageUserRow,
    CliUsageUserMetricsUpdate,
    CliUsageUserMutationResponse,
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


def _counts_from_apply_event(row: Optional[CliUsageEventORM]) -> tuple[int, int, int]:
    """Job counters from one apply usage event (columns or apply_run_log.summary)."""
    if row is None:
        return 0, 0, 0
    if (
        row.jobs_attempted_count is not None
        or row.jobs_submitted_count is not None
        or row.jobs_failed_count is not None
    ):
        return (
            int(row.jobs_attempted_count or 0),
            int(row.jobs_submitted_count or 0),
            int(row.jobs_failed_count or 0),
        )
    meta = row.event_metadata if isinstance(row.event_metadata, dict) else {}
    run_log = meta.get("apply_run_log") or meta.get("apply_summary") or {}
    summary = run_log.get("summary") if isinstance(run_log, dict) else {}
    if isinstance(summary, dict):
        return (
            int(summary.get("jobs_attempted") or 0),
            int(summary.get("jobs_submitted") or 0),
            int(summary.get("jobs_failed") or 0),
        )
    return 0, 0, 0


def _latest_apply_events_query(db: Session, user_ids: Optional[List[str]] = None):
    """One row per user: their most recent ``command=apply`` event."""
    latest_ts_q = (
        db.query(
            CliUsageEventORM.user_id.label("user_id"),
            func.max(CliUsageEventORM.event_ts).label("max_ts"),
        )
        .filter(CliUsageEventORM.command == "apply")
    )
    if user_ids:
        latest_ts_q = latest_ts_q.filter(CliUsageEventORM.user_id.in_(user_ids))
    latest_ts = latest_ts_q.group_by(CliUsageEventORM.user_id).subquery("latest_apply_ts")
    return db.query(CliUsageEventORM).join(
        latest_ts,
        and_(
            CliUsageEventORM.user_id == latest_ts.c.user_id,
            CliUsageEventORM.event_ts == latest_ts.c.max_ts,
            CliUsageEventORM.command == "apply",
        ),
    )


def _apply_run_log_preview(run_log: dict[str, Any]) -> str:
    """Short grid label — full JSON is opened via View (eye) in the UI."""
    if not run_log:
        return "—"
    jobs = run_log.get("jobs")
    if isinstance(jobs, list) and len(jobs) > 0:
        return f"{len(jobs)} jobs"
    summary = run_log.get("summary") if isinstance(run_log.get("summary"), dict) else {}
    attempted = summary.get("jobs_attempted")
    if attempted is not None:
        return f"{int(attempted)} jobs (summary)"
    return "Log available"


def _build_cli_usage_user_row(
    *,
    user_id: str,
    jobs_attempted: int,
    jobs_submitted: int,
    jobs_failed: int,
    last_event_at: Optional[datetime],
    result: Optional[str] = None,
    event: Optional[CliUsageEventORM] = None,
) -> CliUsageUserRow:
    run_log = _run_log_from_event(event) if event else {}
    return CliUsageUserRow(
        user_id=user_id,
        jobs_attempted=int(jobs_attempted or 0),
        jobs_submitted=int(jobs_submitted or 0),
        jobs_failed=int(jobs_failed or 0),
        last_event_at=last_event_at,
        result=(result or (event.result if event else None)),
        apply_run_log=run_log if run_log else None,
        apply_run_log_preview=_apply_run_log_preview(run_log),
        apply_log_history=[],
    )


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass
    return None


def _extract_apply_run_log(
    item: CliUsageEventIn,
    event_row: CliUsageEventORM,
) -> dict[str, Any]:
    meta = item.metadata if isinstance(item.metadata, dict) else {}
    if not meta and isinstance(event_row.event_metadata, dict):
        meta = event_row.event_metadata
    run_log = meta.get("apply_run_log")
    return run_log if isinstance(run_log, dict) else {}


def _run_log_from_event(event: Optional[CliUsageEventORM]) -> dict[str, Any]:
    if event is None:
        return {}
    meta = event.event_metadata if isinstance(event.event_metadata, dict) else {}
    run_log = meta.get("apply_run_log") or meta.get("apply_summary") or {}
    return run_log if isinstance(run_log, dict) else {}


def _normalize_apply_run_jobs(run_log: dict[str, Any]) -> List[CliApplyRunJobOut]:
    jobs = run_log.get("jobs")
    if not isinstance(jobs, list):
        return []
    out: List[CliApplyRunJobOut] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        app_log = job.get("application_log")
        line_count = len(app_log) if isinstance(app_log, list) else 0
        applied = job.get("applied_at")
        out.append(
            CliApplyRunJobOut(
                job_id=job.get("job_id"),
                title=(job.get("title") or None),
                company=(job.get("company") or None),
                url=(job.get("url") or None),
                status=str(job.get("status") or "") or None,
                applied_at=str(applied)[:50] if applied is not None else None,
                application_log_line_count=int(line_count),
            )
        )
    return out


def get_latest_apply_run_for_user(db: Session, user_id: str) -> Optional[CliApplyRunLatestOut]:
    """Latest apply_run_log for a WBL user (from linked usage event or newest apply)."""
    uid = (user_id or "").strip()
    if not uid:
        return None

    event: Optional[CliUsageEventORM] = None
    analytics = (
        db.query(WboxcliApplyAnalyticsORM).filter(WboxcliApplyAnalyticsORM.user_id == uid).first()
    )
    if analytics and analytics.usage_event_id:
        event = db.query(CliUsageEventORM).filter(CliUsageEventORM.id == analytics.usage_event_id).first()
    if event is None or (event.command or "").strip().lower() != "apply":
        event = (
            _latest_apply_events_query(db).filter(CliUsageEventORM.user_id == uid).first()
        )

    run_log = _run_log_from_event(event)
    if not run_log and event is not None:
        return None
    if not run_log:
        return None

    summary = run_log.get("summary")
    if not isinstance(summary, dict):
        summary = {}

    return CliApplyRunLatestOut(
        user_id=uid,
        run_started_at=str(run_log.get("run_started_at") or "") or None,
        run_ended_at=str(run_log.get("run_ended_at") or "") or None,
        result=str(run_log.get("result") or event.result if event else "") or None,
        summary=summary,
        jobs=_normalize_apply_run_jobs(run_log),
        apply_run_log=run_log,
    )


def upsert_apply_analytics_grid(
    db: Session,
    *,
    user_id: str,
    jobs_attempted: int,
    jobs_submitted: int,
    jobs_failed: int,
    last_activity: datetime,
    usage_event_id: Optional[int] = None,
    result: Optional[str] = None,
) -> WboxcliApplyAnalyticsORM:
    """Upsert one row in wboxcli_apply_analytics (matches AG Grid columns)."""
    uid = (user_id or "").strip()[:255] or "unknown_user"
    row = db.query(WboxcliApplyAnalyticsORM).filter(WboxcliApplyAnalyticsORM.user_id == uid).first()
    if row is None:
        row = WboxcliApplyAnalyticsORM(
            user_id=uid,
            jobs_attempted=int(jobs_attempted or 0),
            jobs_submitted=int(jobs_submitted or 0),
            jobs_failed=int(jobs_failed or 0),
            last_activity=last_activity,
            usage_event_id=usage_event_id,
            result=(result or "")[:50] or None,
        )
        db.add(row)
    elif last_activity >= row.last_activity:
        row.jobs_attempted = int(jobs_attempted or 0)
        row.jobs_submitted = int(jobs_submitted or 0)
        row.jobs_failed = int(jobs_failed or 0)
        row.last_activity = last_activity
        row.usage_event_id = usage_event_id
        row.result = (result or "")[:50] or None
    return row


def persist_apply_analytics_from_ingest(
    db: Session,
    event_row: CliUsageEventORM,
    item: CliUsageEventIn,
) -> None:
    """Write latest apply snapshot to wboxcli_apply_analytics for apply events."""
    if (item.command or event_row.command or "").strip().lower() != "apply":
        return
    run_log = _extract_apply_run_log(item, event_row)
    summary = run_log.get("summary") if isinstance(run_log.get("summary"), dict) else {}
    user_id = (item.user_id or event_row.user_id or "").strip()[:255] or "unknown_user"
    run_ended = _parse_iso_datetime(run_log.get("run_ended_at")) or event_row.event_ts
    result = (run_log.get("result") or item.result or event_row.result or "unknown").strip()[:50]
    jobs_attempted = int(
        summary.get("jobs_attempted")
        if summary.get("jobs_attempted") is not None
        else (item.jobs_attempted_count or event_row.jobs_attempted_count or 0)
    )
    jobs_submitted = int(
        summary.get("jobs_submitted")
        if summary.get("jobs_submitted") is not None
        else (item.jobs_submitted_count or event_row.jobs_submitted_count or 0)
    )
    jobs_failed = int(
        summary.get("jobs_failed")
        if summary.get("jobs_failed") is not None
        else (item.jobs_failed_count or event_row.jobs_failed_count or 0)
    )
    upsert_apply_analytics_grid(
        db,
        user_id=user_id,
        jobs_attempted=jobs_attempted,
        jobs_submitted=jobs_submitted,
        jobs_failed=jobs_failed,
        last_activity=run_ended,
        usage_event_id=event_row.id,
        result=result,
    )


def backfill_apply_analytics_from_events(db: Session, *, limit: Optional[int] = None) -> dict:
    """Populate wboxcli_apply_analytics from historical apply events."""
    q = (
        db.query(CliUsageEventORM)
        .filter(CliUsageEventORM.command == "apply")
        .order_by(CliUsageEventORM.event_ts.asc())
    )
    if limit:
        q = q.limit(limit)
    rows = q.all()
    updated = 0
    for row in rows:
        meta = row.event_metadata if isinstance(row.event_metadata, dict) else {}
        item = CliUsageEventIn(
            user_id=row.user_id,
            event_name=row.event_name,
            event_ts=row.event_ts,
            command=row.command,
            result=row.result,
            duration_ms=row.duration_ms,
            jobs_attempted_count=row.jobs_attempted_count,
            jobs_submitted_count=row.jobs_submitted_count,
            jobs_failed_count=row.jobs_failed_count,
            metadata=meta,
        )
        try:
            persist_apply_analytics_from_ingest(db, row, item)
            updated += 1
        except Exception as exc:
            logger.warning("Backfill skip event %s: %s", row.id, exc)
    db.commit()
    return {"updated": updated, "scanned": len(rows)}


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
            event_row = _event_from_input(item)
            db.add(event_row)
            db.flush()
            try:
                persist_apply_analytics_from_ingest(db, event_row, item)
            except Exception as persist_exc:
                logger.warning(
                    "Apply analytics persistence failed for user %s: %s",
                    item.user_id,
                    persist_exc,
                )
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
    analytics_rows = db.query(WboxcliApplyAnalyticsORM).all()
    if analytics_rows:
        total_jobs_attempted = sum(int(r.jobs_attempted or 0) for r in analytics_rows)
        total_jobs_submitted = sum(int(r.jobs_submitted or 0) for r in analytics_rows)
        total_jobs_failed = sum(int(r.jobs_failed or 0) for r in analytics_rows)
    else:
        latest_apply_rows = _latest_apply_events_query(db).all()
        total_jobs_attempted = 0
        total_jobs_submitted = 0
        total_jobs_failed = 0
        for row in latest_apply_rows:
            a, s, f = _counts_from_apply_event(row)
            total_jobs_attempted += a
            total_jobs_submitted += s
            total_jobs_failed += f

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
    latest_apply = (
        _latest_apply_events_query(db)
        .filter(CliUsageEventORM.user_id == user_id)
        .first()
    )
    jobs_attempted, jobs_submitted, jobs_failed = _counts_from_apply_event(latest_apply)
    return CliUsageUserSummary(
        user_id=user_id,
        events=len(rows),
        jobs_attempted=jobs_attempted,
        jobs_submitted=jobs_submitted,
        jobs_failed=jobs_failed,
        last_event_at=last_ts,
    )


def get_paginated_users(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
    user_id: Optional[str] = None,
) -> PaginatedCliUsageUsers:
    """One row per user from wboxcli_apply_analytics (same columns as AG Grid)."""
    page = max(1, page)
    page_size = max(1, min(page_size, 500))

    query = db.query(WboxcliApplyAnalyticsORM)
    if user_id:
        query = query.filter(WboxcliApplyAnalyticsORM.user_id.ilike(f"%{user_id.strip()}%"))

    total = query.count()
    analytics = (
        query.order_by(WboxcliApplyAnalyticsORM.last_activity.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    if analytics:
        event_ids = [int(r.usage_event_id) for r in analytics if r.usage_event_id]
        events_by_id: Dict[int, CliUsageEventORM] = {}
        if event_ids:
            for ev in db.query(CliUsageEventORM).filter(CliUsageEventORM.id.in_(event_ids)).all():
                events_by_id[int(ev.id)] = ev
        users = [
            _build_cli_usage_user_row(
                user_id=row.user_id,
                jobs_attempted=int(row.jobs_attempted or 0),
                jobs_submitted=int(row.jobs_submitted or 0),
                jobs_failed=int(row.jobs_failed or 0),
                last_event_at=row.last_activity,
                result=row.result,
                event=events_by_id.get(int(row.usage_event_id))
                if row.usage_event_id
                else None,
            )
            for row in analytics
        ]
        return PaginatedCliUsageUsers(
            total=int(total),
            page=page,
            page_size=page_size,
            users=users,
        )

    # Fallback before backfill / first apply ingest
    base = db.query(
        CliUsageEventORM.user_id.label("user_id"),
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
    page_user_ids = [row.user_id for row in rows]
    events_by_user: Dict[str, CliUsageEventORM] = {}
    if page_user_ids:
        for ev in _latest_apply_events_query(db, page_user_ids).all():
            events_by_user[ev.user_id] = ev
    users = []
    for row in rows:
        ev = events_by_user.get(row.user_id)
        attempted, submitted, failed = _counts_from_apply_event(ev)
        users.append(
            _build_cli_usage_user_row(
                user_id=row.user_id,
                jobs_attempted=attempted,
                jobs_submitted=submitted,
                jobs_failed=failed,
                last_event_at=row.last_event_at,
                event=ev,
            )
        )
    return PaginatedCliUsageUsers(
        total=int(total),
        page=page,
        page_size=page_size,
        users=users,
    )


def delete_user_usage_events(db: Session, user_id: str) -> CliUsageUserMutationResponse:
    """Delete all CLI usage events for a WBL login (admin cleanup)."""
    uid = (user_id or "").strip()
    if not uid:
        raise ValueError("user_id is required")
    db.query(WboxcliApplyAnalyticsORM).filter(WboxcliApplyAnalyticsORM.user_id == uid).delete(
        synchronize_session=False
    )
    deleted = (
        db.query(CliUsageEventORM)
        .filter(CliUsageEventORM.user_id == uid)
        .delete(synchronize_session=False)
    )
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("CLI usage delete failed for %s: %s", uid, exc)
        raise
    return CliUsageUserMutationResponse(user_id=uid, deleted_events=int(deleted or 0))


def update_user_usage_metrics(
    db: Session,
    user_id: str,
    body: CliUsageUserMetricsUpdate,
) -> CliUsageUserMutationResponse:
    """Adjust aggregated job counters by zeroing all events then setting the latest."""
    uid = (user_id or "").strip()
    if not uid:
        raise ValueError("user_id is required")
    rows = db.query(CliUsageEventORM).filter(CliUsageEventORM.user_id == uid).all()
    if not rows:
        raise LookupError(f"No usage events found for user_id={uid!r}")

    for row in rows:
        row.jobs_attempted_count = 0
        row.jobs_submitted_count = 0
        row.jobs_failed_count = 0

    latest = max(rows, key=lambda r: r.event_ts)
    latest.jobs_attempted_count = int(body.jobs_attempted)
    latest.jobs_submitted_count = int(body.jobs_submitted)
    latest.jobs_failed_count = int(body.jobs_failed)

    analytics = (
        db.query(WboxcliApplyAnalyticsORM).filter(WboxcliApplyAnalyticsORM.user_id == uid).first()
    )
    if analytics:
        analytics.jobs_attempted = int(body.jobs_attempted)
        analytics.jobs_submitted = int(body.jobs_submitted)
        analytics.jobs_failed = int(body.jobs_failed)

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("CLI usage metrics update failed for %s: %s", uid, exc)
        raise

    return CliUsageUserMutationResponse(
        user_id=uid,
        jobs_attempted=int(body.jobs_attempted),
        jobs_submitted=int(body.jobs_submitted),
        jobs_failed=int(body.jobs_failed),
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
