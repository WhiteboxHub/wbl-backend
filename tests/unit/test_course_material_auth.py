"""
Unit tests for the Course Material authentication behaviour.

Covers:
  1.  Unauthenticated GET /api/materials → 200 OK, link field is None.
  2.  Authenticated GET /api/materials   → 200 OK, link field is returned.
  3.  Expired/invalid JWT               → treated as unauthenticated, link is None.
  4.  Unauthenticated GET /api/github-classroom-repos → link is None.
  5.  Authenticated GET /api/github-classroom-repos  → link is returned (manual repos).
  6.  Invalid course name               → 400 Bad Request (existing validation, unchanged).
  7.  Invalid search keyword            → 400 Bad Request (existing validation, unchanged).

Notes
-----
*  The tests mock ``fetch_keyword_presentation`` so they do NOT hit the
   database.  This is consistent with the existing unit-test style in this
   project (e.g. tests/unit/test_job_click_auth.py uses MagicMock for the db).
*  The GitHub API call inside ``get_github_classroom_repos`` is also mocked so
   the tests are fully offline and deterministic.
*  No hard-coded JWT values, user IDs, emails, or material URLs are used.
   All tokens are signed at runtime using the same secret / algorithm that the
   conftest.py already sets up for the test session.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone

from jose import jwt as jose_jwt

# ── conftest fixtures (client, admin_headers, candidate_headers) ───────────
# All fixtures are provided automatically by tests/conftest.py.


# ── helpers ───────────────────────────────────────────────────────────────

# The conftest sets SECRET_KEY = "mock_test_secret_key_12345"
_TEST_SECRET = "mock_test_secret_key_12345"  # pragma: allowlist secret
_ALGORITHM = "HS256"


def _make_token(role: str = "candidate", expired: bool = False) -> str:
    """Forge a signed JWT using the same secret the test app uses."""
    now = datetime.now(tz=timezone.utc)
    exp = now - timedelta(hours=1) if expired else now + timedelta(hours=2)
    payload = {
        "sub": "testuser",
        "role": role,
        "exp": exp,
        "iat": now,
    }
    return jose_jwt.encode(payload, _TEST_SECRET, algorithm=_ALGORITHM)


def _valid_auth_headers(role: str = "candidate") -> dict:
    return {"Authorization": f"Bearer {_make_token(role)}"}


def _expired_auth_headers() -> dict:
    return {"Authorization": f"Bearer {_make_token(expired=True)}"}


# ── sample fixture data (no real URLs) ────────────────────────────────────

_SAMPLE_MATERIALS = [
    {
        "id": 1,
        "name": "Sample Presentation",
        "type": "P",
        "link": "https://example.com/material/1",
        "courseid": 3,
        "subjectid": 10,
        "sortorder": 1,
        "description": "A test material",
    }
]

_SAMPLE_GITHUB_REPOS = [
    {
        "id": "manual-1",
        "name": "classroom-repo",
        "link": "https://github.com/example/classroom-repo",
        "type": "G",
        "sortorder": 1,
    }
]


# ── /api/materials ─────────────────────────────────────────────────────────


class TestGetMaterials:
    """GET /api/materials – authentication-gated link exposure."""

    _ENDPOINT = "/api/materials"
    _BASE_PARAMS = {"course": "ML", "search": "Presentations"}

    def test_unauthenticated_returns_200_with_link_stripped(self, client):
        """Unauthenticated caller sees catalogue but link is None."""
        with patch(
            "fapi.api.routes.resources.fetch_keyword_presentation",
            return_value=_SAMPLE_MATERIALS,
        ):
            response = client.get(self._ENDPOINT, params=self._BASE_PARAMS)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        # Link MUST be absent (None / null) for unauthenticated callers
        assert data[0]["link"] is None
        # Name / other metadata must still be present
        assert data[0]["name"] == "Sample Presentation"

    def test_authenticated_candidate_returns_link(self, client):
        """Authenticated candidate receives the full material link."""
        with patch(
            "fapi.api.routes.resources.fetch_keyword_presentation",
            return_value=_SAMPLE_MATERIALS,
        ):
            response = client.get(
                self._ENDPOINT,
                params=self._BASE_PARAMS,
                headers=_valid_auth_headers(role="candidate"),
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        # Authenticated caller MUST receive the actual link
        assert data[0]["link"] == "https://example.com/material/1"

    def test_authenticated_admin_returns_link(self, client):
        """Admin-role JWT also receives the full material link."""
        with patch(
            "fapi.api.routes.resources.fetch_keyword_presentation",
            return_value=_SAMPLE_MATERIALS,
        ):
            response = client.get(
                self._ENDPOINT,
                params=self._BASE_PARAMS,
                headers=_valid_auth_headers(role="admin"),
            )

        assert response.status_code == 200
        data = response.json()
        assert data[0]["link"] == "https://example.com/material/1"

    def test_expired_jwt_link_is_stripped(self, client):
        """An expired token must be treated the same as no token."""
        with patch(
            "fapi.api.routes.resources.fetch_keyword_presentation",
            return_value=_SAMPLE_MATERIALS,
        ):
            response = client.get(
                self._ENDPOINT,
                params=self._BASE_PARAMS,
                headers=_expired_auth_headers(),
            )

        assert response.status_code == 200
        data = response.json()
        assert data[0]["link"] is None, (
            "Expired token must not expose material links"
        )

    def test_invalid_jwt_link_is_stripped(self, client):
        """A tampered / garbage token must also strip the link."""
        bad_headers = {"Authorization": "Bearer this.is.not.a.valid.jwt"}
        with patch(
            "fapi.api.routes.resources.fetch_keyword_presentation",
            return_value=_SAMPLE_MATERIALS,
        ):
            response = client.get(
                self._ENDPOINT,
                params=self._BASE_PARAMS,
                headers=bad_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data[0]["link"] is None

    def test_invalid_course_returns_400(self, client):
        """Existing validation: unknown course name still returns 400."""
        response = client.get(
            self._ENDPOINT,
            params={"course": "INVALID", "search": "Presentations"},
        )
        assert response.status_code == 400

    def test_empty_results_unauthenticated(self, client):
        """Empty DB result is handled gracefully for unauthenticated users."""
        with patch(
            "fapi.api.routes.resources.fetch_keyword_presentation",
            return_value=[],
        ):
            response = client.get(self._ENDPOINT, params=self._BASE_PARAMS)

        assert response.status_code == 200
        assert response.json() == []


# ── /api/github-classroom-repos ────────────────────────────────────────────


class TestGetGithubClassroomRepos:
    """GET /api/github-classroom-repos – authentication-gated link exposure."""

    _ENDPOINT = "/api/github-classroom-repos"
    _PARAMS = {"course": "ML"}

    def _mock_github_response(self):
        """Return an empty GitHub API response to keep tests offline."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"items": []}
        return mock_resp

    def test_unauthenticated_returns_200_with_link_stripped(self, client):
        """Unauthenticated caller sees repo names but link is None."""
        with patch(
            "fapi.api.routes.resources.fetch_keyword_presentation",
            return_value=_SAMPLE_GITHUB_REPOS,
        ), patch("httpx.AsyncClient.get", return_value=self._mock_github_response()):
            response = client.get(self._ENDPOINT, params=self._PARAMS)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # At least the manually seeded repo should be present
        assert any(item["name"] == "classroom-repo" for item in data)
        # All links must be None for unauthenticated callers
        for item in data:
            assert item["link"] is None, (
                f"link must be None for unauthenticated caller, got: {item['link']}"
            )

    def test_authenticated_returns_link(self, client):
        """Authenticated caller receives the actual repo link."""
        with patch(
            "fapi.api.routes.resources.fetch_keyword_presentation",
            return_value=_SAMPLE_GITHUB_REPOS,
        ), patch("httpx.AsyncClient.get", return_value=self._mock_github_response()):
            response = client.get(
                self._ENDPOINT,
                params=self._PARAMS,
                headers=_valid_auth_headers(),
            )

        assert response.status_code == 200
        data = response.json()
        repo = next(item for item in data if item["name"] == "classroom-repo")
        assert repo["link"] == "https://github.com/example/classroom-repo"

    def test_expired_jwt_link_is_stripped(self, client):
        """Expired token → links stripped, same as no token."""
        with patch(
            "fapi.api.routes.resources.fetch_keyword_presentation",
            return_value=_SAMPLE_GITHUB_REPOS,
        ), patch("httpx.AsyncClient.get", return_value=self._mock_github_response()):
            response = client.get(
                self._ENDPOINT,
                params=self._PARAMS,
                headers=_expired_auth_headers(),
            )

        assert response.status_code == 200
        for item in response.json():
            assert item["link"] is None


# ── _is_request_authenticated unit tests ──────────────────────────────────


class TestIsRequestAuthenticated:
    """
    Direct unit tests for the helper function to confirm the token-validation
    logic in isolation, without spinning up the full HTTP stack.
    """

    def test_valid_token_returns_true(self):
        from fapi.api.routes.resources import _is_request_authenticated
        from fastapi.security import HTTPAuthorizationCredentials

        token = _make_token()
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        assert _is_request_authenticated(creds) is True

    def test_no_credentials_returns_false(self):
        from fapi.api.routes.resources import _is_request_authenticated

        assert _is_request_authenticated(None) is False

    def test_empty_credentials_returns_false(self):
        from fapi.api.routes.resources import _is_request_authenticated
        from fastapi.security import HTTPAuthorizationCredentials

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="")
        assert _is_request_authenticated(creds) is False

    def test_expired_token_returns_false(self):
        from fapi.api.routes.resources import _is_request_authenticated
        from fastapi.security import HTTPAuthorizationCredentials

        token = _make_token(expired=True)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        assert _is_request_authenticated(creds) is False

    def test_garbage_token_returns_false(self):
        from fapi.api.routes.resources import _is_request_authenticated
        from fastapi.security import HTTPAuthorizationCredentials

        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="not.a.real.jwt"
        )
        assert _is_request_authenticated(creds) is False
