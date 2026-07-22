import pytest
from datetime import date
from unittest.mock import patch
from fapi.db.models import CandidateLlmApiKeyORM, AuthUserORM, CandidateORM
from fapi.utils.coderpad_openai_key import encrypt_api_key
from tests.conftest import TestingSessionLocal

def test_validate_endpoint_active(client, candidate_headers):
    payload = {"provider_name": "OpenAI", "api_key": "sk-proj-activekey"}
    with patch("fapi.utils.llm_providers.OpenAIProviderAdapter.validate_key") as mock_val:
        mock_val.return_value = ("active", "Key is active")
        response = client.post("/api/coderpad/me/llm-keys/validate", json=payload, headers=candidate_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["status"] == "ACTIVE"
        assert "validated successfully" in data["message"]

def test_validate_endpoint_invalid(client, candidate_headers):
    payload = {"provider_name": "OpenAI", "api_key": "sk-proj-invalidkey"}
    with patch("fapi.utils.llm_providers.OpenAIProviderAdapter.validate_key") as mock_val:
        mock_val.return_value = ("invalid", "Authentication failed")
        response = client.post("/api/coderpad/me/llm-keys/validate", json=payload, headers=candidate_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["status"] == "INVALID"
        assert "Invalid API key" in data["message"]

def test_save_unvalidated_key_succeeds_directly(client, candidate_headers, db_session):
    payload = {
        "provider_name": "OpenAI",
        "api_key": "sk-proj-anykey",
        "model_name": "gpt-4o-mini",
        "voice_enabled": False,
        "status": "inactive"
    }
    with patch("fapi.utils.llm_providers.OpenAIProviderAdapter.validate_key") as mock_val:
        response = client.post("/api/coderpad/me/llm-keys", json=payload, headers=candidate_headers)
        assert response.status_code == 204
        mock_val.assert_not_called()  # No external API check made during direct save

        # Verify DB entry
        new_sess = TestingSessionLocal()
        try:
            keys = new_sess.query(CandidateLlmApiKeyORM).all()
            assert len(keys) == 1
            assert keys[0].status == "inactive"
            assert keys[0].is_default is False  # Unvalidated keys are never default
        finally:
            new_sess.close()

def test_save_prevalidated_active_key_succeeds(client, candidate_headers, db_session):
    payload = {
        "provider_name": "OpenAI",
        "api_key": "sk-proj-activekey",
        "model_name": "gpt-4o-mini",
        "voice_enabled": True,
        "status": "active"
    }
    with patch("fapi.utils.llm_providers.OpenAIProviderAdapter.validate_key") as mock_val:
        mock_val.return_value = ("active", "Key is active")
        response = client.post("/api/coderpad/me/llm-keys", json=payload, headers=candidate_headers)
        assert response.status_code == 204
        mock_val.assert_called_once()  # Server side re-validation check is run

        # Verify DB entry
        new_sess = TestingSessionLocal()
        try:
            keys = new_sess.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.status == "active").all()
            assert len(keys) == 1
            assert keys[0].is_default is True  # Eligible first active key gets default flag
        finally:
            new_sess.close()

def test_save_prevalidated_invalid_key_saves_as_invalid(client, candidate_headers, db_session):
    payload = {
        "provider_name": "OpenAI",
        "api_key": "sk-proj-badkey",
        "model_name": "gpt-4o-mini",
        "voice_enabled": False,
        "status": "invalid"
    }
    with patch("fapi.utils.llm_providers.OpenAIProviderAdapter.validate_key") as mock_val:
        response = client.post("/api/coderpad/me/llm-keys", json=payload, headers=candidate_headers)
        assert response.status_code == 204
        mock_val.assert_not_called()  # Invalid is saved directly without calling the adapter

        # Verify DB entry
        new_sess = TestingSessionLocal()
        try:
            keys = new_sess.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.status == "invalid").all()
            assert len(keys) == 1
            assert keys[0].is_default is False
        finally:
            new_sess.close()

def test_update_key_to_unvalidated_demotes_default(client, candidate_headers, db_session, candidate_db_user):
    # Setup an existing active default key
    existing_key = CandidateLlmApiKeyORM(
        candidate_id=candidate_db_user["candidate"].id,
        provider_name="OpenAI",
        api_key=encrypt_api_key("sk-proj-oldkey"),
        model_name="gpt-4o-mini",
        voice_enabled=False,
        status="active",
        is_default=True
    )
    db_session.add(existing_key)
    db_session.commit()
    db_session.refresh(existing_key)

    # Edit key to a new value without pre-validation (Option B)
    payload = {
        "provider_name": "OpenAI",
        "api_key": "sk-proj-newunvalidated",
        "model_name": "gpt-4o-mini",
        "voice_enabled": False,
        "status": "inactive"
    }
    with patch("fapi.utils.llm_providers.OpenAIProviderAdapter.validate_key") as mock_val:
        response = client.put(f"/api/coderpad/me/llm-keys/{existing_key.id}", json=payload, headers=candidate_headers)
        assert response.status_code == 204
        mock_val.assert_not_called()

        new_sess = TestingSessionLocal()
        try:
            updated_key = new_sess.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.id == existing_key.id).first()
            assert updated_key.status == "inactive"
            assert updated_key.is_default is False  # Demoted from default since it's no longer active
        finally:
            new_sess.close()

def test_revalidate_saved_key_later(client, candidate_headers, db_session, candidate_db_user):
    # Setup an existing unvalidated key in DB
    existing_key = CandidateLlmApiKeyORM(
        candidate_id=candidate_db_user["candidate"].id,
        provider_name="OpenAI",
        api_key=encrypt_api_key("sk-proj-unvalidated"),
        model_name="gpt-4o-mini",
        voice_enabled=False,
        status="inactive",
        is_default=False
    )
    db_session.add(existing_key)
    db_session.commit()
    db_session.refresh(existing_key)

    # Re-validate via batch validate endpoint
    payload = {
        "keys": [{"id": existing_key.id, "provider_name": "OpenAI", "source": "wbl"}]
    }
    with patch("fapi.utils.llm_providers.OpenAIProviderAdapter.validate_key") as mock_val:
        mock_val.return_value = ("active", "Key is active")
        
        response = client.post("/api/coderpad/me/llm-keys/validate-batch", json=payload, headers=candidate_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["results"][0]["status"] == "active"

        # Check that it updated in DB and became default automatically (since it's now active)
        new_sess = TestingSessionLocal()
        try:
            updated_key = new_sess.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.id == existing_key.id).first()
            assert updated_key.status == "active"
            assert updated_key.is_default is True
        finally:
            new_sess.close()

def test_list_my_llm_keys_returns_fully_masked_value(client, candidate_headers, db_session, candidate_db_user):
    # Setup key in DB
    existing_key = CandidateLlmApiKeyORM(
        candidate_id=candidate_db_user["candidate"].id,
        provider_name="OpenAI",
        api_key=encrypt_api_key("sk-proj-supersecretkey12345"),
        model_name="gpt-4o-mini",
        voice_enabled=False,
        status="active",
        is_default=True
    )
    db_session.add(existing_key)
    db_session.commit()
    db_session.refresh(existing_key)

    response = client.get("/api/coderpad/me/llm-keys", headers=candidate_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    # Verify the masked key is exactly 16 bullets and does not leak any real characters
    assert data[0]["masked_key"] == "••••••••••••••••"
    assert "sk-proj" not in data[0]["masked_key"]
    assert "12345" not in data[0]["masked_key"]

def test_reveal_my_llm_key_succeeds(client, candidate_headers, db_session, candidate_db_user):
    # Setup key in DB
    existing_key = CandidateLlmApiKeyORM(
        candidate_id=candidate_db_user["candidate"].id,
        provider_name="OpenAI",
        api_key=encrypt_api_key("sk-proj-supersecretkey12345"),
        model_name="gpt-4o-mini",
        voice_enabled=False,
        status="active",
        is_default=True
    )
    db_session.add(existing_key)
    db_session.commit()
    db_session.refresh(existing_key)

    response = client.get(f"/api/coderpad/me/llm-keys/{existing_key.id}/reveal", headers=candidate_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["api_key"] == "sk-proj-supersecretkey12345"

def test_reveal_other_user_llm_key_fails(client, candidate_headers, db_session, candidate_db_user):
    # Create candidate B
    email = "candidate_B@test.com"
    auth_user_b = AuthUserORM(
        uname=email,
        passwd="hashed_password",
        status="active",
        role="",
        enddate=date(1990, 1, 1),
    )
    db_session.add(auth_user_b)
    db_session.commit()
    
    candidate_b = CandidateORM(
        full_name="Candidate B",
        email=email,
        status="active",
        phone="555-1111",
    )
    db_session.add(candidate_b)
    db_session.commit()
    db_session.refresh(candidate_b)

    # Create a key for Candidate B
    key_b = CandidateLlmApiKeyORM(
        candidate_id=candidate_b.id,
        provider_name="OpenAI",
        api_key=encrypt_api_key("sk-proj-candidate-b-secret"),
        model_name="gpt-4o-mini",
        voice_enabled=False,
        status="active",
        is_default=True
    )
    db_session.add(key_b)
    db_session.commit()
    db_session.refresh(key_b)

    # Request with Candidate A's headers to reveal Candidate B's key; must fail with 404
    response = client.get(f"/api/coderpad/me/llm-keys/{key_b.id}/reveal", headers=candidate_headers)
    assert response.status_code == 404


from fapi.utils.llm_execution_service import execute_llm_request_with_failover
from fastapi import HTTPException

def test_default_key_promotion_and_uniqueness(client, candidate_headers, db_session, candidate_db_user):
    # Setup key 1 in DB as inactive
    candidate_id = candidate_db_user["candidate"].id
    key1 = CandidateLlmApiKeyORM(
        candidate_id=candidate_id,
        provider_name="OpenAI",
        api_key=encrypt_api_key("sk-proj-key1"),
        model_name="gpt-4o-mini",
        voice_enabled=False,
        status="inactive",
        is_default=False
    )
    db_session.add(key1)
    db_session.commit()

    # Re-validate Key 1 -> becomes active and gets promoted to default
    payload = {
        "keys": [{"id": key1.id, "provider_name": "OpenAI", "source": "wbl"}]
    }
    with patch("fapi.utils.llm_providers.OpenAIProviderAdapter.validate_key") as mock_val:
        mock_val.return_value = ("active", "Key is active")
        response = client.post("/api/coderpad/me/llm-keys/validate-batch", json=payload, headers=candidate_headers)
        assert response.status_code == 200

    # Verify Key 1 is default
    db_session.expire_all()
    k1 = db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.id == key1.id).first()
    assert k1.status == "active"
    assert k1.is_default is True

    # Setup key 2 in DB as inactive
    key2 = CandidateLlmApiKeyORM(
        candidate_id=candidate_id,
        provider_name="Gemini",
        api_key=encrypt_api_key("AIzaSy-key2"),
        model_name="gemini-1.5-flash",
        voice_enabled=False,
        status="inactive",
        is_default=False
    )
    db_session.add(key2)
    db_session.commit()

    # Re-validate Key 2 -> becomes active, but should NOT replace key 1 as default because key 1 is already active default
    payload = {
        "keys": [{"id": key2.id, "provider_name": "Gemini", "source": "wbl"}]
    }
    with patch("fapi.utils.llm_providers.GeminiProviderAdapter.validate_key") as mock_val:
        mock_val.return_value = ("active", "Key is active")
        response = client.post("/api/coderpad/me/llm-keys/validate-batch", json=payload, headers=candidate_headers)
        assert response.status_code == 200

    db_session.expire_all()
    k1 = db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.id == key1.id).first()
    k2 = db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.id == key2.id).first()
    assert k1.is_default is True
    assert k2.is_default is False


def test_failover_flow_credits_exhausted(client, candidate_headers, db_session, candidate_db_user):
    # Setup candidate with 3 active keys (OpenAI, Gemini, Groq)
    candidate_id = candidate_db_user["candidate"].id
    
    # We delete any leftover keys first
    db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.candidate_id == candidate_id).delete()
    db_session.commit()

    key1 = CandidateLlmApiKeyORM(
        candidate_id=candidate_id,
        provider_name="OpenAI",
        api_key=encrypt_api_key("sk-proj-openai-key"),
        model_name="gpt-4o-mini",
        voice_enabled=False,
        status="active",
        is_default=True
    )
    key2 = CandidateLlmApiKeyORM(
        candidate_id=candidate_id,
        provider_name="Gemini",
        api_key=encrypt_api_key("AIzaSy-gemini-key"),
        model_name="gemini-1.5-flash",
        voice_enabled=False,
        status="active",
        is_default=False
    )
    key3 = CandidateLlmApiKeyORM(
        candidate_id=candidate_id,
        provider_name="Groq",
        api_key=encrypt_api_key("gsk_groq-key"),
        model_name="llama-3.1-8b-instant",
        voice_enabled=False,
        status="active",
        is_default=False
    )
    db_session.add_all([key1, key2, key3])
    db_session.commit()

    # Verify initial setup: key 1 is default, others are active
    assert key1.is_default is True
    assert key2.is_default is False
    assert key3.is_default is False

    # We mock execute_request on all 3 adapters:
    # 1. OpenAI returns credits exhausted (quota)
    # 2. Gemini returns credits exhausted (quota)
    # 3. Groq returns credits exhausted (quota)
    with patch("fapi.utils.llm_providers.OpenAIProviderAdapter.execute_request") as mock_openai, \
         patch("fapi.utils.llm_providers.GeminiProviderAdapter.execute_request") as mock_gemini, \
         patch("fapi.utils.llm_providers.GroqProviderAdapter.execute_request") as mock_groq:

        mock_openai.return_value = (None, "OpenAI error: billing_limit_reached", 429)
        mock_gemini.return_value = (None, "Gemini error: quota exhausted", 429)
        mock_groq.return_value = (None, "Groq error: billing limit reached", 429)

        # Call execute_llm_request_with_failover
        # This should fail all three and then raise HTTPException with ALL_LLM_KEYS_UNAVAILABLE
        with pytest.raises(HTTPException) as exc_info:
            execute_llm_request_with_failover(
                db=db_session,
                current_user=candidate_db_user["auth_user"],
                system_prompt="sys",
                user_prompt="user",
            )
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "ALL_LLM_KEYS_UNAVAILABLE"

        # Verify DB states: all keys should be credits_exhausted, and none default
        db_session.expire_all()
        k1 = db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.id == key1.id).first()
        k2 = db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.id == key2.id).first()
        k3 = db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.id == key3.id).first()
        
        assert k1.status == "credits_exhausted"
        assert k1.is_default is False
        assert k2.status == "credits_exhausted"
        assert k2.is_default is False
        assert k3.status == "credits_exhausted"
        assert k3.is_default is False


def test_revalidate_recovered_key_becomes_default(client, candidate_headers, db_session, candidate_db_user):
    # Setup candidate keys with status credits_exhausted and no default
    candidate_id = candidate_db_user["candidate"].id
    db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.candidate_id == candidate_id).delete()
    db_session.commit()

    key1 = CandidateLlmApiKeyORM(
        candidate_id=candidate_id,
        provider_name="OpenAI",
        api_key=encrypt_api_key("sk-proj-openai-key"),
        model_name="gpt-4o-mini",
        voice_enabled=False,
        status="credits_exhausted",
        is_default=False
    )
    db_session.add(key1)
    db_session.commit()

    # Revalidate key1 -> should become ACTIVE and DEFAULT
    payload = {
        "keys": [{"id": key1.id, "provider_name": "OpenAI", "source": "wbl"}]
    }
    with patch("fapi.utils.llm_providers.OpenAIProviderAdapter.validate_key") as mock_val:
        mock_val.return_value = ("active", "Key is active")
        response = client.post("/api/coderpad/me/llm-keys/validate-batch", json=payload, headers=candidate_headers)
        assert response.status_code == 200

    db_session.expire_all()
    k1 = db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.id == key1.id).first()
    assert k1.status == "active"
    assert k1.is_default is True


def test_temporary_errors_do_not_demote_key(client, db_session, candidate_db_user):
    # Setup default active key
    candidate_id = candidate_db_user["candidate"].id
    db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.candidate_id == candidate_id).delete()
    db_session.commit()

    key1 = CandidateLlmApiKeyORM(
        candidate_id=candidate_id,
        provider_name="OpenAI",
        api_key=encrypt_api_key("sk-proj-openai-key"),
        model_name="gpt-4o-mini",
        voice_enabled=False,
        status="active",
        is_default=True
    )
    db_session.add(key1)
    db_session.commit()

    # Mock execute_request to raise a temporary error (like 500 status code)
    with patch("fapi.utils.llm_providers.OpenAIProviderAdapter.execute_request") as mock_openai:
        mock_openai.return_value = (None, "Internal Server Error", 500)

        # Call should raise HTTPException 502
        with pytest.raises(HTTPException) as exc_info:
            execute_llm_request_with_failover(
                db=db_session,
                current_user=candidate_db_user["auth_user"],
                system_prompt="sys",
                user_prompt="user",
            )
        assert exc_info.value.status_code == 502
        assert "Temporary LLM error" in exc_info.value.detail

        # Key status and default flag must remain unchanged
        db_session.expire_all()
        k1 = db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.id == key1.id).first()
        assert k1.status == "active"
        assert k1.is_default is True


from fapi.utils.coderpad_openai_key import delete_candidate_llm_key_for_user, ensure_default_llm_key_for_candidate

def test_delete_key_promotions_and_fallbacks(client, candidate_headers, db_session, candidate_db_user):
    # Setup candidate keys: OpenAI (Active, Default), Gemini (Inactive, No Default), Groq (Active, No Default)
    candidate_id = candidate_db_user["candidate"].id
    db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.candidate_id == candidate_id).delete()
    db_session.commit()

    key1 = CandidateLlmApiKeyORM(
        candidate_id=candidate_id,
        provider_name="OpenAI",
        api_key=encrypt_api_key("sk-proj-openai-key"),
        model_name="gpt-4o-mini",
        voice_enabled=False,
        status="active",
        is_default=True
    )
    key2 = CandidateLlmApiKeyORM(
        candidate_id=candidate_id,
        provider_name="Gemini",
        api_key=encrypt_api_key("AIzaSy-gemini-key"),
        model_name="gemini-1.5-flash",
        voice_enabled=False,
        status="inactive",
        is_default=False
    )
    key3 = CandidateLlmApiKeyORM(
        candidate_id=candidate_id,
        provider_name="Groq",
        api_key=encrypt_api_key("gsk_groq-key"),
        model_name="llama-3.1-8b-instant",
        voice_enabled=False,
        status="active",
        is_default=False
    )
    db_session.add_all([key1, key2, key3])
    db_session.commit()

    # 1. Delete Gemini (non-default, inactive). OpenAI should remain default.
    delete_candidate_llm_key_for_user(db_session, candidate_db_user["auth_user"], key2.id)
    db_session.expire_all()
    
    k1 = db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.id == key1.id).first()
    k3 = db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.id == key3.id).first()
    assert k1.is_default is True
    assert k3.is_default is False

    # 2. Delete OpenAI (default). It should promote the next active key (Groq), skipping inactive/exhausted.
    delete_candidate_llm_key_for_user(db_session, candidate_db_user["auth_user"], key1.id)
    db_session.expire_all()
    
    k3 = db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.id == key3.id).first()
    assert k3.is_default is True

    # 3. Delete Groq (default). No other active keys exist. Default becomes NONE.
    delete_candidate_llm_key_for_user(db_session, candidate_db_user["auth_user"], key3.id)
    db_session.expire_all()
    
    remaining = db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.candidate_id == candidate_id).all()
    assert len(remaining) == 0


def test_reconcile_only_active_key_without_default(db_session, candidate_db_user):
    # Setup: Claude is the only active key but is_default = False (inconsistent state)
    candidate_id = candidate_db_user["candidate"].id
    db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.candidate_id == candidate_id).delete()
    db_session.commit()

    key1 = CandidateLlmApiKeyORM(
        candidate_id=candidate_id,
        provider_name="Claude",
        api_key=encrypt_api_key("sk-ant-claude-key"),
        model_name="claude-3-5-sonnet",
        voice_enabled=False,
        status="active",
        is_default=False
    )
    key1_id = key1.id
    db_session.add(key1)
    db_session.commit()

    # Reconcile defaults
    ensure_default_llm_key_for_candidate(db_session, candidate_id, commit=True)
    db_session.expire_all()

    k1 = db_session.query(CandidateLlmApiKeyORM).filter(CandidateLlmApiKeyORM.candidate_id == candidate_id).first()
    assert k1.is_default is True


