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


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_candidate_id] = override_get_current_candidate_id
client = TestClient(app)


class DummyAssessmentORM:
    def __init__(self, id=101):
        self.id = id
        self.candidate_id = 42
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
        mock_crud.list_candidate_assessments.return_value = [DummyAssessmentORM(101)]
        mock_crud.list_questions.return_value = [DummyQuestionORM(1)]
        mock_crud.create_question.side_effect = lambda *args, **kwargs: DummyQuestionORM(1)

    def test_create_assessment_handler(self):
        payload = CreateAssessmentRequest(
            candidate_id=42,
            assessment_type=AssessmentCategoryEnum.INTRO,
            media_type=MediaTypeEnum.VIDEO,
            job_description="AI Engineer",
        )
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.return_value = "pytest"

        result = api_router.create_assessment(
            payload=payload,
            request=mock_request,
            candidate_id=42,
            db=MagicMock(),
        )
        self.assertEqual(result.id, 101)
        self.assertEqual(result.candidate_id, 42)

    def test_submit_data_handler(self):
        payload = SubmitAssessmentDataRequest(
            questions=[],
            transcript={},
            audio_telemetry={},
            video_telemetry={},
        )

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
