from sqlalchemy import Column, Integer, String, DateTime, Boolean, Date,Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class LeadORM(Base):
    __tablename__ = "lead"

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(255))
    entry_date = Column(DateTime)
    phone = Column(String(20))
    email = Column(String(255), nullable=False)
    workstatus = Column(String(50))
    status = Column(String(50))
    secondary_email = Column(String(255))
    secondary_phone = Column(String(20))
    address = Column(String(255))
    closed_date = Column(Date)
    notes = Column(String(500))
    last_modified = Column(DateTime)
    massemail_unsubscribe = Column(String(5))
    massemail_email_sent = Column(String(5))
    moved_to_candidate = Column(Boolean)


class CandidateORM(Base):
    __tablename__ = "candidate"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=True)

    email = Column(String(100),  nullable=False)
    phone = Column(String(45), nullable=True)
    secondaryemail = Column(String(100), nullable=True)
    secondaryphone = Column(String(45), nullable=True)

    status = Column(String(50), nullable=True)
    workstatus = Column(String(50), nullable=True)
    education = Column(String(255), nullable=True)
    workexperience = Column(String(255), nullable=True)

    ssn = Column(String(20), nullable=True)
    agreement = Column(Boolean, default=False)

    linkedin_id = Column(String(255), nullable=True)
    enrolled_date = Column(DateTime, default=func.now())
    dob = Column(Date, nullable=True)

    emergcontactname = Column(String(100), nullable=True)
    emergcontactemail = Column(String(100), nullable=True)
    emergcontactphone = Column(String(45), nullable=True)
    emergcontactaddrs = Column(String(300), nullable=True)

    address = Column(String(300), nullable=True)
    fee_paid = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    batchid = Column(Integer, nullable=True)  # ForeignKey can be added if batch table exists


from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal
from datetime import date


class CandidateBase(BaseModel):
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    status: Optional[Literal["active", "discontinued", "break"]] = "active"
    workstatus: Optional[Literal["Citizen", "Visa", "Permanent resident", "EAD", "Waiting for Status"]] = None
    education: Optional[str] = None
    workexperience: Optional[str] = None
    ssn: Optional[str] = None
    agreement: Optional[Literal["Y", "N"]] = "N"
    secondaryemail: Optional[EmailStr] = None
    secondaryphone: Optional[str] = None
    address: Optional[str] = None
    linkedin_id: Optional[Literal["Y", "N"]] = None
    dob: Optional[date] = None
    emergcontactname: Optional[str] = None
    emergcontactemail: Optional[EmailStr] = None
    emergcontactphone: Optional[str] = None
    emergcontactaddrs: Optional[str] = None
    fee_paid: Optional[int] = None
    notes: Optional[str] = None
    batchid: int


class CandidateCreate(CandidateBase):
    enrolled_date: Optional[date] = Field(default_factory=date.today)


class CandidateOut(CandidateBase):
    id: int
    enrolled_date: date

    class Config:
        orm_mode = True
