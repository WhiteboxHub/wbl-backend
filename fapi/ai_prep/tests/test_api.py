"""
API Route Tests for AI Prep Platform.
Validates FastAPI router endpoints by calling route handlers directly.
"""

import sys
import unittest
from unittest.mock import MagicMock

# Mock multipart installation check for test environment
import fastapi.dependencies.utils
fastapi.dependencies.utils.ensure_multipart_is_installed = lambda: None

# Mock sqlalchemy and db modules BEFORE importing router
mock_sqla = MagicMock()
for mod in [
    "sqlalchemy",
    "sqlalchemy.orm",
    "sqlalchemy.dialects",
    "sqlalchemy.dialects.mysql",
    "sqlalchemy.exc",
    "pymysql",
]:
    sys.modules.setdefault(mod, mock_sqla)

sys.modules.setdefault("fapi.db.database", MagicMock())
sys.modules.setdefault("fapi.db.models", MagicMock())
sys.modules.setdefault("fapi.ai_prep.models", MagicMock())

import fapi.ai_prep
mock_crud = MagicMock()
sys.modules["fapi.ai_prep.crud"] = mock_crud
fapi.ai_prep.crud = mock_crud

# Mock fapi.ai_prep.models to avoid sqlalchemy dialect imports
sys.modules.setdefault("fapi.ai_prep.models", MagicMock())

import fastapi.dependencies.utils
fastapi.dependencies.utils.ensure_multipart_is_installed = lambda: None

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fapi.ai_prep import dependencies
from fapi.ai_prep.dependencies import get_db, get_current_candidate_id

from fapi.ai_prep.schemas import (
    CreateAssessmentRequest,
    SubmitAssessmentDataRequest,
    QuestionBankCreateRequest,
    QuestionBankUpdateRequest,
    AssessmentStatusEnum,
    AssessmentCategoryEnum,
    MediaTypeEnum,
    DifficultyLevelEnum,
)
from fapi.ai_prep.router import router
import fapi.ai_prep.router
fapi.ai_prep.router.crud = mock_crud


app = FastAPI()
app.include_router(router)


def override_get_db():
    return MagicMock()


def override_get_current_candidate_id():
    return 42


def override_get_authenticated_user_context():
    return {
        "user_id": 42,
        "uname": "testcandidate@example.com",
        "role": "candidate",
        "is_employee": False,
        "is_admin": False,
        "candidate_id": 42,
    }


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_candidate_id] = override_get_current_candidate_id
app.dependency_overrides[dependencies.get_authenticated_user_context] = override_get_authenticated_user_context

client = TestClient(app)


class DummyAssessmentORM:

    def __init__(self, id=101, candidate_id=42):
        self.id = id
        self.candidate_id = candidate_id
        self.assessment_type = AssessmentCategoryEnum.INTRO
        self.media_type = MediaTypeEnum.VIDEO
        self.status = AssessmentStatusEnum.IN_PROGRESS
        self.job_description = "AI Engineer"
        self.youtube_url = None
        self.started_at = None
        self.completed_at = None


class DummyQuestionORM:
    def __init__(self, id=1):
        self.id = id
        self.category = AssessmentCategoryEnum.TECHNICAL
        self.sub_category = "RAG"
        self.difficulty_level = DifficultyLevelEnum.MEDIUM
        self.question_text = "Explain RAG search."
        self.is_active = True
        self.created_at = None
        self.updated_at = None


class TestApiRoutes(unittest.TestCase):

    def setUp(self):
        mock_crud.reset_mock()
        mock_crud.create_assessment.side_effect = lambda *args, **kwargs: DummyAssessmentORM()
        mock_crud.get_assessment_by_id.side_effect = lambda db, id: DummyAssessmentORM(id) if id != 999 else None
        mock_crud.get_candidate_resume_json.return_value = {"skills": ["Python", "FastAPI"]}
        mock_crud.list_questions_by_category.return_value = []

    def test_get_assessment_types_endpoint(self):
        response = client.get("/api/aiprep/assessment-types")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(data["total"], 6)
        types = [item["type"] for item in data["items"]]
        self.assertIn("INTRO", types)
        self.assertIn("TECHNICAL", types)
        self.assertIn("SYSTEM_DESIGN", types)

    def test_candidate_llm_status_endpoint(self):
        response = client.get("/api/aiprep/candidate/llm-status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["candidate_id"], 42)

    def test_candidate_resume_status_endpoint(self):
        response = client.get("/api/aiprep/candidate/resume-status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["candidate_id"], 42)
        self.assertTrue(data["has_resume"])
        self.assertEqual(data["status"], "VALID")

    def test_candidate_forbidden_on_other_candidate_status(self):
        response = client.get("/api/aiprep/candidate/resume-status?candidate_id=999")
        self.assertEqual(response.status_code, 403)

    def test_create_assessment_endpoint_success(self):
        fapi.ai_prep.router.assessment_orchestrator.start_assessment = MagicMock(return_value={
            "id": 101,
            "candidate_id": 42,
            "assessment_type": "INTRO",
            "media_type": "VIDEO",
            "status": "IN_PROGRESS",
            "started_at": None,
            "questions": [{"id": 1, "question_text": "Tell me about yourself"}],
        })

        payload = {
            "candidate_id": 42,
            "assessment_type": "INTRO",
            "media_type": "VIDEO",
            "job_description": "AI Engineer",
        }

        response = client.post("/api/aiprep/assessments", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["id"], 101)
        self.assertEqual(data["assessment_type"], "INTRO")

    def test_create_assessment_missing_llm_key_error(self):
        from fapi.ai_prep.exceptions import LLMKeyMissingError
        fapi.ai_prep.router.assessment_orchestrator.start_assessment = MagicMock(
            side_effect=LLMKeyMissingError()
        )

        payload = {
            "candidate_id": 42,
            "assessment_type": "INTRO",
            "media_type": "VIDEO",
        }
        response = client.post("/api/aiprep/assessments", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("LLM_KEY_NOT_CONFIGURED", response.text)

    def test_create_assessment_missing_resume_error(self):
        from fapi.ai_prep.exceptions import ResumeMissingError
        fapi.ai_prep.router.assessment_orchestrator.start_assessment = MagicMock(
            side_effect=ResumeMissingError()
        )

        payload = {
            "candidate_id": 42,
            "assessment_type": "INTRO",
            "media_type": "VIDEO",
        }
        response = client.post("/api/aiprep/assessments", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("RESUME_NOT_FOUND", response.text)

    def test_submit_assessment_endpoint(self):
        fapi.ai_prep.router.assessment_orchestrator.submit_assessment = MagicMock(return_value={
            "assessment_id": 101,
            "status": "COMPLETED",
            "message": "Assessment evaluation completed successfully.",
            "report": {"audio_evaluation": {}, "video_evaluation": {}, "transcript_evaluation": {}}
        })

        payload = {
            "questions": [{"id": 1}],
            "transcript": {"text": "My background in AI..."},
            "audio_telemetry": {"words_per_minute": 130},
            "video_telemetry": {"is_video_mode": True},
        }

        response = client.post("/api/aiprep/assessments/101/submit", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["assessment_id"], 101)
        self.assertEqual(data["status"], "COMPLETED")

    def test_submit_data_endpoint(self):
        payload = {
            "questions": [],
            "transcript": {},
            "audio_telemetry": {},
            "video_telemetry": {},
        }

        result = api_router.submit_data(
            id=101,
            payload=payload,
            db=MagicMock(),
        )
        self.assertEqual(result["message"], "Data saved successfully")

    def test_list_candidate_assessments_handler(self):
        result = api_router.list_candidate_assessments(
            candidate_id=42,
            current_candidate_id=42,
            limit=50,
            offset=0,
            db=MagicMock(),
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(len(result["items"]), 1)

    def test_list_questions_handler(self):
        result = api_router.list_questions(
            category=AssessmentCategoryEnum.TECHNICAL,
            difficulty_level=DifficultyLevelEnum.MEDIUM,
            is_active=True,
            limit=100,
            offset=0,
            db=MagicMock(),
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(len(result["items"]), 1)

    def test_create_question_handler(self):
        payload = QuestionBankCreateRequest(
            category=AssessmentCategoryEnum.TECHNICAL,
            sub_category="RAG",
            difficulty_level=DifficultyLevelEnum.MEDIUM,
            question_text="Explain RAG search.",
            is_active=True,
        )

        result = api_router.create_question(
            payload=payload,
            db=MagicMock(),
        )
        self.assertEqual(result.id, 1)


if __name__ == "__main__":
    unittest.main()

