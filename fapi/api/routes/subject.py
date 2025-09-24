# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from typing import List

# from fapi.db.database import get_db
# from fapi.db import schemas
# from fapi.utils import subject_utils

# router = APIRouter()

# @router.get("/subjects", response_model=List[schemas.SubjectResponse]) 
# def get_subjects(db: Session = Depends(get_db)):
#     subjects = subject_utils.get_all_subjects(db)
#     return subjects

# @router.get("/subjects/{subject_id}", response_model=schemas.SubjectResponse)
# def get_subject(subject_id: int, db: Session = Depends(get_db)):
#     subject = subject_utils.get_subject_by_id(db, subject_id)
#     if not subject:
#         raise HTTPException(status_code=404, detail="Subject not found")
#     return subject

# @router.post("/subjects", response_model=schemas.SubjectResponse) 
# def create_subject(subject: schemas.SubjectCreate, db: Session = Depends(get_db)):
#     try:
#         db_subject = subject_utils.create_subject(db, subject)
#         return db_subject
#     except ValueError as e:
#         raise HTTPException(status_code=422, detail=str(e))

# @router.put("/subjects/{subject_id}", response_model=schemas.SubjectResponse)
# def update_subject(subject_id: int, subject: schemas.SubjectUpdate, db: Session = Depends(get_db)):
#     try:
#         db_subject = subject_utils.update_subject(db, subject_id, subject)
#         return db_subject
#     except ValueError as e:
#         raise HTTPException(status_code=422, detail=str(e))

# @router.delete("/subjects/{subject_id}")
# def delete_subject(subject_id: int, db: Session = Depends(get_db)):
#     try:
#         subject_utils.delete_subject(db, subject_id)
#         return {"status": "success", "message": "Subject deleted successfully"}
#     except ValueError as e:
#         raise HTTPException(status_code=404, detail=str(e))    
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db import schemas
from fapi.utils import subject_utils

router = APIRouter()

# Use HTTPBearer for Swagger authentication
security = HTTPBearer()

@router.get("/subjects", response_model=List[schemas.SubjectResponse])
def get_subjects(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    subjects = subject_utils.get_all_subjects(db)
    return subjects


@router.get("/subjects/{subject_id}", response_model=schemas.SubjectResponse)
def get_subject(subject_id: int, db: Session = Depends(get_db)):
    subject = subject_utils.get_subject_by_id(db, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject

@router.post("/subjects", response_model=schemas.SubjectResponse) 
def create_subject(subject: schemas.SubjectCreate, db: Session = Depends(get_db)):
    try:
        db_subject = subject_utils.create_subject(db, subject)
        return db_subject
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.put("/subjects/{subject_id}", response_model=schemas.SubjectResponse)
def update_subject(subject_id: int, subject: schemas.SubjectUpdate, db: Session = Depends(get_db)):
    try:
        db_subject = subject_utils.update_subject(db, subject_id, subject)
        return db_subject
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.delete("/subjects/{subject_id}")
def delete_subject(subject_id: int, db: Session = Depends(get_db)):
    try:
        subject_utils.delete_subject(db, subject_id)
        return {"status": "success", "message": "Subject deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    
# @router.get("/subjects/{subject_id}", response_model=schemas.SubjectResponse)
# def get_subject(
#     subject_id: int,
#     db: Session = Depends(get_db),
#     credentials: HTTPAuthorizationCredentials = Security(security),
# ):
#     subject = subject_utils.get_subject_by_id(db, subject_id)
#     if not subject:
#         raise HTTPException(status_code=404, detail="Subject not found")
#     return subject

# @router.post("/subjects", response_model=schemas.SubjectResponse)
# def create_subject(
#     subject: schemas.SubjectCreate,
#     db: Session = Depends(get_db),
#     credentials: HTTPAuthorizationCredentials = Security(security),
# ):
#     try:
#         db_subject = subject_utils.create_subject(db, subject)
#         return db_subject
#     except ValueError as e:
#         raise HTTPException(status_code=422, detail=str(e))

# @router.put("/subjects/{subject_id}", response_model=schemas.SubjectResponse)
# def update_subject(
#     subject_id: int,
#     subject: schemas.SubjectUpdate,
#     db: Session = Depends(get_db),
#     credentials: HTTPAuthorizationCredentials = Security(security),
# ):
#     try:
#         db_subject = subject_utils.update_subject(db, subject_id, subject)
#         return db_subject
#     except ValueError as e:
#         raise HTTPException(status_code=422, detail=str(e))

# @router.delete("/subjects/{subject_id}")
# def delete_subject(
#     subject_id: int,
#     db: Session = Depends(get_db),
#     credentials: HTTPAuthorizationCredentials = Security(security),
# ):
#     try:
#         subject_utils.delete_subject(db, subject_id)
#         return {"status": "success", "message": "Subject deleted successfully"}
#     except ValueError as e:
#         raise HTTPException(status_code=404, detail=str(e))
