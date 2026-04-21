# Import all route modules
from . import (
    candidate, leads, google_auth, talent_search, user_role,
    contact, login, register, resources, vendor_contact,
    vendor, request_demo, unsubscribe,
    user_dashboard, password, employee, course, subject, 
    course_subject, course_content, course_material, batch,
    authuser, avatar_dashboard, session, recording, recording_batch,
    referrals, candidate_dashboard, internal_documents,
    jobs, placement_fee_collection, employee_tasks, job_automation_keywords,
    hr_contact, projects, job_listing, employee_dashboard,
    email_service,
    delivery_engine, email_template, automation_workflow,
    automation_workflow_schedule, automation_workflow_log,
    automation_contact_extract,
    outreach_orchestrator,
    company, company_contact, potential_leads,
    personal_domain_contact, outreach_email_recipient,
    linkedin_only_contact, email_smtp_credentials,
    placement_commission,
    job_click, coderpad
)

__all__ = [
    "authuser", "avatar_dashboard", "batch", "candidate", "candidate_dashboard",
    "company", "company_contact", "contact", "course", "course_content",
    "course_material", "course_subject", "delivery_engine", "email_position",
    "email_service", "email_smtp_credentials", "email_template", "employee",
    "employee_dashboard", "employee_tasks", "google_auth", "hr_contact",
    "internal_documents", "job_automation_keywords", "job_click", "job_listing",
    "jobs", "leads", "linkedin_only_contact", "login", "outreach_email_recipient",
    "outreach_orchestrator", "password", "personal_domain_contact",
    "placement_commission", "placement_fee_collection", "potential_leads",
    "projects", "recording", "recording_batch", "referrals", "register",
    "request_demo", "resources", "session", "subject", "talent_search",
    "unsubscribe", "user_dashboard", "user_role", "vendor", "vendor_contact",
    "weekly_workflow", "automation_contact_extract", "automation_workflow",
    "automation_workflow_log", "automation_workflow_schedule", "coderpad"
]
