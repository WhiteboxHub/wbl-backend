# wbl-backend/fapi/main.py
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from fastapi.security import OAuth2PasswordBearer
from fapi.db.database import SessionLocal

from fapi.auth import JWTAuthorizationMiddleware
from fapi.api.routes import (
    candidate, leads, google_auth, talent_search, user_role,
    contact, login, register, resources, vendor_contact,
    vendor, vendor_activity, request_demo, unsubscribe,
    user_dashboard, password,employee,course, subject, course_subject, course_content , course_material,batch,authuser,avatar_dashboard,session,
    recording


)
from fapi.core.config import limiter 


app = FastAPI()


app.add_middleware(JWTAuthorizationMiddleware)

app.include_router(candidate.router, prefix="/api", tags=["Candidate Marketing & Placements"])
app.include_router(unsubscribe.router, tags=["Unsubscribe"])
app.include_router(leads.router, prefix="/api", tags=["Leads"])
app.include_router(google_auth.router, prefix="/api", tags=["Google Authentication"])
app.include_router(vendor_contact.router, prefix="/api", tags=["Vendor Contact Extracts"])
app.include_router(vendor.router, prefix="/api", tags=["Vendor"])
app.include_router(vendor_activity.router, prefix="/api", tags=["DailyVendorActivity"])
app.include_router(employee.router, prefix="/api", tags=["Employee"])

app.include_router(talent_search.router, prefix="/api", tags=["Talent Search"])
app.include_router(user_role.router, prefix="/api", tags=["User Role"])
app.include_router(password.router, prefix="/api", tags=["password"])
app.include_router(login.router, prefix="/api", tags=["Login"])
app.include_router(contact.router, prefix="/api", tags=["Contact"])
app.include_router(resources.router, prefix="/api", tags=["Resources"])
app.include_router(register.router, prefix="/api", tags=["Register"])
app.include_router(request_demo.router, prefix="/api", tags=["Request Demo"])
app.include_router(user_dashboard.router, prefix="/api", tags=["User Dashboard"])
app.include_router(avatar_dashboard.router, prefix="/api", tags=["Avatar Dashboard"])
app.include_router(batch.router, prefix="/api", tags=["Batch"])
app.include_router(authuser.router, prefix="/api", tags=["Authuser"])
app.include_router(session.router, prefix="/api", tags=["Sessions"])
app.include_router(recording.router, prefix="/api", tags=["Recordings"])
app.include_router(course.router, prefix="/api", tags=["courses"])
app.include_router(subject.router, prefix="/api", tags=["subjects"])
app.include_router(course_subject.router, prefix="/api", tags=["course-subjects"])
app.include_router(course_content.router, prefix="/api", tags=["course-contents"])
app.include_router(course_material.router, prefix="/api", tags=["course-materials"])




def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# router = APIRouter()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,

    allow_origins=["https://whitebox-learning.com", "https://www.whitebox-learning.com", "http://whitebox-learning.com", "http://www.whitebox-learning.com","http://localhost:3000","http://localhost:8000"],

    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth2PasswordBearer instance
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
