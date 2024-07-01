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



from jose import jwt, JWTError
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import hashlib

# Load environment variables from .env file
load_dotenv()

# Retrieve the secret key from environment variables
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is not set")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

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

# MD5 hashing functions
def md5_hash(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()

def verify_md5_hash(plain_password: str, hashed_password: str) -> bool:
    return md5_hash(plain_password) == hashed_password

# If you want to use these commented functions for hashing passwords
# def hash_password_md5(password: str) -> str:
#     return hashlib.md5(password.encode()).hexdigest()

# def verify_password_md5(plain_password: str, hashed_password: str) -> bool:
#     return hash_password_md5(plain_password) == hashed_password
