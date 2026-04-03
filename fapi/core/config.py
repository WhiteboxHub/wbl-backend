import os
from dotenv import load_dotenv
# fapi/utils/limiter_config.py
from slowapi import Limiter
from slowapi.util import get_remote_address

# Load environment variables from .env file
load_dotenv()
limiter = Limiter(key_func=get_remote_address)

# Get secret values from environment
_SECRET_KEY = os.getenv("SECRET_KEY")
if not _SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is not set")
SECRET_KEY: str = _SECRET_KEY

_ALGORITHM = os.getenv("ALGORITHM", "HS256")
if not _ALGORITHM:
    raise ValueError("ALGORITHM environment variable is not set")
ALGORITHM: str = _ALGORITHM

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440))  # Defaults to 1440 if not set
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", 15))

# Upstash Redis Configuration (optional for local dev)
UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

if not UPSTASH_REDIS_REST_URL or not UPSTASH_REDIS_REST_TOKEN:
    # For local dev, just disable Redis cache instead of crashing
    print("Warning: Upstash Redis env vars not set. Caching is disabled.")
    UPSTASH_REDIS_REST_URL = None
    UPSTASH_REDIS_REST_TOKEN = None

REDIS_TTL_DEFAULT = int(os.getenv("REDIS_TTL_DEFAULT", 300))