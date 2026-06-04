"""
test_placements_and_commissions.py
===================================
Integration tests for placement commissions and their scheduler installments:
  - /api/placement-commission                          (list, create, get, update, delete)
  - /api/placement-commission/by-placement/{id}        (filter by placement)
  - /api/placement-commission-scheduler                (create, get, update, delete installment)
  - /api/placement-commission-scheduler/by-commission/{id}

Requires pre-seeded candidate, placement, and employee records.
All requests run as authenticated admin.
"""

import uuid
import pytest
from datetime import date
from decimal import Decimal

from fapi.db.models import (
    CandidateORM,
    EmployeeORM,
    CandidatePlacementORM,
)

# ---------------------------------------------------------------------------
# DB-level fixtures: seed the minimum required records for FK constraints
# ---------------------------------------------------------------------------

def _unique_email():
    return f"pc_{uuid.uuid4().hex[:8]}@test.com"


@pytest.fixture
def seeded_employee(db_session):
    """Insert a raw EmployeeORM to satisfy placement_commission.employee_id FK."""
    emp = EmployeeORM(
        name="Commission Employee",
        email=_unique_email(),
        phone="555-7001",
        status=1,
    )
    db_session.add(emp)
    db_session.commit()
    db_session.refresh(emp)
    return emp


@pytest.fixture
def seeded_candidate(db_session):
    """Insert a raw CandidateORM to satisfy candidate_placement.candidate_id FK."""
    cand = CandidateORM(
        full_name="Commission Candidate",
        email=_unique_email(),
        status="active",
        phone="555-8001",
    )
    db_session.add(cand)
    db_session.commit()
    db_session.refresh(cand)
    return cand


@pytest.fixture
def seeded_placement(db_session, seeded_candidate):
    """Insert a raw CandidatePlacementORM to satisfy placement_commission.placement_id FK."""
    placement = CandidatePlacementORM(
        candidate_id=seeded_candidate.id,
        company="Seed Placement Corp",
        placement_date=date(2026, 2, 1),
        status="Active",
    )
    db_session.add(placement)
    db_session.commit()
    db_session.refresh(placement)
    return placement


# ---------------------------------------------------------------------------
# Helper: create a commission via API and return its id
# ---------------------------------------------------------------------------

@pytest.fixture
def created_commission(client, admin_headers, seeded_placement, seeded_employee):
    payload = {
        "placement_id": seeded_placement.id,
        "employee_id": seeded_employee.id,
        "amount": "5000.00",
    }
    r = client.post("/api/placement-commission", json=payload, headers=admin_headers)
    assert r.status_code in [200, 201], f"Commission creation failed: {r.text}"
    return r.json().get("id")


# ===========================================================================
# 1. Placement Commission CRUD
# ===========================================================================

class TestPlacementCommissionCreate:
    def test_create_commission_returns_commission(
        self, client, admin_headers, seeded_placement, seeded_employee
    ):
        payload = {
            "placement_id": seeded_placement.id,
            "employee_id": seeded_employee.id,
            "amount": "3500.00",
        }
        response = client.post("/api/placement-commission", json=payload, headers=admin_headers)
        assert response.status_code in [200, 201], response.text
        data = response.json()
        assert data.get("placement_id") == seeded_placement.id
        assert data.get("employee_id") == seeded_employee.id

    def test_create_commission_missing_required_field_returns_422(
        self, client, admin_headers, seeded_placement
    ):
        # Missing employee_id
        payload = {"placement_id": seeded_placement.id, "amount": "1000.00"}
        response = client.post("/api/placement-commission", json=payload, headers=admin_headers)
        assert response.status_code == 422

    def test_duplicate_commission_same_placement_employee_returns_error(
        self, client, admin_headers, seeded_placement, seeded_employee
    ):
        """Unique constraint on (placement_id, employee_id) must block duplicates."""
        payload = {
            "placement_id": seeded_placement.id,
            "employee_id": seeded_employee.id,
            "amount": "2000.00",
        }
        r1 = client.post("/api/placement-commission", json=payload, headers=admin_headers)
        assert r1.status_code in [200, 201]
        r2 = client.post("/api/placement-commission", json=payload, headers=admin_headers)
        assert r2.status_code in [409, 422, 500]


class TestPlacementCommissionRead:
    def test_list_commissions_returns_list(self, client, admin_headers, created_commission):
        response = client.get("/api/placement-commission", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_commission_by_id(self, client, admin_headers, created_commission):
        response = client.get(f"/api/placement-commission/{created_commission}", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("id") == created_commission

    def test_get_nonexistent_commission_returns_404(self, client, admin_headers):
        response = client.get("/api/placement-commission/9999999", headers=admin_headers)
        assert response.status_code == 404

    def test_get_commissions_by_placement_id(
        self, client, admin_headers, created_commission, seeded_placement
    ):
        response = client.get(
            f"/api/placement-commission/by-placement/{seeded_placement.id}",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any(c.get("id") == created_commission for c in data)


class TestPlacementCommissionUpdate:
    def test_update_commission_amount(self, client, admin_headers, created_commission):
        payload = {"amount": "7500.00"}
        response = client.put(
            f"/api/placement-commission/{created_commission}",
            json=payload,
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert float(data.get("amount")) == 7500.00

    def test_update_nonexistent_commission_returns_404(self, client, admin_headers):
        response = client.put(
            "/api/placement-commission/9999999",
            json={"amount": "500.00"},
            headers=admin_headers,
        )
        assert response.status_code == 404


class TestPlacementCommissionDelete:
    def test_delete_commission_succeeds(
        self, client, admin_headers, seeded_placement, seeded_employee
    ):
        # Create a fresh one to safely delete
        payload = {
            "placement_id": seeded_placement.id,
            "employee_id": seeded_employee.id,
            "amount": "1234.00",
        }
        r = client.post("/api/placement-commission", json=payload, headers=admin_headers)
        assert r.status_code in [200, 201]
        cid = r.json().get("id")
        response = client.delete(f"/api/placement-commission/{cid}", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "deleted" in str(data).lower() or "message" in data

    def test_deleted_commission_returns_404(
        self, client, admin_headers, seeded_placement, seeded_employee
    ):
        payload = {
            "placement_id": seeded_placement.id,
            "employee_id": seeded_employee.id,
            "amount": "999.00",
        }
        r = client.post("/api/placement-commission", json=payload, headers=admin_headers)
        assert r.status_code in [200, 201]
        cid = r.json().get("id")
        client.delete(f"/api/placement-commission/{cid}", headers=admin_headers)
        response = client.get(f"/api/placement-commission/{cid}", headers=admin_headers)
        assert response.status_code == 404


# ===========================================================================
# 2. Commission Scheduler (Installments)
# ===========================================================================

class TestCommissionScheduler:
    @pytest.fixture
    def created_scheduler(self, client, admin_headers, created_commission):
        payload = {
            "placement_commission_id": created_commission,
            "installment_no": 1,
            "installment_amount": "2500.00",
            "scheduled_date": "2026-06-01",
            "payment_status": "Pending",
        }
        r = client.post(
            "/api/placement-commission-scheduler",
            json=payload,
            headers=admin_headers,
        )
        assert r.status_code in [200, 201], f"Scheduler creation failed: {r.text}"
        return r.json().get("id")

    def test_create_scheduler_entry(self, client, admin_headers, created_commission):
        payload = {
            "placement_commission_id": created_commission,
            "installment_no": 2,
            "installment_amount": "2500.00",
            "scheduled_date": "2026-07-01",
            "payment_status": "Pending",
        }
        response = client.post(
            "/api/placement-commission-scheduler",
            json=payload,
            headers=admin_headers,
        )
        assert response.status_code in [200, 201], response.text
        data = response.json()
        assert data.get("placement_commission_id") == created_commission

    def test_get_scheduler_by_id(self, client, admin_headers, created_scheduler):
        response = client.get(
            f"/api/placement-commission-scheduler/{created_scheduler}",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("id") == created_scheduler

    def test_list_schedulers_by_commission(self, client, admin_headers, created_commission, created_scheduler):
        response = client.get(
            f"/api/placement-commission-scheduler/by-commission/{created_commission}",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any(s.get("id") == created_scheduler for s in data)

    def test_update_scheduler_to_paid(self, client, admin_headers, created_scheduler):
        payload = {"payment_status": "Paid"}
        response = client.put(
            f"/api/placement-commission-scheduler/{created_scheduler}",
            json=payload,
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("payment_status") == "Paid"

    def test_get_nonexistent_scheduler_returns_404(self, client, admin_headers):
        response = client.get(
            "/api/placement-commission-scheduler/9999999",
            headers=admin_headers,
        )
        assert response.status_code == 404

    def test_delete_scheduler_entry(self, client, admin_headers, created_commission):
        # Create a fresh scheduler entry to delete
        payload = {
            "placement_commission_id": created_commission,
            "installment_no": 3,
            "installment_amount": "1000.00",
            "scheduled_date": "2026-08-01",
            "payment_status": "Pending",
        }
        r = client.post(
            "/api/placement-commission-scheduler",
            json=payload,
            headers=admin_headers,
        )
        assert r.status_code in [200, 201]
        sid = r.json().get("id")
        response = client.delete(
            f"/api/placement-commission-scheduler/{sid}",
            headers=admin_headers,
        )
        assert response.status_code == 200

    def test_placement_commission_math_sum(self, client, admin_headers, created_commission):
        """
        Verify that the sum of scheduler installments matches the total commission amount.
        If a developer modifies the logic of commission installment division, this mathematical
        contract ensures the ledger balance is maintained.
        """
        # 1. Fetch the parent commission and get its total amount
        commission_res = client.get(f"/api/placement-commission/{created_commission}", headers=admin_headers)
        assert commission_res.status_code == 200
        total_amount = Decimal(commission_res.json()["amount"])

        # 2. Add two installments to the scheduler
        inst1_payload = {
            "placement_commission_id": created_commission,
            "installment_no": 1,
            "installment_amount": str(total_amount / 2),
            "scheduled_date": "2026-07-01",
            "payment_status": "Pending",
        }
        inst2_payload = {
            "placement_commission_id": created_commission,
            "installment_no": 2,
            "installment_amount": str(total_amount / 2),
            "scheduled_date": "2026-08-01",
            "payment_status": "Pending",
        }
        
        r1 = client.post("/api/placement-commission-scheduler", json=inst1_payload, headers=admin_headers)
        r2 = client.post("/api/placement-commission-scheduler", json=inst2_payload, headers=admin_headers)
        assert r1.status_code in [200, 201]
        assert r2.status_code in [200, 201]

        # 3. Retrieve the scheduler list for this commission
        list_res = client.get(f"/api/placement-commission-scheduler/by-commission/{created_commission}", headers=admin_headers)
        assert list_res.status_code == 200
        installments = list_res.json()

        # 4. Assert sum of installments equals the total commission amount
        inst_sum = sum(Decimal(str(inst["installment_amount"])) for inst in installments)
        assert inst_sum == total_amount, f"ledger imbalance: expected {total_amount}, got {inst_sum}"

