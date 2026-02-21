"""
Utility functions for placement_commission and placement_commission_scheduler tables.
All functions receive an injected SQLAlchemy Session (do NOT open SessionLocal here).
"""
from decimal import Decimal
from typing import List, Optional, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from fapi.db import models


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enrich_commission(
    commission: models.PlacementCommissionORM,
) -> models.PlacementCommissionORM:
    """Attach display-friendly scalar fields to the ORM object."""
    # Employee name
    commission.employee_name = commission.employee.name if commission.employee else None

    # Candidate and company via placement
    placement = commission.placement
    if placement:
        commission.company_name = placement.company
        # Candidate name from the candidate relationship
        candidate = placement.candidate if placement.candidate else None
        commission.candidate_name = candidate.full_name if candidate else None
    else:
        commission.company_name = None
        commission.candidate_name = None

    return commission


# ---------------------------------------------------------------------------
# placement_commission CRUD
# ---------------------------------------------------------------------------

def list_commissions(db: Session) -> List[models.PlacementCommissionORM]:
    commissions = (
        db.query(models.PlacementCommissionORM)
        .options(
            joinedload(models.PlacementCommissionORM.employee),
            joinedload(models.PlacementCommissionORM.placement).joinedload(
                models.CandidatePlacementORM.candidate
            ),
            joinedload(models.PlacementCommissionORM.scheduler_entries),
        )
        .order_by(models.PlacementCommissionORM.id.desc())
        .all()
    )
    return [_enrich_commission(c) for c in commissions]


def get_commission(db: Session, commission_id: int) -> Optional[models.PlacementCommissionORM]:
    commission = (
        db.query(models.PlacementCommissionORM)
        .options(
            joinedload(models.PlacementCommissionORM.employee),
            joinedload(models.PlacementCommissionORM.placement).joinedload(
                models.CandidatePlacementORM.candidate
            ),
            joinedload(models.PlacementCommissionORM.scheduler_entries),
        )
        .filter(models.PlacementCommissionORM.id == commission_id)
        .first()
    )
    if not commission:
        return None
    return _enrich_commission(commission)


def get_commissions_by_placement(
    db: Session, placement_id: int
) -> List[models.PlacementCommissionORM]:
    commissions = (
        db.query(models.PlacementCommissionORM)
        .options(
            joinedload(models.PlacementCommissionORM.employee),
            joinedload(models.PlacementCommissionORM.placement).joinedload(
                models.CandidatePlacementORM.candidate
            ),
            joinedload(models.PlacementCommissionORM.scheduler_entries),
        )
        .filter(models.PlacementCommissionORM.placement_id == placement_id)
        .order_by(models.PlacementCommissionORM.id.asc())
        .all()
    )
    return [_enrich_commission(c) for c in commissions]


def create_commission(
    db: Session, data: Dict[str, Any]
) -> models.PlacementCommissionORM:
    if "amount" in data and data["amount"] is not None:
        data["amount"] = Decimal(str(data["amount"]))

    obj = models.PlacementCommissionORM(**data)
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A commission for this placement and employee already exists.",
        )
    db.refresh(obj)
    return get_commission(db, obj.id)


def update_commission(
    db: Session, commission_id: int, data: Dict[str, Any]
) -> Optional[models.PlacementCommissionORM]:
    obj = db.query(models.PlacementCommissionORM).filter(
        models.PlacementCommissionORM.id == commission_id
    ).first()
    if not obj:
        return None

    if "amount" in data and data["amount"] is not None:
        data["amount"] = Decimal(str(data["amount"]))

    for k, v in data.items():
        setattr(obj, k, v)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A commission for this placement and employee already exists.",
        )
    db.refresh(obj)
    return get_commission(db, commission_id)


def delete_commission(db: Session, commission_id: int) -> None:
    obj = db.query(models.PlacementCommissionORM).filter(
        models.PlacementCommissionORM.id == commission_id
    ).first()
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Placement commission not found.",
        )
    db.delete(obj)
    db.commit()


# ---------------------------------------------------------------------------
# placement_commission_scheduler CRUD
# ---------------------------------------------------------------------------

def list_schedulers(
    db: Session, commission_id: int
) -> List[models.PlacementCommissionSchedulerORM]:
    return (
        db.query(models.PlacementCommissionSchedulerORM)
        .filter(
            models.PlacementCommissionSchedulerORM.placement_commission_id == commission_id
        )
        .order_by(models.PlacementCommissionSchedulerORM.installment_no.asc())
        .all()
    )


def get_scheduler(
    db: Session, scheduler_id: int
) -> Optional[models.PlacementCommissionSchedulerORM]:
    return (
        db.query(models.PlacementCommissionSchedulerORM)
        .filter(models.PlacementCommissionSchedulerORM.id == scheduler_id)
        .first()
    )


def create_scheduler(
    db: Session, data: Dict[str, Any]
) -> models.PlacementCommissionSchedulerORM:
    if "installment_amount" in data and data["installment_amount"] is not None:
        data["installment_amount"] = Decimal(str(data["installment_amount"]))

    # Normalise enum value if passed as an enum instance
    if "payment_status" in data and hasattr(data["payment_status"], "value"):
        data["payment_status"] = data["payment_status"].value

    obj = models.PlacementCommissionSchedulerORM(**data)
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An installment with this number already exists for this commission.",
        )
    db.refresh(obj)
    return obj


def update_scheduler(
    db: Session, scheduler_id: int, data: Dict[str, Any]
) -> Optional[models.PlacementCommissionSchedulerORM]:
    obj = db.query(models.PlacementCommissionSchedulerORM).filter(
        models.PlacementCommissionSchedulerORM.id == scheduler_id
    ).first()
    if not obj:
        return None

    if "installment_amount" in data and data["installment_amount"] is not None:
        data["installment_amount"] = Decimal(str(data["installment_amount"]))

    if "payment_status" in data and hasattr(data["payment_status"], "value"):
        data["payment_status"] = data["payment_status"].value

    for k, v in data.items():
        setattr(obj, k, v)

    db.commit()
    db.refresh(obj)
    return obj


def delete_scheduler(db: Session, scheduler_id: int) -> None:
    obj = db.query(models.PlacementCommissionSchedulerORM).filter(
        models.PlacementCommissionSchedulerORM.id == scheduler_id
    ).first()
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Placement commission scheduler entry not found.",
        )
    db.delete(obj)
    db.commit()
