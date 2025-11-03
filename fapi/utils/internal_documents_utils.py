
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fapi.db.models import InternalDocument
from  fapi.db.schemas import InternalDocumentCreate, InternalDocumentUpdate

def get_all_documents(db: Session):
    return db.query(InternalDocument).order_by(InternalDocument.id.desc()).all()

def get_document_by_id(db: Session, doc_id: int):
    return db.query(InternalDocument).filter(InternalDocument.id == doc_id).first()

def create_document(db: Session, doc: InternalDocumentCreate):
    new_doc = InternalDocument(**doc.model_dump())
    db.add(new_doc)
    try:
        db.commit()
        db.refresh(new_doc)
        return new_doc
    except SQLAlchemyError as e:
        db.rollback()
        raise e

def update_document(db: Session, doc_id: int, doc_data: InternalDocumentUpdate):
    doc = get_document_by_id(db, doc_id)
    if not doc:
        return None

    for key, value in doc_data.model_dump(exclude_unset=True).items():
        setattr(doc, key, value)

    try:
        db.commit()
        db.refresh(doc)
        return doc
    except SQLAlchemyError as e:
        db.rollback()
        raise e

def delete_document(db: Session, doc_id: int):
    doc = get_document_by_id(db, doc_id)
    if not doc:
        return False

    db.delete(doc)
    try:
        db.commit()
        return True
    except SQLAlchemyError:
        db.rollback()
        return False