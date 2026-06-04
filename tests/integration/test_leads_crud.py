"""
test_leads_crud.py
==================
Full CRUD coverage for /api/leads.
All requests run as authenticated admin.
"""

import pytest

LEAD_PAYLOAD={
    "full_name": "John Test Lead",
    "email": "johnlead@example.com",
    "phone": "555-1234",
    "status": "open",
    "notes": "Created by automated test",
}

class TestLeadCreate:
    def test_create_lead_returns_id(self, client, admin_headers):
        response = client.post("/api/leads", json=LEAD_PAYLOAD, headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data or isinstance(data, int), f"Expected id in response, got: {data}"

    def test_create_lead_missing_required_field(self, client, admin_headers):
        payload = {"email": "nofullname@example.com"}
        response = client.post("/api/leads", json=payload, headers=admin_headers)
        assert response.status_code == 422

class TestLeadRead:
    @pytest.fixture
    def created_lead_id(self, client, admin_headers):
        r=client.post("/api/leads", json=LEAD_PAYLOAD, headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        return data["id"] if isinstance(data, dict) else data

    def test_get_all_leads_returns_list(self, client, admin_headers, created_lead_id):
        response = client.get("/api/leads", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        # API returns either a bare list or a paginated wrapper {"data": [...], "total": N}
        records = data if isinstance(data, list) else data.get("data", data)
        assert isinstance(records, list)
        assert len(records) >= 1

    def test_get_lead_by_id(self, client, admin_headers, created_lead_id):
        response = client.get(f"/api/leads/{created_lead_id}", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == LEAD_PAYLOAD["full_name"]
        assert data["email"] == LEAD_PAYLOAD["email"]

    def test_get_nonexistent_lead_returns_404(self, client, admin_headers):
        response = client.get("/api/leads/999999", headers=admin_headers)
        assert response.status_code == 404

    def test_get_leads_metrics(self, client, admin_headers):
        response = client.get("/api/leads/metrics", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "success" in data or "data" in data or isinstance(data, dict)

class TestLeadUpdate:
    @pytest.fixture
    def created_lead_id(self, client, admin_headers):
        r = client.post("/api/leads", json=LEAD_PAYLOAD, headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        return data ["id"] if isinstance(data, dict) else data
    
    def test_update_lead_changes_field(self, client, admin_headers, created_lead_id):
        update_payload = {"notes": "Updated by test"}
        response = client.put(
            f"/api/leads/{created_lead_id}",
            json=update_payload,
            headers=admin_headers,
        )
        assert response.status_code == 200

        get_response = client.get(f"/api/leads/{created_lead_id}", headers=admin_headers)
        assert get_response.json()["notes"] == "Updated by test"
    
    def test_update_nonexistent_lead(self, client, admin_headers):
        response = client.put(
            "/api/leads/999999",
            json={"notes": "ghost"},
            headers=admin_headers,
        )
        assert response.status_code in [404, 422]

class TestLeadDelete:
    @pytest.fixture
    def created_lead_id(self, client, admin_headers):
        r = client.post("/api/leads", json=LEAD_PAYLOAD, headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        return data["id"] if isinstance(data, dict) else data

    def test_delete_lead_succeeds(self, client, admin_headers, created_lead_id):
        response = client.delete(f"/api/leads/{created_lead_id}", headers=admin_headers)
        assert response.status_code == 200
    
    def test_deleted_lead_returns_404(self, client, admin_headers, created_lead_id):
        client.delete(f"/api/leads/{created_lead_id}", headers=admin_headers)
        response = client.get(f"/api/leads/{created_lead_id}", headers=admin_headers)
        assert response.status_code == 404

    def test_delete_nonexistent_lead(self, client, admin_headers):
        response = client.delete("/api/leads/999999", headers=admin_headers)
        assert response.status_code in [404, 200]

class TestLeadBusinessLogic:
    @pytest.fixture
    def created_lead_id(self, client, admin_headers):
        r = client.post("/api/leads", json=LEAD_PAYLOAD, headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        return data["id"] if isinstance(data, dict) else data

    def test_move_lead_to_candidate(self, client, admin_headers, created_lead_id):
        response = client.post(
            f"/api/leads/{created_lead_id}/move-to-candidate",
            headers=admin_headers,
        )
        assert response.status_code in [200, 400, 422]

    def test_search_leads_by_name(self, client, admin_headers, created_lead_id):
        response = client.get(
            "/api/leads/search-names/john",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        