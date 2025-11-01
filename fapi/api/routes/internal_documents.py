from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db

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


@router.get("/internal-documents/", response_model=List[InternalDocumentOut])
def list_internal_documents(db: Session = Depends(get_db)):
    return get_all_documents(db)


@router.get("/internal-documents/{doc_id}", response_model=InternalDocumentOut)
def get_internal_document(doc_id: int, db: Session = Depends(get_db)):
    doc = get_document_by_id(db, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.post("/internal-documents", response_model=InternalDocumentOut)
def create_internal_document(doc: InternalDocumentCreate, db: Session = Depends(get_db)):
    return create_document_util(db, doc)


@router.put("/internal-documents/{doc_id}", response_model=InternalDocumentOut)
def update_internal_document(doc_id: int, doc_data: InternalDocumentUpdate, db: Session = Depends(get_db)):
    updated_doc = update_document_util(db, doc_id, doc_data)
    if not updated_doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return updated_doc


@router.delete("/internal-documents/{doc_id}")
def delete_internal_document(doc_id: int, db: Session = Depends(get_db)):
    deleted = delete_document_util(db, doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found or could not be deleted")
    return {"message": "Document deleted successfully"}

  