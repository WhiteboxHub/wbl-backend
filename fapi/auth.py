# wbl-backend/fapi/auth.py
from fapi.utils.db_queries import get_user_by_username_sync
from jose import jwt, JWTError, ExpiredSignatureError
from datetime import datetime, timedelta
from fapi.core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
import hashlib
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from fastapi import Request
from typing import Optional

# Simple in-memory cache dictionary
cache = {}
cache_clear_seconds = 60 * 180


def cache_set(key, value, ttl_seconds=cache_clear_seconds):
    expiration_time = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    cache[key] = (value, expiration_time)


def cache_get(key):
    if key in cache:
        value, expiration_time = cache[key]
        if expiration_time > datetime.utcnow():
            return value
        else:
            del cache[key]
    return None


def determine_user_role(userinfo) -> str:
    uname = (getattr(userinfo, "uname", "") or "").lower()
    return "admin" if uname == "admin" else "candidate"


class JWTAuthorizationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        skip_paths = ["/login", "/signup", "/", "/verify_token", "/docs", "/openapi.json",
                      "/api/auth/callback/google", "/api/auth/error"]

        if any(request.url.path.startswith(path) for path in skip_paths):
            return await call_next(request)
        # if request.url.path in skip_paths:
        #     return await call_next(request)

        apiToken = request.headers.get('Authtoken')
        if not apiToken:
            return JSONResponse(status_code=401, content={"detail": "Authorization token missing"})

        try:
            decoded_token = jwt.decode(apiToken, SECRET_KEY, algorithms=[ALGORITHM])
            username = decoded_token.get('sub')
            role = decoded_token.get('role')

            user = cache_get(username)
            if user is None:
                userinfo = get_user_by_username_sync(username)
                if not userinfo:
                    return JSONResponse(status_code=401, content={"detail": "User not found"})
                cache_set(username, userinfo)
                user = userinfo

            request.state.user = user
            request.state.role = role

        except ExpiredSignatureError:
            return JSONResponse(status_code=401, content={"detail": "Login session expired"})
        except JWTError:
            return JSONResponse(status_code=401, content={"detail": "Invalid or unauthorized token"})
        except Exception as e:
            return JSONResponse(status_code=500, content={"detail": str(e)})

        return await call_next(request)


def generate_password_reset_token(email: str):
    expire = datetime.utcnow() + timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": email, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_password_reset_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except ExpiredSignatureError:
        return None
    except JWTError:
        return None


def get_password_hash(password: str):
    return hashlib.md5(password.encode()).hexdigest()


async def create_google_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

    username = data.get("sub")
    if username:
        userinfo = cache_get(username)
        if userinfo is None:
            userinfo = get_user_by_username_sync(username)
            if not userinfo:
                raise ValueError(f"User '{username}' not found while creating Google access token")
            cache_set(username, userinfo)

        role = determine_user_role(userinfo)
        to_encode["role"] = role

        # ORM-safe domain handling
        domain = getattr(userinfo, "domain", None)
        if domain:
            to_encode["domain"] = domain

    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

    username = data.get("sub")
    if username:
        userinfo = cache_get(username)
        if userinfo is None:
            userinfo = get_user_by_username_sync(username)
            if not userinfo:
                raise ValueError(f"User '{username}' not found while creating access token")
            cache_set(username, userinfo)

        role = determine_user_role(userinfo)
        to_encode["role"] = role

    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
