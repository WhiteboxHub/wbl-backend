"""
WBL Backend router for AI Prep Tool analytics.
Exposes candidate analytics to the Avatar Admin Dashboard.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.utils.auth_dependencies import staff_or_admin_required

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics/ai-prep", tags=["AI Prep Analytics"])


# ─── Helpers ───────────────────────────────────────────────────────────────

def _prep_status(has_resume, has_project, intro_passed, interview_completed):
    steps = sum([bool(has_resume), bool(has_project), bool(intro_passed), bool(interview_completed)])
    pct = int(steps / 4 * 100)
    if pct == 100:
        label = "Complete"
    elif pct >= 75:
        label = "Almost Ready"
    elif pct >= 50:
        label = "In Progress"
    elif pct >= 25:
        label = "Just Started"
    else:
        label = "Not Started"
    return pct, label


def _extract_from_resume(resume_json):
    if not resume_json:
        return None, None
    try:
        if isinstance(resume_json, str):
            data = json.loads(resume_json)
        else:
            data = resume_json
    except Exception:
        return None, None

    if not isinstance(data, dict):
        return None, None

    name = None
    email = None

    # Try basics (standard JSON resume)
    basics = data.get("basics") or {}
    if isinstance(basics, dict):
        name = basics.get("name")
        email = basics.get("email")

    # Try personal (WBL resume parser format)
    personal = data.get("personal") or {}
    if isinstance(personal, dict):
        fname = personal.get("first_name") or ""
        lname = personal.get("last_name") or ""
        extracted_name = f"{fname.strip()} {lname.strip()}".strip()
        if extracted_name:
            name = extracted_name
        if personal.get("email"):
            email = personal.get("email")

    # Fallbacks in root
    if not name and data.get("name"):
        name = data.get("name")
    if not email and data.get("email"):
        email = data.get("email")

    return name, email


# ─── GET /api/analytics/ai-prep/summary ───────────────────────────────────────

@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    current_user=Depends(staff_or_admin_required),
):
    _ = current_user
    try:
        # Total candidates (active in marketing)
        total_res = db.execute(text("SELECT COUNT(*) AS total FROM candidate_marketing WHERE status = 'active'")).mappings().first()
        total_candidates = total_res["total"] if total_res else 0

        # Active this week (logged in to AI Prep tool)
        active_res = db.execute(text("""
            SELECT COUNT(DISTINCT c.user_id) AS active
            FROM aiprep_tool_candidates c
            JOIN candidate_marketing cm ON c.wbl_email = cm.email OR c.email = cm.email
            WHERE cm.status = 'active' AND c.last_login >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        """)).mappings().first()
        active_week = active_res["active"] if active_res else 0

        # Intro pass rate
        intro_res = db.execute(text("""
            SELECT COUNT(DISTINCT c.user_id) AS passed_users
            FROM aiprep_tool_evaluations e
            JOIN aiprep_tool_candidates c ON e.user_id = c.user_id
            JOIN candidate_marketing cm ON c.wbl_email = cm.email OR c.email = cm.email
            WHERE cm.status = 'active' AND e.type = 'intro' AND e.passed = 1
        """)).mappings().first()
        intro_passed_users = intro_res["passed_users"] if intro_res else 0
        intro_pass_rate = round(intro_passed_users / total_candidates * 100, 1) if total_candidates else 0

        # Interview completion rate
        interview_res = db.execute(text("""
            SELECT COUNT(DISTINCT c.user_id) AS completed
            FROM aiprep_tool_evaluations e
            JOIN aiprep_tool_candidates c ON e.user_id = c.user_id
            JOIN candidate_marketing cm ON c.wbl_email = cm.email OR c.email = cm.email
            WHERE cm.status = 'active' AND e.type = 'interview_complete'
        """)).mappings().first()
        interview_completed = interview_res["completed"] if interview_res else 0
        interview_completion_rate = round(interview_completed / total_candidates * 100, 1) if total_candidates else 0

        # CoderPad adoption (candidates with execution logs)
        cp_res = db.execute(text("""
            SELECT COUNT(DISTINCT cel.authuser_id) AS cp_users 
            FROM code_execution_log cel
            JOIN authuser au ON cel.authuser_id = au.id
            JOIN aiprep_tool_candidates c ON au.uname = c.wbl_email OR au.uname = c.email
            WHERE cel.status = 'success' AND cel.code_snippet_id IS NOT NULL
        """)).mappings().first()
        cp_users = cp_res["cp_users"] if cp_res else 0
        cp_adoption_rate = round(cp_users / total_candidates * 100, 1) if total_candidates else 0

        # Case studies generated
        cs_res = db.execute(text("SELECT COUNT(*) AS cs_total FROM aiprep_tool_case_studies")).mappings().first()
        case_studies = cs_res["cs_total"] if cs_res else 0

        return {
            "total_candidates": total_candidates,
            "active_this_week": active_week,
            "intro_pass_rate": intro_pass_rate,
            "interview_completion_rate": interview_completion_rate,
            "coderpad_adoption_rate": cp_adoption_rate,
            "total_case_studies": case_studies,
            "intro_passed_count": intro_passed_users,
            "interview_completed_count": interview_completed,
            "coderpad_active_count": cp_users,
        }
    except Exception as e:
        logger.error(f"Error in summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── GET /api/analytics/ai-prep/candidates ────────────────────────────────────

@router.get("/candidates")
def get_candidates(
    db: Session = Depends(get_db),
    current_user=Depends(staff_or_admin_required),
    search: Optional[str] = Query(None),
    filter_intro_passed: Optional[bool] = Query(None),
    filter_interview_done: Optional[bool] = Query(None),
    filter_has_coderpad: Optional[bool] = Query(None),
    filter_active_week: Optional[bool] = Query(None),
):
    _ = current_user
    try:
        sql = """
            SELECT
                cm.id AS id,
                COALESCE(c.user_id, CONCAT('marketing_', cm.id)) AS user_id,
                cand.full_name AS name,
                cand.email AS email,
                COALESCE(c.wbl_email, cm.email, cand.email) AS wbl_email,
                COALESCE(c.login_count, 0) AS login_count,
                c.created_at,
                c.last_login,
                COALESCE(c.extraction_status, 'pending') AS extraction_status,

                -- Resume
                (SELECT COUNT(*) FROM aiprep_tool_resumes r WHERE r.user_id = c.user_id OR r.user_id = cand.id) AS has_resume,
                (SELECT r.resume_json FROM aiprep_tool_resumes r WHERE r.user_id = c.user_id OR r.user_id = cand.id) AS resume_json,

                -- Project
                (SELECT COUNT(*) FROM aiprep_tool_project_context p WHERE p.user_id = c.user_id OR p.user_id = cand.id) AS has_project,

                -- Intro attempts
                (SELECT COUNT(*) FROM aiprep_tool_evaluations e
                 WHERE (e.user_id = c.user_id OR e.user_id = cand.id) AND e.type = 'intro') AS intro_attempts,

                -- Best intro score
                (SELECT MAX(e.score) FROM aiprep_tool_evaluations e
                 WHERE (e.user_id = c.user_id OR e.user_id = cand.id) AND e.type = 'intro') AS best_intro_score,

                -- Intro passed (any attempt)
                (SELECT MAX(CASE WHEN e.passed THEN 1 ELSE 0 END)
                 FROM aiprep_tool_evaluations e
                 WHERE (e.user_id = c.user_id OR e.user_id = cand.id) AND e.type = 'intro') AS intro_passed,

                -- Latest intro score
                (SELECT e.score FROM aiprep_tool_evaluations e
                 WHERE (e.user_id = c.user_id OR e.user_id = cand.id) AND e.type = 'intro'
                 ORDER BY e.created_at DESC LIMIT 1) AS latest_intro_score,

                -- Latest video URL
                (SELECT e.video_url FROM aiprep_tool_evaluations e
                 WHERE (e.user_id = c.user_id OR e.user_id = cand.id) AND e.type = 'intro' AND e.video_url IS NOT NULL
                 ORDER BY e.created_at DESC LIMIT 1) AS latest_video_url,

                -- Interview questions answered
                (SELECT COUNT(*) FROM aiprep_tool_evaluations e
                 WHERE (e.user_id = c.user_id OR e.user_id = cand.id) AND e.type = 'interview_answer') AS questions_answered,

                -- Avg interview score (stored as 0-10, * 10 to make /100)
                (SELECT ROUND(AVG(e.score) * 10, 1) FROM aiprep_tool_evaluations e
                 WHERE (e.user_id = c.user_id OR e.user_id = cand.id) AND e.type = 'interview_answer') AS avg_interview_score,

                -- Total interview attempts (sessions)
                (SELECT COUNT(*) FROM aiprep_tool_evaluations e
                 WHERE (e.user_id = c.user_id OR e.user_id = cand.id) AND e.type = 'interview_complete') AS interview_sessions,

                -- Interview completed
                (SELECT MAX(CASE WHEN e.type = 'interview_complete' THEN 1 ELSE 0 END)
                 FROM aiprep_tool_evaluations e
                 WHERE e.user_id = c.user_id OR e.user_id = cand.id) AS interview_completed,

                -- Case studies
                (SELECT COUNT(*) FROM aiprep_tool_case_studies cs
                 WHERE cs.user_id = c.user_id OR cs.user_id = cand.id) AS case_studies_generated,

                -- Real-time CoderPad stats from WBL tables
                (SELECT COUNT(DISTINCT cel.code_snippet_id) 
                 FROM code_execution_log cel 
                 WHERE cel.authuser_id = (SELECT id FROM authuser au WHERE au.uname = cm.email OR au.uname = cand.email LIMIT 1) 
                   AND cel.status = 'success' AND cel.code_snippet_id IS NOT NULL) AS questions_solved,

                (SELECT COUNT(cel.id) 
                 FROM code_execution_log cel 
                 WHERE cel.authuser_id = (SELECT id FROM authuser au WHERE au.uname = cm.email OR au.uname = cand.email LIMIT 1)) AS cp_total_submissions,

                (SELECT ROUND(COALESCE(SUM(CASE WHEN cel.status = 'success' THEN 1 ELSE 0 END) / NULLIF(COUNT(cel.id), 0) * 100, 0), 2)
                 FROM code_execution_log cel 
                 WHERE cel.authuser_id = (SELECT id FROM authuser au WHERE au.uname = cm.email OR au.uname = cand.email LIMIT 1)) AS cp_pass_rate,

                (SELECT COUNT(cel.id) 
                 FROM code_execution_log cel 
                 WHERE cel.authuser_id = (SELECT id FROM authuser au WHERE au.uname = cm.email OR au.uname = cand.email LIMIT 1)
                   AND cel.status = 'success') AS coderpad_passed,

                (SELECT COUNT(cel.id) 
                 FROM code_execution_log cel 
                 WHERE cel.authuser_id = (SELECT id FROM authuser au WHERE au.uname = cm.email OR au.uname = cand.email LIMIT 1)
                   AND cel.status = 'error') AS coderpad_failed,

                (SELECT COALESCE(CONCAT('[', GROUP_CONCAT(DISTINCT CONCAT('"', cel.language, '"')), ']'), '[]')
                 FROM code_execution_log cel 
                 WHERE cel.authuser_id = (SELECT id FROM authuser au WHERE au.uname = cm.email OR au.uname = cand.email LIMIT 1)) AS cp_languages,

                (SELECT MAX(cel.created_at) 
                 FROM code_execution_log cel 
                 WHERE cel.authuser_id = (SELECT id FROM authuser au WHERE au.uname = cm.email OR au.uname = cand.email LIMIT 1)) AS cp_last_synced

            FROM candidate_marketing cm
            JOIN candidate cand ON cand.id = cm.candidate_id
            LEFT JOIN aiprep_tool_candidates c ON c.wbl_email = cm.email OR c.email = cand.email OR c.wbl_email = cand.email
            WHERE cm.status = 'active'
            ORDER BY c.last_login DESC
        """
        rows = db.execute(text(sql)).mappings().all()

        # Parse JSON fields + compute derived fields
        results = []
        for row in rows:
            # Parse languages JSON
            langs = []
            if row.get("cp_languages"):
                try:
                    langs = json.loads(row["cp_languages"]) if isinstance(row["cp_languages"], str) else row["cp_languages"]
                except Exception:
                    langs = []

            pct, label = _prep_status(
                row.get("has_resume"),
                row.get("has_project"),
                row.get("intro_passed"),
                row.get("interview_completed"),
            )

            # Serialize datetimes
            def dtstr(v):
                return v.isoformat() if v else None

            # Attempt to extract candidate name and email from resume_json if missing/generic
            resume_name, resume_email = _extract_from_resume(row.get("resume_json"))

            disp_name = row.get("name")
            if (not disp_name or disp_name == "Candidate" or disp_name == "—") and resume_name:
                disp_name = resume_name
            if not disp_name:
                disp_name = "—"

            disp_email = row.get("email")
            if (not disp_email or disp_email == "—") and resume_email:
                disp_email = resume_email
            if not disp_email or disp_email == "—":
                disp_email = row.get("wbl_email") or "—"

            entry = {
                "id": row["id"],
                "user_id": row["user_id"],
                "name": disp_name,
                "email": disp_email,
                "wbl_email": row.get("wbl_email") or "—",
                "login_count": row.get("login_count") or 0,
                "created_at": dtstr(row.get("created_at")),
                "last_login": dtstr(row.get("last_login")),
                "extraction_status": row.get("extraction_status") or "pending",
                # Resume / Project
                "has_resume": bool(row.get("has_resume")),
                "has_project": bool(row.get("has_project")),
                # Intro
                "intro_attempts": row.get("intro_attempts") or 0,
                "best_intro_score": row.get("best_intro_score") or 0,
                "latest_intro_score": row.get("latest_intro_score") or 0,
                "intro_passed": bool(row.get("intro_passed")),
                "latest_video_url": row.get("latest_video_url"),
                # Interview
                "questions_answered": row.get("questions_answered") or 0,
                "avg_interview_score": row.get("avg_interview_score") or 0,
                "interview_sessions": row.get("interview_sessions") or 0,
                "interview_completed": bool(row.get("interview_completed")),
                # Case studies
                "case_studies_generated": row.get("case_studies_generated") or 0,
                # CoderPad
                "coderpad_questions_solved": row.get("questions_solved") or 0,
                "coderpad_total_submissions": row.get("cp_total_submissions") or 0,
                "coderpad_pass_rate": float(row.get("cp_pass_rate") or 0),
                "coderpad_passed": int(row.get("coderpad_passed") or 0),
                "coderpad_failed": int(row.get("coderpad_failed") or 0),
                "coderpad_languages": langs,
                "coderpad_last_synced": dtstr(row.get("cp_last_synced")),
                # Overall
                "prep_completion_pct": pct,
                "prep_status_label": label,
            }
            results.append(entry)

        # ── Filters ──────────────────────────────────────────────────────────
        if search:
            q = search.lower()
            results = [r for r in results if
                q in (r["name"] or "").lower() or
                q in (r["email"] or "").lower() or
                q in (r["wbl_email"] or "").lower()]

        if filter_intro_passed is True:
            results = [r for r in results if r["intro_passed"]]
        elif filter_intro_passed is False:
            results = [r for r in results if not r["intro_passed"]]

        if filter_interview_done is True:
            results = [r for r in results if r["interview_completed"]]
        elif filter_interview_done is False:
            results = [r for r in results if not r["interview_completed"]]

        if filter_has_coderpad is True:
            results = [r for r in results if r["coderpad_questions_solved"] > 0]
        elif filter_has_coderpad is False:
            results = [r for r in results if r["coderpad_questions_solved"] == 0]

        if filter_active_week is True:
            week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
            results = [r for r in results if r["last_login"] and r["last_login"] >= week_ago]

        return {"candidates": results, "total": len(results)}

    except Exception as e:
        logger.error(f"Error in candidates list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── GET /api/analytics/ai-prep/candidates/{user_id} ──────────────────────────

@router.get("/candidates/{user_id}")
def get_candidate_detail(
    user_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(staff_or_admin_required),
):
    _ = current_user
    try:
        # Handle fallback marketing user_id
        if user_id.startswith("marketing_"):
            marketing_id = int(user_id.replace("marketing_", ""))
            candidate_sql = """
                SELECT 
                    cm.id AS marketing_id,
                    cand.full_name AS joined_name,
                    cand.email AS joined_email,
                    cm.email AS wbl_email
                FROM candidate_marketing cm
                JOIN candidate cand ON cand.id = cm.candidate_id
                WHERE cm.id = :marketing_id
            """
            candidate = db.execute(text(candidate_sql), {"marketing_id": marketing_id}).mappings().first()
            if not candidate:
                raise HTTPException(status_code=404, detail="Candidate not found")
            
            # Since they haven't logged in, they have no AI Prep history. Get CoderPad stats directly:
            wbl_email = candidate.get("wbl_email")
            email = candidate.get("joined_email")
            cp_data = None
            if wbl_email or email:
                cp_sql = """
                    SELECT 
                        COUNT(DISTINCT CASE WHEN cel.status = 'success' THEN cel.code_snippet_id END) AS questions_solved,
                        COUNT(cel.id) AS total_submissions,
                        ROUND(COALESCE(SUM(CASE WHEN cel.status = 'success' THEN 1 ELSE 0 END) / NULLIF(COUNT(cel.id), 0) * 100, 0), 2) AS pass_rate,
                        COALESCE(CONCAT('[', GROUP_CONCAT(DISTINCT CONCAT('"', cel.language, '"')), ']'), '[]') AS languages_used,
                        MAX(cel.created_at) AS last_synced
                    FROM code_execution_log cel
                    WHERE cel.authuser_id = (SELECT id FROM authuser au WHERE au.uname = :wbl_email OR au.uname = :email LIMIT 1)
                """
                cp_data = db.execute(text(cp_sql), {"wbl_email": wbl_email, "email": email}).mappings().first()
            
            def dtstr(v):
                return v.isoformat() if v else None
            
            cp_out = {}
            if cp_data:
                try:
                    langs = json.loads(cp_data.get("languages_used")) if isinstance(cp_data.get("languages_used"), str) else cp_data.get("languages_used")
                except Exception:
                    langs = []
                cp_out = {
                    "questions_solved": cp_data.get("questions_solved") or 0,
                    "total_submissions": cp_data.get("total_submissions") or 0,
                    "pass_rate": float(cp_data.get("pass_rate") or 0),
                    "languages_used": langs,
                    "last_synced": dtstr(cp_data.get("last_synced")),
                }

            return {
                "candidate": {
                    "user_id": user_id,
                    "name": candidate.get("joined_name"),
                    "email": candidate.get("joined_email"),
                    "wbl_email": candidate.get("wbl_email") or "—",
                    "login_count": 0,
                    "created_at": None,
                    "last_login": None,
                },
                "intro_history": [],
                "interview_history": [],
                "case_studies": [],
                "coderpad": cp_out,
            }

        # Otherwise, candidate exists in aiprep_tool_candidates
        candidate_sql = """
            SELECT 
                c.*,
                cand.full_name AS joined_name,
                cand.email AS joined_email,
                cand.id AS cand_id
            FROM aiprep_tool_candidates c
            LEFT JOIN candidate cand ON cand.email = c.wbl_email OR cand.email = c.email
            WHERE c.user_id = :user_id
        """
        candidate = db.execute(text(candidate_sql), {"user_id": user_id}).mappings().first()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        cand_id = str(candidate.get("cand_id")) if candidate.get("cand_id") is not None else None

        # Get resume JSON if any to extract details
        resume_res = db.execute(text("""
            SELECT resume_json FROM aiprep_tool_resumes 
            WHERE user_id = :user_id OR (:cand_id IS NOT NULL AND user_id = :cand_id)
        """), {"user_id": user_id, "cand_id": cand_id}).mappings().first()
        resume_json = resume_res["resume_json"] if resume_res else None

        # All intro evaluations (timeline)
        intro_history = db.execute(text("""
            SELECT score, passed, feedback, created_at
            FROM aiprep_tool_evaluations
            WHERE (user_id = :user_id OR (:cand_id IS NOT NULL AND user_id = :cand_id)) AND type = 'intro'
            ORDER BY created_at ASC
        """), {"user_id": user_id, "cand_id": cand_id}).mappings().all()

        # All interview answer evaluations
        interview_history = db.execute(text("""
            SELECT score, feedback, raw_response, created_at
            FROM aiprep_tool_evaluations
            WHERE (user_id = :user_id OR (:cand_id IS NOT NULL AND user_id = :cand_id)) AND type = 'interview_answer'
            ORDER BY created_at ASC
        """), {"user_id": user_id, "cand_id": cand_id}).mappings().all()

        # Case studies
        case_studies = db.execute(text("""
            SELECT topic, created_at
            FROM aiprep_tool_case_studies
            WHERE user_id = :user_id OR (:cand_id IS NOT NULL AND user_id = :cand_id)
            ORDER BY created_at DESC
        """), {"user_id": user_id, "cand_id": cand_id}).mappings().all()

        # CoderPad stats directly from live WBL execution logs
        wbl_email = candidate.get("wbl_email")
        email = candidate.get("email") or candidate.get("joined_email")
        cp_data = None
        if wbl_email or email:
            cp_sql = """
                SELECT 
                    COUNT(DISTINCT CASE WHEN cel.status = 'success' THEN cel.code_snippet_id END) AS questions_solved,
                    COUNT(cel.id) AS total_submissions,
                    ROUND(COALESCE(SUM(CASE WHEN cel.status = 'success' THEN 1 ELSE 0 END) / NULLIF(COUNT(cel.id), 0) * 100, 0), 2) AS pass_rate,
                    COALESCE(CONCAT('[', GROUP_CONCAT(DISTINCT CONCAT('"', cel.language, '"')), ']'), '[]') AS languages_used,
                    MAX(cel.created_at) AS last_synced
                FROM code_execution_log cel
                WHERE cel.authuser_id = (SELECT id FROM authuser au WHERE au.uname = :wbl_email OR au.uname = :email LIMIT 1)
            """
            cp_data = db.execute(text(cp_sql), {"wbl_email": wbl_email, "email": email}).mappings().first()

        def dtstr(v):
            return v.isoformat() if v else None

        def parse_json_field(v):
            if not v:
                return {}
            if isinstance(v, (dict, list)):
                return v
            try:
                return json.loads(v)
            except Exception:
                return {}

        # Parse intro history
        intro_list = []
        for e in intro_history:
            intro_list.append({
                "score": e.get("score") or 0,
                "passed": bool(e.get("passed")),
                "feedback": parse_json_field(e.get("feedback")),
                "created_at": dtstr(e.get("created_at")),
            })

        # Parse interview history
        interview_list = []
        for e in interview_history:
            interview_list.append({
                "score": e.get("score") or 0,
                "feedback": parse_json_field(e.get("feedback")),
                "created_at": dtstr(e.get("created_at")),
            })

        cp_out = {}
        if cp_data:
            cp_out = {
                "questions_solved": cp_data.get("questions_solved") or 0,
                "total_submissions": cp_data.get("total_submissions") or 0,
                "pass_rate": float(cp_data.get("pass_rate") or 0),
                "languages_used": parse_json_field(cp_data.get("languages_used")),
                "last_synced": dtstr(cp_data.get("last_synced")),
            }

        resume_name, resume_email = _extract_from_resume(resume_json)
        disp_name = candidate.get("joined_name")
        if (not disp_name or disp_name == "Candidate" or disp_name == "—") and resume_name:
            disp_name = resume_name
        if not disp_name:
            disp_name = "—"

        disp_email = candidate.get("joined_email")
        if (not disp_email or disp_email == "—") and resume_email:
            disp_email = resume_email
        if not disp_email or disp_email == "—":
            disp_email = candidate.get("wbl_email") or "—"

        return {
            "candidate": {
                "user_id": candidate.get("user_id"),
                "name": disp_name,
                "email": disp_email,
                "wbl_email": candidate.get("wbl_email") or "—",
                "login_count": candidate.get("login_count") or 0,
                "created_at": dtstr(candidate.get("created_at")),
                "last_login": dtstr(candidate.get("last_login")),
            },
            "intro_history": intro_list,
            "interview_history": interview_list,
            "case_studies": [{"topic": cs.get("topic"), "created_at": dtstr(cs.get("created_at"))} for cs in case_studies],
            "coderpad": cp_out,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in candidate details: {e}")
        raise HTTPException(status_code=500, detail=str(e))
