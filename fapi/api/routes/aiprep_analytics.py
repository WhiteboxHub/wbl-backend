"""
WBL Backend router for AI Prep Tool analytics.
Exposes candidate analytics to the Avatar Admin Dashboard.

Schema after V119 migration:
- aiprep_tool_evaluations: 1-per-candidate, keyed by candidate_marketing.id
- aiprep_tool_project_context: keyed by candidate_marketing.id
- aiprep_tool_case_studies: keyed by candidate_marketing.id
- Resumes: from candidate_resume (keyed by candidate.id)
- Identity: from candidate_marketing -> candidate
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.utils.auth_dependencies import staff_or_admin_required
from fapi.db.models import (
    CandidateMarketingORM,
    CandidateORM,
    AIPrepToolProjectContextORM,
    AIPrepToolEvaluationORM,
    AIPrepToolCaseStudyORM,
    CandidateResumeORM,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics/ai-prep", tags=["AI Prep Analytics"])


# ─── Helpers ───────────────────────────────────────────────────────────────

def _prep_status(has_resume, has_project, intro_passed):
    steps = sum([bool(has_resume), bool(has_project), bool(intro_passed)])
    pct = int(steps / 3 * 100)
    if pct == 100:
        label = "Complete"
    elif pct >= 66:
        label = "Almost Ready"
    elif pct >= 33:
        label = "In Progress"
    elif pct > 0:
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
        # Total active marketing candidates
        total_candidates = db.query(CandidateMarketingORM).filter(
            CandidateMarketingORM.status == 'active'
        ).count()

        # Total registered in AI Prep (have an evaluations row)
        total_ai_prep = db.query(AIPrepToolEvaluationORM).count()

        # Active this week (last_login within 7 days)
        week_ago = datetime.now() - timedelta(days=7)
        active_week = db.query(AIPrepToolEvaluationORM).filter(
            AIPrepToolEvaluationORM.last_login >= week_ago
        ).count()

        # Intro pass rate (intro_score >= 75)
        intro_passed_count = db.query(AIPrepToolEvaluationORM).filter(
            AIPrepToolEvaluationORM.intro_score >= 75
        ).count()
        intro_pass_rate = round(intro_passed_count / total_ai_prep * 100, 1) if total_ai_prep else 0

        # Case studies generated
        case_studies = db.query(AIPrepToolCaseStudyORM).count()

        return {
            "total_marketing_candidates": total_candidates,
            "total_ai_prep_registered": total_ai_prep,
            "active_this_week": active_week,
            "intro_pass_rate": intro_pass_rate,
            "total_case_studies": case_studies,
            "intro_passed_count": intro_passed_count,
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
        # Subqueries correlated to CandidateMarketingORM
        has_resume_sub = db.query(func.count(CandidateResumeORM.id)).filter(
            CandidateResumeORM.candidate_id == CandidateMarketingORM.candidate_id
        ).correlate(CandidateMarketingORM).as_scalar()

        resume_json_sub = db.query(CandidateResumeORM.resume_json).filter(
            CandidateResumeORM.candidate_id == CandidateMarketingORM.candidate_id
        ).order_by(CandidateResumeORM.id.desc()).limit(1).correlate(CandidateMarketingORM).as_scalar()

        has_project_sub = db.query(func.count(AIPrepToolProjectContextORM.id)).filter(
            AIPrepToolProjectContextORM.candidate_id == CandidateMarketingORM.id
        ).correlate(CandidateMarketingORM).as_scalar()

        case_studies_sub = db.query(func.count(AIPrepToolCaseStudyORM.id)).filter(
            AIPrepToolCaseStudyORM.candidate_id == CandidateMarketingORM.id
        ).correlate(CandidateMarketingORM).as_scalar()

        # Build main query joining candidate_marketing -> candidate -> evaluations
        db_rows = db.query(
            CandidateMarketingORM.id.label("marketing_id"),
            CandidateMarketingORM.candidate_id.label("candidate_id"),
            CandidateORM.full_name.label("name"),
            CandidateORM.email.label("email"),
            CandidateMarketingORM.email.label("wbl_email"),
            AIPrepToolEvaluationORM.login_count.label("login_count"),
            AIPrepToolEvaluationORM.last_login.label("last_login"),
            AIPrepToolEvaluationORM.intro_score.label("intro_score"),
            AIPrepToolEvaluationORM.intro_video.label("latest_video_url"),
            AIPrepToolEvaluationORM.intro_status.label("intro_status"),
            AIPrepToolEvaluationORM.created_at.label("created_at"),
            has_resume_sub.label("has_resume"),
            resume_json_sub.label("resume_json"),
            has_project_sub.label("has_project"),
            case_studies_sub.label("case_studies_generated"),
        ).join(
            CandidateORM, CandidateORM.id == CandidateMarketingORM.candidate_id
        ).outerjoin(
            AIPrepToolEvaluationORM,
            AIPrepToolEvaluationORM.candidate_id == CandidateMarketingORM.id
        ).filter(
            CandidateMarketingORM.status == 'active'
        ).order_by(
            AIPrepToolEvaluationORM.last_login.desc()
        ).all()

        rows = [r._mapping for r in db_rows]

        # Parse and compute fields
        results = []
        for row in rows:
            intro_score = row.get("intro_score") or 0
            intro_passed = intro_score >= 75

            pct, label = _prep_status(
                row.get("has_resume"),
                row.get("has_project"),
                intro_passed,
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
                "user_id": str(row["marketing_id"]),
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
                # Intro
                "intro_score": intro_score,
                "intro_status": row.get("intro_status") or "not_started",
                "intro_passed": intro_passed,
                "latest_video_url": row.get("latest_video_url"),
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

        if filter_active_week is True:
            week_ago_str = (datetime.utcnow() - timedelta(days=7)).isoformat()
            results = [r for r in results if r["last_login"] and r["last_login"] >= week_ago_str]

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
        try:
            marketing_id = int(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user_id format. Expected integer candidate marketing ID.")

        # Fetch candidate info via candidate_marketing
        row = db.query(
            CandidateMarketingORM.id.label("marketing_id"),
            CandidateMarketingORM.candidate_id.label("candidate_id"),
            CandidateORM.full_name.label("name"),
            CandidateORM.email.label("email"),
            CandidateMarketingORM.email.label("wbl_email"),
            AIPrepToolEvaluationORM.login_count.label("login_count"),
            AIPrepToolEvaluationORM.last_login.label("last_login"),
            AIPrepToolEvaluationORM.intro_score.label("intro_score"),
            AIPrepToolEvaluationORM.intro_video.label("intro_video"),
            AIPrepToolEvaluationORM.intro_status.label("intro_status"),
            AIPrepToolEvaluationORM.created_at.label("created_at"),
        ).join(
            CandidateORM, CandidateORM.id == CandidateMarketingORM.candidate_id
        ).outerjoin(
            AIPrepToolEvaluationORM,
            AIPrepToolEvaluationORM.candidate_id == CandidateMarketingORM.id
        ).filter(
            CandidateMarketingORM.id == marketing_id
        ).first()

        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found")

        candidate_map = row._mapping
        cid = candidate_map["candidate_id"]

        # Resume JSON from candidate_resume
        resume_res = db.query(CandidateResumeORM.resume_json).filter(
            CandidateResumeORM.candidate_id == cid
        ).order_by(CandidateResumeORM.id.desc()).first()
        resume_json = resume_res.resume_json if resume_res else None

        # Case studies
        cs_rows = db.query(
            AIPrepToolCaseStudyORM.topic,
            AIPrepToolCaseStudyORM.created_at
        ).filter(
            AIPrepToolCaseStudyORM.candidate_id == marketing_id
        ).order_by(AIPrepToolCaseStudyORM.created_at.desc()).all()

        def dtstr(v):
            return v.isoformat() if v else None

        resume_name, resume_email = _extract_from_resume(resume_json)
        disp_name = candidate_map.get("name")
        if (not disp_name or disp_name == "Candidate" or disp_name == "—") and resume_name:
            disp_name = resume_name
        if not disp_name:
            disp_name = "—"

        disp_email = candidate_map.get("email")
        if (not disp_email or disp_email == "—") and resume_email:
            disp_email = resume_email
        if not disp_email or disp_email == "—":
            disp_email = candidate_map.get("wbl_email") or "—"

        return {
            "candidate": {
                "id": candidate_map.get("marketing_id"),
                "user_id": user_id,
                "marketing_id": candidate_map.get("marketing_id"),
                "candidate_id": candidate_map.get("candidate_id"),
                "name": disp_name,
                "email": disp_email,
                "wbl_email": candidate_map.get("wbl_email") or "—",
                "login_count": candidate_map.get("login_count") or 0,
                "created_at": dtstr(candidate_map.get("created_at")),
                "last_login": dtstr(candidate_map.get("last_login")),
                "intro_score": candidate_map.get("intro_score"),
                "intro_video": candidate_map.get("intro_video"),
                "intro_status": candidate_map.get("intro_status") or "not_started",
            },
            "case_studies": [{"topic": cs.topic, "created_at": dtstr(cs.created_at)} for cs in cs_rows],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in candidate details: {e}")
        raise HTTPException(status_code=500, detail=str(e))
