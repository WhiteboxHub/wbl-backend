# utils that use the provided db session (do NOT open their own SessionLocal)
from sqlalchemy.orm import Session
from decimal import Decimal
from typing import Dict, Any, Optional

from fapi.db import models


from sqlalchemy import func

def list_placement_fees(db: Session):
    results = db.query(
        models.PlacementFeeCollection,
        models.CandidateORM.full_name.label("candidate_name"),
        func.coalesce(models.AuthUserORM.fullname, models.AuthUserORM.uname).label("lastmod_user_name")
    ).outerjoin(
        models.CandidatePlacementORM,
        models.PlacementFeeCollection.placement_id == models.CandidatePlacementORM.id
    ).outerjoin(
        models.CandidateORM,
        models.CandidatePlacementORM.candidate_id == models.CandidateORM.id
    ).outerjoin(
        models.AuthUserORM,
        models.PlacementFeeCollection.lastmod_user_id == models.AuthUserORM.id
    ).all()

    fees = []
    import logging
    logger = logging.getLogger("wbl")
    for fee, c_name, u_name in results:
        logger.info(f"PlacementFee {fee.id}: candidate={c_name}, lastmod_user={u_name}")
        fee.candidate_name = c_name
        fee.lastmod_user_name = u_name.title() if u_name else None
        fees.append(fee)
    return fees


def get_placement_fee(db: Session, fee_id: int) -> Optional[models.PlacementFeeCollection]:
    result = db.query(
        models.PlacementFeeCollection,
        models.CandidateORM.full_name.label("candidate_name"),
        func.coalesce(models.AuthUserORM.fullname, models.AuthUserORM.uname).label("lastmod_user_name")
    ).outerjoin(
        models.CandidatePlacementORM,
        models.PlacementFeeCollection.placement_id == models.CandidatePlacementORM.id
    ).outerjoin(
        models.CandidateORM,
        models.CandidatePlacementORM.candidate_id == models.CandidateORM.id
    ).outerjoin(
        models.AuthUserORM,
        models.PlacementFeeCollection.lastmod_user_id == models.AuthUserORM.id
    ).filter(
        models.PlacementFeeCollection.id == fee_id
    ).first()

    if result:
        fee, c_name, u_name = result
        fee.candidate_name = c_name
        fee.lastmod_user_name = u_name
        return fee
    return None


def create_placement_fee(db: Session, data: Dict[str, Any], user_id: int = None) -> models.PlacementFeeCollection:
    # Normalize fields
    if "deposit_amount" in data and data["deposit_amount"] is not None:
        data["deposit_amount"] = Decimal(str(data["deposit_amount"]))

    if "amount_collected" in data and hasattr(data["amount_collected"], "value"):
        data["amount_collected"] = data["amount_collected"].value

    if user_id:
        data["lastmod_user_id"] = user_id

    obj = models.PlacementFeeCollection(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)   
    return get_placement_fee(db, obj.id)


def update_placement_fee(db: Session, fee_id: int, data: Dict[str, Any], user_id: int = None) -> Optional[models.PlacementFeeCollection]:
    obj = db.query(models.PlacementFeeCollection).filter(
        models.PlacementFeeCollection.id == fee_id
    ).first()
    if not obj:
        raise ValueError("Placement fee not found")

    if "deposit_amount" in data and data["deposit_amount"] is not None:
        data["deposit_amount"] = Decimal(str(data["deposit_amount"]))

    if "amount_collected" in data and hasattr(data["amount_collected"], "value"):
        data["amount_collected"] = data["amount_collected"].value
    
    if user_id:
        obj.lastmod_user_id = user_id

    for k, v in data.items():
        if k != "lastmod_user_id":
            setattr(obj, k, v)

    db.add(obj)
    db.commit()
    db.refresh(obj)
    return get_placement_fee(db, fee_id)


def delete_placement_fee(db: Session, fee_id: int) -> None:
    obj = db.query(models.PlacementFeeCollection).filter(
        models.PlacementFeeCollection.id == fee_id
    ).first()
    if not obj:
        raise ValueError("Placement fee not found")
    db.delete(obj)
    db.commit()
