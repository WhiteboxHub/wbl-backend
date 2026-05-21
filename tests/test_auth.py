import pytest

def test_user_registration(client, mocker):
    """
    Test user registration flow.
    Mocks the recaptcha verification and email sending to isolate the test.
    """
    # Mock external calls
    mocker.patch("fapi.api.routes.register.verify_recaptcha_token", return_value=True)
    mocker.patch("fapi.api.routes.register.send_email_to_user")
    
    payload = {
        "uname": "testuser@example.com",
        "passwd": "testpassword123",
        "recaptcha_token": "dummy_token",
        "status": "active"   # Required: authenticate_user rejects inactive accounts
    }
    
    response = client.post("/api/signup", json=payload)
    
    assert response.status_code == 200
    assert "successfully" in response.json().get("message", "")

def test_user_login_success(client, mocker, db_session):
    """
    Test login flow after a user has registered.
    """
    # 1. Register a user
    mocker.patch("fapi.api.routes.register.verify_recaptcha_token", return_value=True)
    mocker.patch("fapi.api.routes.register.send_email_to_user")
    
    reg_payload = {
        "uname": "loginuser@example.com",
        "passwd": "testpassword123",
        "recaptcha_token": "dummy_token",
        "status": "active"   # Required: authenticate_user rejects inactive accounts
    }
    client.post("/api/signup", json=reg_payload)
    
    # 1.5 Insert an active Candidate record for this email
    from fapi.db.models import CandidateORM
    candidate = CandidateORM(
        full_name="Login User",
        email="loginuser@example.com",
        status="active"
    )
    db_session.add(candidate)
    db_session.commit()
    
    # 2. Login as the user
    # Note: OAuth2PasswordRequestForm expects form data, not JSON
    login_payload = {
        "username": "loginuser@example.com",
        "password": "testpassword123"
    }
    
    response = client.post("/api/login", data=login_payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    # Login count should be 1 after first login
    assert data.get("login_count") == 1

def test_user_login_invalid_credentials(client):
    """
    Test login rejection with non-existent or wrong credentials.
    """
    login_payload = {
        "username": "nonexistent@example.com",
        "password": "wrongpassword"
    }
    
    response = client.post("/api/login", data=login_payload)
    
    assert response.status_code in [404, 401]
