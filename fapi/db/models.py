from pydantic import BaseModel, EmailStr, Field
from decimal import Decimal 
from typing import Optional, List, Literal
from datetime import time, date, datetime
from sqlalchemy import Column, Integer, String, Enum, DateTime, Boolean, Date ,DECIMAL, Text, ForeignKey, TIMESTAMP, CHAR
from sqlalchemy.ext.declarative import declarative_base
from fapi.db.database import Base
Base = declarative_base()

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
    visa_status: Optional[str] = Field(None, alias="visaStatus")  
    experience: Optional[str] = None
    education: Optional[str] = None
    specialization: Optional[str] = None
    referby: Optional[str] = Field(None, alias="referredBy")  

    class Config:
        allow_population_by_field_name = True
        allow_population_by_alias = True




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


# --------google_login=-------------
# class AuthUser(Base): 
#     __tablename__ = "authuser"

#     id = Column(Integer, primary_key=True, index=True)
#     uname = Column(String(255), unique=True, index=True)
#     fullname = Column(String(255))
#     googleId = Column(String(255))
#     passwd = Column(String(255))
#     status = Column(String(50), default="inactive")
#     registereddate = Column(DateTime, default=datetime.utcnow)
class AuthUser(Base):
    __tablename__ = "authuser"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uname = Column(String(50), nullable=False, unique=True, index=True)
    passwd = Column(String(32), nullable=False)
    team = Column(String(255))
    status = Column(String(255))
    lastlogin = Column(DateTime)
    logincount = Column(Integer)
    fullname = Column(String(50))
    address = Column(String(50))
    phone = Column(String(20))
    state = Column(String(45))
    zip = Column(String(45))
    city = Column(String(45))
    country = Column(String(45))
    message = Column(Text)
    registereddate = Column(DateTime)
    level3date = Column(DateTime)
    lastmoddatetime = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    demo = Column(String(1), default='N', nullable=False)
    enddate = Column(Date, default=datetime(1990, 1, 1), nullable=False)
    googleId = Column(String(255))
    reset_token = Column(String(255))
    token_expiry = Column(DateTime)
    role = Column(String(100))
    visa_status = Column(String(50))
    experience = Column(String(100))
    education = Column(String(255))
    referby = Column(String(100))
    specialization = Column(String(255))

# class Lead(Base):
#     __tablename__ = "lead"
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     full_name = Column(String(255))
#     email = Column(String(255), unique=True)


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
    
# ------------------------------------------- Leads----------------------------------------
# class LeadORM(Base):
#     __tablename__ = "lead"

#     id = Column(Integer, primary_key=True, autoincrement=True)
#     full_name = Column(String(255))
#     entry_date = Column(DateTime)
#     phone = Column(String(20))
#     email = Column(String(255), nullable=False)
#     workstatus = Column(String(50))
#     status = Column(String(50))
#     secondary_email = Column(String(255))
#     secondary_phone = Column(String(20))
#     address = Column(String(255))
#     closed_date = Column(Date)
#     notes = Column(String(500))
#     last_modified = Column(DateTime)
#     massemail_unsubscribe = Column(String(5))
#     massemail_email_sent = Column(String(5))
#     moved_to_candidate = Column(Boolean)
class LeadORM(Base):
    __tablename__ = "lead"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    phone = Column(String(20), nullable=True)
    secondary_email = Column(String(255))
    secondary_phone = Column(String(20))
    address = Column(String(255), nullable=True)
    workstatus = Column(String(50), nullable=True)
    status = Column(String(50), default="Open")
    visa_status = Column(String, nullable=True)
    experience = Column(String, nullable=True)
    education = Column(String, nullable=True)
    referby = Column(String, nullable=True)
    specialization = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Tracking and system fields
    entry_date = Column(DateTime)
    closed_date = Column(Date)
    last_modified = Column(DateTime)
    massemail_unsubscribe = Column(String(5))
    massemail_email_sent = Column(String(5))
    moved_to_candidate = Column(Boolean)

    # created_at = Column(DateTime, default=datetime.utcnow)
    # is_processed = Column(Boolean, default=False)

# -------------------------------------------------------------------------------



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

class TalentSearchBaseModel(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str
    role: str
    experience: int
    location: str
    availability: str
    skills: str


class TalentSearch(TalentSearchBaseModel):
    id: int
    
    class Config:
        orm_mode = True


class UnsubscribeRequest(BaseModel):
    email: str





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
    id: int  

    class Config:
        from_attributes = True  


# ----------------------------------------Candidate------------------------------------
class CandidateORM(Base):
    __tablename__ = "candidate"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=True)
    enrolled_date = Column(Date, nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(100), nullable=True)
    status = Column(String(20), nullable=True)  # No ENUM used
    workstatus = Column(String(50), nullable=True)  # No ENUM used
    education = Column(String(200), nullable=True)
    workexperience = Column(String(200), nullable=True)
    ssn = Column(String(11), nullable=True)
    agreement = Column(String(1), default="N", nullable=True)
    secondaryemail = Column(String(100), nullable=True)
    secondaryphone = Column(String(45), nullable=True)
    address = Column(String(300), nullable=True)
    linkedin_id = Column(String(100), nullable=True)
    dob = Column(Date, nullable=True)
    emergcontactname = Column(String(100), nullable=True)
    emergcontactemail = Column(String(100), nullable=True)
    emergcontactphone = Column(String(100), nullable=True)
    emergcontactaddrs = Column(String(300), nullable=True)
    fee_paid = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    batchid = Column(Integer, nullable=False)



# --------------------------------------Candidate_Marketing-------------------------------


class CandidateMarketingORM(Base):
    __tablename__ = "candidate_marketing"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # candidate_id = Column(Integer, ForeignKey("candidate.candidateid", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(Integer)
    # primary_instructor_id = Column(Integer, ForeignKey("employee.id"), nullable=True)
    primary_instructor_id = Column(Integer)
    # sec_instructor_id = Column(Integer, ForeignKey("employee.id"), nullable=True)
    sec_instructor_id = Column(Integer)
    # marketing_manager = Column(Integer, ForeignKey("employee.id"), nullable=True)
    marketing_manager = Column(Integer)
    start_date = Column(Date, nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(Enum('active', 'break', 'not responding'), nullable=False)
    last_mod_datetime = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)


# --------------------------------------Candidate_Placement-------------------------------

class CandidatePlacementORM(Base):
    __tablename__ = "candidate_placement"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # candidate_id = Column(Integer, ForeignKey("candidate.candidateid", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(Integer)
    company = Column(String(200), nullable=False)
    placement_date = Column(Date, nullable=False)
    type = Column(Enum('Company', 'Client', 'Vendor', 'Implementation Partner'), nullable=True)
    status = Column(Enum('scheduled', 'cancelled'), nullable=False)
    base_salary_offered = Column(DECIMAL(10, 2), nullable=True)
    benefits = Column(Text, nullable=True)
    fee_paid = Column(DECIMAL(10, 2), nullable=True)
    notes = Column(Text, nullable=True)
    last_mod_datetime = Column(TIMESTAMP, default=None, onupdate=None)


# ===================================================register+++++++++++++++++++++


# class AuthUser(Base):
#     __tablename__ = "authuser"

#     id = Column(Integer, primary_key=True, index=True, autoincrement=True)
#     uname = Column(String(50), nullable=False, unique=True)
#     passwd = Column(String(32), nullable=False)
#     dailypwd = Column(String(255))
#     team = Column(String(255))
#     level = Column(String(255))
#     instructor = Column(String(100))
#     override = Column(CHAR(1))
#     status = Column(String(255), default="active")
#     lastlogin = Column(DateTime)
#     logincount = Column(Integer, default=0)
#     fullname = Column(String(50))
#     address = Column(String(50))
#     phone = Column(String(20))
#     state = Column(String(45))
#     zip = Column(String(45))
#     city = Column(String(45))
#     country = Column(String(45))
#     message = Column(Text)
#     registereddate = Column(DateTime, default=datetime.utcnow)
#     level3date = Column(DateTime)
#     lastmoddatetime = Column(TIMESTAMP)
#     demo = Column(CHAR(1))
#     enddate = Column(Date)
#     googleId = Column(String(255))
#     reset_token = Column(String(255))
#     token_expiry = Column(DateTime)
#     role = Column(String(100))
#     visa_status = Column(String(50))
#     experience = Column(String(100))
#     education = Column(String(255))
#     referby = Column(String(100))
#     specialization = Column(String(255))


# class LeadORM(Base):
#     __tablename__ = "lead"

#     id = Column(Integer, primary_key=True, index=True)
#     full_name = Column(String)
#     phone = Column(String)
#     email = Column(String, unique=True)
#     address = Column(String)
#     workstatus = Column(String)
#     status = Column(String, default="Open")
#     visa_status = Column(String)
#     experience = Column(String)
#     education = Column(String)
#     referby = Column(String)
#     specialization = Column(String)

# class LeadORM(Base):
#     __tablename__ = "lead"

#     id = Column(Integer, primary_key=True, autoincrement=True, index=True)
#     full_name = Column(String(255), nullable=False)
#     email = Column(String(255), nullable=False, unique=True, index=True)
#     phone = Column(String(20), nullable=True)
#     secondary_email = Column(String(255))
#     secondary_phone = Column(String(20))
#     address = Column(String(255), nullable=True)
#     workstatus = Column(String(50), nullable=True)
#     status = Column(String(50), default="Open")
#     visa_status = Column(String, nullable=True)
#     experience = Column(String, nullable=True)
#     education = Column(String, nullable=True)
#     referby = Column(String, nullable=True)
#     specialization = Column(String, nullable=True)
#     notes = Column(Text, nullable=True)
    
#     # Tracking and system fields
#     entry_date = Column(DateTime)
#     closed_date = Column(Date)
#     last_modified = Column(DateTime)
#     massemail_unsubscribe = Column(String(5))
#     massemail_email_sent = Column(String(5))
#     moved_to_candidate = Column(Boolean)

#     created_at = Column(DateTime, default=datetime.utcnow)
#     is_processed = Column(Boolean, default=False)