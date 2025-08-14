# wbl-backend/fapi/auth/autils.py
import hashlib
import jwt
import os
from datetime import datetime, timedelta
from fapi.core.config import SECRET_KEY, ALGORITHM


# MD5 hashing functions

def md5_hash(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()

def verify_md5_hash(plain_password: str, hashed_password: str) -> bool:
    return md5_hash(plain_password) == hashed_password

def update_password(new_password: str) -> str:
    """Hashes the new password using MD5 and returns the hashed password."""
    return md5_hash(new_password)

def check_password_strength(password: str) -> bool:
    """Check if the password meets certain strength criteria (e.g., length, complexity)."""
    # Example criteria: at least 8 characters long
    return len(password) >= 8


def create_reset_token(email: str):
    expiration = datetime.utcnow() + timedelta(hours=1)
    to_encode = {"sub": email, "exp": expiration}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_reset_token(token: str):
    try:
        decoded_jwt = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return decoded_jwt["sub"]
    except jwt.ExpiredSignatureError:
        return None

def hash_password(password: str):
    return md5_hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return verify_md5_hash(plain_password, hashed_password)
