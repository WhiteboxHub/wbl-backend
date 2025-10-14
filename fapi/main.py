# # # wbl-backend/fapi/main.py
# # from fastapi import FastAPI, Depends
# # from fastapi.middleware.cors import CORSMiddleware
# # from fapi.db.database import SessionLocal

# # # Import route modules
# # from fapi.api.routes import (
# #     candidate, leads, google_auth, talent_search, user_role,
# #     contact, login, register, resources, vendor_contact,
# #     vendor, vendor_activity, request_demo, unsubscribe,
# #     user_dashboard, password, employee, course, subject, course_subject,
# #     course_content, course_material, batch, authuser, avatar_dashboard,
# #     session, recording, referrals,
# # )

# # # Import auth dependencies
# # from fapi.utils.auth_dependencies import get_current_user, admin_required

# # # Create FastAPI app
# # app = FastAPI()

# # # ===============================
# # # 🔐 AUTHENTICATION SETUP
# # # ===============================
# # protected = [Depends(get_current_user)]
# # admin_only = [Depends(admin_required)]

# # # ===============================
# # # 🔗 ROUTES CONFIGURATION (No /api prefix)
# # # ===============================

# # # ✅ Authenticated routes
# # app.include_router(candidate.router, tags=["Candidate"], dependencies=protected)
# # app.include_router(leads.router, tags=["Leads"], dependencies=protected)
# # app.include_router(vendor_contact.router, tags=["Vendor Contact Extracts"], dependencies=protected)
# # app.include_router(vendor.router, tags=["Vendor"], dependencies=protected)
# # app.include_router(vendor_activity.router, tags=["DailyVendorActivity"], dependencies=protected)
# # app.include_router(employee.router, tags=["Employee"], dependencies=protected)
# # app.include_router(talent_search.router, tags=["Talent Search"], dependencies=protected)
# # app.include_router(user_role.router, tags=["User Role"], dependencies=protected)
# # app.include_router(password.router, tags=["Password"], dependencies=protected)
# # app.include_router(contact.router, tags=["Contact"], dependencies=protected)
# # app.include_router(resources.router, tags=["Resources"], dependencies=protected)
# # app.include_router(request_demo.router, tags=["Request Demo"], dependencies=protected)
# # app.include_router(user_dashboard.router, tags=["User Dashboard"], dependencies=protected)
# # app.include_router(batch.router, tags=["Batch"], dependencies=protected)
# # app.include_router(authuser.router, tags=["Authuser"], dependencies=protected)
# # app.include_router(session.router, tags=["Sessions"], dependencies=protected)
# # app.include_router(recording.router, tags=["Recordings"], dependencies=protected)
# # app.include_router(course.router, tags=["Courses"], dependencies=protected)
# # app.include_router(subject.router, tags=["Subjects"], dependencies=protected)
# # app.include_router(course_subject.router, tags=["Course Subjects"], dependencies=protected)
# # app.include_router(course_content.router, tags=["Course Contents"], dependencies=protected)
# # app.include_router(course_material.router, tags=["Course Materials"], dependencies=protected)
# # app.include_router(referrals.router, tags=["Referrals"], dependencies=protected)

# # # 👑 Admin-only routes
# # app.include_router(avatar_dashboard.router, tags=["Avatar Dashboard"], dependencies=admin_only)

# # # 🌍 Public routes (no token required)
# # app.include_router(register.router, tags=["Register"])
# # # app.include_router(login.router, tags=["Login"])
# # app.include_router(login.router, prefix="/api", tags=["Login"])

# # app.include_router(unsubscribe.router, tags=["Unsubscribe"])
# # app.include_router(google_auth.router, tags=["Google Authentication"])

# # # ===============================
# # # ⚙️ DATABASE DEPENDENCY
# # # ===============================
# # def get_db():
# #     db = SessionLocal()
# #     try:
# #         yield db
# #     finally:
# #         db.close()

# # # ===============================
# # # 🌐 CORS CONFIGURATION
# # # ===============================
# # app.add_middleware(
# #     CORSMiddleware,
# #     allow_origins=[
# #         "https://whitebox-learning.com",
# #         "https://www.whitebox-learning.com",
# #         "http://whitebox-learning.com",
# #         "http://www.whitebox-learning.com",
# #         "http://localhost:3000",
# #         "http://localhost:8000",
# #     ],
# #     allow_credentials=True,
# #     allow_methods=["*"],
# #     allow_headers=["*"],
# # )

# # # ===============================
# # # 🧱 LOCAL RUN COMMAND
# # # ===============================
# # # Run using:
# # # uvicorn fapi.main:app --reload
# # wbl-backend/fapi/main.py
# from fastapi import FastAPI, Depends
# from fastapi.middleware.cors import CORSMiddleware
# from fapi.db.database import SessionLocal

# # Import route modules
# from fapi.api.routes import (
#     candidate, leads, google_auth, talent_search, user_role,
#     contact, login, register, resources, vendor_contact,
#     vendor, vendor_activity, request_demo, unsubscribe,
#     user_dashboard, password, employee, course, subject, course_subject,
#     course_content, course_material, batch, authuser, avatar_dashboard,
#     session, recording, referrals,
# )

# # Import auth dependencies
# from fapi.utils.auth_dependencies import get_current_user, admin_required

# # Create FastAPI app
# app = FastAPI(title="WBL Backend")

# # ===============================
# # 🔐 AUTHENTICATION SETUP
# # ===============================
# protected = [Depends(get_current_user)]
# admin_only = [Depends(admin_required)]

# # ===============================
# # 🔗 ROUTES CONFIGURATION
# # ===============================
# # We include each router TWICE:
# #  - once with prefix="/api" so frontend that uses NEXT_PUBLIC_API_URL=http://.../api keeps working
# #  - once without prefix so non-prefixed calls also work
# #
# # Note: This intentionally exposes the same endpoints at both /<route> and /api/<route>.

# # ---------- Protected routers (require authentication) ----------
# # candidate
# app.include_router(candidate.router, prefix="/api", tags=["Candidate"], dependencies=protected)
# app.include_router(candidate.router, tags=["Candidate"], dependencies=protected)

# # leads
# app.include_router(leads.router, prefix="/api", tags=["Leads"], dependencies=protected)
# app.include_router(leads.router, tags=["Leads"], dependencies=protected)

# # vendor_contact
# app.include_router(vendor_contact.router, prefix="/api", tags=["Vendor Contact Extracts"], dependencies=protected)
# app.include_router(vendor_contact.router, tags=["Vendor Contact Extracts"], dependencies=protected)

# # vendor
# app.include_router(vendor.router, prefix="/api", tags=["Vendor"], dependencies=protected)
# app.include_router(vendor.router, tags=["Vendor"], dependencies=protected)

# # vendor_activity
# app.include_router(vendor_activity.router, prefix="/api", tags=["DailyVendorActivity"], dependencies=protected)
# app.include_router(vendor_activity.router, tags=["DailyVendorActivity"], dependencies=protected)

# # employee
# app.include_router(employee.router, prefix="/api", tags=["Employee"], dependencies=protected)
# app.include_router(employee.router, tags=["Employee"], dependencies=protected)

# # talent_search
# app.include_router(talent_search.router, prefix="/api", tags=["Talent Search"], dependencies=protected)
# app.include_router(talent_search.router, tags=["Talent Search"], dependencies=protected)

# # user_role
# app.include_router(user_role.router, prefix="/api", tags=["User Role"], dependencies=protected)
# app.include_router(user_role.router, tags=["User Role"], dependencies=protected)

# # password
# app.include_router(password.router, prefix="/api", tags=["Password"], dependencies=protected)
# app.include_router(password.router, tags=["Password"], dependencies=protected)

# # contact
# app.include_router(contact.router, prefix="/api", tags=["Contact"], dependencies=protected)
# app.include_router(contact.router, tags=["Contact"], dependencies=protected)

# # resources
# app.include_router(resources.router, prefix="/api", tags=["Resources"], dependencies=protected)
# app.include_router(resources.router, tags=["Resources"], dependencies=protected)

# # request_demo
# app.include_router(request_demo.router, prefix="/api", tags=["Request Demo"], dependencies=protected)
# app.include_router(request_demo.router, tags=["Request Demo"], dependencies=protected)

# # user_dashboard
# app.include_router(user_dashboard.router, prefix="/api", tags=["User Dashboard"], dependencies=protected)
# app.include_router(user_dashboard.router, tags=["User Dashboard"], dependencies=protected)

# # batch
# app.include_router(batch.router, prefix="/api", tags=["Batch"], dependencies=protected)
# app.include_router(batch.router, tags=["Batch"], dependencies=protected)

# # authuser
# app.include_router(authuser.router, prefix="/api", tags=["Authuser"], dependencies=protected)
# app.include_router(authuser.router, tags=["Authuser"], dependencies=protected)

# # session
# app.include_router(session.router, prefix="/api", tags=["Sessions"], dependencies=protected)
# app.include_router(session.router, tags=["Sessions"], dependencies=protected)

# # recording
# app.include_router(recording.router, prefix="/api", tags=["Recordings"], dependencies=protected)
# app.include_router(recording.router, tags=["Recordings"], dependencies=protected)

# # course & related
# app.include_router(course.router, prefix="/api", tags=["Courses"], dependencies=protected)
# app.include_router(course.router, tags=["Courses"], dependencies=protected)
# app.include_router(subject.router, prefix="/api", tags=["Subjects"], dependencies=protected)
# app.include_router(subject.router, tags=["Subjects"], dependencies=protected)
# app.include_router(course_subject.router, prefix="/api", tags=["Course Subjects"], dependencies=protected)
# app.include_router(course_subject.router, tags=["Course Subjects"], dependencies=protected)
# app.include_router(course_content.router, prefix="/api", tags=["Course Contents"], dependencies=protected)
# app.include_router(course_content.router, tags=["Course Contents"], dependencies=protected)
# app.include_router(course_material.router, prefix="/api", tags=["Course Materials"], dependencies=protected)
# app.include_router(course_material.router, tags=["Course Materials"], dependencies=protected)

# # referrals
# app.include_router(referrals.router, prefix="/api", tags=["Referrals"], dependencies=protected)
# app.include_router(referrals.router, tags=["Referrals"], dependencies=protected)

# # -------------------------
# # Admin-only router(s)
# # -------------------------
# app.include_router(avatar_dashboard.router, prefix="/api", tags=["Avatar Dashboard"], dependencies=admin_only)
# app.include_router(avatar_dashboard.router, tags=["Avatar Dashboard"], dependencies=admin_only)

# # -------------------------
# # Public routers (no token required)
# # -------------------------
# app.include_router(register.router, prefix="/api", tags=["Register"])
# app.include_router(register.router, tags=["Register"])

# app.include_router(login.router, prefix="/api", tags=["Login"])
# app.include_router(login.router, tags=["Login"])

# app.include_router(unsubscribe.router, prefix="/api", tags=["Unsubscribe"])
# app.include_router(unsubscribe.router, tags=["Unsubscribe"])

# app.include_router(google_auth.router, prefix="/api", tags=["Google Authentication"])
# app.include_router(google_auth.router, tags=["Google Authentication"])

# # ===============================
# # ⚙️ DATABASE DEPENDENCY
# # ===============================
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

# # ===============================
# # 🌐 CORS CONFIGURATION
# # ===============================
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=[
#         "https://whitebox-learning.com",
#         "https://www.whitebox-learning.com",
#         "http://whitebox-learning.com",
#         "http://www.whitebox-learning.com",
#         "http://localhost:3000",
#         "http://localhost:8000",
#     ],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ===============================
# # 🧱 LOCAL RUN COMMAND
# # ===============================
# # Run using:
# # uvicorn fapi.main:app --reload
# fapi/main.py
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
import logging
import traceback

# create app
app = FastAPI(title="WBL Backend")

# setup simple logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wbl")

# -----------------------
# CORS - apply EARLY
# -----------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://whitebox-learning.com",
        "https://www.whitebox-learning.com",
        "http://whitebox-learning.com",
        "http://www.whitebox-learning.com",
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------
# Health endpoint
# -----------------------
@app.get("/health")
def health():
    return {"status": "ok"}

# -----------------------
# Middleware to log unhandled exceptions (helps debug 500s)
# -----------------------
@app.middleware("http")
async def log_exceptions(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error("Unhandled exception during request: %s %s", request.method, request.url)
        logger.error(traceback.format_exc())
        # re-raise so fastapi returns 500; CORS middleware is already applied
        raise

# -----------------------
# Now import DB, routers and auth deps (after CORS)
# -----------------------
from fapi.db.database import SessionLocal

# Import route modules
from fapi.api.routes import (
    candidate, leads, google_auth, talent_search, user_role,
    contact, login, register, resources, vendor_contact,
    vendor, vendor_activity, request_demo, unsubscribe,
    user_dashboard, password, employee, course, subject, course_subject,
    course_content, course_material, batch, authuser, avatar_dashboard,
    session, recording, referrals,
)

# Import auth dependencies
from fapi.utils.auth_dependencies import get_current_user, admin_required

# ===============================
# Authentication dependency shortcuts
# ===============================
protected = [Depends(get_current_user)]
admin_only = [Depends(admin_required)]

# ===============================
# ROUTES CONFIGURATION
# Note: routers are included with and without /api prefix to maintain compatibility
# ===============================

# Protected routers (require authentication)
app.include_router(candidate.router, prefix="/api", tags=["Candidate"], dependencies=protected)
app.include_router(candidate.router, tags=["Candidate"], dependencies=protected)

app.include_router(leads.router, prefix="/api", tags=["Leads"], dependencies=protected)
app.include_router(leads.router, tags=["Leads"], dependencies=protected)

app.include_router(vendor_contact.router, prefix="/api", tags=["Vendor Contact Extracts"], dependencies=protected)
app.include_router(vendor_contact.router, tags=["Vendor Contact Extracts"], dependencies=protected)

app.include_router(vendor.router, prefix="/api", tags=["Vendor"], dependencies=protected)
app.include_router(vendor.router, tags=["Vendor"], dependencies=protected)

app.include_router(vendor_activity.router, prefix="/api", tags=["DailyVendorActivity"], dependencies=protected)
app.include_router(vendor_activity.router, tags=["DailyVendorActivity"], dependencies=protected)

app.include_router(employee.router, prefix="/api", tags=["Employee"], dependencies=protected)
app.include_router(employee.router, tags=["Employee"], dependencies=protected)

app.include_router(talent_search.router, prefix="/api", tags=["Talent Search"], dependencies=protected)
app.include_router(talent_search.router, tags=["Talent Search"], dependencies=protected)

app.include_router(user_role.router, prefix="/api", tags=["User Role"], dependencies=protected)
app.include_router(user_role.router, tags=["User Role"], dependencies=protected)

app.include_router(password.router, prefix="/api", tags=["Password"], dependencies=protected)
app.include_router(password.router, tags=["Password"], dependencies=protected)

# app.include_router(contact.router, prefix="/api", tags=["Contact"], dependencies=protected)
# app.include_router(contact.router, tags=["Contact"], dependencies=protected)

app.include_router(resources.router, prefix="/api", tags=["Resources"], dependencies=protected)
app.include_router(resources.router, tags=["Resources"], dependencies=protected)

app.include_router(request_demo.router, prefix="/api", tags=["Request Demo"], dependencies=protected)
app.include_router(request_demo.router, tags=["Request Demo"], dependencies=protected)

app.include_router(user_dashboard.router, prefix="/api", tags=["User Dashboard"], dependencies=protected)
app.include_router(user_dashboard.router, tags=["User Dashboard"], dependencies=protected)

app.include_router(batch.router, prefix="/api", tags=["Batch"], dependencies=protected)
app.include_router(batch.router, tags=["Batch"], dependencies=protected)

app.include_router(authuser.router, prefix="/api", tags=["Authuser"], dependencies=protected)
app.include_router(authuser.router, tags=["Authuser"], dependencies=protected)

app.include_router(session.router, prefix="/api", tags=["Sessions"], dependencies=protected)
app.include_router(session.router, tags=["Sessions"], dependencies=protected)

app.include_router(recording.router, prefix="/api", tags=["Recordings"], dependencies=protected)
app.include_router(recording.router, tags=["Recordings"], dependencies=protected)

# course & related
app.include_router(course.router, prefix="/api", tags=["Courses"], dependencies=protected)
app.include_router(course.router, tags=["Courses"], dependencies=protected)
app.include_router(subject.router, prefix="/api", tags=["Subjects"], dependencies=protected)
app.include_router(subject.router, tags=["Subjects"], dependencies=protected)
app.include_router(course_subject.router, prefix="/api", tags=["Course Subjects"], dependencies=protected)
app.include_router(course_subject.router, tags=["Course Subjects"], dependencies=protected)
app.include_router(course_content.router, prefix="/api", tags=["Course Contents"], dependencies=protected)
app.include_router(course_content.router, tags=["Course Contents"], dependencies=protected)
app.include_router(course_material.router, prefix="/api", tags=["Course Materials"], dependencies=protected)
app.include_router(course_material.router, tags=["Course Materials"], dependencies=protected)

app.include_router(referrals.router, prefix="/api", tags=["Referrals"], dependencies=protected)
app.include_router(referrals.router, tags=["Referrals"], dependencies=protected)

# Admin-only routers
app.include_router(avatar_dashboard.router, prefix="/api", tags=["Avatar Dashboard"], dependencies=admin_only)
app.include_router(avatar_dashboard.router, tags=["Avatar Dashboard"], dependencies=admin_only)

# Public routers (no token required)
# contact — make it PUBLIC (no authentication required)
app.include_router(contact.router, prefix="/api", tags=["Contact"])
app.include_router(contact.router, tags=["Contact"])


app.include_router(register.router, prefix="/api", tags=["Register"])
app.include_router(register.router, tags=["Register"])

app.include_router(login.router, prefix="/api", tags=["Login"])
app.include_router(login.router, tags=["Login"])

app.include_router(unsubscribe.router, prefix="/api", tags=["Unsubscribe"])
app.include_router(unsubscribe.router, tags=["Unsubscribe"])

app.include_router(google_auth.router, prefix="/api", tags=["Google Authentication"])
app.include_router(google_auth.router, tags=["Google Authentication"])

# ===============================
# Database dependency
# ===============================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ===============================
# If you run with: uvicorn fapi.main:app --reload
# ===============================
