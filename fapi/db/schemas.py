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
    dailypwd: Optional[str] = None
    team: Optional[str]
    level: Optional[str]
    instructor: Optional[str]
    override: Optional[str]
    lastlogin: Optional[str]
    logincount: Optional[int]
    firstname: Optional[str]
    lastname: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    city: Optional[str]
    Zip: Optional[str]
    country: Optional[str]
    message: Optional[str]
    visa_status: Optional[str]  # Maps from workauthorization
    registereddate: Optional[datetime]
    level3date: Optional[datetime]
    experience: Optional[str]
    education: Optional[str]
    specialization: Optional[str]
    referby: Optional[str]


# ----------------------Lead-------------------------

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




# class CandidateBase(BaseModel):
#     full_name: str
#     email: EmailStr
#     phone: Optional[str] = None
#     status: Optional[Literal["active", "discontinued", "break"]] = "active"
#     workstatus: Optional[Literal["Citizen", "Visa", "Permanent resident", "EAD", "Waiting for Status"]] = None
#     education: Optional[str] = None
#     workexperience: Optional[str] = None
#     ssn: Optional[str] = None
#     agreement: Optional[Literal["Y", "N"]] = "N"
#     secondaryemail: Optional[EmailStr] = None
#     secondaryphone: Optional[str] = None
#     address: Optional[str] = None
#     linkedin_id: Optional[Literal["Y", "N"]] = None
#     dob: Optional[date] = None
#     emergcontactname: Optional[str] = None
#     emergcontactemail: Optional[EmailStr] = None
#     emergcontactphone: Optional[str] = None
#     emergcontactaddrs: Optional[str] = None
#     fee_paid: Optional[int] = None
#     notes: Optional[str] = None
#     batchid: int


# class CandidateCreate(CandidateBase):
#     enrolled_date: Optional[date] = Field(default_factory=date.today)


# class CandidateOut(CandidateBase):
#     id: int
#     enrolled_date: date

#     class Config:
#         orm_mode = True





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

class CandidateDelete(CandidateBase):
    id: int

    class Config:
        from_attributes = True
    
class PaginatedCandidateResponse(BaseModel):
    page: int
    limit: int
    total: int
    data: List[CandidateBase]

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



# ================================================contact====================================

# class ContactCreate(BaseModel):
#     first_name: str
#     last_name: str
#     email: EmailStr
#     phone: Optional[str] = None
#     notes: Optional[str] = None
#     workstatus: Optional[str] = None


# class ContactFormResponse(BaseModel):
#     id: int
#     full_name: str
#     email: str
#     phone: Optional[str] = None
#     notes: Optional[str] = None

#     class Config:
#         orm_mode = True

class ContactForm(BaseModel):
    firstName: str
    lastName: str
    email: EmailStr
    phone: str
    message: str





from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class CourseBase(BaseModel):
    name: str
    alias: str

class CourseCreate(CourseBase):
    pass

class Course(CourseBase):
    id: int

    class Config:
        orm_mode = True

class SubjectBase(BaseModel):
    name: str

class SubjectCreate(SubjectBase):
    pass

class Subject(SubjectBase):
    id: int

    class Config:
        orm_mode = True

class CourseSubjectBase(BaseModel):
    course_id: int
    subject_id: int

class CourseSubjectCreate(CourseSubjectBase):
    pass

class CourseSubject(CourseSubjectBase):
    id: int

    class Config:
        orm_mode = True

class BatchBase(BaseModel):
    batchname: str
    courseid: int

class BatchCreate(BatchBase):
    pass

class Batch(BatchBase):
    batchid: int

    class Config:
        orm_mode = True

class RecordingBase(BaseModel):
    batchname: str
    description: Optional[str] = None
    type: Optional[str] = None
    classdate: Optional[datetime] = None
    link: Optional[str] = None
    videoid: Optional[str] = None
    subject: Optional[str] = None
    filename: Optional[str] = None
    lastmoddatetime: Optional[datetime] = None
    new_subject_id: Optional[int] = None

class RecordingCreate(RecordingBase):
    pass

class Recording(RecordingBase):
    id: int

    class Config:
        orm_mode = True

class RecordingBatchBase(BaseModel):
    recording_id: int
    batch_id: int

class RecordingBatchCreate(RecordingBatchBase):
    pass

class RecordingBatch(RecordingBatchBase):
    id: int

    class Config:
        orm_mode = True

class SessionBase(BaseModel):
    title: str
    link: Optional[str] = None
    videoid: Optional[str] = None
    subject: Optional[str] = None
    type: Optional[str] = None
    sessiondate: Optional[datetime] = None
    lastmoddatetime: Optional[datetime] = None
    subject_id: int

class SessionCreate(SessionBase):
    pass

class Session(SessionBase):
    sessionid: int

    class Config:
        orm_mode = True
