from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db.models import DeliveryEngineORM
from fapi.db.schemas import DeliveryEngine, DeliveryEngineCreate, DeliveryEngineUpdate
from fapi.utils.permission_gate import enforce_access

router = APIRouter(prefix="/delivery-engine", tags=["Delivery Engine"])

@router.get("/", response_model=List[DeliveryEngine])
def get_delivery_engines(db: Session = Depends(get_db)):
    return db.query(DeliveryEngineORM).all()

@router.post("/", response_model=DeliveryEngine, status_code=status.HTTP_201_CREATED)
def create_delivery_engine(engine: DeliveryEngineCreate, db: Session = Depends(get_db)):
    db_engine = DeliveryEngineORM(**engine.model_dump())
    db.add(db_engine)
    db.commit()
    db.refresh(db_engine)
    return db_engine

@router.put("/{engine_id}", response_model=DeliveryEngine)
def update_delivery_engine(engine_id: int, engine: DeliveryEngineUpdate, db: Session = Depends(get_db)):
    db_engine = db.query(DeliveryEngineORM).filter(DeliveryEngineORM.id == engine_id).first()
    if not db_engine:
        raise HTTPException(status_code=404, detail="Delivery Engine not found")
    
    update_data = engine.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_engine, key, value)
    
    db.commit()
    db.refresh(db_engine)
    return db_engine

@router.delete("/{engine_id}")
def delete_delivery_engine(engine_id: int, db: Session = Depends(get_db)):
    db_engine = db.query(DeliveryEngineORM).filter(DeliveryEngineORM.id == engine_id).first()
    if not db_engine:
        raise HTTPException(status_code=404, detail="Delivery Engine not found")
    db.delete(db_engine)
    db.commit()
    return {"message": "Delivery Engine deleted"}
