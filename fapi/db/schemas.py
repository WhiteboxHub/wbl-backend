from sqlalchemy import Column, Integer, String, Enum, DateTime, Boolean, Date ,DECIMAL, Text, ForeignKey, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, date
from pydantic import BaseModel,ConfigDict, EmailStr, field_validator, validator, Field
from typing import Optional, List, Literal, Union,Dict,Any

from enum import Enum



# class EmployeeBase(BaseModel):
#     name: Optional[str] =None
#     email: Optional[str] =None
#     phone: Optional[str] = None
#     address: Optional[str] = None
#     state: Optional[str] = None
#     dob: Optional[date] = None
#     startdate: Optional[date] = None
#     enddate: Optional[datetime] = None
#     notes: Optional[str] = None
#     status: Optional[int] = None
#     instructor: Optional[int] = None
#     aadhaar: Optional[str] = None

# class EmployeeCreate(EmployeeBase):
#     pass

# # class EmployeeUpdate(EmployeeBase):
# #     id: int

# #     @field_validator("dob", "startdate", "enddate", mode="before")
# #     def handle_invalid_dates(cls, v):
# #         if isinstance(v, str) and v.startswith("0000-00-00"):
# #             return None
# #         return v

# #     model_config = ConfigDict(from_attributes=True)


# class EmployeeUpdate(BaseModel):
#     id: int
#     name: Optional[str] = None
#     email: Optional[str] = None
#     phone: Optional[str] = None
#     address: Optional[str] = None
#     state: Optional[str] = None
#     dob: Optional[date] = None
#     startdate: Optional[date] = None
#     enddate: Optional[date] = None
#     notes: Optional[str] = None
#     status: Optional[int] = None
#     instructor: Optional[int] = None
#     aadhaar: Optional[str] = None

#     @field_validator("dob", "startdate", "enddate", mode="before")
#     def handle_invalid_dates(cls, v):
#         if v == "":
#             return None
#         return v

#     model_config = ConfigDict(from_attributes=True)
from pydantic import BaseModel, field_validator, ConfigDict
from typing import Optional
from datetime import date

class EmployeeBase(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    state: Optional[str] = None
    dob: Optional[date] = None
    startdate: Optional[date] = None
    enddate: Optional[date] = None
    notes: Optional[str] = None
    status: Optional[int] = None
    instructor: Optional[int] = None
    aadhaar: Optional[str] = None

    @field_validator("dob", "startdate", "enddate", mode="before")
    def handle_empty_dates(cls, v):
        if v == "":
            return None
        return v

class EmployeeCreate(EmployeeBase):
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)

class EmployeeUpdate(EmployeeBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

class Employee(EmployeeBase):
    id: int

    @field_validator("dob", "startdate", "enddate", mode="before")
    def handle_invalid_dates(cls, v):
        if isinstance(v, str) and v.startswith("0000-00-00"):
            return None
        return v

    class Config:
        from_attributes = True

class EmployeeBirthdayOut(BaseModel):
    id: int
    name: str
    dob: date
    # wish: str | None = None 
    wish: Optional[str] = None     

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str
    team: Optional[str] = None
    team: Optional[str] = None

class TokenRequest(BaseModel):
    access_token: str
    # token_type: str



class UserRegistration(BaseModel):
    uname: EmailStr
    passwd: str
    team: Optional[str] = None
    status: Optional[str] = None
    # lastlogin: Optional[datetime] = None
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
  

class AuthUserBase(BaseModel):
    uname: Union[EmailStr, str] = None
    fullname: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    team: Optional[str] = None
    role: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country: Optional[str] = None
    message: Optional[str] = None
    notes: Optional[str] = None
    visa_status: Optional[str] = None
    googleId: Optional[str] = None


    @validator("uname", pre=True)
    def validate_uname(cls, v):
        if not v:
            return None
        try:
            return EmailStr.validate(v)
        except Exception:
            return v 

class AuthUserCreate(AuthUserBase):
    uname: EmailStr
    passwd: str

class AuthUserUpdate(AuthUserBase):
    passwd: Optional[str] = None

class AuthUserResponse(AuthUserBase):
    id: int
    # lastlogin: Optional[datetime] = None
    logincount: Optional[int] = None
    registereddate: Optional[datetime] = None
    # level3date: Optional[datetime] = None
    # lastmoddatetime: Optional[datetime] = None
    # demo: Optional[str] = "N"
    enddate: Optional[date] = None
    # reset_token: Optional[str] = None
    # token_expiry: Optional[datetime] = None


    @validator(
        # "lastlogin",
        "registereddate",
        # "level3date",
        # "lastmoddatetime",
        "enddate",
        # "token_expiry",
        pre=True,
    )
    def fix_invalid_datetime(cls, v):
        if v in ("0000-00-00 00:00:00", "0000-00-00", None, ""):
            return None
        return v

    class Config:
        orm_mode = True

class PaginatedUsers(BaseModel):
    total: int
    page: int
    per_page: int
    users: List[AuthUserResponse]



# ----------------------------------------------------------------------------------------

class LeadBase(BaseModel):
    full_name: Optional[str] = None
    entry_date: Optional[datetime] = None
    phone: Optional[str] = None
    email: EmailStr
    workstatus: Optional[str] = None
    status: Optional[str] = "open"
    secondary_email: Optional[str] = None
    secondary_phone: Optional[str] = None
    address: Optional[str] = None
    closed_date: Optional[date] = None
    notes: Optional[str] = None
    # last_modified: Optional[date] = None

    massemail_unsubscribe: Optional[bool] = None
    massemail_email_sent: Optional[bool] = None

    moved_to_candidate: Optional[bool] = None


class LeadCreate(LeadBase):
    pass
class LeadUpdate(LeadBase):
    pass
class LeadSchema(LeadBase):
    id: int
    class Config:
        from_attributes = True  
# --------------------------------------------------------candidate-------------------------------------------------------


class CandidateBase(BaseModel):

    id:int
    full_name: Optional[str]
    name: Optional[str] = Field(None, alias="full_name")
    enrolled_date: Optional[date]
    email: Optional[str]
    phone: Optional[str]
    status: Optional[Literal['active', 'discontinued', 'break', 'closed']] = None   
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
    candidate_folder: Optional[str] = None   


    class Config:
        orm_mode = True
        allow_population_by_field_name = True
class CandidateCreate(CandidateBase):
    pass 

class StatusEnum(str, Enum):
    active = 'active'
    discontinued = 'discontinued'
    break_ = 'break'
    closed = 'closed'

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

# class CandidateBase(BaseModel):
#     name: str

    class Config:
        orm_mode = True

# -------------------------------------------------




class CandidateMarketingBase(BaseModel):
    candidate_id: int
    marketing_manager: Optional[int] = None
    start_date: date
    notes: Optional[str] = None
    status: Literal["active", "break", "not responding"]
    instructor1_id: Optional[int] = None
    instructor2_id: Optional[int] = None
    instructor3_id: Optional[int] = None
    email: Optional[str] = None
    password: Optional[str] = None
    google_voice_number: Optional[str] = None
    rating: Optional[int] = None
    priority: Optional[int] = None
    candidate: Optional[CandidateBase]

    # extra fields for name display in UI
    instructor1: Optional[EmployeeBase] = None
    instructor2: Optional[EmployeeBase] = None
    instructor3: Optional[EmployeeBase] = None
    marketing_manager_obj: Optional[EmployeeBase] = None


class CandidateMarketingCreate(CandidateMarketingBase):
    pass


class CandidateMarketing(CandidateMarketingBase):
    id: int
    last_mod_datetime: Optional[datetime]

    class Config:
        from_attributes = True










# --------------------------------------------
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
# ----------------------------------------------------

class InstructorOut(BaseModel):
    id: int
    full_name: str  # adjust if your Instructor model uses a different field name
    class Config:
        orm_mode = True



# =====================================employee  --hkd ========================


# ------------------hkd-------------------------


 
class CandidatePreparationBase(BaseModel):
    id: int = Field(..., alias="id")
    candidate_id: int
    batch: Optional[str] = None
    start_date: Optional[date] = None
    status: str
    instructor1_id: Optional[int] = Field(None, alias="instructor_1id")
    instructor2_id: Optional[int] = Field(None, alias="instructor_2id")
    instructor3_id: Optional[int] = Field(None, alias="instructor_3id")
    rating: Optional[str] = None
    tech_rating: Optional[str] = None
    communication: Optional[str] = None
    years_of_experience: Optional[str] = None
    topics_finished: Optional[str] = None
    current_topics: Optional[str] = None
    target_date_of_marketing: Optional[date] = None
    notes: Optional[str] = None

    candidate: Optional[CandidateBase]  # candidate relationship
    instructor1: Optional[EmployeeBase]  # instructor relationships
    instructor2: Optional[EmployeeBase]
    instructor3: Optional[EmployeeBase]

    class Config:
        from_attributes = True  # Pydantic v2 equivalent of orm_mode
    


class CandidatePreparationCreate(CandidatePreparationBase):
    id: int = Field(..., alias="id")
    candidate_id: int
    batch: Optional[str] = None
    start_date: Optional[date] = None
    status: str
    instructor1_id: Optional[int] = Field(None, alias="instructor_1id")
    instructor2_id: Optional[int] = Field(None, alias="instructor_2id")
    instructor3_id: Optional[int] = Field(None, alias="instructor_3id")
    rating: Optional[str] = None
    tech_rating: Optional[str] = None
    communication: Optional[str] = None
    years_of_experience: Optional[str] = None
    topics_finished: Optional[str] = None
    current_topics: Optional[str] = None
    target_date_of_marketing: Optional[date] = None
    notes: Optional[str] = None
    candidate: Optional[CandidateBase]  # added line

class CandidatePreparationUpdate(BaseModel):
    batch: Optional[str] = None
    start_date: Optional[date] = None
    status: Optional[str] = None
    instructor1_id: Optional[int] = None
    instructor2_id: Optional[int] = None
    instructor3_id: Optional[int] = None
    rating: Optional[str] = None
    tech_rating: Optional[str] = None
    communication: Optional[str] = None
    years_of_experience: Optional[str] = None
    topics_finished: Optional[str] = None
    current_topics: Optional[str] = None
    target_date_of_marketing: Optional[date] = None
    notes: Optional[str] = None
    candidate: Optional[CandidateBase]  # added line
    


# class CandidatePreparationOut(CandidatePreparationBase):
#     id: int
#     last_mod_datetime: Optional[datetime]
    
#     instructor1_id: Optional[int] = Field(None, alias="instructor_1id")
#     instructor2_id: Optional[int] = Field(None, alias="instructor_2id")
#     instructor3_id: Optional[int] = Field(None, alias="instructor_3id")

#     candidate: Optional[CandidateBase] 
#     model_config = {
#         "from_attributes": True,
#         "populate_by_name": True  
#     }


class CandidatePreparationOut(BaseModel):
    id: int
    batch: Optional[str] = None
    start_date: Optional[date] = None
    status: str
    rating: Optional[str] = None
    tech_rating: Optional[str] = None
    communication: Optional[str] = None
    years_of_experience: Optional[str] = None
    topics_finished: Optional[str] = None
    current_topics: Optional[str] = None
    target_date_of_marketing: Optional[date] = None
    notes: Optional[str] = None
    last_mod_datetime: Optional[datetime]

    candidate: Optional[CandidateBase]

    # Nested instructors
    instructor1: Optional[EmployeeBase]
    instructor2: Optional[EmployeeBase]
    instructor3: Optional[EmployeeBase]

    # Keep the IDs for reference if needed
    instructor1_id: Optional[int] = Field(None, alias="instructor_1id")
    instructor2_id: Optional[int] = Field(None, alias="instructor_2id")
    instructor3_id: Optional[int] = Field(None, alias="instructor_3id")

    class Config:
        from_attributes = True
        populate_by_name = True


# --------------------------------------------------
class InterviewTypeEnum(str, Enum):
    phone = "Phone"
    virtual = "Virtual"
    in_person = "In Person"
    assessment = "Assessment"


class FeedbackEnum(str, Enum):
    negative = "Negative"
    positive = "Positive"
    no_response = "No Response"
    cancelled = "Cancelled" 
    


class CandidateInterviewBase(BaseModel):
    candidate_id: int
    # candidate_name: Optional[str] = None
    company: str
    interviewer_emails: Optional[str] = None
    interviewer_contact: Optional[str] = None
    interview_date: date
    interview_type: Optional[InterviewTypeEnum] = None
    recording_link: Optional[str] = None
    backup_url: Optional[str] = None
    status: Optional[str] = None
    feedback: Optional[FeedbackEnum] = None
    notes: Optional[str] = None
    candidate: Optional[CandidateBase]  # added line


class CandidateInterviewCreate(CandidateInterviewBase):
    pass


class CandidateInterviewUpdate(BaseModel):
    candidate_id: Optional[int] = None
    # candidate_name: Optional[str] = None
    company: Optional[str] = None
    interviewer_emails: Optional[str] = None
    interviewer_contact: Optional[str] = None
    interview_date: Optional[date] = None
    interview_type: Optional[InterviewTypeEnum] = None
    recording_link: Optional[str] = None
    backup_url: Optional[str] = None
    status: Optional[str] = None
    feedback: Optional[FeedbackEnum] = None
    notes: Optional[str] = None
    candidate: Optional[CandidateBase]  # added line


class CandidateInterviewOut(CandidateInterviewBase):
    id: int
    # candidate_name: Optional[str]   # only in output
    last_mod_datetime: Optional[datetime]
    candidate: Optional[CandidateBase]  # added line

    class Config:
        from_attributes = True









# -----------------------------------------------------------------------------------

class GoogleUserCreate(BaseModel):
    name: str
    email: str
    google_id: str

    model_config = {
        "from_attributes": True  
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
    full_name: Optional[str] =None
    source_email: Optional[EmailStr] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_id: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    extraction_date: Optional[date] = None
    moved_to_vendor: Optional[bool] = None
    created_at: Optional[datetime] = None
    linkedin_internal_id : Optional[str] = None 


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
        "from_attributes": True  
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
    linkedin_internal_id : Optional[str] = None 



# -------------------- Vendor Schemas --------------------
class VendorBase(BaseModel):
    full_name: Optional[str] =None
    phone_number: Optional[str] = None
    secondary_phone: Optional[str] = None
    email: Optional[EmailStr] = None
    type: Optional[VendorTypeEnum] = None
    notes: Optional[str] = None
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
    intro_call: Optional[str] ="No"
    linkedin_internal_id: Optional[str] = None

    @validator("email", pre=True)
    def empty_string_to_none(cls, v):
        return v or None

    @validator("type","vendor_type" ,pre=True)  
    def normalize_enum_fields(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v




class Vendor(VendorBase):
    id: int
    status: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True  
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
    linkedin_internal_id: Optional[str] = None

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
        "from_attributes": True  
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
    email: EmailStr         
    name: str               
    email: EmailStr         
    name: str               
    phone: Optional[str]

    model_config = { 
        "from_attributes": True  
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
        "from_attributes": True  
    }

class SubjectBase(BaseModel):
    name: str


class SubjectOut(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True

class SubjectCreate(SubjectBase):
    pass

class Subject(SubjectBase):
    id: int

    model_config = {
        "from_attributes": True  
    }

class CourseSubjectBase(BaseModel):
    course_id: int
    subject_id: int

class CourseSubjectCreate(CourseSubjectBase):
    pass

class CourseSubject(CourseSubjectBase):
    id: int

    model_config = {
        "from_attributes": True  
    }

# ----------------------------------batch-------------



class BatchBase(BaseModel):
    batchname: str
    orientationdate: Optional[date] = None
    subject: Optional[str] = "ML"
    startdate: Optional[date] = None
    enddate: Optional[date] = None
    courseid: Optional[int] = None

class BatchCreate(BatchBase):
    pass

class BatchUpdate(BatchBase):
    pass


class BatchOut(BatchBase):
    batchid: int
    # lastmoddatetime: Optional[datetime]

    # @field_validator("lastmoddatetime", mode="before")
    # def handle_invalid_datetime(cls, v):
    #     if v in (None, "0000-00-00 00:00:00"):
    #         return None
    #     return v

    class Config:
        orm_mode = True

# -----------------------------------------------------------

# -----------------------------------------------------Recordings------------------------------------

class RecordingBase(BaseModel):
    batchname: str
    description: Optional[str] = None
    type: Optional[str] = "class"
    classdate: Optional[datetime] = None
    link: Optional[str] = None
    videoid: Optional[str] = None
    subject: Optional[str] = None
    filename: Optional[str] = None
    # lastmoddatetime: Optional[datetime] = None
    new_subject_id: Optional[int] = None

class RecordingCreate(RecordingBase):
    pass

class RecordingUpdate(RecordingBase):
    pass

class RecordingOut(RecordingBase):
    id: int
    # lastmoddatetime: Optional[datetime]

    class Config:
        orm_mode = True


class Recording(RecordingBase):
    id: int

    model_config = {
 
        "from_attributes": True  
    }

class PaginatedRecordingOut(BaseModel):
    total: int
    page: int
    per_page: int
    recordings: List[RecordingOut]
# -----------------------------------------------------------------------------


class RecordingBatchBase(BaseModel):
    recording_id: int
    batch_id: int

class RecordingBatchCreate(RecordingBatchBase):
    pass

class RecordingBatch(RecordingBatchBase):
    id: int
      
    model_config = {

        "from_attributes": True  
    }



class CourseContentCreate(BaseModel):
    Fundamentals: Optional[str] = None
    AIML: str
    UI: Optional[str] = None
    QE: Optional[str] = None

class CourseContentResponse(CourseContentCreate):
    id: int

    model_config = {
 
        "from_attributes": True  
    }



# -------------------------
    
# Course Schemas 
class CourseResponse(BaseModel):
    id: int
    name: str
    alias: str
    description: Optional[str] = None
    syllabus: Optional[str] = None
    #lastmoddatetime: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }

class CourseCreate(BaseModel):
    name: str
    alias: str
    description: Optional[str] = None
    syllabus: Optional[str] = None

    model_config = {
        "from_attributes": True  
    }
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
    #lastmoddatetime: Optional[datetime] = None

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
    #lastmoddatetime: Optional[datetime] = None

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
    orientationdate: Optional[date] = None
    startdate: Optional[date] = None
    enddate: Optional[date] = None

class BatchCreate(BatchBase):
    pass

class Batch(BatchBase):
    batchid: int

    model_config = {

        "from_attributes": True  
    }

class PaginatedBatches(BaseModel):
    total: int
    page: int
    per_page: int
    batches: List[BatchOut]




    
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
        "from_attributes": True 
    }

class RecordingBatchBase(BaseModel):
    recording_id: int
    batch_id: int

class RecordingBatchCreate(RecordingBatchBase):
    pass

class RecordingBatch(RecordingBatchBase):
    id: int

    model_config = {
        "from_attributes": True  
    }


# -----------------------------------------------------Session------------------------------------

class SessionBase(BaseModel):
    title: str
    link: Optional[str] = None
    videoid: Optional[str] = None
    subject: Optional[str] = None
    type: Optional[str] = None
    sessiondate: Optional[datetime] = None
    # lastmoddatetime: Optional[datetime] = None
    subject_id: int
    # notes: Optional[str] = None
    # status: Optional[str] = None 


class SessionCreate(SessionBase):
    pass

class SessionUpdate(SessionBase):
    pass

class Session(SessionBase):
    sessionid: int

    model_config = {
        "from_attributes": True 
    }




class SessionOut(SessionBase):
    sessionid: int
    # lastmoddatetime: Optional[datetime]
    subject: Optional[SubjectOut]

    class Config:
        orm_mode = True


class PaginatedSession(BaseModel):
    data: list[SessionOut]
    total: int
    page: int
    per_page: int
    pages: int
   

    class Config:
        orm_mode = True



# -----------------------------Avatar Dashboard schemas----------------------------------------------------
class BatchMetrics(BaseModel):
    current_active_batches: str
    current_active_batches_count: int 
    enrolled_candidates_current: int
    total_candidates: int
    candidates_last_batch: int
    new_enrollments_month: int
    candidate_status_breakdown: Dict[str, int]


class FinancialMetrics(BaseModel):
    total_fee_current_batch: float
    fee_collected_last_batch: float
    top_batches_fee: List[Dict[str, Any]]


class PlacementMetrics(BaseModel):
    total_placements: int
    placements_year: int
    placements_last_month: int
    last_placement: Optional[Dict[str, Any]]
    active_placements: int


class InterviewMetrics(BaseModel):
    upcoming_interviews: int
    total_interviews: int
    interviews_month: int
    marketing_candidates: int
    feedback_breakdown: Dict[str, int]


class DashboardMetrics(BaseModel):
    batch_metrics: BatchMetrics
    financial_metrics: FinancialMetrics
    placement_metrics: PlacementMetrics
    interview_metrics: InterviewMetrics


class UpcomingBatch(BaseModel):
    batchname: str
    startdate: date
    enddate: date

    class Config:
        from_attributes = True

class LeadMetrics(BaseModel):
    total_leads: int
    leads_this_month: int
    latest_lead: Optional[Dict[str, Any]] = None

class LeadMetricsResponse(BaseModel):
    success: bool
    data: LeadMetrics
    message: str

class LeadsPaginatedResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    message: str


# =====================================employee========================
class EmployeeBase(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    state: Optional[str] = None
    dob: Optional[date] = None
    startdate: Optional[date] = None
    enddate: Optional[datetime] = None
    notes: Optional[str] = None
    status: Optional[int] = None
    instructor: Optional[int] = None
    aadhaar: Optional[str] = None

class EmployeeCreate(EmployeeBase):
    pass

class EmployeeUpdate(EmployeeBase):
    id: int
    name: Optional[str] = None
    email: Optional[str] = None



class Employee(EmployeeBase):
    id: int

    @field_validator("dob", "startdate", "enddate", mode="before")
    def handle_invalid_dates(cls, v):
        if isinstance(v, str) and v.startswith("0000-00-00"):
            return None
        return v

    class Config:
        from_attributes = True

class EmployeeBirthdayOut(BaseModel):
    id: int
    name: str
    dob: date
    # wish: str | None = None     
    wish: Optional[str] = None  

    class Config:
        orm_mode = True


# --------------------------------------------Password----------------------------
class ResetPasswordRequest(BaseModel):
    email: EmailStr   

class ResetPassword(BaseModel):
    token: str
    new_password: str




