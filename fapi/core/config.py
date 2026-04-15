import os
from dotenv import load_dotenv
# fapi/utils/limiter_config.py
from slowapi import Limiter
from slowapi.util import get_remote_address




# Load environment variables from .env file
load_dotenv()
limiter = Limiter(key_func=get_remote_address)

# Get secret values from environment
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is not set")

ALGORITHM = os.getenv("ALGORITHM", "HS256")
if not ALGORITHM:
    raise ValueError("ALGORITHM environment variable is not set")

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440))  # Defaults to 1440 if not set
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES  = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", 15))
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    # We should ideally raise an error here to prevent starting without security
    # but for development we can default or warn.
    # raise ValueError("ENCRYPTION_KEY environment variable is not set")
    print("WARNING: ENCRYPTION_KEY not set. API keys will NOT be secured properly.")

# Upstash Redis Configuration
UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

if not UPSTASH_REDIS_REST_URL:
    raise ValueError("UPSTASH_REDIS_REST_URL not set")

if not UPSTASH_REDIS_REST_TOKEN:
    raise ValueError("UPSTASH_REDIS_REST_TOKEN not set")

REDIS_TTL_DEFAULT = int(os.getenv("REDIS_TTL_DEFAULT", 300))