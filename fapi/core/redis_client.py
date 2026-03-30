import redis
from fapi.core import config
import logging

logger = logging.getLogger(__name__)

class RedisClient:
    _client = None

    @classmethod
    def get_client(cls):
        if cls._client is None:
            try:
                cls._client = redis.Redis(
                    host=config.REDIS_HOST,
                    port=config.REDIS_PORT,
                    db=config.REDIS_DB,
                    password=config.REDIS_PASSWORD,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True
                )
                logger.info("✅ Redis connected")
            except Exception as e:
                logger.error(f"❌ Redis connection failed: {e}")
                cls._client = None
        return cls._client

redis_client = RedisClient()