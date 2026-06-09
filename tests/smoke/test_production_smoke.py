"""
test_production_smoke.py
========================
Standalone, live production smoke tests designed to verify that the deployed
FastAPI service is healthy, responding, and secured.
Runs in the CD pipeline against the newly deployed production environment.
"""

import os
import pytest
import httpx

# Retrieve the production URL from environment variables
PROD_URL = os.environ.get("PROD_URL", "").strip()

# Skip the whole module if PROD_URL is not configured
pytestmark = pytest.mark.skipif(
    not PROD_URL,
    reason="PROD_URL environment variable is not configured for production smoke tests.",
)


@pytest.fixture(scope="module")
def client():
    # Standard HTTPX client pointing to the production deployment URL
    with httpx.Client(base_url=PROD_URL, timeout=30.0) as c:
        yield c


@pytest.mark.smoke
def test_production_fastapi_docs_reachable(client):
    """Verify that the FastAPI interactive documentation endpoint is alive and well."""
    response = client.get("/docs")
    assert response.status_code == 200, (
        f"Production /docs returned {response.status_code}, expected 200. "
        "The application might be failing to start or crash looping."
    )


@pytest.mark.smoke
def test_production_redis_health_active(client):
    """Verify that the backend's Redis health check endpoint is healthy and returning 200."""
    response = client.get("/api/redis-health")
    assert response.status_code == 200, (
        f"Production /api/redis-health returned {response.status_code}, expected 200. "
        "Redis or internal DB connection might be down."
    )

    # Assert JSON response structure is healthy
    data = response.json()
    assert (
        data.get("status") == "connected"
    ), f"Expected Redis status 'connected', got: {data.get('status')}"


@pytest.mark.smoke
def test_production_auth_gate_enforced(client):
    """Verify that admin endpoints correctly reject unauthenticated traffic with a 401."""
    # Attempting to fetch restricted leads without any Authorization header
    response = client.get("/api/leads")
    assert response.status_code == 401, (
        f"Expected 401 Unauthorized for unauthenticated /api/leads, got {response.status_code}. "
        "CRITICAL: Authorization layer might be bypassed or failing!"
    )
