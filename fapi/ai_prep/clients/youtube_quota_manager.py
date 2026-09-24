"""
YouTube API Quota Manager
==========================
Thread-safe and distributed YouTube Data API v3 quota tracker and enforcement engine.
Supports optional Redis backend for multi-worker synchronization with in-memory fallback.
Tracks daily quota usage, estimates remaining capacity, and automatically resets
accounting when the quota period rolls over (midnight Pacific Time).
"""
import logging
import threading
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from fapi.ai_prep.config import settings

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
    PT_TZ = ZoneInfo("America/Los_Angeles")
except ImportError:
    try:
        from dateutil.tz import gettz
        PT_TZ = gettz("America/Los_Angeles")
    except ImportError:
        PT_TZ = timezone(timedelta(hours=-7))

try:
    import redis
except ImportError:
    redis = None


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
        self._active_reservations: Dict[str, int] = {}
        self._redis_client = None
        self._init_redis()

    def _init_redis(self):
        redis_url = getattr(settings, "REDIS_URL", None)
        if redis_url and redis is not None:
            try:
                self._redis_client = redis.from_url(redis_url, decode_responses=True, socket_timeout=2)
                self._redis_client.ping()
                logger.info("YouTubeQuotaManager connected to distributed Redis at %s", redis_url)
            except Exception as e:
                logger.warning("Failed to initialize Redis for YouTubeQuotaManager (%s). Falling back to in-memory tracking.", e)
                self._redis_client = None

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
            self._active_reservations.clear()
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

    # Lua scripts for atomic Redis quota operations
    _LUA_RESERVE = """
    local key_units = KEYS[1]
    local key_exceeded = KEYS[2]
    local key_res = KEYS[3]
    local cost = tonumber(ARGV[1])
    local limit = tonumber(ARGV[2])
    local ttl = tonumber(ARGV[3])
    local res_ttl = tonumber(ARGV[4])

    if redis.call("EXISTS", key_exceeded) == 1 then
        return -1
    end

    local current = redis.call("INCRBY", key_units, cost)
    redis.call("EXPIRE", key_units, ttl)

    if current > limit then
        redis.call("DECRBY", key_units, cost)
        return 0
    end

    redis.call("SET", key_res, cost, "EX", res_ttl)
    return 1
    """

    _LUA_COMMIT_RESERVATION = """
    local key_uploads = KEYS[1]
    local key_res = KEYS[2]
    local ttl = tonumber(ARGV[1])

    if redis.call("DEL", key_res) == 1 then
        redis.call("INCRBY", key_uploads, 1)
        redis.call("EXPIRE", key_uploads, ttl)
        return 1
    else
        return 0
    end
    """

    _LUA_COMMIT_DIRECT = """
    local key_uploads = KEYS[1]
    local key_units = KEYS[2]
    local cost = tonumber(ARGV[1])
    local ttl = tonumber(ARGV[2])

    redis.call("INCRBY", key_uploads, 1)
    redis.call("EXPIRE", key_uploads, ttl)
    redis.call("INCRBY", key_units, cost)
    redis.call("EXPIRE", key_units, ttl)
    return 1
    """

    _LUA_RELEASE = """
    local key_units = KEYS[1]
    local key_res = KEYS[2]

    local reserved = redis.call("GET", key_res)
    if reserved then
        redis.call("DEL", key_res)
        redis.call("DECRBY", key_units, tonumber(reserved))
        return 1
    else
        return 0
    end
    """

    def reserve_quota(self, cost: Optional[int] = None) -> Optional[str]:
        """
        Atomically reserves quota units for an upload operation.
        Returns a reservation token if successful, or None if quota is insufficient.
        Units are accounted for at reservation time.
        """
        if not self.is_enabled:
            return "untracked_quota_token"

        required_cost = cost if cost is not None else self.upload_cost
        pt_date = self._get_current_pt_date()
        reservation_token = str(uuid.uuid4())

        if self._redis_client:
            try:
                key_units = f"aiprep:yt_quota:units:{pt_date}"
                key_exceeded = f"aiprep:yt_quota:exceeded:{pt_date}"
                key_res = f"aiprep:yt_quota:res:{reservation_token}"

                res = self._redis_client.eval(
                    self._LUA_RESERVE,
                    3,
                    key_units,
                    key_exceeded,
                    key_res,
                    required_cost,
                    self.daily_limit,
                    172800,  # 48h TTL
                    3600,    # 1h reservation hold TTL
                )
                if res == 1:
                    return reservation_token
                return None
            except Exception as e:
                logger.warning("Redis reserve_quota failed (%s), falling back to in-memory lock", e)

        with self._lock:
            self._check_and_reset_if_new_day()
            if self._quota_exceeded_flag:
                return None
            if (self._units_used + required_cost) > self.daily_limit:
                return None

            self._units_used += required_cost
            self._active_reservations[reservation_token] = required_cost
            return reservation_token

    def commit_quota(self, reservation_token: Optional[str] = None, cost: Optional[int] = None) -> None:
        """
        Confirms successful upload and records the upload count.
        - If a valid reservation_token is provided, finalizes the reservation without double-counting units.
        - If reservation_token is None (direct consumption path), increments both units and uploads count.
        Idempotent: repeating commit with the same token is a no-op.
        """
        if not self.is_enabled or reservation_token == "untracked_quota_token":
            return

        pt_date = self._get_current_pt_date()
        if self._redis_client:
            try:
                key_uploads = f"aiprep:yt_quota:uploads:{pt_date}"
                if reservation_token:
                    key_res = f"aiprep:yt_quota:res:{reservation_token}"
                    self._redis_client.eval(
                        self._LUA_COMMIT_RESERVATION,
                        2,
                        key_uploads,
                        key_res,
                        172800,
                    )
                else:
                    applied_cost = cost if cost is not None else self.upload_cost
                    key_units = f"aiprep:yt_quota:units:{pt_date}"
                    self._redis_client.eval(
                        self._LUA_COMMIT_DIRECT,
                        2,
                        key_uploads,
                        key_units,
                        applied_cost,
                        172800,
                    )
                return
            except Exception as e:
                logger.warning("Redis commit_quota failed (%s)", e)

        with self._lock:
            self._check_and_reset_if_new_day()
            if reservation_token:
                if reservation_token in self._active_reservations:
                    del self._active_reservations[reservation_token]
                    self._uploads_count += 1
                # If token was already committed or invalid -> idempotent no-op
            else:
                # Direct consumption without prior reservation (e.g. consume_quota)
                applied_cost = cost if cost is not None else self.upload_cost
                self._units_used += applied_cost
                self._uploads_count += 1

            if self._units_used >= self.daily_limit:
                self._quota_exceeded_flag = True

    def release_quota(self, reservation_token: Optional[str], cost: Optional[int] = None) -> None:
        """
        Rolls back a quota reservation if an upload fails before hitting Google API.
        Idempotent: repeating release with the same token is a no-op and will not restore units twice.
        """
        if not self.is_enabled or not reservation_token or reservation_token == "untracked_quota_token":
            return

        pt_date = self._get_current_pt_date()
        if self._redis_client:
            try:
                key_units = f"aiprep:yt_quota:units:{pt_date}"
                key_res = f"aiprep:yt_quota:res:{reservation_token}"
                self._redis_client.eval(
                    self._LUA_RELEASE,
                    2,
                    key_units,
                    key_res,
                )
                return
            except Exception as e:
                logger.warning("Redis release_quota failed (%s)", e)

        with self._lock:
            self._check_and_reset_if_new_day()
            if reservation_token in self._active_reservations:
                reserved_amount = self._active_reservations.pop(reservation_token)
                self._units_used = max(0, self._units_used - reserved_amount)

    def has_sufficient_quota(self, cost: Optional[int] = None) -> bool:
        """Determines whether sufficient quota units remain for an upload."""
        if not self.is_enabled:
            return True

        required_cost = cost if cost is not None else self.upload_cost
        pt_date = self._get_current_pt_date()

        if self._redis_client:
            try:
                key_units = f"aiprep:yt_quota:units:{pt_date}"
                key_exceeded = f"aiprep:yt_quota:exceeded:{pt_date}"
                if self._redis_client.get(key_exceeded):
                    return False
                used = int(self._redis_client.get(key_units) or 0)
                return (used + required_cost) <= self.daily_limit
            except Exception as e:
                logger.warning("Redis has_sufficient_quota query failed (%s)", e)

        with self._lock:
            self._check_and_reset_if_new_day()
            if self._quota_exceeded_flag:
                return False
            return (self._units_used + required_cost) <= self.daily_limit

    def consume_quota(self, cost: Optional[int] = None) -> None:
        """
        Records direct quota consumption after an upload (without prior reservation).
        Used primarily for testing or direct one-shot quota accounting.
        """
        if not self.is_enabled:
            return
        self.commit_quota(reservation_token=None, cost=cost)

    def mark_quota_exceeded(self) -> None:
        """Marks quota as exceeded immediately when Google API responds with 403 quotaExceeded."""
        pt_date = self._get_current_pt_date()
        if self._redis_client:
            try:
                key_exceeded = f"aiprep:yt_quota:exceeded:{pt_date}"
                self._redis_client.set(key_exceeded, "1", ex=172800)
            except Exception as e:
                logger.warning("Redis mark_quota_exceeded failed (%s)", e)

        with self._lock:
            self._check_and_reset_if_new_day()
            self._quota_exceeded_flag = True
            self._units_used = max(self._units_used, self.daily_limit)
            logger.warning("YouTube quota marked as EXCEEDED for the remainder of today (%s).", self._last_reset_date)

    def reset_quota(self) -> None:
        """Manually resets quota counter (primarily for testing or admin overrides)."""
        pt_date = self._get_current_pt_date()
        if self._redis_client:
            try:
                self._redis_client.delete(
                    f"aiprep:yt_quota:units:{pt_date}",
                    f"aiprep:yt_quota:uploads:{pt_date}",
                    f"aiprep:yt_quota:exceeded:{pt_date}",
                )
            except Exception as e:
                logger.warning("Redis reset_quota failed (%s)", e)

        with self._lock:
            self._units_used = 0
            self._uploads_count = 0
            self._quota_exceeded_flag = False
            self._active_reservations.clear()
            self._last_reset_date = self._get_current_pt_date()
            logger.info("YouTube quota counter manually reset.")

    def get_quota_status(self) -> Dict[str, Any]:
        """Returns comprehensive real-time quota metrics and health report."""
        pt_date = self._get_current_pt_date()
        limit = self.daily_limit
        cost = self.upload_cost

        used = 0
        uploads = 0
        exceeded = False

        if self._redis_client:
            try:
                used = int(self._redis_client.get(f"aiprep:yt_quota:units:{pt_date}") or 0)
                uploads = int(self._redis_client.get(f"aiprep:yt_quota:uploads:{pt_date}") or 0)
                exceeded = bool(self._redis_client.get(f"aiprep:yt_quota:exceeded:{pt_date}"))
            except Exception as e:
                logger.warning("Redis get_quota_status failed (%s), using local state", e)
                with self._lock:
                    self._check_and_reset_if_new_day()
                    used = self._units_used
                    uploads = self._uploads_count
                    exceeded = self._quota_exceeded_flag
        else:
            with self._lock:
                self._check_and_reset_if_new_day()
                used = self._units_used
                uploads = self._uploads_count
                exceeded = self._quota_exceeded_flag

        remaining = max(0, limit - used)
        estimated_uploads_remaining = 0 if exceeded else remaining // cost
        usage_pct = round((used / limit) * 100.0, 2) if limit > 0 else 100.0

        return {
            "quota_tracking_enabled": self.is_enabled,
            "current_date_pt": pt_date,
            "daily_limit_units": limit,
            "units_used": used,
            "units_remaining": remaining,
            "usage_percentage": usage_pct,
            "upload_cost_units": cost,
            "successful_uploads_today": uploads,
            "estimated_uploads_remaining": estimated_uploads_remaining,
            "is_quota_exceeded": exceeded or (remaining < cost),
            "can_upload": (not exceeded) and (remaining >= cost) if self.is_enabled else True,
        }


# Global singleton instance
youtube_quota_manager = YouTubeQuotaManager()
