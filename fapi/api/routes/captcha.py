
# wbl-backend\fapi\api\routes\captcha.py
from fastapi import Depends, HTTPException, status
from fapi.utils.captcha_utils import verify_recaptcha
from typing import Optional

async def verify_captcha_dependency(
    captcha_token: str,
    expected_action: Optional[str] = None
):
    """
    Dependency to verify CAPTCHA token
    """
    await verify_recaptcha(captcha_token, expected_action)
    return True