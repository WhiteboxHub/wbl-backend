from fapi.utils.permission_gate import enforce_access
from fapi.api.routes import (
    candidate, leads, google_auth, talent_search, user_role,
    contact, login, register, resources, vendor_contact,
    vendor, request_demo, unsubscribe,
    user_dashboard, password, employee, course, subject, course_subject,
    course_content, course_material, batch, authuser, avatar_dashboard,
    session, recording, recording_batch, referrals, candidate_dashboard, internal_documents,
    jobs, placement_fee_collection, employee_tasks, job_automation_keywords, hr_contact, projects,
    position, raw_position, employee_dashboard, job_definition, job_schedule, job_run, 
    job_request, email_engine, outreach_contact, job_trigger, remote_worker
)
from fapi.email_orchestrator import start_background_orchestrator
from fapi.db.database import SessionLocal
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
import logging
import traceback

app = FastAPI(title="WBL Backend")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wbl")




app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://whitebox-learning.com",
        "https://www.whitebox-learning.com",
        "https://innova-path.com",
        "https://www.innova-path.com",
        "https://wbl-frontend-560359652969.us-central1.run.app",
        "http://localhost:3000",
        "http://127.0.0.1:8000"
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


app.include_router(candidate.router, prefix="/api", tags=["Candidate"], dependencies=[Depends(enforce_access)])
app.include_router(leads.router, prefix="/api", tags=["Leads"], dependencies=[Depends(enforce_access)])
app.include_router(vendor_contact.router, prefix="/api", tags=["Vendor Contact Extracts"], dependencies=[Depends(enforce_access)])
app.include_router(vendor.router, prefix="/api", tags=["Vendor"], dependencies=[Depends(enforce_access)])
app.include_router(employee.router, prefix="/api", tags=["Employee"], dependencies=[Depends(enforce_access)])
app.include_router(employee_tasks.router, prefix="/api", tags=["Employee Tasks"])
app.include_router(talent_search.router,  prefix="/api", tags=["Talent Search"], dependencies=[Depends(enforce_access)])
app.include_router(user_role.router, prefix="/api", tags=["User Role"])
app.include_router(password.router, prefix="/api", tags=["Password"])
app.include_router(request_demo.router, prefix="/api",
                   tags=["Request Demo"], dependencies=[Depends(enforce_access)])
app.include_router(user_dashboard.router, prefix="/api",
                   tags=["User Dashboard"], dependencies=[Depends(enforce_access)])
app.include_router(batch.router, prefix="/api",
                   tags=["Batch"],  dependencies=[Depends(enforce_access)])
app.include_router(authuser.router, prefix="/api",
                   tags=["Authuser"], dependencies=[Depends(enforce_access)])
app.include_router(session.router, prefix="/api",
                   tags=["Sessions"], dependencies=[Depends(enforce_access)])
app.include_router(recording.router, prefix="/api",
                   tags=["Recordings"], dependencies=[Depends(enforce_access)])
app.include_router(recording_batch.router, prefix="/api",
                   tags=["Recording Batches"], dependencies=[Depends(enforce_access)])
app.include_router(course.router, prefix="/api",
                   tags=["Courses"], dependencies=[Depends(enforce_access)])
app.include_router(subject.router, prefix="/api",
                   tags=["Subjects"], dependencies=[Depends(enforce_access)])
app.include_router(course_subject.router, prefix="/api",
                   tags=["Course Subjects"], dependencies=[Depends(enforce_access)])
app.include_router(course_content.router, prefix="/api",
                   tags=["Course Contents"], dependencies=[Depends(enforce_access)])
app.include_router(course_material.router, prefix="/api",
                   tags=["Course Materials"], dependencies=[Depends(enforce_access)])
app.include_router(referrals.router, prefix="/api", tags=["Referrals"])
app.include_router(avatar_dashboard.router, prefix="/api",
                   tags=["Avatar Dashboard"], dependencies=[Depends(enforce_access)])
app.include_router(candidate.router, prefix="/api",
                   tags=["Candidates"], dependencies=[Depends(enforce_access)])
app.include_router(projects.router, prefix="/api", tags=["Projects"], dependencies=[Depends(enforce_access)])
app.include_router(contact.router, prefix="/api", tags=["Contact"])
app.include_router(resources.router, prefix="/api",
                   tags=["Resources"], dependencies=[Depends(enforce_access)])
app.include_router(register.router,  prefix="/api", tags=["Register"])
app.include_router(login.router,  prefix="/api", tags=["Login"])
app.include_router(unsubscribe.router, prefix="/api", tags=["Unsubscribe"])
app.include_router(google_auth.router, prefix="/api",
                   tags=["Google Authentication"])
app.include_router(candidate_dashboard.router, tags=["Candidate Dashboard"])
app.include_router(internal_documents.router, prefix="/api/internal-documents", tags=["Internal Documents"])
app.include_router(jobs.router, prefix="/api", tags=["Job Activity Log"], dependencies=[Depends(enforce_access)])
app.include_router(placement_fee_collection.router, prefix="/api", tags=["Placement Fee Collection"], dependencies=[Depends(enforce_access)])
app.include_router(job_automation_keywords.router, prefix="/api", tags=["Job Automation Keywords"], dependencies=[Depends(enforce_access)])
app.include_router(hr_contact.router, prefix="/api", tags=["HR Contact"], dependencies=[Depends(enforce_access)])

# New Job Automation Routers
app.include_router(job_definition.router, prefix="/api", tags=["Job Definition"], dependencies=[Depends(enforce_access)])
app.include_router(job_schedule.router, prefix="/api", tags=["Job Schedule"], dependencies=[Depends(enforce_access)])
app.include_router(job_run.router, prefix="/api", tags=["Job Run"], dependencies=[Depends(enforce_access)])
app.include_router(job_request.router, prefix="/api", tags=["Job Request"], dependencies=[Depends(enforce_access)])
app.include_router(email_engine.router, prefix="/api", tags=["Email Engine"], dependencies=[Depends(enforce_access)])
app.include_router(outreach_contact.router, prefix="/api", tags=["Outreach Contact"], dependencies=[Depends(enforce_access)])
app.include_router(job_trigger.router, prefix="/api", tags=["Job Trigger"], dependencies=[Depends(enforce_access)])
app.include_router(remote_worker.router, prefix="/api", tags=["Remote Worker"])
app.include_router(position.router, prefix="/api", tags=["Positions"], dependencies=[Depends(enforce_access)])
app.include_router(raw_position.router, prefix="/api", tags=["Raw Positions"], dependencies=[Depends(enforce_access)])
app.include_router(employee_dashboard.router, prefix="/api", tags=["Employee Dashboard"], dependencies=[Depends(enforce_access)])






