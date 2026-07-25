"""Unit and integration tests for Complete Setup eligibility and LLM key validation."""
import pytest
from unittest.mock import MagicMock, patch

from fapi.utils.coderpad_openai_key import finish_setup_for_user


def test_finish_setup_no_keys():
    """Test 2 & 12: No keys configured -> finish_setup_for_user rejects setup."""
    db = MagicMock()
    user = MagicMock(id=1)
    
    with patch("fapi.utils.coderpad_openai_key._candidate_id_for_user", return_value=10):
        db.query.return_value.filter.return_value.all.return_value = []
        result = finish_setup_for_user(db, user)
        
        assert result["setup_complete"] is False
        assert result["error_code"] == "NO_USABLE_LLM_KEY"


def test_finish_setup_invalid_key():
    """Test 4: INVALID key -> finish_setup_for_user rejects setup."""
    db = MagicMock()
    user = MagicMock(id=1)
    mock_key = MagicMock(id=101, status="invalid", provider_name="OpenAI")
    
    with patch("fapi.utils.coderpad_openai_key._candidate_id_for_user", return_value=10), \
         patch("fapi.utils.coderpad_openai_key.ensure_default_llm_key_for_candidate"), \
         patch("fapi.utils.coderpad_openai_key._default_llm_key_row", return_value=mock_key):
        db.query.return_value.filter.return_value.all.return_value = [mock_key]
        result = finish_setup_for_user(db, user)
        
        assert result["setup_complete"] is False
        assert result["error_code"] == "NO_USABLE_LLM_KEY"


def test_finish_setup_active_key():
    """Test 7: ACTIVE usable key -> finish_setup_for_user succeeds."""
    db = MagicMock()
    user = MagicMock(id=1)
    mock_key = MagicMock(id=101, status="active", provider_name="OpenAI", is_default=True)
    mock_detection = {
        "detected_provider": "OpenAI",
        "status": "active",
        "message": "Key is active",
        "available_models": ["gpt-4o"],
        "default_model": "gpt-4o"
    }
    
    with patch("fapi.utils.coderpad_openai_key._candidate_id_for_user", return_value=10), \
         patch("fapi.utils.coderpad_openai_key.ensure_default_llm_key_for_candidate"), \
         patch("fapi.utils.coderpad_openai_key._default_llm_key_row", return_value=mock_key), \
         patch("fapi.utils.coderpad_openai_key._row_secret", return_value="sk-proj-testkey"), \
         patch("fapi.utils.llm_provider_registry.provider_registry.detect_and_validate", return_value=mock_detection):
        db.query.return_value.filter.return_value.all.return_value = [mock_key]
        result = finish_setup_for_user(db, user)
        
        assert result["setup_complete"] is True


def test_finish_setup_multiple_keys_one_working():
    """Test 8: Multiple keys with at least one usable active key -> succeeds."""
    db = MagicMock()
    user = MagicMock(id=1)
    key1 = MagicMock(id=1, status="invalid", provider_name="OpenAI")
    key2 = MagicMock(id=2, status="active", provider_name="Groq", is_default=False)
    mock_detection = {
        "detected_provider": "Groq",
        "status": "active",
        "message": "Key is active",
        "available_models": ["llama-3.3-70b-versatile"],
        "default_model": "llama-3.3-70b-versatile"
    }
    
    with patch("fapi.utils.coderpad_openai_key._candidate_id_for_user", return_value=10), \
         patch("fapi.utils.coderpad_openai_key.ensure_default_llm_key_for_candidate"), \
         patch("fapi.utils.coderpad_openai_key._default_llm_key_row", return_value=key2), \
         patch("fapi.utils.coderpad_openai_key._row_secret", return_value="gsk_testkey"), \
         patch("fapi.utils.llm_provider_registry.provider_registry.detect_and_validate", return_value=mock_detection):
        db.query.return_value.filter.return_value.all.return_value = [key1, key2]
        result = finish_setup_for_user(db, user)
        
        assert result["setup_complete"] is True
