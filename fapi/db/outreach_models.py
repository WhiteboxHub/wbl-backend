from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, ForeignKey, JSON, func, BigInteger, Text
from sqlalchemy.orm import relationship, validates
from fapi.db.models import Base
from datetime import datetime

class OutreachContactORM(Base):
    __tablename__ = "outreach_contacts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    email = Column(String(255), nullable=False)

    email_lc = Column(String(255), unique=True, nullable=False) 
    
    source_type = Column(String(50), nullable=False)
    source_id = Column(BigInteger, nullable=True)
    
    status = Column(String(50), nullable=False, default='ACTIVE')
    
    unsubscribe_flag = Column(Boolean, nullable=False, default=False)
    unsubscribe_at = Column(TIMESTAMP, nullable=True)
    unsubscribe_reason = Column(String(255), nullable=True)
    
    bounce_flag = Column(Boolean, nullable=False, default=False)
    bounce_type = Column(String(20), nullable=True)
    bounce_reason = Column(String(255), nullable=True)
    bounce_code = Column(String(100), nullable=True)
    bounced_at = Column(TIMESTAMP, nullable=True)
    
    complaint_flag = Column(Boolean, nullable=False, default=False)
    complained_at = Column(TIMESTAMP, nullable=True)
    
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.current_timestamp())

    @validates('email')
    def update_email_lc(self, key, value):
        self.email_lc = value.lower() if value else None
        return value

class JobDefinitionORM(Base):
    __tablename__ = "job_definition"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    job_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default='ACTIVE')
    
    candidate_marketing_id = Column(Integer, nullable=True)
    config_json = Column(JSON, nullable=True)
    
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.current_timestamp())

class JobScheduleORM(Base):
    __tablename__ = "job_schedule"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    job_definition_id = Column(BigInteger, ForeignKey('job_definition.id', ondelete='CASCADE'), nullable=False)
    
    timezone = Column(String(64), nullable=False, default='America/Los_Angeles')
    frequency = Column(String(20), nullable=False)
    interval_value = Column(Integer, nullable=False, default=1)
    
    next_run_at = Column(TIMESTAMP, nullable=False)
    last_run_at = Column(TIMESTAMP, nullable=True)
    
    lock_token = Column(String(64), nullable=True)
    lock_expires_at = Column(TIMESTAMP, nullable=True)
    
    enabled = Column(Boolean, nullable=False, default=True)
    
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.current_timestamp())

class JobRunORM(Base):
    __tablename__ = "job_run"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    job_definition_id = Column(BigInteger, ForeignKey('job_definition.id'), nullable=False)
    job_schedule_id = Column(BigInteger, ForeignKey('job_schedule.id'), nullable=False)
    
    run_status = Column(String(20), nullable=False, default='RUNNING')
    started_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())
    finished_at = Column(TIMESTAMP, nullable=True)
    
    items_total = Column(Integer, default=0)
    items_succeeded = Column(Integer, default=0)
    items_failed = Column(Integer, default=0)
    
    error_message = Column(Text, nullable=True)
    details_json = Column(JSON, nullable=True)

class JobRequestORM(Base):
    __tablename__ = "job_request"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    job_type = Column(String(50), nullable=False)
    candidate_marketing_id = Column(Integer, nullable=False)
    
    status = Column(String(20), nullable=False, default='PENDING')
    requested_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())
    processed_at = Column(TIMESTAMP, nullable=True)
