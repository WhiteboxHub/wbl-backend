"""
Assessment Orchestrator Implementation for AI Prep Platform.
Thin Coordination Layer ('brain of the system').
Sequences calls between DB persistence (crud.py), business engine (AssessmentEngine),
and AI evaluation pipeline (llm_orchestrator.py). ZERO business logic lives here.
"""

import asyncio
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from fapi.db.database import SessionLocal
from fapi.db.models import CandidateLlmApiKeyORM
from fapi.ai_prep import crud
from fapi.ai_prep.schemas import (
    AssessmentCategoryEnum,
    MediaTypeEnum,
    AssessmentStatusEnum,
)
from fapi.ai_prep.core.assessment_engine import AssessmentEngine
from fapi.ai_prep.orchestrator import llm_orchestrator
from fapi.ai_prep.services.storage_service import storage_service
from fapi.ai_prep.services.media_service import media_service
from fapi.ai_prep.services.youtube_service import youtube_service

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class AssessmentOrchestrator:
    """
    Thin Coordination Layer — orchestrates CRUD + Engine + LLM Orchestrator.
    Contains ZERO business logic. All decisions, validations, pre-flight checks,
    question selections, and response payload formatting are delegated to AssessmentEngine.
    """

    @staticmethod
    def start_assessment(
        db: Any,
        candidate_id: int,
        assessment_type: AssessmentCategoryEnum,
        media_type: MediaTypeEnum,
        job_description: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Workflow: Start Assessment
        1. crud   → check active LLM key & candidate resume pre-flight status
        2. engine → validate pre-flight conditions (raises exception if missing)
        3. crud   → create new assessment record in DB
        4. crud   → fetch eligible questions from DB
        5. engine → validate START operation, select questions, build start response payload
        """
        # 1. DB: Retrieve pre-flight requirement states
        has_active_key = (
            db.query(CandidateLlmApiKeyORM.id)
            .filter(
                CandidateLlmApiKeyORM.candidate_id == candidate_id,
                CandidateLlmApiKeyORM.status == "active",
            )
            .first()
            is not None
        )
        resume_json = crud.get_candidate_resume_json(db, candidate_id)

        # 2. Engine: Validate pre-flight conditions
        AssessmentEngine.validate_preflight(
            has_active_key=has_active_key,
            has_resume=(resume_json is not None),
        )

        # 3. DB: Create assessment record
        assessment_orm = crud.create_assessment(
            db=db,
            candidate_id=candidate_id,
            assessment_type=assessment_type,
            media_type=media_type,
            job_description=job_description,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # 4. DB: Fetch eligible questions from question bank
        eligible_questions = crud.list_questions_by_category(db, category=assessment_type)

        # 5. Engine: Execute start assessment business logic & build response payload
        return AssessmentEngine.start_assessment(
            assessment_orm=assessment_orm,
            eligible_questions=eligible_questions,
        )

    @staticmethod
    def submit_assessment(
        db: Any,
        assessment_id: int,
        questions: List[Dict[str, Any]],
        transcript: Dict[str, Any],
        audio_telemetry: Dict[str, Any],
        video_telemetry: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Workflow: Submit Assessment
        1. crud   → fetch assessment record
        2. engine → validate SUBMIT operation and extract transcript/type info
        3. crud   → persist status change to EVALUATING + save telemetry data
        4. crud   → fetch LLM config + resume JSON
        5. llm    → run evaluation pipeline
        6. crud   → persist evaluation report + mark COMPLETED (or FAILED)
        7. engine → build completion response
        """
        # 1. DB: Fetch assessment record
        assessment_orm = crud.get_assessment_by_id(db, assessment_id)
        if not assessment_orm:
            raise ValueError(f"Assessment ID {assessment_id} not found.")

        # 2. Engine: Validate operation and prepare submission parameters
        prep = AssessmentEngine.submit_assessment(
            assessment_orm=assessment_orm,
            transcript=transcript,
        )

        # 3. DB: Persist status change and submitted data
        crud.update_assessment_status(db, assessment_id, AssessmentStatusEnum.EVALUATING)
        crud.save_assessment_data(
            db=db,
            assessment_id=assessment_id,
            questions=questions,
            transcript=transcript,
            audio_telemetry=audio_telemetry,
            video_telemetry=video_telemetry,
        )

        try:
            # 4. DB: Fetch LLM config and candidate resume JSON
            llm_config = llm_orchestrator.get_candidate_llm_config(db, assessment_orm.candidate_id)
            resume_json = crud.get_candidate_resume_json(db, assessment_orm.candidate_id)

            # 5. LLM Orchestrator: Run evaluation pipeline
            eval_results = asyncio.run(
                llm_orchestrator.run_evaluation(
                    candidate_id=assessment_orm.candidate_id,
                    assessment_type=prep["assessment_type_str"],
                    transcript_text=prep["transcript_text"],
                    audio_telemetry=audio_telemetry,
                    video_telemetry=video_telemetry,
                    resume_json=resume_json,
                    llm_config=llm_config,
                    db=db,
                )
            )

            # 6. DB: Persist evaluation report & transition status to COMPLETED
            crud.save_assessment_report(
                db=db,
                assessment_id=assessment_id,
                audio_evaluation=eval_results["audio_evaluation"],
                video_evaluation=eval_results["video_evaluation"],
                transcript_evaluation=eval_results["transcript_evaluation"],
            )
            AssessmentEngine.transition_evaluation_status(
                assessment_id=assessment_id,
                current_status=AssessmentStatusEnum.EVALUATING,
                success=True,
            )
            crud.update_assessment_status(db, assessment_id, AssessmentStatusEnum.COMPLETED)

            # 7. Engine: Build final completion response
            return AssessmentEngine.build_completion_response(assessment_id)

        except Exception:
            AssessmentEngine.transition_evaluation_status(
                assessment_id=assessment_id,
                current_status=AssessmentStatusEnum.EVALUATING,
                success=False,
            )
            crud.update_assessment_status(db, assessment_id, AssessmentStatusEnum.FAILED)
            raise

    def process_assessment_evaluation(self, assessment_id: int) -> None:
        """
        Workflow: Background Evaluation Task (own DB session).
        Called by FastAPI BackgroundTasks after media upload.

        1. crud   → open own DB session, fetch assessment + telemetry data
        2. engine → prepare background evaluation parameters
        3. crud   → fetch LLM config + candidate resume JSON
        4. llm    → run evaluation pipeline
        5. crud   → persist report + mark COMPLETED (or FAILED on error)
        """
        db = SessionLocal()
        try:
            # 1. DB: Fetch assessment & telemetry data
            assessment_orm = crud.get_assessment_by_id(db, assessment_id)
            if not assessment_orm:
                raise ValueError(f"Assessment ID {assessment_id} not found in background task.")

            data_orm = crud.get_assessment_data(db, assessment_id)

            # 2. Engine: Extract & prepare parameters for background evaluation
            eval_prep = AssessmentEngine.process_assessment_evaluation(
                assessment_orm=assessment_orm,
                data_orm=data_orm,
            )

            # 3. DB: Fetch LLM config and candidate resume
            llm_config = llm_orchestrator.get_candidate_llm_config(db, assessment_orm.candidate_id)
            resume_json = crud.get_candidate_resume_json(db, assessment_orm.candidate_id)

            # 4. LLM Orchestrator: Run evaluation pipeline
            eval_results = asyncio.run(
                llm_orchestrator.run_evaluation(
                    candidate_id=assessment_orm.candidate_id,
                    assessment_type=eval_prep["assessment_type_str"],
                    transcript_text=eval_prep["transcript_text"],
                    audio_telemetry=eval_prep["audio_telemetry"],
                    video_telemetry=eval_prep["video_telemetry"],
                    resume_json=resume_json,
                    llm_config=llm_config,
                    db=db,
                )
            )

            # 5. DB: Save report & mark COMPLETED
            crud.save_assessment_report(
                db=db,
                assessment_id=assessment_id,
                audio_evaluation=eval_results["audio_evaluation"],
                video_evaluation=eval_results["video_evaluation"],
                transcript_evaluation=eval_results["transcript_evaluation"],
            )
            crud.update_assessment_status(db, assessment_id, AssessmentStatusEnum.COMPLETED)

        except Exception:
            crud.update_assessment_status(db, assessment_id, AssessmentStatusEnum.FAILED)
            raise

        finally:
            db.close()

    @staticmethod
    def cancel_assessment(db: Any, assessment_id: int) -> Dict[str, Any]:
        """
        Workflow: Cancel Assessment
        1. crud   → fetch assessment record
        2. engine → validate CANCEL operation and build payload
        3. crud   → persist FAILED status
        """
        # 1. DB: Fetch assessment record
        assessment_orm = crud.get_assessment_by_id(db, assessment_id)
        if not assessment_orm:
            raise ValueError(f"Assessment ID {assessment_id} not found.")

        # 2. Engine: Validate cancel operation and build response payload
        cancel_response = AssessmentEngine.cancel_assessment(assessment_orm)

        # 3. DB: Persist status change
        crud.update_assessment_status(db, assessment_id, AssessmentStatusEnum.FAILED)

        return cancel_response

    @staticmethod
    def get_assessment_details(db: Any, assessment_id: int) -> Optional[Dict[str, Any]]:
        """
        Workflow: Get Assessment Details
        1. crud   → fetch assessment record + submitted data
        2. engine → build and return details response payload
        """
        # 1. DB: Fetch record and data
        assessment_orm = crud.get_assessment_by_id(db, assessment_id)
        if not assessment_orm:
            return None
        data_orm = crud.get_assessment_data(db, assessment_id)

        # 2. Engine: Build details response payload
        return AssessmentEngine.get_assessment_details(
            assessment_orm=assessment_orm,
            data_orm=data_orm,
        )

    @staticmethod
    def get_assessment_report(db: Any, assessment_id: int) -> Optional[Dict[str, Any]]:
        """
        Workflow: Get Assessment Report
        1. crud   → fetch evaluation report record
        2. engine → build and return report response payload
        """
        # 1. DB: Fetch report record
        report_orm = crud.get_assessment_report_by_assessment_id(db, assessment_id)
        if not report_orm:
            return None

        # 2. Engine: Build report response payload
        return AssessmentEngine.get_assessment_report(report_orm)

    # ─── BE2 Media Ingestion & YouTube Upload Coordination ────────────────────

    def __init__(self):
        self.storage_service = storage_service
        self.media_service = media_service

    def handle_chunk_upload(
        self,
        candidate_id: int,
        assessment_id: int,
        chunk_number: int,
        file_bytes: bytes,
        total_chunks: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Saves media chunk to local server storage."""
        chunk_path, file_size = storage_service.save_chunk(
            candidate_id=candidate_id,
            assessment_id=assessment_id,
            chunk_number=chunk_number,
            file_bytes=file_bytes,
        )
        return {
            "chunk_number": chunk_number,
            "status": "uploaded",
            "storage_path": chunk_path,
            "total_chunks": total_chunks,
        }

    def get_chunk_status(
        self,
        candidate_id: int,
        assessment_id: int,
        expected_total: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Returns uploaded and missing chunk numbers for resume/retry logic."""
        return storage_service.get_chunk_status(candidate_id, assessment_id, expected_total=expected_total)

    def assemble_and_process_media(
        self,
        db: Any,
        candidate_id: int,
        assessment_id: int,
        total_chunks: int,
        background_tasks: Optional[Any] = None,
    ) -> Any:
        """Assembles chunks, extracts audio, records media file, and dispatches processing."""
        return media_service.assemble_and_process_media(
            db=db,
            candidate_id=candidate_id,
            assessment_id=assessment_id,
            total_chunks=total_chunks,
            background_tasks=background_tasks,
        )

    def execute_media_pipeline(
        self,
        assessment_id: int,
        local_video_path: str,
        local_audio_path: str,
    ) -> None:
        """Executes full media pipeline: task logging, upload, cleanup."""
        media_service.execute_media_pipeline(
            assessment_id=assessment_id,
            local_video_path=local_video_path,
            local_audio_path=local_audio_path,
        )

    def upload_to_youtube(self, assessment_id: int, video_path: str) -> Optional[str]:
        """Direct upload of assembled video to YouTube with quota rotation."""
        return youtube_service.upload_video(assessment_id, video_path)


assessment_orchestrator = AssessmentOrchestrator()
