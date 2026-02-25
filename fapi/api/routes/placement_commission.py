from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from fapi.db.database import get_db
from fapi.utils.table_fingerprint import generate_version_for_model
from fapi.db.schemas import (
    PlacementCommissionCreate,
    PlacementCommissionUpdate,
    PlacementCommissionOut,
    PlacementCommissionSchedulerCreate,
    PlacementCommissionSchedulerUpdate,
    PlacementCommissionSchedulerOut,
)
from fapi.utils import placement_commission_utils as utils
from fapi.db.models import PlacementCommissionORM
import hashlib
from fastapi import Response
from sqlalchemy import func

router = APIRouter()

security = HTTPBearer()

@router.head("/placement-commission")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return generate_version_for_model(db, PlacementCommissionORM)

def check_placement_commissions_version(db: Session = Depends(get_db)):
    try:
        result = db.query(
            func.count().label("cnt"),
            func.max(PlacementCommissionORM.id).label("max_id"),
            func.sum(
                func.crc32(
                    func.concat_ws(
                        '|',
                        PlacementCommissionORM.id,
                        func.coalesce(PlacementCommissionORM.candidate_id, ''),
                        func.coalesce(PlacementCommissionORM.employee_id, ''),
                        func.coalesce(PlacementCommissionORM.amount, ''),
                        func.coalesce(PlacementCommissionORM.status, '')
                    )
                )
            ).label("checksum")
        ).first()

        response = Response(status_code=200)
        if result and result.cnt > 0:
            fingerprint = f"{result.cnt}|{result.max_id}|{result.checksum}"
            version_hash = hashlib.md5(fingerprint.encode()).hexdigest()
            response.headers["X-Data-Version"] = version_hash
            response.headers["Last-Modified"] = version_hash
        else:
            response.headers["X-Data-Version"] = "empty"
            response.headers["Last-Modified"] = "empty"

        return response
    except Exception as e:
        response = Response(status_code=200)
        response.headers["X-Data-Version"] = "error"
        response.headers["Last-Modified"] = "error"
        return response


# ---------------------------------------------------------------------------
# placement_commission endpoints
# ---------------------------------------------------------------------------

@router.get("/placement-commission", response_model=List[PlacementCommissionOut])
def list_commissions(db: Session = Depends(get_db)):
    """List all placement commissions enriched with employee/candidate/company names."""
    return utils.list_commissions(db)


@router.get(
    "/placement-commission/by-placement/{placement_id}",
    response_model=List[PlacementCommissionOut],
)
def get_commissions_by_placement(placement_id: int, db: Session = Depends(get_db)):
    """Get all commissions for a specific placement."""
    return utils.get_commissions_by_placement(db, placement_id)


@router.get("/placement-commission/{commission_id}", response_model=PlacementCommissionOut)
def get_commission(commission_id: int, db: Session = Depends(get_db)):
    """Get a single placement commission by ID."""
    obj = utils.get_commission(db, commission_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Placement commission not found",
        )
    return obj


@router.post(
    "/placement-commission",
    response_model=PlacementCommissionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_commission(payload: PlacementCommissionCreate, db: Session = Depends(get_db)):
    """Create a new placement commission."""
    return utils.create_commission(db, payload.dict())


@router.put("/placement-commission/{commission_id}", response_model=PlacementCommissionOut)
def update_commission(
    commission_id: int,
    payload: PlacementCommissionUpdate,
    db: Session = Depends(get_db),
):
    """Update an existing placement commission."""
    obj = utils.update_commission(db, commission_id, payload.dict(exclude_unset=True))
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Placement commission not found",
        )
    return obj


@router.delete("/placement-commission/{commission_id}", status_code=status.HTTP_200_OK)
def delete_commission(commission_id: int, db: Session = Depends(get_db)):
    """Delete a placement commission (cascades to scheduler entries)."""
    utils.delete_commission(db, commission_id)
    return {"message": "Placement commission deleted successfully"}


# ---------------------------------------------------------------------------
# placement_commission_scheduler endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/placement-commission-scheduler/by-commission/{commission_id}",
    response_model=List[PlacementCommissionSchedulerOut],
)
def list_schedulers(commission_id: int, db: Session = Depends(get_db)):
    """List all installment schedule entries for a commission."""
    return utils.list_schedulers(db, commission_id)


@router.get(
    "/placement-commission-scheduler/{scheduler_id}",
    response_model=PlacementCommissionSchedulerOut,
)
def get_scheduler(scheduler_id: int, db: Session = Depends(get_db)):
    """Get a single scheduler entry by ID."""
    obj = utils.get_scheduler(db, scheduler_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Placement commission scheduler entry not found",
        )
    return obj


@router.post(
    "/placement-commission-scheduler",
    response_model=PlacementCommissionSchedulerOut,
    status_code=status.HTTP_201_CREATED,
)
def create_scheduler(
    payload: PlacementCommissionSchedulerCreate, db: Session = Depends(get_db)
):
    """Create a new installment schedule entry for a commission."""
    return utils.create_scheduler(db, payload.dict())


@router.put(
    "/placement-commission-scheduler/{scheduler_id}",
    response_model=PlacementCommissionSchedulerOut,
)
def update_scheduler(
    scheduler_id: int,
    payload: PlacementCommissionSchedulerUpdate,
    db: Session = Depends(get_db),
):
    """Update a scheduler entry (e.g. mark as Paid)."""
    obj = utils.update_scheduler(db, scheduler_id, payload.dict(exclude_unset=True))
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Placement commission scheduler entry not found",
        )
    return obj


@router.delete(
    "/placement-commission-scheduler/{scheduler_id}", status_code=status.HTTP_200_OK
)
def delete_scheduler(scheduler_id: int, db: Session = Depends(get_db)):
    """Delete a scheduler entry."""
    utils.delete_scheduler(db, scheduler_id)
    return {"message": "Placement commission scheduler entry deleted successfully"}
