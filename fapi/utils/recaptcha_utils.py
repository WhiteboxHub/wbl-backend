
import httpx
from os import getenv
from typing import Dict, Any


class ReCAPTCHAVerificationError(Exception):
    pass


async def verify_recaptcha_token(token: str) -> Dict[str, Any]:
    secret_key = getenv("RECAPTCHA_SECRET_KEY")

    if not secret_key:
        raise ReCAPTCHAVerificationError("RECAPTCHA_SECRET_KEY not configured")

    if not token:
        raise ReCAPTCHAVerificationError("No reCAPTCHA token provided")

    url = "https://www.google.com/recaptcha/api/siteverify"
    payload = {
        "secret": secret_key,
        "response": token,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, data=payload)

        result = response.json()

        if not result.get("success", False):
            error_codes = result.get("error-codes", [])
            raise ReCAPTCHAVerificationError(
                f"reCAPTCHA failed: {', '.join(error_codes) if error_codes else 'Unknown error'}"
            )

        return {
            "success": True,
            "challenge_ts": result.get("challenge_ts", ""),
            "hostname": result.get("hostname", ""),
        }

    except httpx.RequestError as e:
        raise ReCAPTCHAVerificationError(f"reCAPTCHA API error: {str(e)}")
