from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from models import UserCreate, UserLogin, UserPost, Token
from db import insert_user, fetch_resources,  get_user_by_username, verify_password, fetch_batch_recordings, fetch_keyword_recordings
from dotenv import load_dotenv
import os

app = FastAPI()

load_dotenv()


@app.get("/recordings")
def get_recordings(batch: str = None,  search: str = None):
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




