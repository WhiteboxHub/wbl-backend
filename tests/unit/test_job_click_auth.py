import pytest
from unittest.mock import MagicMock
from fapi.utils.job_click_utils import _validate_authuser_id, _resolve_candidate_to_authuser_id

def test_validate_authuser_id_valid():
    db = MagicMock()
    # Mock finding an AuthUser
    mock_auth_user = MagicMock(id=15)
    db.query.return_value.filter.return_value.first.return_value = mock_auth_user

    result = _validate_authuser_id(db, 15)
    assert result == 15

def test_validate_authuser_id_invalid():
    db = MagicMock()
    # Mock NOT finding an AuthUser
    db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(ValueError, match="Invalid authuser_id"):
        _validate_authuser_id(db, 99)

def test_validate_authuser_id_falsy():
    db = MagicMock()
    with pytest.raises(ValueError, match="Invalid authuser_id"):
        _validate_authuser_id(db, 0)
    with pytest.raises(ValueError, match="Invalid authuser_id"):
        _validate_authuser_id(db, None)

def test_resolve_candidate_to_authuser_id_valid():
    db = MagicMock()
    
    # Mock finding a Candidate
    mock_candidate = MagicMock()
    mock_candidate.email = "test@example.com"
    
    # Mock finding a linked AuthUser
    mock_linked_user = MagicMock(id=42)

    # We need to simulate the sequence of first() calls on db.query
    # first call is for candidate
    # second call is for auth_user
    db.query.return_value.filter.return_value.first.side_effect = [mock_candidate, mock_linked_user]

    result = _resolve_candidate_to_authuser_id(db, 15)
    assert result == 42

def test_resolve_candidate_to_authuser_id_invalid_candidate():
    db = MagicMock()
    
    # Mock NOT finding a Candidate
    db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(ValueError, match="Invalid candidate_id"):
        _resolve_candidate_to_authuser_id(db, 99)

def test_resolve_candidate_to_authuser_id_collision():
    db = MagicMock()
    
    # Candidate A has ID=15
    mock_candidate = MagicMock()
    mock_candidate.email = "candA@example.com"
    
    # AuthUser B has ID=15, but AuthUser A has ID=42
    # In this context, _resolve_candidate_to_authuser_id will look up the email
    mock_linked_user = MagicMock(id=42)

    db.query.return_value.filter.return_value.first.side_effect = [mock_candidate, mock_linked_user]

    # Resolve candidate ID 15
    result = _resolve_candidate_to_authuser_id(db, 15)
    
    # It must return the LINKED AuthUser A (42), completely ignoring the fact
    # that AuthUser B (15) exists in the database.
    assert result == 42
    assert result != 15
