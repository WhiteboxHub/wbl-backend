import unittest
from fastapi import Depends, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from fapi.main import app
from fapi.db.database import get_db
from fapi.ai_prep.dependencies import get_assessment_or_403
from fapi.ai_prep.models import (
    CandidateResume, AiPrepQuestionBank, AiPrepAssessment,
    AiPrepAssessmentQuestion, AiPrepHardwareCheck, AiPrepMediaFile,
    AiPrepTranscript, AiPrepVisionTelemetry, AiPrepAudioTelemetry,
    AiPrepReport, AiPrepConsent, AiPrepShareGrant,
    AiPrepDeletionRequest, AiPrepAuditEvent, AiPrepAnalysisRun
)

# Setup shared in-memory SQLite database with StaticPool for thread-safe unit tests
SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all 14 AI Prep tables for unit testing
aiprep_tables = [
    CandidateResume.__table__,
    AiPrepQuestionBank.__table__,
    AiPrepAssessment.__table__,
    AiPrepAssessmentQuestion.__table__,
    AiPrepHardwareCheck.__table__,
    AiPrepMediaFile.__table__,
    AiPrepTranscript.__table__,
    AiPrepVisionTelemetry.__table__,
    AiPrepAudioTelemetry.__table__,
    AiPrepReport.__table__,
    AiPrepConsent.__table__,
    AiPrepShareGrant.__table__,
    AiPrepDeletionRequest.__table__,
    AiPrepAuditEvent.__table__,
    AiPrepAnalysisRun.__table__,
]

for t in aiprep_tables:
    t.create(bind=engine, checkfirst=True)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def override_get_assessment_or_403(assessment_id: int, db: Session = Depends(override_get_db)):
    assessment = db.query(AiPrepAssessment).filter(AiPrepAssessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment session {assessment_id} not found."
        )
    return assessment


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_assessment_or_403] = override_get_assessment_or_403

client = TestClient(app)


class TestAiPrepAssessmentEngine(unittest.TestCase):
    """Unit tests for AI Prep Assessment Engine Router & Services."""

    def test_01_create_question_bank_item(self):
        """Test seeding a question into Question Bank."""
        payload = {
            "category": "TECHNICAL",
            "sub_category": "System Design",
            "difficulty_level": "MEDIUM",
            "question_text": "How do you design a high-throughput message queue?"
        }
        response = client.post("/api/ai-prep/questions", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["category"], "TECHNICAL")
        self.assertEqual(data["question_text"], payload["question_text"])

    def test_02_list_questions(self):
        """Test listing questions in Question Bank."""
        response = client.get("/api/ai-prep/questions?category=TECHNICAL")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)

    def test_03_create_assessment_session(self):
        """Test creating a new practice assessment session."""
        payload = {
            "assessment_type": "TECHNICAL",
            "assessment_mode": "VIDEO_AUDIO",
            "job_description_text": "Senior Backend AI Engineer"
        }
        response = client.post("/api/ai-prep/assessments?candidate_id=1", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["candidate_id"], 1)
        self.assertEqual(data["assessment_type"], "TECHNICAL")
        self.assertEqual(data["status"], "TESTING")

    def test_04_get_assessment_details(self):
        """Test fetching details of an assessment session."""
        payload = {
            "assessment_type": "GENERAL_INTRO",
            "assessment_mode": "AUDIO_ONLY"
        }
        create_res = client.post("/api/ai-prep/assessments?candidate_id=1", json=payload)
        session_id = create_res.json()["id"]

        get_res = client.get(f"/api/ai-prep/assessments/{session_id}")
        self.assertEqual(get_res.status_code, 200)
        data = get_res.json()
        self.assertEqual(data["id"], session_id)
        self.assertEqual(data["assessment_type"], "GENERAL_INTRO")

    def test_05_get_assessment_not_found(self):
        """Test 404 response for invalid assessment ID."""
        response = client.get("/api/ai-prep/assessments/999999")
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    def test_06_update_assessment_status(self):
        """Test updating session status state transition."""
        create_res = client.post("/api/ai-prep/assessments?candidate_id=1", json={"assessment_type": "TECHNICAL"})
        session_id = create_res.json()["id"]

        patch_res = client.patch(f"/api/ai-prep/assessments/{session_id}/status", json={"status": "IN_PROGRESS"})
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.json()["status"], "IN_PROGRESS")

    def test_07_record_and_get_hardware_check(self):
        """Test logging and retrieving device hardware check logs."""
        create_res = client.post("/api/ai-prep/assessments?candidate_id=1", json={"assessment_type": "TECHNICAL"})
        session_id = create_res.json()["id"]

        hw_payload = {
            "assessment_id": session_id,
            "browser_info": "Chrome 126",
            "os_info": "macOS",
            "camera_permission": True,
            "mic_permission": True,
            "speaker_ok": True,
            "bandwidth_kbps": 15000
        }
        hw_res = client.post("/api/ai-prep/hardware-check", json=hw_payload)
        self.assertEqual(hw_res.status_code, 201)
        self.assertTrue(hw_res.json()["camera_permission"])

        get_hw = client.get(f"/api/ai-prep/hardware-check/{session_id}")
        self.assertEqual(get_hw.status_code, 200)
        self.assertEqual(get_hw.json()["bandwidth_kbps"], 15000)

    def test_08_record_and_get_consents(self):
        """Test recording and reading privacy consents."""
        payload = {
            "consent_type": "VIDEO_ANALYTICS",
            "consented": True
        }
        post_res = client.post("/api/ai-prep/consents?candidate_id=1", json=payload)
        self.assertEqual(post_res.status_code, 201)

        get_res = client.get("/api/ai-prep/consents/1")
        self.assertEqual(get_res.status_code, 200)
        self.assertGreaterEqual(len(get_res.json()), 1)


if __name__ == "__main__":
    unittest.main()
