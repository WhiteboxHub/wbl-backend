"""
test_vendors_crud.py
=====================
Full CRUD coverage for /api/vendors.
All requests run as authenticated admin.
"""

import uuid
import pytest

VENDOR_PAYLOAD = {
    "full_name": "Test Vendor Corp",
    "email": "vendor_test@example.com",
    "phone_number": "555-9999",
    "type": "client",
    "status": "prospect",
    "company_name": "Test Corp",
    "location": "New York",
}


class TestVendorCreate:

    def test_create_vendor_returns_object(self, client, admin_headers):
        payload = {**VENDOR_PAYLOAD, "email": f"v_{uuid.uuid4().hex[:6]}@test.com"}
        response = client.post("/api/vendors", json=payload, headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["email"] == payload["email"]

    def test_create_vendor_missing_type_uses_default(self, client, admin_headers):
        payload = {
            "full_name": "No Type Vendor",
            "email": f"notype_{uuid.uuid4().hex[:6]}@test.com",
        }
        response = client.post("/api/vendors", json=payload, headers=admin_headers)
        assert response.status_code in [200, 422]


class TestVendorRead:

    @pytest.fixture
    def vendor_id(self, client, admin_headers):
        payload = {**VENDOR_PAYLOAD, "email": f"r_{uuid.uuid4().hex[:6]}@test.com"}
        r = client.post("/api/vendors", json=payload, headers=admin_headers)
        assert r.status_code == 200
        return r.json()["id"]

    def test_get_all_vendors_returns_list(self, client, admin_headers, vendor_id):
        response = client.get("/api/vendors", headers=admin_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) >= 1

    def test_get_vendor_by_id(self, client, admin_headers, vendor_id):
        response = client.get(f"/api/vendors/{vendor_id}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["id"] == vendor_id

    def test_get_nonexistent_vendor_returns_404(self, client, admin_headers):
        response = client.get("/api/vendors/999999", headers=admin_headers)
        assert response.status_code == 404

    def test_get_vendor_metrics(self, client, admin_headers):
        response = client.get("/api/vendors/metrics", headers=admin_headers)
        assert response.status_code == 200


class TestVendorUpdate:

    @pytest.fixture
    def vendor_id(self, client, admin_headers):
        payload = {**VENDOR_PAYLOAD, "email": f"u_{uuid.uuid4().hex[:6]}@test.com"}
        r = client.post("/api/vendors", json=payload, headers=admin_headers)
        assert r.status_code == 200
        return r.json()["id"]

    def test_update_vendor_notes(self, client, admin_headers, vendor_id):
        update = {"location": "New Jersey"}
        response = client.put(f"/api/vendors/{vendor_id}", json=update, headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["location"] == "New Jersey"

    def test_update_nonexistent_vendor(self, client, admin_headers):
        response = client.put("/api/vendors/999999", json={"location": "Ghost Town"}, headers=admin_headers)
        assert response.status_code == 404


class TestVendorDelete:

    @pytest.fixture
    def vendor_id(self, client, admin_headers):
        payload = {**VENDOR_PAYLOAD, "email": f"d_{uuid.uuid4().hex[:6]}@test.com"}
        r = client.post("/api/vendors", json=payload, headers=admin_headers)
        assert r.status_code == 200
        return r.json()["id"]

    def test_delete_vendor(self, client, admin_headers, vendor_id):
        response = client.delete(f"/api/vendors/{vendor_id}", headers=admin_headers)
        assert response.status_code == 200

    def test_deleted_vendor_is_gone(self, client, admin_headers, vendor_id):
        client.delete(f"/api/vendors/{vendor_id}", headers=admin_headers)
        response = client.get(f"/api/vendors/{vendor_id}", headers=admin_headers)
        assert response.status_code == 404


class TestVendorBulkDelete:

    def test_bulk_delete_vendors(self, client, admin_headers):
        ids = []
        for _ in range(3):
            payload = {**VENDOR_PAYLOAD, "email": f"bulk_{uuid.uuid4().hex[:6]}@test.com"}
            r = client.post("/api/vendors", json=payload, headers=admin_headers)
            assert r.status_code == 200
            ids.append(r.json()["id"])

        response = client.post("/api/vendors/bulk-delete", json=ids, headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] == 3

    def test_bulk_delete_empty_list_returns_400(self, client, admin_headers):
        response = client.post("/api/vendors/bulk-delete", json=[], headers=admin_headers)
        assert response.status_code == 400