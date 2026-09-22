"""
YouTube API Quota Manager
==========================
Thread-safe in-memory YouTube Data API v3 quota tracker and enforcement engine.
Tracks daily quota usage, estimates remaining capacity, and automatically resets
accounting when the quota period rolls over (midnight Pacific Time).
"""
import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from fapi.ai_prep.config import settings

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
    PT_TZ = ZoneInfo("America/Los_Angeles")
except ImportError:
    from datetime import timezone, timedelta
    PT_TZ = timezone(timedelta(hours=-7))


class YouTubeQuotaManager:
    """
    Manages and tracks YouTube Data API v3 quota usage.
    Default daily limit: 10,000 units.
    Standard video upload cost: 1,600 units.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._units_used: int = 0
        self._uploads_count: int = 0
        self._quota_exceeded_flag: bool = False
        self._last_reset_date: str = self._get_current_pt_date()

    @staticmethod
    def _get_current_pt_date() -> str:
        """Returns current date formatted as YYYY-MM-DD in Pacific Time."""
        return datetime.now(PT_TZ).strftime("%Y-%m-%d")

    def _check_and_reset_if_new_day(self) -> None:
        """Resets quota accounting if a new calendar day in Pacific Time has begun."""
        current_date = self._get_current_pt_date()
        if current_date != self._last_reset_date:
            logger.info(
                "YouTube quota day rollover detected (%s -> %s). Resetting daily quota counter.",
                self._last_reset_date,
                current_date,
            )
            self._units_used = 0
            self._uploads_count = 0
            self._quota_exceeded_flag = False
            self._last_reset_date = current_date

    @property
    def daily_limit(self) -> int:
        return getattr(settings, "YOUTUBE_DAILY_QUOTA_LIMIT", 10000)

    @property
    def upload_cost(self) -> int:
        return getattr(settings, "YOUTUBE_UPLOAD_QUOTA_COST", 1600)

    @property
    def is_enabled(self) -> bool:
        return getattr(settings, "YOUTUBE_ENABLE_QUOTA_TRACKING", True)

    def has_sufficient_quota(self, cost: Optional[int] = None) -> bool:
        """
        Determines whether sufficient quota units remain for an upload.
        If quota tracking is disabled, always returns True.
        """
        if not self.is_enabled:
            return True

        with self._lock:
            self._check_and_reset_if_new_day()
            if self._quota_exceeded_flag:
                return False
            required_cost = cost if cost is not None else self.upload_cost
            return (self._units_used + required_cost) <= self.daily_limit

    def consume_quota(self, cost: Optional[int] = None) -> None:
        """
        Records quota consumption after a successful YouTube upload or API operation.
        """
        if not self.is_enabled:
            return

        with self._lock:
            self._check_and_reset_if_new_day()
            applied_cost = cost if cost is not None else self.upload_cost
            self._units_used += applied_cost
            self._uploads_count += 1
            logger.info(
                "YouTube quota consumed: +%d units (Total today: %d / %d units, %d uploads)",
                applied_cost,
                self._units_used,
                self.daily_limit,
                self._uploads_count,
            )
            if self._units_used >= self.daily_limit:
                self._quota_exceeded_flag = True
                logger.warning(
                    "YouTube daily quota limit reached: %d / %d units used.",
                    self._units_used,
                    self.daily_limit,
                )

    def mark_quota_exceeded(self) -> None:
        """
        Marks quota as exceeded immediately when Google API responds with 403 quotaExceeded.
        """
        with self._lock:
            self._check_and_reset_if_new_day()
            self._quota_exceeded_flag = True
            self._units_used = max(self._units_used, self.daily_limit)
            logger.warning("YouTube quota marked as EXCEEDED for the remainder of today (%s).", self._last_reset_date)

    def reset_quota(self) -> None:
        """Manually resets quota counter (primarily for testing or admin overrides)."""
        with self._lock:
            self._units_used = 0
            self._uploads_count = 0
            self._quota_exceeded_flag = False
            self._last_reset_date = self._get_current_pt_date()
            logger.info("YouTube quota counter manually reset.")

    def get_quota_status(self) -> Dict[str, Any]:
        """Returns comprehensive real-time quota metrics and health report."""
        with self._lock:
            self._check_and_reset_if_new_day()
            limit = self.daily_limit
            used = self._units_used
            cost = self.upload_cost
            remaining = max(0, limit - used)
            estimated_uploads_remaining = (
                0 if self._quota_exceeded_flag else remaining // cost
            )
            usage_pct = round((used / limit) * 100.0, 2) if limit > 0 else 100.0

            return {
                "quota_tracking_enabled": self.is_enabled,
                "current_date_pt": self._last_reset_date,
                "daily_limit_units": limit,
                "units_used": used,
                "units_remaining": remaining,
                "usage_percentage": usage_pct,
                "upload_cost_units": cost,
                "successful_uploads_today": self._uploads_count,
                "estimated_uploads_remaining": estimated_uploads_remaining,
                "is_quota_exceeded": self._quota_exceeded_flag or (remaining < cost),
                "can_upload": (not self._quota_exceeded_flag) and (remaining >= cost) if self.is_enabled else True,
            }


# Global singleton instance
youtube_quota_manager = YouTubeQuotaManager()
