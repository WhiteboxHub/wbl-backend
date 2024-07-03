# from jose import jwt
# from datetime import datetime, timedelta
# import os
# from dotenv import load_dotenv
# import hashlib

# # Load environment variables from .env file
# load_dotenv()

# # Retrieve the secret key from environment variables
# SECRET_KEY = os.getenv('SECRET_KEY')
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 30

# # Function to create access token
# def create_access_token(data: dict, expires_delta: timedelta = None):
#     to_encode = data.copy()
#     if expires_delta:
#         expire = datetime.utcnow() + expires_delta
#     else:
#         expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     to_encode.update({"exp": expire})
#     encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
#     return encoded_jwt

# # Function to verify token
# def verify_token(token: str):
#     payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#     return payload

# # MD5 hashing functions
# def md5_hash(password: str) -> str:
#     return hashlib.md5(password.encode()).hexdigest()

# def verify_md5_hash(plain_password: str, hashed_password: str) -> bool:
#     return md5_hash(plain_password) == hashed_password



# # Function to hash password using MD5
# # def hash_password_md5(password: str) -> str:
# #     return hashlib.md5(password.encode()).hexdigest()

# # Function to verify MD5 hashed password
# # def verify_password_md5(plain_password: str, hashed_password: str) -> bool:
# #     return hash_password_md5(plain_password) == hashed_password



from jose import jwt, JWTError,ExpiredSignatureError
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import hashlib
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from fastapi import Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from db import get_user_by_username


# Load environment variables from .env file
load_dotenv()

# Retrieve the secret key from environment variables
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is not set")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 300

#middleware to check authorization of a token
# class JWTAuthorizationMiddleware(BaseHTTPMiddleware):
#     async def dispatch(self,request:Request,call_next):
#         skip_validation_paths=["/login","/signup","/","/docs","/openapi.json"]
#         if request.url.path in skip_validationpaths:
#             response = await call_next(request)
#             return response
#         apiToken = request.headers.get('Authorization')



# class JWTBearer(HTTPBearer):
#     def __init__(self, auto_error: bool = True):
#         super(JWTBearer, self).__init__(auto_error=auto_error)
    
#     async def __call__(self, request: Request):
#         credentials: HTTPAuthorizationCredentials = await super(JWTBearer, self).__call__(request)
#         if credentials:
#             if not credentials.scheme == "Bearer":
#                 raise HTTPException(status_code=403, detail="Invalid authentication scheme.")
#             if not self.verify_jwt(credentials.credentials):
#                 raise HTTPException(status_code=403, detail="Invalid token or expired token.")
#             return credentials.credentials
#         else:
#             raise HTTPException(status_code=403, detail="Invalid authorization code.")
#     def verify_jwt(self, jwtoken: str) -> bool:
#         isTokenValid: bool = False

#         try:
#             payload = jwt.decode(jwtoken, SECRET_KEY, algorithms=[ALGORITHM])
#         except jwt.ExpiredSignatureError:
#             raise HTTPException(status_code=403, detail="Token expired.")
#         except jwt.InvalidTokenError:
#             raise HTTPException(status_code=403, detail="Invalid token.")
#         else:
#             isTokenValid = True
#         return isTokenValid

# Simple in-memory cache dictionary
cache = {}

cache_clear_secondes = 60*180
def cache_set(key, value, ttl_seconds=cache_clear_secondes):  # Default TTL of 1 hour
    expiration_time = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    cache[key] = (value, expiration_time)

def cache_get(key):
    if key in cache:
        value, expiration_time = cache[key]
        if expiration_time > datetime.utcnow():
            # print('found ins cache')
            return value
        else:
            del cache[key]  # Remove expired item from cache
    return None

#middleware to check authorization of a token
class JWTAuthorizationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request:Request,call_next):
        skip_validation_paths = ["/login","/signup","/","/docs","/openapi.json"]
        if request.url.path in skip_validation_paths:
            response = await call_next(request)
            return response
        apiToken = request.headers.get('Authorization')
        # if not apiToken:
        #   raise JSONResponse(status_code=401,content={'detail':'Unauthorized user'})
            
        try:
            decoded_token = jwt.decode(apiToken,SECRET_KEY,algorithms=[ALGORITHM])
            username = decoded_token.get('sub')
            # userinfo = await get_user_by_username(username)
            user = cache_get(username)
            if user is None:
                # print('checking in db')
                userinfo = await get_user_by_username(username)
                if not userinfo:
                    return JSONResponse(status_code=401,content={'detail':'Unauthorized user'})
                cache_set(username,userinfo)
        except ExpiredSignatureError:
            return JSONResponse(status_code=401,content={'detail':'Login Session Expired'})
        except JWTError:
            # print('jwterror')
            return JSONResponse(status_code=401,content={'detail':'unauthorized'})     
        except Exception as e:
            # Catch any other unexpected exceptions
            if not apiToken:
                return JSONResponse(status_code=401,content={'detail':'Unauthorized user'})
            
            return JSONResponse(status_code=500,content={'detail':str(e)})
        response = await call_next(request)
        return response

# Function to create access token
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Function to verify token
def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise ValueError(f"Token verification failed: {str(e)}")

# # MD5 hashing functions
# def md5_hash(password: str) -> str:
#     return hashlib.md5(password.encode()).hexdigest()

# def verify_md5_hash(plain_password: str, hashed_password: str) -> bool:
#     return md5_hash(plain_password) == hashed_password

# If you want to use these commented functions for hashing passwords
# def hash_password_md5(password: str) -> str:
#     return hashlib.md5(password.encode()).hexdigest()

# def verify_password_md5(plain_password: str, hashed_password: str) -> bool:
#     return hash_password_md5(plain_password) == hashed_password
