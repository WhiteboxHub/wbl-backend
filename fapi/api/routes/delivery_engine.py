from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db.schemas import DeliveryEngine, DeliveryEngineCreate, DeliveryEngineUpdate
from fapi.utils import delivery_engine_utils
from fapi.utils.delivery_engine_utils import get_delivery_engines_version

router = APIRouter(prefix="/delivery-engine", tags=["Delivery Engine"])

security = HTTPBearer()

@router.head("/")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return get_delivery_engines_version(db)

@router.get("/", response_model=List[DeliveryEngine])
def get_delivery_engines(db: Session = Depends(get_db)):
    return delivery_engine_utils.get_delivery_engines(db)

@router.post("/", response_model=DeliveryEngine, status_code=status.HTTP_201_CREATED)
def create_delivery_engine(engine: DeliveryEngineCreate, db: Session = Depends(get_db)):
    return delivery_engine_utils.create_delivery_engine(db, engine)

@router.put("/{engine_id}", response_model=DeliveryEngine)
def update_delivery_engine(engine_id: int, engine: DeliveryEngineUpdate, db: Session = Depends(get_db)):
    db_engine = delivery_engine_utils.update_delivery_engine(db, engine_id, engine)
    if not db_engine:
        raise HTTPException(status_code=404, detail="Delivery Engine not found")
    
    update_data = engine.model_dump(exclude_unset=True)
    # These columns are NOT NULL in the DB — skip if None to preserve existing value
    NOT_NULLABLE = {"name", "engine_type", "from_email", "max_retries", "timeout_seconds"}
    for key, value in update_data.items():
        if key in NOT_NULLABLE and value is None:
            continue
        setattr(db_engine, key, value)
    
    db.commit()
    db.refresh(db_engine)
    return db_engine

@router.delete("/{engine_id}")
def delete_delivery_engine(engine_id: int, db: Session = Depends(get_db)):
    success = delivery_engine_utils.delete_delivery_engine(db, engine_id)
    if not success:
        raise HTTPException(status_code=404, detail="Delivery Engine not found")
    return {"message": "Delivery Engine deleted"}
