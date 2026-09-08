"""
Unit Tests for Assessment Orchestrator.
Mocks dependencies to allow pure python execution without external system library requirements.
"""

import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from fapi.ai_prep.schemas import (
    AssessmentCategoryEnum,
    DifficultyLevelEnum,
    MediaTypeEnum,
    AssessmentStatusEnum,
)
from fapi.ai_prep.orchestrator.assessment_orchestrator import AssessmentOrchestrator


class DummyAssessmentORM:
    def __init__(self, id=101, candidate_id=42, status=AssessmentStatusEnum.IN_PROGRESS):
        self.id = id
        self.candidate_id = candidate_id
        self.assessment_type = AssessmentCategoryEnum.INTRO
        self.media_type = MediaTypeEnum.VIDEO
        self.status = status
        self.job_description = "AI Engineer role"
        self.youtube_url = None
        self.started_at = None
        self.completed_at = None


class DummyQuestionORM:
    def __init__(self, id, category, difficulty_level, question_text):
        self.id = id
        self.category = category
        self.difficulty_level = difficulty_level
        self.question_text = question_text


class DummyDataORM:
    def __init__(self):
        self.questions = [{"id": 1, "text": "Tell me about yourself"}]
        self.transcript = {"text": "Hello world"}
        self.audio_telemetry = {"speaking_pace_wpm": 140}
        self.video_telemetry = {"eye_contact_pct": 88.0}


class DummyReportORM:
    def __init__(self, assessment_id=101):
        self.id = 1
        self.assessment_id = assessment_id
        self.audio_evaluation = {"coherence": "High"}
        self.video_evaluation = {"eye_contact_pct": 88.0}
        self.transcript_evaluation = {"overall_score": 85}
        self.created_at = None


class TestAssessmentOrchestrator(unittest.TestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        self.dummy_assessment = DummyAssessmentORM()
        self.dummy_questions = [
            DummyQuestionORM(1, AssessmentCategoryEnum.INTRO, DifficultyLevelEnum.EASY, "Tell me about yourself"),
            DummyQuestionORM(2, AssessmentCategoryEnum.INTRO, DifficultyLevelEnum.MEDIUM, "Why this role?"),
        ]

    @patch("fapi.ai_prep.crud.get_candidate_resume_json")
    @patch("fapi.ai_prep.crud.list_questions_by_category")
    @patch("fapi.ai_prep.crud.create_assessment")
    def test_start_assessment_workflow(self, mock_create, mock_list_q, mock_resume):
        mock_create.return_value = self.dummy_assessment
        mock_list_q.return_value = self.dummy_questions
        mock_resume.return_value = {"skills": ["Python"]}

        result = AssessmentOrchestrator.start_assessment(
            db=self.mock_db,
            candidate_id=42,
            assessment_type=AssessmentCategoryEnum.INTRO,
            media_type=MediaTypeEnum.VIDEO,
            job_description="AI Engineer role",
        )

        self.assertEqual(result["id"], 101)
        self.assertEqual(result["candidate_id"], 42)
        self.assertEqual(result["status"], "IN_PROGRESS")
        self.assertEqual(len(result["questions"]), 1)
        mock_create.assert_called_once()

    @patch("fapi.ai_prep.crud.save_assessment_report")
    @patch("fapi.ai_prep.crud.save_assessment_data")
    @patch("fapi.ai_prep.crud.update_assessment_status")
    @patch("fapi.ai_prep.crud.get_candidate_resume_json")
    @patch("fapi.ai_prep.crud.get_assessment_by_id")
    @patch("fapi.ai_prep.orchestrator.llm_orchestrator.get_candidate_llm_config")
    @patch("fapi.ai_prep.orchestrator.llm_orchestrator.run_evaluation", new_callable=AsyncMock)
    def test_submit_assessment_workflow(
        self, mock_run_eval, mock_get_cfg, mock_get_by_id, mock_resume, mock_update_status, mock_save_data, mock_save_report
    ):
        mock_get_by_id.return_value = self.dummy_assessment
        mock_get_cfg.return_value = {"api_key": "test_key", "provider": "openai", "model": "gpt-4o"}
        mock_resume.return_value = {"skills": ["Python"]}
        mock_run_eval.return_value = {
            "transcript_evaluation": {"score": 85},
            "audio_evaluation": {"score": 90},
            "video_evaluation": {"score": 88},
        }

        submit_res = AssessmentOrchestrator.submit_assessment(
            db=self.mock_db,
            assessment_id=101,
            questions=[],
            transcript={"text": "Hello world"},
            audio_telemetry={"speaking_pace_wpm": 140},
            video_telemetry={"eye_contact_pct": 88.0},
        )

        self.assertEqual(submit_res["status"], "COMPLETED")
        mock_save_data.assert_called_once()
        mock_save_report.assert_called_once()

    @patch("fapi.ai_prep.crud.update_assessment_status")
    @patch("fapi.ai_prep.crud.get_assessment_by_id")
    def test_cancel_assessment_workflow(self, mock_get_by_id, mock_update_status):
        mock_get_by_id.return_value = self.dummy_assessment

        cancel_res = AssessmentOrchestrator.cancel_assessment(self.mock_db, 101)

        self.assertEqual(cancel_res["status"], "FAILED")
        mock_update_status.assert_called_with(self.mock_db, 101, AssessmentStatusEnum.FAILED)

    @patch("fapi.ai_prep.crud.get_assessment_by_id")
    def test_rejects_resubmit_on_completed_assessment(self, mock_get_by_id):
        completed_assessment = DummyAssessmentORM(status=AssessmentStatusEnum.COMPLETED)
        mock_get_by_id.return_value = completed_assessment

        with self.assertRaises(ValueError) as ctx:
            AssessmentOrchestrator.submit_assessment(
                db=self.mock_db,
                assessment_id=101,
                questions=[],
                transcript={},
                audio_telemetry={},
                video_telemetry={},
            )
        self.assertIn("Submission rejected", str(ctx.exception))

    @patch("fapi.ai_prep.crud.get_assessment_data")
    @patch("fapi.ai_prep.crud.get_assessment_by_id")
    def test_get_assessment_details(self, mock_get_by_id, mock_get_data):
        mock_get_by_id.return_value = self.dummy_assessment
        mock_get_data.return_value = DummyDataORM()

        details = AssessmentOrchestrator.get_assessment_details(self.mock_db, 101)

        self.assertIsNotNone(details)
        self.assertEqual(details["id"], 101)
        self.assertIsNotNone(details["submitted_data"])

    @patch("fapi.ai_prep.crud.get_assessment_report_by_assessment_id")
    def test_get_assessment_report(self, mock_get_report):
        mock_get_report.return_value = DummyReportORM(assessment_id=101)

        report = AssessmentOrchestrator.get_assessment_report(self.mock_db, 101)

        self.assertIsNotNone(report)
        self.assertEqual(report["assessment_id"], 101)
        self.assertIn("audio_evaluation", report)


if __name__ == "__main__":
    unittest.main()
