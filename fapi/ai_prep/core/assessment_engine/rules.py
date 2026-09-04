"""
Business Rules and State Transition Validation for Assessment Engine (Core Engine 1).
Pure business logic implementation — NO side effects, NO DB calls.
"""

from typing import Optional, List, Dict, Any, Tuple
from fapi.ai_prep.schemas import (
    AssessmentStatusEnum,
    EngineOperationEnum,
    AssessmentEngineError,
)


STATUS_TRANSITION_MAP = {
    EngineOperationEnum.START: {
        "allowed_from": [AssessmentStatusEnum.IN_PROGRESS],
        "target": AssessmentStatusEnum.IN_PROGRESS,
    },
    EngineOperationEnum.SUBMIT: {
        "allowed_from": [AssessmentStatusEnum.IN_PROGRESS],
        "target": AssessmentStatusEnum.EVALUATING,
    },
    EngineOperationEnum.CANCEL: {
        "allowed_from": [AssessmentStatusEnum.IN_PROGRESS],
        "target": AssessmentStatusEnum.FAILED,
    },
}

TERMINAL_STATUSES = {AssessmentStatusEnum.COMPLETED, AssessmentStatusEnum.FAILED}


def validate_operation_transition(
    current_status: AssessmentStatusEnum, operation: EngineOperationEnum
) -> Tuple[bool, Optional[AssessmentStatusEnum], Optional[AssessmentEngineError]]:
    """
    Validates if an operation (START, SUBMIT, CANCEL) is allowed from current_status.
    Returns (is_valid, target_status, error).
    """
    if current_status in TERMINAL_STATUSES:
        return (
            False,
            None,
            AssessmentEngineError(
                code="ALREADY_TERMINATED",
                message=f"Assessment is already in terminal state '{current_status.value}' and cannot execute '{operation.value}'.",
            ),
        )

    rule = STATUS_TRANSITION_MAP.get(operation)
    if not rule:
        return (
            False,
            None,
            AssessmentEngineError(
                code="INVALID_OPERATION",
                message=f"Operation '{operation.value}' is not recognized.",
            ),
        )

    if current_status not in rule["allowed_from"]:
        allowed_str = ", ".join(s.value for s in rule["allowed_from"])
        return (
            False,
            None,
            AssessmentEngineError(
                code="INVALID_STATUS_TRANSITION",
                message=f"Operation '{operation.value}' requires status to be in [{allowed_str}], but current status is '{current_status.value}'.",
            ),
        )

    return True, rule["target"], None


def validate_evaluation_transition(
    current_status: AssessmentStatusEnum, success: bool
) -> Tuple[bool, Optional[AssessmentStatusEnum], Optional[AssessmentEngineError]]:
    """
    Validates transition from EVALUATING -> COMPLETED (if success) or FAILED (if failure).
    """
    if current_status != AssessmentStatusEnum.EVALUATING:
        return (
            False,
            None,
            AssessmentEngineError(
                code="INVALID_STATUS_TRANSITION",
                message=f"Evaluation transition requires current status 'EVALUATING', but status is '{current_status.value}'.",
            ),
        )

    target_status = AssessmentStatusEnum.COMPLETED if success else AssessmentStatusEnum.FAILED
    return True, target_status, None


def select_question_non_repeating(
    eligible_questions: List[Dict[str, Any]], used_question_ids: List[int]
) -> Optional[Dict[str, Any]]:
    """
    Pure question selection logic.
    Selects the first question from eligible_questions whose ID is not in used_question_ids.
    If all eligible questions have been used, resets pool and selects the first question.
    """
    if not eligible_questions:
        return None

    used_set = set(used_question_ids)
    unused_questions = [q for q in eligible_questions if q.get("id") not in used_set]

    if unused_questions:
        return unused_questions[0]

    return eligible_questions[0]
