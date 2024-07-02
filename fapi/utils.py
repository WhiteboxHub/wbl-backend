
import hashlib

# MD5 hashing functions

def md5_hash(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()

def verify_md5_hash(plain_password: str, hashed_password: str) -> bool:
    return md5_hash(plain_password) == hashed_password