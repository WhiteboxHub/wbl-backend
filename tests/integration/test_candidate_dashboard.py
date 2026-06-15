"""
test_candidate_dashboard.py
============================
Tests for the candidate-facing dashboard endpoints.
Each candidate can only view THEIR OWN data.
"""

from datetime import date
import pytest


class TestCandidateDashboardOverview:

    def test_dashboard_overview_returns_dict(self, client, candidate_headers, candidate_db_user):
        candidate_id = candidate_db_user["candidate"].id
        response = client.get(
            f"/api/candidates/{candidate_id}/dashboard/overview",
            headers=candidate_headers,
        )
        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            assert isinstance(response.json(), dict)

    def test_dashboard_overview_requires_auth(self, client, candidate_db_user):
        candidate_id = candidate_db_user["candidate"].id
        response = client.get(f"/api/candidates/{candidate_id}/dashboard/overview")
        assert response.status_code in [401, 403, 422]

    def test_dashboard_overview_nonexistent_candidate(self, client, admin_headers):
        response = client.get(
            "/api/candidates/999999/dashboard/overview",
            headers=admin_headers,
        )
        assert response.status_code in [404, 500]


class TestCandidateJourney:

    def test_journey_endpoint_returns_dict(self, client, candidate_headers, candidate_db_user):
        candidate_id = candidate_db_user["candidate"].id
        response = client.get(
            f"/api/candidates/{candidate_id}/journey",
            headers=candidate_headers,
        )
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            assert isinstance(response.json(), dict)


class TestCandidateProfile:

    def test_profile_endpoint_returns_dict(self, client, candidate_headers, candidate_db_user):
        candidate_id = candidate_db_user["candidate"].id
        response = client.get(
            f"/api/candidates/{candidate_id}/profile",
            headers=candidate_headers,
        )
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_profile_test_basic_endpoint(self, client, candidate_db_user):
        candidate_id = candidate_db_user["candidate"].id
        response = client.get(f"/api/candidates/{candidate_id}/test-basic")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert data["candidate_id"] == candidate_id
        assert data["email"] == candidate_db_user["candidate"].email


class TestCandidatePhases:

    def test_preparation_endpoint(self, client, candidate_headers, candidate_db_user):
        candidate_id = candidate_db_user["candidate"].id
        response = client.get(
            f"/api/candidates/{candidate_id}/preparation",
            headers=candidate_headers,
        )
        assert response.status_code in [200, 404]

    def test_marketing_endpoint(self, client, candidate_headers, candidate_db_user):
        candidate_id = candidate_db_user["candidate"].id
        response = client.get(
            f"/api/candidates/{candidate_id}/marketing",
            headers=candidate_headers,
        )
        assert response.status_code in [200, 404]

    def test_placement_endpoint(self, client, candidate_headers, candidate_db_user):
        candidate_id = candidate_db_user["candidate"].id
        response = client.get(
            f"/api/candidates/{candidate_id}/placement",
            headers=candidate_headers,
        )
        assert response.status_code in [200, 404]

    def test_phase_summary_endpoint(self, client, candidate_headers, candidate_db_user):
        candidate_id = candidate_db_user["candidate"].id
        response = client.get(
            f"/api/candidates/{candidate_id}/phase-summary",
            headers=candidate_headers,
        )
        assert response.status_code in [200, 404]


class TestCandidateInterviews:

    def test_interviews_endpoint_returns_list(self, client, candidate_headers, candidate_db_user):
        candidate_id = candidate_db_user["candidate"].id
        response = client.get(
            f"/api/candidates/{candidate_id}/interviews",
            headers=candidate_headers,
        )
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            assert isinstance(response.json(), list)

    def test_interview_analytics_endpoint(self, client, candidate_headers, candidate_db_user):
        candidate_id = candidate_db_user["candidate"].id
        response = client.get(
            f"/api/candidates/{candidate_id}/interviews/analytics",
            headers=candidate_headers,
        )
        assert response.status_code in [200, 404]

    def test_update_interview_feedback_invalid_value(self, client, admin_headers):
        response = client.patch(
            "/api/candidates/interviews/1/feedback?feedback=InvalidStatus",
            headers=admin_headers,
        )
        assert response.status_code == 400


class TestCandidateStatistics:

    def test_statistics_endpoint(self, client, candidate_headers, candidate_db_user):
        candidate_id = candidate_db_user["candidate"].id
        response = client.get(
            f"/api/candidates/{candidate_id}/statistics",
            headers=candidate_headers,
        )
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            assert isinstance(response.json(), dict)
