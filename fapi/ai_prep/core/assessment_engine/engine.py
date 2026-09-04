"""
Assessment Engine (Core Engine 1) Implementation.
Pure workflow state machine and business logic component.
ZERO Database access, ZERO API calls, ZERO external service side effects.
"""

from typing import Optional, List, Dict, Any
from fapi.ai_prep.schemas import (
    AssessmentStatusEnum,
    AssessmentEngineInput,
    AssessmentEngineOutput,
)
from fapi.ai_prep.core.assessment_engine.rules import (
    validate_operation_transition,
    validate_evaluation_transition,
    select_question_non_repeating,
)


class AssessmentEngine:
    """
    Core Engine 1: Pure Assessment State Machine.
    Evaluates assessment operations (START, SUBMIT, CANCEL), status transitions,
    and question selection logic cleanly in memory.
    """

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
        Handles transition during background evaluation completion/failure.
        Transitions EVALUATING -> COMPLETED (if success) or FAILED (if failure).
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

    @staticmethod
    def select_next_question(
        eligible_questions: List[Dict[str, Any]], used_question_ids: List[int]
    ) -> Optional[Dict[str, Any]]:
        """
        Selects the next eligible question ensuring non-repetition rules.
        """
        return select_question_non_repeating(eligible_questions, used_question_ids)
