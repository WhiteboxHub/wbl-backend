"""
Exhaustive API Route Handler Tests for AI Prep Platform.
Validates FastAPI router handlers directly in memory.
"""

import sys
import unittest
from unittest.mock import MagicMock

import secrets

# Mock multipart installation check for test environment
import fastapi.dependencies.utils
fastapi.dependencies.utils.ensure_multipart_is_installed = lambda: None

# Mock sqlalchemy and db modules BEFORE importing router
mock_sqla = MagicMock()
sys.modules.setdefault("jose", mock_sqla)
sys.modules.setdefault("jose.jwt", mock_sqla)
sys.modules.setdefault("dotenv", mock_sqla)
sys.modules.setdefault("fapi.core.config", MagicMock(SECRET_KEY=secrets.token_urlsafe(16), ALGORITHM="HS256"))

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
_real_crud = sys.modules.get("fapi.ai_prep.crud")
mock_crud = MagicMock()
sys.modules["fapi.ai_prep.crud"] = mock_crud
fapi.ai_prep.crud = mock_crud


def tearDownModule():
    if _real_crud is not None:
        sys.modules["fapi.ai_prep.crud"] = _real_crud
        fapi.ai_prep.crud = _real_crud

from fastapi import HTTPException
from fapi.ai_prep.schemas import (
    CreateAssessmentRequest,
    SubmitAssessmentDataRequest,
    SubmitAssessmentRequest,
    UpdateMediaUrlRequest,
    QuestionBankCreateRequest,
    QuestionBankUpdateRequest,
    AssessmentStatusEnum,
    AssessmentCategoryEnum,
    MediaTypeEnum,
    DifficultyLevelEnum,
)
from fastapi import HTTPException, FastAPI
from fastapi.testclient import TestClient
from fapi.ai_prep import router as api_router, dependencies

app = FastAPI()
app.include_router(api_router.router)


def override_get_authenticated_user_context():
    return {
        "user_id": 42,
        "uname": "test@example.com",
        "role": "candidate",
        "is_employee": False,
        "is_admin": False,
        "candidate_id": 42,
    }


def override_get_db():
    return MagicMock()


app.dependency_overrides[dependencies.get_authenticated_user_context] = override_get_authenticated_user_context
app.dependency_overrides[dependencies.get_db] = override_get_db

client = TestClient(app)


class DummyAssessmentORM:
    def __init__(self, id=101):
        self.id = id
        self.candidate_id = 42
        self.assessment_type = AssessmentCategoryEnum.INTRO
        self.media_type = MediaTypeEnum.VIDEO
        self.status = AssessmentStatusEnum.IN_PROGRESS
        self.job_description = "AI Engineer"
        self.youtube_url = "https://youtube.com/watch?v=mock"
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


class TestApiRoutesExhaustive(unittest.TestCase):

    def setUp(self):
        fapi.ai_prep.router.crud = mock_crud
        fapi.ai_prep.dependencies.crud = mock_crud
        mock_crud.reset_mock()
        mock_crud.create_assessment.side_effect = lambda *args, **kwargs: DummyAssessmentORM()
        mock_crud.get_assessment_by_id.side_effect = lambda db, id: DummyAssessmentORM(id) if id != 999 else None
        mock_crud.get_candidate_resume_json.return_value = {"skills": ["Python", "FastAPI"]}
        mock_crud.list_questions_by_category.return_value = []
        mock_crud.update_assessment_youtube_url.side_effect = lambda db, id, url: DummyAssessmentORM(id) if id != 999 else None
        mock_crud.list_candidate_assessments.return_value = [DummyAssessmentORM(101)]
        mock_crud.list_questions.return_value = [DummyQuestionORM(1)]
        mock_crud.create_question.side_effect = lambda *args, **kwargs: DummyQuestionORM(1)
        def mock_update_q(db, *args, **kwargs):
            qid = kwargs.get("question_id") or (args[0] if args else 1)
            return DummyQuestionORM(qid) if qid != 999 else None

        def mock_get_q(db, *args, **kwargs):
            qid = kwargs.get("question_id") or (args[0] if args else 1)
            return DummyQuestionORM(qid) if qid != 999 else None

        mock_crud.update_question.side_effect = mock_update_q
        mock_crud.get_question_by_id.side_effect = mock_get_q

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

    def test_employee_endpoints_forbidden_for_candidate(self):
        # Default user context in test client is candidate role -> must get 403 Forbidden
        response = client.get("/api/aiprep/employee/candidate/999/llm-status")
        self.assertEqual(response.status_code, 403)

        response_resume = client.get("/api/aiprep/employee/candidate/999/resume-status")
        self.assertEqual(response_resume.status_code, 403)

        response_list = client.get("/api/aiprep/employee/assessments")
        self.assertEqual(response_list.status_code, 403)

    def test_employee_endpoints_accessible_for_employee(self):
        def override_employee_user_context():
            return {
                "user_id": 1,
                "uname": "admin@example.com",
                "role": "admin",
                "is_employee": True,
                "is_admin": True,
                "candidate_id": 1,
            }
        app.dependency_overrides[dependencies.get_authenticated_user_context] = override_employee_user_context
        try:
            mock_crud.list_assessments_for_employee.return_value = []
            res = client.get("/api/aiprep/employee/assessments?candidate_id=42")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["total"], 0)

            res_resume = client.get("/api/aiprep/employee/candidate/42/resume-status")
            self.assertEqual(res_resume.status_code, 200)
            self.assertEqual(res_resume.json()["candidate_id"], 42)
        finally:
            app.dependency_overrides[dependencies.get_authenticated_user_context] = override_get_authenticated_user_context


    def test_create_assessment_endpoint_success(self):
        fapi.ai_prep.router.assessment_orchestrator.start_assessment = MagicMock(return_value={
            "id": 101,
            "candidate_id": 42,
            "status": "IN_PROGRESS",
            "assessment_type": "INTRO",
            "media_type": "VIDEO",
        })
        api_router.assessment_orchestrator.submit_assessment.return_value = {
            "status": "COMPLETED",
            "message": "Evaluation completed.",
            "report": {"overall_score": 85},
        }

    def test_list_assessment_types(self):
        res = api_router.list_assessment_types()
        self.assertEqual(res.total, 6)

    def test_check_candidate_llm_status(self):
        auth_ctx = {"candidate_id": 42, "is_employee": False, "is_admin": False}
        res = api_router.check_candidate_llm_status(auth_ctx=auth_ctx, db=MagicMock())
        self.assertIsNotNone(res.status)

    def test_check_candidate_resume_status(self):
        auth_ctx = {"candidate_id": 42, "is_employee": False, "is_admin": False}
        res = api_router.check_candidate_resume_status(auth_ctx=auth_ctx, db=MagicMock())
        self.assertIsNotNone(res.status)

    def test_create_assessment_handler_success(self):
        payload = CreateAssessmentRequest(
            candidate_id=42,
            assessment_type=AssessmentCategoryEnum.INTRO,
            media_type=MediaTypeEnum.VIDEO,
            job_description="AI Engineer",
        )
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.return_value = "pytest"
        auth_ctx = {"candidate_id": 42, "is_employee": False, "is_admin": False}

        result = api_router.create_assessment(
            payload=payload,
            request=mock_request,
            auth_ctx=auth_ctx,
            db=MagicMock(),
        )
        self.assertEqual(result.id, 101)

    def test_submit_assessment_handler(self):
        payload = SubmitAssessmentRequest(
            questions=[],
            transcript={"full_text": "sample"},
            audio_telemetry={"speaking_pace_wpm": 140},
            video_telemetry={},
        )
        auth_ctx = {"candidate_id": 42, "is_employee": False, "is_admin": False}
        api_router.assessment_orchestrator.submit_assessment = MagicMock(return_value={
            "assessment_id": 101,
            "status": "COMPLETED",
            "message": "Assessment evaluation completed successfully.",
        })

        result = api_router.submit_assessment(
            id=101,
            payload=payload,
            auth_ctx=auth_ctx,
            db=MagicMock(),
        )
        self.assertEqual(result.status, "COMPLETED")

    def test_submit_data_handler_success(self):
        payload = SubmitAssessmentDataRequest(
            questions=[{"id": 1, "question_text": "Explain RAG."}],
            transcript={"full_text": "RAG stands for..."},
            audio_telemetry={"words_per_minute": 135},
            video_telemetry={"face_visible_pct": 98.0},
        )

        result = api_router.submit_data(
            id=101,
            payload=payload,
            db=MagicMock(),
        )
        self.assertEqual(result["message"], "Data saved successfully")

    def test_submit_data_handler_not_found(self):
        payload = SubmitAssessmentDataRequest()
        with self.assertRaises(HTTPException) as ctx:
            api_router.submit_data(id=999, payload=payload, db=MagicMock())
        self.assertEqual(ctx.exception.status_code, 404)

    def test_update_media_url_success(self):
        payload = UpdateMediaUrlRequest(youtube_url="https://youtube.com/watch?v=new")
        result = api_router.update_media_url(id=101, payload=payload, db=MagicMock())
        self.assertEqual(result.id, 101)

    def test_update_media_url_not_found(self):
        payload = UpdateMediaUrlRequest(youtube_url="https://youtube.com/watch?v=new")
        with self.assertRaises(HTTPException) as ctx:
            api_router.update_media_url(id=999, payload=payload, db=MagicMock())
        self.assertEqual(ctx.exception.status_code, 404)

    def test_trigger_evaluation_success(self):
        bg_tasks = MagicMock()
        result = api_router.trigger_evaluation(id=101, bg_tasks=bg_tasks, db=MagicMock())
        self.assertEqual(result["id"], 101)
        self.assertEqual(result["status"], AssessmentStatusEnum.EVALUATING)

    def test_trigger_evaluation_not_found(self):
        bg_tasks = MagicMock()
        with self.assertRaises(HTTPException) as ctx:
            api_router.trigger_evaluation(id=999, bg_tasks=bg_tasks, db=MagicMock())
        self.assertEqual(ctx.exception.status_code, 404)

    def test_get_assessment_report_success(self):
        auth_ctx = {"candidate_id": 42, "is_employee": False, "is_admin": False}
        result = api_router.get_assessment_report(id=101, auth_ctx=auth_ctx, db=MagicMock())
        self.assertEqual(result["id"], 101)
        self.assertIn("data", result)
        self.assertIn("report", result)

    def test_list_candidate_assessments_handler(self):
        auth_ctx = {"candidate_id": 42, "is_employee": False, "is_admin": False}
        result = api_router.list_candidate_assessments(
            candidate_id=42,
            auth_ctx=auth_ctx,
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
        result = api_router.create_question(payload=payload, db=MagicMock())
        self.assertEqual(result.id, 1)

    def test_update_question_handler_success(self):
        payload = QuestionBankUpdateRequest(is_active=False)
        result = api_router.update_question(id=1, payload=payload, db=MagicMock())
        self.assertEqual(result.id, 1)

    def test_update_question_handler_not_found(self):
        payload = QuestionBankUpdateRequest(is_active=False)
        with self.assertRaises(HTTPException) as ctx:
            api_router.update_question(id=999, payload=payload, db=MagicMock())
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
