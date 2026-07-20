import os
import json
from pathlib import Path
from typing import Any, Optional, List
import logging

RESUME_PARSER_SYSTEM_PROMPT = """You are an expert resume parsing assistant.
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
                    marketing_id_str = str(marketing_id)
                    existing = conn.query(AiPrepToolProjectContextORM).filter(AiPrepToolProjectContextORM.user_id == marketing_id_str).first()
                    fields = {
                        "company_name": company_name, "domain": domain, "product": product,
                        "business_problem": business_problem, "previous_system": previous_system,
                        "key_problems": key_problems, "ai_techniques": ai_techniques,
                        "agent_usage": agent_usage, "impact": impact,
                        "evaluation_approach": evaluation_approach, "challenges_learnings": challenges_learnings,
                        "learnings": learnings, "future_roadmap": future_roadmap,
                        "background": background, "skills": json.dumps(skills),
                        "architecture": architecture, "business_value": business_value, "role": role
                    }
                    if existing:
                        for k, v in fields.items(): setattr(existing, k, v)
                    else:
                        new_ctx = AiPrepToolProjectContextORM(user_id=marketing_id_str, **fields)
                        conn.add(new_ctx)
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

    system_prompt = RESUME_PARSER_SYSTEM_PROMPT
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
    from fapi.db.models import CandidateORM, AuthUserORM
    row = db.query(CandidateORM.id).join(AuthUserORM, CandidateORM.email == AuthUserORM.uname).filter(AuthUserORM.uname == user_email).first()
    
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
    cm = db.query(CandidateMarketingORM).filter(CandidateMarketingORM.id == marketing_id).first()
    if cm:
        cm.candidate_json = json.loads(resume_json_str) if isinstance(resume_json_str, str) else resume_json_str
    db.commit()

from fastapi import HTTPException
from sqlalchemy import text
from fapi.db.schemas import SetupInit, SyncFromWblRequest, ResumeCreate, APIKeyCreate
from fapi.utils.encryption_utils import encrypt_api_key, decrypt_api_key

def fetch_resume_raw(db, session_id: str):
    if not session_id or session_id == "null": return None
    try:
        marketing_id = int(session_id)
        result = db.execute(text("SELECT candidate_json FROM candidate_marketing WHERE id = :mid"), {"mid": marketing_id}).fetchone()
        if not result or not result[0]:
            return None
        raw = result[0]
        if isinstance(raw, str):
            try:
                import json
                parsed = json.loads(raw)
                if isinstance(parsed, str):
                    try:
                        parsed = json.loads(parsed)
                    except Exception:
                        pass
                return parsed
            except Exception:
                return None
        return raw
    except Exception:
        return None

def _resolve_session(db, data: SetupInit) -> int:
    if data.prep_token:
        result = db.execute(text("SELECT id FROM candidate_marketing WHERE id = :id"), {"id": int(data.prep_token)}).fetchone()
        if result: return result[0]
    if data.marketing_id:
        result = db.execute(text("SELECT id FROM candidate_marketing WHERE id = :id"), {"id": int(data.marketing_id)}).fetchone()
        if result: return result[0]
    candidate_id = None
    if data.candidate_id:
        result = db.execute(text("SELECT id FROM candidate WHERE id = :id"), {"id": int(data.candidate_id)}).fetchone()
        if result: candidate_id = result[0]
    if not candidate_id and data.candidate_email:
        result = db.execute(text("SELECT id FROM candidate WHERE email = :email LIMIT 1"), {"email": data.candidate_email}).fetchone()
        if result: candidate_id = result[0]
    if candidate_id:
        result = db.execute(
            text("SELECT id FROM candidate_marketing WHERE candidate_id = :cid ORDER BY id DESC LIMIT 1"),
            {"cid": candidate_id}
        ).fetchone()
        if result: return result[0]
        db.execute(text("INSERT INTO candidate_marketing (candidate_id, status) VALUES (:cid, 'active')"), {"cid": candidate_id})
        db.commit()
        result = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()
        return result[0]
    raise HTTPException(status_code=400, detail="Cannot resolve session from provided tokens")

def _upsert_eval_login(db, marketing_id: int):
    pass

def get_resume_summary_logic(session_id: str, db):
    try:
        if session_id == "null" or not session_id:
            raise HTTPException(status_code=404, detail="Invalid session ID")
        marketing_id = int(session_id)
        cand_row = db.execute(
            text("""
            SELECT c.full_name AS name, cm.email, cm.candidate_id, (cm.candidate_json IS NOT NULL) AS has_binary_resume
            FROM candidate_marketing cm
            JOIN candidate c ON c.id = cm.candidate_id
            WHERE cm.id = :mid
            """),
            {"mid": marketing_id}
        ).mappings().fetchone()
        if not cand_row:
            raise HTTPException(status_code=404, detail="Session/Candidate not found")
        candidate_name = cand_row["name"] if cand_row and cand_row.get("name") else ""
        candidate_email = cand_row["email"] if cand_row and cand_row.get("email") else ""
        cid = cand_row["candidate_id"] if cand_row else None
        has_binary_resume = bool(cand_row["has_binary_resume"]) if cand_row and "has_binary_resume" in cand_row else False
        raw_resume = fetch_resume_raw(db, session_id)
        has_resume = raw_resume is not None
        llm_keys = []
        has_api_key = False
        if cid:
            keys = db.execute(
                text("SELECT id, provider_name, model_name, voice_enabled, created_at FROM candidate_llm_api_keys WHERE candidate_id = :cid ORDER BY id ASC"),
                {"cid": cid}
            ).mappings().fetchall()
            llm_keys = [dict(k) for k in keys]
            has_api_key = len(llm_keys) > 0
        resume_json_out = raw_resume
        resume_filename = ""
        if isinstance(resume_json_out, dict):
            resume_filename = resume_json_out.get("_meta_filename", "")
        if has_resume and not candidate_name and isinstance(resume_json_out, dict):
            basics = resume_json_out.get("basics") or {}
            candidate_name = basics.get("name") or resume_json_out.get("name") or ""
        return {
            "resume_text": "Exists" if has_resume else None,
            "candidate_name": candidate_name,
            "candidate_email": candidate_email,
            "has_api_key": has_api_key,
            "resume_json": resume_json_out,
            "resume_filename": resume_filename,
            "llm_keys": llm_keys,
            "has_binary_resume": has_binary_resume,
        }
    except Exception as e:
        logger.error("ERROR in get_resume_summary: " + str(e))
        raise HTTPException(status_code=500, detail=str(e))

def init_session_logic(data: SetupInit, db):
    try:
        marketing_id = _resolve_session(db, data)
        _upsert_eval_login(db, marketing_id)
        db.commit()
        return {"session_id": str(marketing_id)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("ERROR in init_session: " + str(e))
        raise HTTPException(status_code=500, detail=str(e))

def init_and_summary_logic(data: SetupInit, db):
    try:
        marketing_id = _resolve_session(db, data)
        _upsert_eval_login(db, marketing_id)
        db.commit()
        session_id = str(marketing_id)
        summary = get_resume_summary_logic(session_id, db)
        return {
            "session_id": session_id,
            "summary": summary
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("ERROR in init_and_summary: " + str(e))
        raise HTTPException(status_code=500, detail=str(e))

async def sync_from_wbl_logic(data: SyncFromWblRequest, db):
    session_id = data.prep_token
    resume = fetch_resume_raw(db, session_id)
    if not resume:
        raise HTTPException(status_code=400, detail="Setup not completed yet")
    needs_extraction = False
    name = "Candidate"
    email = ""
    try:
        candidate_id = int(session_id)
        result = db.query(AiPrepToolProjectContextORM.id).filter(AiPrepToolProjectContextORM.user_id == str(candidate_id)).first()
        needs_extraction = not result
        row = db.execute(
            text("SELECT full_name AS name, email FROM candidate c JOIN candidate_marketing cm ON c.id = cm.candidate_id WHERE cm.id = :mid"),
            {"mid": candidate_id}
        ).mappings().fetchone()
        if row:
            if row.get("name"):
                name = row["name"]
            email = row.get("email") or ""
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if needs_extraction:
        try:
            extract_latest_company_bg(session_id, resume, "dummy_key", "openai")
        except Exception as e:
            logger.error(f"Extraction failed during sync: {e}")
    return {"session_id": session_id, "candidate_name": name, "candidate_email": email}

def get_current_user_logic(user_email: str, db):
    try:
        candidate_id = _get_candidate_id(db, user_email)
        row = db.query(CandidateORM.full_name).filter(CandidateORM.id == candidate_id).first()
        name = row[0] if row and row[0] else "Candidate"
        return {
            "session_id": str(candidate_id),
            "candidate_name": name,
            "candidate_email": user_email
        }
    except Exception as e:
        logger.error(f"get_current_user error for {user_email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch candidate profile")

def get_setup_status_logic(user_email: str, db):
    try:
        candidate_id = _get_candidate_id(db, user_email)
        resume_exists = db.query(CandidateMarketingORM.id).filter(CandidateMarketingORM.candidate_id == candidate_id, CandidateMarketingORM.candidate_json.isnot(None)).first() is not None
        keys_exist = db.query(CandidateLlmApiKeyORM.id).filter(CandidateLlmApiKeyORM.candidate_id == candidate_id).first() is not None
        return {
            "resume_uploaded": resume_exists,
            "api_keys_configured": keys_exist,
            "setup_complete": resume_exists and keys_exist,
        }
    except Exception as e:
        logger.error(f"setup-status error for {user_email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch setup status")

async def upload_resume_file_logic(file, resume_json, user_email: str, db):
    import json
    try:
        candidate_id = _get_candidate_id(db, user_email)
        from datetime import datetime
        marketing = db.query(CandidateMarketingORM).filter(CandidateMarketingORM.candidate_id == candidate_id).order_by(CandidateMarketingORM.id.desc()).first()
        if not marketing:
            marketing = CandidateMarketingORM(candidate_id=candidate_id, status='active', start_date=datetime.utcnow().date())
            db.add(marketing)
            db.commit()
            db.refresh(marketing)
        marketing_id_row = [marketing.id]
        marketing_id = marketing_id_row[0]
        updated_resume = None
        file_name = file.filename if file else "resume.json"
        if file:
            content = await file.read()
            if file.filename.endswith(".json") or file.content_type == "application/json":
                updated_resume = json.loads(content.decode("utf-8"))
                save_resume_for_session(db, str(marketing_id), updated_resume)
            else:
                updated_resume = process_resume_parsing(content, file.filename, candidate_id, marketing_id, db)
                save_resume_for_session(db, str(marketing_id), updated_resume)
        elif resume_json:
            updated_resume = json.loads(resume_json)
            save_resume_for_session(db, str(marketing_id), updated_resume)
        else:
            raise HTTPException(status_code=400, detail="No file or resume_json provided")
        return {"resume_json": updated_resume, "file_name": file_name}
    except Exception as e:
        logger.error(f"upload_resume error for {user_email}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def get_resume_logic(user_email: str, db):
    try:
        candidate_id = _get_candidate_id(db, user_email)
        marketing = db.query(CandidateMarketingORM.id).filter(CandidateMarketingORM.candidate_id == candidate_id).order_by(CandidateMarketingORM.id.desc()).first()
        marketing_id_row = [marketing[0]] if marketing else None
        if not marketing_id_row:
            raise HTTPException(status_code=404, detail="Resume not found")
        raw = fetch_resume_raw(db, str(marketing_id_row[0]))
        if not raw:
            raise HTTPException(status_code=404, detail="Resume not found")
        return {"resume_json": raw}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_resume error for {user_email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch resume")

def update_resume_logic(body: ResumeCreate, user_email: str, db):
    try:
        candidate_id = _get_candidate_id(db, user_email)
        marketing = db.query(CandidateMarketingORM.id).filter(CandidateMarketingORM.candidate_id == candidate_id).order_by(CandidateMarketingORM.id.desc()).first()
        marketing_id_row = [marketing[0]] if marketing else None
        if not marketing_id_row:
            raise HTTPException(status_code=404, detail="Candidate marketing not found")
        save_resume_for_session(db, str(marketing_id_row[0]), body.resume_json)
        return {"resume_json": body.resume_json, "file_name": body.file_name}
    except Exception as e:
        logger.error(f"update_resume error for {user_email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update resume")

def add_api_key_logic(body: APIKeyCreate, user_email: str, db):
    provider = body.provider_name.lower()
    is_valid, supports_voice = _validate_api_key(provider, body.api_key)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid API Key")
    encrypted_key = encrypt_api_key(body.api_key)
    try:
        candidate_id = _get_candidate_id(db, user_email)
        dup = db.query(CandidateLlmApiKeyORM).filter(
            CandidateLlmApiKeyORM.candidate_id == candidate_id,
            CandidateLlmApiKeyORM.provider_name == body.provider_name,
            CandidateLlmApiKeyORM.model_name == (body.model_name or ""),
            CandidateLlmApiKeyORM.api_key == encrypted_key
        ).first()
        if dup:
            dup.voice_enabled = body.voice_enabled
            db.commit()
            db.refresh(dup)
            row = {"id": dup.id, "provider_name": dup.provider_name, "model_name": dup.model_name, "voice_enabled": dup.voice_enabled, "api_key": dup.api_key}
        else:
            new_key = CandidateLlmApiKeyORM(
                candidate_id=candidate_id, provider_name=body.provider_name,
                api_key=encrypted_key, model_name=body.model_name or "",
                voice_enabled=body.voice_enabled
            )
            db.add(new_key)
            db.commit()
            db.refresh(new_key)
            row = {"id": new_key.id, "provider_name": new_key.provider_name, "model_name": new_key.model_name, "voice_enabled": new_key.voice_enabled, "api_key": new_key.api_key}
        row_dict = dict(row)
        try:
            raw = decrypt_api_key(row_dict["api_key"])
            row_dict["masked_key"] = _mask_key(raw)
        except:
            row_dict["masked_key"] = "****"
        row_dict.pop("api_key", None)
        return row_dict
    except Exception as e:
        logger.error(f"add_api_key error for {user_email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save API key")

def list_api_keys_logic(user_email: str, db):
    try:
        candidate_id = _get_candidate_id(db, user_email)
        keys = db.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.candidate_id == candidate_id).all()
        rows = [{"id": k.id, "provider_name": k.provider_name, "model_name": k.model_name, "voice_enabled": k.voice_enabled, "api_key": k.api_key} for k in keys]
        result = []
        for r in rows:
            row_dict = dict(r)
            try:
                raw = decrypt_api_key(row_dict["api_key"])
                row_dict["masked_key"] = _mask_key(raw)
            except:
                row_dict["masked_key"] = "****"
            row_dict.pop("api_key", None)
            result.append(row_dict)
        return result
    except Exception as e:
        logger.error(f"list_api_keys error for {user_email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list API keys")

def delete_api_key_logic(key_id: int, user_email: str, db):
    try:
        candidate_id = _get_candidate_id(db, user_email)
        existing = db.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.id == key_id, CandidateLlmApiKeyORM.candidate_id == candidate_id).first()
        if not existing:
            raise HTTPException(status_code=404, detail="API key not found")
        db.delete(existing)
        db.commit()
        return {"message": "API key deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_api_key error for {user_email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete API key")

def extract_project_logic(user_email: str, db):
    try:
        candidate_id = _get_candidate_id(db, user_email)
        marketing = db.query(CandidateMarketingORM.id).filter(CandidateMarketingORM.candidate_id == candidate_id).order_by(CandidateMarketingORM.id.desc()).first()
        marketing_id_row = [marketing[0]] if marketing else None
        if not marketing_id_row:
            raise HTTPException(status_code=404, detail="Setup not completed yet")
        marketing_id = str(marketing_id_row[0])
        import json
        ctx = db.query(AiPrepToolProjectContextORM).filter(AiPrepToolProjectContextORM.user_id == str(marketing_id)).first()
        if ctx:
            res = {c.name: getattr(ctx, c.name) for c in ctx.__table__.columns}
            try: res["skills"] = json.loads(res.get("skills") or "[]")
            except: res["skills"] = []
            return res
        return {}
    except Exception as e:
        logger.error(f"extract-project error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def get_latest_project_logic(user_email: str, db):
    try:
        candidate_id = _get_candidate_id(db, user_email)
        marketing = db.query(CandidateMarketingORM.id).filter(CandidateMarketingORM.candidate_id == candidate_id).order_by(CandidateMarketingORM.id.desc()).first()
        marketing_id_row = [marketing[0]] if marketing else None
        if not marketing_id_row:
            return {}
        marketing_id = str(marketing_id_row[0])
        import json
        ctx = db.query(AiPrepToolProjectContextORM).filter(AiPrepToolProjectContextORM.user_id == str(marketing_id)).first()
        if ctx:
            res = {c.name: getattr(ctx, c.name) for c in ctx.__table__.columns}
            try: res["skills"] = json.loads(res.get("skills") or "[]")
            except: res["skills"] = []
            return res
        return {}
    except Exception as e:
        logger.error(f"latest-project error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
