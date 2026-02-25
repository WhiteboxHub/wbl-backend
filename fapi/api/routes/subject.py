# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from typing import List

# from fapi.db.database import get_db
from fapi.utils.table_fingerprint import generate_version_for_model
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
from fastapi import APIRouter, Depends, HTTPException, Security, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from fapi.db.database import get_db
from fapi.db import schemas, models
from fapi.utils import subject_utils
import hashlib

router = APIRouter()

# Use HTTPBearer for Swagger authentication
security = HTTPBearer()

@router.head("/subjects")
def check_subjects_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    try:
        result = db.query(
            func.count().label("cnt"),
            func.max(models.Subject.id).label("max_id"),
            func.sum(
                func.crc32(
                    func.concat_ws(
                        '|',
                        models.Subject.id,
                        func.coalesce(models.Subject.name, ''),
                        func.coalesce(models.Subject.courseid, '')
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
        print(f"[ERROR] HEAD /subjects failed: {e}")
        response = Response(status_code=200)
        response.headers["X-Data-Version"] = "error"
        response.headers["Last-Modified"] = "error"
        return response

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
