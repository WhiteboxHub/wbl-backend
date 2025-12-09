


from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from fapi.utils.captcha_utils import verify_recaptcha
import json

class CaptchaMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip CAPTCHA for non-POST requests or specific paths
        if request.method != "POST" or request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
        
        # Check if this is a route that requires CAPTCHA
        captcha_routes = ["/signup", "/contact"]
        if request.url.path in captcha_routes:
            try:
                # Read request body
                body = await request.body()
                
                # Parse JSON to get CAPTCHA token
                if body:
                    data = json.loads(body)
                    captcha_token = data.get("captcha_token")
                    
                    if not captcha_token:
                        raise HTTPException(status_code=400, detail="CAPTCHA token required")
                    
                    # Verify CAPTCHA
                    action = "signup" if request.url.path == "/signup" else "contact"
                    await verify_recaptcha(captcha_token, action)
                
                # Reset request body for the next middleware/route
                request._body = body
                
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON")
        
        return await call_next(request)
