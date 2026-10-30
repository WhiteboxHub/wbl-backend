import json
import hashlib
import functools
import inspect
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
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, set):
        return list(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if hasattr(obj, "__dict__"):
        # For SQLAlchemy ORM objects
        data = dict(obj.__dict__)
        data.pop("_sa_instance_state", None)
        
        for attr_name in dir(obj.__class__):
            attr = getattr(obj.__class__, attr_name)
            if isinstance(attr, property):
                try:
                    data[attr_name] = getattr(obj, attr_name)
                except Exception:
                    pass
        return data
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def generate_cache_key(prefix: str, path: str, params: dict) -> str:
    """Generate a unique cache key with environment isolation."""
    # Sort params to ensure consistent key generation
    sorted_params = sorted(params.items())
    params_str = json.dumps(sorted_params)
    params_hash = hashlib.md5(params_str.encode()).hexdigest()
    # Use APP_ENV to isolate local dev from production
    return f"{config.APP_ENV}:cache:{prefix}:{path}:{params_hash}"

def _format_cache_arg(key: Optional[str], val: Any) -> Optional[str]:
    """Formats an argument for cache key generation or returns None if it should be skipped."""
    if key and key.lower() in ("db", "request", "background_tasks", "response"):
        return None
    if hasattr(val, "__class__"):
        class_name = val.__class__.__name__
        if any(skip in class_name for skip in ("Session", "Request", "BackgroundTasks", "Response", "StreamingResponse", "UploadFile")):
            return None
        if "AuthUser" in class_name or "User" in class_name:
            user_id = getattr(val, "id", None) or getattr(val, "uname", None)
            return f"user_{user_id}"
    return str(val)


def cache_result(ttl: int = config.REDIS_TTL_DEFAULT, prefix: str = "general"):
    """
    Decorator to cache the result of any function.
    Keys are generated based on function name and its relevant arguments.
    Skips 'db' (Session), 'request' (Request), and other non-cacheable context arguments.
    Supports both synchronous and asynchronous functions.
    """
    def decorator(func: Callable):
        is_async = inspect.iscoroutinefunction(func)

        def _build_cache_key(*args, **kwargs) -> str:
            key_params = {}
            for i, arg in enumerate(args):
                formatted = _format_cache_arg(None, arg)
                if formatted is not None:
                    key_params[f"arg_{i}"] = formatted

            for k, v in kwargs.items():
                formatted = _format_cache_arg(k, v)
                if formatted is not None:
                    key_params[k] = formatted

            return generate_cache_key(prefix, func.__name__, key_params)

        def _get_from_cache(client, cache_key: str):
            try:
                cached_data = client.get(cache_key)
                if cached_data:
                    if isinstance(cached_data, (bytes, bytearray)):
                        cached_data = cached_data.decode()
                    msg = f"[REDIS CACHE HIT] Function: {func.__name__} | Key: {cache_key}"
                    logger.info(msg)
                    return True, json.loads(cached_data)
            except Exception as e:
                logger.error(f"Error fetching from Redis: {e}")
            return False, None

        def _store_in_cache(client, cache_key: str, result: Any):
            try:
                if result is not None:
                    client.set(
                        cache_key,
                        json.dumps(result, default=alchemy_encoder),
                        ex=ttl
                    )
                    msg = f"[REDIS CACHE MISS] Function: {func.__name__} | Key: {cache_key}"
                    logger.info(msg)
            except Exception as e:
                logger.error(f"Error storing in Redis: {e}")

        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                client = redis_client.get_client()
                if not client:
                    return await func(*args, **kwargs)

                cache_key = _build_cache_key(*args, **kwargs)
                hit, cached_val = _get_from_cache(client, cache_key)
                if hit:
                    return cached_val

                result = await func(*args, **kwargs)
                _store_in_cache(client, cache_key, result)
                return result

            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                client = redis_client.get_client()
                if not client:
                    return func(*args, **kwargs)

                cache_key = _build_cache_key(*args, **kwargs)
                hit, cached_val = _get_from_cache(client, cache_key)
                if hit:
                    return cached_val

                result = func(*args, **kwargs)
                _store_in_cache(client, cache_key, result)
                return result

            return sync_wrapper

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
                    if isinstance(cached_data, (bytes, bytearray)):
                        cached_data = cached_data.decode()
                    logger.info(f"CACHE HIT: {cache_key}")
                    return json.loads(cached_data)
            except Exception as e:
                logger.error(f"Error fetching from Redis: {e}")

            # Cache miss: execute function
            response_data = await func(*args, **kwargs)

            # Store result in cache
            try:
                if response_data is not None:
                    client.set(
                        cache_key,
                        json.dumps(response_data, default=alchemy_encoder),
                        ex=ttl
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
        # Include APP_ENV in the pattern to match keys generated by generate_cache_key
        full_pattern = f"{config.APP_ENV}:cache:{pattern}:*"
        keys = client.keys(full_pattern)
        if keys:
            client.delete(*keys)
            logger.info(f"Invalidated {len(keys)} cache keys matching pattern: {full_pattern}")
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
