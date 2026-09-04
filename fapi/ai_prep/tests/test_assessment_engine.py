"""
Unit tests for Assessment Engine (Core Engine 1).
Validates state machine transitions, business rules, and question selection logic.
"""

import unittest
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


class TestAssessmentEngine(unittest.TestCase):

    def setUp(self):
        self.base_state = AssessmentStateInput(
            assessment_id=101,
            candidate_id=42,
            assessment_type=AssessmentCategoryEnum.INTRO,
            media_type=MediaTypeEnum.VIDEO,
            status=AssessmentStatusEnum.IN_PROGRESS,
        )

    def test_start_operation_success(self):
        inp = AssessmentEngineInput(
            assessment=self.base_state,
            operation=EngineOperationEnum.START,
        )
        res = AssessmentEngine.execute_operation(inp)
        self.assertTrue(res.success)
        self.assertIsNotNone(res.assessment)
        self.assertEqual(res.assessment["status"], "IN_PROGRESS")
        self.assertIsNone(res.error)

    def test_submit_operation_success(self):
        inp = AssessmentEngineInput(
            assessment=self.base_state,
            operation=EngineOperationEnum.SUBMIT,
        )
        res = AssessmentEngine.execute_operation(inp)
        self.assertTrue(res.success)
        self.assertEqual(res.assessment["status"], "EVALUATING")
        self.assertIsNone(res.error)

    def test_cancel_operation_success(self):
        inp = AssessmentEngineInput(
            assessment=self.base_state,
            operation=EngineOperationEnum.CANCEL,
        )
        res = AssessmentEngine.execute_operation(inp)
        self.assertTrue(res.success)
        self.assertEqual(res.assessment["status"], "FAILED")
        self.assertIsNone(res.error)

    def test_rejects_operation_on_completed_assessment(self):
        completed_state = self.base_state.model_copy(
            update={"status": AssessmentStatusEnum.COMPLETED}
        )
        inp = AssessmentEngineInput(
            assessment=completed_state,
            operation=EngineOperationEnum.SUBMIT,
        )
        res = AssessmentEngine.execute_operation(inp)
        self.assertFalse(res.success)
        self.assertIsNone(res.assessment)
        self.assertEqual(res.error.code, "ALREADY_TERMINATED")

    def test_rejects_operation_on_failed_assessment(self):
        failed_state = self.base_state.model_copy(
            update={"status": AssessmentStatusEnum.FAILED}
        )
        inp = AssessmentEngineInput(
            assessment=failed_state,
            operation=EngineOperationEnum.SUBMIT,
        )
        res = AssessmentEngine.execute_operation(inp)
        self.assertFalse(res.success)
        self.assertEqual(res.error.code, "ALREADY_TERMINATED")

    def test_rejects_submit_on_evaluating_assessment(self):
        eval_state = self.base_state.model_copy(
            update={"status": AssessmentStatusEnum.EVALUATING}
        )
        inp = AssessmentEngineInput(
            assessment=eval_state,
            operation=EngineOperationEnum.SUBMIT,
        )
        res = AssessmentEngine.execute_operation(inp)
        self.assertFalse(res.success)
        self.assertEqual(res.error.code, "INVALID_STATUS_TRANSITION")

    def test_transition_evaluation_status_success(self):
        res = AssessmentEngine.transition_evaluation_status(
            assessment_id=101,
            current_status=AssessmentStatusEnum.EVALUATING,
            success=True,
        )
        self.assertTrue(res.success)
        self.assertEqual(res.assessment["status"], "COMPLETED")

    def test_transition_evaluation_status_failure(self):
        res = AssessmentEngine.transition_evaluation_status(
            assessment_id=101,
            current_status=AssessmentStatusEnum.EVALUATING,
            success=False,
        )
        self.assertTrue(res.success)
        self.assertEqual(res.assessment["status"], "FAILED")

    def test_select_next_question_non_repeating(self):
        questions = [
            {"id": 1, "text": "Question 1"},
            {"id": 2, "text": "Question 2"},
            {"id": 3, "text": "Question 3"},
        ]
        used_ids = [1]
        selected = AssessmentEngine.select_next_question(questions, used_ids)
        self.assertEqual(selected["id"], 2)

    def test_select_next_question_rollover(self):
        questions = [
            {"id": 1, "text": "Question 1"},
            {"id": 2, "text": "Question 2"},
        ]
        used_ids = [1, 2]
        selected = AssessmentEngine.select_next_question(questions, used_ids)
        self.assertEqual(selected["id"], 1)


if __name__ == "__main__":
    unittest.main()
