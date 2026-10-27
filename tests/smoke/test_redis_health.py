import pytest

def test_redis_health_endpoint(client):
    """
    Tests that the /api/redis-health endpoint returns correctly.
    Our mock_redis fixture in conftest.py stubs out the real Redis client.
    """
    response = client.get("/api/redis-health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    # Depending on our mock, it might return connected or error if we test failure.
    # Our simple mock has a `.ping()` method implicitly mocked by MagicMock, so it succeeds.
    assert data["status"] == "connected"


def test_redis_client_production_missing_password_raises(monkeypatch):
    """Verifies that RedisClient raises ValueError in production if REDIS_PASSWORD is missing."""
    from fapi.core.redis_client import RedisClient
    from fapi.core import config

    orig_client = RedisClient._client
    RedisClient._client = None

    monkeypatch.setattr(config, "REDIS_HOST", "10.128.0.42")
    monkeypatch.setattr(config, "REDIS_PASSWORD", None)
    monkeypatch.setattr(config, "APP_ENV", "production")
    monkeypatch.delenv("ENV", raising=False)

    try:
        with pytest.raises(ValueError, match="REDIS_PASSWORD must be configured in production"):
            RedisClient.get_client()
    finally:
        RedisClient._client = orig_client


def test_redis_client_local_missing_password_allowed(monkeypatch):
    """Verifies that RedisClient does not raise ValueError in local dev if REDIS_PASSWORD is missing."""
    from fapi.core.redis_client import RedisClient
    from fapi.core import config

    orig_client = RedisClient._client
    RedisClient._client = None

    monkeypatch.setattr(config, "REDIS_HOST", "127.0.0.1")
    monkeypatch.setattr(config, "REDIS_PASSWORD", None)
    monkeypatch.setattr(config, "APP_ENV", "local")
    monkeypatch.delenv("ENV", raising=False)

    try:
        # Should not raise ValueError; fails connection gracefully and returns None
        client = RedisClient.get_client()
        assert client is None
    finally:
        RedisClient._client = orig_client
