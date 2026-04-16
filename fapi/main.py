import asyncio
import logging
import traceback
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from fapi.api import approval
from fapi.api.routes import (
    authuser,
    avatar_dashboard,
    batch,
    candidate,
    candidate_dashboard,
    company,
    company_contact,
    contact,
    course,
    course_content,
    course_material,
    course_subject,
    delivery_engine,
    email_position,
    email_service,
    email_smtp_credentials,
    email_template,
    employee,
    employee_dashboard,
    employee_tasks,
    google_auth,
    hr_contact,
    internal_documents,
    job_automation_keywords,
    job_click,
    job_listing,
    jobs,
    leads,
    linkedin_only_contact,
    login,
    outreach_email_recipient,
    outreach_orchestrator,
    password,
    personal_domain_contact,
    placement_commission,
    placement_fee_collection,
    potential_leads,
    projects,
    recording,
    recording_batch,
    referrals,
    register,
    request_demo,
    resources,
    session,
    subject,
    talent_search,
    unsubscribe,
    user_dashboard,
    user_role,
    vendor,
    vendor_contact,
    weekly_workflow,
    automation_contact_extract,
    automation_workflow,
    automation_workflow_log,
    automation_workflow_schedule,
)
from fapi.api.routes.coderpad import router as coderpad_router
from fapi.api.routes.dynamic_weekly_report import router as dynamic_weekly_report_router
from fapi.auth import JWTAuthorizationMiddleware
from fapi.core.config import limiter
from fapi.core.redis_client import redis_client
from fapi.db import database as db_database
from fapi.db.database import SessionLocal
from fapi.db.models import Base
from fapi.utils.permission_gate import enforce_access

# import fapi.utils.workflow_scheduler_service  # auto-starts the workflow scheduler

app = FastAPI(title="WBL Backend")
app.include_router(approval.router, prefix="/api", tags=["Approval"],)
app.state.limiter = limiter



origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def init_auth():
    print("AUTH SCRIPT STARTED")

async def rate_limit_handler(request: Request, exc: Exception):
    return await _rate_limit_exceeded_handler(request, exc)  # type: ignore[arg-type]


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wbl")

@app.on_event("startup")
async def startup_event():
    redis_client.get_client()

    Base.metadata.create_all(bind=db_database.engine)

    try:
        from fapi.db.models import CodeSnippetORM, CodeExecutionLogORM, CoderpadQuestionORM
        CodeSnippetORM.__table__.create(bind=db_database.engine, checkfirst=True)
        CodeExecutionLogORM.__table__.create(bind=db_database.engine, checkfirst=True)
        CoderpadQuestionORM.__table__.create(bind=db_database.engine, checkfirst=True)
        logger.info("CoderPad tables checked/created successfully.")
    except Exception as e:
        logger.error(f"Failed to create CoderPad tables: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    pass  # Upstash Redis is HTTP-based; no persistent connection to close

@app.get("/api/redis-health", tags=["Health"])
async def redis_health():
    client = redis_client.get_client()
    if client:
        try:
            client.ping()
            return {"status": "connected", "message": "Redis is up and running"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "disconnected", "message": "Redis client not initialized"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "https://whitebox-learning.com",
        "https://www.whitebox-learning.com",
        "https://innova-path.com",
        "https://www.innova-path.com",
        "https://wbl-frontend-560359652969.us-central1.run.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_exceptions(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception:
        logger.error("Unhandled exception during request: %s %s",
                     request.method, request.url)
        logger.error(traceback.format_exc())
        raise

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/redis-test")
def redis_test():
    from fapi.core.redis_client import redis_client
    client = redis_client.get_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Redis client is not initialized")

    client.set("ping", "pong", ex=60)
    value = client.get("ping")
    return {"value": value} 

# Base Routes
app.include_router(job_click.router, prefix="/api", tags=["Job Link Click Tracking"], dependencies=[Depends(enforce_access)])
app.include_router(candidate.router, prefix="/api", tags=["Candidate"], dependencies=[Depends(enforce_access)])
app.include_router(vendor_contact.router, prefix="/api", tags=["Vendor Contact Extracts"], dependencies=[Depends(enforce_access)])
app.include_router(vendor.router, prefix="/api", tags=["Vendor"], dependencies=[Depends(enforce_access)])
app.include_router(leads.router, prefix="/api", tags=["Leads"], dependencies=[Depends(enforce_access)])
app.include_router(employee.router, prefix="/api", tags=["Employee"], dependencies=[Depends(enforce_access)])
app.include_router(employee_tasks.router, prefix="/api", tags=["Employee Tasks"])
app.include_router(talent_search.router,  prefix="/api", tags=["Talent Search"], dependencies=[Depends(enforce_access)])
app.include_router(user_role.router, prefix="/api", tags=["User Role"])
app.include_router(password.router, prefix="/api", tags=["Password"])
app.include_router(request_demo.router, prefix="/api", tags=["Request Demo"], dependencies=[Depends(enforce_access)])
app.include_router(user_dashboard.router, prefix="/api", tags=["User Dashboard"], dependencies=[Depends(enforce_access)])
app.include_router(batch.router, prefix="/api", tags=["Batch"],  dependencies=[Depends(enforce_access)])
app.include_router(authuser.router, prefix="/api", tags=["Authuser"], dependencies=[Depends(enforce_access)])
app.include_router(session.router, prefix="/api", tags=["Sessions"], dependencies=[Depends(enforce_access)])
app.include_router(recording.router, prefix="/api", tags=["Recordings"], dependencies=[Depends(enforce_access)])
app.include_router(recording_batch.router, prefix="/api", tags=["Recording Batches"], dependencies=[Depends(enforce_access)])
app.include_router(course.router, prefix="/api", tags=["Courses"], dependencies=[Depends(enforce_access)])
app.include_router(subject.router, prefix="/api", tags=["Subjects"], dependencies=[Depends(enforce_access)])
app.include_router(course_subject.router, prefix="/api", tags=["Course Subjects"], dependencies=[Depends(enforce_access)])
app.include_router(course_content.router, prefix="/api", tags=["Course Contents"], dependencies=[Depends(enforce_access)])
app.include_router(course_material.router, prefix="/api", tags=["Course Materials"], dependencies=[Depends(enforce_access)])
app.include_router(referrals.router, prefix="/api", tags=["Referrals"])
app.include_router(avatar_dashboard.router, prefix="/api", tags=["Avatar Dashboard"], dependencies=[Depends(enforce_access)])
app.include_router(projects.router, prefix="/api", tags=["Projects"], dependencies=[Depends(enforce_access)])
app.include_router(contact.router, prefix="/api", tags=["Contact"])
app.include_router(resources.router, prefix="/api", tags=["Resources"], dependencies=[Depends(enforce_access)])
app.include_router(register.router,  prefix="/api", tags=["Register"])
app.include_router(login.router,  prefix="/api", tags=["Login"])
app.include_router(unsubscribe.router, prefix="/api", tags=["Unsubscribe"])
app.include_router(google_auth.router, prefix="/api", tags=["Google Authentication"])
app.include_router(candidate_dashboard.router, tags=["Candidate Dashboard"])
app.include_router(internal_documents.router, prefix="/api/internal-documents", tags=["Internal Documents"])
app.include_router(jobs.router, prefix="/api", tags=["Job Activity Log"], dependencies=[Depends(enforce_access)])
app.include_router(placement_fee_collection.router, prefix="/api", tags=["Placement Fee Collection"], dependencies=[Depends(enforce_access)])
app.include_router(placement_commission.router, prefix="/api", tags=["Placement Commission"], dependencies=[Depends(enforce_access)])
app.include_router(job_automation_keywords.router, prefix="/api", tags=["Job Automation Keywords"], dependencies=[Depends(enforce_access)])
app.include_router(hr_contact.router, prefix="/api", tags=["HR Contact"], dependencies=[Depends(enforce_access)])

# Job and Outreach Routers
app.include_router(job_listing.router, prefix="/api", tags=["Positions"], dependencies=[Depends(enforce_access)])
app.include_router(email_position.router, prefix="/api", tags=["Email Positions"], dependencies=[Depends(enforce_access)])
app.include_router(employee_dashboard.router, prefix="/api", tags=["Employee Dashboard"], dependencies=[Depends(enforce_access)])
app.include_router(email_service.router, prefix="/api", tags=["Internal Email Service"])

app.include_router(dynamic_weekly_report_router, prefix="/api", tags=["Dynamic Weekly Report"])

app.include_router(company.router, prefix="/api", tags=["Companies"], dependencies=[Depends(enforce_access)])
app.include_router(company_contact.router, prefix="/api", tags=["Company Contacts"], dependencies=[Depends(enforce_access)])
app.include_router(potential_leads.router, prefix="/api", tags=["Potential Leads"], dependencies=[Depends(enforce_access)])
app.include_router(personal_domain_contact.router, prefix="/api", tags=["Personal Domain Contacts"], dependencies=[Depends(enforce_access)])
app.include_router(outreach_email_recipient.router, prefix="/api", tags=["Outreach Email Recipients"], dependencies=[Depends(enforce_access)])
app.include_router(linkedin_only_contact.router, prefix="/api", tags=["Linkedin Only Contacts"], dependencies=[Depends(enforce_access)])
app.include_router(automation_contact_extract.router, prefix="/api", tags=["Automation Extracts"], dependencies=[Depends(enforce_access)])

# Automation Workflow Routers
app.include_router(delivery_engine.router, prefix="/api", tags=["Delivery Engine"], dependencies=[Depends(enforce_access)])
app.include_router(email_template.router, prefix="/api", tags=["Email Template"], dependencies=[Depends(enforce_access)])
app.include_router(automation_workflow.router, prefix="/api", tags=["Automation Workflow"], dependencies=[Depends(enforce_access)])
app.include_router(automation_workflow_schedule.router, prefix="/api", tags=["Automation Workflow Schedule"], dependencies=[Depends(enforce_access)])
app.include_router(automation_workflow_log.router, prefix="/api", tags=["Automation Workflow Log"], dependencies=[Depends(enforce_access)])
app.include_router(coderpad_router, prefix="/api", tags=["CoderPad"], dependencies=[Depends(enforce_access)])
app.include_router(outreach_orchestrator.router, prefix="/api", tags=["Outreach Orchestrator"])
app.include_router(weekly_workflow.router, prefix="/api/weekly-workflow", tags=["Weekly Workflow"])
app.include_router(email_smtp_credentials.router, prefix="/api", tags=["Email SMTP Credentials"], dependencies=[Depends(enforce_access)])
