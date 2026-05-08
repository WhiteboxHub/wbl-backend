try:
    from upstash_redis import Redis
except ImportError:  # pragma: no cover - runtime environment dependent
    Redis = None  # type: ignore[assignment]
from fapi.core import config
import logging

logger = logging.getLogger(__name__)

class RedisClient:
    _client = None

    @classmethod
    def get_client(cls):
        if Redis is None:
            logger.warning("upstash_redis package is not installed; Redis cache is disabled")
            return None
        if cls._client is None:
            try:
                cls._client = Redis(
                    url=config.UPSTASH_REDIS_REST_URL,
                    token=config.UPSTASH_REDIS_REST_TOKEN,
                )
                logger.info("Upstash Redis connected")
            except Exception as e:
                logger.error(f"Upstash Redis connection failed: {e}")
                cls._client = None
        return cls._client

redis_client = RedisClient()