import redis
from fapi.core import config
import logging

logger = logging.getLogger(__name__)

class RedisClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisClient, cls).__new__(cls)
            cls._instance.client = None
        return cls._instance

    def connect(self):
        """Initialize Redis connection pool."""
        if self.client is None:
            try:
                self.client = redis.Redis(
                    host=config.REDIS_HOST,
                    port=config.REDIS_PORT,
                    password=config.REDIS_PASSWORD,
                    db=config.REDIS_DB,
                    decode_responses=True  # Returns strings instead of bytes
                )
                # Test connection
                self.client.ping()
                logger.info(f"Connected to Redis at {config.REDIS_HOST}:{config.REDIS_PORT}")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self.client = None

    def get_client(self):
        """Get the Redis client instance."""
        if self.client is None:
            self.connect()
        return self.client

    def disconnect(self):
        """Close Redis connection."""
        if self.client:
            self.client.close()
            self.client = None
            logger.info("Redis connection closed")

# Singleton instance
redis_client = RedisClient()
