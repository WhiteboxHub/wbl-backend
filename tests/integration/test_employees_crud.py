"""
test_employees_crud.py
======================
Full CRUD coverage for employee routes:
  - /api/employees            (list, create, update, delete)
  - /api/employees/search     (search by query string)
  - /api/employees/{id}/candidates
  - /api/employees/{id}/tasks
  - /api/employees/{id}/placements
  - /api/employees/{id}/session-class-data
  - /api/employee-birthdays
  - /api/employee-tasks/     (task CRUD)

All standard CRUD routes run as authenticated admin.
"""

import uuid
import pytest
from datetime import date

# ---------------------------------------------------------------------------
# Shared payloads
# ---------------------------------------------------------------------------

def _unique_email():
    return f"emp_{uuid.uuid4().hex[:8]}@company.com"

EMPLOYEE_PAYLOAD = {
    "name": "Test Employee",
    "email": None,          # filled per-test to avoid UNIQUE constraint violations
    "phone": "555-3001",
    "status": 1,
}

TASK_PAYLOAD = {
    "employee_id": None,    # filled by fixture
    "task": "Review onboarding documents",
    "assigned_date": "2026-05-01",
    "due_date": "2026-05-15",
    "status": "pending",
    "priority": "high",
}


# ---------------------------------------------------------------------------
# Helper fixture: create a fresh employee, return its id
# ---------------------------------------------------------------------------

@pytest.fixture
def created_employee(client, admin_headers):
    payload = {**EMPLOYEE_PAYLOAD, "email": _unique_email()}
    r = client.post("/api/employees", json=payload, headers=admin_headers)
    assert r.status_code in [200, 201], f"Employee creation failed: {r.text}"
    data = r.json()
    eid = data.get("id") if isinstance(data, dict) else data
    assert eid is not None
    return eid


# ===========================================================================
# 1. Employee CRUD
# ===========================================================================

class TestEmployeeCreate:
    def test_create_employee_returns_employee(self, client, admin_headers):
        payload = {**EMPLOYEE_PAYLOAD, "email": _unique_email()}
        response = client.post("/api/employees", json=payload, headers=admin_headers)
        assert response.status_code in [200, 201], response.text
        data = response.json()
        assert data.get("name") == "Test Employee"

    def test_create_employee_duplicate_email_returns_409(self, client, admin_headers):
        email = _unique_email()
        payload = {**EMPLOYEE_PAYLOAD, "email": email}
        r1 = client.post("/api/employees", json=payload, headers=admin_headers)
        assert r1.status_code in [200, 201]
        r2 = client.post("/api/employees", json=payload, headers=admin_headers)
        assert r2.status_code == 409

    def test_create_employee_missing_name_returns_422(self, client, admin_headers):
        payload = {"email": _unique_email(), "phone": "555-0000"}
        response = client.post("/api/employees", json=payload, headers=admin_headers)
        assert response.status_code == 422


class TestEmployeeRead:
    def test_list_employees_returns_list(self, client, admin_headers, created_employee):
        response = client.get("/api/employees", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_search_employees_returns_results(self, client, admin_headers, created_employee):
        response = client.get("/api/employees/search?query=Test", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_search_employees_empty_query_returns_all(self, client, admin_headers, created_employee):
        response = client.get("/api/employees/search", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestEmployeeUpdate:
    def test_update_employee_phone(self, client, admin_headers, created_employee):
        payload = {"phone": "555-UPDATED", "name": "Test Employee"}
        response = client.put(
            f"/api/employees/{created_employee}",
            json=payload,
            headers=admin_headers,
        )
        assert response.status_code in [200, 204], response.text

    def test_update_nonexistent_employee_returns_404(self, client, admin_headers):
        payload = {"name": "Ghost Employee", "email": _unique_email()}
        response = client.put("/api/employees/9999999", json=payload, headers=admin_headers)
        assert response.status_code == 404


class TestEmployeeDelete:
    def test_delete_employee_succeeds(self, client, admin_headers):
        payload = {**EMPLOYEE_PAYLOAD, "email": _unique_email()}
        r = client.post("/api/employees", json=payload, headers=admin_headers)
        assert r.status_code in [200, 201]
        eid = r.json().get("id")
        response = client.delete(f"/api/employees/{eid}", headers=admin_headers)
        assert response.status_code in [200, 204], response.text

    def test_delete_nonexistent_employee_returns_404(self, client, admin_headers):
        response = client.delete("/api/employees/9999999", headers=admin_headers)
        assert response.status_code == 404


# ===========================================================================
# 2. Employee Sub-resource Endpoints
# ===========================================================================

class TestEmployeeSubResources:
    def test_employee_candidates_returns_dict(self, client, admin_headers, created_employee):
        response = client.get(f"/api/employees/{created_employee}/candidates", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_employee_tasks_returns_list(self, client, admin_headers, created_employee):
        response = client.get(f"/api/employees/{created_employee}/tasks", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_employee_placements_returns_data(self, client, admin_headers, created_employee):
        response = client.get(f"/api/employees/{created_employee}/placements", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        # get_employee_placements returns either a list or a dict with count/names keys
        assert isinstance(data, (list, dict))

    def test_employee_session_class_data_returns_timeline(self, client, admin_headers, created_employee):
        response = client.get(
            f"/api/employees/{created_employee}/session-class-data",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "timeline" in data or "class_count" in data

    def test_employee_jobs_returns_list(self, client, admin_headers, created_employee):
        response = client.get(f"/api/employees/{created_employee}/jobs", headers=admin_headers)
        assert response.status_code == 200

    def test_employee_birthdays_endpoint(self, client, admin_headers):
        response = client.get("/api/employee-birthdays", headers=admin_headers)
        assert response.status_code == 200

    def test_nonexistent_employee_candidates_returns_404(self, client, admin_headers):
        response = client.get("/api/employees/9999999/candidates", headers=admin_headers)
        assert response.status_code == 404


# ===========================================================================
# 3. Employee Tasks CRUD (/api/employee-tasks/)
# ===========================================================================

class TestEmployeeTasksCRUD:
    @pytest.fixture
    def created_task(self, client, admin_headers, created_employee):
        payload = {**TASK_PAYLOAD, "employee_id": created_employee}
        r = client.post("/api/employee-tasks/", json=payload, headers=admin_headers)
        assert r.status_code in [200, 201], f"Task creation failed: {r.text}"
        return r.json().get("id")

    def test_create_task_returns_task(self, client, admin_headers, created_employee):
        payload = {**TASK_PAYLOAD, "employee_id": created_employee}
        response = client.post("/api/employee-tasks/", json=payload, headers=admin_headers)
        assert response.status_code in [200, 201], response.text
        data = response.json()
        assert data.get("task") == TASK_PAYLOAD["task"]
        assert data.get("employee_id") == created_employee

    def test_list_tasks_returns_list(self, client, admin_headers, created_task):
        response = client.get("/api/employee-tasks/", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_tasks_filtered_by_employee(self, client, admin_headers, created_employee, created_task):
        response = client.get(
            f"/api/employee-tasks/?employee_id={created_employee}",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_update_task_status(self, client, admin_headers, created_task):
        payload = {"status": "completed"}
        response = client.put(
            f"/api/employee-tasks/{created_task}",
            json=payload,
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "completed"

    def test_update_nonexistent_task_returns_404(self, client, admin_headers):
        response = client.put(
            "/api/employee-tasks/9999999",
            json={"status": "done"},
            headers=admin_headers,
        )
        assert response.status_code == 404

    def test_delete_task_succeeds(self, client, admin_headers, created_task):
        response = client.delete(f"/api/employee-tasks/{created_task}", headers=admin_headers)
        assert response.status_code in [200, 204], response.text

    def test_delete_nonexistent_task_returns_404(self, client, admin_headers):
        response = client.delete("/api/employee-tasks/9999999", headers=admin_headers)
        assert response.status_code == 404
