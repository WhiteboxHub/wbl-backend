from fastapi import HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any

from fapi.utils.db_queries import fetch_candidate_id_and_status_by_email

def get_candidate_id(user, db: Session):
    # uname in AuthUserORM is usually the email in CandidateORM
    candidate_info = fetch_candidate_id_and_status_by_email(db, user.uname)
    if not candidate_info:
         raise HTTPException(status_code=404, detail="Candidate profile not found for this user.")
    return candidate_info.candidateid

def validate_resume_json(resume_json: Dict[str, Any]):
    # Define sets of possible keys for each mandatory field
    field_maps = {
        "Work Experience": ["Work Experience", "experience", "work", "work_experience", "employment"],
        "Education": ["Education", "education", "academics"],
        "LinkedIn": ["LinkedIn", "linkedin", "linkedin_url"],
        "Contact Number": ["Contact Number", "phone", "contact_number", "mobile", "phone_number"],
        "Email ID": ["Email ID", "email", "email_id"]
    }
    
    def find_field(data, keys):
        if isinstance(data, dict):
            for k, v in data.items():
                if k in keys and str(v).strip():
                    return True
                if find_field(v, keys):
                    return True
        elif isinstance(data, list):
            for item in data:
                if find_field(item, keys):
                    return True
        return False

    missing_fields = []
    
    for label, possible_keys in field_maps.items():
        if not find_field(resume_json, possible_keys):
            missing_fields.append(label)
    
    if missing_fields:
        raise HTTPException(
            status_code=400, 
            detail=f"Missing or invalid mandatory fields: {', '.join(missing_fields)}"
        )

def detect_provider(api_key: str) -> str:
    if api_key.startswith("sk-ant"):
        return "claude"
    if api_key.startswith("sk-") or api_key.startswith("sk-proj-"):
        return "openai"
    if api_key.startswith("AIzaSy"):
        return "gemini"
    return "unknown"
