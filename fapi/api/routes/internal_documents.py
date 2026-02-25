


import hashlib
from fastapi import APIRouter, Depends, HTTPException, Security, Query, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from fapi.db.database import get_db
from fapi.utils.table_fingerprint import generate_version_for_model
from fapi.db.models import InternalDocument
from fapi.db.schemas import (
    InternalDocumentCreate,
    InternalDocumentUpdate,
    InternalDocumentOut,
)
from fapi.utils.internal_documents_utils import (
    get_all_documents,
    get_document_by_id,
    create_document as create_document_util,
    update_document as update_document_util,
    delete_document as delete_document_util,
)

router = APIRouter()

#  Add authentication scheme
security = HTTPBearer()

@router.head("/")
def check_documents_version(db: Session = Depends(get_db)):
    try:
        result = db.query(
            func.count().label("cnt"),
            func.max(InternalDocument.id).label("max_id"),
            func.sum(
                func.crc32(
                    func.concat_ws(
                        '|',
                        InternalDocument.id,
                        func.coalesce(InternalDocument.title, ''),
                        func.coalesce(InternalDocument.file, ''),
                        func.coalesce(InternalDocument.description, '')
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
    except Exception:
        response = Response(status_code=200)
        response.headers["X-Data-Version"] = "error"
        response.headers["Last-Modified"] = "error"
        return response


#  Get all documents (protected)
@router.get("/", response_model=List[InternalDocumentOut])
def list_internal_documents(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return get_all_documents(db)

#  Get one document (protected)
@router.get("/{doc_id}", response_model=InternalDocumentOut)
def get_internal_document(
    doc_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    doc = get_document_by_id(db, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

#  Create new document (protected)
@router.post("/", response_model=InternalDocumentOut)
def create_internal_document(
    doc: InternalDocumentCreate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return create_document_util(db, doc)

#  Update document (protected)
@router.put("/{doc_id}", response_model=InternalDocumentOut)
def update_internal_document(
    doc_id: int,
    doc_data: InternalDocumentUpdate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    updated_doc = update_document_util(db, doc_id, doc_data)
    if not updated_doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return updated_doc

#  Delete document (protected)
@router.delete("/{doc_id}")
def delete_internal_document(
    doc_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    deleted = delete_document_util(db, doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found or could not be deleted")
    return {"message": "Document deleted successfully"}

