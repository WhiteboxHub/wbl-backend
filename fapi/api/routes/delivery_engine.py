from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.utils.table_fingerprint import generate_version_for_model
from fapi.db.models import DeliveryEngineORM
from fapi.db.schemas import DeliveryEngine, DeliveryEngineCreate, DeliveryEngineUpdate
from fapi.utils.permission_gate import enforce_access
import hashlib
from fastapi import Response
from sqlalchemy import func

router = APIRouter(prefix="/delivery-engine", tags=["Delivery Engine"])

security = HTTPBearer()

@router.head("/")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return generate_version_for_model(db, DeliveryEngineORM)

def check_delivery_engines_version(db: Session = Depends(get_db)):
    try:
        result = db.query(
            func.count().label("cnt"),
            func.max(DeliveryEngineORM.id).label("max_id"),
            func.sum(
                func.crc32(
                    func.concat_ws(
                        '|',
                        DeliveryEngineORM.id,
                        func.coalesce(DeliveryEngineORM.name, ''),
                        func.coalesce(DeliveryEngineORM.status, '')
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
