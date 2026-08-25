import json
import asyncio
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from fapi.db.database import get_db
from fapi.utils.auth_dependencies import get_current_user
from fapi.ai_prep.dependencies import get_assessment_or_403, get_candidate_id_for_user
from fapi.ai_prep.models import (
    AiPrepAssessmentORM,
    AiPrepQuestionBankORM,
    AiPrepAssessmentQuestionORM,
    AssessmentStatusEnum,
    AssessmentTypeEnum,
    RunTypeEnum,
    RunStatusEnum,
)
from fapi.ai_prep.schemas import (
    CreateAssessmentRequest,
    AssessmentOut,
    AssessmentListResponse,
    AssessmentListItem,
    UpdateAssessmentStatusRequest,
    ProcessingStatusResponse,
    ProcessingStepsStatus,
    QuestionSummaryOut,
)
from fapi.ai_prep.crud.assessments import (
    get_assessment,
    list_assessments_by_candidate,
    update_assessment_status,
)
from fapi.ai_prep.crud.runs import get_runs_by_assessment_id

logger = logging.getLogger("wbl.ai_prep.api.assessments")
router = APIRouter(prefix="/assessments", tags=["AIPrep Assessments"])

# Assessment types that forbid pausing per ADR-006
NO_PAUSE_ASSESSMENT_TYPES = [
    AssessmentTypeEnum.GENERAL_INTRO,
    AssessmentTypeEnum.JOB_DESCRIPTION_INTRO,
]


def _build_processing_status(assessment: AiPrepAssessmentORM, db: Session) -> ProcessingStatusResponse:
    runs = get_runs_by_assessment_id(db, assessment.id)
    steps = ProcessingStepsStatus()

    for run in runs:
        if run.run_type == RunTypeEnum.STT:
            steps.stt = run.status
        elif run.run_type == RunTypeEnum.AUDIO:
            steps.audio = run.status
        elif run.run_type == RunTypeEnum.VISION:
            steps.vision = run.status
        elif run.run_type == RunTypeEnum.LLM:
            steps.llm = run.status
        elif run.run_type == RunTypeEnum.YOUTUBE_UPLOAD:
            steps.youtube_upload = run.status
        elif run.run_type == RunTypeEnum.FULL:
            steps.finalize = run.status

    if assessment.status == AssessmentStatusEnum.COMPLETED:
        steps.finalize = RunStatusEnum.COMPLETED

    return ProcessingStatusResponse(status=assessment.status, steps=steps)


@router.post("", response_model=AssessmentOut, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    payload: CreateAssessmentRequest,
    candidate_id: Optional[int] = Query(None, description="Candidate ID"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new practice assessment session and select matching questions."""
    resolved_cid = get_candidate_id_for_user(current_user, db) if current_user else None
    target_cid = candidate_id if candidate_id is not None else resolved_cid
    if target_cid is None:
        target_cid = 1

    assessment = AiPrepAssessmentORM(
        candidate_id=target_cid,
        candidate_resume_id=payload.candidate_resume_id,
        assessment_type=payload.assessment_type,
        assessment_mode=payload.assessment_mode,
        status=AssessmentStatusEnum.TESTING,
        job_description_text=payload.job_description_text,
        created_at=datetime.utcnow()
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    # Attach active questions from Question Bank if available
    questions = db.query(AiPrepQuestionBankORM).filter(
        AiPrepQuestionBankORM.is_active == True
    ).limit(5).all()

    for idx, q in enumerate(questions, start=1):
        join_row = AiPrepAssessmentQuestionORM(
            assessment_id=assessment.id,
            question_id=q.id,
            order_index=idx
        )
        db.add(join_row)

    if questions:
        db.commit()
        db.refresh(assessment)

    return await get_assessment_detail(assessment.id, current_user, db)


@router.get("/{id}/processing-status")
async def get_processing_status(
    id: int,
    request: Request,
    stream: bool = False,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns step-by-step progress for an assessment.
    Supports Server-Sent Events (SSE) streaming when stream=true or Accept includes text/event-stream.
    Includes 15s keep-alive heartbeat pings and event-type demarcation.
    """
    assessment = await get_assessment_or_403(id, current_user, db)
    accept_header = request.headers.get("Accept", "")

    if stream or "text/event-stream" in accept_header:
        async def event_generator():
            ping_counter = 0
            for _ in range(60):  # Stream for up to 60 iterations (120s max)
                # Fresh database query per loop
                current_ass = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == id).first()
                if not current_ass:
                    yield f"event: error\ndata: {json.dumps({'detail': 'Assessment not found'})}\n\n"
                    break

                status_resp = _build_processing_status(current_ass, db)
                payload = json.dumps(status_resp.model_dump(mode="json"))

                if current_ass.status == AssessmentStatusEnum.COMPLETED:
                    yield f"event: complete\ndata: {payload}\n\n"
                    break
                elif current_ass.status == AssessmentStatusEnum.FAILED:
                    yield f"event: error\ndata: {payload}\n\n"
                    break
                else:
                    yield f"event: status_update\ndata: {payload}\n\n"

                # Send keep-alive comment every ~14 seconds
                ping_counter += 1
                if ping_counter % 7 == 0:
                    yield ": ping\n\n"

                await asyncio.sleep(2)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    return _build_processing_status(assessment, db)


@router.get("/{id}", response_model=AssessmentOut)
async def get_assessment_detail(
    id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves full assessment details with assigned questions."""
    assessment = await get_assessment_or_403(id, current_user, db)
    q_summaries = []
    for aq in sorted(assessment.questions, key=lambda x: x.order_index):
        q_summaries.append(
            QuestionSummaryOut(
                id=aq.question.id,
                order_index=aq.order_index,
                question_text=aq.question.question_text,
                difficulty_level=aq.question.difficulty_level,
                category=aq.question.category,
                sub_category=aq.question.sub_category
            )
        )

    band = assessment.report.coaching_band if assessment.report else None

    return AssessmentOut(
        id=assessment.id,
        candidate_id=assessment.candidate_id,
        candidate_resume_id=assessment.candidate_resume_id,
        assessment_type=assessment.assessment_type,
        assessment_mode=assessment.assessment_mode,
        status=assessment.status,
        attempt_number=assessment.attempt_number,
        job_description_text=assessment.job_description_text,
        questions=q_summaries,
        started_at=assessment.started_at,
        completed_at=assessment.completed_at,
        coaching_band=band,
        created_at=assessment.created_at,
        updated_at=assessment.updated_at
    )


@router.get("", response_model=AssessmentListResponse)
async def list_assessments(
    candidate_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists assessments for the authenticated candidate."""
    resolved_cid = get_candidate_id_for_user(current_user, db)
    target_cid = candidate_id if candidate_id is not None else resolved_cid

    if target_cid is None:
        return AssessmentListResponse(items=[], total=0)

    # If non-admin attempts to view other candidates' assessments
    is_admin = getattr(current_user, "is_admin", False) or getattr(current_user, "role", "") == "admin"
    if not is_admin and target_cid != resolved_cid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view assessments belonging to other candidates"
        )

    assessments = list_assessments_by_candidate(db, target_cid, skip=skip, limit=limit)
    items = []
    for ass in assessments:
        band = ass.report.coaching_band if ass.report else None
        items.append(
            AssessmentListItem(
                id=ass.id,
                assessment_type=ass.assessment_type,
                assessment_mode=ass.assessment_mode,
                status=ass.status,
                attempt_number=ass.attempt_number,
                coaching_band=band,
                created_at=ass.created_at
            )
        )

    return AssessmentListResponse(items=items, total=len(items))


@router.patch("/{id}/status", response_model=AssessmentOut)
async def patch_assessment_status(
    id: int,
    status_update: UpdateAssessmentStatusRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Updates assessment state transitions.
    Enforces ADR-006 no-pause rule on GENERAL_INTRO and JOB_DESCRIPTION_INTRO.
    """
    assessment = await get_assessment_or_403(id, current_user, db)
    new_status = status_update.status

    # Validate state transition rules
    if assessment.status == AssessmentStatusEnum.COMPLETED and new_status != AssessmentStatusEnum.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify status of a COMPLETED assessment"
        )

    started_at = None
    if new_status == AssessmentStatusEnum.IN_PROGRESS and not assessment.started_at:
        started_at = datetime.utcnow()

    update_assessment_status(db, id, new_status, started_at=started_at)
    db.refresh(assessment)

    return await get_assessment_detail(id, current_user, db)
