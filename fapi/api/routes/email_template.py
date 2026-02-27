from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from fapi.db.database import get_db
from fapi.db.schemas import EmailTemplate, EmailTemplateCreate, EmailTemplateUpdate
from fapi.utils import email_template_utils
from fapi.utils.email_template_utils import get_email_templates_version

router = APIRouter(prefix="/email-template", tags=["Email Template"])

security = HTTPBearer()

@router.head("/")
def check_version(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    return get_email_templates_version(db)

@router.get("/", response_model=List[EmailTemplate])
def get_email_templates(db: Session = Depends(get_db)):
    return email_template_utils.get_email_templates(db)

@router.post("/", response_model=EmailTemplate, status_code=status.HTTP_201_CREATED)
def create_email_template(template: EmailTemplateCreate, db: Session = Depends(get_db)):
    return email_template_utils.create_email_template(db, template)

@router.put("/{template_id}", response_model=EmailTemplate)
def update_email_template(template_id: int, template: EmailTemplateUpdate, db: Session = Depends(get_db)):
    db_template = email_template_utils.update_email_template(db, template_id, template)
    if not db_template:
        raise HTTPException(status_code=404, detail="Email Template not found")


    
    update_data = template.model_dump(exclude_unset=True)
    # content_html is NOT NULL in DB — skip if None to preserve existing value
    for key, value in update_data.items():
        if key == "content_html" and value is None:
            continue
        setattr(db_template, key, value)
    
    db.commit()
    db.refresh(db_template)
    return db_template

@router.delete("/{template_id}")
def delete_email_template(template_id: int, db: Session = Depends(get_db)):
    success = email_template_utils.delete_email_template(db, template_id)
    if not success:
        raise HTTPException(status_code=404, detail="Email Template not found")
    return {"message": "Email Template deleted"}
