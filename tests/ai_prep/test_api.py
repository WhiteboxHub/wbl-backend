"""
FastAPI Integration Tests for AIPrep
====================================
Tests the 10 fixed API endpoints via TestClient:
- Assessment creation, listing, status transitions
- Chunk upload, chunk status, media assembly
- Processing status SSE/JSON snapshot
- YouTube media update
- Report fetching
"""
import io
import os
from jose import jwt
from fapi.ai_prep.models import AiPrepAssessment
from fapi.ai_prep.services.storage_service import storage_service


def get_auth_headers(candidate_id: int):
    token = jwt.encode(
        {"sub": str(candidate_id), "candidate_id": candidate_id},
        os.getenv("SECRET_KEY", "mock_test_secret_key_12345"),
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_api_assessment_lifecycle(client, db_session):
    headers = get_auth_headers(3001)

    # 1. Create Assessment
    create_res = client.post(
        "/api/ai-prep/assessments",
        json={
            "assessment_type": "TECHNICAL",
            "assessment_mode": "VIDEO",
            "job_description": "Senior Backend Engineer",
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    created_json = create_res.json()
    assert created_json["candidate_id"] == 3001
    assert created_json["status"] == "IN_PROGRESS"
    assessment_id = created_json["id"]

    # 2. Get Assessment Details
    get_res = client.get(f"/api/ai-prep/assessments/{assessment_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == assessment_id

    # 3. List Assessments for Candidate
    list_res = client.get("/api/ai-prep/assessments", headers=headers)
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1

    # 4. Patch Status
    patch_res = client.patch(
        f"/api/ai-prep/assessments/{assessment_id}/status",
        json={"status": "EVALUATING"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "EVALUATING"

    # 5. Patch YouTube Media URL
    media_patch_res = client.patch(
        f"/api/ai-prep/assessments/{assessment_id}/media",
        json={"youtube_url": "https://youtube.com/watch?v=mock_video_id"},
        headers=headers,
    )
    assert media_patch_res.status_code == 200
    assert media_patch_res.json()["youtube_url"] == "https://youtube.com/watch?v=mock_video_id"

    # 6. Check Processing Status JSON Snapshot
    status_res = client.get(
        f"/api/ai-prep/assessments/{assessment_id}/processing-status",
        headers=headers,
    )
    assert status_res.status_code == 200
    status_json = status_res.json()
    assert "progress_percentage" in status_json
    assert "current_step" in status_json


def test_api_media_pipeline(client, db_session):
    headers = get_auth_headers(3002)

    # Create assessment
    assessment = AiPrepAssessment(
        candidate_id=3002,
        assessment_type="TECHNICAL",
        assessment_mode="VIDEO",
        status="IN_PROGRESS",
    )
    db_session.add(assessment)
    db_session.commit()
    db_session.refresh(assessment)
    aid = assessment.id

    try:
        # 1. Upload chunk 0
        chunk0_bytes = b"WebM_Chunk_0_Binary_Content"
        upload0_res = client.post(
            "/api/ai-prep/media/upload-chunk",
            data={"assessment_id": aid, "chunk_number": 0, "total_chunks": 2},
            files={"file": ("0.webm", io.BytesIO(chunk0_bytes), "video/webm")},
            headers=headers,
        )
        assert upload0_res.status_code == 200
        assert upload0_res.json()["chunk_number"] == 0

        # 2. Check chunks status
        status_res = client.get(f"/api/ai-prep/media/chunks-status/{aid}", headers=headers)
        assert status_res.status_code == 200
        assert status_res.json()["uploaded_chunks"] == [0]

        # 3. Upload chunk 1
        chunk1_bytes = b"WebM_Chunk_1_Binary_Content"
        upload1_res = client.post(
            "/api/ai-prep/media/upload-chunk",
            data={"assessment_id": aid, "chunk_number": 1, "total_chunks": 2},
            files={"file": ("1.webm", io.BytesIO(chunk1_bytes), "video/webm")},
            headers=headers,
        )
        assert upload1_res.status_code == 200

        # 4. Assemble
        assemble_res = client.post(
            "/api/ai-prep/media/assemble",
            json={"assessment_id": aid, "total_chunks": 2},
            headers=headers,
        )
        assert assemble_res.status_code == 202
        assert assemble_res.json()["status"] == "PROCESSING"

    finally:
        storage_service.delete_assessment_media(3002, aid)

