from sqlalchemy.orm import Session
from fapi.db.models import EmailTemplateORM
from fapi.db.schemas import EmailTemplateCreate, EmailTemplateUpdate
from typing import List, Optional
from fapi.utils.table_fingerprint import generate_version_for_model
from fastapi import Response
from fapi.core.cache import cache_result, invalidate_cache

@cache_result(ttl=300, prefix="email_templates")
def get_email_templates(db: Session) -> List[EmailTemplateORM]:
    return db.query(EmailTemplateORM).all()

@cache_result(ttl=300, prefix="email_templates")
def get_email_template(db: Session, template_id: int) -> Optional[EmailTemplateORM]:
    return db.query(EmailTemplateORM).filter(EmailTemplateORM.id == template_id).first()

@cache_result(ttl=300, prefix="email_templates")
def get_email_template_by_key(db: Session, template_key: str) -> Optional[EmailTemplateORM]:
    return db.query(EmailTemplateORM).filter(EmailTemplateORM.template_key == template_key).first()

def create_email_template(db: Session, template: EmailTemplateCreate) -> EmailTemplateORM:
    invalidate_cache("email_templates")
    # B3 fix: also bust the workflow execution bundle cache so the scheduler
    # immediately uses the new template content instead of a stale snapshot.
    invalidate_cache("workflows")
    db_template = EmailTemplateORM(**template.model_dump())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

def update_email_template(db: Session, template_id: int, template: EmailTemplateUpdate) -> Optional[EmailTemplateORM]:
    invalidate_cache("email_templates")
    # B3 fix: bust execution bundle cache so template edits take effect immediately.
    invalidate_cache("workflows")
    db_template = db.query(EmailTemplateORM).filter(EmailTemplateORM.id == template_id).first()
    if not db_template:
        return None
    
    update_data = template.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_template, key, value)
    
    db.commit()
    db.refresh(db_template)
    return db_template

def delete_email_template(db: Session, template_id: int) -> bool:
    invalidate_cache("email_templates")
    # B3 fix: bust execution bundle cache on deletion too.
    invalidate_cache("workflows")
    db_template = db.query(EmailTemplateORM).filter(EmailTemplateORM.id == template_id).first()
    if not db_template:
        return False
    db.delete(db_template)
    db.commit()
    return True

def get_email_templates_version(db: Session) -> Response:
    return generate_version_for_model(db, EmailTemplateORM)
