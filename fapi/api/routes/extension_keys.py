from fastapi import APIRouter, Depends, HTTPException, status, Response, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from fapi.db.database import get_db
from fapi.db.schemas import (
    ExtensionKeyCreate, 
    ExtensionKeyUpdate, 
    ExtensionKeyOut,
    ExtensionKeyBulkCreate,
    ExtensionKeyBulkResponse
)
from fapi.utils import extension_keys_utils
from fapi.utils.extension_keys_utils import get_extension_keys_version

router = APIRouter(prefix="/extension-keys", tags=["Extension Keys"], redirect_slashes=False)

security = HTTPBearer()

@router.head("/")
@router.head("/paginated")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return get_extension_keys_version(db)

@router.get("/", response_model=List[ExtensionKeyOut])
def read_extension_keys(skip: int = 0, limit: Optional[int] = None, db: Session = Depends(get_db)):
    return extension_keys_utils.get_extension_keys(db, skip=skip, limit=limit)

@router.get("/paginated")
def read_extension_keys_paginated(
    page: int = 1, 
    page_size: int = 5000, 
    db: Session = Depends(get_db)
):
    page_size = min(max(1, page_size), 10000)
    page = max(1, page)
    skip = (page - 1) * page_size
    total_records = extension_keys_utils.count_extension_keys(db)
    data = extension_keys_utils.get_extension_keys(db, skip=skip, limit=page_size)
    total_pages = (total_records + page_size - 1) // page_size  
    
    return {
        "data": data,
        "page": page,
        "page_size": page_size,
        "total_records": total_records,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1
    }

@router.get("/count", response_model=dict)
def count_extension_keys(db: Session = Depends(get_db)):
    count = extension_keys_utils.count_extension_keys(db)
    return {"count": count}

@router.get("/search", response_model=List[ExtensionKeyOut])
def search_extension_keys(term: str, db: Session = Depends(get_db)):
    return extension_keys_utils.search_extension_keys(db, term=term)

@router.get("/{key_id}", response_model=ExtensionKeyOut)
def read_extension_key(key_id: int, db: Session = Depends(get_db)):
    db_key = extension_keys_utils.get_extension_key(db, key_id=key_id)
    if not db_key:
        raise HTTPException(status_code=404, detail="Extension Key not found")
    return db_key

@router.post("/", response_model=ExtensionKeyOut, status_code=status.HTTP_201_CREATED)
def create_extension_key(key_data: ExtensionKeyCreate, db: Session = Depends(get_db)):
    return extension_keys_utils.create_extension_key(db, extension_key=key_data)

@router.post("/bulk", response_model=ExtensionKeyBulkResponse)
async def create_extension_keys_bulk(
    bulk_data: ExtensionKeyBulkCreate,
    db: Session = Depends(get_db)
):
    return await extension_keys_utils.insert_extension_keys_bulk(bulk_data.extension_keys, db)

@router.put("/{key_id}", response_model=ExtensionKeyOut)
def update_extension_key(key_id: int, key_data: ExtensionKeyUpdate, db: Session = Depends(get_db)):
    db_key = extension_keys_utils.update_extension_key(db, key_id=key_id, extension_key=key_data)
    if not db_key:
        raise HTTPException(status_code=404, detail="Extension Key not found")
    return db_key

@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_extension_key(key_id: int, db: Session = Depends(get_db)):
    success = extension_keys_utils.delete_extension_key(db, key_id=key_id)
    if not success:
        raise HTTPException(status_code=404, detail="Extension Key not found")
    return None
