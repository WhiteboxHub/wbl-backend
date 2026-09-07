"""
YouTube Account Pool & Sequential Quota Manager
===============================================
Manages a pool of YouTube accounts for sequential quota rotation.
- Tracks daily uploads per account (up to 6 videos per account per day).
- Uses accounts sequentially (Account 1 -> Account 2 -> Account 3).
- Automatically resets quotas at 08:00 UTC (Midnight PST, when Google resets quota).
- Computes countdown to quota reset when all accounts are exhausted.
"""
import os
import json
import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from fapi.ai_prep.config import settings
from fapi.ai_prep.exceptions import AllYouTubeQuotasExhaustedError

logger = logging.getLogger(__name__)


@dataclass
class YouTubeAccount:
    """Represents a single YouTube API account credential set with daily quota tracking."""
    account_id: str
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    refresh_token: Optional[str] = None
    api_key: Optional[str] = None
    credentials_file: Optional[str] = None
    daily_limit: int = 6
    upload_count_today: int = 0
    is_exhausted: bool = False
    last_reset_date: Optional[str] = None

    def has_credentials(self) -> bool:
        return bool(
            self.refresh_token or
            (self.credentials_file and os.path.exists(self.credentials_file)) or
            self.api_key
        )


class YouTubeAccountPool:
    """Thread-safe pool managing sequential account rotation and quota resets."""

    def __init__(self):
        self._accounts: List[YouTubeAccount] = []
        self._lock = threading.Lock()
        self.reload_accounts()

    def reload_accounts(self) -> None:
        """Loads or reloads accounts from environment / settings."""
        with self._lock:
            accounts: List[YouTubeAccount] = []
            raw_json = settings.YOUTUBE_ACCOUNTS_JSON

            if raw_json:
                try:
                    parsed = json.loads(raw_json)
                    if isinstance(parsed, list):
                        for idx, item in enumerate(parsed):
                            acc = YouTubeAccount(
                                account_id=item.get("account_id", f"account_{idx + 1}"),
                                client_id=item.get("client_id"),
                                client_secret=item.get("client_secret"),
                                refresh_token=item.get("refresh_token"),
                                api_key=item.get("api_key"),
                                credentials_file=item.get("credentials_file"),
                                daily_limit=int(item.get("daily_limit", settings.YOUTUBE_DAILY_UPLOAD_LIMIT_PER_ACCOUNT)),
                            )
                            accounts.append(acc)
                except Exception as e:
                    logger.error("Failed to parse YOUTUBE_ACCOUNTS_JSON: %s", str(e))

            # Fallback to single account credentials in settings if no JSON pool configured
            if not accounts:
                accounts.append(
                    YouTubeAccount(
                        account_id="primary_account",
                        client_id=settings.YOUTUBE_CLIENT_ID,
                        client_secret=settings.YOUTUBE_CLIENT_SECRET,
                        refresh_token=settings.YOUTUBE_REFRESH_TOKEN,
                        api_key=settings.YOUTUBE_API_KEY,
                        credentials_file=settings.YOUTUBE_CREDENTIALS_FILE,
                        daily_limit=settings.YOUTUBE_DAILY_UPLOAD_LIMIT_PER_ACCOUNT,
                    )
                )

            self._accounts = accounts
            logger.info("Loaded %d YouTube account(s) into sequential quota pool.", len(self._accounts))

    def _get_current_quota_date(self) -> str:
        """
        Returns string representing current quota date based on reset hour (08:00 UTC = 00:00 PST).
        """
        now = datetime.now(timezone.utc)
        reset_hour = settings.YOUTUBE_QUOTA_RESET_HOUR_UTC
        # If current time is before reset hour, quota belongs to previous calendar day
        if now.hour < reset_hour:
            quota_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            quota_date = now.strftime("%Y-%m-%d")
        return quota_date

    def _check_and_reset_daily_quotas(self) -> None:
        """Resets all account daily counters if date has rolled over past reset hour."""
        current_date = self._get_current_quota_date()
        for acc in self._accounts:
            if acc.last_reset_date != current_date:
                acc.upload_count_today = 0
                acc.is_exhausted = False
                acc.last_reset_date = current_date
                logger.info("Reset YouTube upload quota for account %s (date: %s)", acc.account_id, current_date)

    def get_next_active_account(self) -> Optional[YouTubeAccount]:
        """
        Sequentially returns the first non-exhausted account that has not reached its daily limit.
        Returns None if all accounts in the pool are exhausted.
        """
        with self._lock:
            self._check_and_reset_daily_quotas()
            for acc in self._accounts:
                if acc.has_credentials() and not acc.is_exhausted and acc.upload_count_today < acc.daily_limit:
                    return acc
            return None

    def record_successful_upload(self, account_id: str) -> None:
        """Increments upload count and marks exhausted if limit reached."""
        with self._lock:
            for acc in self._accounts:
                if acc.account_id == account_id:
                    acc.upload_count_today += 1
                    logger.info(
                        "Recorded upload for account %s: %d/%d used today.",
                        acc.account_id, acc.upload_count_today, acc.daily_limit
                    )
                    if acc.upload_count_today >= acc.daily_limit:
                        acc.is_exhausted = True
                        logger.warning(
                            "Account %s reached daily upload limit (%d). Marking QUOTA_EXHAUSTED.",
                            acc.account_id, acc.daily_limit
                        )
                    break

    def mark_account_exhausted(self, account_id: str, reason: str = "quota_exceeded") -> None:
        """Manually marks an account exhausted upon receiving 403 API quota error."""
        with self._lock:
            for acc in self._accounts:
                if acc.account_id == account_id:
                    acc.is_exhausted = True
                    logger.warning("Marked account %s as QUOTA_EXHAUSTED. Reason: %s", account_id, reason)
                    break

    def get_seconds_until_next_reset(self) -> int:
        """Calculates exact seconds remaining until next YouTube quota reset (08:00 UTC / 00:00 PST)."""
        now = datetime.now(timezone.utc)
        reset_hour = settings.YOUTUBE_QUOTA_RESET_HOUR_UTC

        # Target reset time today at reset_hour
        target_reset = now.replace(hour=reset_hour, minute=0, second=0, microsecond=0)
        if now >= target_reset:
            # If already past reset hour today, next reset is tomorrow at reset_hour
            target_reset += timedelta(days=1)

        diff = int((target_reset - now).total_seconds())
        return max(diff, 60)

    def get_pool_status(self) -> Dict[str, Any]:
        """Returns snapshot of all accounts in the pool for telemetry/monitoring."""
        with self._lock:
            self._check_and_reset_daily_quotas()
            return {
                "total_accounts": len(self._accounts),
                "seconds_until_reset": self.get_seconds_until_next_reset(),
                "accounts": [
                    {
                        "account_id": acc.account_id,
                        "upload_count_today": acc.upload_count_today,
                        "daily_limit": acc.daily_limit,
                        "is_exhausted": acc.is_exhausted,
                    }
                    for acc in self._accounts
                ]
            }


youtube_account_pool = YouTubeAccountPool()
