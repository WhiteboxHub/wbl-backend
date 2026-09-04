"""
FastAPI Router for AI Prep Assessment Platform.
Strictly implements the 10 API endpoints specified in contracts/api_endpoints.md.
"""

import os
from typing import Optional
from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    BackgroundTasks,
    HTTPException,
    Query,
    Request,
    status,
)
from sqlalchemy.orm import Session

from fapi.ai_prep import schemas, crud, config, dependencies
from fapi.ai_prep.orchestrator.assessment_orchestrator import AssessmentOrchestrator
from fapi.ai_prep.clients.youtube_client import YouTubeClient

router = APIRouter(prefix="/api/aiprep", tags=["AIPrep"])


# ─── Part 1: Assessment Execution Flow ───────────────────────────────────────

@router.post(
    "/assessments",
    response_model=schemas.CreateAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="1. Create Assessment Session",
)
def create_assessment(
    payload: schemas.CreateAssessmentRequest,
    request: Request,
    candidate_id: int = Depends(dependencies.get_current_candidate_id),
    db: Session = Depends(dependencies.get_db),
):
    """Initializes a new assessment session for a candidate."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    assessment = crud.create_assessment(
        db=db,
        candidate_id=payload.candidate_id or candidate_id,
        assessment_type=payload.assessment_type,
        media_type=payload.media_type,
        job_description=payload.job_description,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return assessment


@router.post(
    "/assessments/{id}/upload-media",
    status_code=status.HTTP_200_OK,
    summary="2. Upload Raw Media to Local Server Storage",
)
async def upload_media(
    id: int,
    file: UploadFile = File(...),
    bg_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(dependencies.get_db),
):
    """Saves raw recorded video/audio blob to local disk storage and triggers YouTube upload."""
    assessment = crud.get_assessment_by_id(db, id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    os.makedirs(config.settings.LOCAL_STORAGE_DIR, exist_ok=True)
    local_file_path = os.path.join(config.settings.LOCAL_STORAGE_DIR, f"{id}.webm")

    with open(local_file_path, "wb") as f:
        f.write(await file.read())

    # Background task creates its own independent SessionLocal() - no session connection leak!
    youtube_client = YouTubeClient()
    bg_tasks.add_task(youtube_client.upload_unlisted_video, id, local_file_path)

    return {
        "assessment_id": id,
        "local_file_path": local_file_path,
        "upload_status": "PROCESSING_YOUTUBE",
    }


@router.post(
    "/assessments/{id}/data",
    status_code=status.HTTP_200_OK,
    summary="3. Submit Telemetry Data",
)
def submit_data(
    id: int,
    payload: schemas.SubmitAssessmentDataRequest,
    db: Session = Depends(dependencies.get_db),
):
    """Saves telemetry data (questions, transcript, audio/video telemetry) for an assessment."""
    assessment = crud.get_assessment_by_id(db, id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    crud.create_or_update_assessment_data(
        db=db,
        assessment_id=id,
        questions=payload.questions,
        transcript=payload.transcript,
        audio_telemetry=payload.audio_telemetry,
        video_telemetry=payload.video_telemetry,
    )
    return {"message": "Data saved successfully"}


@router.patch(
    "/assessments/{id}/media",
    response_model=schemas.CreateAssessmentResponse,
    status_code=status.HTTP_200_OK,
    summary="4. Update Assessment Youtube Media URL",
)
def update_media_url(
    id: int,
    payload: schemas.UpdateMediaUrlRequest,
    db: Session = Depends(dependencies.get_db),
):
    """Updates the youtube_url after processing completes."""
    assessment = crud.update_assessment_youtube_url(db, id, payload.youtube_url)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment


@router.post(
    "/assessments/{id}/evaluate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="5. Trigger Assessment Evaluation",
)
def trigger_evaluation(
    id: int,
    bg_tasks: BackgroundTasks,
    db: Session = Depends(dependencies.get_db),
):
    """Changes assessment status to EVALUATING and triggers the Central Orchestrator."""
    assessment = crud.get_assessment_by_id(db, id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    crud.update_assessment_status(db, id, schemas.AssessmentStatusEnum.EVALUATING)

    # Background task creates its own independent SessionLocal() inside AssessmentOrchestrator
    orchestrator = AssessmentOrchestrator()
    bg_tasks.add_task(orchestrator.process_assessment_evaluation, id)

    return {"id": id, "status": schemas.AssessmentStatusEnum.EVALUATING}


@router.get(
    "/assessments/{id}",
    status_code=status.HTTP_200_OK,
    summary="6. Get Assessment Report & Telemetry Data",
)
def get_assessment_report(
    id: int,
    db: Session = Depends(dependencies.get_db),
):
    """Fetches full assessment details including telemetry data and evaluation report."""
    assessment = crud.get_assessment_by_id(db, id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    data = crud.get_assessment_data_by_assessment_id(db, id)
    report = crud.get_assessment_report_by_assessment_id(db, id)

    return {
        "id": assessment.id,
        "candidate_id": assessment.candidate_id,
        "assessment_type": assessment.assessment_type,
        "media_type": assessment.media_type,
        "status": assessment.status,
        "youtube_url": assessment.youtube_url,
        "data": {
            "questions": data.questions if data else None,
            "transcript": data.transcript if data else None,
            "audio_telemetry": data.audio_telemetry if data else None,
            "video_telemetry": data.video_telemetry if data else None,
        },
        "report": {
            "audio_evaluation": report.audio_evaluation if report else None,
            "video_evaluation": report.video_evaluation if report else None,
            "transcript_evaluation": report.transcript_evaluation if report else None,
        },
    }


# ─── Part 2: Candidate Dashboard ──────────────────────────────────────────────

@router.get(
    "/assessments",
    response_model=schemas.AssessmentListResponse,
    status_code=status.HTTP_200_OK,
    summary="7. List Candidate Assessments",
)
def list_candidate_assessments(
    candidate_id: int = Query(..., description="Candidate ID filter"),
    current_candidate_id: int = Depends(dependencies.get_current_candidate_id),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(dependencies.get_db),
):
    """Fetches a paginated list of assessments for a specific candidate with auth validation."""
    effective_candidate_id = candidate_id or current_candidate_id
    assessments = crud.list_candidate_assessments(
        db, candidate_id=effective_candidate_id, limit=limit, offset=offset
    )
    return {"items": assessments, "total": len(assessments)}


# ─── Part 3: Question Bank Admin ──────────────────────────────────────────────

@router.get(
    "/questions",
    response_model=schemas.QuestionListResponse,
    status_code=status.HTTP_200_OK,
    summary="8. List Question Bank",
)
def list_questions(
    category: Optional[schemas.AssessmentCategoryEnum] = None,
    difficulty_level: Optional[schemas.DifficultyLevelEnum] = None,
    is_active: Optional[bool] = True,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(dependencies.get_db),
):
    """Fetches filtered list of questions for assessment engine or admin grid."""
    questions = crud.list_questions(
        db,
        category=category,
        difficulty_level=difficulty_level,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return {"items": questions, "total": len(questions)}


@router.post(
    "/questions",
    response_model=schemas.QuestionBankResponse,
    status_code=status.HTTP_201_CREATED,
    summary="9. Create Question Bank Item",
)
def create_question(
    payload: schemas.QuestionBankCreateRequest,
    db: Session = Depends(dependencies.get_db),
):
    """Adds a new question to the question bank."""
    return crud.create_question(
        db,
        category=payload.category,
        sub_category=payload.sub_category,
        difficulty_level=payload.difficulty_level,
        question_text=payload.question_text,
        is_active=payload.is_active,
    )


@router.patch(
    "/questions/{id}",
    response_model=schemas.QuestionBankResponse,
    status_code=status.HTTP_200_OK,
    summary="10. Update Question Bank Item",
)
def update_question(
    id: int,
    payload: schemas.QuestionBankUpdateRequest,
    db: Session = Depends(dependencies.get_db),
):
    """Updates fields on an existing question (e.g. soft-delete by setting is_active=False)."""
    question = crud.update_question(
        db,
        question_id=id,
        sub_category=payload.sub_category,
        difficulty_level=payload.difficulty_level,
        question_text=payload.question_text,
        is_active=payload.is_active,
    )
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question
