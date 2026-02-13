from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db.models import EmailTemplateORM
from fapi.db.schemas import EmailTemplate, EmailTemplateCreate, EmailTemplateUpdate
from fapi.utils.permission_gate import enforce_access

router = APIRouter(prefix="/email-template", tags=["Email Template"])

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
