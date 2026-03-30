import json
import hashlib
import functools
from typing import Any, Callable, Optional
from fastapi import Request
from fapi.core.redis_client import redis_client
from fapi.core import config
import logging

from datetime import datetime, date
from decimal import Decimal

logger = logging.getLogger(__name__)

def alchemy_encoder(obj: Any) -> Any:
    """Helper to serialize SQLAlchemy objects and other types."""
    if hasattr(obj, "__dict__"):
        # For SQLAlchemy ORM objects
        data = dict(obj.__dict__)
        data.pop("_sa_instance_state", None)
        return data
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)

def generate_cache_key(prefix: str, path: str, params: dict) -> str:
    """Generate a unique cache key."""
    # Sort params to ensure consistent key generation
    sorted_params = sorted(params.items())
    params_str = json.dumps(sorted_params)
    params_hash = hashlib.md5(params_str.encode()).hexdigest()
    return f"cache:{prefix}:{path}:{params_hash}"

def cache_result(ttl: int = config.REDIS_TTL_DEFAULT, prefix: str = "general"):
    """
    Decorator to cache the result of any function.
    Keys are generated based on function name and its relevant arguments.
    Skips 'db' (Session) and 'request' (Request) arguments.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Check if Redis is enabled/connected
            client = redis_client.get_client()
            if not client:
                return func(*args, **kwargs)

            # Build a list of relevant arguments for the cache key
            key_params = {}
            for i, arg in enumerate(args):
                # Skip db sessions, requests, etc.
                if hasattr(arg, "__class__"):
                    class_name = arg.__class__.__name__
                    if "Session" in class_name or "Request" in class_name:
                        continue
                key_params[f"arg_{i}"] = str(arg)
            
            for k, v in kwargs.items():
                if k in ("db", "request"):
                    continue
                if hasattr(v, "__class__"):
                    class_name = v.__class__.__name__
                    if "Session" in class_name or "Request" in class_name:
                        continue
                key_params[k] = str(v)

            # Generate cache key using function name as path
            cache_key = generate_cache_key(prefix, func.__name__, key_params)

            # Try to get data from cache
            try:
                cached_data = client.get(cache_key)
                if cached_data:
                    msg = f"🟢 [REDIS CACHE HIT] Function: {func.__name__} | Key: {cache_key}"
                    logger.info(msg)
                    print(msg) # Ensure visibility in terminal
                    return json.loads(cached_data)
            except Exception as e:
                logger.error(f"Error fetching from Redis: {e}")

            # Cache miss: execute function
            result = func(*args, **kwargs)

            # Store result in cache
            try:
                if result is not None:
                    client.setex(
                        cache_key,
                        ttl,
                        json.dumps(result, default=alchemy_encoder)
                    )
                    msg = f"⚪ [REDIS CACHE MISS] Function: {func.__name__} | Key: {cache_key}"
                    logger.info(msg)
                    print(msg) # Ensure visibility in terminal
            except Exception as e:
                logger.error(f"Error storing in Redis: {e}")

            return result
        return wrapper
    return decorator

def cache_response(ttl: int = config.REDIS_TTL_DEFAULT, prefix: str = "general"):
    """
    Decorator to cache FastAPI endpoint responses.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Try to get the request object from kwargs
            request: Optional[Request] = kwargs.get("request")
            if not request:
                # Fallback: check if any arg is a Request object
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            # If no request object found, bypass cache
            if not request:
                return await func(*args, **kwargs)

            # Check if Redis is enabled/connected
            client = redis_client.get_client()
            if not client:
                return await func(*args, **kwargs)

            # Generate cache key
            cache_key = generate_cache_key(prefix, request.url.path, dict(request.query_params))

            # Try to get data from cache
            try:
                cached_data = client.get(cache_key)
                if cached_data:
                    logger.info(f"CACHE HIT: {cache_key}")
                    return json.loads(cached_data)
            except Exception as e:
                logger.error(f"Error fetching from Redis: {e}")

            # Cache miss: execute function
            response_data = await func(*args, **kwargs)

            # Store result in cache
            try:
                if response_data is not None:
                    client.setex(
                        cache_key,
                        ttl,
                     json.dumps(response_data, default=alchemy_encoder)
                    )
                    logger.info(f"CACHE MISS (Stored in Redis): {cache_key}")
            except Exception as e:
                logger.error(f"Error storing in Redis: {e}")

            return response_data
        return wrapper
    return decorator

def invalidate_cache(pattern: str):
    """Invalidate cache keys matching a pattern."""
    client = redis_client.get_client()
    if not client:
        return
    
    try:
        keys = client.keys(f"cache:{pattern}:*")
        if keys:
            client.delete(*keys)
            logger.info(f"Invalidated {len(keys)} cache keys matching pattern: {pattern}")
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
