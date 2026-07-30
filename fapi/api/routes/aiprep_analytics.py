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
from sqlalchemy.exc import OperationalError
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


# ─── GET /api/analytics/ai-prep/summary ───────────────────────────────────────

@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    current_user=Depends(staff_or_admin_required),
):
    _ = current_user
    try:
        total_candidates = db.execute(text("SELECT COUNT(1) FROM candidate_marketing WHERE status = 'active'")).scalar() or 0
        total_ai_prep = db.execute(text("SELECT COUNT(DISTINCT user_id) FROM aiprep_tool_candidates")).scalar() or 0
        week_ago = datetime.utcnow() - timedelta(days=7)
        active_week = db.execute(text("SELECT COUNT(DISTINCT user_id) FROM aiprep_tool_candidates WHERE last_login >= :week_ago"), {"week_ago": week_ago}).scalar() or 0
        intro_passed_count = db.execute(text("SELECT COUNT(DISTINCT user_id) FROM aiprep_tool_evaluations WHERE type = 'intro' AND score >= 75")).scalar() or 0
        intro_pass_rate = round(intro_passed_count / total_ai_prep * 100, 1) if total_ai_prep else 0.0
        case_studies = db.execute(text("SELECT COUNT(1) FROM aiprep_tool_case_studies")).scalar() or 0

        return {
            "total_marketing_candidates": total_candidates,
            "total_ai_prep_registered": total_ai_prep,
            "active_this_week": active_week,
            "intro_pass_rate": intro_pass_rate,
            "total_case_studies": case_studies,
            "intro_passed_count": intro_passed_count,
        }
    except OperationalError as e:
        logger.warning(f"aiprep_tool tables unavailable, returning empty summary: {e}")
        return {
            "total_marketing_candidates": 0, "total_ai_prep_registered": 0,
            "active_this_week": 0, "intro_pass_rate": 0.0,
            "total_case_studies": 0, "intro_passed_count": 0,
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
    filter_active_week: Optional[bool] = Query(None),
):
    _ = current_user
    if search and not isinstance(search, str):
        search = None
    if filter_intro_passed and not isinstance(filter_intro_passed, bool):
        filter_intro_passed = None
    if filter_active_week and not isinstance(filter_active_week, bool):
        filter_active_week = None

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
                (SELECT COUNT(1) FROM aiprep_tool_resumes r WHERE r.user_id = c.user_id) AS has_resume,
                (SELECT r.resume_json FROM aiprep_tool_resumes r WHERE r.user_id = c.user_id ORDER BY id DESC LIMIT 1) AS resume_json,
                (SELECT COUNT(1) FROM aiprep_tool_project_context p WHERE p.user_id = c.user_id) AS has_project,
                (SELECT MAX(score) FROM aiprep_tool_evaluations e WHERE e.user_id = c.user_id AND e.type = 'intro') AS best_intro_score,
                (SELECT e.score FROM aiprep_tool_evaluations e WHERE e.user_id = c.user_id AND e.type = 'intro' ORDER BY e.created_at DESC LIMIT 1) AS latest_intro_score,
                (SELECT e.video_url FROM aiprep_tool_evaluations e WHERE e.user_id = c.user_id AND e.type = 'intro' AND e.video_url IS NOT NULL ORDER BY e.created_at DESC LIMIT 1) AS latest_video_url,
                (SELECT MAX(created_at) FROM aiprep_tool_evaluations e WHERE e.user_id = c.user_id AND e.type = 'intro') AS last_intro_at,
                (SELECT COUNT(1) FROM aiprep_tool_evaluations e WHERE e.user_id = c.user_id AND e.type = 'interview_answer') AS interview_answers_count,
                (SELECT COUNT(1) FROM aiprep_tool_case_studies cs WHERE cs.candidate_id = cm.id OR cs.candidate_id = cand.id) AS case_studies_generated
            FROM candidate_marketing cm
            JOIN candidate cand ON cand.id = cm.candidate_id
            LEFT JOIN aiprep_tool_candidates c ON (c.wbl_email = cm.email OR c.wbl_email = cand.email OR c.email = cand.email OR c.name = cm.email)
            WHERE cm.status = 'active'
            ORDER BY c.last_login DESC
        """
        rows = db.execute(text(sql)).mappings().all()

        results = []
        for row in rows:
            best_intro = row.get("best_intro_score") or 0
            latest_intro = row.get("latest_intro_score") or 0
            intro_passed = best_intro >= 75
            interview_completed = (row.get("interview_answers_count") or 0) > 0

            pct, label = _prep_status(
                row.get("has_resume"),
                row.get("has_project"),
                intro_passed,
                interview_completed,
            )

            def dtstr(v):
                return v.isoformat() if v else None

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
                "id": row["marketing_id"],
                "user_id": str(row["user_id"] or row["marketing_id"]),
                "candidate_id": row["candidate_id"],
                "name": disp_name,
                "email": disp_email,
                "wbl_email": row.get("wbl_email") or "—",
                "login_count": row.get("login_count") or 0,
                "created_at": dtstr(row.get("created_at")),
                "last_login": dtstr(row.get("last_login")),
                # Resume / Project
                "has_resume": bool(row.get("has_resume")),
                "has_project": bool(row.get("has_project")),
                # Intro / Interview
                "best_intro_score": best_intro,
                "latest_intro_score": latest_intro,
                "intro_score": best_intro,
                "intro_status": "passed" if intro_passed else ("failed" if best_intro > 0 else "not_started"),
                "intro_passed": intro_passed,
                "latest_video_url": row.get("latest_video_url"),
                "last_intro_at": dtstr(row.get("last_intro_at")),
                "interview_answers_count": row.get("interview_answers_count") or 0,
                "interview_completed": interview_completed,
                # Case studies
                "case_studies_generated": row.get("case_studies_generated") or 0,
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

        if filter_active_week is True:
            week_ago_str = (datetime.utcnow() - timedelta(days=7)).isoformat()
            results = [r for r in results if r["last_login"] and r["last_login"] >= week_ago_str]

        return {"candidates": results, "total": len(results)}

    except OperationalError as e:
        logger.warning(f"aiprep_tool tables unavailable, returning empty candidates list: {e}")
        return {"candidates": [], "total": 0}
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
        candidate_sql = """
            SELECT 
                c.*,
                cand.full_name AS joined_name,
                cand.email AS joined_email
            FROM candidate_marketing cm
            JOIN candidate cand ON cand.id = cm.candidate_id
            LEFT JOIN aiprep_tool_candidates c ON (c.wbl_email = cm.email OR c.wbl_email = cand.email OR c.email = cand.email OR c.name = cm.email OR c.user_id = :user_id)
            WHERE cm.id = :user_id_int OR c.user_id = :user_id
            LIMIT 1
        """
        user_id_int = int(user_id) if user_id.isdigit() else -1
        candidate = db.execute(text(candidate_sql), {"user_id": user_id, "user_id_int": user_id_int}).mappings().first()

        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        real_user_id = candidate.get("user_id") or user_id

        # Get resume JSON
        resume_res = db.execute(text("SELECT resume_json FROM aiprep_tool_resumes WHERE user_id = :user_id"), {"user_id": real_user_id}).mappings().first()
        resume_json = resume_res["resume_json"] if resume_res else None

        # All intro evaluations (timeline)
        intro_history = db.execute(text("""
            SELECT score, passed, feedback, created_at, video_url
            FROM aiprep_tool_evaluations
            WHERE user_id = :user_id AND type = 'intro'
            ORDER BY created_at ASC
        """), {"user_id": real_user_id}).mappings().all()

        # All interview answer evaluations
        interview_history = db.execute(text("""
            SELECT score, feedback, raw_response, created_at
            FROM aiprep_tool_evaluations
            WHERE user_id = :user_id AND type = 'interview_answer'
            ORDER BY created_at ASC
        """), {"user_id": real_user_id}).mappings().all()

        # Case studies
        case_studies = db.execute(text("""
            SELECT topic, created_at
            FROM aiprep_tool_case_studies
            WHERE user_id = :user_id OR candidate_id = :user_id_int
            ORDER BY created_at DESC
        """), {"user_id": real_user_id, "user_id_int": user_id_int}).mappings().all()

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

        intro_list = []
        for e in intro_history:
            intro_list.append({
                "score": e.get("score") or 0,
                "passed": bool(e.get("passed")),
                "feedback": parse_json_field(e.get("feedback")),
                "created_at": dtstr(e.get("created_at")),
                "video_url": e.get("video_url"),
            })

        interview_list = []
        for e in interview_history:
            interview_list.append({
                "score": e.get("score") or 0,
                "feedback": parse_json_field(e.get("feedback")),
                "created_at": dtstr(e.get("created_at")),
            })

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
                "user_id": real_user_id,
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
        }

    except HTTPException:
        raise
    except OperationalError as e:
        logger.warning(f"aiprep_tool tables unavailable for candidate detail: {e}")
        raise HTTPException(status_code=404, detail="Candidate not found (AI-Prep data unavailable)")
    except Exception as e:
        logger.error(f"Error in candidate details: {e}")
        raise HTTPException(status_code=500, detail=str(e))
