"""
Stream Manager — Real-time In-Memory Event Streaming for AI Prep Assessments.

Provides strict, thread-safe, reactive push-based Server-Sent Events (SSE)
streaming without database polling loops.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class AssessmentStreamManager:
    """
    In-memory PubSub manager for assessment real-time SSE progress events.
    Thread-safe: marshals cross-thread event dispatches back onto the event
    loop thread via call_soon_threadsafe.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[int, Set[asyncio.Queue]] = {}
        self._latest_snapshots: Dict[int, Dict[str, Any]] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_loop(self) -> Optional[asyncio.AbstractEventLoop]:
        """Resolves and caches the running event loop."""
        if self._loop and not self._loop.is_closed():
            return self._loop
        try:
            self._loop = asyncio.get_running_loop()
            return self._loop
        except RuntimeError:
            return None

    def subscribe(self, assessment_id: int) -> Tuple[asyncio.Queue, Optional[Dict[str, Any]]]:
        """
        Registers a new client subscriber queue for a given assessment.
        Must be called from the asyncio event loop thread.
        Returns the new queue and any existing snapshot.
        """
        # Capture the active event loop if not yet stored
        self._get_loop()

        queue: asyncio.Queue = asyncio.Queue()
        if assessment_id not in self._subscribers:
            self._subscribers[assessment_id] = set()
        self._subscribers[assessment_id].add(queue)

        latest = self._latest_snapshots.get(assessment_id)
        return queue, latest

    def unsubscribe(self, assessment_id: int, queue: asyncio.Queue) -> None:
        """Removes a client queue and purges empty subscriber sets."""
        if assessment_id in self._subscribers:
            self._subscribers[assessment_id].discard(queue)
            if not self._subscribers[assessment_id]:
                self._subscribers.pop(assessment_id, None)

    def publish_progress(
        self,
        assessment_id: int,
        status: str,
        step: str,
        progress: int,
        error: Optional[str] = None,
    ) -> None:
        """
        Publishes a real-time progress update to all connected SSE clients.
        Fully thread-safe: can be called from async tasks or worker threads (to_thread/run_in_executor).
        """
        payload: Dict[str, Any] = {
            "status": status,
            "step": step,
            "progress": int(progress),
        }
        if error:
            payload["error"] = str(error)

        loop = self._get_loop()
        if loop and not loop.is_closed():
            # Cross-thread guarantee: marshal execution onto the event loop thread
            loop.call_soon_threadsafe(self._apply, assessment_id, payload)
        else:
            # Fallback for synchronous test execution where no event loop is active
            self._apply(assessment_id, payload)

    def _apply(self, assessment_id: int, payload: Dict[str, Any]) -> None:
        """
        Mutates state, updates latest snapshot, dispatches to subscriber queues,
        and schedules TTL purge. Strictly executed on the loop thread.
        """
        self._latest_snapshots[assessment_id] = payload

        subscribers = self._subscribers.get(assessment_id)
        if subscribers:
            for q in list(subscribers):
                try:
                    q.put_nowait(payload)
                except Exception as exc:
                    logger.debug("Failed to dispatch SSE event to queue for %s: %s", assessment_id, exc)

        # Schedule TTL purge on terminal states via call_later (avoids task GC risks)
        if payload.get("status") in ("COMPLETED", "FAILED", "CANCELLED"):
            loop = self._get_loop()
            if loop and not loop.is_closed():
                loop.call_later(60.0, self._purge_snapshot, assessment_id, payload)

    def _purge_snapshot(self, assessment_id: int, expected_payload: Dict[str, Any]) -> None:
        """
        Purges snapshot only if it strictly matches the exact instance scheduled.
        Prevents race conditions if a retried assessment published a new evaluation snapshot.
        """
        if self._latest_snapshots.get(assessment_id) is expected_payload:
            self._latest_snapshots.pop(assessment_id, None)


# Global singleton instance
stream_manager = AssessmentStreamManager()
