from sqlalchemy import Column, Integer, String, Enum, DateTime, Boolean, Date ,DECIMAL, Text, ForeignKey, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, date
from pydantic import BaseModel, EmailStr, Field,validator
from typing import Optional, List, Literal
from enum import Enum


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

#----------------------------vendor - tables -----------------
# -------------------- Enums --------------------
class VendorTypeEnum(str, Enum):
    client = "client"
    third_party_vendor = "third-party-vendor"
    implementation_partner = "implementation-partner"
    sourcer = "sourcer"
    ip_request_demo = "IP_REQUEST_DEMO"


# -------------------- VendorContactExtract Schemas --------------------
class VendorContactExtract(BaseModel):
    id: int
    full_name: str
    source_email: Optional[EmailStr] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_id: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    extraction_date: Optional[date] = None
    moved_to_vendor: Optional[bool] = None
    created_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class VendorContactExtractCreate(BaseModel):
    full_name: str
    source_email: Optional[EmailStr] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_id: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None


class VendorContactExtractUpdate(BaseModel):
    full_name: Optional[str] = None
    source_email: Optional[EmailStr] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_id: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    extraction_date: Optional[date] = None
    moved_to_vendor: Optional[bool] = None


# -------------------- Vendor Schemas --------------------
class VendorBase(BaseModel):
    full_name: str
    phone_number: Optional[str] = None
    secondary_phone: Optional[str] = None
    email: Optional[EmailStr] = None
    type: Optional[VendorTypeEnum] = None
    note: Optional[str] = None
    linkedin_id: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    vendor_type: Optional[VendorTypeEnum] = None
    linkedin_connected: Optional[str] = "NO"
    intro_email_sent: Optional[str] = "NO"
    intro_call: Optional[str] = "NO"

    @validator("email", pre=True)
    def empty_string_to_none(cls, v):
        return v or None

    @validator("type", "vendor_type", pre=True)
    def normalize_enum_fields(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v


class VendorCreate(VendorBase):
    pass


class Vendor(VendorBase):
    id: int
    status: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class VendorUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    secondary_phone: Optional[str] = None
    email: Optional[EmailStr] = None
    type: Optional[VendorTypeEnum] = None
    note: Optional[str] = None
    linkedin_id: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    vendor_type: Optional[VendorTypeEnum] = None
    status: Optional[Literal['active', 'working', 'not_useful', 'do_not_contact', 'inactive', 'prospect']] = None
    linkedin_connected: Optional[Literal['YES', 'NO']] = None
    intro_email_sent: Optional[Literal['YES', 'NO']] = None
    intro_call: Optional[Literal['YES', 'NO']] = None

# ---------------daily-vendor-activity --------------

class YesNoEnum(str, Enum):
    YES = "YES"
    NO = "NO"

class DailyVendorActivity(BaseModel):
    activity_id: int
    vendor_id: int
    application_date: Optional[date]
    linkedin_connected: Optional[YesNoEnum]
    contacted_on_linkedin: Optional[YesNoEnum]
    notes: Optional[str]
    employee_id: Optional[int]
    created_at: Optional[datetime]

    class Config:
        orm_mode = True

class DailyVendorActivityCreate(BaseModel):
    vendor_id: int
    application_date: Optional[date]
    linkedin_connected: Optional[YesNoEnum]
    contacted_on_linkedin: Optional[YesNoEnum]
    notes: Optional[str]
    employee_id: Optional[int]

class DailyVendorActivityUpdate(BaseModel):
    vendor_id: Optional[int] = None
    application_date: Optional[date] = None
    linkedin_connected: Optional[YesNoEnum] = None
    contacted_on_linkedin: Optional[YesNoEnum] = None
    notes: Optional[str] = None
    employee_id: Optional[int] = None