# wbl-backend/fapi/auth.py
from fapi.db.database import get_user_by_username_sync,get_user_by_username
from jose import jwt, JWTError,ExpiredSignatureError
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import hashlib
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from fastapi import Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional  
from datetime import timedelta  
import asyncio

# Load environment variables from .env file
load_dotenv()

# Retrieve the secret key from environment variables
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is not set")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440
# ACCESS_TOKEN_EXPIRE_MINUTES =1
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 15  # Token expiry time for password reset

# Simple in-memory cache dictionary
cache = {}

cache_clear_seconds = 60*180

def cache_set(key, value, ttl_seconds=cache_clear_seconds):  # Default TTL of 1 hour
    expiration_time = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    cache[key] = (value, expiration_time)

def cache_get(key):
    if key in cache:
        value, expiration_time = cache[key]
        if expiration_time > datetime.utcnow():
            return value
        else:
            del cache[key]  # Remove expired item from cache
    return None

# ----------------------------------------------------------------------- Avatar ---------------------------------------------------------------------------
def determine_user_role(userinfo: dict) -> str:
    """
    Determine role based on email domain or 'team' field.
    """
    email = userinfo.get('uname', '')
    team = (userinfo.get('team') or '').lower()
    if "whitebox-learning" in email or "innova-path" in email or "admin" in email or team == "admin":
        return "admin"
    return "candidate"

# --------------------------------------------------------------------------------------------------------------------------

class JWTAuthorizationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        skip_paths = ["/login", "/signup", "/", "/verify_token", "/docs", "/openapi.json","/api/auth/callback/google","/api/auth/error"]
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
                userinfo = await get_user_by_username(username)
                if not userinfo:
                    return JSONResponse(status_code=401, content={"detail": "Unauthorized user"})
                cache_set(username, userinfo)
                user = userinfo

            # Attach user and role info to request state
            request.state.user = user
            request.state.role = role

        except ExpiredSignatureError:
            return JSONResponse(status_code=401, content={"detail": "Login session expired"})
        except JWTError:
            return JSONResponse(status_code=401, content={"detail": "Invalid or unauthorized token"})
        except Exception as e:
            return JSONResponse(status_code=500, content={"detail": str(e)})

        return await call_next(request)



def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

    # Get user info from DB (to add role into token)
    username = data.get("sub")
    if username:
        userinfo = cache_get(username)
        if not userinfo:
            userinfo = asyncio.run(get_user_by_username(username))
            cache_set(username, userinfo)
        role = determine_user_role(userinfo)
        to_encode["role"] = role

    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    
def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except ExpiredSignatureError:
        return JSONResponse(status_code=401, content={'detail': 'Login Session Expired'})
    except JWTError:
        return JSONResponse(status_code=401, content={'detail': 'Unauthorized - invalid User, please login again'})

# Function to create password reset token
def generate_password_reset_token(email: str):
    expire = datetime.utcnow() + timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": email, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Function to verify password reset token
def verify_password_reset_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        return email
    except ExpiredSignatureError:
        return None
    except JWTError:
        return None

# Function to hash the new password
def get_password_hash(password: str):
    return hashlib.md5(password.encode()).hexdigest()


# def create_google_access_token(data: dict, expires_delta: Optional[timedelta] = None):
#     to_encode = data.copy()
    
#     # Set expiration based on expires_delta or default to ACCESS_TOKEN_EXPIRE_MINUTES
#     if expires_delta:
#         expire = datetime.utcnow() + expires_delta
#     else:
#         expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
#     to_encode.update({"exp": expire})
#     encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
#     return encoded_jwt


# def create_google_access_token(data: dict, expires_delta: Optional[timedelta] = None):
#     to_encode = data.copy()
#     expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

#     username = data.get("sub")
#     if username:
#         userinfo = cache_get(username)
#         if not userinfo:
#             userinfo = asyncio.run(get_user_by_username(username))
#             cache_set(username, userinfo)
#         role = determine_user_role(userinfo)
#         to_encode["role"] = role

#     to_encode["exp"] = expire
#     return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)



async def create_google_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

    username = data.get("sub")
    if username:
        userinfo = cache_get(username)
        if not userinfo:
            userinfo = await get_user_by_username(username) 
            cache_set(username, userinfo)
        role = determine_user_role(userinfo)
        to_encode["role"] = role

        if "domain" in userinfo:
            to_encode["domain"] = userinfo["domain"]

    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# -------------------------------------------------- Avatar --------------------------------------------------
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

    username = data.get("sub")
    if username:
        userinfo = cache_get(username)
        if not userinfo:
            userinfo = get_user_by_username_sync(username)  # Using sync version
            cache_set(username, userinfo)
        role = determine_user_role(userinfo)
        to_encode["role"] = role

    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)