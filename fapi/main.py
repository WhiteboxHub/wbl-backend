# from fapi.models import UserCreate, Token, UserRegistration,ContactForm
# from fapi.db import (
#     insert_user,get_user_by_username, verify_md5_hash, 
#     fetch_keyword_recordings, fetch_keyword_presentation, 
#     fetch_sessions_by_type,fetch_course_batches,fetch_subject_batch_recording,user_contact,course_content
# )
# from fapi.utils import md5_hash,verify_md5_hash
# from fapi.auth import create_access_token, verify_token,JWTAuthorizationMiddleware
# from fapi.utils import md5_hash
from models import UserCreate, Token, UserRegistration,ContactForm
from db import (
    insert_user,get_user_by_username, verify_md5_hash, 
    fetch_keyword_recordings, fetch_keyword_presentation, 
    fetch_sessions_by_type,fetch_course_batches,fetch_subject_batch_recording,user_contact,course_content
)
from utils import md5_hash,verify_md5_hash
from auth import create_access_token, verify_token,JWTAuthorizationMiddleware
from utils import md5_hash
from fastapi import FastAPI, Depends, HTTPException, status,Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from jose import JWTError
from typing import List
import os
from fastapi.responses import JSONResponse

# Load environment variables from .env file
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this list to include your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth2PasswordBearer instance
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# #applying middleware funcion
# app.add_middleware(JWTAuthorizationMiddleware)

# Function to authenticate user
async def authenticate_user(uname: str, passwd: str):
    user = await get_user_by_username(uname)
    if not user or not verify_md5_hash(passwd, user["passwd"]):
        return False
    
    if user["status"] != 'active':
        return "inactive"  # User status is not active
    
    return user


# Signup endpoint
@app.post("/signup")
async def register_user(user: UserRegistration):
    existing_user = await get_user_by_username(user.uname)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    
    hashed_password = md5_hash(user.passwd)
    await insert_user(
        uname=user.uname,
        passwd=hashed_password,
        dailypwd=user.dailypwd,
        team=user.team,
        level=user.level,
        instructor=user.instructor,
        override=user.override,
        status=user.status,
        lastlogin=user.lastlogin,
        logincount=user.logincount,
        fullname=user.fullname,
        phone=user.phone,
        address=user.address,
        city=user.city,
        Zip=user.Zip,
        country=user.country,
        message=user.message,
        registereddate=user.registereddate,
        level3date=user.level3date
    )
    return {"message": "User registered successfully"}


# Login endpoint
@app.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
    
    if user == "inactive":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="PLease Contact Recruiting '+1 925-557-1053' ",
            headers={"WWW-Authenticate": "Bearer"},
        )
    elif not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not a Valid User / Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # At this point, user should contain the user data if authentication is successful
    access_token = create_access_token(data={"sub": user["uname"]})
    return {"access_token": access_token, "token_type": "bearer"}


# Function to get the current user based on the token
async def get_current_user(token: str = Depends(oauth2_scheme)):
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
    except JWTError:
        raise credentials_exception
    user = await get_user_by_username(username)
    if user is None:
        raise credentials_exception
    return user


@app.get("/materials")
async def get_materials(course: str = Query(...), search: str = Query(...)):
    valid_courses = ["QA", "UI", "ML"]
    if course.upper() not in valid_courses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid course. Please select one of: QA, UI, ML"
        )

    try:
        data = await fetch_keyword_presentation(search, course)
        return JSONResponse(content=data)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    

# Token verification endpoint
@app.post("/verify_token")
async def verify_token_endpoint(token: Token):
    try:
        payload = verify_token(token.access_token)
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Fetch user details endpoint
@app.get("/user_dashboard")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user


# Sessions endpoint
@app.get("/sessions")
async def get_sessions(category: str = None):
    try:
        sessions = await fetch_sessions_by_type(category)
        if not sessions:
            raise HTTPException(status_code=404, detail="Sessions not found")
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


#End Point to get batches info based on the course input
@app.get("/batches")
async def get_batches(course:str=None):
    try:
        if not course:
            return {"details":"Course subject Expected","batches":[]}
        batches = await fetch_course_batches(course)
        return {"batches": batches}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# End Point to get Recodings of batches basd on subject and batch 
# and also covers search based on subject and search keyword


@app.get("/recording")
async def get_recordings(course:str=None,batchname:str=None,search:str=None):
    try:
        if not course:
            return {"Details":"subject expected"}
        if not batchname and not search:
            return {"details":"Batchname or Search Keyword expected"}
        if search:
            recording = await fetch_keyword_recordings(course,search)
            # print('search started')
            recording = await fetch_keyword_recordings(course,search)
            return {"batch_recordings": recording}
        recordings = await fetch_subject_batch_recording(course,batchname)
        return {"batch_recordings": recordings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/contact")
async def contact(user: ContactForm):
        
    await user_contact(
        name=user.name,
        email=user.email,
        phone=user.phone,
        message=user.message
        
        )
    return {"detail": "Message Sent Successfully"}


@app.get("/coursecontent")
def get_course_content():
    content = course_content()
    return {"coursecontent": content}



