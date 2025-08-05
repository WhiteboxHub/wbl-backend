from sqlalchemy import Column, Integer, String, Enum, DateTime, Boolean, Date ,DECIMAL, Text, ForeignKey, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, date
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Literal



Base = declarative_base()

  
class LeadBase(BaseModel):
    full_name: Optional[str] = None
    entry_date: Optional[datetime] = None
    phone: Optional[str] = None
    email: EmailStr
    workstatus: Optional[str] = None
    status: Optional[str] = None
    secondary_email: Optional[str] = None
    secondary_phone: Optional[str] = None
    address: Optional[str] = None
    closed_date: Optional[date] = None
    notes: Optional[str] = None
    last_modified: Optional[datetime] = None
    massemail_unsubscribe: Optional[bool] = None
    massemail_email_sent: Optional[bool] = None
    moved_to_candidate: Optional[bool] = None


class LeadCreate(LeadBase):
    pass

class LeadSchema(LeadBase):
    id: int
    class Config:
        from_attributes = True  


# --------------------------------------------------------candidate-------------------------------------------------------

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

class CandidateMarketingBase(BaseModel):
    candidate_id: int
    primary_instructor_id: Optional[int] = None
    sec_instructor_id: Optional[int] = None
    marketing_manager: Optional[int] = None
    start_date: date
    notes: Optional[str] = None
    status: Literal['active', 'break', 'not responding']

class CandidateMarketingCreate(CandidateMarketingBase):
    pass

class CandidateMarketing(CandidateMarketingBase):
    id: int
    last_mod_datetime: Optional[datetime]

    class Config:
        from_attributes = True


class CandidatePlacementBase(BaseModel):
    candidate_id: int
    company: str
    placement_date: date
    type: Optional[Literal['Company', 'Client', 'Vendor', 'Implementation Partner']] = None
    status: Literal['scheduled', 'cancelled']
    base_salary_offered: Optional[float] = None
    benefits: Optional[str] = None
    fee_paid: Optional[float] = None
    notes: Optional[str] = None

class CandidatePlacementCreate(CandidatePlacementBase):
    pass

class CandidatePlacement(CandidatePlacementBase):
    id: int
    last_mod_datetime: Optional[datetime]
    class Config:
        from_attributes = True

# -----------------------------------------------------------------------------------

class GoogleUserCreate(BaseModel):
    name: str
    email: str
    google_id: str

    class Config:
        orm_mode = True