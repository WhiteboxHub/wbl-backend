from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.utils.table_fingerprint import generate_version_for_model
from fapi.db.models import EmailTemplateORM
from fapi.db.schemas import EmailTemplate, EmailTemplateCreate, EmailTemplateUpdate
from fapi.utils.permission_gate import enforce_access
import hashlib
from fastapi import Response
from sqlalchemy import func

router = APIRouter(prefix="/email-template", tags=["Email Template"])

security = HTTPBearer()

@router.head("/")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return generate_version_for_model(db, EmailTemplateORM)

def check_email_templates_version(db: Session = Depends(get_db)):
    try:
        result = db.query(
            func.count().label("cnt"),
            func.max(EmailTemplateORM.id).label("max_id"),
            func.sum(
                func.crc32(
                    func.concat_ws(
                        '|',
                        EmailTemplateORM.id,
                        func.coalesce(EmailTemplateORM.template_key, ''),
                        func.coalesce(EmailTemplateORM.subject, ''),
                        func.coalesce(EmailTemplateORM.status, '')
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

@router.get("/", response_model=List[EmailTemplate])
def get_email_templates(db: Session = Depends(get_db)):
    return db.query(EmailTemplateORM).all()

@router.post("/", response_model=EmailTemplate, status_code=status.HTTP_201_CREATED)
def create_email_template(template: EmailTemplateCreate, db: Session = Depends(get_db)):
    db_template = EmailTemplateORM(**template.model_dump())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

@router.put("/{template_id}", response_model=EmailTemplate)
def update_email_template(template_id: int, template: EmailTemplateUpdate, db: Session = Depends(get_db)):
    db_template = db.query(EmailTemplateORM).filter(EmailTemplateORM.id == template_id).first()
    if not db_template:
        raise HTTPException(status_code=404, detail="Email Template not found")
    
    update_data = template.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_template, key, value)
    
    db.commit()
    db.refresh(db_template)
    return db_template

@router.delete("/{template_id}")
def delete_email_template(template_id: int, db: Session = Depends(get_db)):
    db_template = db.query(EmailTemplateORM).filter(EmailTemplateORM.id == template_id).first()
    if not db_template:
        raise HTTPException(status_code=404, detail="Email Template not found")
    db.delete(db_template)
    db.commit()
    return {"message": "Email Template deleted"}
