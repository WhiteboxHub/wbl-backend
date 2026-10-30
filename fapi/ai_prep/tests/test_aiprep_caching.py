import json
import pytest
from unittest.mock import MagicMock, patch
from fapi.core.cache import cache_result, invalidate_cache
from fapi.core.redis_client import redis_client


@pytest.fixture
def mock_redis():
    """Mock Redis client storing keys in memory for caching tests."""
    storage = {}
    client = MagicMock()

    def mock_get(key):
        return storage.get(key)

    def mock_set(key, val, ex=None):
        storage[key] = val
        return True

    def mock_delete(*keys):
        for k in keys:
            storage.pop(k, None)
        return len(keys)

    def mock_keys(pattern):
        # basic pattern matcher
        prefix = pattern.replace("*", "")
        return [k for k in storage.keys() if k.startswith(prefix)]

    client.get.side_effect = mock_get
    client.set.side_effect = mock_set
    client.delete.side_effect = mock_delete
    client.keys.side_effect = mock_keys

    with patch.object(redis_client, "get_client", return_value=client):
        yield client, storage


def test_aiprep_readiness_cache_miss_and_hit(mock_redis):
    client, storage = mock_redis
    from fapi.ai_prep.utils.aiprep_utils import assessment_readiness_precheck_logic

    mock_db = MagicMock()
    mock_user = MagicMock()
    mock_user.id = 99
    mock_user.uname = "candidate_99@test.com"
    mock_user.role = "candidate"
    mock_user.is_employee = False

    # Mock DB query for CandidateORM
    mock_cand = MagicMock()
    mock_cand.id = 99
    mock_db.query.return_value.filter.return_value.first.return_value = mock_cand

    with patch("fapi.ai_prep.utils.aiprep_utils._resolve_candidate_id", return_value=99), \
         patch("fapi.ai_prep.utils.aiprep_utils._check_candidate_llm_db", return_value={"status": "success", "is_configured": True, "provider": "openai", "model": "gpt-4", "voice_enabled": True, "message": "OK", "available_models": []}), \
         patch("fapi.ai_prep.utils.aiprep_utils._check_candidate_resume_db", return_value={"status": "success", "has_resume": True, "has_parsed_json": True, "candidate_name": "Test Candidate", "current_title": "AI Engineer", "skills": [], "message": "OK"}):

        # First call: Cache miss
        res1 = assessment_readiness_precheck_logic(mock_db, mock_user, candidate_id=99)
        assert res1.eligible is True
        assert res1.candidate_id == 99

        # Verify cached in Redis
        aiprep_keys = [k for k in storage.keys() if "aiprep" in k]
        assert len(aiprep_keys) >= 1
        cached_key = aiprep_keys[0]
        assert "assessment_readiness_precheck_logic" in cached_key

        # Second call: Cache hit
        res2 = assessment_readiness_precheck_logic(mock_db, mock_user, candidate_id=99)
        # On cache hit, returns deserialized dict or model matching the cached response
        if hasattr(res2, "eligible"):
            assert res2.eligible is True
            assert res2.candidate_id == 99
        else:
            assert res2["eligible"] is True
            assert res2["candidate_id"] == 99


def test_aiprep_list_assessments_cache_miss_and_hit(mock_redis):
    client, storage = mock_redis
    from fapi.ai_prep.utils.aiprep_utils import candidate_list_assessments_logic

    mock_db = MagicMock()
    mock_user = MagicMock()
    mock_user.id = 42
    mock_user.uname = "cand_42@test.com"

    mock_cand = MagicMock()
    mock_cand.id = 42
    mock_cand.full_name = "Jane Doe"
    mock_cand.email = "cand_42@test.com"
    mock_db.query.return_value.filter.return_value.first.return_value = mock_cand

    mock_asm = MagicMock()
    mock_asm.id = 101
    mock_asm.assessment_uuid = "uuid-101"
    mock_asm.candidate_id = 42
    mock_asm.assessment_type = "TECHNICAL"
    mock_asm.media_type = "VIDEO"
    mock_asm.status = "COMPLETED"
    mock_asm.job_description = "AI Engineer"
    mock_asm.youtube_url = None
    mock_asm.consent = {"video": True, "audio": True}
    mock_asm.started_at = None
    mock_asm.completed_at = None
    mock_asm.cancelled_at = None
    mock_asm.created_at = None
    mock_asm.report_record = None

    with patch("fapi.ai_prep.utils.aiprep_utils._resolve_candidate_id", return_value=42), \
         patch("fapi.ai_prep.crud.list_candidate_assessments", return_value=([mock_asm], 1)) as mock_crud_list:

        # First call: Cache miss
        res1 = candidate_list_assessments_logic(mock_db, mock_user, candidate_id=42)
        assert mock_crud_list.call_count == 1

        # Second call: Cache hit
        res2 = candidate_list_assessments_logic(mock_db, mock_user, candidate_id=42)
        # Should not call crud again on cache hit
        assert mock_crud_list.call_count == 1

        # Check returned items and verify Pydantic model type preservation on cache hit
        assert type(res2) is type(res1)
        assert hasattr(res2, "items")
        assert len(res2.items) == 1


def test_aiprep_cache_invalidation_clears_keys(mock_redis):
    from fapi.core import config
    client, storage = mock_redis

    k1 = f"{config.APP_ENV}:cache:aiprep:assessment_readiness_precheck_logic:123"
    k2 = f"{config.APP_ENV}:cache:aiprep:candidate_list_assessments_logic:456"
    k3 = f"{config.APP_ENV}:cache:candidates:get_dashboard:789"

    # Seed Redis storage with AI Prep keys
    storage[k1] = '{"eligible": true}'
    storage[k2] = '{"items": [], "total": 0}'
    storage[k3] = '{"name": "Keep Me"}'

    assert len(storage) == 3

    # Invalidate aiprep cache
    invalidate_cache("aiprep")

    # Verify aiprep keys are deleted, but other prefixes remain untouched
    assert k1 not in storage
    assert k2 not in storage
    assert k3 in storage
