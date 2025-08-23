from sqlalchemy import Column, Integer, String, Enum, DateTime, Boolean, Date ,DECIMAL, Text, ForeignKey, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, date
from pydantic import BaseModel, EmailStr, Field,validator
from typing import Optional, List, Literal
from enum import Enum





# Base = declarative_base()




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
    massemail_unsubscribe: Optional[bool] = None
    massemail_email_sent: Optional[bool] = None
    # moved_to_candidate: Optional[bool] = None


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

    model_config = {
        "from_attributes": True  # Enables ORM mode in Pydantic v2
    }


#----------------------------vendor - tables -----------------
# -------------------- Enums --------------------
class VendorTypeEnum(str, Enum):
    client = "client"
    third_party_vendor = "third-party-vendor"
    implementation_partner = "implementation-partner"
    sourcer = "sourcer"
    contact_from_ip= "contact-from-ip"


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


    model_config = {
        "from_attributes": True  # Enables ORM mode in Pydantic v2
    }


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

    @validator("type","vendor_type" ,pre=True)
    def normalize_enum_fields(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v


# class VendorCreate(VendorBase):
#     full_name: str
#     phone_number: Optional[str] = None
#     secondary_phone: Optional[str] = None
#     email: Optional[EmailStr] = None
#     type: Optional[VendorTypeEnum] = None
#     note: Optional[str] = None
#     linkedin_id: Optional[str] = None
#     company_name: Optional[str] = None
#     location: Optional[str] = None
#     city: Optional[str] = None
#     postal_code: Optional[str] = None
#     address: Optional[str] = None
#     country: Optional[str] = None
#     vendor_type: Optional[VendorTypeEnum] = None
#     linkedin_connected: Optional[str] = "NO"
#     intro_email_sent: Optional[str] = "NO"
#     intro_call: Optional[str] = "NO"   



class Vendor(VendorBase):
    id: int
    status: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True  # Enables ORM mode in Pydantic v2
    }


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

    model_config = {
        "from_attributes": True  # Enables ORM mode in Pydantic v2
    }

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
    
    
# class VendorCreate(VendorBase):
#     full_name: str
#     phone_number: Optional[str] = None
#     secondary_phone: Optional[str] = None
#     email: Optional[EmailStr] = None
#     type: Optional[VendorTypeEnum] = None
#     note: Optional[str] = None
#     linkedin_id: Optional[str] = None
#     company_name: Optional[str] = None
#     location: Optional[str] = None
#     city: Optional[str] = None
#     postal_code: Optional[str] = None
#     address: Optional[str] = None
#     country: Optional[str] = None
#     vendor_type: Optional[VendorTypeEnum] = None
#     linkedin_connected: Optional[str] = "NO"
#     intro_email_sent: Optional[str] = "NO"
#     intro_call: Optional[str] = "NO"


# class VendorResponse(BaseModel):
#     message: str




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

    model_config = {
        "from_attributes": True  # Enables ORM mode in Pydantic v2
    }

# ===============================Resources==============================

class CourseBase(BaseModel):
    name: str
    alias: str

class CourseCreate(CourseBase):
    pass

class Course(CourseBase):
    id: int

    model_config = {
        "from_attributes": True  # Enables ORM mode in Pydantic v2
    }

class SubjectBase(BaseModel):
    name: str

class SubjectCreate(SubjectBase):
    pass

class Subject(SubjectBase):
    id: int

    model_config = {
        "from_attributes": True  # Enables ORM mode in Pydantic v2
    }

class CourseSubjectBase(BaseModel):
    course_id: int
    subject_id: int

class CourseSubjectCreate(CourseSubjectBase):
    pass

class CourseSubject(CourseSubjectBase):
    id: int

    model_config = {
        "from_attributes": True  # Enables ORM mode in Pydantic v2
    }

class BatchBase(BaseModel):
    batchname: str
    courseid: int

class BatchCreate(BatchBase):
    pass

class Batch(BatchBase):
    batchid: int

    model_config = {
        "from_attributes": True  # Enables ORM mode in Pydantic v2
    }

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

    model_config = {
        "from_attributes": True  # Enables ORM mode in Pydantic v2
    }

class RecordingBatchBase(BaseModel):
    recording_id: int
    batch_id: int

class RecordingBatchCreate(RecordingBatchBase):
    pass

class RecordingBatch(RecordingBatchBase):
    id: int
      
    model_config = {
        "from_attributes": True  # Enables ORM mode in Pydantic v2
    }



class CourseContentCreate(BaseModel):
    Fundamentals: Optional[str] = None
    AIML: str
    UI: Optional[str] = None
    QE: Optional[str] = None

class CourseContentResponse(CourseContentCreate):
    id: int

    model_config = {
        "from_attributes": True  # Enables ORM mode in Pydantic v2
    }


    # ===============================
    
# Course Schemas 
class CourseResponse(BaseModel):
    id: int
    name: str
    alias: str
    description: Optional[str] = None
    syllabus: Optional[str] = None
    lastmoddatetime: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }

class CourseCreate(BaseModel):
    name: str
    alias: str
    description: Optional[str] = None
    syllabus: Optional[str] = None

class CourseUpdate(BaseModel):
    name: Optional[str] = None
    alias: Optional[str] = None
    description: Optional[str] = None
    syllabus: Optional[str] = None    

# Subject Schemas 
class SubjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    lastmoddatetime: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }

class SubjectCreate(BaseModel):
    name: str
    description: str

class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    
# CourseSubject Schemas 
class CourseSubjectResponse(BaseModel):
    subject_id: int
    course_id: int
    lastmoddatetime: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }

class CourseSubjectCreate(BaseModel):
    subject_id: int
    course_id: int
    
class CourseSubjectUpdate(BaseModel):
    course_id: int
    subject_id: int
    lastmoddatetime: Optional[datetime] = None
    
#coursecontent    
class CourseContentBase(BaseModel):
    Fundamentals: Optional[str] = None
    AIML: str
    UI: Optional[str] = None
    QE: Optional[str] = None

class CourseContentCreate(CourseContentBase):
    pass

class CourseContentUpdate(BaseModel):
    Fundamentals: Optional[str] = None
    AIML: Optional[str] = None
    UI: Optional[str] = None
    QE: Optional[str] = None

class CourseContentResponse(BaseModel):
    id: int
    Fundamentals: Optional[str] = None
    AIML: str
    UI: Optional[str] = None
    QE: Optional[str] = None

    model_config = {
        "from_attributes": True
    }
#coursematerial    
class CourseMaterialBase(BaseModel):
    subjectid: int
    courseid: int
    name: str
    description: Optional[str] = None
    type: str = 'P'
    link: str
    sortorder: int = Field(default=9999)

class CourseMaterialCreate(CourseMaterialBase):
    pass

class CourseMaterialUpdate(BaseModel):
    subjectid: Optional[int] = None
    courseid: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    link: Optional[str] = None
    sortorder: Optional[int] = None

class CourseMaterialResponse(BaseModel):
    id: int
    subjectid: int
    courseid: int
    name: str
    description: Optional[str] = None
    type: str
    link: str
    sortorder: int  

    model_config = {
        "from_attributes": True
    }
  
class BatchBase(BaseModel):
    batchname: str
    courseid: int

class BatchCreate(BatchBase):
    pass

class Batch(BatchBase):
    batchid: int

    model_config = {
        "from_attributes": True  # Enables ORM mode in Pydantic v2
    }

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

    model_config = {
        "from_attributes": True  # Enables ORM mode in Pydantic v2
    }

class RecordingBatchBase(BaseModel):
    recording_id: int
    batch_id: int

class RecordingBatchCreate(RecordingBatchBase):
    pass

class RecordingBatch(RecordingBatchBase):
    id: int

    model_config = {
        "from_attributes": True  # Enables ORM mode in Pydantic v2
    }


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

    model_config = {
        "from_attributes": True  # Enables ORM mode in Pydantic v2
    }

