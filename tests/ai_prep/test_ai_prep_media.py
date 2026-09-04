"""
Unit Tests for AIPrep Storage Service & Chunks
==============================================
Tests:
- Chunk saving and idempotency
- Chunk status inspection (uploaded vs missing)
- Sequential assembly into full.webm
- 16kHz mono audio.wav extraction
- Local file deletion & GDPR candidate purge
- Abandoned chunk TTL cleanup
"""
import os
import time
import pytest
from fapi.ai_prep.services.storage_service import storage_service
from fapi.ai_prep.exceptions import (
    ChunkValidationError,
    MissingChunksError,
    MediaAssemblyError,
    AudioExtractionError,
)


class TestStorageAndChunks:

    def setup_method(self):
        self.candidate_id = 999
        self.assessment_id = 888
        storage_service.delete_assessment_media(self.candidate_id, self.assessment_id)

    def teardown_method(self):
        storage_service.delete_assessment_media(self.candidate_id, self.assessment_id)

    def test_save_chunk_success(self):
        content = b"Mock_WebM_Chunk_0_Bytes"
        path, size = storage_service.save_chunk(
            candidate_id=self.candidate_id,
            assessment_id=self.assessment_id,
            chunk_number=0,
            file_bytes=content,
        )
        assert os.path.exists(path)
        assert size == len(content)
        assert path.endswith("0.webm")

    def test_save_chunk_idempotency_on_retry(self):
        content1 = b"Initial_Attempt_Bytes"
        content2 = b"Retry_Attempt_Bytes_Overwritten"

        storage_service.save_chunk(self.candidate_id, self.assessment_id, 0, content1)
        path2, size2 = storage_service.save_chunk(self.candidate_id, self.assessment_id, 0, content2)

        with open(path2, "rb") as f:
            read_back = f.read()

        assert read_back == content2
        assert size2 == len(content2)

    def test_save_chunk_negative_number_raises_error(self):
        with pytest.raises(ChunkValidationError):
            storage_service.save_chunk(self.candidate_id, self.assessment_id, -1, b"Invalid")

    def test_chunk_status_detection(self):
        # Save chunks 0 and 2 (missing chunk 1)
        storage_service.save_chunk(self.candidate_id, self.assessment_id, 0, b"Chunk_0")
        storage_service.save_chunk(self.candidate_id, self.assessment_id, 2, b"Chunk_2")

        status = storage_service.get_chunk_status(self.candidate_id, self.assessment_id, expected_total=3)

        assert status["uploaded_chunks"] == [0, 2]
        assert status["missing_chunks"] == [1]
        assert status["is_ready_for_assembly"] is False

    def test_assemble_chunks_success(self):
        chunk0 = b"Part0_"
        chunk1 = b"Part1_"
        chunk2 = b"Part2"

        storage_service.save_chunk(self.candidate_id, self.assessment_id, 0, chunk0)
        storage_service.save_chunk(self.candidate_id, self.assessment_id, 1, chunk1)
        storage_service.save_chunk(self.candidate_id, self.assessment_id, 2, chunk2)

        assembled_path = storage_service.assemble_chunks(self.candidate_id, self.assessment_id, total_chunks=3)

        assert os.path.exists(assembled_path)
        with open(assembled_path, "rb") as f:
            data = f.read()

        assert data == b"Part0_Part1_Part2"

    def test_assemble_chunks_missing_raises_missing_chunks_error(self):
        storage_service.save_chunk(self.candidate_id, self.assessment_id, 0, b"Part0")
        # Missing chunk 1 of 2

        with pytest.raises(MissingChunksError) as exc_info:
            storage_service.assemble_chunks(self.candidate_id, self.assessment_id, total_chunks=2)

        assert exc_info.value.missing_chunks == [1]

    def test_extract_audio_generates_wav(self):
        # Create dummy video file
        storage_service.save_chunk(self.candidate_id, self.assessment_id, 0, b"Dummy_Video_Header")
        video_path = storage_service.assemble_chunks(self.candidate_id, self.assessment_id, total_chunks=1)

        audio_path = storage_service.extract_audio(video_path)
        assert os.path.exists(audio_path)
        assert audio_path.endswith("audio.wav")

    def test_delete_local_file(self):
        video_path = storage_service.get_assembled_video_path(self.candidate_id, self.assessment_id)
        with open(video_path, "wb") as f:
            f.write(b"Temp_Video_Bytes")

        assert os.path.exists(video_path)
        deleted = storage_service.delete_local_file(video_path)
        assert deleted is True
        assert not os.path.exists(video_path)

    def test_gdpr_candidate_media_purge(self):
        storage_service.save_chunk(self.candidate_id, self.assessment_id, 0, b"GDPR_Sensitive_Data")
        assert os.path.exists(storage_service.get_chunks_dir(self.candidate_id, self.assessment_id))

        purged = storage_service.purge_candidate_data_gdpr(self.candidate_id)
        assert purged is True
        assert not os.path.exists(os.path.join(storage_service.base_path, str(self.candidate_id)))

    def test_abandoned_chunk_ttl_cleanup(self):
        path, _ = storage_service.save_chunk(self.candidate_id, self.assessment_id, 0, b"Stale_Chunk")
        # Artificially age the file modified time
        old_time = time.time() - (48 * 3600)  # 48 hours ago
        os.utime(path, (old_time, old_time))

        purged_count = storage_service.cleanup_abandoned_chunks(ttl_hours=24)
        assert purged_count >= 1
        assert not os.path.exists(path)
