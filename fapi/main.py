from models import EmailRequest, UserCreate, Token, UserRegistration, ContactForm, ResetPasswordRequest, ResetPassword ,GoogleUserCreate 
from db import (
      fetch_sessions_by_type, fetch_types, insert_login_history, insert_user, get_user_by_username, update_login_info, verify_md5_hash,
    fetch_keyword_recordings, fetch_keyword_presentation,
 fetch_course_batches, fetch_subject_batch_recording, user_contact, course_content, fetch_candidate_id_by_email,
    unsubscribe_user, update_user_password ,get_user_by_username, update_user_password ,insert_user,get_google_user_by_email,insert_google_user_db,fetch_candidate_id_by_email
)
from utils import md5_hash, verify_md5_hash, create_reset_token, verify_reset_token
from auth import create_access_token, verify_token, JWTAuthorizationMiddleware, generate_password_reset_token, verify_password_reset_token, get_password_hash ,create_google_access_token
from contactMailTemplet import ContactMail_HTML_templete
from mail_service import send_reset_password_email
from fastapi import FastAPI, Depends, HTTPException, Request, status, Query, Body ,APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from jose import JWTError
from typing import List, Optional
import os
from fastapi.responses import JSONResponse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import jwt


# Load environment variables from .env file
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

router = APIRouter()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://whitebox-learning.com", "https://www.whitebox-learning.com", "http://whitebox-learning.com", "http://www.whitebox-learning.com"],  # Adjust this list to include your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth2PasswordBearer instance
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# Load environment variables from .env file
load_dotenv()

# Retrieve the secret key from environment variables
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is not set")
ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 720

# app.add_middleware(JWTAuthorizationMiddleware)

# ------------------------------------------------------------------------------------
# @app.post("/api/google_users/")
# async def register_google_user(user: GoogleUserCreate):
#     existing_user = await get_google_user_by_email(user.email)
#     if existing_user:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

#     await insert_google_user_db(email=user.email, name=user.name, google_id=user.google_id)
#     return {"message": "Google user registered successfully!"}


# @app.post("/api/google_login/")
# async def login_google_user(user: GoogleUserCreate):
#     existing_user = await get_google_user_by_email(user.email)
#     if existing_user is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
#     if existing_user['status'] == 'inactive':
#         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive account. Please contact admin.")

#     # Generate token upon successful login
#     token_data = {
#         "sub": existing_user['uname'],
#         "name": existing_user['fullname'],
#         "google_id": existing_user['googleId'],
#     }
#     access_token = create_google_access_token(data=token_data)

#     return {
#         "access_token": access_token,
#         "token_type": "bearer"
#     }


@app.post("/api/check_user/")
async def check_user_exists(user: GoogleUserCreate):
    existing_user = await get_google_user_by_email(user.email)
    if existing_user:
        return {"exists": True, "status": existing_user['status']}
    return {"exists": False}


@app.post("/api/google_users/")
async def register_google_user(user: GoogleUserCreate):
    existing_user = await get_google_user_by_email(user.email)
    
    if existing_user:
        if existing_user['status'] == 'active':
            return {"message": "User already registered and active, please log in."}
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive account. Please contact admin.")

    await insert_google_user_db(email=user.email, name=user.name, google_id=user.google_id)
    return {"message": "Google user registered successfully!"}

@app.post("/api/google_login/")
async def login_google_user(user: GoogleUserCreate):
    existing_user = await get_google_user_by_email(user.email)
    if existing_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if existing_user['status'] == 'inactive':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive account. Please contact admin.")

    # Generate token upon successful login
    token_data = {
        "sub": existing_user['uname'],
        "name": existing_user['fullname'],
        "google_id": existing_user['googleId'],
    }   
    
    access_token = create_google_access_token(data=token_data)
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@app.post("/api/verify_google_token/")
async def verify_google_token(token: str):
    try:
        # Remove extra quotes from token if present
        if token.startswith('"') and token.endswith('"'):
            token = token[1:-1]
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

# ------------------------------------------------------------------------------------

async def authenticate_user(uname: str, passwd: str):
    user = await get_user_by_username(uname)
    if not user or not verify_md5_hash(passwd, user["passwd"]):
        return None

    if user["status"] != 'active':
        return "inactive"  # User status is not active

    # Fetch candidateid from the candidate table
    candidate_info = await fetch_candidate_id_by_email(uname)
    candidateid = candidate_info["candidateid"] if candidate_info else "Candidate ID not present"
    return {**user, "candidateid": candidateid}
    # return user

@app.post("/api/signup")
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
        level3date=user.level3date,
        candidate_info={
            'name': user.fullname,
            'enrolleddate': user.registereddate,
            'email': user.uname,
            'phone': user.phone,
            'address': user.address,
            'city': user.city,
            'country': user.country,
            'zip': user.Zip,
            'status': user.status
        }
    )
    return {"message": "User registered successfully"}

@app.post("/api/login", response_model=Token)
async def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
    if user == "inactive":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive Account !! Please Contact Recruiting '+1 925-557-1053'",
            headers={"WWW-Authenticate": "Bearer"},
        )
    elif not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not a Valid User / Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Ensure user is a dictionary
    if not isinstance(user, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid user object returned from authentication",
        )
    useragent = request.headers.get('User-Agent', '')

    # Update login count and last login timestamp
    # print(user)
    await update_login_info(user["id"])

    # Insert login history
    await insert_login_history(user["id"], request.client.host, useragent)

    # Create token payload with candidateid
    # access_token = create_access_token(data={"sub": user["uname"]})

 # Create token payload with candidateid
    access_token = create_access_token(data={"sub": user["uname"], "candidateid": user["candidateid"]})

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

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

@app.get("/api/materials")
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


# Fetch user details endpoint
@app.get("/api/user_dashboard")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user


# # Sessions endpoint#######################old code
# @app.get("/api/sessions")
# async def get_sessions(category: str = None):
#     try:
#         sessions = await fetch_sessions_by_type(category)
#         if not sessions:
#             raise HTTPException(status_code=404, detail="Sessions not found")
#         return {"sessions": sessions}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
################################################newly added ######################################
# Fetch types from the new_session table


# Fetch sessions by course and type
# @app.get("/api/sessions")
# async def get_sessions(course_id: str = None, session_type: str = None):
#     try:
#         # Call the function to fetch sessions by the provided course and session type
#         sessions = await fetch_sessions_by_type(course_id, session_type)
#         if not sessions:
#             raise HTTPException(status_code=404, detail="Sessions not found")
#         return {"sessions": sessions}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/session-types")
async def get_types():
    try:
        types = await fetch_types()
        if not types:
            raise HTTPException(status_code=404, detail="Types not found")
        return {"types": types}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
@app.get("/api/sessions")
async def get_sessions(course_name: Optional[str] = None, session_type: Optional[str] = None):
    try:
        # Local mapping of course names to course IDs for this endpoint only
        course_name_to_id = {
            "QA": 1,
            "UI": 2,
            "ML": 3,
            
        }

        # Validate and map course_name to course_id
        if course_name:
            course_id = course_name_to_id.get(course_name.upper())  # Ensure case-insensitivity
            if not course_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid course name: {course_name}. Valid values are QA, UI, ML."
                )
        else:
            course_id = None  # If course_name is not provided, no filtering on course_id

        # Call the function to fetch sessions by the provided course_id and session_type
        sessions = await fetch_sessions_by_type(course_id, session_type)
        if not sessions:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessions not found")
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    

###########################################################################

# End Point to get batches info based on the course input
@app.get("/api/batches")
async def get_batches(course: str = None):
    try:
        if not course:
            return {"details": "Course subject Expected", "batches": []}
        batches = await fetch_course_batches(course)
        return {"batches": batches}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recording")
async def get_recordings(course: str = None, batchid: int = None, search: str = None):
    try:
        if not course:
            return {"details": "Course expected"}
        if not batchid and not search:
            return {"details": "Batchid or Search Keyword expected"}
        if search:
            recordings = await fetch_keyword_recordings(course, search)
            if not recordings:
                raise HTTPException(status_code=404, detail="No recordings found for the provided search keyword.")
            return {"batch_recordings": recordings}
        recordings = await fetch_subject_batch_recording(course, batchid)
        if not recordings:
            raise HTTPException(status_code=404, detail="No recordings found for the provided course and batch.")
        return {"batch_recordings": recordings}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/contact")
async def contact(user: ContactForm):
        
    await user_contact(
        name=user.name,
        email=user.email,
        phone=user.phone,
        message=user.message        
        )
    def sendEmail():
        from_Email = os.getenv('EMAIL_USER')
        password = os.getenv('EMAIL_PASS')
        to_email = os.getenv('TO_RECRUITING_EMAIL')
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = os.getenv('SMTP_PORT')
        html_content = ContactMail_HTML_templete(user.name,user.email,user.phone,user.message)
        msg = MIMEMultipart()
        msg['From'] = from_Email
        msg['To'] = to_email
        msg['Subject'] = 'WBL Contact lead generated'
        msg.attach(MIMEText(html_content, 'html'))
        try:
            # server = smtplib.SMTP('smtp.gmail.com',587)
            server = smtplib.SMTP(smtp_server, int(smtp_port))
            server.starttls()
            server.login(from_Email,password)
            text = msg.as_string()
            server.sendmail(from_Email,to_email,text)
            server.quit()
        except Exception as e:
            raise HTTPException(status_code=500, detail='Erro while sending the mail to recruiting teams')
    sendEmail()
    return {"detail": "Message Sent Successfully Our Team will Reachout to you"}


@app.get("/api/coursecontent")
def get_course_content():
    content = course_content()
    return {"coursecontent": content}

@app.put("/api/unsubscribe")
def unsubscribe(request: EmailRequest):
    status, message = unsubscribe_user(request.email)
    if status:
        return {"message": message}
    else:
        raise HTTPException(status_code=404, detail=message)

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
