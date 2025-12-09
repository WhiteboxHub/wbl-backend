
# fapi/utils/captcha_utils.py
import os
import requests
from fastapi import HTTPException, status

RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"

def verify_recaptcha_token(captcha_token: str) -> bool:
    """
    Verify reCAPTCHA token (v2 checkbox) with Google.
    Raises HTTPException on error.
    """
    if not captcha_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CAPTCHA token is required")

    secret_key = os.getenv("RECAPTCHA_SECRET_KEY")
    if not secret_key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="RECAPTCHA_SECRET_KEY not configured")

    try:
        resp = requests.post(RECAPTCHA_VERIFY_URL, data={
            "secret": secret_key,
            "response": captcha_token
        }, timeout=10)
        data = resp.json()
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail="CAPTCHA verification timeout")
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="CAPTCHA verification failed")

    # Example response:
    # { "success": true|false, "challenge_ts": "...", "hostname": "...", "error-codes": [...] }
    if not data.get("success", False):
        # Map common error codes to messages
        codes = data.get("error-codes", [])
        if "invalid-input-secret" in codes:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid CAPTCHA secret key")
        if "missing-input-response" in codes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CAPTCHA token missing")
        if "invalid-input-response" in codes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid CAPTCHA token")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CAPTCHA verification failed")

    # Optionally: check data.get("hostname") matches your domain in production
    return True
