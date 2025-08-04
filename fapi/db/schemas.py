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
    massemail_unsubscribe: Optional[str] = None
    massemail_email_sent: Optional[str] = None
    moved_to_candidate: Optional[bool] = None


class LeadCreate(LeadBase):
    pass

class LeadSchema(LeadBase):
    id: int
    class Config:
        from_attributes = True  


# --------------------------------------------------------candidate-------------------------------------------------------

class CandidateBase(BaseModel):
    full_name: Optional[str]
    enrolled_date: Optional[date]
    email: Optional[str]
    phone: Optional[str]
    status: Optional[str]
    workstatus: Optional[str]
    education: Optional[str]
    workexperience: Optional[str]
    ssn: Optional[str]
    agreement: Optional[str]
    secondaryemail: Optional[str]
    secondaryphone: Optional[str]
    address: Optional[str]
    linkedin_id: Optional[str]
    dob: Optional[date]
    emergcontactname: Optional[str]
    emergcontactemail: Optional[str]
    emergcontactphone: Optional[str]
    emergcontactaddrs: Optional[str]
    fee_paid: Optional[int]
    notes: Optional[str]
    batchid: int

class CandidateCreate(CandidateBase):
    pass

class CandidateUpdate(CandidateBase):
    pass

class Candidate(CandidateBase):
    id: int

    class Config:
        from_attributes = True

class PaginatedCandidateResponse(BaseModel):
    page: int
    limit: int
    total: int
    data: List[Candidate]


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