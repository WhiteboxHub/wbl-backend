from fapi.api.routes import candidate_dashboard
from fapi.utils.permission_gate import enforce_access
from fapi.api.routes import (
    candidate, leads, google_auth, talent_search, user_role,
    contact, login, register, resources, vendor_contact,
    vendor, request_demo, unsubscribe,
    user_dashboard, password, employee, course, subject, course_subject,
    course_content, course_material, batch, authuser, avatar_dashboard,
    session, recording, recording_batch, referrals, candidate_dashboard, internal_documents,
    jobs, placement_fee_collection, placement_commission, employee_tasks, job_automation_keywords, hr_contact, projects,
    job_listing, employee_dashboard, email_service,
    delivery_engine, email_template, automation_workflow, 
    automation_workflow_schedule, automation_workflow_log,
    outreach_orchestrator,
    weekly_workflow,
    company, company_contact, potential_leads,personal_domain_contact,outreach_email_recipient,
    linkedin_only_contact, automation_contact_extract, email_smtp_credentials,


    email_position, job_click, coderpad, dynamic_weekly_report, extension_keys, report_data, report_pdf, sync_cli, cli_analytics,
    campaign_email, outreach_email, tracking
)
import fapi.utils.workflow_scheduler_service_utils  # auto-starts the workflow scheduler
import asyncio
from fapi.core.redis_client import redis_client
from fapi.db.database import SessionLocal, engine
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
import logging
import traceback
from sqlalchemy import text
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from fapi.core.config import limiter
import logging
import traceback

app = FastAPI(title="WBL Backend")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


from fastapi.responses import JSONResponse
import logging
logger = logging.getLogger("wbl")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception during request: %s %s: %s", request.method, request.url, exc)
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"}
    )

@app.on_event("startup")
async def startup_event():
    redis_client.get_client()
    from fapi.db.models import (
        CodeSnippetORM,
        CodeExecutionLogORM,
        CoderpadQuestionORM,
        CliUsageEventORM,
        WboxcliApplyAnalyticsORM,
        ApplicationReportORM
    )
    # Ensure all tables (including new columns) are created/updated
    from fapi.db.models import Base
    Base.metadata.create_all(bind=engine, checkfirst=True)

        
    # Ensure missing columns exist (for older DB schemas)
    cm_cols = [
        ("candidate_marketing", [
            ("outreach_date", "DATE"),
            ("run_daily_workflow", "TINYINT(1) NOT NULL DEFAULT 0"),
            ("run_weekly_workflow", "TINYINT(1) NOT NULL DEFAULT 0"),
            ("run_email_extraction", "TINYINT(1) NOT NULL DEFAULT 0"),
            ("run_raw_positions_workflow", "TINYINT(1) NOT NULL DEFAULT 0"),
            ("run_outreach_emails", "TINYINT(1) NOT NULL DEFAULT 0"),
            ("linkedin_post", "TINYINT(1) NOT NULL DEFAULT 0"),
            ("candidate_json", "JSON NULL"),
            ("total_outreach_count", "INT NOT NULL DEFAULT 0"),
            ("daily_outreach_limit", "INT NOT NULL DEFAULT 250"),
            ("max_outreach_limit", "INT NOT NULL DEFAULT 500"),
            ("fcount", "INT NOT NULL DEFAULT 0"),
        ]),
        ("candidate", [
            ("placement_percentage", "INT NULL DEFAULT 13"),
            ("enrollment_status", "VARCHAR(50) NULL DEFAULT 'not completed'"),
        ]),
        ("candidate_interview", [
            ("duration_minutes", "INT NULL DEFAULT 60"),
        ])
    ]
    with engine.connect() as conn:
        for tbl, cols in cm_cols:
            try:
                existing = [row[0] for row in conn.execute(text(f"SHOW COLUMNS FROM {tbl}"))]
                for col_name, col_type in cols:
                    if col_name not in existing:
                        conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
            except Exception as e:
                logger.info(f"Column sync check error for {tbl}: {e}")

    # Ensure user_id column exists in application_report (for older DB schemas)
    try:
        with engine.connect() as conn:
            getattr(conn, "execute")(text("ALTER TABLE application_report ADD COLUMN user_id INT NULL"))
            conn.commit()
    except Exception as e:
        logger.info(f"user_id column in application_report may already exist or failed to add: {e}")
    # Coderpad Tables
    try:
        CodeSnippetORM.__table__.create(bind=engine, checkfirst=True)
        CodeExecutionLogORM.__table__.create(bind=engine, checkfirst=True)
        CoderpadQuestionORM.__table__.create(bind=engine, checkfirst=True)
        CliUsageEventORM.__table__.create(bind=engine, checkfirst=True)
        WboxcliApplyAnalyticsORM.__table__.create(bind=engine, checkfirst=True)

        # ATS Application Report Table
        ApplicationReportORM.__table__.create(bind=engine, checkfirst=True)
        logger.info("CoderPad, CLI analytics, and ATS report tables checked/created successfully.")

    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")



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
    allow_origin_regex=".*",  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Data-Version", "Last-Modified", "Content-Length"],
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
    client.set("ping", "pong", ex=60)
    return {"value": client.get("ping")}

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
app.include_router(candidate_dashboard.router, prefix="/api", tags=["Candidate Dashboard"])
app.include_router(internal_documents.router, prefix="/api/internal-documents", tags=["Internal Documents"])
app.include_router(jobs.router, prefix="/api", tags=["Job Activity Log"], dependencies=[Depends(enforce_access)])
app.include_router(placement_fee_collection.router, prefix="/api", tags=["Placement Fee Collection"], dependencies=[Depends(enforce_access)])
app.include_router(placement_commission.router, prefix="/api", tags=["Placement Commission"], dependencies=[Depends(enforce_access)])
app.include_router(job_automation_keywords.router, prefix="/api", tags=["Job Automation Keywords"], dependencies=[Depends(enforce_access)])
app.include_router(hr_contact.router, prefix="/api", tags=["HR Contact"], dependencies=[Depends(enforce_access)])
app.include_router(sync_cli.router, prefix="/api", tags=["JobCLI Sync"])
app.include_router(cli_analytics.router, prefix="/api", tags=["WboxCLI Analytics"])
app.include_router(tracking.router, prefix="/api", tags=["ATS Reporting"])


# Job and Outreach Routers
app.include_router(job_listing.router, prefix="/api", tags=["Positions"], dependencies=[Depends(enforce_access)])
app.include_router(email_position.router, prefix="/api", tags=["Email Positions"], dependencies=[Depends(enforce_access)])
app.include_router(employee_dashboard.router, prefix="/api", tags=["Employee Dashboard"], dependencies=[Depends(enforce_access)])
app.include_router(email_service.router, prefix="/api", tags=["Internal Email Service"])
app.include_router(dynamic_weekly_report.router, prefix="/api", tags=["Dynamic Weekly Report"])
app.include_router(report_data.router, prefix="/api", tags=["Marketing Report Data"])
app.include_router(report_pdf.router, prefix="/api", tags=["Marketing Report PDF"])
app.include_router(company.router, prefix="/api", tags=["Companies"], dependencies=[Depends(enforce_access)])
app.include_router(company_contact.router, prefix="/api", tags=["Company Contacts"], dependencies=[Depends(enforce_access)])
app.include_router(potential_leads.router, prefix="/api", tags=["Potential Leads"], dependencies=[Depends(enforce_access)])
app.include_router(personal_domain_contact.router, prefix="/api", tags=["Personal Domain Contacts"], dependencies=[Depends(enforce_access)])
app.include_router(outreach_email_recipient.router, prefix="/api", tags=["Outreach Email Recipients"], dependencies=[Depends(enforce_access)])
app.include_router(linkedin_only_contact.router, prefix="/api", tags=["Linkedin Only Contacts"], dependencies=[Depends(enforce_access)])
app.include_router(automation_contact_extract.router, prefix="/api", tags=["Automation Extracts"], dependencies=[Depends(enforce_access)])
app.include_router(extension_keys.router, prefix="/api", tags=["Extension Keys"], dependencies=[Depends(enforce_access)])

# Automation Workflow Routers
app.include_router(delivery_engine.router, prefix="/api", tags=["Delivery Engine"], dependencies=[Depends(enforce_access)])
app.include_router(email_template.router, prefix="/api", tags=["Email Template"], dependencies=[Depends(enforce_access)])
app.include_router(automation_workflow.router, prefix="/api", tags=["Automation Workflow"], dependencies=[Depends(enforce_access)])
app.include_router(automation_workflow_schedule.router, prefix="/api", tags=["Automation Workflow Schedule"], dependencies=[Depends(enforce_access)])
app.include_router(automation_workflow_log.router, prefix="/api", tags=["Automation Workflow Log"], dependencies=[Depends(enforce_access)])
app.include_router(campaign_email.router, prefix="/api", tags=["Campaign Emails"], dependencies=[Depends(enforce_access)])
app.include_router(outreach_email.router, prefix="/api", tags=["Outreach Emails"], dependencies=[Depends(enforce_access)])
app.include_router(coderpad.router, prefix="/api", tags=["CoderPad"], dependencies=[Depends(enforce_access)])
app.include_router(outreach_orchestrator.router, prefix="/api", tags=["Outreach Orchestrator"])
app.include_router(weekly_workflow.router, prefix="/api/weekly-workflow", tags=["Weekly Workflow"])
app.include_router(email_smtp_credentials.router, prefix="/api", tags=["Email SMTP Credentials"], dependencies=[Depends(enforce_access)])