# fapi/utils/token.py
from jose import jwt, JWTError, ExpiredSignatureError
from fapi.core.config import SECRET_KEY, ALGORITHM

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except ExpiredSignatureError as e:
        # Raise so callers can convert to HTTP responses if needed
        raise e
    except JWTError as e:
        raise e
