# from fastapi import FastAPI, Depends, HTTPException, status
# from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
# from models import UserCreate, Token, UserRegistration
# from fastapi.middleware.cors import CORSMiddleware
# from db import insert_user,fetch_batches, get_user_by_username, verify_md5_hash, fetch_batch_recordings, fetch_keyword_recordings, fetch_keyword_presentation,fetch_sessions_by_type
# # from auth import create_access_token, verify_token, md5_hash,hash_password_md5, verify_password_md5
# from auth import create_access_token, verify_token, md5_hash
# from dotenv import load_dotenv
# from jose import JWTError
# from typing import List
# import os
# # from passlib.context import CryptContext

# # Load environment variables from .env file
# load_dotenv()

# # Initialize FastAPI app
# app = FastAPI()

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # Adjust this list to include your frontend URL
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # OAuth2PasswordBearer instance
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
# # pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# # Function to authenticate user
# async def authenticate_user(uname: str, passwd: str):
#     user =await get_user_by_username(uname)
#     if not user or not verify_md5_hash(passwd, user["passwd"]):
#         return False
#     return user

# # Signup endpoint
# @app.post("/signup")
# async def register_user(user: UserRegistration):
#     existing_user =await get_user_by_username(user.uname)
#     # if (existing_user):
#     if existing_user:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
#     hashed_password = md5_hash(user.passwd)
#     # hashed_password = hash_password_md5(user.passwd)

#     await insert_user(
#         uname=user.uname,
#         passwd=hashed_password,
#         dailypwd=user.dailypwd,
#         team=user.team,
#         level=user.level,
#         instructor=user.instructor,
#         override=user.override,
#         status=user.status,
#         lastlogin=user.lastlogin,
#         logincount=user.logincount,
#         fullname=user.fullname,
#         phone=user.phone,
#         address=user.address,
#         city=user.city,
#         Zip=user.Zip,
#         country=user.country,
#         message=user.message,
#         registereddate=user.registereddate,
#         level3date=user.level3date
#     )
#     return {"message": "User registered successfully"}

# # Login endpoint
# @app.post("/login", response_model=Token)
# async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    
#     user = await authenticate_user(form_data.username, form_data.password)
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Not a Valid User / Incorrect username or password",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
#     access_token = create_access_token(data={"sub": user["uname"]})
#     return {"access_token": access_token, "token_type": "bearer"}

# # Function to get the current user based on the token
# async def get_current_user(token: str = Depends(oauth2_scheme)):
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
    
#     try:
#         payload = verify_token(token)
#         username: str = payload.get("sub")
#         if username is None:
#             raise credentials_exception
#     except JWTError:
#         raise credentials_exception
#     user = await get_user_by_username(username)
#     if user is None:
#         raise credentials_exception
#     return user

# @app.get("/recording")
# async def get_recordings(batchname: str = None, search: str = None, current_user: dict = Depends(get_current_user)):
# # async def get_recordings(batchname: str = None, search: str = None):
#     # print(current_user)
#     try:
#         batches = fetch_batches()  # Fetch all batch names regardless of whether batchname is provided or not
        
#         if batchname:
#             # Fetch all recordings for a specific batch if batchname is provided
#             batch_recordings = fetch_batch_recordings(batchname)
#             if not batch_recordings:
#                 raise HTTPException(status_code=404, detail="Batch recordings not found")
#         else:
#             batch_recordings = None  # Set batch_recordings to None if batchname is not provided
        
#         if search:
#             # Fetch recordings based on keyword search
#             recording = fetch_keyword_recordings(search)
#             if recording:
#                 return {"batches": batches, "batch_recordings": batch_recordings, "recording": recording}
#             else:
#                 raise HTTPException(status_code=404, detail="No recording found for the given name")

#         return {"batches": batches, "batch_recordings": batch_recordings}

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# # @app.get("/recordings")
# # async def get_recordings(batch: str = None, search: str = None):
# #     if batch:
# #         recording = await fetch_batch_recordings(batch)
# #         if recording:
# #             return {"recording": recording}
# #         else:
# #             raise HTTPException(status_code=404, detail="No recording found for the given batch")

# #     if search:
# #         recording = await fetch_keyword_recordings(search)
# #         if recording:
# #             return {"recording": recording}
# #         else:
# #             raise HTTPException(status_code=404, detail="No recording found for the given name")

# #     raise HTTPException(status_code=400, detail="No valid query parameter provided")

# # @app.get("/batches")
# # async def get_batches(batchname: str = None):
# #     try:
# #         if batchname:
# #             # Fetch all recordings for a specific batch
# #             batch_recordings = await fetch_batch_recordings(batchname)
# #             if batch_recordings:
# #                 return {"batch_recordings": batch_recordings}
# #             else:
# #                 raise HTTPException(status_code=404, detail="Batch recordings not found")
# #         else:
# #             # Fetch only batch names
# #             batches = await fetch_keyword_batch()
# #             return {"batches": batches}

# #     except Exception as e:
# #         raise HTTPException(status_code=500, detail=str(e))




# @app.get("/presentation")
# async def get_presentation(search: str = None, current_user: dict = Depends(get_current_user)):
# # async def get_presentation(search: str = None ):
#     if search:
#         presentation =await fetch_keyword_presentation(search)
#         if presentation:
#             return {"presentation": presentation}
#         else:
#             raise HTTPException(status_code=404, detail="No Data found for the given name")
#     raise HTTPException(status_code=400, detail="No valid query parameter provided")


# # Token verification endpoint
# @app.post("/verify_token")
# async def verify_token_endpoint(token: Token):
#     try:
#         payload = verify_token(token.access_token)
#         return payload
#     except JWTError:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid token",
#             headers={"WWW-Authenticate": "Bearer"},
#         )


# # Fetch user details endpoint
# @app.get("/user_dashboard")
# async def read_users_me(current_user: dict = Depends(get_current_user)):
#     return current_user


# @app.get("/sessions/")
# async def get_sessions(category: str):
#     try:
#         sessions = await fetch_sessions_by_type(category)
#         if not sessions:
#             raise HTTPException(status_code=404, detail="Sessions not found")
#         return {"sessions": sessions}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))




from fastapi import FastAPI, Depends, HTTPException, status,Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from models import UserCreate, Token, UserRegistration
from fastapi.middleware.cors import CORSMiddleware
from db import (
    insert_user, fetch_batches, get_user_by_username, 
    fetch_batch_recordings, fetch_keyword_recordings, fetch_keyword_presentation, 
    fetch_sessions_by_type,fetch_course_batches,fetch_subject_batch_recording
)
from auth import create_access_token, verify_token,JWTAuthorizationMiddleware
from utils import md5_hash, verify_md5_hash
from dotenv import load_dotenv
from jose import JWTError
from typing import List
import os

# from auth import JWTBearer
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

# Function to authenticate user
async def authenticate_user(uname: str, passwd: str):
    user = await get_user_by_username(uname)
    if not user or not verify_md5_hash(passwd, user["passwd"]):
        return False
    return user

#applying middleware funcion
# app.add_middleware(JWTAuthorizationMiddleware)

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
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not a Valid User / Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
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

# Recordings endpoint
# @app.get("/recording",dependencies=[Depends(JWTBearer())])
@app.get("/recording")
# async def get_recordings(batchname: str = None, search: str = None, current_user: dict = Depends(get_current_user)):
async def get_recordings(subject:str=None,batchname: str = None, search: str = None):
    try:
        batches = await fetch_course_batches(subject)  # Fetch all batch names regardless of whether batchname is provided or not
        if search:
            recording = await fetch_keyword_recordings(search)
            if recording:
                return {"batches": batches, "batch_recordings": batch_recordings, "recording": recording}
            else:
                raise HTTPException(status_code=204, detail="No recording found for the given name")
        
        if batchname:
            batch_recordings = await fetch_subject_batch_recording(subject,batchname)
            # if not batch_recordings:
            #     raise HTTPException(status_code=204, detail="no data found")
            return {"batches": batches, "batch_recordings": batch_recordings}
        else:
            batch_recordings = await fetch_subject_batch_recording(subject,batches[0]['batchname'])

        return {"batches": batches, "batch_recordings": batch_recordings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Presentation endpoint
@app.get("/presentation")
# async def get_presentation(search: str = None, current_user: dict = Depends(get_current_user)):
async def get_presentation(search: str = None):
    if search:
        presentation = await fetch_keyword_presentation(search)
        if presentation:
            return {"presentation": presentation}
        else:
            raise HTTPException(status_code=404, detail="No Data found for the given name")
    raise HTTPException(status_code=400, detail="No valid query parameter provided")

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
# @app.get("/sessions")
# async def get_sessions(category: str):
#     try:
#         sessions = await fetch_sessions_by_type(category)
#         if not sessions:
#             raise HTTPException(status_code=404, detail="Sessions not found")
#         return {"sessions": sessions}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


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
@app.get("/getrecordings")
async def get_recordings(subject:str=None,batchname:str=None,search:str=None):
    try:
        if not subject:
            return {"Details":"subject expected"}
        if not batchname and not search:
            return {"details":"Batchname or Search Keyword expected"}
        if search:
            recording = await fetch_keyword_recordings(subject,search)
            return {"batch_recordings": recording}
            
        recordings = await fetch_subject_batch_recording(subject,batchname)
        return {"batch_recordings": recordings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
