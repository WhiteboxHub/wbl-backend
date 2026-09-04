"""
API Route Tests for AI Prep Platform.
Validates FastAPI endpoints specified in contracts/api_endpoints.md.
"""

import sys
import unittest
from unittest.mock import MagicMock

import fapi.ai_prep

mock_crud = MagicMock()
mock_sqla = MagicMock()
sys.modules["fapi.ai_prep.crud"] = mock_crud
fapi.ai_prep.crud = mock_crud
sys.modules.setdefault("sqlalchemy", mock_sqla)
sys.modules.setdefault("sqlalchemy.orm", mock_sqla)
sys.modules.setdefault("fapi.db.database", MagicMock())

import fastapi.dependencies.utils

fastapi.dependencies.utils.ensure_multipart_is_installed = lambda: None

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fapi.db.database import get_db
from fapi.ai_prep.dependencies import get_current_candidate_id
from fapi.ai_prep.schemas import (
    AssessmentStatusEnum,
    AssessmentCategoryEnum,
    MediaTypeEnum,
)
from fapi.ai_prep.router import router

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


class TestApiRoutes(unittest.TestCase):

    def setUp(self):
        mock_crud.reset_mock()
        mock_crud.create_assessment.side_effect = lambda *args, **kwargs: DummyAssessmentORM()
        mock_crud.get_assessment_by_id.side_effect = lambda db, id: DummyAssessmentORM(id) if id != 999 else None

    def test_create_assessment_endpoint(self):
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

    def test_submit_data_endpoint(self):
        payload = {
            "questions": [],
            "transcript": {},
            "audio_telemetry": {},
            "video_telemetry": {},
        }

        response = client.post("/api/aiprep/assessments/101/data", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Data saved successfully")

    def test_get_assessment_not_found(self):
        response = client.get("/api/aiprep/assessments/999")
        self.assertEqual(response.status_code, 404)

    def test_list_candidate_assessments(self):
        mock_crud.list_candidate_assessments.return_value = []
        response = client.get("/api/aiprep/assessments?candidate_id=42")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 0)

    def test_list_questions(self):
        mock_crud.list_questions.return_value = []
        response = client.get("/api/aiprep/questions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 0)


if __name__ == "__main__":
    unittest.main()
