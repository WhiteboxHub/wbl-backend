"""
Assessment Engine (Core Engine 1) Implementation.
Pure workflow state machine, business logic, and data transformation component.
ZERO Database access, ZERO API calls, ZERO external service side effects.

All assessment business logic lives here:
  - Pre-flight validation (LLM API key & Candidate Resume checks)
  - Workflow business operations (start, submit, cancel, evaluation data prep, details, report)
  - State machine transitions (START / SUBMIT / CANCEL / EVALUATE)
  - Question selection and non-repetition rules
  - ORM -> dict conversion
  - Response payload construction
  - Transcript text extraction

The orchestrator is a thin coordinator that calls these methods and handles persistence.
"""

from typing import Optional, List, Dict, Any

from fapi.ai_prep.schemas import (
    AssessmentCategoryEnum,
    MediaTypeEnum,
    AssessmentStatusEnum,
    AssessmentEngineInput,
    AssessmentEngineOutput,
    AssessmentStateInput,
    EngineOperationEnum,
)
from fapi.ai_prep.exceptions import (
    LLMKeyMissingError,
    ResumeMissingError,
    AssessmentOperationError,
)
from fapi.ai_prep.core.assessment_engine.rules import (
    validate_operation_transition,
    validate_evaluation_transition,
    select_question_non_repeating,
)


class AssessmentEngine:
    """
    Core Engine 1: Pure Assessment State Machine and Business Logic.

    Responsibilities:
      1. Pre-flight checks (LLM Key & Resume existence)
      2. Workflow business operations (start_assessment, submit_assessment, process_assessment_evaluation, cancel_assessment, get_assessment_details, get_assessment_report)
      3. Validate state machine operations (START, SUBMIT, CANCEL, EVALUATE)
      4. Select questions for a session using non-repetition rules
      5. Convert ORM objects to plain dicts (no DB dependency)
      6. Build all API response payloads
      7. Extract transcript text from various input shapes

    All methods are @staticmethod because this engine holds no instance state.
    It is a pure transformation layer — same inputs always produce same outputs.
    """

    # ─── 1. Pre-flight Checks & Workflow Business Logic Operations ───────────────

    @staticmethod
    def validate_preflight(has_active_key: bool, has_resume: bool) -> None:
        """
        Validates pre-flight conditions before allowing assessment creation:
          - Active LLM API key must exist
          - Candidate resume must exist and be parsed
        """
        if not has_active_key:
            raise LLMKeyMissingError()
        if not has_resume:
            raise ResumeMissingError()

    @staticmethod
    def start_assessment(
        assessment_orm: Any,
        eligible_questions: List[Any],
    ) -> Dict[str, Any]:
        """
        Engine logic for Start Assessment workflow:
          1. Validate state transition to START.
          2. Convert eligible question ORMs to plain dicts.
          3. Select question(s) dynamically based on category and eligible pool.
          4. Construct and return response payload.
        """
        return AssessmentEngine.process_start_assessment(
            assessment_orm=assessment_orm,
            eligible_questions=eligible_questions,
        )

    @staticmethod
    def process_start_assessment(
        assessment_orm: Any,
        eligible_questions: List[Any],
    ) -> Dict[str, Any]:
        """
        Processes Start Assessment workflow validation, question selection, and response formatting.
        """
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
            raise AssessmentOperationError(
                f"Assessment start rejected: {engine_result.error.message if engine_result.error else 'Invalid state'}"
            )

        question_dicts = AssessmentEngine.orm_to_question_dicts(eligible_questions)

        # Select target number of questions based on assessment type
        assessment_type = assessment_orm.assessment_type
        target_count = (
            1
            if assessment_type in (AssessmentCategoryEnum.INTRO, AssessmentCategoryEnum.JD_INTRO)
            else len(question_dicts)
        )
        selected_questions = AssessmentEngine.select_questions_for_session(
            question_dicts, max_questions=target_count
        )

        return AssessmentEngine.build_start_response(assessment_orm, selected_questions)

    @staticmethod
    def submit_assessment(
        assessment_orm: Any,
        transcript: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Engine logic for Submit Assessment validation and data extraction.
        """
        return AssessmentEngine.validate_and_prepare_submission(
            assessment_orm=assessment_orm,
            transcript=transcript,
        )

    @staticmethod
    def validate_and_prepare_submission(
        assessment_orm: Any,
        transcript: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Engine logic for Submit Assessment validation and data extraction:
          1. Validate state transition to SUBMIT.
          2. Extract transcript plain text and assessment type string.
        """
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

        transcript_text = AssessmentEngine.extract_transcript_text(transcript)
        assessment_type_str = (
            assessment_orm.assessment_type.value
            if hasattr(assessment_orm.assessment_type, "value")
            else str(assessment_orm.assessment_type)
        )

        return {
            "transcript_text": transcript_text,
            "assessment_type_str": assessment_type_str,
        }

    @staticmethod
    def build_completion_response(assessment_id: int) -> Dict[str, Any]:
        """
        Builds submission completion payload.
        """
        return {
            "assessment_id": assessment_id,
            "status": AssessmentStatusEnum.COMPLETED.value,
            "message": "Assessment evaluation completed successfully.",
        }

    @staticmethod
    def process_assessment_evaluation(
        assessment_orm: Any,
        data_orm: Any,
    ) -> Dict[str, Any]:
        """
        Engine logic for background task evaluation data preparation.
        """
        return AssessmentEngine.prepare_background_evaluation_data(
            assessment_orm=assessment_orm,
            data_orm=data_orm,
        )

    @staticmethod
    def prepare_background_evaluation_data(
        assessment_orm: Any,
        data_orm: Any,
    ) -> Dict[str, Any]:
        """
        Engine logic for background task evaluation data preparation.
        """
        transcript = data_orm.transcript if data_orm and data_orm.transcript else {}
        audio_telemetry = data_orm.audio_telemetry if data_orm and data_orm.audio_telemetry else {}
        video_telemetry = data_orm.video_telemetry if data_orm and data_orm.video_telemetry else {}
        questions = data_orm.questions if data_orm and data_orm.questions else []

        transcript_text = AssessmentEngine.extract_transcript_text(transcript)
        assessment_type_str = (
            assessment_orm.assessment_type.value
            if hasattr(assessment_orm.assessment_type, "value")
            else str(assessment_orm.assessment_type)
        )

        return {
            "questions": questions,
            "transcript": transcript,
            "audio_telemetry": audio_telemetry,
            "video_telemetry": video_telemetry,
            "transcript_text": transcript_text,
            "assessment_type_str": assessment_type_str,
        }

    @staticmethod
    def cancel_assessment(assessment_orm: Any) -> Dict[str, Any]:
        """
        Engine logic for Cancel Assessment workflow:
          1. Validate state transition to CANCEL.
          2. Return success response payload.
        """
        return AssessmentEngine.process_cancel_assessment(assessment_orm)

    @staticmethod
    def process_cancel_assessment(assessment_orm: Any) -> Dict[str, Any]:
        """
        Engine logic for Cancel Assessment workflow.
        """
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

        return {
            "assessment_id": assessment_orm.id,
            "status": AssessmentStatusEnum.FAILED.value,
            "message": "Assessment cancelled successfully.",
        }

    @staticmethod
    def get_assessment_details(
        assessment_orm: Any,
        data_orm: Any,
    ) -> Dict[str, Any]:
        """
        Engine logic for Get Assessment Details payload.
        """
        return AssessmentEngine.build_assessment_details(assessment_orm, data_orm)

    @staticmethod
    def get_assessment_report(report_orm: Any) -> Dict[str, Any]:
        """
        Engine logic for Get Assessment Report payload.
        """
        return AssessmentEngine.build_assessment_report(report_orm)

    # ─── 2. State Machine Operations ─────────────────────────────────────────

    @staticmethod
    def execute_operation(input_data: AssessmentEngineInput) -> AssessmentEngineOutput:
        """
        Main entry point for processing an assessment operation (START, SUBMIT, CANCEL).
        Validates inputs and current state, then returns updated assessment state or error.
        """
        current_status = input_data.assessment.status
        operation = input_data.operation

        is_valid, target_status, error = validate_operation_transition(current_status, operation)
        if not is_valid or error:
            return AssessmentEngineOutput(success=False, assessment=None, error=error)

        updated_assessment = {
            "assessment_id": input_data.assessment.assessment_id,
            "candidate_id": input_data.assessment.candidate_id,
            "assessment_type": input_data.assessment.assessment_type.value,
            "media_type": input_data.assessment.media_type.value,
            "status": target_status.value if target_status else current_status.value,
            "operation_executed": operation.value,
        }

        return AssessmentEngineOutput(
            success=True,
            assessment=updated_assessment,
            error=None,
        )

    @staticmethod
    def transition_evaluation_status(
        assessment_id: int, current_status: AssessmentStatusEnum, success: bool
    ) -> AssessmentEngineOutput:
        """
        Handles transition during background evaluation completion or failure.
        Transitions: EVALUATING -> COMPLETED (success=True) or FAILED (success=False).
        """
        is_valid, target_status, error = validate_evaluation_transition(current_status, success)
        if not is_valid or error:
            return AssessmentEngineOutput(success=False, assessment=None, error=error)

        return AssessmentEngineOutput(
            success=True,
            assessment={
                "assessment_id": assessment_id,
                "status": target_status.value if target_status else current_status.value,
            },
            error=None,
        )

    # ─── 3. Question Selection Logic ──────────────────────────────────────────

    @staticmethod
    def select_next_question(
        eligible_questions: List[Dict[str, Any]], used_question_ids: List[int]
    ) -> Optional[Dict[str, Any]]:
        """
        Selects the next eligible question ensuring non-repetition rules.
        Delegates to rules.select_question_non_repeating.
        """
        return select_question_non_repeating(eligible_questions, used_question_ids)

    @staticmethod
    def select_questions_for_session(
        question_dicts: List[Dict[str, Any]],
        max_questions: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Encapsulates question selection loop for an assessment session.
        If the question bank has 0 questions, returns an empty list (safe fallback).
        """
        selected_questions: List[Dict[str, Any]] = []
        used_ids: List[int] = []

        for _ in range(min(max_questions, len(question_dicts))):
            next_q = select_question_non_repeating(question_dicts, used_ids)
            if next_q and next_q.get("id") not in used_ids:
                selected_questions.append(next_q)
                used_ids.append(next_q["id"])

        return selected_questions

    # ─── 4. ORM -> Dict Conversion ────────────────────────────────────────────

    @staticmethod
    def orm_to_question_dicts(eligible_questions: list) -> List[Dict[str, Any]]:
        """
        Converts a list of AiPrepQuestionBankORM objects into plain dicts.
        """
        return [
            {
                "id": q.id,
                "category": q.category.value if hasattr(q.category, "value") else str(q.category),
                "difficulty_level": (
                    q.difficulty_level.value
                    if hasattr(q.difficulty_level, "value")
                    else str(q.difficulty_level)
                ),
                "question_text": q.question_text,
            }
            for q in eligible_questions
        ]

    # ─── 5. Response Payload Builders ─────────────────────────────────────────

    @staticmethod
    def build_start_response(
        assessment_orm: Any,
        selected_questions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Builds the complete API response payload for a newly started assessment.
        """
        return {
            "id": assessment_orm.id,
            "candidate_id": assessment_orm.candidate_id,
            "assessment_type": (
                assessment_orm.assessment_type.value
                if hasattr(assessment_orm.assessment_type, "value")
                else str(assessment_orm.assessment_type)
            ),
            "media_type": (
                assessment_orm.media_type.value
                if hasattr(assessment_orm.media_type, "value")
                else str(assessment_orm.media_type)
            ),
            "status": (
                assessment_orm.status.value
                if hasattr(assessment_orm.status, "value")
                else str(assessment_orm.status)
            ),
            "started_at": (
                assessment_orm.started_at.isoformat()
                if getattr(assessment_orm, "started_at", None)
                else None
            ),
            "questions": selected_questions,
        }

    @staticmethod
    def build_assessment_details(
        assessment_orm: Any,
        data_orm: Any,
    ) -> Dict[str, Any]:
        """
        Builds the full assessment details payload combining:
          - Assessment metadata (from ai_prep_assessment table)
          - Submitted telemetry data (from ai_prep_assessment_data table)
        """
        return {
            "id": assessment_orm.id,
            "candidate_id": assessment_orm.candidate_id,
            "assessment_type": (
                assessment_orm.assessment_type.value
                if hasattr(assessment_orm.assessment_type, "value")
                else str(assessment_orm.assessment_type)
            ),
            "media_type": (
                assessment_orm.media_type.value
                if hasattr(assessment_orm.media_type, "value")
                else str(assessment_orm.media_type)
            ),
            "status": (
                assessment_orm.status.value
                if hasattr(assessment_orm.status, "value")
                else str(assessment_orm.status)
            ),
            "job_description": assessment_orm.job_description,
            "youtube_url": assessment_orm.youtube_url,
            "started_at": (
                assessment_orm.started_at.isoformat()
                if getattr(assessment_orm, "started_at", None)
                else None
            ),
            "completed_at": (
                assessment_orm.completed_at.isoformat()
                if getattr(assessment_orm, "completed_at", None)
                else None
            ),
            "submitted_data": (
                {
                    "questions": data_orm.questions,
                    "transcript": data_orm.transcript,
                    "audio_telemetry": data_orm.audio_telemetry,
                    "video_telemetry": data_orm.video_telemetry,
                }
                if data_orm
                else None
            ),
        }

    @staticmethod
    def build_assessment_report(report_orm: Any) -> Dict[str, Any]:
        """
        Builds the evaluation report payload from ai_prep_assessment_report table.
        """
        return {
            "id": report_orm.id,
            "assessment_id": report_orm.assessment_id,
            "audio_evaluation": report_orm.audio_evaluation,
            "video_evaluation": report_orm.video_evaluation,
            "transcript_evaluation": report_orm.transcript_evaluation,
            "created_at": (
                report_orm.created_at.isoformat()
                if getattr(report_orm, "created_at", None)
                else None
            ),
        }

    # ─── 6. Data Extraction Helpers ───────────────────────────────────────────

    @staticmethod
    def extract_transcript_text(transcript: Any) -> str:
        """
        Extracts plain spoken text from transcript dictionary.
        Supports both 'full_text' (new contract) and 'text' (legacy contract).
        """
        if isinstance(transcript, dict):
            return transcript.get("full_text", transcript.get("text", ""))
        return str(transcript) if transcript else ""
