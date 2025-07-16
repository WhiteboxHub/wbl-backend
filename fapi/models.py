from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import time, date, datetime
# from .db import Base, engine, get_db

class UserCreate(BaseModel):
    uname: str
    passwd: str

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
    visa_status: Optional[str] = Field(None, alias="visaStatus")  # with alias
    experience: Optional[str] = None
    education: Optional[str] = None
    specialization: Optional[str] = None
    referby: Optional[str] = Field(None, alias="referredBy")  # with alias

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


class RecentInterview(BaseModel):
    candidate_name: str
    candidate_role: Optional[str] = None
    interview_time: str
    interview_date: str
    interview_mode: Optional[str] = None
    client_name: Optional[str] = None
    interview_location: Optional[str] = None
    
# ------------------------------------------- Avatar ----------------------------------------
class LeadBase(BaseModel):
    name: Optional[str] = None
    startdate: Optional[datetime] = None
    phone: Optional[str] = None
    email: str
    priority: Optional[str] = None
    workstatus: Optional[str] = None
    source: Optional[str] = None
    workexperience: Optional[str] = None
    sourcename: Optional[str] = None
    course: Optional[str] = 'QA'
    intent: Optional[str] = None
    attendedclass: Optional[str] = None
    siteaccess: Optional[str] = None
    assignedto: Optional[str] = None
    status: Optional[str] = 'Open'
    secondaryemail: Optional[str] = None
    secondaryphone: Optional[str] = None
    address: Optional[str] = None
    spousename: Optional[str] = None
    spouseemail: Optional[str] = None
    spousephone: Optional[str] = None
    spouseoccupationinfo: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    zip: Optional[str] = None
    faq: Optional[str] = None
    callsmade: Optional[int] = 0
    # closedate: Optional[str] = None
    closedate: Optional[date]
    notes: Optional[str] = None



class LeadCreate(LeadBase):
    pass


class Lead(LeadBase):
    leadid: int

    class Config:
        orm_mode = True  # not strictly needed for raw dict cursor, but helpful for future ORM


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

