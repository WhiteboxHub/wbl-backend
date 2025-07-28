from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import time, date, datetime
from sqlalchemy import Column, Integer, String, DateTime, Date, Boolean
from sqlalchemy.ext.declarative import declarative_base
# from .db import Base, engine, get_db

class UserCreate(BaseModel):
    uname: str
    passwd: str


# class UserRegistration(BaseModel):
#     uname: str
#     passwd: str
#     dailypwd: Optional[str] = None
#     team: Optional[str] = None
#     level: Optional[str] = None
#     instructor: Optional[str] = None
#     override: Optional[str] = None
#     status: Optional[str] = None
#     lastlogin: Optional[str] = None
#     logincount: Optional[str] = None
#     # firstname: Optional[str] = None
#     # lastname: Optional[str] = None
#     firstname: Optional[str] = Field(None, alias="firstName")
#     lastname: Optional[str] = Field(None, alias="lastName")
#     fullname: Optional[str] = None
#     phone: Optional[str] = None
#     address: Optional[str] = None
#     city: Optional[str] = None
#     Zip: Optional[str] = None
#     country: Optional[str] = None
#     message: Optional[str] = None
#     registereddate: Optional[str] = None
#     level3date: Optional[str] = None
#     last: Optional[str] = None
#     visastatus: Optional[str] = Field(None, alias="visaStatus")  # with alias
#     experience: Optional[str] = None
#     education: Optional[str] = None
#     specialization: Optional[str] = None
#     referred_by: Optional[str] = Field(None, alias="referredBy")  # with alias

#     class Config:
#         allow_population_by_field_name = True


# class ContactForm(BaseModel):
#     firstName: str
#     lastName: str
#     email: str
#     phone: str
#     message: str

# class Token(BaseModel):
#     access_token: str
#     token_type: str

# class EmailRequest(BaseModel):
#     email: EmailStr

# class ResetPasswordRequest(BaseModel):
#     email: EmailStr

# class ResetPassword(BaseModel):
#     token: str
#     new_password: str


# # class UserCreate(BaseModel):
# #     email: str
# #     name: str   
# #     google_id: str


# # Model for Google user creation
# class GoogleUserCreate(BaseModel):
#     name: str
#     email: str
#     google_id: str

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import time, date, datetime
from decimal import Decimal 
class UserCreate(BaseModel):
    uname: str
    passwd: str



class UserRegistration(BaseModel):
    uname: str
    passwd: str
    dailypwd: Optional[str] = None
    team: Optional[str] = None
    level: Optional[str] = None
    instructor: Optional[str] = None
    override: Optional[str] = None
    status: Optional[str] = None
    lastlogin: Optional[str] = None
    logincount: Optional[str] = None
    # firstname: Optional[str] = None
    # lastname: Optional[str] = None
    firstname: Optional[str] = Field(None, alias="firstName")
    lastname: Optional[str] = Field(None, alias="lastName")
    fullname: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    Zip: Optional[str] = None
    country: Optional[str] = None
    message: Optional[str] = None
    registereddate: Optional[str] = None
    level3date: Optional[str] = None
    last: Optional[str] = None
    visastatus: Optional[str] = Field(None, alias="visaStatus")  # with alias
    experience: Optional[str] = None
    education: Optional[str] = None
    specialization: Optional[str] = None
    referred_by: Optional[str] = Field(None, alias="referredBy")  # with alias

    class Config:
        allow_population_by_field_name = True
        allow_population_by_alias = True


class ContactForm(BaseModel):
    firstName: str
    lastName: str
    email: str
    phone: str
    message: str


class Token(BaseModel):
    access_token: str
    token_type: str


class EmailRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    token: str
    new_password: str


class GoogleUserCreate(BaseModel):
    name: str
    email: str
    google_id: str


# ---------------------------- Innovapath - Request demo --------------------

class VendorCreate(BaseModel):
    full_name: str
    phone_number: str
    email: Optional[EmailStr] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    note: Optional[str] = None
# --------------------------------------------------------------------------

class RecentPlacement(BaseModel):
    id: int
    candidate_name: str
    company: str
    position: str
    placement_date: str


# class RecentInterview(BaseModel):
#     id: int
#     candidate_name: str
#     candidate_role: Optional[str]
#     interview_time: time
#     interview_date: date
#     interview_mode: Optional[str]
#     client_name: Optional[str]
#     interview_location: Optional[str]
#     created_at: datetime
class RecentInterview(BaseModel):
    candidate_name: str
    candidate_role: Optional[str] = None
    interview_time: str
    interview_date: str
    interview_mode: Optional[str] = None
    client_name: Optional[str] = None
    interview_location: Optional[str] = None
    
# ------------------------------------------- Leads----------------------------------------


# Base class shared by all lead operations

class LeadBase(BaseModel):
    id: Optional[int] = None
    full_name: Optional[str] = None
    entry_date: Optional[datetime] = None
    phone: Optional[str] = None
    email: EmailStr  # Required field
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
    moved_to_candidate: Optional[bool] = None  # Assuming TINYINT(1) represents boolean

# For creating new leads
class LeadCreate(LeadBase):
    email: EmailStr  # Ensure email is still required
    id: Optional[int] = None  # Usually auto-incremented

# For reading/fetching lead data (response model)
class Lead(LeadBase):
    leadid: int = Field(..., alias="id")  # Maps DB 'id' to model field 'leadid'

    class Config:
        from_attributes = True
        populate_by_name = True






class CandidateBase(BaseModel):
    name: Optional[str]
    enrolleddate: Optional[date]
    email: Optional[str]
    course: Optional[str]
    phone: Optional[str]
    status: Optional[str]
    workstatus: Optional[str]
    education: Optional[str]
    workexperience: Optional[str]
    ssn: Optional[str]
    agreement: Optional[str]
    promissory: Optional[str]
    driverslicense: Optional[str]
    workpermit: Optional[str]
    wpexpirationdate: Optional[date]
    offerletter: Optional[str]
    secondaryemail: Optional[str]
    secondaryphone: Optional[str]
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    country: Optional[str]
    zip: Optional[str]
    linkedin: Optional[str]
    dob: Optional[date]
    emergcontactname: Optional[str]
    emergcontactemail: Optional[str]
    emergcontactphone: Optional[str]
    emergcontactaddrs: Optional[str]
    guidelines: Optional[str]
    ssnvalidated: Optional[str]
    bgv: Optional[str]
    term: Optional[str]
    feepaid: Optional[float]
    feedue: Optional[float]
    salary0: Optional[str]
    salary6: Optional[str]
    salary12: Optional[str]
    guarantorname: Optional[str]
    guarantordesignation: Optional[str]
    guarantorcompany: Optional[str]
    contracturl: Optional[str]
    empagreementurl: Optional[str]
    offerletterurl: Optional[str]
    dlurl: Optional[str]
    workpermiturl: Optional[str]
    ssnurl: Optional[str]
    referralid: Optional[int]
    portalid: Optional[int]
    avatarid: Optional[int]
    notes: Optional[str]
    batchname: str
    background: Optional[str]
    recruiterassesment: Optional[str]
    processflag: Optional[str] = "N"
    defaultprocessflag: Optional[str] = "N"
    originalresume: Optional[str]
    statuschangedate: Optional[date]
    diceflag: Optional[str]
    batchid: int
    emaillist: Optional[str] = "Y"
    marketing_startdate: Optional[date]
    instructor: Optional[str]
    second_instructor: Optional[str]

class CandidateCreate(CandidateBase):
    pass

class CandidateUpdate(CandidateBase):
    pass

class Candidate(CandidateBase):
    candidateid: int

    class Config:
        orm_mode = True

        





class PlacementBase(BaseModel):
    candidate_id: Optional[int]
    candidate_name: Optional[str]
    candidate_email: Optional[str]
    company: Optional[str]
    client_id: Optional[int]
    batch: Optional[str]
    # placed_date: Optional[date]
    placement_date: Optional[date]
    status: Optional[str]
    marketing_email_address: Optional[str]
    vendor_or_client_name: Optional[str]
    vendor_or_client_contact: Optional[str]
    start_date: Optional[date]
    position: Optional[str]
    amount_paid: Optional[float]
    work_authorization: Optional[str]
    experience_in_resume: Optional[str]
    role: Optional[str]
    job_location: Optional[str]
    terms_and_conditions: Optional[str]
    notes: Optional[str]
    candidate_profile_folder: Optional[str]
    placement_verified: Optional[bool] = False
    joining_letter_url: Optional[str]


class PlacementCreate(PlacementBase):
    pass


class PlacementUpdate(PlacementBase):
    pass


class Placement(PlacementBase):
    id: int

    class Config:
        orm_mode = True
# =======


class RecentPlacement(BaseModel):
    id: int
    candidate_name: str
    company: str
    position: str
    placement_date: str


class RecentInterview(BaseModel):
    id: int
    candidate_name: str
    candidate_role: Optional[str]
    interview_time: time
    interview_date: date
    interview_mode: Optional[str]
    client_name: Optional[str]
    interview_location: Optional[str]
    created_at: datetime


# .......................................NEW INNOVAPATH..............................


class CandidateMarketingBaseModel(BaseModel):
    candidate_id: int
    full_name: str
    email: str
    phone: str
    role: str
    experience: int
    location: str
    availability: str
    skills: str

# class CandidateMarketingCreate(CandidateMarketingBase):
    # pass

class CandidateMarketing(CandidateMarketingBaseModel):
    id: int
    
    class Config:
        orm_mode = True






from pydantic import BaseModel
from typing import Optional
from datetime import date

class VendorBase(BaseModel):
    id: Optional[int]
    full_name: Optional[str]
    phone_number: Optional[str]
    email: Optional[str]
    city: Optional[str] = None
    postal_code: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    type: Optional[str] = None
    note: Optional[str] = None
    last_contacted: Optional[date] = None
class VendorCreate(VendorBase):
    pass

class VendorUpdate(VendorBase):
    pass

class VendorResponse(VendorBase):
    id: int  # ✅ correct usage in Pydantic

    class Config:
        from_attributes = True  # Use this if using Pydantic v2 instead of `orm_mode = True`
