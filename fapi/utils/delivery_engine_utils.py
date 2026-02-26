from sqlalchemy.orm import Session
from fapi.db.models import DeliveryEngineORM
from fapi.db.schemas import DeliveryEngineCreate, DeliveryEngineUpdate
from typing import List, Optional
from fapi.utils.table_fingerprint import generate_version_for_model
from fastapi import Response

def get_delivery_engines(db: Session) -> List[DeliveryEngineORM]:
    return db.query(DeliveryEngineORM).all()

def get_delivery_engine(db: Session, engine_id: int) -> Optional[DeliveryEngineORM]:
    return db.query(DeliveryEngineORM).filter(DeliveryEngineORM.id == engine_id).first()

def create_delivery_engine(db: Session, engine: DeliveryEngineCreate) -> DeliveryEngineORM:
    db_engine = DeliveryEngineORM(**engine.model_dump())
    db.add(db_engine)
    db.commit()
    db.refresh(db_engine)
    return db_engine

def update_delivery_engine(db: Session, engine_id: int, engine: DeliveryEngineUpdate) -> Optional[DeliveryEngineORM]:
    db_engine = db.query(DeliveryEngineORM).filter(DeliveryEngineORM.id == engine_id).first()
    if not db_engine:
        return None
    
    update_data = engine.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_engine, key, value)
    
    db.commit()
    db.refresh(db_engine)
    return db_engine

def delete_delivery_engine(db: Session, engine_id: int) -> bool:
    db_engine = db.query(DeliveryEngineORM).filter(DeliveryEngineORM.id == engine_id).first()
    if not db_engine:
        return False
    db.delete(db_engine)
    db.commit()
    return True

def get_delivery_engines_version(db: Session) -> Response:
    return generate_version_for_model(db, DeliveryEngineORM)
