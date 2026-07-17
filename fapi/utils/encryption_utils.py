from cryptography.fernet import Fernet
from fapi.core.config import ENCRYPTION_KEY
import logging

logger = logging.getLogger(__name__)

# Use a default key for development if none provided, 
# but strongly recommend setting it in .env
DEFAULT_KEY = b'HIizg-wNBLUCcw5JjCA8JVGKu0WE5Omst8gI59UMqEc='

def get_fernet():
    key = ENCRYPTION_KEY.encode() if ENCRYPTION_KEY else DEFAULT_KEY
    try:
        return Fernet(key)
    except Exception as e:
        logger.error(f"Error initializing Fernet: {e}")
        # If key is invalid, fallback to default key for safety during dev
        return Fernet(DEFAULT_KEY)

def encrypt_api_key(api_key: str) -> str:
    """Encrypts a string using AES (Fernet)."""
    if not api_key:
        return ""
    f = get_fernet()
    return f.encrypt(api_key.encode()).decode()

def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypts an encrypted string."""
    if not encrypted_key:
        return ""
    f = get_fernet()
    try:
        return f.decrypt(encrypted_key.encode()).decode()
    except Exception as e:
        # Fallbacks: try DEFAULT_KEY and the alternative key
        fallbacks = [
            DEFAULT_KEY,
            b'7aqK1zhMEO0AF08ewGf1tL6nqY9kA9v8_E00MlsNjLw='
        ]
        for key in fallbacks:
            try:
                fallback_f = Fernet(key)
                return fallback_f.decrypt(encrypted_key.encode()).decode()
            except Exception:
                continue
        logger.error(f"Decryption failed: {e}")
        return "DECRYPTION_FAILED"
