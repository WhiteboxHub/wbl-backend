from sqlalchemy import Column, Integer, String, Enum, UniqueConstraint, BigInteger, DateTime, Boolean, Date, DECIMAL, Text, ForeignKey, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, validator, Field, HttpUrl, condecimal, model_validator
from typing import Optional, List, Literal, Union, Dict, Any
from enum import Enum
import enum
import re

class PositionTypeEnum(str, enum.Enum):
    full_time = 'full_time'
    contract = 'contract'
    contract_to_hire = 'contract_to_hire'
    internship = 'internship'


class EmploymentModeEnum(str, enum.Enum):
    onsite = 'onsite'
    hybrid = 'hybrid'
    remote = 'remote'


class PositionStatusEnum(str, enum.Enum):
    open = 'open'
    closed = 'closed'
    on_hold = 'on_hold'
    duplicate = 'duplicate'
    invalid = 'invalid'


class ProcessingStatusEnum(str, enum.Enum):
    new = 'new'
    parsed = 'parsed'
    mapped = 'mapped'
    discarded = 'discarded'
    error = 'error'


class ContactClassificationEnum(str, enum.Enum):
    company_contact = 'company_contact'
    personal_domain_contact = 'personal_domain_contact'
    linkedin_only_contact = 'linkedin_only_contact'
    company_only = 'company_only'
    unknown = 'unknown'


class ContactProcessingStatusEnum(str, enum.Enum):
    new = 'new'
    classified = 'classified'
    moved = 'moved'
    duplicate = 'duplicate'
    error = 'error'


# -------------------- Automation Contact Extract Schemas --------------------
class AutomationContactExtractBase(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    linkedin_id: Optional[str] = None
    linkedin_internal_id: Optional[str] = None
    source_type: str
    source_reference: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None

    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return v.lower().strip()
        return v


class AutomationContactExtractCreate(AutomationContactExtractBase):
    pass


class AutomationContactExtractUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    linkedin_id: Optional[str] = None
    linkedin_internal_id: Optional[str] = None
    source_type: str
    source_reference: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None

    @model_validator(mode='before')
    @classmethod
    def empty_string_to_none(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {
                k: (None if v == "" else v)
                for k, v in data.items()
            }
        return data


class AutomationContactExtractOut(AutomationContactExtractBase):
    id: int
    classification: ContactClassificationEnum = ContactClassificationEnum.unknown
    processing_status: ContactProcessingStatusEnum = ContactProcessingStatusEnum.new
    processed_at: Optional[datetime] = None
    target_table: Optional[str] = None
    target_id: Optional[int] = None
    error_message: Optional[str] = None
    email_lc: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AutomationContactExtractBulkCreate(BaseModel):
    extracts: List[AutomationContactExtractCreate]


class AutomationContactExtractBulkResponse(BaseModel):
    total: int
    inserted: int
    duplicates: int
    failed: int
    errors: List[Dict[str, Any]] = []


class CheckEmailsRequest(BaseModel):
    emails: List[str]


class CheckEmailsResponse(BaseModel):
    existing_emails: List[str]



class JobListingBase(BaseModel):
    title: str
    normalized_title: Optional[str] = None
    company_name: str
    company_id: Optional[int] = None
    position_type: PositionTypeEnum = PositionTypeEnum.full_time
    employment_mode: EmploymentModeEnum = EmploymentModeEnum.hybrid
    source: str
    source_uid: Optional[str] = None
    source_job_id: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_linkedin: Optional[str] = None
    job_url: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    status: PositionStatusEnum = PositionStatusEnum.open
    confidence_score: Optional[float] = None
    created_from_raw_id: Optional[int] = None

    @field_validator('contact_email')
    @classmethod
    def normalize_email(cls, v: Optional[str]) -> Optional[str]:
        """Normalize email to lowercase"""
        if v:
            return v.lower().strip()
        return v


class JobListingCreate(JobListingBase):
    pass


class JobListingUpdate(BaseModel):
    title: Optional[str] = None
    normalized_title: Optional[str] = None
    company_name: Optional[str] = None
    company_id: Optional[int] = None
    position_type: Optional[PositionTypeEnum] = None
    employment_mode: Optional[EmploymentModeEnum] = None
    source: Optional[str] = None
    source_uid: Optional[str] = None
    source_job_id: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_linkedin: Optional[str] = None
    job_url: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[PositionStatusEnum] = None
    confidence_score: Optional[float] = None
    created_from_raw_id: Optional[int] = None

    @field_validator('contact_email')
    @classmethod
    def normalize_email(cls, v: Optional[str]) -> Optional[str]:
        """Normalize email to lowercase"""
        if v:
            return v.lower().strip()
        return v


class JobListingOut(JobListingBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
class JobListingBulkCreate(BaseModel):
    positions: List[JobListingCreate]


class JobListingBulkResponse(BaseModel):
    inserted: int
    skipped: int
    total: int
    failed_contacts: List[dict] = []


class RawJobListingBase(BaseModel):
    candidate_id: Optional[int] = None
    source: str
    source_uid: Optional[str] = None
    extractor_version: Optional[str] = None
    raw_title: Optional[str] = None
    raw_company: Optional[str] = None
    raw_location: Optional[str] = None
    raw_zip: Optional[str] = None
    raw_description: Optional[str] = None
    raw_contact_info: Optional[str] = None
    raw_notes: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None
    processing_status: ProcessingStatusEnum = ProcessingStatusEnum.new
    error_message: Optional[str] = None

    @field_validator('raw_contact_info')
    @classmethod
    def normalize_contact_info(cls, v: Optional[str]) -> Optional[str]:
        """Normalize emails in contact info to lowercase"""
        if v:
            # Use regex to find and normalize email addresses
            import re
            def lowercase_email(match):
                return match.group(0).lower()
            # Pattern to match email addresses
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            return re.sub(email_pattern, lowercase_email, v)
        return v


class RawJobListingCreate(RawJobListingBase):
    pass


class RawJobListingUpdate(BaseModel):
    source: Optional[str] = None
    source_uid: Optional[str] = None
    extractor_version: Optional[str] = None
    raw_title: Optional[str] = None
    raw_company: Optional[str] = None
    raw_location: Optional[str] = None
    raw_zip: Optional[str] = None
    raw_description: Optional[str] = None
    raw_contact_info: Optional[str] = None
    raw_notes: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None
    processing_status: Optional[ProcessingStatusEnum] = None
    error_message: Optional[str] = None
    processed_at: Optional[datetime] = None

    @field_validator('raw_contact_info')
    @classmethod
    def normalize_contact_info(cls, v: Optional[str]) -> Optional[str]:
        """Normalize emails in contact info to lowercase"""
        if v:
            import re
            def lowercase_email(match):
                return match.group(0).lower()
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            return re.sub(email_pattern, lowercase_email, v)
        return v


class RawJobListingBulkCreate(BaseModel):
    positions: List[RawJobListingCreate]


class RawJobListingBulkResponse(BaseModel):
    inserted: int
    skipped: int
    total: int
    failed_contacts: List[dict] = []


class RawJobListingOut(RawJobListingBase):
    id: int
    extracted_at: datetime
    processed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True



# Visa Status Enum
class VisaStatusEnum(str, enum.Enum):
    US_CITIZEN = "US_CITIZEN"
    GREEN_CARD = "GREEN_CARD"
    GC_EAD = "GC_EAD"
    I485_EAD = "I485_EAD"
    I140_APPROVED = "I140_APPROVED"
    F1 = "F1"
    F1_OPT = "F1_OPT"
    F1_CPT = "F1_CPT"
    J1 = "J1"
    J1_AT = "J1_AT"
    H1B = "H1B"
    H1B_TRANSFER = "H1B_TRANSFER"
    H1B_CAP_EXEMPT = "H1B_CAP_EXEMPT"
    H4 = "H4"
    H4_EAD = "H4_EAD"
    L1A = "L1A"
    L1B = "L1B"
    L2 = "L2"
    L2_EAD = "L2_EAD"
    O1 = "O1"
    TN = "TN"
    E3 = "E3"
    E3_EAD = "E3_EAD"
    E2 = "E2"
    E2_EAD = "E2_EAD"
    TPS_EAD = "TPS_EAD"
    ASYLUM_EAD = "ASYLUM_EAD"
    REFUGEE_EAD = "REFUGEE_EAD"
    DACA_EAD = "DACA_EAD"

class EmployeeBase(BaseModel):
    id: Optional[int] = None
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
    def handle_invalid_dates(cls, v):
        if v in ("", "0000-00-00", None):
            return None
        return v


class EmployeeCreate(EmployeeBase):
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class EmployeeUpdate(EmployeeBase):
    # id: int
    pass

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
    wish: Optional[str] = None

    class Config:
        from_attributes = True

# ---------------------------enployee search -----------------------------
class EmployeeDetailSchema(BaseModel):
    id: Optional[int] = None
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

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    team: Optional[str] = None
    login_count: Optional[int] = None


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
    visa_status: Optional[VisaStatusEnum] = None
    experience: Optional[str] = None
    education: Optional[str] = None
    referby: Optional[str] = None
    specialization: Optional[str] = None
    notes: Optional[str] = None
    recaptcha_token: str = Field(..., description="reCAPTCHA v2 token from frontend")


class UserCreate(BaseModel):
    uname: str
    passwd: str


class ContactForm(BaseModel):
    firstName: str
    lastName: str
    email: str
    phone: str
    message: str


class EmailRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    token: str
    new_password: str


class AuthUserBase(BaseModel):
    uname: Union[EmailStr, str] = None
    passwd: Optional[str] = None
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
    visa_status: Optional[VisaStatusEnum] = None
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
    logincount: Optional[int] = None
    registereddate: Optional[datetime] = None
    enddate: Optional[date] = None

    @validator(
        "registereddate",
        "enddate",
        pre=True,
    )
    def fix_invalid_datetime(cls, v):
        if v in ("0000-00-00 00:00:00", "0000-00-00", None, ""):
            return None
        return v

    class Config:
        from_attributes = True


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
    workstatus: Optional[VisaStatusEnum] = None
    status: Optional[str] = "open"
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


class LeadUpdate(LeadBase):
    pass


class LeadSchema(LeadBase):
    id: int

    class Config:
        from_attributes = True


class PotentialLeadBase(BaseModel):
    full_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    profession: Optional[str] = None
    linkedin_id: Optional[str] = None
    internal_linkedin_id: Optional[str] = None
    entry_date: Optional[datetime] = None
    work_status: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None


class PotentialLeadCreate(PotentialLeadBase):
    pass

class PotentialLeadUpdate(PotentialLeadBase):
    pass


class PotentialLeadSchema(PotentialLeadBase):
    id: int
    lastmoddatetime: datetime

    class Config:
        from_attributes = True
# --------------------------------------------------------candidate-------------------------------------------------------


class BatchBase(BaseModel):
    batchname: str
    courseid: int
    orientationdate: Optional[date] = None
    startdate: Optional[date] = None
    enddate: Optional[date] = None


class BatchCreate(BatchBase):
    pass


class BatchUpdate(BatchBase):
    pass


class BatchOut(BaseModel):
    batchid: int
    batchname: str
    orientationdate: Optional[date] = None
    startdate: Optional[date] = None
    enddate: Optional[date] = None
    subject: Optional[str] = None
    courseid: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedBatches(BaseModel):
    total: int
    page: int
    per_page: int
    batches: List[BatchOut]


class CandidateBase(BaseModel):

    id: Optional[int] = None
    full_name: Optional[str] = None
    name: Optional[str] = Field(None)
    enrolled_date: Optional[date] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[Literal['active', 'inactive',
                             'discontinued', 'break', 'closed']] = None
    workstatus: Optional[VisaStatusEnum] = None
    education: Optional[str] = None
    workexperience: Optional[str] = None
    ssn: Optional[str] = None
    agreement: Optional[str] = None
    secondaryemail: Optional[str] = None
    secondaryphone: Optional[str] = None
    address: Optional[str] = None
    zip_code: Optional[str] = None
    linkedin_id: Optional[str] = None
    github_link: Optional[str] = None
    dob: Optional[date] = None
    emergcontactname: Optional[str] = None
    emergcontactemail: Optional[str] = None
    emergcontactphone: Optional[str] = None
    emergcontactaddrs: Optional[str] = None
    fee_paid: Optional[int] = None
    notes: Optional[str] = None
    batchid: int = None
    batch: Optional[BatchOut] = None
    candidate_folder: Optional[str] = None
    move_to_prep: Optional[bool] = False
    is_in_prep: Optional[str] = "No"
    is_in_marketing: Optional[str] = "No"

    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }

    @field_validator("agreement", mode="before")
    def normalize_agreement(cls, v):
        if v is True:
            return "Y"
        if v is False:
            return "N"
        return v


class CandidateCreate(CandidateBase):
    pass


class StatusEnum(str, Enum):
    active = 'active'
    inactive = 'inactive'
    discontinued = 'discontinued'
    break_ = 'break'
    closed = 'closed'


class CandidateUpdate(BaseModel):
    id: Optional[int] = None
    full_name: Optional[str] = None
    name: Optional[str] = None
    enrolled_date: Optional[date] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[Literal['active', 'inactive',
                             'discontinued', 'break', 'closed']] = None
    workstatus: Optional[VisaStatusEnum] = None
    education: Optional[str] = None
    workexperience: Optional[str] = None
    ssn: Optional[str] = None
    agreement: Optional[str] = None
    secondaryemail: Optional[str] = None
    secondaryphone: Optional[str] = None
    address: Optional[str] = None
    zip_code: Optional[str] = None
    linkedin_id: Optional[str] = None
    dob: Optional[date] = None
    emergcontactname: Optional[str] = None
    emergcontactemail: Optional[str] = None
    emergcontactphone: Optional[str] = None
    emergcontactaddrs: Optional[str] = None
    fee_paid: Optional[int] = None
    notes: Optional[str] = None
    batchid: Optional[int] = None
    candidate_folder: Optional[str] = None
    move_to_prep: Optional[bool] = False

    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }

    @field_validator("agreement", mode="before")
    def normalize_agreement(cls, v):
        if v is True:
            return "Y"
        if v is False:
            return "N"
        return v


class CandidateDelete(CandidateBase):
    id: int

    class Config:
        from_attributes = True


class PaginatedCandidateResponse(BaseModel):
    page: int
    limit: int
    total: int
    data: List[CandidateBase]

    class Config:
        from_attributes = True

# -------------------------MARKETING-----------------------


class CandidateMarketingBase(BaseModel):
    candidate_id: int
    marketing_manager: Optional[int] = None
    start_date: date
    notes: Optional[str] = None
    status: Literal["active", "inactive"] = "active"
    email: Optional[str] = None
    password: Optional[str] = None
    imap_password: Optional[str] = None
    priority: Optional[int] = None
    google_voice_number: Optional[str] = None
    linkedin_username: Optional[str] = None
    linkedin_passwd: Optional[str] = None
    linkedin_premium_end_date: Optional[date] = None
    resume_url: Optional[HttpUrl] = None
    move_to_placement: Optional[bool] = False
    mass_email: Optional[bool] = False
    candidate_intro: Optional[str] = None
    run_daily_workflow: bool = False
    run_weekly_workflow: bool = False
    candidate: Optional["CandidateBase"] = None
    marketing_manager_obj: Optional["EmployeeBase"] = None


class CandidateMarketingCreate(CandidateMarketingBase):
    pass


class CandidateMarketing(CandidateMarketingBase):
    id: int
    last_mod_datetime: Optional[datetime]

    class Config:
        from_attributes = True


class CandidateMarketingUpdate(BaseModel):
    candidate_id: Optional[int] = None
    marketing_manager: Optional[int] = None
    start_date: Optional[date] = None
    notes: Optional[str] = None
    status: Optional[Literal["active", "inactive"]] = None
    email: Optional[str] = None
    password: Optional[str] = None
    imap_password: Optional[str] = None
    priority: Optional[int] = None
    google_voice_number: Optional[str] = None
    linkedin_username: Optional[str] = None
    linkedin_passwd: Optional[str] = None
    linkedin_premium_end_date: Optional[date] = None
    resume_url: Optional[HttpUrl] = None
    move_to_placement: Optional[bool] = None
    mass_email: Optional[bool] = None
    candidate_intro: Optional[str] = None
    run_daily_workflow: Optional[bool] = None
    run_weekly_workflow: Optional[bool] = None

# -----------------------PLACEMENT---------------------------------

class InstallmentEnum(str, enum.Enum):
    one = "1"
    two = "2"
    three = "3"
    four = "4"
    five = "5"



class CandidatePlacementBase(BaseModel):
    candidate_id: int
    position: Optional[str] = None
    company: str
    placement_date: date
    joining_date: Optional[date] = None
    type: Optional[Literal['Company', 'Client',
                           'Vendor', 'Implementation Partner']] = None
    status: Literal['Active', 'Inactive']
    # priority: Optional[int] =
    base_salary_offered: Optional[float] = None
    benefits: Optional[str] = None
    fee_paid: Optional[float] = None
    no_of_installments: Optional[InstallmentEnum] = None
    last_mod_datetime: Optional[datetime] = None
    notes: Optional[str] = None


class CandidatePlacementCreate(CandidatePlacementBase):
    pass


class CandidatePlacement(CandidatePlacementBase):
    id: int
    last_mod_datetime: Optional[datetime]

    class Config:
        from_attributes = True


class CandidatePlacementUpdate(BaseModel):
    position: Optional[str] = None
    company: Optional[str] = None
    placement_date: Optional[date] = None
    joining_date: Optional[date] = None
    type: Optional[Literal['Company', 'Client',
                           'Vendor', 'Implementation Partner']] = None
    status: Optional[Literal['Active', 'Inactive']]
    base_salary_offered: Optional[float] = None
    benefits: Optional[str] = None
    fee_paid: Optional[float] = None
    no_of_installments: Optional[InstallmentEnum] = None
    notes: Optional[str] = None


# ----------------------------------------------------

class InstructorOut(BaseModel):
    id: int
    full_name: str

    class Config:
        from_attributes = True


# ------------------hkd-------------------------
class CandidatePreparationBase(BaseModel):
    id: int
    candidate_id: int
    start_date: Optional[date] = None
    status: str
    instructor1_id: Optional[int] = None
    instructor2_id: Optional[int] = None
    instructor3_id: Optional[int] = None
    rating: Optional[str] = None
    communication: Optional[str] = None
    years_of_experience: Optional[int] = None
    target_date: Optional[date] = None
    notes: Optional[str] = None
    move_to_mrkt: Optional[bool] = False
    # linkedin_id: Optional[str] = None
    github_url: Optional[str] = None
    resume_url: Optional[str] = None

    candidate: Optional["CandidateBase"]
    instructor1: Optional["EmployeeBase"]
    instructor2: Optional["EmployeeBase"]
    instructor3: Optional["EmployeeBase"]

    class Config:
        from_attributes = True


class CandidatePreparationCreate(BaseModel):
    candidate_id: int
    start_date: Optional[date] = None
    status: str = "active"
    instructor1_id: Optional[int] = None
    instructor2_id: Optional[int] = None
    instructor3_id: Optional[int] = None
    rating: Optional[str] = None
    communication: Optional[str] = None
    years_of_experience: Optional[int] = None
    target_date: Optional[date] = None
    notes: Optional[str] = None
    move_to_mrkt: Optional[bool] = False
    # linkedin_id: Optional[str] = None
    github_url: Optional[str] = None
    resume_url: Optional[str] = None


class CandidatePreparationUpdate(BaseModel):
    start_date: Optional[date] = None
    status: Optional[str] = None
    instructor1_id: Optional[int] = None
    instructor2_id: Optional[int] = None
    instructor3_id: Optional[int] = None
    rating: Optional[str] = None
    communication: Optional[str] = None
    years_of_experience: Optional[int] = None
    target_date: Optional[date] = None
    notes: Optional[str] = None
    move_to_mrkt: Optional[bool] = None
    # linkedin_id: Optional[str] = None
    github_url: Optional[str] = None
    resume_url: Optional[str] = None


class CandidatePreparationOut(BaseModel):
    id: int
    start_date: Optional[date] = None
    status: str
    rating: Optional[str] = None
    communication: Optional[str] = None
    years_of_experience: Optional[int] = None
    target_date: Optional[date] = None
    notes: Optional[str] = None
    last_mod_datetime: Optional[datetime] = None
    move_to_mrkt: Optional[bool] = None
    # linkedin_id: Optional[str] = None
    github_url: Optional[str] = None
    resume_url: Optional[str] = None
    is_in_marketing: Optional[str] = "No"

    candidate: Optional["CandidateBase"]
    instructor1: Optional["EmployeeBase"]
    instructor2: Optional["EmployeeBase"]
    instructor3: Optional["EmployeeBase"]

    class Config:
        from_attributes = True
        populate_by_name = True

# ---------Interview-------------------------------

class ModeOfInterviewEnum(str, Enum):
    virtual = "Virtual"
    in_person = "In Person"
    phone = "Phone"
    assessment = "Assessment"
    ai_interview = "AI Interview"


class TypeOfInterviewEnum(str, Enum):
    recruiter_call = "Recruiter Call"
    technical = "Technical"
    hr = "HR"
    prep_call = "Prep Call"


class FeedbackEnum(str, Enum):
    pending = "Pending"
    positive = "Positive"
    negative = "Negative"

class CompanyTypeEnum(str, Enum):
    client = "client"
    third_party_vendor = "third-party-vendor"
    implementation_partner = "implementation-partner"
    sourcer = "sourcer"


# --- Base Schema ---
class CandidateInterviewBase(BaseModel):
    candidate_id: int
    company: str
    company_type: Optional[CompanyTypeEnum] = CompanyTypeEnum.client
    interviewer_emails: Optional[str] = None
    interviewer_contact: Optional[str] = None
    interviewer_linkedin: Optional[str] = None
    interview_date: date
    mode_of_interview: Optional[ModeOfInterviewEnum] = ModeOfInterviewEnum.virtual
    type_of_interview: Optional[TypeOfInterviewEnum] = TypeOfInterviewEnum.recruiter_call
    transcript: Optional[str] = None
    recording_link: Optional[str] = None
    backup_recording_url: Optional[str] = None
    job_posting_url: Optional[str] = None
    feedback: Optional[FeedbackEnum] = FeedbackEnum.pending
    notes: Optional[str] = None
    position_id: Optional[int] = None
    candidate: Optional["CandidateBase"] = None


# --- Create Schema ---
class CandidateInterviewCreate(BaseModel):
    candidate_id: int
    company: str
    company_type: Optional[CompanyTypeEnum] = CompanyTypeEnum.client
    interview_date: date
    mode_of_interview: Optional[ModeOfInterviewEnum] = ModeOfInterviewEnum.virtual
    type_of_interview: Optional[TypeOfInterviewEnum] = TypeOfInterviewEnum.recruiter_call
    interviewer_emails: Optional[str] = None
    interviewer_contact: Optional[str] = None
    interviewer_linkedin: Optional[str] = None
    recording_link: Optional[str] = None
    backup_recording_url: Optional[str] = None
    job_posting_url: Optional[str] = None
    feedback: Optional[FeedbackEnum] = FeedbackEnum.pending
    notes: Optional[str] = None
    position_id: Optional[int] = None
    position_title: Optional[str] = None
    position_location: Optional[str] = None


model_config = {
    "from_attributes": True,
    "validate_by_name": True
}


# --- Update Schema ---
class CandidateInterviewUpdate(BaseModel):
    candidate_id: Optional[int] = None
    company: Optional[str] = None
    company_type: Optional[CompanyTypeEnum] = None
    interviewer_emails: Optional[str] = None
    interviewer_contact: Optional[str] = None
    interviewer_linkedin: Optional[str] = None
    interview_date: Optional[date] = None
    mode_of_interview: Optional[ModeOfInterviewEnum] = None
    type_of_interview: Optional[TypeOfInterviewEnum] = None
    transcript: Optional[str] = None
    recording_link: Optional[str] = None
    backup_recording_url: Optional[str] = None
    job_posting_url: Optional[str] = None
    feedback: Optional[FeedbackEnum] = None
    notes: Optional[str] = None
    position_id: Optional[int] = None


# --- Output Schema ---
class CandidateInterviewOut(CandidateInterviewBase):
    id: int
    company_type: Optional[CompanyTypeEnum] = None
    instructor1_name: Optional[str] = None
    instructor2_name: Optional[str] = None
    instructor3_name: Optional[str] = None
    position_title: Optional[str] = None
    position_company: Optional[str] = None
    # source_job_id: Optional[str] = None
    last_mod_datetime: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Paginated Output ---
class PaginatedInterviews(BaseModel):
    items: List[CandidateInterviewOut]
    total: int
    page: int
    per_page: int


class ActiveMarketingCandidate(BaseModel):
    candidate_id: int
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    start_date: date
    status: str

    class Config:
        from_attributes = True

# -----------------------------Placement_Fee_Collection---------------------------------

class AmountCollectedEnum(str, enum.Enum):
    yes = "yes"
    no = "no"

Decimal2 = condecimal(max_digits=10, decimal_places=2)

class PlacementFeeBase(BaseModel):
    placement_id: int
    installment_id: Optional[int] = None
    deposit_date: Optional[date] = None
    deposit_amount: Optional[Decimal2] = None
    amount_collected: AmountCollectedEnum = AmountCollectedEnum.no
    lastmod_user_id: Optional[int] = None

class PlacementFeeCreate(PlacementFeeBase):
    pass

class PlacementFeeUpdate(BaseModel):
    placement_id: Optional[int] = None
    installment_id: Optional[int] = None
    deposit_date: Optional[date] = None
    deposit_amount: Optional[Decimal2] = None
    amount_collected: Optional[AmountCollectedEnum] = None
    lastmod_user_id: Optional[int] = None

class PlacementFeeOut(PlacementFeeBase):
    id: int
    candidate_name: Optional[str] = None
    company_name: Optional[str] = None
    lastmod_user_name: Optional[str] = None
    last_mod_date: Optional[datetime] = None

    class Config:
        from_attributes = True

# -----------------------------------------------------------------------------------

# ----------------------------- Placement Commission Schemas --------------------------------

class CommissionPaymentStatusEnum(str, enum.Enum):
    pending = "Pending"
    paid = "Paid"


class PlacementCommissionBase(BaseModel):
    placement_id: int
    employee_id: int
    amount: Decimal2

    model_config = {"from_attributes": True}


class PlacementCommissionCreate(PlacementCommissionBase):
    pass


class PlacementCommissionUpdate(BaseModel):
    amount: Optional[Decimal2] = None
    employee_id: Optional[int] = None

    model_config = {"from_attributes": True}


class PlacementCommissionSchedulerOut(BaseModel):
    id: int
    placement_commission_id: int
    installment_no: int
    installment_amount: Decimal2
    scheduled_date: date
    payment_status: Optional[CommissionPaymentStatusEnum] = CommissionPaymentStatusEnum.pending
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PlacementCommissionOut(PlacementCommissionBase):
    id: int
    lastmod_user_id: Optional[int] = None
    created_at: Optional[datetime] = None
    lastmod_datetime: Optional[datetime] = None
    employee_name: Optional[str] = None
    candidate_name: Optional[str] = None
    company_name: Optional[str] = None
    scheduler_entries: List[PlacementCommissionSchedulerOut] = []

    model_config = {"from_attributes": True}


# ---- Scheduler ----

class PlacementCommissionSchedulerBase(BaseModel):
    placement_commission_id: int
    installment_no: int
    installment_amount: Decimal2
    scheduled_date: date
    payment_status: Optional[CommissionPaymentStatusEnum] = CommissionPaymentStatusEnum.pending

    model_config = {"from_attributes": True}


class PlacementCommissionSchedulerCreate(PlacementCommissionSchedulerBase):
    pass


class PlacementCommissionSchedulerUpdate(BaseModel):
    installment_amount: Optional[Decimal2] = None
    scheduled_date: Optional[date] = None
    payment_status: Optional[CommissionPaymentStatusEnum] = None

    model_config = {"from_attributes": True}

# -----------------------------------------------------------------------------------


class GoogleUserCreate(BaseModel):
    name: str
    email: str
    google_id: str

    model_config = {
        "from_attributes": True
    }


# ----------------------------vendor - tables -----------------
# -------------------- Enums --------------------
class VendorTypeEnum(str, Enum):
    client = "client"
    third_party_vendor = "third-party-vendor"
    implementation_partner = "implementation-partner"
    sourcer = "sourcer"
    contact_from_ip = "contact-from-ip"


# -------------------- VendorContactExtract Schemas --------------------
class VendorContactExtract(BaseModel):
    id: int
    full_name: Optional[str] = None
    source_email: Optional[EmailStr] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_id: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    extraction_date: Optional[date] = None
    moved_to_vendor: Optional[bool] = None
    moved_at: Optional[datetime] = None
    vendor_id: Optional[int] = None
    created_at: Optional[datetime] = None
    linkedin_internal_id: Optional[str] = None
    notes: Optional[str] = None
    last_modified_datetime: Optional[datetime] = None
    job_source: Optional[str] = None
    model_config = {
        "from_attributes": True
    }


# -------------------- Projects Schemas --------------------

class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    owner: str
    start_date: date
    target_end_date: Optional[date] = None
    end_date: Optional[date] = None
    priority: Optional[Literal['Low', 'Medium', 'High', 'Critical']] = 'Medium'
    status: Optional[Literal['Planned', 'In Progress', 'Completed', 'On Hold', 'Cancelled']] = 'Planned'

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    start_date: Optional[date] = None
    target_end_date: Optional[date] = None
    end_date: Optional[date] = None
    priority: Optional[Literal['Low', 'Medium', 'High', 'Critical']] = None
    status: Optional[Literal['Planned', 'In Progress', 'Completed', 'On Hold', 'Cancelled']] = None

class ProjectOut(ProjectBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# -------------------- Employee Task Schemas (Updated) --------------------

class EmployeeTaskBase(BaseModel):
    employee_id: int
    project_id: Optional[int] = None
    task: str
    assigned_date: date
    due_date: Optional[date] = None
    status: Optional[str] = "pending"
    priority: Optional[str] = "medium"
    notes: Optional[str] = None
    employee_name: Optional[str] = None # Helper for UI

class EmployeeTaskCreate(EmployeeTaskBase):
    employee_name: Optional[str] = None
    project_name: Optional[str] = None

class EmployeeTaskUpdate(BaseModel):
    employee_id: Optional[int] = None
    project_id: Optional[int] = None
    task: Optional[str] = None
    assigned_date: Optional[date] = None
    due_date: Optional[date] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    notes: Optional[str] = None
    employee_name: Optional[str] = None
    project_name: Optional[str] = None

class EmployeeTask(EmployeeTaskBase):
    id: int
    project_name: Optional[str] = None
    
    class Config:
        from_attributes = True



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
    extraction_date: Optional[date] = None
    location: Optional[str] = None
    linkedin_internal_id: Optional[str] = None
    notes: Optional[str] = None
    job_source: Optional[str] = None
    vendor_id: Optional[int] = None
    last_modified_datetime: Optional[datetime] = None

    @validator("email", "linkedin_id", "linkedin_internal_id", pre=True)
    def empty_to_none(cls, v):
        if v == "" or (isinstance(v, str) and v.lower() == "none"):
            return None
        return v


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
    moved_at: Optional[datetime] = None
    vendor_id: Optional[int] = None
    linkedin_internal_id: Optional[str] = None
    notes: Optional[str] = None
    job_source: Optional[str] = None




class VendorContactBulkCreate(BaseModel):
    contacts: List[VendorContactExtractCreate]


class VendorContactBulkResponse(BaseModel):
    inserted: int
    failed: int
    duplicates: int
    total: int
    failed_contacts: List[dict] = []
    duplicate_contacts: List[dict] = []


class MoveToVendorRequest(BaseModel):
    contact_ids: List[int] = Field(..., description="List of contact IDs to move to vendor")


# -------------------- Vendor Schemas --------------------
class VendorBase(BaseModel):
    full_name: Optional[str] = None
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
    intro_call: Optional[str] = "NO"
    linkedin_internal_id: Optional[str] = None
    last_modified_datetime: Optional[datetime] = None

    @validator("email", pre=True)
    def empty_string_to_none(cls, v):
        return v or None

    @validator("type", "vendor_type", pre=True)
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
    status: Optional[Literal['active', 'working', 'not_useful',
                             'do_not_contact', 'inactive', 'prospect']] = None
    linkedin_connected: Optional[Literal['YES', 'NO']] = None
    intro_email_sent: Optional[Literal['YES', 'NO']] = None
    intro_call: Optional[Literal['YES', 'NO']] = None
    linkedin_internal_id: Optional[str] = None


class VendorMetrics(BaseModel):
    total_vendors: int
    today_extracted: int
    week_extracted: int

    class Config:
        from_attributes = True

# ---------------daily-vendor-activity --------------

class YesNoEnum(str, Enum):
    YES = "YES"
    NO = "NO"


class DailyVendorActivity(BaseModel):
    activity_id: int
    vendor_id: int
    application_date: Optional[date]
    source_email: Optional[str] = None
    extraction_date: Optional[datetime] = None
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
    linkedin_internal_id: Optional[str] = None

class VendorResponse(BaseModel):
    message: str


# -------------------- HR Contact Schemas --------------------
class HRContactBase(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    job_title: Optional[str] = None
    is_immigration_team: Optional[bool] = False

    @validator("email", pre=True)
    def empty_string_to_none(cls, v):
        return v or None

    @field_validator("full_name", "company_name", "location", "job_title", mode="before")
    @classmethod
    def init_cap_fields(cls, v):
        if v is None or not isinstance(v, str):
            return v
        # Converts to Init Cap (Title Case)
        return " ".join(word.capitalize() for word in v.strip().split())


class HRContactCreate(HRContactBase):
    full_name: str
    email: EmailStr


class HRContactUpdate(HRContactBase):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    job_title: Optional[str] = None
    is_immigration_team: Optional[bool] = None


class HRContact(HRContactBase):
    id: int
    extraction_date: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }


# ---------------linkedin_activity_log---------------------

class ActivityType(str, Enum):
    extraction = "extraction"
    connection = "connection"


class Status(str, Enum):
    success = "success"
    failed = "failed"


class LinkedInActivityLogBase(BaseModel):
    candidate_id: int
    source_email: Optional[str] = None
    activity_type: ActivityType
    linkedin_profile_url: Optional[str] = None
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    status: Status = Status.success
    message: Optional[str] = None


class LinkedInActivityLogCreate(LinkedInActivityLogBase):
    pass


class LinkedInActivityLogUpdate(BaseModel):
    source_email: Optional[str] = None
    activity_type: Optional[ActivityType] = None
    linkedin_profile_url: Optional[str] = None
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    status: Optional[Status] = None
    message: Optional[str] = None


class LinkedInActivityLogOut(LinkedInActivityLogBase):
    id: int
    created_at: datetime
    candidate_name: Optional[str] = None

    class Config:
        from_attributes = True


class PaginatedLinkedInActivityLogs(BaseModel):
    total: int
    page: int
    per_page: int
    logs: List[LinkedInActivityLogOut]


# ================================================contact====================================

class ContactForm(BaseModel):
    firstName: str
    lastName: str
    email: EmailStr
    phone: str
    message: str
    recaptcha_token: str = Field(..., description="reCAPTCHA v2 token from frontend")


# -----------------------------------------------------unsubscribe-------------------------
class UnsubscribeRequest(BaseModel):
    email: EmailStr
    # for both unsubscribe_user and unsubscribe_leads


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
        from_attributes = True


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

# -----------------------------------------------------Recordings------------------------------------


class RecordingBase(BaseModel):
    description: str
    type: str = "class"
    classdate: date
    link: str
    videoid: Optional[str] = None
    backup_url: Optional[str] = None
    subject: Optional[str] = None
    filename: Optional[str] = None
    lastmoddatetime: Optional[datetime] = None
    new_subject_id: Optional[int] = None


class RecordingCreate(RecordingBase):
    pass


class RecordingUpdate(RecordingBase):
    pass


class RecordingOut(RecordingBase):
    id: int

    @field_validator("lastmoddatetime", mode="before")
    def clean_invalid_datetime(cls, v):
        if v in ("0000-00-00 00:00:00", None, ""):
            return None
        return v

    class Config:
        from_attributes = True


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
    # lastmoddatetime: Optional[datetime] = None

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
    # lastmoddatetime: Optional[datetime] = None

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
    course_name: str
    subject_name: str
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

# coursecontent


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
# coursematerial


class CourseMaterialBase(BaseModel):
    subjectid: int
    courseid: int
    name: str
    description: Optional[str] = None
    type: str = 'P'
    link: str
    sortorder: int = Field(default=9999)


class CourseMaterialCreate(CourseMaterialBase):
    subjectid: int
    courseid: int
    name: str
    description: Optional[str] = None
    type: str
    link: str
    sortorder: int


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
    cm_subject: str
    cm_course: str
    material_type: str

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
    description: str
    type: str = "class"
    classdate: date
    link: str
    videoid: Optional[str] = None
    backup_url: Optional[str] = None
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
    model_config = {
        "from_attributes": True
    }


# -----------------------------------------------------Session------------------------------------

class SessionBase(BaseModel):
    title: Optional[str] = None
    status: str
    link: Optional[str] = None
    backup_url: Optional[str] = None
    videoid: Optional[str] = None
    subject: Optional[str] = None
    type: Optional[str] = None
    sessiondate: Optional[date] = None
    lastmoddatetime: Optional[datetime] = None
    subject_id: int
    notes: Optional[str] = None


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

    @field_validator("sessiondate", mode="before")
    def clean_invalid_date(cls, v):
        if v in ("0000-00-00", None, ""):
            return None
        return v


    class Config:
        from_attributes = True


class PaginatedSession(BaseModel):
    data: list[SessionOut]
    total: int
    page: int
    per_page: int
    pages: int

    class Config:
        from_attributes = True


# -----------------------------Avatar Dashboard schemas----------------------------------------------------
class BatchMetrics(BaseModel):
    current_active_batches: str
    current_active_batches_count: int
    enrolled_candidates_current: int
    total_candidates: int
    candidates_previous_batch: int
    new_enrollments_month: int
    candidate_status_breakdown: Dict[str, int]


class PlacementFeeMetrics(BaseModel):
    total_expected: float
    total_collected: float
    total_pending: float
    collected_this_month: float
    installment_stats: Optional[Dict[str, int]] = None


class FinancialMetrics(BaseModel):
    total_fee_current_batch: float
    fee_collected_previous_batch: float
    top_batches_fee: List[Dict[str, Any]]
    placement_fee_metrics: PlacementFeeMetrics


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
    interviews_today: int
    marketing_candidates: int
    priority_1_candidates: int
    priority_2_candidates: int
    priority_3_candidates: int
    feedback_breakdown: Dict[str, int]


class EmployeeTaskMetrics(BaseModel):
    total_tasks: int
    pending_tasks: int
    in_progress_tasks: int
    completed_tasks: int
    overdue_tasks: int

class JobsMetrics(BaseModel):
    total_job_types: int
    total_activities: int
    activities_today: int
    activities_this_week: int
    recent_activities: List[Dict[str, Any]]

class DashboardMetrics(BaseModel):
    batch_metrics: BatchMetrics
    financial_metrics: FinancialMetrics
    placement_metrics: PlacementMetrics
    interview_metrics: InterviewMetrics
    employee_task_metrics: EmployeeTaskMetrics
    jobs_metrics: JobsMetrics
    my_tasks: Optional[List["EmployeeTask"]] = None
    my_jobs: Optional[List["JobTypeOut"]] = None
    employee_name: Optional[str] = None


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
    leads_this_week: int
    open_leads: int
    closed_leads: int
    future_leads: int


class LeadMetricsResponse(BaseModel):
    success: bool
    data: LeadMetrics
    message: str


class LeadsPaginatedResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    message: str


class CandidateInterviewPerformance(BaseModel):
    candidate_id: int
    candidate_name: str
    total_interviews: int
    success_count: int


class CandidateInterviewPerformanceResponse(BaseModel):
    success: bool
    data: List[CandidateInterviewPerformance]
    message: str


class CandidatePreparationMetrics(BaseModel):
    total_preparation_candidates: int
    active_candidates: int
    inactive_candidates: int


class BatchClassSummary(BaseModel):
    batchname: str
    classes_count: int




    class Config:
        from_attributes = True


# =====================================employee========================



# Duplicate EmployeeTask schemas removed.


# --------------------------------------------Password----------------------------
class ResetPasswordRequest(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    token: str
    new_password: str


class InternalDocumentBase(BaseModel):
    title: str
    description: Optional[str] = None
    file: Optional[str] = None


class InternalDocumentCreate(InternalDocumentBase):
    pass


class InternalDocumentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    file: Optional[str] = None


class InternalDocumentOut(InternalDocumentBase):
    id: int

    model_config = {
        "from_attributes": True
    }


# -------------------- Job Types Schemas --------------------
class JobTypeBase(BaseModel):
    unique_id: str
    name: str
    job_owner_1: Optional[int] = None
    job_owner_2: Optional[int] = None
    job_owner_3: Optional[int] = None
    category: Optional[Literal["manual", "automation"]] = "manual"
    description: Optional[str] = None
    notes: Optional[str] = None


class JobTypeCreate(BaseModel):
    unique_id: str
    name: str
    job_owner_1: Optional[int] = None
    job_owner_2: Optional[int] = None
    job_owner_3: Optional[int] = None
    category: Optional[Literal["manual", "automation"]] = "manual"
    description: Optional[str] = None
    notes: Optional[str] = None


class JobTypeUpdate(BaseModel):
    unique_id: Optional[str] = None
    name: Optional[str] = None
    job_owner_1: Optional[int] = None
    job_owner_2: Optional[int] = None
    job_owner_3: Optional[int] = None
    category: Optional[Literal["manual", "automation"]] = None
    description: Optional[str] = None
    notes: Optional[str] = None


class JobTypeOut(JobTypeBase):
    id: int
    job_owner_1_name: Optional[str] = None
    job_owner_2_name: Optional[str] = None
    job_owner_3_name: Optional[str] = None
    lastmod_date_time: Optional[str] = None
    lastmod_user_name: Optional[str] = None

    @field_validator("lastmod_date_time", mode="before")
    def format_timestamp(cls, v):
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(v, date):
            return v.strftime("%Y-%m-%d")
        return str(v).split()[0] if v else None

    class Config:
        from_attributes = True


# -------------------- Job Activity Log Schemas --------------------
class JobActivityLogBase(BaseModel):
    job_id: int
    candidate_id: Optional[int] = None
    employee_id: Optional[int] = None
    activity_date: date
    activity_count: Optional[int] = Field(default=0, ge=0)
    notes: Optional[str] = None


class JobActivityLogCreate(JobActivityLogBase):
    pass


class JobActivityLogUpdate(BaseModel):
    job_id: Optional[int] = None
    candidate_id: Optional[int] = None
    employee_id: Optional[int] = None
    activity_date: Optional[date] = None
    activity_count: Optional[int] = None
    notes: Optional[str] = None


class JobActivityLogBulkCreate(BaseModel):
    logs: List[JobActivityLogCreate]


class JobActivityLogBulkResponse(BaseModel):
    inserted: int
    failed: int
    total: int
    failed_logs: List[dict] = []


class JobActivityLogOut(JobActivityLogBase):
    id: int
    last_mod_date: Optional[datetime] = None
    lastmod_user_name: Optional[str] = None
    job_name: Optional[str] = None
    candidate_name: Optional[str] = None
    employee_name: Optional[str] = None

    class Config:
        from_attributes = True


class PaginatedJobActivityLogs(BaseModel):
    total: int
    page: int
    per_page: int
    logs: List[JobActivityLogOut]


# ==================== Job Automation Keywords ====================

class MatchTypeEnum(str, Enum):
    exact = "exact"
    contains = "contains"
    regex = "regex"


class ActionEnum(str, Enum):
    allow = "allow"
    block = "block"


class JobAutomationKeywordBase(BaseModel):
    category: str = Field(..., max_length=50, description="Category like blocked_personal_domain, allowed_staffing_domain")
    source: str = Field(default="email_extractor", max_length=50, description="Which extractor uses this")
    keywords: str = Field(..., description="Comma-separated keywords: gmail.com,yahoo.com,outlook.com")
    match_type: MatchTypeEnum = Field(default=MatchTypeEnum.contains, description="How to match")
    action: Optional[ActionEnum] = Field(default=ActionEnum.block, description="Allow or block")
    priority: int = Field(default=100, description="Lower = higher priority. Allowlist=1, Blocklist=100")
    context: Optional[str] = Field(None, description="Why this filter exists")
    is_active: bool = Field(default=True)


class JobAutomationKeywordCreate(JobAutomationKeywordBase):
    pass


class JobAutomationKeywordUpdate(BaseModel):
    category: Optional[str] = Field(None, max_length=50)
    source: Optional[str] = Field(None, max_length=50)
    keywords: Optional[str] = None
    match_type: Optional[MatchTypeEnum] = None
    action: Optional[ActionEnum] = None
    priority: Optional[int] = None
    context: Optional[str] = None
    is_active: Optional[bool] = None


class JobAutomationKeywordOut(JobAutomationKeywordBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }


class PaginatedJobAutomationKeywords(BaseModel):
    total: int
    page: int
    per_page: int
    keywords: List[JobAutomationKeywordOut]


# -------------------- Company HR Contact Schemas --------------------
class CompanyHRContactBase(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    job_title: Optional[str] = None
    is_immigration_team: bool = False

class CompanyHRContactCreate(CompanyHRContactBase):
    full_name: str
    email: EmailStr

class CompanyHRContactUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    job_title: Optional[str] = None
    is_immigration_team: Optional[bool] = None

class CompanyHRContactOut(CompanyHRContactBase):
    id: int
    extraction_date: Optional[datetime] = None

    class Config:
        from_attributes = True


# -------------------- Job Definition Schemas --------------------
class JobDefinitionBase(BaseModel):
    job_type: Optional[str] = None
    status: Optional[str] = "ACTIVE"
    candidate_marketing_id: Optional[int] = None
    email_engine_id: Optional[int] = None
    config_json: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class JobDefinitionCreate(JobDefinitionBase):
    pass


class JobDefinitionUpdate(BaseModel):
    job_type: Optional[str] = None
    status: Optional[str] = None
    candidate_marketing_id: Optional[int] = None
    email_engine_id: Optional[int] = None
    config_json: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class JobDefinitionOut(JobDefinitionBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# -------------------- Job Schedule Schemas --------------------
class JobScheduleBase(BaseModel):
    job_definition_id: Optional[int] = None
    timezone: Optional[str] = "America/Los_Angeles"
    frequency: Optional[str] = None
    interval_value: Optional[int] = 1
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    lock_token: Optional[str] = None
    lock_expires_at: Optional[datetime] = None
    enabled: Optional[bool] = True
    manually_triggered: Optional[bool] = False

    model_config = ConfigDict(from_attributes=True)


class JobScheduleCreate(JobScheduleBase):
    pass


class JobScheduleUpdate(BaseModel):
    job_definition_id: Optional[int] = None
    timezone: Optional[str] = None
    frequency: Optional[str] = None
    interval_value: Optional[int] = None
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    lock_token: Optional[str] = None
    lock_expires_at: Optional[datetime] = None
    enabled: Optional[bool] = None
    manually_triggered: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class JobScheduleOut(JobScheduleBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# -------------------- Job Run Schemas --------------------
class JobRunBase(BaseModel):
    job_definition_id: Optional[int] = None
    job_schedule_id: Optional[int] = None
    run_status: Optional[str] = "RUNNING"
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    items_total: int = 0
    items_succeeded: int = 0
    items_failed: int = 0
    error_message: Optional[str] = None
    details_json: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class JobRunCreate(JobRunBase):
    pass


class JobRunUpdate(BaseModel):
    job_definition_id: Optional[int] = None
    job_schedule_id: Optional[int] = None
    run_status: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    items_total: Optional[int] = None
    items_succeeded: Optional[int] = None
    items_failed: Optional[int] = None
    error_message: Optional[str] = None
    details_json: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class JobRunOut(JobRunBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# -------------------- Job Request Schemas --------------------
class JobRequestBase(BaseModel):
    job_type: str
    candidate_marketing_id: int
    status: str = "PENDING"
    requested_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class JobRequestCreate(BaseModel):
    job_type: str
    candidate_marketing_id: int

    model_config = ConfigDict(from_attributes=True)


class JobRequestUpdate(BaseModel):
    status: Optional[str] = None
    processed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class JobRequestOut(JobRequestBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# -------------------- Email Sender Engine Schemas --------------------
class EmailSenderEngineBase(BaseModel):
    engine_name: str
    provider: str
    is_active: bool = True
    priority: int = 1
    credentials_json: str

    model_config = ConfigDict(from_attributes=True)


class EmailSenderEngineCreate(EmailSenderEngineBase):
    pass


class EmailSenderEngineUpdate(BaseModel):
    engine_name: Optional[str] = None
    provider: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    credentials_json: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class EmailSenderEngineOut(EmailSenderEngineBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# -------------------- Outreach Contact Schemas --------------------
class OutreachContactBase(BaseModel):
    email: str
    source_type: str
    source_id: Optional[int] = None
    status: str = "ACTIVE"
    unsubscribe_flag: bool = False
    unsubscribe_at: Optional[datetime] = None
    unsubscribe_reason: Optional[str] = None
    bounce_flag: bool = False
    bounce_type: Optional[str] = None
    bounce_reason: Optional[str] = None
    bounce_code: Optional[str] = None
    bounced_at: Optional[datetime] = None
    complaint_flag: bool = False
    complained_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class OutreachContactCreate(OutreachContactBase):
    pass


class OutreachContactUpdate(BaseModel):
    email: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[int] = None
    status: Optional[str] = None
    unsubscribe_flag: Optional[bool] = None
    bounce_flag: Optional[bool] = None
    bounce_type: Optional[str] = None
    bounce_reason: Optional[str] = None
    bounce_code: Optional[str] = None
    bounced_at: Optional[datetime] = None
    complaint_flag: Optional[bool] = None
    complained_at: Optional[datetime] = None
    unsubscribe_at: Optional[datetime] = None
    unsubscribe_reason: Optional[str] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class OutreachContactOut(OutreachContactBase):
    id: int
    email_lc: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)



class EmployeeDashboardMetrics(BaseModel):
    employee_info: Employee
    placements: List[CandidatePlacement]
    assigned_prep_candidates: List[CandidatePreparationOut]
    assigned_marketing_candidates: List[CandidateMarketing]
    pending_tasks: List[EmployeeTask]
    job_help_candidates: List[CandidatePlacement]
    classes: List[Recording]
    sessions: List[Session]
    is_birthday: bool = False

    model_config = {
        "from_attributes": True
    }


# -------------------- Company & Company Contact Schemas --------------------

class CompanyBase(BaseModel):
    name: Optional[str] = None
    address1: Optional[str] = None
    address2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    phone_ext: Optional[str] = None
    domain: Optional[str] = None
    notes: Optional[str] = None

    @field_validator('phone')
    @classmethod
    def normalize_phone(cls, v: Optional[str]) -> Optional[str]:
        """Normalize phone number by removing spaces"""
        if v:
            return v.replace(" ", "")
        return v


class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(CompanyBase):
    pass

class CompanyOut(CompanyBase):
    id: int
    created_datetime: datetime
    created_userid: str
    lastmod_datetime: datetime
    lastmod_userid: str

    class Config:
        from_attributes = True

class CompanyContactBase(BaseModel):
    company_id: int
    name: Optional[str] = None
    job_title: Optional[str] = None
    address1: Optional[str] = None
    address2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    phone_ext: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    linkedin_id: Optional[str] = None
    linkedin_internal_id: Optional[str] = None

    @field_validator('phone')
    @classmethod
    def normalize_phone(cls, v: Optional[str]) -> Optional[str]:
        """Normalize phone number by removing spaces"""
        if v:
            return v.replace(" ", "")
        return v


    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: Optional[str]) -> Optional[str]:
        """Normalize email to lowercase"""
        if v:
            return v.lower().strip()
        return v

class CompanyContactCreate(CompanyContactBase):
    pass

class CompanyContactUpdate(CompanyContactBase):
    company_id: Optional[int] = None

    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: Optional[str]) -> Optional[str]:
        """Normalize email to lowercase"""
        if v:
            return v.lower().strip()
        return v

class CompanyContactOut(CompanyContactBase):
    id: int
    created_datetime: datetime
    created_userid: str
    lastmod_datetime: datetime
    lastmod_userid: str

    class Config:
        from_attributes = True


# -------------------- Delivery Engines --------------------
class DeliveryEngineBase(BaseModel):
    name: str
    engine_type: Literal["smtp", "mailgun", "sendgrid", "aws_ses", "outlook_api"]
    host: Optional[str] = None
    port: Optional[int] = None
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    from_email: str
    from_name: Optional[str] = None
    max_recipients_per_run: Optional[int] = None
    batch_size: Optional[int] = 50
    rate_limit_per_minute: Optional[int] = 60
    dedupe_window_minutes: Optional[int] = None
    retry_policy: Optional[Dict[str, Any]] = None
    max_retries: int = 3
    timeout_seconds: int = 600
    status: Literal["active", "inactive", "deprecated"] = "active"

class DeliveryEngineCreate(DeliveryEngineBase):
    pass

class DeliveryEngineUpdate(BaseModel):
    name: Optional[str] = None
    engine_type: Optional[Literal["smtp", "mailgun", "sendgrid", "aws_ses", "outlook_api"]] = None
    host: Optional[str] = None
    port: Optional[int] = None
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    max_recipients_per_run: Optional[int] = None
    batch_size: Optional[int] = None
    rate_limit_per_minute: Optional[int] = None
    dedupe_window_minutes: Optional[int] = None
    retry_policy: Optional[Dict[str, Any]] = None
    max_retries: Optional[int] = None
    timeout_seconds: Optional[int] = None
    status: Optional[Literal["active", "inactive", "deprecated"]] = None

class DeliveryEngine(DeliveryEngineBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# -------------------- Email Templates --------------------
class EmailTemplateBase(BaseModel):
    template_key: str
    name: str
    description: Optional[str] = None
    subject: str
    content_html: str
    content_text: Optional[str] = None
    parameters: Optional[List[str]] = None
    status: Literal["draft", "active", "inactive"] = "draft"
    version: int = 1

class EmailTemplateCreate(EmailTemplateBase):
    pass

class EmailTemplateUpdate(BaseModel):
    template_key: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    subject: Optional[str] = None
    content_html: Optional[str] = None
    content_text: Optional[str] = None
    parameters: Optional[List[str]] = None
    status: Optional[Literal["draft", "active", "inactive"]] = None
    version: Optional[int] = None

class EmailTemplate(EmailTemplateBase):
    id: int
    created_time: datetime
    last_mod_time: datetime
    last_mod_user_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


# -------------------- Automation Workflows --------------------
class AutomationWorkflowBase(BaseModel):
    workflow_key: str
    name: str
    description: Optional[str] = None
    workflow_type: Literal["email_sender", "extractor", "transformer", "webhook", "sync"]
    owner_id: Optional[int] = None
    status: Literal["draft", "active", "paused", "inactive"] = "draft"
    email_template_id: Optional[int] = None
    delivery_engine_id: Optional[int] = None
    credentials_list_sql: Optional[str] = None
    recipient_list_sql: Optional[str] = None
    parameters_config: Optional[Dict[str, Any]] = None
    version: int = 1

class AutomationWorkflowCreate(AutomationWorkflowBase):
    pass

class AutomationWorkflowUpdate(BaseModel):
    workflow_key: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    workflow_type: Optional[Literal["email_sender", "extractor", "transformer", "webhook", "sync"]] = None
    owner_id: Optional[int] = None
    status: Optional[Literal["draft", "active", "paused", "inactive"]] = None
    email_template_id: Optional[int] = None
    delivery_engine_id: Optional[int] = None
    credentials_list_sql: Optional[str] = None
    recipient_list_sql: Optional[str] = None
    parameters_config: Optional[Dict[str, Any]] = None
    version: Optional[int] = None

class AutomationWorkflow(AutomationWorkflowBase):
    id: int
    created_at: datetime
    updated_at: datetime
    last_mod_user_id: Optional[int] = None
    template: Optional[EmailTemplate] = None
    delivery_engine: Optional[DeliveryEngine] = None
    model_config = ConfigDict(from_attributes=True)


# -------------------- Automation Workflows Schedule --------------------
class AutomationWorkflowScheduleBase(BaseModel):
    automation_workflow_id: int
    timezone: str = "America/Los_Angeles"
    cron_expression: Optional[str] = None
    frequency: Literal["once", "daily", "weekly", "monthly", "custom"]
    interval_value: int = 1
    run_parameters: Optional[Dict[str, Any]] = None
    enabled: bool = True

class AutomationWorkflowScheduleCreate(AutomationWorkflowScheduleBase):
    pass

class AutomationWorkflowScheduleUpdate(BaseModel):
    automation_workflow_id: Optional[int] = None
    timezone: Optional[str] = None
    cron_expression: Optional[str] = None
    frequency: Optional[Literal["once", "daily", "weekly", "monthly", "custom"]] = None
    interval_value: Optional[int] = None
    run_parameters: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None

class AutomationWorkflowSchedule(AutomationWorkflowScheduleBase):
    id: int
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    is_running: bool = False
    workflow: Optional[AutomationWorkflow] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# -------------------- Automation Workflow Logs --------------------
class AutomationWorkflowLogBase(BaseModel):
    workflow_id: int
    schedule_id: Optional[int] = None
    run_id: str
    status: Literal["queued", "running", "success", "failed", "partial_success", "timed_out"] = "queued"
    parameters_used: Optional[Any] = None
    execution_metadata: Optional[Any] = None
    records_processed: int = 0
    records_failed: int = 0
    error_summary: Optional[str] = None
    error_details: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

class AutomationWorkflowLogCreate(AutomationWorkflowLogBase):
    pass

class AutomationWorkflowLogUpdate(BaseModel):
    status: Optional[str] = None
    parameters_used: Optional[Any] = None
    execution_metadata: Optional[Any] = None
    records_processed: Optional[int] = None
    records_failed: Optional[int] = None
    error_summary: Optional[str] = None
    error_details: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

class AutomationWorkflowLog(AutomationWorkflowLogBase):
    id: int
    created_at: datetime
    updated_at: datetime
    workflow: Optional[AutomationWorkflow] = None
    model_config = ConfigDict(from_attributes=True)


# -------------------- Outreach Contacts --------------------
class OutreachContactBase(BaseModel):
    email: str
    source_type: str
    source_id: Optional[int] = None
    status: str = "ACTIVE"
    unsubscribe_flag: bool = False
    unsubscribe_at: Optional[datetime] = None
    unsubscribe_reason: Optional[str] = None
    bounce_flag: bool = False
    bounce_type: Optional[str] = None
    bounce_reason: Optional[str] = None
    bounce_code: Optional[str] = None
    bounced_at: Optional[datetime] = None
    complaint_flag: bool = False
    complained_at: Optional[datetime] = None

class OutreachContactCreate(OutreachContactBase):
    pass

class OutreachContactUpdate(BaseModel):
    email: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[int] = None
    status: Optional[str] = None
    unsubscribe_flag: Optional[bool] = None
    unsubscribe_at: Optional[datetime] = None
    unsubscribe_reason: Optional[str] = None
    bounce_flag: Optional[bool] = None
    bounce_type: Optional[str] = None
    bounce_reason: Optional[str] = None
    bounce_code: Optional[str] = None
    bounced_at: Optional[datetime] = None
    complaint_flag: Optional[bool] = None
    complained_at: Optional[datetime] = None

class OutreachContact(OutreachContactBase):
    id: int
    email_lc: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


# -------------------- Personal Domain Contact Schemas --------------------
class PersonalDomainContactBase(BaseModel):
    name: Optional[str] = None
    job_title: Optional[str] = None
    address1: Optional[str] = None
    address2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    phone_ext: Optional[str] = None
    email: str
    linkedin_id: Optional[str] = None
    linkedin_internal_id: Optional[str] = None
    notes: Optional[str] = None

    @field_validator('phone')
    @classmethod
    def normalize_phone(cls, v: Optional[str]) -> Optional[str]:
        """Normalize phone number by removing spaces"""
        if v:
            return v.replace(" ", "")
        return v


    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: Optional[str]) -> Optional[str]:
        """Normalize email to lowercase"""
        if v:
            return v.lower().strip()
        return v

class PersonalDomainContactCreate(PersonalDomainContactBase):
    pass

class PersonalDomainContactUpdate(BaseModel):
    name: Optional[str] = None
    job_title: Optional[str] = None
    address1: Optional[str] = None
    address2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    phone_ext: Optional[str] = None
    email: Optional[str] = None

    @model_validator(mode='before')
    @classmethod
    def empty_string_to_none(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {
                k: (None if v == "" else v)
                for k, v in data.items()
            }
        return data

    @field_validator('phone')
    @classmethod
    def normalize_phone(cls, v: Optional[str]) -> Optional[str]:
        """Normalize phone number by removing spaces"""
        if v:
            return v.replace(" ", "")
        return v

    linkedin_id: Optional[str] = None
    linkedin_internal_id: Optional[str] = None
    notes: Optional[str] = None

    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: Optional[str]) -> Optional[str]:
        """Normalize email to lowercase"""
        if v:
            return v.lower().strip()
        return v

class PersonalDomainContactOut(PersonalDomainContactBase):
    id: int
    created_datetime: datetime
    created_userid: str
    lastmod_datetime: datetime
    lastmod_userid: str

    class Config:
        from_attributes = True


# -------------------- Outreach Email Recipients Schemas --------------------
class OutreachEmailRecipientBase(BaseModel):
    email: str
    email_invalid: bool = False
    domain_invalid: bool = False
    source_type: str
    source_id: Optional[int] = None
    status: str = "ACTIVE"
    unsubscribe_flag: bool = False
    unsubscribe_at: Optional[datetime] = None
    unsubscribe_reason: Optional[str] = None
    bounce_flag: bool = False
    bounce_type: Optional[str] = None
    bounce_reason: Optional[str] = None
    bounce_code: Optional[str] = None
    bounced_at: Optional[datetime] = None
    complaint_flag: bool = False
    complained_at: Optional[datetime] = None

    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: Optional[str]) -> Optional[str]:
        """Normalize email to lowercase"""
        if v:
            return v.lower().strip()
        return v

class OutreachEmailRecipientCreate(OutreachEmailRecipientBase):
    pass

class OutreachEmailRecipientUpdate(BaseModel):
    email: Optional[str] = None
    email_invalid: Optional[bool] = None
    domain_invalid: Optional[bool] = None
    source_type: Optional[str] = None
    source_id: Optional[int] = None
    status: Optional[str] = None
    unsubscribe_flag: Optional[bool] = None
    unsubscribe_at: Optional[datetime] = None
    unsubscribe_reason: Optional[str] = None
    bounce_flag: Optional[bool] = None
    complained_at: Optional[datetime] = None

    @model_validator(mode='before')
    @classmethod
    def empty_string_to_none(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {
                k: (None if v == "" else v)
                for k, v in data.items()
            }
        return data

    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: Optional[str]) -> Optional[str]:
        """Normalize email to lowercase"""
        if v:
            return v.lower().strip()
        return v

class OutreachEmailRecipientOut(OutreachEmailRecipientBase):
    id: int
    email_lc: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# -------------------- Linkedin Only Contact Schemas --------------------
class LinkedinOnlyContactBase(BaseModel):
    name: Optional[str] = None
    job_title: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    linkedin_id: Optional[str] = None
    linkedin_internal_id: Optional[str] = None
    notes: Optional[str] = None

    @field_validator('phone')
    @classmethod
    def normalize_phone(cls, v: Optional[str]) -> Optional[str]:
        """Normalize phone number by removing spaces"""
        if v:
            return v.replace(" ", "")
        return v

class LinkedinOnlyContactCreate(LinkedinOnlyContactBase):
    pass

class LinkedinOnlyContactUpdate(BaseModel):
    name: Optional[str] = None
    job_title: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    linkedin_id: Optional[str] = None
    linkedin_internal_id: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode='before')
    @classmethod
    def empty_string_to_none(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {
                k: (None if v == "" else v)
                for k, v in data.items()
            }
        return data

    @field_validator('phone')
    @classmethod
    def normalize_phone(cls, v: Optional[str]) -> Optional[str]:
        """Normalize phone number by removing spaces"""
        if v:
            return v.replace(" ", "")
        return v

class LinkedinOnlyContactOut(LinkedinOnlyContactBase):
    id: int
    created_datetime: datetime
    created_userid: str
    lastmod_datetime: datetime
    lastmod_userid: str

    class Config:
        from_attributes = True

class PaginatedLinkedinOnlyContactResponse(BaseModel):
    data: List[LinkedinOnlyContactOut]
    page: int
    page_size: int
    total_records: int
    total_pages: int
    has_next: bool
    has_prev: bool

# ------------------ Email SMTP Credentials ------------------

class EmailSMTPCredentialsBase(BaseModel):
    name: str
    email: EmailStr
    daily_limit: int
    note: Optional[str] = None
    is_active: bool = True

    @field_validator('daily_limit')
    @classmethod
    def validate_daily_limit(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('daily_limit must be greater than 0')
        return v

class EmailSMTPCredentialsCreate(EmailSMTPCredentialsBase):
    password: str
    app_password: Optional[str] = None

class EmailSMTPCredentialsUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    app_password: Optional[str] = None
    daily_limit: Optional[int] = None
    note: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator('daily_limit')
    @classmethod
    def validate_daily_limit(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError('daily_limit must be greater than 0')
        return v

class EmailSMTPCredentialsOut(EmailSMTPCredentialsBase):
    id: int
    password: str
    app_password: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

