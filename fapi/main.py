# wbl-backend/fapi/main.py
from fapi.db.models import EmailRequest, UserCreate, Token, ResetPasswordRequest, ResetPassword , LeadORM
from  fapi.db.database import (
     verify_md5_hash,
 update_user_password , update_user_password
)
from typing import Dict, Any
from  fapi.utils.auth_utils import md5_hash, verify_md5_hash, create_reset_token, verify_reset_token
from fapi.utils.token_utils import verify_token
from  fapi.auth import create_access_token,  JWTAuthorizationMiddleware, generate_password_reset_token, get_password_hash,verify_password_reset_token,determine_user_role
from  fapi.mail.templets.contactMailTemplet import ContactMail_HTML_templete
from  fapi.utils.email_utils import send_reset_password_email ,send_request_demo_emails,send_contact_emails,send_email_to_user
from fastapi import FastAPI, Depends, HTTPException, Request, status, Query, Body ,APIRouter, status as http_status,Path
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm,HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from jose import JWTError, ExpiredSignatureError
from typing import List, Optional, Dict, Any
import os
from fastapi.responses import JSONResponse
import smtplib
from mysql.connector import Error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date,datetime, timedelta
import jwt
from sqlalchemy.orm import Session
from fapi.db.database import Base, engine
from fapi.api.routes import candidate, leads, google_auth, talent_search, user_role,  contact, login, register, request_demo, unsubscribe, user_dashboard
from fastapi import Query, Path
# from fapi.db.models import VendorResponse
from fapi.db.database import db_config
from typing import Dict, Any
from fastapi import FastAPI, Query, Path
from fapi.core.config import SECRET_KEY, ALGORITHM, limiter
from fapi.db.database import SessionLocal




load_dotenv()

Base.metadata.create_all(bind=engine)
app = FastAPI()



app.include_router(candidate.router, prefix="/api", tags=["Candidate Marketing & Placements"])
app.include_router(unsubscribe.router, tags=["Unsubscribe"])
app.include_router(leads.router, prefix="/api", tags=["Leads"])
app.include_router(google_auth.router, prefix="/api", tags=["Google Authentication"])
app.include_router(talent_search.router, prefix="/api", tags=["Talent Search"])
app.include_router(user_role.router, prefix="/api", tags=["User Role"])
app.include_router(login.router, prefix="/api", tags=["Login"])
app.include_router(contact.router, prefix="/api", tags=["Contact"])
app.include_router(register.router, prefix="/api", tags=["Register"])
app.include_router(request_demo.router, prefix="/api", tags=["Request Demo"])
app.include_router(user_dashboard.router, prefix="/api", tags=["User Dashboard"])



def get_db():
    db.database = SessionLocal()
    try:
        yield db
    finally:
        db.close()


router = APIRouter()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,

    allow_origins=["https://whitebox-learning.com", "https://www.whitebox-learning.com", "http://whitebox-learning.com", "http://www.whitebox-learning.com","http://localhost:3000"],  # Adjust this list to include your frontend URL

    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth2PasswordBearer instance
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")





# # -----------------------------------------------------------------------------------------------------


# @app.get("/api/placements", response_model=List[RecentPlacement])
# async def get_recent_placements():
#     placements = await fetch_recent_placements()
#     return placements




# Function to get the current user based on the token
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


# Token verification endpoint
@app.post("/api/verify_token")
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

# # Fetch user details endpoint
# @app.get("/api/user_dashboard")
# async def read_users_me(current_user: dict = Depends(get_current_user)):
#     return current_user




@app.post("/api/forget-password")
async def forget_password(request: ResetPasswordRequest):
    user = await get_user_by_username(request.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    token = create_reset_token(user["uname"])
    await send_reset_password_email(user["uname"], token)
    return JSONResponse(content={"message": "Password reset link has been sent to your email", "token": token})



@app.post("/api/reset-password")
async def reset_password(data: ResetPassword):
    email = verify_reset_token(data.token)
    if email is None:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    await update_user_password(email, data.new_password)
    return {"message": "Password updated successfully"}

