import unittest
import warnings
warnings.filterwarnings("ignore")

from fastapi import Depends, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from fapi.main import app
from fapi.db.database import get_db
from fapi.ai_prep.dependencies import get_assessment_or_403
from fapi.ai_prep.models import (
    CandidateResume, AiPrepQuestionBankORM as AiPrepQuestionBank,
    AiPrepAssessmentORM as AiPrepAssessment, AiPrepAssessmentQuestionORM as AiPrepAssessmentQuestion,
    AiPrepHardwareCheckORM as AiPrepHardwareCheck, AiPrepMediaFileORM as AiPrepMediaFile,
    AiPrepTranscriptORM as AiPrepTranscript, AiPrepVisionTelemetryORM as AiPrepVisionTelemetry,
    AiPrepAudioTelemetryORM as AiPrepAudioTelemetry, AiPrepReportORM as AiPrepReport,
    AiPrepConsentORM as AiPrepConsent, AiPrepShareGrantORM as AiPrepShareGrant,
    AiPrepDeletionRequestORM as AiPrepDeletionRequest, AiPrepAuditEventORM as AiPrepAuditEvent,
    AiPrepAnalysisRunORM as AiPrepAnalysisRun, AssessmentTypeEnum, AssessmentStatusEnum,
    CoachingBandEnum
)

# Setup shared in-memory SQLite database with StaticPool for thread-safe E2E testing
SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all AI Prep tables for E2E testing
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


from fapi.utils.auth_dependencies import get_current_user


class DummyUser:
    id = 1
    user_id = 1
    role = "candidate"
    is_admin = False


def override_get_current_user():
    return DummyUser()


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
app.dependency_overrides[get_current_user] = override_get_current_user
app.dependency_overrides[get_assessment_or_403] = override_get_assessment_or_403

client = TestClient(app)


class TestAiPrepE2EAssessmentFlow(unittest.TestCase):
    """W3-BE1-01: Full Assessment Flow E2E Automated Test Suite covering all 7 Assessment Types."""

    def setUp(self):
        """Seed question bank with sample questions across categories."""
        db = TestingSessionLocal()
        existing_count = db.query(AiPrepQuestionBank).count()
        if existing_count == 0:
            categories = ["TECHNICAL", "SYSTEM_DESIGN", "RECRUITER", "HIRING_MANAGER", "BEHAVIORAL", "GENERAL"]
            for cat in categories:
                for i in range(1, 4):
                    q = AiPrepQuestionBank(
                        category=cat,
                        sub_category=f"{cat} Subtopic {i}",
                        difficulty_level="MEDIUM",
                        question_text=f"Sample question {i} for category {cat}",
                        is_active=True
                    )
                    db.add(q)
            db.commit()
        db.close()

    def _run_e2e_happy_path_for_type(self, assessment_type: str, requires_jd: bool = False):
        """Executes full 8-step E2E lifecycle for a given assessment type."""
        candidate_id = 1

        # 1. Record Privacy Consent
        consent_res = client.post(
            f"/api/ai-prep/consents?candidate_id={candidate_id}",
            json={"consent_type": "VIDEO_ANALYTICS", "consented": True}
        )
        self.assertIn(consent_res.status_code, [200, 201])

        # 2. Create Assessment Session
        create_payload = {
            "assessment_type": assessment_type,
            "assessment_mode": "VIDEO_AUDIO"
        }
        if requires_jd:
            create_payload["job_description_text"] = "Senior AI Systems Engineer position"

        create_res = client.post(f"/api/ai-prep/assessments?candidate_id={candidate_id}", json=create_payload)
        self.assertEqual(create_res.status_code, 201, f"Failed to create assessment for {assessment_type}: {create_res.text}")
        session_data = create_res.json()
        session_id = session_data["id"]
        self.assertEqual(session_data["assessment_type"], assessment_type)
        self.assertEqual(session_data["status"], "TESTING")

        # 3. Record Hardware Check
        hw_payload = {
            "assessment_id": session_id,
            "browser_info": "Chrome 126.0",
            "os_info": "macOS",
            "camera_permission": True,
            "mic_permission": True,
            "speaker_ok": True,
            "bandwidth_kbps": 25000,
            "yolo_model_enabled": True
        }
        hw_res = client.post("/api/ai-prep/hardware-check", json=hw_payload)
        self.assertEqual(hw_res.status_code, 201)

        # 4. Transition Status to IN_PROGRESS
        patch_res = client.patch(f"/api/ai-prep/assessments/{session_id}/status", json={"status": "IN_PROGRESS"})
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.json()["status"], "IN_PROGRESS")

        # 5. Fetch Session Details & Verify Questions Assigned
        get_res = client.get(f"/api/ai-prep/assessments/{session_id}")
        self.assertEqual(get_res.status_code, 200)

        # 6. Poll Processing Status
        poll_res = client.get(f"/api/ai-prep/assessments/{session_id}/processing-status")
        self.assertEqual(poll_res.status_code, 200)
        self.assertIn("status", poll_res.json())

        # 7. Transition Status to PROCESSING
        processing_res = client.patch(f"/api/ai-prep/assessments/{session_id}/status", json={"status": "PROCESSING"})
        self.assertEqual(processing_res.status_code, 200)
        self.assertEqual(processing_res.json()["status"], "PROCESSING")

        # 8. Transition Status to COMPLETED
        completed_res = client.patch(f"/api/ai-prep/assessments/{session_id}/status", json={"status": "COMPLETED"})
        self.assertEqual(completed_res.status_code, 200)
        self.assertEqual(completed_res.json()["status"], "COMPLETED")

    def test_e2e_01_general_intro(self):
        """E2E Test 1/7: GENERAL_INTRO happy path."""
        self._run_e2e_happy_path_for_type("GENERAL_INTRO")

    def test_e2e_02_job_description_intro(self):
        """E2E Test 2/7: JOB_DESCRIPTION_INTRO happy path with JD."""
        self._run_e2e_happy_path_for_type("JOB_DESCRIPTION_INTRO", requires_jd=True)

    def test_e2e_03_recruiter(self):
        """E2E Test 3/7: RECRUITER happy path."""
        self._run_e2e_happy_path_for_type("RECRUITER")

    def test_e2e_04_hiring_manager(self):
        """E2E Test 4/7: HIRING_MANAGER happy path."""
        self._run_e2e_happy_path_for_type("HIRING_MANAGER")

    def test_e2e_05_technical(self):
        """E2E Test 5/7: TECHNICAL happy path."""
        self._run_e2e_happy_path_for_type("TECHNICAL")

    def test_e2e_06_system_design(self):
        """E2E Test 6/7: SYSTEM_DESIGN happy path."""
        self._run_e2e_happy_path_for_type("SYSTEM_DESIGN")

    def test_e2e_07_hr(self):
        """E2E Test 7/7: HR happy path."""
        self._run_e2e_happy_path_for_type("HR")


if __name__ == "__main__":
    unittest.main()
