from sqlalchemy import Column, Integer, String, Enum, DateTime, Boolean, Date ,DECIMAL, Text, ForeignKey, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, date
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Literal

Base = declarative_base()



class Token(BaseModel):
    access_token: str
    token_type: str
    team: str


class UserRegistration(BaseModel):
    uname: EmailStr
    passwd: str
    team: Optional[str] = None
    status: Optional[str] = None
    lastlogin: Optional[datetime] = None
    logincount: Optional[int] = None
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    message: Optional[str] = None
    registereddate: Optional[datetime] = None
    level3date: Optional[datetime] = None
    demo: Optional[str] = None
    enddate: Optional[date] = None
    googleId: Optional[str] = None
    reset_token: Optional[str] = None
    token_expiry: Optional[datetime] = None
    role: Optional[str] = None
    visa_status: Optional[str] = None
    experience: Optional[str] = None
    education: Optional[str] = None
    referby: Optional[str] = None
    specialization: Optional[str] = None
    notes: Optional[str] = None
  
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
    position: Optional[str] = None
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

# ------------------------------------Innovapath----------------------------
class TalentSearch(BaseModel):
    id: int
    full_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    role: Optional[str]
    experience: Optional[int]
    location: Optional[str]
    availability: Optional[str]
    skills: Optional[str]

    class Config:
        orm_mode = True




class VendorCreate(BaseModel):
    full_name: str
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None


class VendorResponse(BaseModel):
    message: str




# ================================================contact====================================
class ContactForm(BaseModel):
    firstName: str
    lastName: str
    email: EmailStr
    phone: str
    message: str


# -----------------------------------------------------unsubscribe-------------------------
class UnsubscribeRequest(BaseModel):
    email: EmailStr
                                                #for both unsubscribe_user and unsubscribe_leads
class UnsubscribeResponse(BaseModel):
    message: str



# -----------------------------------user_dashboard--------------------------------

class UserOut(BaseModel):
    email: EmailStr         # uname is email
    name: str               # fullname field mapped to name
    phone: Optional[str]

    class Config:
        orm_mode = True