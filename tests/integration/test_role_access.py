"""
test_role_access.py
====================
Verifies that the permission_gate correctly blocks non-admin
users from admin-only routes, and allows admins through.
Strategy:
  - We create two users in the in-memory test DB (from conftest):
      1. A regular candidate-linked user (no role → gets 403 on admin routes)
      2. An admin user (role="admin" → passes through)
  - We forge valid JWTs for each using the same SECRET_KEY conftest injects.
  - We hit a sample of known admin-only routes and assert:
      * candidate → 403 (or 422 if a body is required, which also means auth passed)
      * admin     → NOT 401 or 403
"""

import pytest
from jose import jwt
from datetime import datetime, timedelta, timezone, date
from fapi.db.models import AuthUserORM
import os
import uuid

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SECRET_KEY = os.environ["SECRET_KEY"]
ALGORITHM = os.environ.get("ALGORITHM", "HS256")


def _make_token(
    user_id: int, uname: str, role: str = "", is_admin: bool = False
) -> str:
    """Forge a JWT token using the same secret conftest injects."""
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(user_id),
        "uname": uname,
        "role": role,
        "is_admin": is_admin,
        "exp": now + timedelta(hours=1),
        "iat": now,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _auth_headers(token: str) -> dict:
    return {"authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixtures: seed two users into the in-memory DB
# ---------------------------------------------------------------------------


@pytest.fixture
def candidate_user(db_session):
    """a regular (non admin) authuser with no role"""
    unique_id = uuid.uuid4().hex[:8]
    user = AuthUserORM(
        uname=f"candidate_{unique_id}@example.com",
        passwd="hashed_password",  # pragma: allowlist secret
        status="active",
        role=None,
        enddate=date(1990, 1, 1),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session):
    """An admin AuthUser with role='admin'."""
    unique_id = uuid.uuid4().hex[:8]
    user = AuthUserORM(
        uname=f"admin_{unique_id}@example.com",
        passwd="hashed_password",  # pragma: allowlist secret
        status="active",
        role="admin",
        enddate=date(1990, 1, 1),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# The actual tests
# ---------------------------------------------------------------------------
# A sample of routes that go through enforce_access and are NOT in
# the ALLOWED_*_PREFIXES for non-admin users.

ADMIN_ONLY_GET_ROUTES = [
    "/api/leads",
    "/api/vendors",
    "/api/employees",
    "/api/job-types",
    "/api/companies",
]
ADMIN_ONLY_POST_ROUTES = [
    "/api/leads",
    "/api/vendors",
]


class TestcandidateBlockedOnAdminRoutes:
    """Non-admin users must receive 403 on admin-only routes."""

    def test_candidate_blocked_on_get_routes(self, client, candidate_user):
        token = _make_token(
            candidate_user.id, candidate_user.uname, role="", is_admin=False
        )
        headers = _auth_headers(token)

        for route in ADMIN_ONLY_GET_ROUTES:
            response = client.get(route, headers=headers)
            assert (
                response.status_code == 403
            ), f"Expected 403 on GET {route} for candidate, got {response.status_code}"

    def test_candidate_blocked_on_post_routes(self, client, candidate_user):
        token = _make_token(
            candidate_user.id, candidate_user.uname, role="", is_admin=False
        )
        headers = _auth_headers(token)

        for route in ADMIN_ONLY_POST_ROUTES:
            response = client.post(route, json={}, headers=headers)
            assert (
                response.status_code == 403
            ), f"Expected 403 on POST {route} for candidate, got {response.status_code}"


class TestAdminPassesThroughGate:
    """Admin users must NOT receive 401 or 403 on those same routes."""

    def test_admin_not_blocked_on_get_routes(self, client, admin_user):
        token = _make_token(
            admin_user.id, admin_user.uname, role="admin", is_admin=True
        )
        headers = _auth_headers(token)

        for route in ADMIN_ONLY_GET_ROUTES:
            response = client.get(route, headers=headers)
            assert response.status_code not in [
                401,
                403,
            ], f"Admin should not be blocked on GET {route}, got {response.status_code}"

    def test_admin_not_blocked_on_post_routes(self, client, admin_user):
        token = _make_token(
            admin_user.id, admin_user.uname, role="admin", is_admin=True
        )
        headers = _auth_headers(token)

        for route in ADMIN_ONLY_POST_ROUTES:
            response = client.post(route, json={}, headers=headers)
            assert response.status_code not in [
                401,
                403,
            ], f"Admin should not be blocked on POST {route}, got {response.status_code}"
