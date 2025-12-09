
from fastapi import HTTPException, status
import time
from collections import defaultdict
from typing import Dict, Tuple

# Simple in-memory rate limiter (use Redis in production)
request_log: Dict[str, list] = defaultdict(list)

def check_rate_limit(identifier: str, max_requests: int, time_window: int):
    """
    Check if the request exceeds rate limit
    
    Args:
        identifier: IP address or user identifier
        max_requests: Maximum number of requests allowed
        time_window: Time window in seconds
    """
    current_time = time.time()
    
    # Clean old entries
    request_log[identifier] = [
        req_time for req_time in request_log[identifier] 
        if current_time - req_time < time_window
    ]
    
    # Check if rate limit exceeded
    if len(request_log[identifier]) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
    
    # Add current request
    request_log[identifier].append(current_time)

