"""
Tests for AIPrep Media Pipeline Orchestrator (BE2)
==================================================
Validates that AssessmentOrchestrator correctly coordinates:
- Assessment startup and lifecycle state transitions
- Chunk upload and validation
- Media assembly & task dispatch
- YouTube Unlisted upload and local server file deletion
"""
import os
import pytest
from fapi.ai_prep.schemas import CreateAssessmentRequest
from fapi.ai_prep.orchestrator.assessment_orchestrator import assessment_orchestrator
from fapi.ai_prep.services.storage_service import storage_service


def test_assessment_orchestrator_start_and_transition(db_session):
    # 1. Start assessment via Central Hub
    req = CreateAssessmentRequest(
        assessment_type="TECHNICAL",
        assessment_mode="VIDEO",
        job_description="AI Platform Engineer",
    )
    assessment = assessment_orchestrator.start_assessment(
        db=db_session,
        candidate_id=2001,
        payload=req,
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0 Chrome/120.0",
    )
    assert assessment.id is not None
    assert assessment.candidate_id == 2001
    assert assessment.status == "IN_PROGRESS"
    assert assessment.ip_address == "192.168.1.100"

    # 2. Transition status via Central Hub
    updated = assessment_orchestrator.transition_status(
        db=db_session,
        assessment_id=assessment.id,
        target_status="EVALUATING",
    )
    assert updated.status == "EVALUATING"


def test_assessment_orchestrator_media_workflow(db_session):
    # 1. Setup Assessment
    req = CreateAssessmentRequest(
        assessment_type="SYSTEM_DESIGN",
        assessment_mode="VIDEO",
    )
    assessment = assessment_orchestrator.start_assessment(db_session, 2002, req)
    aid = assessment.id

    try:
        # 2. Upload Chunks via Central Hub
        chunk0 = b"WebM_Header_and_Chunk_0"
        chunk1 = b"WebM_Body_and_Chunk_1"

        res0 = assessment_orchestrator.handle_chunk_upload(2002, aid, 0, chunk0, total_chunks=2)
        assert res0["status"] == "uploaded"

        status_info = assessment_orchestrator.get_chunk_status(2002, aid, expected_total=2)
        assert status_info["uploaded_chunks"] == [0]
        assert status_info["missing_chunks"] == [1]

        res1 = assessment_orchestrator.handle_chunk_upload(2002, aid, 1, chunk1, total_chunks=2)
        assert res1["status"] == "uploaded"

        # 3. Assemble and process media via Central Hub
        assemble_res = assessment_orchestrator.assemble_and_process_media(
            db=db_session,
            candidate_id=2002,
            assessment_id=aid,
            total_chunks=2,
        )
        assert assemble_res.assessment_id == aid
        assert assemble_res.status == "PROCESSING"

        # Background processing uploads to YouTube and deletes local file
        db_session.refresh(assessment)
        assert assessment.youtube_url is not None
        local_video = storage_service.get_assembled_video_path(2002, aid)
        assert not os.path.exists(local_video)

        # 4. Also test upload_to_youtube_and_cleanup directly with a created file
        with open(local_video, "wb") as f:
            f.write(b"Direct_Upload_Test_Video")
        
        yt_res = assessment_orchestrator.upload_to_youtube_and_cleanup(db_session, aid)
        assert "youtube_url" in yt_res
        assert yt_res["local_file_deleted"] is True
        assert not os.path.exists(local_video)

    finally:
        storage_service.delete_assessment_media(2002, aid)
