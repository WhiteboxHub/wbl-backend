
# wbl-backend/fapi/main.py
from fapi.models import EmailRequest, UserCreate, Token, UserRegistration, ContactForm, ResetPasswordRequest, ResetPassword ,GoogleUserCreate, VendorCreate , RecentPlacement , RecentInterview,Placement, PlacementCreate, PlacementUpdate
from  fapi.db import (
      fetch_sessions_by_type, fetch_types, insert_login_history, insert_user, get_user_by_username, update_login_info, verify_md5_hash,
    fetch_keyword_recordings, fetch_keyword_presentation,fetch_interviews_by_name,insert_interview,delete_interview,update_interview,
 fetch_course_batches, fetch_subject_batch_recording, user_contact, course_content, fetch_candidate_id_by_email,get_candidates_by_status,fetch_interview_by_id,
    unsubscribe_user, update_user_password ,get_user_by_username, update_user_password ,insert_user,get_google_user_by_email,insert_google_user_db,fetch_candidate_id_by_email,insert_vendor ,fetch_recent_placements , fetch_recent_interviews, get_candidate_by_name, get_candidate_by_id, create_candidate, delete_candidate as db_delete_candidate,update_candidate as db_update_candidate,get_all_placements,
    get_placement_by_id,search_placements_by_candidate_name,create_placement,update_placement,delete_placement,


)
from  fapi.utils import md5_hash, verify_md5_hash, create_reset_token, verify_reset_token
from  fapi.auth import create_access_token, verify_token, JWTAuthorizationMiddleware, generate_password_reset_token, verify_password_reset_token, get_password_hash ,create_google_access_token,determine_user_role
from  fapi.contactMailTemplet import ContactMail_HTML_templete
from  fapi.mail_service import send_reset_password_email ,send_request_demo_emails
from fastapi import FastAPI, Depends, HTTPException, Request, status, Query, Body ,APIRouter, status as http_status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm,HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from jose import JWTError
from typing import List, Optional
import os
from fastapi.responses import JSONResponse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date,datetime, timedelta
import jwt
from fapi.models import Candidate, CandidateCreate, CandidateUpdate
from fapi.models import LeadBase, LeadCreate, Lead

from fapi.db import get_connection
import fapi.db as leads_db


from fapi.db import (
    # get_all_candidates,
    get_candidate_by_id,
    create_candidate,
    update_candidate,
    delete_candidate,
    get_all_candidates_paginated
)

from slowapi import Limiter
from slowapi.util import get_remote_address

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr

# Load environment variables
load_dotenv()

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr





load_dotenv()


# Initialize FastAPI app
app = FastAPI()

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

router = APIRouter()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,


    allow_origins=["*","https://whitebox-learning.com", "https://www.whitebox-learning.com", "http://whitebox-learning.com", "http://www.whitebox-learning.com","http://localhost:3000"],  # Adjust this list to include your frontend URL


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
ACCESS_TOKEN_EXPIRE_MINUTES = 720



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
    except (jwt.ExpiredSignatureError, JWTError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    userinfo = await get_user_by_username(username)
    if not userinfo:
        raise HTTPException(status_code=404, detail="User not found")

    role = determine_user_role(userinfo)

    return {"role": role}

# def determine_user_role(userinfo):
#     username = userinfo.get("username") or userinfo.get("email") or ""
#     team = userinfo.get("team") or ""

#     if (
#         team == "admin"
#         or username.endswith("@whitebox-learning.com")
#         or username.endswith("@innova-path")
#         or username == "admin"
#     ):
#         return "admin"

#     return "candidate"

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
# ------------------------------------------------- Candidate ------------------------------------------

#GET all candidates
@app.get("/api/candidates", response_model=List[Candidate])
async def get_all_candidates_endpoint(page: int = 1, limit: int = 100):
    try:
        rows = get_all_candidates_paginated(page, limit)
        return [Candidate(**row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    
    # GET Candidate status
@app.get("/api/candidates/{status}", response_model=List[Candidate])
async def get_candidates_by_dynamic_status(
    status: str,
    page: int = 1,
    limit: int = 100
):
    # Define valid statuses (you can expand this set as needed)
    valid_statuses = {"active", "marketing"}  

    if status.lower() not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    try:
        rows = get_candidates_by_status(status, page, limit)
        return [Candidate(**row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    


#GET candidate by Name
@app.get("/api/candidates/by-name/{name}", response_model=List[Candidate])
async def get_candidates_by_name_endpoint(name: str):
    candidates = get_candidate_by_name(name)
    if not candidates:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidates


# GET candidate by ID
@app.get("/api/candidates/{candidateid}", response_model=Candidate)
async def get_candidate(candidateid: int):
    candidate = get_candidate_by_id(candidateid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return Candidate(**candidate)


    




# POST - Create candidate
@app.post("/api/candidates", response_model=Candidate)
async def create_candidate_endpoint(candidate: CandidateCreate):
    try:
        fields = candidate.dict(exclude_unset=True)
        new_id = create_candidate(fields)
        return Candidate(**fields, candidateid=new_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insertion failed: {str(e)}")
    

# PUT - Update candidate
@app.put("/api/candidates/{candidateid}", response_model=Candidate)
async def update_candidate(candidateid: int, update_data: CandidateUpdate):
    fields = update_data.dict(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No data to update")
    try:
        db_update_candidate(candidateid, fields)
        return Candidate(**fields, candidateid=candidateid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


# DELETE candidate
@app.delete("/api/candidates/{candidateid}")
async def delete_candidate(candidateid: int):
    try:
        # You can enhance db.py to return rowcount if needed
        db_delete_candidate(candidateid)
        return {"detail": f"Candidate {candidateid} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


# ------------------------------------------------------Placements--------------------------------------

# GET all placements
@app.get("/api/placements", response_model=List[Placement])
async def get_placements(page: int = 1, limit: int = 100):
    try:
        rows = get_all_placements(page, limit)
        return [Placement(**row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# GET placement by ID
@app.get("/api/placements/{placement_id}", response_model=Placement)
async def get_placement(placement_id: int):
    row = get_placement_by_id(placement_id)
    if not row:
        raise HTTPException(status_code=404, detail="Placement not found")
    return Placement(**row)


# GET placements by candidate name
@app.get("/api/placements/by-name/{candidate_name}", response_model=List[Placement])
async def get_placements_by_name(candidate_name: str):
    rows = search_placements_by_candidate_name(candidate_name)
    if not rows:
        raise HTTPException(status_code=404, detail="No placements found")
    return [Placement(**row) for row in rows]


# POST - Create placement
@app.post("/api/placements", response_model=Placement)
async def create_placement_endpoint(data: PlacementCreate):
    try:
        fields = data.dict(exclude_unset=True)
        new_id = create_placement(fields)
        return Placement(**fields, id=new_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insertion failed: {str(e)}")


# PUT - Update placement
@app.put("/api/placements/{placement_id}", response_model=Placement)
async def update_placement_endpoint(placement_id: int, update_data: PlacementUpdate):
    fields = update_data.dict(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No data to update")
    try:
        update_placement(placement_id, fields)
        return Placement(**fields, id=placement_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


# DELETE placement
@app.delete("/api/placements/{placement_id}")
async def delete_placement_endpoint(placement_id: int):
    try:
        delete_placement(placement_id)
        return {"detail": f"Placement {placement_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

# ------------------------------------------------------- Leads -------------------------------------------------


# GET all leads
@app.get("/api/leads", response_model=List[Lead])
async def get_all_leads_endpoint(page: int = 1, limit: int = 100):
    try:
        rows = leads_db.fetch_all_leads_paginated(page, limit)
        return [Lead(**row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/leads/search", response_model=List[Lead])
def search_leads(name: Optional[str] = Query(None), email: Optional[str] = Query(None)):
    try:
        results = leads_db.search_leads(name, email)
        if not results:
            raise HTTPException(status_code=404, detail="No leads found")
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/leads/{leadid}", response_model=Lead)
def get_lead(leadid: int):
    try:
        lead = leads_db.fetch_lead_by_id(leadid)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        return lead
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/leads", response_model=Lead, status_code=http_status.HTTP_201_CREATED)
def create_lead(lead: LeadCreate):
    try:
        lead_data = lead.dict(exclude_unset=True)
        lead_id = leads_db.create_new_lead(lead_data)
        return {**lead_data, "leadid": lead_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/leads/{leadid}", response_model=Lead)
def update_lead(leadid: int, lead: LeadCreate):
    try:
        update_data = lead.dict(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        leads_db.update_existing_lead(leadid, update_data)
        return {**update_data, "leadid": leadid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/leads/{leadid}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_lead(leadid: int):
    try:
        leads_db.delete_lead_by_id(leadid)
        return
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# # ----------------------------------------------------------------------------------------------

@app.get("/api/placements", response_model=List[RecentPlacement])
async def get_recent_placements():
    placements = await fetch_recent_placements()
    return placements


# @app.get("/api/interviews", response_model=List[RecentInterview])
# async def get_recent_interviews():
#     interviews = await fetch_recent_interviews()
#     return interviews


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


@app.post("/vendor/request-demo")
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




# --------------------------------------------------------------------------------------

@app.post("/api/check_user/")
async def check_user_exists(user: GoogleUserCreate):
    existing_user = await get_google_user_by_email(user.email)
    if existing_user:
        return {"exists": True, "status": existing_user['status']}
    return {"exists": False}


@app.post("/api/google_users/")
@limiter.limit("15/minute")
async def register_google_user(request:Request,user: GoogleUserCreate):
    existing_user = await get_google_user_by_email(user.email)
    
    if existing_user:
        if existing_user['status'] == 'active':
            return {"message": "User already registered and active, please log in."}
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive account. Please contact admin.")

    await insert_google_user_db(email=user.email, name=user.name, google_id=user.google_id)
    return {"message": "Google user registered successfully!"}

@app.post("/api/google_login/")
@limiter.limit("15/minute")
async def login_google_user(request:Request,user: GoogleUserCreate):
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
#@limiter.limit("5/minute")
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
# @app.post("/api/signup")
# async def register_user(user: UserRegistration):
#     existing_user = await get_user_by_username(user.uname)
#     if existing_user:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")

#     hashed_password = md5_hash(user.passwd)
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
#         level3date=user.level3date,
#         candidate_info={
#             'name': user.fullname,
#             'enrolleddate': user.registereddate,
#             'email': user.uname,
#             'phone': user.phone,
#             'address': user.address,
#             'city': user.city,
#             'country': user.country,
#             'zip': user.Zip,
#             'status': user.status
#         }
#     )
#     return {"message": "User registered successfully "}


# # Send email function
# def send_email_to_user(user_email: str, user_name: str,admin_email:str):
#     from_email = os.getenv('EMAIL_USER')
#     password = os.getenv('EMAIL_PASS')
#     smtp_server = os.getenv('SMTP_SERVER')
#     smtp_port = os.getenv('SMTP_PORT')

#     # Create the email content
#     html_content = f"""
#     <html>
#         <body>
#             <p>Dear {user_name},</p>
#             <p>Thank you for registering with us. We are pleased to inform you that our recruiting team will reach out to you shortly.</p>
#             <p>Best regards,<br>Recruitment Team</p>
#         </body>
#     </html>
#     """

#     # Create the MIME message
#     msg = MIMEMultipart()
#     msg['From'] = from_email
#     msg['To'] = user_email
#     msg['Subject'] = 'Registration Successful - Recruiting Team will Reach Out'

#     msg.attach(MIMEText(html_content, 'html'))

#     try:
#         # Establish the connection with the email server
#         server = smtplib.SMTP(smtp_server, int(smtp_port))
#         server.starttls()
#         server.login(from_email, password)
#         text = msg.as_string()
#         server.sendmail(from_email, user_email, text)
#         server.quit()
#     except Exception as e:
#         raise HTTPException(status_code=500, detail='Error while sending the confirmation email.')

# @app.post("/api/signup")
# async def register_user(user: UserRegistration):
#     # Check if the user already exists
#     existing_user = await get_user_by_username(user.uname)
#     if existing_user:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")

#     # Hash the password and insert the new user
#     hashed_password = md5_hash(user.passwd)
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
#         level3date=user.level3date,
#         candidate_info={
#             'name': user.fullname,
#             'enrolleddate': user.registereddate,
#             'email': user.uname,
#             'phone': user.phone,
#             'address': user.address,
#             'city': user.city,
#             'country': user.country,
#             'zip': user.Zip,
#             'status': user.status
#         }
#     )

#     # Send confirmation email to the user
#     send_email_to_user(user.uname, user.fullname)

#     return {"message": "User registered successfully and a confirmation email has been sent to the user."}


# Email server configuration
mail_conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv('EMAIL_USER'),
    MAIL_PASSWORD=os.getenv('EMAIL_PASS'),
    MAIL_FROM=os.getenv('EMAIL_USER'),
    MAIL_PORT=int(os.getenv('SMTP_PORT')),
    MAIL_SERVER=os.getenv('SMTP_SERVER'),  
    MAIL_STARTTLS=os.getenv('SMTP_STARTTLS', 'True').lower() == 'true',
    MAIL_SSL_TLS=os.getenv('SMTP_SSL_TLS', 'False').lower() == 'true', 
   
    USE_CREDENTIALS=True
)

# async def send_email_to_user(user_email: str, user_name: str):
#     from_email = os.getenv('EMAIL_USER')
#     to_recruiting_email = os.getenv('TO_RECRUITING_EMAIL')
#     to_admin_email = os.getenv('ADMIN_MAIL')
#     print(to_recruiting_email,to_admin_email,"-"*100)

#     # Email content for the user
#     user_html_content = f"""
#     <html>
#         <body>
#             <p>Dear {user_name},</p>
#             <p>Thank you for registering with us. We are pleased to inform you that our recruiting team will reach out to you shortly.</p>
#             <p>Best regards,<br>Recruitment Team</p>
#         </body>
#     </html>
#     """

#     # Email content for the admin
#     admin_html_content = f"""
#     <html>
#         <body>
#             <p>Hello Admin,</p>
#             <p>A new user has registered on the website. Please review their details and provide access.</p>
#             <p><strong>User Details:</strong></p>
#             <ul>
#                 <li>Name: {user_name}</li>
#                 <li>Email: {user_email}</li>
#             </ul>
#             <p>Best regards,<br>System Notification</p>
#         </body>
#     </html>
#     """

#     # Prepare message schemas
#     user_message = MessageSchema(
#         subject="Registration Successful - Recruiting Team will Reach Out",
#         recipients=[user_email],
#         body=user_html_content,
#         subtype="html"
#     )

#     admin_message = MessageSchema(
#         subject="New User Registration Notification",
#         recipients=[to_recruiting_email, to_admin_email],
#         body=admin_html_content,
#         subtype="html"
#     )

#     # Send the emails
#     fm = FastMail(mail_conf)
#     try:
#         await fm.send_message(user_message)
#         await fm.send_message(admin_message)
#     except Exception as e:
#         from fastapi import HTTPException
#         raise HTTPException(status_code=500, detail=f"Error while sending emails: {e}")
# Send email function
def send_email_to_user(user_email: str, user_name: str, user_phone: str):
    from_email = os.getenv('EMAIL_USER')  # The "from" email (distributor)
    to_recruiting_email = os.getenv('TO_RECRUITING_EMAIL') # Admin email from environment variable
    to_admin_email = os.getenv('ADMIN_MAIL') # Admin email from environment variable
    password = os.getenv('EMAIL_PASS')
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = os.getenv('SMTP_PORT')
    print(f"user name is {user_name}")
    # Email content for the user
    user_html_content = f"""
    <html>
        <body>
            <p>Dear {user_name},</p>
            <p>Thank you for registering with us. We are pleased to inform you that our recruiting team will reach out to you shortly.</p>
            <p>Best regards,<br>Recruitment Team</p>
        </body>
    </html>
    """

    # Email content for the admin
    admin_html_content = f"""
    <html>
        <body>
            <p>Hello Admin,</p>
            <p>A new user has registered on the website. Please review their details and provide access.</p>
            <p><strong>User Details:</strong></p>
            <ul>
                <li>Name: {user_name}</li>
                <li>Email: {user_email}</li>
                <li>Phone: {user_phone}</li>
            </ul>
            <p>Best regards,<br>System Notification</p>
        </body>
    </html>
    """

    try:
        # Establish the connection with the email server
        server = smtplib.SMTP(smtp_server, int(smtp_port))
        server.starttls()
        server.login(from_email, password)

        # send_html_email(server, from_email, user_email, 'Registration Successful - Recruiting Team will Reach Out', user_html_content)

        # admin_emails = [to_recruiting_email, to_admin_email]
        # for admin_email in admin_emails:
        #     send_html_email(server, from_email, admin_email, 'New User Registration Notification', admin_html_content)


        # # Send email to the user
        user_msg = MIMEMultipart()
        user_msg['From'] = from_email
        user_msg['To'] = user_email
        user_msg['Subject'] = 'Registration Successful - Recruiting Team will Reach Out'
        user_msg.attach(MIMEText(user_html_content, 'html'))
        server.sendmail(from_email, user_email, user_msg.as_string())

        # List of admin emails to notify
        for admin_emails in [to_recruiting_email, to_admin_email]:

            # Send email to the admin
            admin_msg = MIMEMultipart()
            admin_msg['From'] = from_email  
            admin_msg['To'] = admin_emails
            admin_msg['Subject'] = 'New User Registration Notification'
            admin_msg.attach(MIMEText(admin_html_content, 'html'))
            server.sendmail(from_email, admin_emails, admin_msg.as_string())


        # # Send email to the admin
        admin_msg = MIMEMultipart()
        admin_msg['From'] = from_email  
        admin_msg['To'] = to_admin_email
        admin_msg['Subject'] = 'New User Registration Notification'
        admin_msg.attach(MIMEText(admin_html_content, 'html'))
        server.sendmail(from_email, to_admin_email, admin_msg.as_string())

        # Close the server
        server.quit()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Error while sending emails: {e}')


def send_html_email(server, from_email, to_email, subject, html_content):
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_content, 'html'))
    server.sendmail(from_email, to_email, msg.as_string())


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

# @app.post("/api/signup")
# @limiter.limit("15/minute")
# async def register_user(request:Request,user: UserRegistration):
#     # Check if user exists
#     existing_user = await get_user_by_username(user.uname)
#     if existing_user:
#         raise HTTPException(status_code=400, detail="Username already registered")

#     # Clean inputs (only change needed)
#     user = clean_input_fields(user)

#     # Rest of your existing code remains exactly the same...
#     hashed_password = md5_hash(user.passwd)
#     # fullname = f"{user.firstname or ''} {user.lastname or ''}".strip(),
#     fullname = user.fullname or f"{user.firstname or ''} {user.lastname or ''}".strip()
#     # print(" Full name constructed:", fullname)  # <---- Add this line

#     await insert_user(
#     uname=user.uname,
#     passwd=hashed_password,
#     dailypwd=user.dailypwd,
#     team=user.team,
#     level=user.level,
#     instructor=user.instructor,
#     override=user.override,
#     lastlogin=user.lastlogin,
#     logincount=user.logincount,
#     # fullname=user.fullname,
#     fullname=fullname,
#     phone=user.phone,
#     address=user.address,
#     city=user.city,
#     Zip=user.Zip,
#     country=user.country,
#     message=user.message,
#     registereddate=user.registereddate,
#     level3date=user.level3date,
#     visastatus=user.visastatus,
#     experience=user.experience,
#     education=user.education,
#     referred_by=user.referred_by,
#     candidate_info={  # optional dict
#         'name': user.fullname,
#         'enrolleddate': user.registereddate,
#         'email': user.uname,
#         'phone': user.phone,
#         'address': user.address,
#         'city': user.city,
#         'country': user.country,
#         'zip': user.Zip,
#         }
#     )


#     # Send confirmation email to the user and notify the admin
#     send_email_to_user(user_email=user.uname, user_name=user.fullname)

#     return {"message": "User registered successfully. Confirmation email sent to the user and notification sent to the admin."}


# data to deploy


@app.post("/api/signup")
@limiter.limit("15/minute")
async def register_user(request:Request,user: UserRegistration):
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
    # print(" Full name constructed:", fullname)  # <---- Add this line

  
    

    # await insert_user(
    #     uname=user.uname,
    #     passwd=hashed_password,
    #     dailypwd=user.dailypwd,
    #     team=user.team,
    #     level=user.level,
    #     instructor=user.instructor,
    #     override=user.override,
    #     # status=user.status,
    #     lastlogin=user.lastlogin,
    #     logincount=user.logincount,
    #     fullname=user.fullname,
    #     phone=user.phone,
    #     address=user.address,
    #     city=user.city,
    #     Zip=user.Zip,
    #     country=user.country,
    #     message=user.message,
    #     registereddate=user.registereddate,
    #     level3date=user.level3date,
    #     candidate_info={
    #         'name': user.fullname,
    #         'enrolleddate': user.registereddate,
    #         'email': user.uname,
    #         'phone': user.phone,
    #         'address': user.address,
    #         'city': user.city,
    #         'country': user.country,
    #         'zip': user.Zip,
    #         # 'status': user.status
    #     }
    # )
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
    # fullname=user.fullname,
    fullname=fullname,
    phone=user.phone,
    address=user.address,
    city=user.city,
    Zip=user.Zip,
    country=user.country,
    message=user.message,
    registereddate=user.registereddate,
    level3date=user.level3date,
    visastatus=user.visastatus,
    experience=user.experience,
    education=user.education,
    referred_by=user.referred_by,
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


    # Send confirmation email to the user and notify the admin
    send_email_to_user(user_email=user.uname, user_name=fullname, user_phone=user.phone)

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
    
    

    await user_contact(
        # name=f"{user.firstName} {user.lastName}",
        name=f"{user.firstName} {user.lastName}",
        email=user.email,
        phone=user.phone,
        message=user.message        
        )

    # def sendEmail():
    #     from_Email = os.getenv('EMAIL_USER')
    #     password = os.getenv('EMAIL_PASS')
    #     to_email = os.getenv('TO_RECRUITING_EMAIL')
    #     admin_to_email = os.getenv('ADMIN_MAIL')
    #     smtp_server = os.getenv('SMTP_SERVER')
    #     smtp_port = os.getenv('SMTP_PORT')
    # html_content = ContactMail_HTML_templete(f"{user.firstName} {user.lastName}",user.email,user.phone,user.message)
    # await lead_generation_mail(f"{user.firstName} {user.lastName}",user.email,html_content)
        # for email in [to_email,admin_to_email]:
            
        #     msg = MIMEMultipart()
        #     msg['From'] = from_Email
        #     msg['To'] = email
        #     msg['Subject'] = 'WBL Contact lead generated'
        #     msg.attach(MIMEText(html_content, 'html'))
        #     try:
        #         # server = smtplib.SMTP('smtp.gmail.com',587)
        #         server = smtplib.SMTP(smtp_server, int(smtp_port))
        #         server.starttls()
        #         server.login(from_Email,password)
        #         text = msg.as_string()
        #         server.sendmail(from_Email,email,text)
        #     except Exception as e:
        #         raise HTTPException(status_code=500, detail='Erro while sending the mail to recruiting teams')
        # server.quit()
        
    # sendEmail()

    def sendEmail(email):
        from_Email = os.getenv('EMAIL_USER')
        password = os.getenv('EMAIL_PASS')
        to_email = email
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = os.getenv('SMTP_PORT')
        html_content = ContactMail_HTML_templete(f"{user.firstName} {user.lastName}",user.email,user.phone,user.message)
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
            print(e)
            raise HTTPException(status_code=500, detail='Erro while sending the mail to recruiting teams')
    
        # to_email = os.getenv('TO_RECRUITING_EMAIL')
    sendEmail(os.getenv('TO_RECRUITING_EMAIL'))
    sendEmail(os.getenv('ADMIN_MAIL'))
    return {"detail": "Message Sent Successfully"}

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

@app.get("/candidate_marketing/", response_model=List[CandidateMarketing])
async def get_candidate_marketing(
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
    
  

