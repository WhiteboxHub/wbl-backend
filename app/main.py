from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from models import UserCreate, UserLogin, UserPost, Token
from db import insert_user, get_user_by_username, verify_password, fetch_batch_recordings, fetch_keyword_recordings,fetch_keyword_presentation
from dotenv import load_dotenv
from auth import  create_access_token,verify_access_token
import os
from jose import JWTError, jwt
from datetime import datetime, timedelta

app = FastAPI()

load_dotenv()

# Secret key to encode the JWT token
SECRET_KEY = os.getenv('SECRET_KEY')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_by_username(username)
    if user is None:
        raise credentials_exception
    return user

@app.get("/recordings")
def get_recordings(batch: str = None, search: str = None):
    if batch:
        recording = fetch_batch_recordings(batch)
        if recording:
            return {"recording": recording}
        else:
            raise HTTPException(status_code=404, detail="No recording found for the given batch")
    
    if search:
        recording = fetch_keyword_recordings(search)
        if recording:
            return {"recording": recording}
        else:
            raise HTTPException(status_code=404, detail="No recording found for the given name")
    
    raise HTTPException(status_code=400, detail="No valid query parameter provided")





@app.get("/presentation")
def get_presentation(search: str = None):
    
    if search:
        presentation = fetch_keyword_presentation(search)
        if presentation:
            return {"presentation": presentation}
        else:
            raise HTTPException(status_code=404, detail="No Data found for the given name")
    
    raise HTTPException(status_code=400, detail="No valid query parameter provided")


@app.post("/signup")
def register_user(user_data: UserPost):
    return insert_user(**user_data.dict())

@app.post("/login", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_username(form_data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not verify_password(form_data.password, user[2]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user[1]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me")
def read_users_me(current_user: UserCreate = Depends(get_current_user)):
    return current_user




