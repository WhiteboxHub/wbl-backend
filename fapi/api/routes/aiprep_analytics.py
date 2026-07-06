"""
WBL Backend router for AI Prep Tool analytics.
Exposes candidate analytics to the Avatar Admin Dashboard.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text, func, or_, and_, case
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.utils.auth_dependencies import staff_or_admin_required
from fapi.db.models import (
    CandidateMarketingORM,
    CandidateORM,
    AIPrepToolCandidateORM,
    AIPrepToolResumeORM,
    AIPrepToolProjectContextORM,
    AIPrepToolEvaluationORM,
    AIPrepToolCaseStudyORM
)

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
        total_candidates = db.query(CandidateMarketingORM).filter(
            CandidateMarketingORM.status == 'active'
        ).count()

        # Active this week (logged in to AI Prep tool)
        week_ago = datetime.now() - timedelta(days=7)
        active_week = db.query(func.count(func.distinct(AIPrepToolCandidateORM.user_id))).join(
            CandidateMarketingORM,
            or_(
                AIPrepToolCandidateORM.wbl_email == CandidateMarketingORM.email,
                AIPrepToolCandidateORM.email == CandidateMarketingORM.email
            )
        ).filter(
            CandidateMarketingORM.status == 'active',
            AIPrepToolCandidateORM.last_login >= week_ago
        ).scalar() or 0

        # Intro pass rate
        intro_passed_users = db.query(func.count(func.distinct(AIPrepToolCandidateORM.user_id))).join(
            AIPrepToolEvaluationORM,
            AIPrepToolEvaluationORM.user_id == AIPrepToolCandidateORM.user_id
        ).join(
            CandidateMarketingORM,
            or_(
                AIPrepToolCandidateORM.wbl_email == CandidateMarketingORM.email,
                AIPrepToolCandidateORM.email == CandidateMarketingORM.email
            )
        ).filter(
            CandidateMarketingORM.status == 'active',
            AIPrepToolEvaluationORM.type == 'intro',
            AIPrepToolEvaluationORM.passed == True
        ).scalar() or 0
        intro_pass_rate = round(intro_passed_users / total_candidates * 100, 1) if total_candidates else 0

        # Interview completion rate
        interview_completed = db.query(func.count(func.distinct(AIPrepToolCandidateORM.user_id))).join(
            AIPrepToolEvaluationORM,
            AIPrepToolEvaluationORM.user_id == AIPrepToolCandidateORM.user_id
        ).join(
            CandidateMarketingORM,
            or_(
                AIPrepToolCandidateORM.wbl_email == CandidateMarketingORM.email,
                AIPrepToolCandidateORM.email == CandidateMarketingORM.email
            )
        ).filter(
            CandidateMarketingORM.status == 'active',
            AIPrepToolEvaluationORM.type == 'interview_complete'
        ).scalar() or 0
        interview_completion_rate = round(interview_completed / total_candidates * 100, 1) if total_candidates else 0

        # Case studies generated
        case_studies = db.query(AIPrepToolCaseStudyORM).count()

        return {
            "total_candidates": total_candidates,
            "active_this_week": active_week,
            "intro_pass_rate": intro_pass_rate,
            "interview_completion_rate": interview_completion_rate,
            "total_case_studies": case_studies,
            "intro_passed_count": intro_passed_users,
            "interview_completed_count": interview_completed,
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
    try:
        # Define the scalar subqueries
        has_resume_sub = db.query(func.count(AIPrepToolResumeORM.id)).filter(
            or_(
                AIPrepToolResumeORM.user_id == AIPrepToolCandidateORM.user_id,
                AIPrepToolResumeORM.user_id == CandidateORM.id
            )
        ).correlate(AIPrepToolCandidateORM, CandidateORM).as_scalar()

        resume_json_sub = db.query(AIPrepToolResumeORM.resume_json).filter(
            or_(
                AIPrepToolResumeORM.user_id == AIPrepToolCandidateORM.user_id,
                AIPrepToolResumeORM.user_id == CandidateORM.id
            )
        ).correlate(AIPrepToolCandidateORM, CandidateORM).limit(1).as_scalar()

        has_project_sub = db.query(func.count(AIPrepToolProjectContextORM.id)).filter(
            or_(
                AIPrepToolProjectContextORM.user_id == AIPrepToolCandidateORM.user_id,
                AIPrepToolProjectContextORM.user_id == CandidateORM.id
            )
        ).correlate(AIPrepToolCandidateORM, CandidateORM).as_scalar()

        intro_attempts_sub = db.query(func.count(AIPrepToolEvaluationORM.id)).filter(
            or_(
                AIPrepToolEvaluationORM.user_id == AIPrepToolCandidateORM.user_id,
                AIPrepToolEvaluationORM.user_id == CandidateORM.id
            ),
            AIPrepToolEvaluationORM.type == 'intro'
        ).correlate(AIPrepToolCandidateORM, CandidateORM).as_scalar()

        best_intro_score_sub = db.query(func.max(AIPrepToolEvaluationORM.score)).filter(
            or_(
                AIPrepToolEvaluationORM.user_id == AIPrepToolCandidateORM.user_id,
                AIPrepToolEvaluationORM.user_id == CandidateORM.id
            ),
            AIPrepToolEvaluationORM.type == 'intro'
        ).correlate(AIPrepToolCandidateORM, CandidateORM).as_scalar()

        intro_passed_sub = db.query(func.max(case((AIPrepToolEvaluationORM.passed == True, 1), else_=0))).filter(
            or_(
                AIPrepToolEvaluationORM.user_id == AIPrepToolCandidateORM.user_id,
                AIPrepToolEvaluationORM.user_id == CandidateORM.id
            ),
            AIPrepToolEvaluationORM.type == 'intro'
        ).correlate(AIPrepToolCandidateORM, CandidateORM).as_scalar()

        latest_intro_score_sub = db.query(AIPrepToolEvaluationORM.score).filter(
            or_(
                AIPrepToolEvaluationORM.user_id == AIPrepToolCandidateORM.user_id,
                AIPrepToolEvaluationORM.user_id == CandidateORM.id
            ),
            AIPrepToolEvaluationORM.type == 'intro'
        ).order_by(AIPrepToolEvaluationORM.created_at.desc()).limit(1).correlate(AIPrepToolCandidateORM, CandidateORM).as_scalar()

        latest_video_url_sub = db.query(AIPrepToolEvaluationORM.video_url).filter(
            or_(
                AIPrepToolEvaluationORM.user_id == AIPrepToolCandidateORM.user_id,
                AIPrepToolEvaluationORM.user_id == CandidateORM.id
            ),
            AIPrepToolEvaluationORM.type == 'intro',
            AIPrepToolEvaluationORM.video_url.isnot(None)
        ).order_by(AIPrepToolEvaluationORM.created_at.desc()).limit(1).correlate(AIPrepToolCandidateORM, CandidateORM).as_scalar()

        questions_answered_sub = db.query(func.count(AIPrepToolEvaluationORM.id)).filter(
            or_(
                AIPrepToolEvaluationORM.user_id == AIPrepToolCandidateORM.user_id,
                AIPrepToolEvaluationORM.user_id == CandidateORM.id
            ),
            AIPrepToolEvaluationORM.type == 'interview_answer'
        ).correlate(AIPrepToolCandidateORM, CandidateORM).as_scalar()

        avg_interview_score_sub = db.query(func.round(func.avg(AIPrepToolEvaluationORM.score) * 10, 1)).filter(
            or_(
                AIPrepToolEvaluationORM.user_id == AIPrepToolCandidateORM.user_id,
                AIPrepToolEvaluationORM.user_id == CandidateORM.id
            ),
            AIPrepToolEvaluationORM.type == 'interview_answer'
        ).correlate(AIPrepToolCandidateORM, CandidateORM).as_scalar()

        interview_sessions_sub = db.query(func.count(AIPrepToolEvaluationORM.id)).filter(
            or_(
                AIPrepToolEvaluationORM.user_id == AIPrepToolCandidateORM.user_id,
                AIPrepToolEvaluationORM.user_id == CandidateORM.id
            ),
            AIPrepToolEvaluationORM.type == 'interview_complete'
        ).correlate(AIPrepToolCandidateORM, CandidateORM).as_scalar()

        interview_completed_sub = db.query(func.max(case((AIPrepToolEvaluationORM.type == 'interview_complete', 1), else_=0))).filter(
            or_(
                AIPrepToolEvaluationORM.user_id == AIPrepToolCandidateORM.user_id,
                AIPrepToolEvaluationORM.user_id == CandidateORM.id
            )
        ).correlate(AIPrepToolCandidateORM, CandidateORM).as_scalar()

        case_studies_generated_sub = db.query(func.count(AIPrepToolCaseStudyORM.id)).filter(
            or_(
                AIPrepToolCaseStudyORM.user_id == AIPrepToolCandidateORM.user_id,
                AIPrepToolCaseStudyORM.user_id == CandidateORM.id
            )
        ).correlate(AIPrepToolCandidateORM, CandidateORM).as_scalar()

        # Build main query
        db_rows = db.query(
            CandidateMarketingORM.id.label("id"),
            func.coalesce(AIPrepToolCandidateORM.user_id, func.concat('marketing_', CandidateMarketingORM.id)).label("user_id"),
            CandidateORM.full_name.label("name"),
            CandidateORM.email.label("email"),
            func.coalesce(AIPrepToolCandidateORM.wbl_email, CandidateMarketingORM.email, CandidateORM.email).label("wbl_email"),
            func.coalesce(AIPrepToolCandidateORM.login_count, 0).label("login_count"),
            AIPrepToolCandidateORM.created_at.label("created_at"),
            AIPrepToolCandidateORM.last_login.label("last_login"),
            func.coalesce(AIPrepToolCandidateORM.extraction_status, 'pending').label("extraction_status"),
            
            has_resume_sub.label("has_resume"),
            resume_json_sub.label("resume_json"),
            has_project_sub.label("has_project"),
            intro_attempts_sub.label("intro_attempts"),
            best_intro_score_sub.label("best_intro_score"),
            intro_passed_sub.label("intro_passed"),
            latest_intro_score_sub.label("latest_intro_score"),
            latest_video_url_sub.label("latest_video_url"),
            questions_answered_sub.label("questions_answered"),
            avg_interview_score_sub.label("avg_interview_score"),
            interview_sessions_sub.label("interview_sessions"),
            interview_completed_sub.label("interview_completed"),
            case_studies_generated_sub.label("case_studies_generated")
        ).join(
            CandidateORM, CandidateORM.id == CandidateMarketingORM.candidate_id
        ).outerjoin(
            AIPrepToolCandidateORM,
            or_(
                AIPrepToolCandidateORM.wbl_email == CandidateMarketingORM.email,
                AIPrepToolCandidateORM.email == CandidateORM.email,
                AIPrepToolCandidateORM.wbl_email == CandidateORM.email
            )
        ).filter(
            CandidateMarketingORM.status == 'active'
        ).order_by(
            AIPrepToolCandidateORM.last_login.desc()
        ).all()

        rows = [r._mapping for r in db_rows]

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
            candidate = db.query(
                CandidateMarketingORM.id.label("marketing_id"),
                CandidateORM.full_name.label("joined_name"),
                CandidateORM.email.label("joined_email"),
                CandidateMarketingORM.email.label("wbl_email")
            ).join(
                CandidateORM, CandidateORM.id == CandidateMarketingORM.candidate_id
            ).filter(
                CandidateMarketingORM.id == marketing_id
            ).first()

            if not candidate:
                raise HTTPException(status_code=404, detail="Candidate not found")
            
            candidate_map = candidate._mapping

            return {
                "candidate": {
                    "user_id": user_id,
                    "name": candidate_map.get("joined_name"),
                    "email": candidate_map.get("joined_email"),
                    "wbl_email": candidate_map.get("wbl_email") or "—",
                    "login_count": 0,
                    "created_at": None,
                    "last_login": None,
                },
                "intro_history": [],
                "interview_history": [],
                "case_studies": [],
                "coderpad": {},
            }

        # Otherwise, candidate exists in aiprep_tool_candidates
        candidate = db.query(
            AIPrepToolCandidateORM.id,
            AIPrepToolCandidateORM.user_id,
            AIPrepToolCandidateORM.wbl_email,
            AIPrepToolCandidateORM.email,
            AIPrepToolCandidateORM.role,
            AIPrepToolCandidateORM.api_key_encrypted,
            AIPrepToolCandidateORM.login_count,
            AIPrepToolCandidateORM.last_login,
            AIPrepToolCandidateORM.extraction_status,
            AIPrepToolCandidateORM.created_at,
            CandidateORM.full_name.label("joined_name"),
            CandidateORM.email.label("joined_email"),
            CandidateORM.id.label("cand_id")
        ).outerjoin(
            CandidateORM,
            or_(
                CandidateORM.email == AIPrepToolCandidateORM.wbl_email,
                CandidateORM.email == AIPrepToolCandidateORM.email
            )
        ).filter(
            AIPrepToolCandidateORM.user_id == user_id
        ).first()

        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        candidate_map = candidate._mapping
        cand_id = str(candidate_map.get("cand_id")) if candidate_map.get("cand_id") is not None else None

        # Get resume JSON if any to extract details
        resume_res = db.query(AIPrepToolResumeORM.resume_json).filter(
            or_(
                AIPrepToolResumeORM.user_id == user_id,
                and_(cand_id is not None, AIPrepToolResumeORM.user_id == cand_id)
            )
        ).first()
        resume_json = resume_res.resume_json if resume_res else None

        # All intro evaluations (timeline)
        intro_history_rows = db.query(
            AIPrepToolEvaluationORM.score,
            AIPrepToolEvaluationORM.passed,
            AIPrepToolEvaluationORM.feedback,
            AIPrepToolEvaluationORM.created_at
        ).filter(
            or_(
                AIPrepToolEvaluationORM.user_id == user_id,
                and_(cand_id is not None, AIPrepToolEvaluationORM.user_id == cand_id)
            ),
            AIPrepToolEvaluationORM.type == 'intro'
        ).order_by(AIPrepToolEvaluationORM.created_at.asc()).all()

        intro_history = [e._mapping for e in intro_history_rows]

        # All interview answer evaluations
        interview_history_rows = db.query(
            AIPrepToolEvaluationORM.score,
            AIPrepToolEvaluationORM.feedback,
            AIPrepToolEvaluationORM.raw_response,
            AIPrepToolEvaluationORM.created_at
        ).filter(
            or_(
                AIPrepToolEvaluationORM.user_id == user_id,
                and_(cand_id is not None, AIPrepToolEvaluationORM.user_id == cand_id)
            ),
            AIPrepToolEvaluationORM.type == 'interview_answer'
        ).order_by(AIPrepToolEvaluationORM.created_at.asc()).all()

        interview_history = [e._mapping for e in interview_history_rows]

        # Case studies
        case_studies_rows = db.query(
            AIPrepToolCaseStudyORM.topic,
            AIPrepToolCaseStudyORM.created_at
        ).filter(
            or_(
                AIPrepToolCaseStudyORM.user_id == user_id,
                and_(cand_id is not None, AIPrepToolCaseStudyORM.user_id == cand_id)
            )
        ).order_by(AIPrepToolCaseStudyORM.created_at.desc()).all()

        case_studies = [cs._mapping for cs in case_studies_rows]

        # CoderPad stats directly from live WBL execution logs removed

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

        resume_name, resume_email = _extract_from_resume(resume_json)
        disp_name = candidate_map.get("joined_name")
        if (not disp_name or disp_name == "Candidate" or disp_name == "—") and resume_name:
            disp_name = resume_name
        if not disp_name:
            disp_name = "—"

        disp_email = candidate_map.get("joined_email")
        if (not disp_email or disp_email == "—") and resume_email:
            disp_email = resume_email
        if not disp_email or disp_email == "—":
            disp_email = candidate_map.get("wbl_email") or "—"

        return {
            "candidate": {
                "user_id": candidate_map.get("user_id"),
                "name": disp_name,
                "email": disp_email,
                "wbl_email": candidate_map.get("wbl_email") or "—",
                "login_count": candidate_map.get("login_count") or 0,
                "created_at": dtstr(candidate_map.get("created_at")),
                "last_login": dtstr(candidate_map.get("last_login")),
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
