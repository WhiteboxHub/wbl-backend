import os
import json
from pathlib import Path
from typing import Any, Optional, List
import logging

from fapi.db.database import get_db
from fapi.utils.llm_service import call_llm_with_context

logger = logging.getLogger(__name__)

def parse_pdf(file_path: str) -> str:
    import fitz  # PyMuPDF
    text = []
    with fitz.open(file_path) as doc:
        for page in doc:
            page_text = page.get_text()
            links = page.get_links()
            for link in links:
                if 'uri' in link:
                    page_text += f"\n[Link found in document: {link['uri']}]"
            text.append(page_text)
    return "\n".join(text).strip()

def parse_docx(file_path: str) -> str:
    from docx import Document
    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs).strip()

def parse_json(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return json.dumps(data, indent=2)

def parse_resume(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return parse_pdf(file_path)
    elif ext in (".docx", ".doc"):
        return parse_docx(file_path)
    elif ext == ".json":
        return parse_json(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Please upload a PDF, DOCX, or JSON.")

def generate_fallback_template(candidate_name: str, candidate_email: str, candidate_phone: str) -> dict:
    first_name = ""
    last_name = ""
    if candidate_name:
        parts = candidate_name.strip().split()
        if len(parts) > 0:
            first_name = parts[0]
            if len(parts) > 1:
                last_name = " ".join(parts[1:])
            else:
                last_name = ""
    return {
        "personal": {
            "first_name": first_name or "First",
            "last_name": last_name or "Last",
            "email": candidate_email or "email@example.com",
            "phone": candidate_phone or "+1 (123) 456-7890",
            "location": "City, State, Country",
            "linkedin": "https://www.linkedin.com/in/yourprofile",
            "github": "https://github.com/yourprofile"
        },
        "education": [
            {
                "degree": "Degree / Field of Study (e.g., Bachelor of Science)",
                "institution": "University / Institution Name",
                "location": "City, State",
                "start_date": "YYYY-MM",
                "end_date": "YYYY-MM"
            }
        ],
        "experience": [
            {
                "company": "Company Name Placeholder",
                "title": "Your Role / Position",
                "location": "City, State",
                "start_date": "YYYY-MM",
                "end_date": "Present",
                "description": "Brief summary of your role and responsibilities.",
                "achievements": [
                    "Designed and implemented high-performance backend systems and APIs."
                ]
            }
        ],
        "skills": [
            "Python",
            "JavaScript",
            "SQL",
            "Docker",
            "Git"
        ]
    }

def extract_latest_company_bg(user_id: str, resume_json: dict, api_key: str, provider: str = "openai"):
    from fapi.db.database import engine
    from sqlalchemy import text

    prompt = f"""
    Extract the candidate's latest project details from the following resume JSON to populate an 18-field project explanation form.
    Return ONLY a JSON object with the following keys, populated with information if found in the resume, otherwise leave them as empty strings:
    - company_name
    - domain
    - background (1-2 sentences summarizing their experience)
    - skills (a list of strings)
    - product
    - architecture
    - business_value
    - role
    - business_problem
    - previous_system
    - key_problems
    - ai_techniques
    - agent_usage (must be exactly 'Agent', 'Hybrid', or 'None')
    - impact
    - evaluation_approach
    - challenges_learnings
    - learnings
    - future_roadmap

    Resume:
    {json.dumps(resume_json)[:5000]}
    """

    try:
        from fapi.utils.llm_service import call_llm_with_context
        res_str = call_llm_with_context(
            api_key=api_key,
            provider=provider,
            prompt=prompt,
            system_prompt="You are an expert resume parser.",
            response_format="json_object",
        )

        res_str = res_str.strip()
        if res_str.startswith("```json"):
            res_str = res_str[7:]
        if res_str.startswith("```"):
            res_str = res_str[3:]
        if res_str.endswith("```"):
            res_str = res_str[:-3]

        data = json.loads(res_str)
        company_name     = data.get("company_name", "")
        domain           = data.get("domain", "")
        background       = data.get("background", "")
        skills           = data.get("skills", [])
        product          = data.get("product", "")
        architecture     = data.get("architecture", "")
        business_value   = data.get("business_value", "")
        role             = data.get("role", "")
        business_problem = data.get("business_problem", "")
        previous_system  = data.get("previous_system", "")
        key_problems     = data.get("key_problems", "")
        ai_techniques    = data.get("ai_techniques", "")
        agent_usage      = data.get("agent_usage", "None")
        impact           = data.get("impact", "")
        evaluation_approach   = data.get("evaluation_approach", "")
        challenges_learnings  = data.get("challenges_learnings", "")
        learnings        = data.get("learnings", "")
        future_roadmap   = data.get("future_roadmap", "")

        if company_name or domain or product:
            try:
                with engine.connect() as conn:
                    marketing_id = int(user_id)
                    conn.execute(
                        text("""
                        INSERT INTO aiprep_tool_project_context (
                            user_id, company_name, domain, product, business_problem, previous_system,
                            key_problems, ai_techniques, agent_usage, impact, evaluation_approach,
                            challenges_learnings, learnings, future_roadmap,
                            background, skills, architecture, business_value, role
                        )
                        VALUES (:u, :c, :d, :p, :bp, :ps, :kp, :at, :au, :im, :ea, :cl, :l, :fr, :bg, :sk, :ar, :bv, :r)
                        ON DUPLICATE KEY UPDATE
                            company_name = VALUES(company_name),
                            domain = VALUES(domain),
                            product = VALUES(product),
                            business_problem = VALUES(business_problem),
                            previous_system = VALUES(previous_system),
                            key_problems = VALUES(key_problems),
                            ai_techniques = VALUES(ai_techniques),
                            agent_usage = VALUES(agent_usage),
                            impact = VALUES(impact),
                            evaluation_approach = VALUES(evaluation_approach),
                            challenges_learnings = VALUES(challenges_learnings),
                            learnings = VALUES(learnings),
                            future_roadmap = VALUES(future_roadmap),
                            background = VALUES(background),
                            skills = VALUES(skills),
                            architecture = VALUES(architecture),
                            business_value = VALUES(business_value),
                            role = VALUES(role)
                        """),
                        {
                            "u": marketing_id, "c": company_name, "d": domain, "p": product,
                            "bp": business_problem, "ps": previous_system, "kp": key_problems,
                            "at": ai_techniques, "au": agent_usage, "im": impact, "ea": evaluation_approach,
                            "cl": challenges_learnings, "l": learnings, "fr": future_roadmap,
                            "bg": background, "sk": json.dumps(skills), "ar": architecture,
                            "bv": business_value, "r": role
                        }
                    )
                    conn.commit()
            except Exception as e:
                logger.error(f"Failed to update project context DB: {e}")
    except Exception as e:
        logger.error(f"Background extraction failed: {str(e)}")

def process_resume_parsing(content: bytes, filename: str, candidate_id: int, marketing_id: int, db) -> dict:
    import tempfile
    from fapi.utils.encryption_utils import decrypt_api_key
    from fapi.utils.llm_service import generate_text
    import asyncio
    from fapi.db.models import CandidateLlmApiKeyORM

    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        extracted_text = parse_resume(tmp_path)
    except Exception as e:
        raise ValueError(f"Failed to extract text from binary resume: {str(e)}")
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    if not extracted_text.strip():
        raise ValueError("The uploaded file contains no readable text content.")

    keys = db.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.candidate_id == candidate_id).order_by(CandidateLlmApiKeyORM.is_default.desc(), CandidateLlmApiKeyORM.updated_at.desc(), CandidateLlmApiKeyORM.id.desc()).all()
    
    if not keys:
        raise ValueError("No active LLM API key configured. Please set up your LLM key in 'My LLM Setup' first.")

    system_prompt = """You are an expert resume parsing assistant.
Your task is to analyze the candidate's raw resume text and extract all details into a clean, structured JSON format matching the standard JSON Resume schema EXACTLY:
{
  "basics": {
    "name": "Candidate Full Name",
    "label": "Primary Job Title or Role",
    "image": "",
    "email": "Email Address (REQUIRED - must be present)",
    "url": "Personal website or portfolio URL",
    "summary": "A 2-3 sentence professional summary extracted or inferred from the resume",
    "location": {
      "address": "Street Address",
      "postalCode": "Postal/Zip Code",
      "city": "City",
      "countryCode": "Country Code (e.g. US)",
      "region": "State/Region"
    },
    "profiles": [
      {
        "network": "LinkedIN",
        "username": "LinkedIn Username",
        "url": "Full LinkedIn URL (REQUIRED)"
      },
      {
        "network": "Github",
        "username": "Github Username",
        "url": "Full Github URL"
      }
    ]
  },
  "work": [
    {
      "name": "Company Name",
      "position": "Job Title / Role",
      "url": "Company URL if available",
      "startDate": "YYYY-MM-DD",
      "endDate": "YYYY-MM-DD or 'Present' if current",
      "summary": "Brief summary of role",
      "highlights": [
        "Extract EVERY SINGLE bullet point, achievement, and responsibility listed under this role exactly as they appear",
        "Do not summarize or truncate the bullet points. Include all of them."
      ]
    }
  ],
  "education": [
    {
      "institution": "University/School Name",
      "url": "Institution URL if available",
      "area": "Field of Study / Major",
      "studyType": "Degree Type (e.g. Masters, Bachelors)",
      "startDate": "YYYY-MM-DD",
      "endDate": "YYYY-MM-DD",
      "score": "GPA if available",
      "courses": []
    }
  ],
  "skills": [
    {
      "name": "Skill Category (e.g. Programming Languages, Frameworks)",
      "keywords": [
        "Skill 1",
        "Skill 2",
        "Skill 3"
      ]
    }
  ],
  "custom_fields": {
    "eeo": {
      "gender": "decline"
    },
    "legal": {
      "work_auth_us": true
    },
    "technical_screening": {
      "years_python": 0
    },
    "application_logistics": {
      "willing_to_relocate": "yes/no/null",
      "willing_to_travel": "yes/no/null"
    }
  }
}
"""
    used_provider = None
    used_api_key = None
    use_fallback = True

    last_error = None
    for idx, key_obj in enumerate(keys):
        decrypted_key = decrypt_api_key(key_obj.api_key)
        if decrypted_key == "DECRYPTION_FAILED":
            continue
            
        provider = (key_obj.provider_name or "").lower()
        if "openai" in provider:
            provider = "openai"
        elif "gemini" in provider or "google" in provider:
            provider = "gemini"
        elif "claude" in provider or "anthropic" in provider:
            provider = "claude"
        else:
            provider = "openai"

        try:
            logger.info(f"Attempting parse with key {idx+1}/{len(keys)} (Provider: {provider})...")
            parsed_json_str = generate_text(
                prompt=extracted_text,
                api_key=decrypted_key,
                provider=provider,
                system_prompt=system_prompt,
                response_format="json_object"
            )
            used_api_key = decrypted_key
            used_provider = provider
            use_fallback = False
            logger.info(f"Successfully parsed resume using candidate key {idx+1}!")
            break
        except Exception as e:
            import traceback
            traceback.print_exc()
            last_error = str(e)
            logger.warning(f"Candidate key {idx+1} failed: {e}")
            continue

    if use_fallback:
        raise ValueError(f"All candidate LLM API keys failed. Last error: {last_error}")
    else:
        parsed_json_str = parsed_json_str.strip()
        if parsed_json_str.startswith("```json"):
            parsed_json_str = parsed_json_str[7:]
        if parsed_json_str.startswith("```"):
            parsed_json_str = parsed_json_str[3:]
        if parsed_json_str.endswith("```"):
            parsed_json_str = parsed_json_str[:-3]

        try:
            parsed_json = json.loads(parsed_json_str)
        except Exception as e:
            raise ValueError(f"LLM returned invalid JSON: {str(e)}")

    parsed_json["_meta_filename"] = filename
    
    # Fire off bg task for context extraction if a valid key was used
    if not use_fallback and used_api_key:
        def run_bg():
            extract_latest_company_bg(str(marketing_id), parsed_json, used_api_key, used_provider)
            
        try:
            import threading
            t = threading.Thread(target=run_bg)
            t.start()
        except Exception as e:
            logger.error(f"Failed to start bg thread: {e}")

    return parsed_json

def _get_candidate_id(db, user_email: str) -> int:
    from sqlalchemy import text
    row = db.execute(
        text("""
        SELECT c.id 
        FROM candidate c 
        JOIN authuser a ON c.email = a.uname 
        WHERE a.uname = :email
        """),
        {"email": user_email}
    ).fetchone()
    
    if not row:
        row = db.execute(text("SELECT id FROM candidate WHERE email = :email"), {"email": user_email}).fetchone()
        
    if not row:
        raise ValueError(f"Candidate profile not found for email: {user_email}")
    return row[0]

def _mask_key(raw: str) -> str:
    if len(raw) > 4:
        return "*" * (len(raw) - 4) + raw[-4:]
    return "****"

def _validate_api_key(provider: str, api_key: str) -> tuple[bool, bool]:
    import requests
    is_valid = False
    supports_voice = False
    try:
        if provider == "openai":
            res = requests.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=5,
            )
            if res.status_code == 200:
                is_valid = True
                models = res.json().get("data", [])
                supports_voice = any(m["id"] == "whisper-1" for m in models)
        elif provider in ("claude", "anthropic"):
            res = requests.get(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                timeout=5,
            )
            if res.status_code == 200:
                is_valid = True
                supports_voice = True
        elif provider in ("gemini", "google"):
            res = requests.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
                timeout=5,
            )
            if res.status_code == 200:
                is_valid = True
                models = res.json().get("models", [])
                supports_voice = any("gemini-1.5" in m["name"] for m in models)
        else:
            is_valid = True
            supports_voice = True
    except Exception as e:
        logger.error(f"Error validating API key for {provider}: {e}")
    return is_valid, supports_voice

def save_resume_for_session(db, session_id: str, resume_data: dict) -> None:
    from sqlalchemy import text
    resume_json_str = json.dumps(resume_data)
    marketing_id = int(session_id)
    db.execute(
        text("""
        UPDATE candidate_marketing
        SET candidate_json = :r
        WHERE id = :mid
        """),
        {"r": resume_json_str, "mid": marketing_id}
    )
    db.commit()
