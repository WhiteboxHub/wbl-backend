from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fapi.db.database import get_db
from fapi.utils.table_fingerprint import generate_version_for_model
from fapi.db.schemas import PlacementFeeCreate, PlacementFeeUpdate, PlacementFeeOut
from fapi.utils import placement_fee_collection_utils as utils
from fapi.utils.auth_dependencies import get_current_user
from fapi.db.models import PlacementFeeCollection
import hashlib
from fastapi import Response
from sqlalchemy import func

router = APIRouter()

@router.head("/placement-fee")
def check_placement_fees_version(db: Session = Depends(get_db)):
    try:
        result = db.query(
            func.count().label("cnt"),
            func.max(PlacementFeeCollection.id).label("max_id"),
            func.sum(
                func.crc32(
                    func.concat_ws(
                        '|',
                        PlacementFeeCollection.id,
                        func.coalesce(PlacementFeeCollection.candidate_id, ''),
                        func.coalesce(PlacementFeeCollection.deposit_amount, ''),
                        func.coalesce(PlacementFeeCollection.amount_collected, ''),
                        func.coalesce(PlacementFeeCollection.status, '')
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


@router.get("/placement-fee", response_model=list[PlacementFeeOut])
def list_placement_fees(db: Session = Depends(get_db)):
    return utils.list_placement_fees(db)


@router.get("/placement-fee/{fee_id}", response_model=PlacementFeeOut)
def get_placement_fee(fee_id: int, db: Session = Depends(get_db)):
    obj = utils.get_placement_fee(db, fee_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Placement fee record not found")
    return obj


@router.post("/placement-fee", response_model=PlacementFeeOut, status_code=status.HTTP_201_CREATED)
def create_placement_fee(
    payload: PlacementFeeCreate, 
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    created_obj = utils.create_placement_fee(db, payload.dict(exclude_unset=True), user_id=current_user.id)
    if not created_obj:
        raise HTTPException(status_code=500, detail="Failed to create placement fee")
    return created_obj


@router.put("/placement-fee/{fee_id}", response_model=PlacementFeeOut)
def update_placement_fee(
    fee_id: int, 
    payload: PlacementFeeUpdate, 
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    try:
        updated_obj = utils.update_placement_fee(db, fee_id, payload.dict(exclude_unset=True), user_id=current_user.id)
        if not updated_obj:
             raise HTTPException(status_code=404, detail="Placement fee not found after update")
        return updated_obj
    except ValueError:
        raise HTTPException(status_code=404, detail="Placement fee not found")


@router.delete("/placement-fee/{fee_id}")
def delete_placement_fee(fee_id: int, db: Session = Depends(get_db)):
    try:
        utils.delete_placement_fee(db, fee_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Placement fee not found")
    return {"message": "Placement fee deleted successfully"}
