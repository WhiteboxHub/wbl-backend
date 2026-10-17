"""
WBL Backend router for AI Prep Tool analytics.
Exposes candidate analytics to the Avatar Admin Dashboard.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.utils.auth_dependencies import staff_or_admin_required

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics/ai-prep", tags=["AI Prep Analytics"])


# ─── Helpers ───────────────────────────────────────────────────────────────




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


# ─── GET /api/analytics/ai-prep-report ────────────────────────────────────────

@router.get("/ai-prep-report")
def get_ai_prep_report(
    db: Session = Depends(get_db),
    current_user=Depends(staff_or_admin_required),
):
    _ = current_user
    try:
        sql = """
            SELECT 
                cm.id AS marketing_id,
                cand.id AS candidate_id,
                COALESCE(c.name, cand.full_name) AS name,
                COALESCE(c.email, cand.email) AS email,
                cm.email AS wbl_email,
                c.user_id,
                COALESCE(c.login_count, 0) AS login_count,
                c.created_at,
                c.last_login,
                c.extraction_status,
                (SELECT COUNT(1) FROM aiprep_tool_resumes r WHERE r.user_id = c.user_id) AS has_resume,
                (SELECT r.resume_json FROM aiprep_tool_resumes r WHERE r.user_id = c.user_id ORDER BY id DESC LIMIT 1) AS resume_json,
                (SELECT COUNT(1) FROM aiprep_tool_project_context p WHERE p.user_id = c.user_id) AS has_project,
                (SELECT COUNT(1) FROM aiprep_tool_evaluations e WHERE e.user_id = c.user_id AND e.type = 'intro') AS intro_attempts,
                (SELECT MAX(score) FROM aiprep_tool_evaluations e WHERE e.user_id = c.user_id AND e.type = 'intro') AS best_intro_score,
                (SELECT e.score FROM aiprep_tool_evaluations e WHERE e.user_id = c.user_id AND e.type = 'intro' ORDER BY e.created_at DESC LIMIT 1) AS latest_intro_score,
                (SELECT e.video_url FROM aiprep_tool_evaluations e WHERE e.user_id = c.user_id AND e.type = 'intro' AND e.video_url IS NOT NULL ORDER BY e.created_at DESC LIMIT 1) AS latest_video_url,
                (SELECT MAX(created_at) FROM aiprep_tool_evaluations e WHERE e.user_id = c.user_id AND e.type = 'intro') AS last_intro_at,
                (SELECT e.feedback FROM aiprep_tool_evaluations e WHERE e.user_id = c.user_id AND e.type = 'intro' ORDER BY e.created_at DESC LIMIT 1) AS latest_feedback,
                (SELECT e.raw_response FROM aiprep_tool_evaluations e WHERE e.user_id = c.user_id AND e.type = 'intro' ORDER BY e.created_at DESC LIMIT 1) AS latest_raw_response
            FROM candidate_marketing cm
            JOIN candidate cand ON cand.id = cm.candidate_id
            LEFT JOIN aiprep_tool_candidates c ON (c.wbl_email = cm.email OR c.wbl_email = cand.email OR c.email = cand.email OR c.name = cm.email)
            WHERE cm.status = 'active'
            ORDER BY c.last_login DESC
        """
        rows = db.execute(text(sql)).mappings().all()

        users = []
        total_intro_scores = []
        users_with_intro = 0
        intro_passed_count = 0
        active_last_7_days = 0
        seven_days_ago = datetime.utcnow() - timedelta(days=7)

        for row in rows:
            user_id = str(row["user_id"] or row["marketing_id"])
            best_intro = row.get("best_intro_score")
            latest_intro = row.get("latest_intro_score")
            intro_passed = (best_intro or 0) >= 75
            intro_attempts = row.get("intro_attempts") or 0

            if intro_attempts > 0:
                users_with_intro += 1
            if intro_passed:
                intro_passed_count += 1
            if best_intro is not None:
                total_intro_scores.append(best_intro)

            last_login_dt = row.get("last_login")
            if last_login_dt and last_login_dt >= seven_days_ago:
                active_last_7_days += 1

            def dtstr(v):
                return v.isoformat() if v else None

            resume_name, resume_email = _extract_from_resume(row.get("resume_json"))
            disp_name = row.get("name")
            if (not disp_name or disp_name == "Candidate" or disp_name == "—") and resume_name:
                disp_name = resume_name
            if not disp_name:
                disp_name = "—"

            disp_email = row.get("wbl_email") or row.get("email") or resume_email or "—"

            strengths = []
            weaknesses = []
            raw = row.get("latest_raw_response")
            if raw:
                try:
                    raw_dict = json.loads(raw) if isinstance(raw, str) else raw
                    if isinstance(raw_dict, dict):
                        strengths = raw_dict.get("feedback") or []
                        weaknesses = raw_dict.get("missing_points") or []
                except Exception:
                    pass

            u_entry = {
                "session_id": user_id,
                "wbl_email": disp_email,
                "name": disp_name,
                "login_count": row.get("login_count") or 0,
                "last_active": dtstr(row.get("last_login")),
                "extraction_status": row.get("extraction_status") or "completed",
                "intro_attempts": intro_attempts,
                "intro_best_score": best_intro,
                "intro_latest_score": latest_intro,
                "intro_passed": intro_passed,
                "last_intro_date": dtstr(row.get("last_intro_at")),
                "video_url": row.get("latest_video_url"),
                "scores": {},
                "overall_score": best_intro,
                "strengths": strengths if isinstance(strengths, list) else [],
                "weaknesses": weaknesses if isinstance(weaknesses, list) else [],
                "ai_suggestions": [],
                "improvement_areas": [],
                "created_at": dtstr(row.get("created_at")),
            }
            users.append(u_entry)

        avg_intro = round(sum(total_intro_scores) / len(total_intro_scores), 1) if total_intro_scores else 0
        pass_rate = round(intro_passed_count / users_with_intro * 100, 1) if users_with_intro else 0

        return {
            "total_users": len(users),
            "users_with_intro": users_with_intro,
            "active_last_7_days": active_last_7_days,
            "avg_intro_score": avg_intro,
            "pass_rate_pct": pass_rate,
            "users": users,
        }
    except OperationalError as e:
        # aiprep_tool_* tables don't exist in this environment (e.g. test DB or not yet set up)
        logger.warning(f"aiprep_tool tables unavailable, returning empty report: {e}")
        return {
            "total_users": 0, "users_with_intro": 0, "active_last_7_days": 0,
            "avg_intro_score": 0, "pass_rate_pct": 0, "users": [],
        }
    except Exception as e:
        logger.error(f"Error in ai-prep-report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

