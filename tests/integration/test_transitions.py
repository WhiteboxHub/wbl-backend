import pytest
from datetime import date
from fapi.db.models import CandidateORM, CandidatePreparation, CandidateMarketingORM, CandidatePlacementORM
from fapi.db.schemas import CandidatePreparationUpdate, CandidateMarketingUpdate
from fapi.utils.candidate_utils import update_candidate_preparation, update_marketing, update_candidate

def test_transition_prep_to_marketing(db_session):
    # 1. Create a candidate
    candidate = CandidateORM(
        full_name="Transition Test Candidate",
        email="transition@test.com",
        status="active",
        phone="555-1234",
        batchid=1
    )
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)

    # 2. Create CandidatePreparation with move_to_mrkt=True
    prep = CandidatePreparation(
        candidate_id=candidate.id,
        start_date=date.today(),
        status="active",
        move_to_mrkt=True
    )
    db_session.add(prep)
    db_session.commit()
    db_session.refresh(prep)

    # Manually ensure CandidateMarketingORM exists as it would be created during flow
    marketing = CandidateMarketingORM(
        candidate_id=candidate.id,
        start_date=date.today(),
        status="active"
    )
    db_session.add(marketing)
    db_session.commit()

    # Now verify the flag is True
    assert prep.move_to_mrkt is True

    # 3. Call update_candidate_preparation with move_to_mrkt=False
    updates = CandidatePreparationUpdate(move_to_mrkt=False)
    updated_prep = update_candidate_preparation(db_session, prep.id, updates)

    # 4. Verify candidate marketing status is inactive
    db_session.refresh(marketing)
    assert marketing.status == "inactive"
    assert updated_prep.move_to_mrkt is False

def test_transition_marketing_to_placement(db_session):
    # 1. Create candidate
    candidate = CandidateORM(
        full_name="Transition Test Candidate 2",
        email="transition2@test.com",
        status="active",
        phone="555-5678",
        batchid=1
    )
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)

    # 2. Create CandidateMarketing with move_to_placement=True
    marketing = CandidateMarketingORM(
        candidate_id=candidate.id,
        start_date=date.today(),
        status="active",
        move_to_placement=True
    )
    db_session.add(marketing)
    db_session.commit()
    db_session.refresh(marketing)

    # Create active Placement
    placement = CandidatePlacementORM(
        candidate_id=candidate.id,
        company="Test Corp",
        placement_date=date.today(),
        status="Active"
    )
    db_session.add(placement)
    db_session.commit()

    assert marketing.move_to_placement is True

    # 3. Call update_marketing with move_to_placement=False
    payload = CandidateMarketingUpdate(move_to_placement=False)
    updated_mkt = update_marketing(marketing.id, payload)

    # 4. Verify placement status is Inactive
    db_session.refresh(placement)
    assert placement.status == "Inactive"
    
    # Reload marketing via SessionLocal (since update_marketing creates its own session)
    updated_mkt_db = db_session.query(CandidateMarketingORM).filter(CandidateMarketingORM.id == marketing.id).first()
    db_session.refresh(updated_mkt_db)
    assert updated_mkt_db.move_to_placement is False

def test_transition_candidate_to_prep(db_session):
    # 1. Create candidate with move_to_prep=True
    candidate = CandidateORM(
        full_name="Transition Test Candidate 3",
        email="transition3@test.com",
        status="active",
        phone="555-8888",
        batchid=1,
        move_to_prep=True
    )
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)

    # Create active preparation
    prep = CandidatePreparation(
        candidate_id=candidate.id,
        start_date=date.today(),
        status="active"
    )
    db_session.add(prep)
    db_session.commit()

    assert candidate.move_to_prep is True

    # 2. Update candidate with move_to_prep=False
    update_candidate(candidate.id, {"move_to_prep": False})

    # 3. Verify prep status is inactive
    db_session.refresh(prep)
    assert prep.status == "inactive"

    db_session.refresh(candidate)
    assert candidate.move_to_prep is False

def test_transition_candidate_closed(db_session):
    # 1. Create a candidate
    candidate = CandidateORM(
        full_name="Transition Test Candidate 4",
        email="transition4@test.com",
        status="active",
        phone="555-9999",
        batchid=1,
        move_to_prep=True
    )
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)

    # 2. Create active prep, marketing, and placement records
    prep = CandidatePreparation(
        candidate_id=candidate.id,
        start_date=date.today(),
        status="active",
        move_to_mrkt=True
    )
    db_session.add(prep)
    
    marketing = CandidateMarketingORM(
        candidate_id=candidate.id,
        start_date=date.today(),
        status="active",
        move_to_placement=True
    )
    db_session.add(marketing)

    placement = CandidatePlacementORM(
        candidate_id=candidate.id,
        company="Closed test corp",
        placement_date=date.today(),
        status="Active"
    )
    db_session.add(placement)
    
    db_session.commit()

    # Verify initial states
    assert candidate.move_to_prep is True
    assert prep.move_to_mrkt is True
    assert marketing.move_to_placement is True
    assert prep.status == "active"
    assert marketing.status == "active"
    assert placement.status == "Active"

    # 3. Update candidate status to "closed"
    update_candidate(candidate.id, {"status": "closed"})

    # 4. Verify all records deactivated and flags synchronized
    db_session.refresh(candidate)
    db_session.refresh(prep)
    db_session.refresh(marketing)
    db_session.refresh(placement)

    assert candidate.status == "closed"
    assert candidate.move_to_prep is False
    assert prep.status == "inactive"
    assert prep.move_to_mrkt is False
    assert marketing.status == "inactive"
    assert marketing.move_to_placement is False
    assert placement.status == "Inactive"

