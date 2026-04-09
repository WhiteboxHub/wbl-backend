import os
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
RateLimitExceededError = RateLimitExceeded
RateLimitExceededHandler = _rate_limit_exceeded_handler

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY") or ""
ALGORITHM = os.getenv("ALGORITHM", "HS256")

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440))
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", 15))

UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

REDIS_TTL_DEFAULT = int(os.getenv("REDIS_TTL_DEFAULT", 300))

if not SECRET_KEY:
    raise ValueError("SECRET_KEY not set")