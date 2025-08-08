# wbl-backend/fapi/main.py
from fapi.db.models import EmailRequest, UserCreate, Token, UserRegistration, ContactForm, ResetPasswordRequest, ResetPassword , VendorCreate , RecentPlacement , RecentInterview,Candidate, CandidateCreate, CandidateUpdate,LeadORM, TalentSearch
from  fapi.db.database import (
      fetch_sessions_by_type, fetch_types,fetch_candidates, insert_login_history, insert_user, get_user_by_username, update_login_info, verify_md5_hash,
    fetch_keyword_recordings, fetch_keyword_presentation,fetch_interviews_by_name,insert_interview,delete_interview,update_interview,
 fetch_course_batches, fetch_subject_batch_recording, user_contact, course_content, fetch_candidate_id_by_email,fetch_interview_by_id,
    unsubscribe_user, update_user_password ,get_user_by_username, update_user_password ,insert_user,fetch_candidate_id_by_email,insert_vendor ,fetch_recent_placements , fetch_recent_interviews,insert_lead_new
)
from typing import Dict, Any
from  fapi.utils.auth_utils import md5_hash, verify_md5_hash, create_reset_token, verify_reset_token
from  fapi.auth import create_access_token, verify_token, JWTAuthorizationMiddleware, generate_password_reset_token, verify_password_reset_token, get_password_hash ,determine_user_role
from  fapi.mail.templets.contactMailTemplet import ContactMail_HTML_templete
from  fapi.utils.email_utils import send_reset_password_email ,send_request_demo_emails,send_contact_emails,send_email_to_user
from fastapi import FastAPI, Depends, HTTPException, Request, status, Query, Body ,APIRouter, status as http_status,Path
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm,HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from jose import JWTError
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
from fapi.api.routes import candidate, leads, google_auth,vendor_contact ,vendor, vendor_activity
from fastapi import FastAPI,Query, Path
from slowapi import Limiter
from slowapi.util import get_remote_address
from fapi.db.models import VendorResponse
from fapi.db.database import db_config
from typing import Dict, Any
from fapi.core.config import SECRET_KEY, ALGORITHM


load_dotenv()

Base.metadata.create_all(bind=engine)
app = FastAPI()

app.include_router(candidate.router, prefix="/api", tags=["Candidate Marketing & Placements"])
app.include_router(leads.router, prefix="/api", tags=["Leads"])
app.include_router(google_auth.router, prefix="/api", tags=["Google Authentication"])
app.include_router(vendor_contact.router, prefix="/api", tags=["Vendor Contact Extracts"])
app.include_router(vendor.router, prefix="/api", tags=["Vendor"])
app.include_router(vendor_activity.router, prefix="/api", tags=["DailyVendorActivity"])

def get_db():
    db.database = SessionLocal()
    try:
        yield db
    finally:
        db.close()

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

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



# ----------------------------------- Avatar --------------------------------------
security = HTTPBearer()

@app.get("/api/user_role")
async def get_user_role(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
    except (ExpiredSignatureError, JWTError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    userinfo = await get_user_by_username(username)
    if not userinfo:
        raise HTTPException(status_code=404, detail="User not found")

    role = determine_user_role(userinfo)

    return {"role": role}


def determine_user_role(userinfo):
    email = userinfo.get("uname") or userinfo.get("email") or ""
    team = (userinfo.get("team") or "").lower()

    if (
        team == "admin"
        or "whitebox-learning" in email
        or "innova-path" in email
        or email == "admin"
    ):
        return "admin"

    return "candidate"

# # -----------------------------------------------------------------------------------------------------


@app.get("/api/placements", response_model=List[RecentPlacement])
async def get_recent_placements():
    placements = await fetch_recent_placements()
    return placements



@app.get("/api/interviews", response_model=List[dict])
async def get_interviews(limit: int = 10, offset: int = 0):
    return await fetch_recent_interviews(limit, offset)

@app.get("/api/interviews/{interview_id}", response_model=dict)
async def get_interview_by_id(interview_id: int):
    interview = await fetch_interview_by_id(interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    return interview

@app.get("/api/interviews/name/{candidate_name}", response_model=List[dict])
async def get_interview_by_name(candidate_name: str):
    return await fetch_interviews_by_name(candidate_name)

@app.post("/api/interviews")
async def create_interview(data: RecentInterview):
    await insert_interview(data)
    return {"message": "Interview created successfully"}

@app.put("/api/interviews/{interview_id}")
async def update_interview_api(interview_id: int, data: RecentInterview):
    existing = await fetch_interview_by_id(interview_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Interview not found")
    await update_interview(interview_id, data)
    return {"message": "Interview updated successfully"}

@app.delete("/api/interviews/{interview_id}")
async def remove_interview(interview_id: int):
    await delete_interview(interview_id)
    return {"message": "Interview deleted successfully"}



# -------------------------------------------------------- IP -----------------------------------------


@app.post("/api/request-demo")
async def create_vendor_request_demo(vendor: VendorCreate):
    try:
        vendor_data = vendor.dict()
        vendor_data["type"] = "IP_REQUEST_DEMO"  # force the type value

        await insert_vendor(vendor_data)

        # Trigger emails after saving the vendor info
        await send_request_demo_emails(
            name=vendor_data.get("full_name", "User"),
            email=vendor_data.get("email"),
            phone=vendor_data.get("phone_number", "N/A"),
            address=vendor_data.get("address", "")
        )

        return {"message": "Vendor added successfully from request demo"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


def clean_input_fields(user_data: UserRegistration):
    """Convert empty strings and format datetimes for MySQL"""
    # Convert empty strings to None for all fields
    for field in ['lastlogin', 'registereddate', 'level3date']:
        value = getattr(user_data, field)
        if value == '':
            setattr(user_data, field, None)
        elif value and 'T' in value:  # Format ISO datetime strings
            setattr(user_data, field, value.replace('T', ' ').split('.')[0])
    
    # Handle integer field
    user_data.logincount = 0 if user_data.logincount in ('', None) else int(user_data.logincount)
    
    return user_data


@app.post("/api/signup")
@limiter.limit("15/minute")
async def register_user(request:Request,user: UserRegistration):
    user.uname = user.uname.lower().strip()
    # Check if user exists
    existing_user = await get_user_by_username(user.uname)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    # Clean inputs (only change needed)
    user = clean_input_fields(user)

    # Rest of your existing code remains exactly the same...
    hashed_password = md5_hash(user.passwd)
    # fullname = f"{user.firstname or ''} {user.lastname or ''}".strip(),
    fullname = user.fullname or f"{user.firstname or ''} {user.lastname or ''}".strip()
    fullname = fullname.lower()
    user.fullname = fullname
    leads_full_name = f"{user.firstname or ''} {user.lastname or ''}".strip()
    # print(" Full name constructed:", fullname)  # <---- Add this line

  
    await insert_user(
    uname=user.uname,
    passwd=hashed_password,
    dailypwd=user.dailypwd,
    team=user.team,
    level=user.level,
    instructor=user.instructor,
    override=user.override,
    lastlogin=user.lastlogin,
    logincount=user.logincount,   
    fullname=fullname,
    phone=user.phone,
    address=user.address,
    city=user.city,
    Zip=user.Zip,
    country=user.country,
    message=user.message,
    registereddate=user.registereddate,
    level3date=user.level3date,    
    visa_status=user.visa_status,
    experience=user.experience,
    education=user.education,
    referby=user.referby,
    candidate_info={  # optional dict
        'name': user.fullname,
        'enrolleddate': user.registereddate,
        'email': user.uname,
        'phone': user.phone,
        'address': user.address,
        'city': user.city,
        'country': user.country,
        'zip': user.Zip,
        }
    )

    await insert_lead_new(
    full_name=leads_full_name,
    phone=user.phone,
    email=user.uname,
    address=user.address,
    workstatus=None,  # If available, pass user.workstatus
    status="Open",
    secondary_email=None,  # Or user.secondaryemail if you collect it
    secondary_phone=None,  # Or user.secondaryphone
    closed_date=None,
    notes=None
    )

    # Send confirmation email to the user and notify the admin
    send_email_to_user(user_email=user.uname, user_name=user.fullname, user_phone=user.phone)
    return {"message": "User registered successfully. Confirmation email sent to the user and notification sent to the admin."}


@app.post("/api/login", response_model=Token)
@limiter.limit("15/minute")
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

    await update_login_info(user["id"])
    await insert_login_history(user["id"], request.client.host, request.headers.get('User-Agent', ''))

    access_token = create_access_token(
        data={"sub": user["uname"], "team": user["team"]}  # Add team info to the token
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "team": user["team"],  # Explicitly include team info in response
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
@limiter.limit("15/minute")
async def get_materials(request:Request,course: str = Query(...), search: str = Query(...)):
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


@app.get("/api/session-types")
async def get_types(current_user: dict = Depends(get_current_user)):
    try:
        team = current_user.get("team", "null")  # Extract the team from the user data
        types = await fetch_types(team)  # Pass the team to fetch_types
        if not types:
            raise HTTPException(status_code=404, detail="Types not found")
        return {"types": types}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions")
async def get_sessions(course_name: Optional[str] = None, session_type: Optional[str] = None, current_user: dict = Depends(get_current_user)):
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

        # Fetch the current user's team
        team = current_user.get("team", "null")

        # Call the function to fetch sessions by the provided course_id and session_type
        sessions = await fetch_sessions_by_type(course_id, session_type, team)  # Pass the team to fetch_sessions_by_type
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
@limiter.limit("15/minute")
async def get_recordings(request:Request,course: str = None, batchid: int = None, search: str = None):
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
        # Send emails
    send_contact_emails(
        first_name=user.firstName,
        last_name=user.lastName,
        email=user.email,
        phone=user.phone,
        message=user.message
    )
    
    # Save to database
    full_name = f"{user.firstName} {user.lastName}"
    await user_contact(
        full_name=full_name,
        email=user.email,
        phone=user.phone,
        message=user.message
    )
    return {"detail": "Message sent successfully"}


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



# ...................................NEW INNOVAPATH......................................
@app.get("/api/talent_search", response_model=List[TalentSearch])
async def get_talent_search(
    role: Optional[str] = None,
    experience: Optional[int] = None,
    location: Optional[str] = None,
    availability: Optional[str] = None,
    skills: Optional[str] = None
):
    """
    Search candidates with filters
    """
    filters = {
        "role": role,
        "experience": experience,
        "location": location,
        "availability": availability,
        "skills": skills
    }
    try:
        candidates = await fetch_candidates(filters)
        return candidates
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")