"""
Assessment Orchestrator Implementation for AI Prep Platform.
The central workflow coordinator ('brain of the system').
Coordinates DB persistence (crud.py), state machine validation (AssessmentEngine),
and execution of evaluation pipeline engines.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, TYPE_CHECKING
import asyncio

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from fapi.ai_prep.schemas import (
    AssessmentCategoryEnum,
    MediaTypeEnum,
    AssessmentStatusEnum,
    EngineOperationEnum,
)
from fapi.ai_prep.core.assessment_engine import (
    AssessmentEngine,
    AssessmentEngineInput,
    AssessmentStateInput,
)


class AssessmentOrchestrator:
    """
    Assessment Orchestrator (Workflow Coordinator).
    Translates API request intents into database actions, state machine checks,
    question selections, and core engine invocations.
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
        1. Creates new assessment record in DB via crud.create_assessment.
        2. Validates start operation via AssessmentEngine.
        3. Retrieves questions from question bank using non-repetition rules.
        """
        from fapi.ai_prep import crud

        # 1. Create DB record
        assessment_orm = crud.create_assessment(
            db=db,
            candidate_id=candidate_id,
            assessment_type=assessment_type,
            media_type=media_type,
            job_description=job_description,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # 2. Validate start operation with AssessmentEngine
        engine_input = AssessmentEngineInput(
            assessment=AssessmentStateInput(
                assessment_id=assessment_orm.id,
                candidate_id=assessment_orm.candidate_id,
                assessment_type=assessment_orm.assessment_type,
                media_type=assessment_orm.media_type,
                status=assessment_orm.status,
                job_description=assessment_orm.job_description,
            ),
            operation=EngineOperationEnum.START,
        )
        engine_result = AssessmentEngine.execute_operation(engine_input)
        if not engine_result.success:
            raise ValueError(f"Assessment start rejected: {engine_result.error.message}")

        # 3. Select questions for this assessment
        eligible_questions = crud.list_questions_by_category(db, category=assessment_type)
        question_dicts = [
            {
                "id": q.id,
                "category": q.category.value if hasattr(q.category, "value") else str(q.category),
                "difficulty_level": q.difficulty_level.value if hasattr(q.difficulty_level, "value") else str(q.difficulty_level),
                "question_text": q.question_text,
            }
            for q in eligible_questions
        ]

        # For INTRO / JD_INTRO assessments, select exactly 1 question ("Tell me about yourself")
        selected_questions = []
        used_ids = []
        for _ in range(min(1, len(question_dicts))):
            next_q = AssessmentEngine.select_next_question(question_dicts, used_ids)
            if next_q and next_q["id"] not in used_ids:
                selected_questions.append(next_q)
                used_ids.append(next_q["id"])

        return {
            "id": assessment_orm.id,
            "candidate_id": assessment_orm.candidate_id,
            "assessment_type": assessment_orm.assessment_type.value if hasattr(assessment_orm.assessment_type, "value") else str(assessment_orm.assessment_type),
            "media_type": assessment_orm.media_type.value if hasattr(assessment_orm.media_type, "value") else str(assessment_orm.media_type),
            "status": assessment_orm.status.value if hasattr(assessment_orm.status, "value") else str(assessment_orm.status),
            "started_at": assessment_orm.started_at.isoformat() if getattr(assessment_orm, "started_at", None) else None,
            "questions": selected_questions,
        }

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
        1. Retrieves assessment record from DB.
        2. Validates SUBMIT operation with AssessmentEngine (must be IN_PROGRESS).
        3. Updates status to EVALUATING and saves submitted data (telemetry/transcript).
        4. Runs evaluation pipeline (or builds default report structure).
        5. Saves report to DB and transitions status to COMPLETED (or FAILED on error).
        """
        from fapi.ai_prep import crud

        assessment_orm = crud.get_assessment_by_id(db, assessment_id)
        if not assessment_orm:
            raise ValueError(f"Assessment ID {assessment_id} not found.")

        # 1. State machine transition check
        engine_input = AssessmentEngineInput(
            assessment=AssessmentStateInput(
                assessment_id=assessment_orm.id,
                candidate_id=assessment_orm.candidate_id,
                assessment_type=assessment_orm.assessment_type,
                media_type=assessment_orm.media_type,
                status=assessment_orm.status,
            ),
            operation=EngineOperationEnum.SUBMIT,
        )
        engine_result = AssessmentEngine.execute_operation(engine_input)
        if not engine_result.success:
            raise ValueError(f"Submission rejected: {engine_result.error.message}")

        # 2. Update status to EVALUATING
        crud.update_assessment_status(db, assessment_id, AssessmentStatusEnum.EVALUATING)

        # 3. Save submitted data payload
        crud.save_assessment_data(
            db=db,
            assessment_id=assessment_id,
            questions=questions,
            transcript=transcript,
            audio_telemetry=audio_telemetry,
            video_telemetry=video_telemetry,
        )

        try:
            # 4. Fetch candidate LLM config (key + provider + model) from DB
            from fapi.ai_prep.orchestrator import llm_orchestrator

            candidate_id: int = assessment_orm.candidate_id
            assessment_type_str: str = (
                assessment_orm.assessment_type.value
                if hasattr(assessment_orm.assessment_type, "value")
                else str(assessment_orm.assessment_type)
            )
            transcript_text: str = transcript.get("text", "") if isinstance(transcript, dict) else str(transcript)

            llm_config = llm_orchestrator.get_candidate_llm_config(db, candidate_id)

            # Fetch candidate resume JSON (career reference for transcript prompt)
            resume_json = crud.get_candidate_resume_json(db, candidate_id)

            # 5. Run concurrent LLM evaluation pipeline (async → sync bridge)
            eval_results = asyncio.run(
                llm_orchestrator.run_evaluation(
                    candidate_id=candidate_id,
                    assessment_type=assessment_type_str,
                    transcript_text=transcript_text,
                    audio_telemetry=audio_telemetry,
                    video_telemetry=video_telemetry,
                    resume_json=resume_json,
                    llm_config=llm_config,
                    db=db,
                )
            )

            transcript_eval = eval_results["transcript_evaluation"]
            audio_eval = eval_results["audio_evaluation"]
            video_eval = eval_results["video_evaluation"]

            # 6. Save report to DB
            crud.save_assessment_report(
                db=db,
                assessment_id=assessment_id,
                audio_evaluation=audio_eval,
                video_evaluation=video_eval,
                transcript_evaluation=transcript_eval,
            )

            # 7. Transition to COMPLETED
            AssessmentEngine.transition_evaluation_status(
                assessment_id=assessment_id,
                current_status=AssessmentStatusEnum.EVALUATING,
                success=True,
            )
            crud.update_assessment_status(db, assessment_id, AssessmentStatusEnum.COMPLETED)

            return {
                "assessment_id": assessment_id,
                "status": AssessmentStatusEnum.COMPLETED.value,
                "message": "Assessment evaluation completed successfully.",
            }

        except Exception as err:
            # Transition to FAILED on any evaluation error
            AssessmentEngine.transition_evaluation_status(
                assessment_id=assessment_id,
                current_status=AssessmentStatusEnum.EVALUATING,
                success=False,
            )
            crud.update_assessment_status(db, assessment_id, AssessmentStatusEnum.FAILED)
            raise
    
    def process_assessment_evaluation(self, assessment_id: int) -> None:
        """Background task creating its own DB session to run evaluation pipeline."""
        import asyncio
        from fapi.db.database import SessionLocal
        from fapi.ai_prep import crud
        from fapi.ai_prep.orchestrator import llm_orchestrator

        db = SessionLocal()
        try:
            data_orm = crud.get_assessment_data(db, assessment_id)
            questions = data_orm.questions if data_orm and data_orm.questions else []
            transcript = data_orm.transcript if data_orm and data_orm.transcript else {}
            audio_telemetry = data_orm.audio_telemetry if data_orm and data_orm.audio_telemetry else {}
            video_telemetry = data_orm.video_telemetry if data_orm and data_orm.video_telemetry else {}

            # Retrieve assessment record to get candidate_id and assessment_type
            assessment_orm = crud.get_assessment_by_id(db, assessment_id)
            if not assessment_orm:
                raise ValueError(f"Assessment ID {assessment_id} not found in background task.")

            candidate_id: int = assessment_orm.candidate_id
            assessment_type_str: str = (
                assessment_orm.assessment_type.value
                if hasattr(assessment_orm.assessment_type, "value")
                else str(assessment_orm.assessment_type)
            )
            # TranscriptDataContract stores spoken text under "full_text"
            transcript_text: str = (
                transcript.get("full_text", transcript.get("text", ""))
                if isinstance(transcript, dict)
                else str(transcript)
            )

            # Fetch LLM config (key + provider + model) from DB
            llm_config = llm_orchestrator.get_candidate_llm_config(db, candidate_id)

            # Fetch candidate resume JSON (career reference for transcript prompt)
            resume_json = crud.get_candidate_resume_json(db, candidate_id)

            # Run concurrent LLM evaluation pipeline (async → sync bridge)
            eval_results = asyncio.run(
                llm_orchestrator.run_evaluation(
                    candidate_id=candidate_id,
                    assessment_type=assessment_type_str,
                    transcript_text=transcript_text,
                    audio_telemetry=audio_telemetry,
                    video_telemetry=video_telemetry,
                    resume_json=resume_json,
                    llm_config=llm_config,
                    db=db,
                )
            )

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
        Validates cancellation with AssessmentEngine and updates status to FAILED.
        """
        from fapi.ai_prep import crud

        assessment_orm = crud.get_assessment_by_id(db, assessment_id)
        if not assessment_orm:
            raise ValueError(f"Assessment ID {assessment_id} not found.")

        engine_input = AssessmentEngineInput(
            assessment=AssessmentStateInput(
                assessment_id=assessment_orm.id,
                candidate_id=assessment_orm.candidate_id,
                assessment_type=assessment_orm.assessment_type,
                media_type=assessment_orm.media_type,
                status=assessment_orm.status,
            ),
            operation=EngineOperationEnum.CANCEL,
        )
        engine_result = AssessmentEngine.execute_operation(engine_input)
        if not engine_result.success:
            raise ValueError(f"Cancellation rejected: {engine_result.error.message}")

        crud.update_assessment_status(db, assessment_id, AssessmentStatusEnum.FAILED)

        return {
            "assessment_id": assessment_id,
            "status": AssessmentStatusEnum.FAILED.value,
            "message": "Assessment cancelled successfully.",
        }

    @staticmethod
    def get_assessment_details(db: Any, assessment_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves assessment metadata and submitted telemetry data.
        """
        from fapi.ai_prep import crud

        assessment_orm = crud.get_assessment_by_id(db, assessment_id)
        if not assessment_orm:
            return None

        data_orm = crud.get_assessment_data(db, assessment_id)

        return {
            "id": assessment_orm.id,
            "candidate_id": assessment_orm.candidate_id,
            "assessment_type": assessment_orm.assessment_type.value if hasattr(assessment_orm.assessment_type, "value") else str(assessment_orm.assessment_type),
            "media_type": assessment_orm.media_type.value if hasattr(assessment_orm.media_type, "value") else str(assessment_orm.media_type),
            "status": assessment_orm.status.value if hasattr(assessment_orm.status, "value") else str(assessment_orm.status),
            "job_description": assessment_orm.job_description,
            "youtube_url": assessment_orm.youtube_url,
            "started_at": assessment_orm.started_at.isoformat() if getattr(assessment_orm, "started_at", None) else None,
            "completed_at": assessment_orm.completed_at.isoformat() if getattr(assessment_orm, "completed_at", None) else None,
            "submitted_data": {
                "questions": data_orm.questions if data_orm else None,
                "transcript": data_orm.transcript if data_orm else None,
                "audio_telemetry": data_orm.audio_telemetry if data_orm else None,
                "video_telemetry": data_orm.video_telemetry if data_orm else None,
            }
            if data_orm
            else None,
        }

    @staticmethod
    def get_assessment_report(db: Any, assessment_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves evaluation report for a completed assessment.
        """
        from fapi.ai_prep import crud

        report_orm = crud.get_assessment_report(db, assessment_id)
        if not report_orm:
            return None

        return {
            "id": report_orm.id,
            "assessment_id": report_orm.assessment_id,
            "audio_evaluation": report_orm.audio_evaluation,
            "video_evaluation": report_orm.video_evaluation,
            "transcript_evaluation": report_orm.transcript_evaluation,
            "created_at": report_orm.created_at.isoformat() if getattr(report_orm, "created_at", None) else None,
        }
