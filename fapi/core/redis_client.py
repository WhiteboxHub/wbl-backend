from upstash_redis import Redis
from fapi.core import config
import logging

logger = logging.getLogger(__name__)

class RedisClient:
    _client = None

    @classmethod
    def get_client(cls):
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