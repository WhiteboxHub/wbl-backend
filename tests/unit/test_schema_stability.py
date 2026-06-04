"""
test_schema_stability.py
========================
Tests the core database and API request/response schemas defined in Pydantic.
Verifies that required fields raise ValidationError when missing, custom validators
behave as expected (like date cleanups, agreement normalizations, email normalizations),
and no field names/types are accidentally refactored.
"""

import pytest
from pydantic import ValidationError
from datetime import date
from fapi.db.schemas import (
    EmployeeCreate,
    CandidateCreate,
    CandidateMarketingCreate,
    CandidatePlacementCreate,
    JobListingCreate,
)

# ---------------------------------------------------------------------------
# 1. EmployeeCreate Tests
# ---------------------------------------------------------------------------


def test_employee_create_required_fields():
    # 'name' and 'email' are required
    with pytest.raises(ValidationError) as exc_info:
        EmployeeCreate()  # missing both
    errors = exc_info.value.errors()
    missing_fields = {err["loc"][0] for err in errors}
    assert "name" in missing_fields
    assert "email" in missing_fields


def test_employee_create_valid():
    emp = EmployeeCreate(
        name="John Doe", email="john@example.com", phone="123-456-7890"
    )
    assert emp.name == "John Doe"
    assert emp.email == "john@example.com"
    assert emp.phone == "123-456-7890"


def test_employee_date_normalization():
    # Test handle_invalid_dates validator
    emp1 = EmployeeCreate(name="John Doe", email="john@example.com", dob="")
    assert emp1.dob is None

    emp2 = EmployeeCreate(name="John Doe", email="john@example.com", dob="0000-00-00")
    assert emp2.dob is None

    emp3 = EmployeeCreate(name="John Doe", email="john@example.com", dob=None)
    assert emp3.dob is None

    emp4 = EmployeeCreate(
        name="John Doe", email="john@example.com", dob=date(1995, 5, 15)
    )
    assert emp4.dob == date(1995, 5, 15)


# ---------------------------------------------------------------------------
# 2. CandidateCreate Tests
# ---------------------------------------------------------------------------


def test_candidate_create_fields():
    candidate = CandidateCreate(
        full_name="Jane Smith",
        email="jane@example.com",
        phone="987-654-3210",
        agreement=True,
        status="active",
    )
    assert candidate.full_name == "Jane Smith"
    assert candidate.email == "jane@example.com"
    # normalize_agreement: True -> "Y"
    assert candidate.agreement == "Y"

    candidate_false = CandidateCreate(
        full_name="Jane Smith",
        agreement=False,
    )
    assert candidate_false.agreement == "N"

    candidate_str = CandidateCreate(
        full_name="Jane Smith",
        agreement="Maybe",
    )
    assert candidate_str.agreement == "Maybe"


# ---------------------------------------------------------------------------
# 3. CandidateMarketingCreate Tests
# ---------------------------------------------------------------------------


def test_candidate_marketing_create_json_validation():
    # 1. Dictionary input
    marketing_dict = CandidateMarketingCreate(
        candidate_id=1,
        start_date=date(2026, 1, 1),
        candidate_json={"skills": ["Python", "FastAPI"]},
    )
    assert marketing_dict.candidate_json == {"skills": ["Python", "FastAPI"]}

    # 2. Valid JSON String input
    marketing_str = CandidateMarketingCreate(
        candidate_id=1,
        start_date=date(2026, 1, 1),
        candidate_json='{"skills": ["Python", "FastAPI"]}',
    )
    assert marketing_str.candidate_json == {"skills": ["Python", "FastAPI"]}

    # 3. Empty string should return None
    marketing_empty = CandidateMarketingCreate(
        candidate_id=1,
        start_date=date(2026, 1, 1),
        candidate_json="   ",
    )
    assert marketing_empty.candidate_json is None

    # 4. Invalid JSON string raises ValidationError
    with pytest.raises(ValidationError) as exc_info:
        CandidateMarketingCreate(
            candidate_id=1,
            start_date=date(2026, 1, 1),
            candidate_json="invalid json string",
        )
    assert "Invalid JSON string for candidate_json" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 4. CandidatePlacementCreate Tests
# ---------------------------------------------------------------------------


def test_candidate_placement_create():
    with pytest.raises(ValidationError) as exc_info:
        CandidatePlacementCreate()
    errors = exc_info.value.errors()
    missing_fields = {err["loc"][0] for err in errors}
    assert "candidate_id" in missing_fields
    assert "company" in missing_fields
    assert "placement_date" in missing_fields
    assert "status" in missing_fields

    placement = CandidatePlacementCreate(
        candidate_id=42,
        company="TechCorp Inc.",
        placement_date=date(2026, 3, 1),
        status="Active",
    )
    assert placement.candidate_id == 42
    assert placement.company == "TechCorp Inc."
    assert placement.placement_date == date(2026, 3, 1)
    assert placement.status == "Active"


# ---------------------------------------------------------------------------
# 5. JobListingCreate Tests
# ---------------------------------------------------------------------------


def test_job_listing_create():
    with pytest.raises(ValidationError) as exc_info:
        JobListingCreate()
    errors = exc_info.value.errors()
    missing_fields = {err["loc"][0] for err in errors}
    assert "title" in missing_fields
    assert "company_name" in missing_fields

    job = JobListingCreate(
        title="Software Engineer",
        company_name="Google",
        contact_email="  TEST_EMAIL@Gmail.COM  ",
    )
    assert job.contact_email == "test_email@gmail.com"
