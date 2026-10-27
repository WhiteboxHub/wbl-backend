try:
    import redis as redis_lib
except ImportError:  # pragma: no cover - runtime environment dependent
    redis_lib = None  # type: ignore[assignment]

import os
import logging
from fapi.core import config

logger = logging.getLogger(__name__)


class RedisClient:
    _client = None

    @classmethod
    def get_client(cls):
        """
        Returns a shared Redis client instance, or None if Redis is unavailable.
        Uses decode_responses=True so values are returned as strings, not bytes.
        Includes connection and socket timeouts so a dead Redis server does not
        stall the application.
        """
        if cls._client is not None:
            return cls._client

        if not config.REDIS_HOST:
            return None

        # Validate that REDIS_PASSWORD is provided in production (OWASP A07 guard)
        app_env = (getattr(config, "APP_ENV", None) or os.getenv("APP_ENV", "local")).strip().lower()
        if app_env in ("production", "prod"):
            if not config.REDIS_PASSWORD:
                raise ValueError(
                    "Insecure configuration: REDIS_PASSWORD must be configured in production when REDIS_HOST is set."
                )

        if redis_lib is None:
            return None

        try:
            cls._client = redis_lib.Redis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                password=config.REDIS_PASSWORD or None,
                decode_responses=True,          # returns str, not bytes
                socket_connect_timeout=2.0,     # fail fast if VM unreachable
                socket_timeout=2.0,             # fail fast on slow operations
            )
            cls._client.ping()
            logger.info(
                "Redis connected at %s:%s", config.REDIS_HOST, config.REDIS_PORT
            )
        except Exception as e:
            logger.warning(
                "Redis unavailable, continuing without cache: %s", e
            )
            cls._client = None

        return cls._client

    @classmethod
    def close(cls):
        """Close the connection pool on application shutdown."""
        if cls._client is not None:
            try:
                cls._client.close()
            except Exception:
                pass
            cls._client = None


redis_client = RedisClient()