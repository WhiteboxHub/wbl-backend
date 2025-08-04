import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get secret values from environment
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is not set")

ALGORITHM = os.getenv("ALGORITHM", "HS256")
if not ALGORITHM:
    raise ValueError("ALGORITHM environment variable is not set")

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440))  # Defaults to 1440 if not set
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES  = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", 15))
# ACCESS_TOKEN_EXPIRE_MINUTES = 720