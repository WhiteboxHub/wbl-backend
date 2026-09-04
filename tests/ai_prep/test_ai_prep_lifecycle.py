"""
End-to-End Lifecycle Integration Tests for AIPrep
=================================================
Validates full workflow:
1. Candidate creates assessment
2. Candidate uploads chunks 0 and 1
3. Checks chunk status
4. Assembles chunks and triggers pipeline
5. Full pipeline executes STT -> Audio -> Vision -> LLM -> YouTube -> Complete
"""
import os
import io
import pytest
from jose import jwt

from fapi.ai_prep.models import AiPrepAssessment, AssessmentStatusEnum
from fapi.ai_prep.services.storage_service import storage_service
from fapi.ai_prep.services.media_service import media_service


def get_auth_headers(candidate_id: int):
    token = jwt.encode(
        {"sub": str(candidate_id), "candidate_id": candidate_id},
        os.getenv("SECRET_KEY", "mock_test_secret_key_12345"),
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_chunk_upload_api_and_assembly(client, db_session):
    headers = get_auth_headers(1001)

    # 1. Create Assessment
    assessment = AiPrepAssessment(
        candidate_id=1001,
        assessment_type="TECHNICAL",
        assessment_mode="VIDEO_AUDIO",
        status="IN_PROGRESS",
    )
    db_session.add(assessment)
    db_session.commit()
    db_session.refresh(assessment)
    aid = assessment.id

    storage_service.delete_assessment_media(1001, aid)

    try:
        # 2. Upload Chunk 0
        chunk0_bytes = b"WebM_Chunk_0_Binary_Content"
        response0 = client.post(
            "/api/ai-prep/media/upload-chunk",
            data={"assessment_id": aid, "chunk_number": 0, "total_chunks": 2},
            files={"file": ("0.webm", io.BytesIO(chunk0_bytes), "video/webm")},
            headers=headers,
        )
        assert response0.status_code == 200
        res0_json = response0.json()
        assert res0_json["chunk_number"] == 0
        assert res0_json["status"] == "uploaded"

        # 3. Check Chunks Status
        status_res = client.get(
            f"/api/ai-prep/media/chunks-status/{aid}",
            headers=headers,
        )
        assert status_res.status_code == 200
        status_json = status_res.json()
        assert status_json["uploaded_chunks"] == [0]

        # 4. Upload Chunk 1
        chunk1_bytes = b"WebM_Chunk_1_Binary_Content"
        response1 = client.post(
            "/api/ai-prep/media/upload-chunk",
            data={"assessment_id": aid, "chunk_number": 1, "total_chunks": 2},
            files={"file": ("1.webm", io.BytesIO(chunk1_bytes), "video/webm")},
            headers=headers,
        )
        assert response1.status_code == 200

        # 5. Assemble Chunks
        assemble_res = client.post(
            "/api/ai-prep/media/assemble",
            json={"assessment_id": aid, "total_chunks": 2},
            headers=headers,
        )
        assert assemble_res.status_code == 202
        assemble_json = assemble_res.json()
        assert assemble_json["status"] == "PROCESSING"

    finally:
        storage_service.delete_assessment_media(1001, aid)


def test_full_pipeline_task_execution(db_session):
    # Setup Assessment
    candidate_id = 1002
    assessment = AiPrepAssessment(
        candidate_id=candidate_id,
        assessment_type="TECHNICAL",
        assessment_mode="VIDEO",
        status=AssessmentStatusEnum.IN_PROGRESS.value,
    )
    db_session.add(assessment)
    db_session.commit()
    db_session.refresh(assessment)
    aid = assessment.id

    # Create dummy assembled video
    video_path = storage_service.get_assembled_video_path(candidate_id, aid)
    with open(video_path, "wb") as f:
        f.write(b"Pipeline_Test_Assembled_Video")

    try:
        # Execute background media processing directly
        res = media_service.process_assessment_background(aid)
        assert res is not None
        assert res["status"] == "COMPLETED"

        db_session.refresh(assessment)
        assert assessment.status == AssessmentStatusEnum.COMPLETED.value
        assert assessment.youtube_url is not None

        # Verify local video was cleaned up after YouTube upload
        assert not os.path.exists(video_path)

    finally:
        storage_service.delete_assessment_media(candidate_id, aid)

