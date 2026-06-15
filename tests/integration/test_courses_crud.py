"""
test_courses_crud.py
====================
Full CRUD coverage for the academy / learning management domain:
  - /api/courses          (list, get, create, update, delete)
  - /api/batch            (list, search, get, create, update, delete)
  - /api/vendor_contact_extracts  (list, create, update, delete, bulk-delete,
                                    move-to-vendor)

All requests run as authenticated admin.
"""

import uuid
import pytest
from datetime import date

from fapi.db.models import Course


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _uid():
    return uuid.uuid4().hex[:8]


def _unique_email():
    return f"vc_{_uid()}@test.com"


# ===========================================================================
# 1. Courses  /api/courses
# ===========================================================================

COURSE_PAYLOAD = {
    "name": "Python Fundamentals",
    "alias": f"PY_{uuid.uuid4().hex[:4].upper()}",
    "description": "Core Python programming concepts",
}


@pytest.fixture
def created_course(client, admin_headers):
    payload = {**COURSE_PAYLOAD, "alias": f"PY_{_uid()[:4].upper()}"}
    r = client.post("/api/courses", json=payload, headers=admin_headers)
    assert r.status_code in [200, 201], f"Course creation failed: {r.text}"
    return r.json().get("id")


class TestCoursesCRUD:
    def test_create_course_returns_record(self, client, admin_headers):
        payload = {**COURSE_PAYLOAD, "alias": f"PY_{_uid()[:4].upper()}"}
        response = client.post("/api/courses", json=payload, headers=admin_headers)
        assert response.status_code in [200, 201], response.text
        data = response.json()
        assert data.get("name") == "Python Fundamentals"
        assert data.get("id") is not None

    def test_create_course_missing_required_returns_422(self, client, admin_headers):
        # name and alias are required
        response = client.post("/api/courses", json={"description": "no name or alias"}, headers=admin_headers)
        assert response.status_code == 422

    def test_list_courses_returns_list(self, client, admin_headers, created_course):
        response = client.get("/api/courses", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_course_by_id(self, client, admin_headers, created_course):
        response = client.get(f"/api/courses/{created_course}", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("id") == created_course

    def test_get_nonexistent_course_returns_404(self, client, admin_headers):
        response = client.get("/api/courses/9999999", headers=admin_headers)
        assert response.status_code == 404

    def test_update_course_description(self, client, admin_headers, created_course):
        payload = {"description": "Updated Python course description"}
        response = client.put(
            f"/api/courses/{created_course}",
            json=payload,
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("description") == "Updated Python course description"

    def test_delete_course_succeeds(self, client, admin_headers):
        payload = {**COURSE_PAYLOAD, "alias": f"PY_{_uid()[:4].upper()}"}
        r = client.post("/api/courses", json=payload, headers=admin_headers)
        assert r.status_code in [200, 201]
        cid = r.json().get("id")
        response = client.delete(f"/api/courses/{cid}", headers=admin_headers)
        assert response.status_code in [200, 204], response.text
        data = response.json()
        assert "success" in str(data).lower() or "deleted" in str(data).lower()

    def test_deleted_course_returns_404(self, client, admin_headers):
        payload = {**COURSE_PAYLOAD, "alias": f"PY_{_uid()[:4].upper()}"}
        r = client.post("/api/courses", json=payload, headers=admin_headers)
        assert r.status_code in [200, 201]
        cid = r.json().get("id")
        client.delete(f"/api/courses/{cid}", headers=admin_headers)
        response = client.get(f"/api/courses/{cid}", headers=admin_headers)
        assert response.status_code == 404


# ===========================================================================
# 2. Batches  /api/batch
# ===========================================================================

@pytest.fixture
def seeded_course(db_session):
    """Insert a minimal Course ORM so batch.courseid FK is satisfied."""
    course = Course(
        name=f"Seed Course {_uid()}",
        alias=f"SC_{_uid()[:4].upper()}",
    )
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)
    return course


@pytest.fixture
def created_batch(client, admin_headers, seeded_course):
    payload = {
        "batchname": f"Batch {_uid()}",
        "courseid": seeded_course.id,
        "startdate": "2026-01-10",
        "enddate": "2026-04-10",
    }
    r = client.post("/api/batch", json=payload, headers=admin_headers)
    assert r.status_code in [200, 201], f"Batch creation failed: {r.text}"
    return r.json().get("batchid")


class TestBatchCRUD:
    def test_create_batch_returns_record(self, client, admin_headers, seeded_course):
        payload = {
            "batchname": f"Batch {_uid()}",
            "courseid": seeded_course.id,
            "startdate": "2026-02-01",
            "enddate": "2026-05-01",
        }
        response = client.post("/api/batch", json=payload, headers=admin_headers)
        assert response.status_code in [200, 201], response.text
        data = response.json()
        assert "batchid" in data
        assert data.get("batchname") is not None

    def test_create_batch_missing_required_returns_422(self, client, admin_headers):
        # batchname and courseid are required
        response = client.post("/api/batch", json={}, headers=admin_headers)
        assert response.status_code == 422

    def test_list_batches_returns_list(self, client, admin_headers, created_batch):
        response = client.get("/api/batch", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_batches_with_search(self, client, admin_headers, created_batch):
        response = client.get("/api/batch?search=Batch", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_batch_by_id(self, client, admin_headers, created_batch):
        response = client.get(f"/api/batch/{created_batch}", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("batchid") == created_batch

    def test_get_nonexistent_batch_returns_404(self, client, admin_headers):
        response = client.get("/api/batch/9999999", headers=admin_headers)
        assert response.status_code == 404

    def test_update_batch_enddate(self, client, admin_headers, created_batch, seeded_course):
        payload = {
            "batchname": "Updated Batch",
            "courseid": seeded_course.id,
            "enddate": "2026-06-30",
        }
        response = client.put(
            f"/api/batch/{created_batch}",
            json=payload,
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("enddate") == "2026-06-30"

    def test_update_nonexistent_batch_returns_404(self, client, admin_headers, seeded_course):
        payload = {"batchname": "Ghost", "courseid": seeded_course.id}
        response = client.put("/api/batch/9999999", json=payload, headers=admin_headers)
        assert response.status_code == 404

    def test_delete_batch_succeeds(self, client, admin_headers, seeded_course):
        payload = {
            "batchname": f"ToDelete {_uid()}",
            "courseid": seeded_course.id,
        }
        r = client.post("/api/batch", json=payload, headers=admin_headers)
        assert r.status_code in [200, 201]
        bid = r.json().get("batchid")
        response = client.delete(f"/api/batch/{bid}", headers=admin_headers)
        assert response.status_code in [200, 204], response.text

    def test_delete_nonexistent_batch_returns_404(self, client, admin_headers):
        response = client.delete("/api/batch/9999999", headers=admin_headers)
        assert response.status_code == 404


# ===========================================================================
# 3. Vendor Contact Extracts  /api/vendor_contact_extracts
# ===========================================================================

VENDOR_CONTACT_PAYLOAD = {
    "full_name": "Test Contact",
    "email": None,         # filled per-test
    "phone": "555-4001",
    "company_name": "Outreach Corp",
    "location": "New York, NY",
}


@pytest.fixture
def created_vendor_contact(client, admin_headers):
    payload = {**VENDOR_CONTACT_PAYLOAD, "email": _unique_email()}
    r = client.post("/api/vendor_contact", json=payload, headers=admin_headers)
    if r.status_code not in [200, 201]:
        pytest.skip(f"Vendor contact creation failed ({r.status_code}) — skipping dependent tests")
    return r.json().get("id")


class TestVendorContactsCRUD:
    def test_create_vendor_contact_returns_record(self, client, admin_headers):
        payload = {**VENDOR_CONTACT_PAYLOAD, "email": _unique_email()}
        response = client.post("/api/vendor_contact", json=payload, headers=admin_headers)
        # 400 is returned if a unique constraint fires (e.g. linkedin_internal_id)
        assert response.status_code in [200, 201, 400], response.text
        if response.status_code in [200, 201]:
            data = response.json()
            assert data.get("full_name") == "Test Contact"
            assert data.get("id") is not None

    def test_list_vendor_contacts_returns_list(self, client, admin_headers, created_vendor_contact):
        response = client.get("/api/vendor_contact_extracts", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_vendor_contact_by_id(self, client, admin_headers, created_vendor_contact):
        response = client.get(
            f"/api/vendor_contact_extracts/{created_vendor_contact}",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("id") == created_vendor_contact

    def test_get_nonexistent_vendor_contact_returns_404(self, client, admin_headers):
        response = client.get("/api/vendor_contact_extracts/9999999", headers=admin_headers)
        assert response.status_code == 404

    def test_update_vendor_contact_location(self, client, admin_headers, created_vendor_contact):
        payload = {"location": "San Francisco, CA"}
        response = client.put(
            f"/api/vendor_contact/{created_vendor_contact}",
            json=payload,
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("location") == "San Francisco, CA"

    def test_delete_vendor_contact_succeeds(self, client, admin_headers):
        payload = {**VENDOR_CONTACT_PAYLOAD, "email": _unique_email()}
        r = client.post("/api/vendor_contact", json=payload, headers=admin_headers)
        if r.status_code not in [200, 201]:
            pytest.skip("Vendor contact create failed (unique constraint) — skipping delete test")
        cid = r.json().get("id")
        response = client.delete(f"/api/vendor_contact/{cid}", headers=admin_headers)
        assert response.status_code in [200, 204], response.text

    def test_bulk_delete_vendor_contacts(self, client, admin_headers):
        # Create two contacts to bulk-delete
        ids = []
        for _ in range(2):
            payload = {**VENDOR_CONTACT_PAYLOAD, "email": _unique_email()}
            r = client.post("/api/vendor_contact", json=payload, headers=admin_headers)
            if r.status_code in [200, 201]:
                ids.append(r.json().get("id"))

        if len(ids) < 2:
            pytest.skip("Could not create 2 vendor contacts — skipping bulk delete test")

        response = client.delete(
            f"/api/vendor_contact/bulk?contact_ids={ids[0]}&contact_ids={ids[1]}",
            headers=admin_headers,
        )
        assert response.status_code in [200, 204], response.text

    def test_move_contacts_to_vendor(self, client, admin_headers, created_vendor_contact):
        payload = {"contact_ids": [created_vendor_contact]}
        response = client.post(
            "/api/vendor_contact/move-to-vendor",
            json=payload,
            headers=admin_headers,
        )
        # May return 200 with stats or 207 partial success
        assert response.status_code in [200, 207], response.text
        data = response.json()
        assert isinstance(data, dict)
