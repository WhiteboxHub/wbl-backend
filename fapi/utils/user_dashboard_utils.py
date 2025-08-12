# fapi/utils/user_dashboard_utils.py
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, ExpiredSignatureError

from fapi.db.database import SessionLocal
from fapi.db.models import AuthUserORM
from fapi.utils.token_utils import verify_token  

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_by_username(db: Session, username: str):
   
    return db.query(AuthUserORM).filter(AuthUserORM.uname == username).first()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = verify_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except ExpiredSignatureError:
        # token expired
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login Session Expired")
    except JWTError:
        raise credentials_exception

    user = get_user_by_username(db, username)
    if user is None:
        raise credentials_exception

    return user
