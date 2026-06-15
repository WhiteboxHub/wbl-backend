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
