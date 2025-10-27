from pydantic import BaseModel, EmailStr, Field
from decimal import Decimal 
from typing import Optional, List, Literal
from datetime import time, date, datetime
from sqlalchemy.sql import func
from sqlalchemy import Column, Integer, String, Enum, DateTime, Boolean, Date ,DECIMAL, Text, ForeignKey, TIMESTAMP,Enum as SQLAEnum, func, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import declarative_base, relationship
import enum



Base = declarative_base()




class UserCreate(BaseModel):
    uname: str
    passwd: str

# -----------------------------------------------------

class AuthUserORM(Base):
    __tablename__ = "authuser"

    id = Column(Integer, primary_key=True, index=True)
    uname = Column(String(50), unique=True, nullable=False, default="")
    passwd = Column(String(32), nullable=False)
    team = Column(String(255))
    status = Column(String(255), default="inactive")
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
    lastmoddatetime = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    enddate = Column(Date, default="1990-01-01")
    googleId = Column(String(255))
    reset_token = Column(String(255))
    token_expiry = Column(DateTime)
    role = Column(String(100))
    visa_status = Column(String(50))
    notes = Column(Text)


# ----------------------------------------------
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



    
# ------------------------------------------- Leads----------------------------------------
class LeadORM(Base):
    __tablename__ = "lead"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(255))
    entry_date = Column(DateTime)
    phone = Column(String(20))
    email = Column(String(255), nullable=False)
    workstatus = Column(String(50),default="Waiting for Status")
    status = Column(String(45), nullable=False, server_default="Open")
    secondary_email = Column(String(255))
    secondary_phone = Column(String(20))
    address = Column(String(255))
    closed_date = Column(Date)
    notes = Column(String(500))
    massemail_unsubscribe = Column(Boolean, nullable=True)
    massemail_email_sent = Column(Boolean, nullable=True)
    moved_to_candidate = Column(Boolean,server_default='0')
    last_modified = Column(
        DateTime,
        default=func.now(),       # set automatically on insert
        onupdate=func.now()       # update automatically when record changes
    )

# -------------------------------------------------------------------------------



# .......................................NEW INNOVAPATH..............................


class TalentSearch(Base):
    __tablename__ = "talent_search"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100))
    email = Column(String(100))
    phone = Column(String(20))
    role = Column(String(50))
    experience = Column(Integer)
    location = Column(String(100))
    availability = Column(String(50))
    skills = Column(Text)



class VendorTypeEnum(str, enum.Enum):
    client = "client"
    third_party_vendor = "third-party-vendor"
    implementation_partner = "implementation-partner"
    sourcer = "sourcer"
    contact_from_ip = "contact-from-ip"

class Vendor(Base):
    __tablename__ = "vendor"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=True)
    phone_number = Column(String(50))
    secondary_phone = Column(String(50))
    email = Column(String(255), unique=True, index=True)
    type = Column(
        SQLAEnum(
            VendorTypeEnum,
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        server_default=VendorTypeEnum.client.value
    )
    notes = Column(Text)
    linkedin_id = Column(String(255))
    company_name = Column(String(255))
    location = Column(String(255))
    city = Column(String(50))
    postal_code = Column(String(20))
    address = Column(Text)
    country = Column(String(50))
    
    status = Column(
        SQLAEnum(
            "active",
            "working",
            "not_useful",
            "do_not_contact",
            "inactive",
            "prospect",
            name="vendorstatusenum"
        ),
        default="prospect"
    )
    linkedin_connected = Column(
        SQLAEnum("YES", "NO", name="yesnoenum"),
        default="NO"
    )
    intro_email_sent = Column(
        SQLAEnum("YES", "NO", name="yesnoenum2"),
        default="NO"
    )
    intro_call = Column(
        SQLAEnum("YES", "NO", name="yesnoenum3"),
        default="NO"
    )
    created_at = Column(TIMESTAMP, server_default=func.now())
    linkedin_internal_id = Column(String(255))

# ------------------------------------------



class UnsubscribeUser(Base):
    __tablename__ = "massemail"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False)
    remove = Column(String(1), default='N') 
    


# ------------------------------------- Candidate --------------------
class CandidateORM(Base):
    __tablename__ = "candidate"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String(100), nullable=True)
    enrolled_date = Column(Date, nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(100), nullable=True)
    status = Column(Enum('active', 'inactive', 'discontinued', 'break', 'closed', name='status_enum'), nullable=True)
    workstatus = Column(String(50), nullable=True)
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
    batchid = Column(Integer, ForeignKey("batch.batchid"), nullable=False)
    github_link = Column(String(500), nullable=True)
    candidate_folder = Column(String(500), nullable=True, comment="Google Drive folder link for the candidate")
    move_to_prep = Column(Boolean, default=False)
   
    interviews = relationship("CandidateInterview", back_populates="candidate", cascade="all, delete-orphan")
    preparations = relationship("CandidatePreparation", back_populates="candidate", cascade="all, delete-orphan")
    placements = relationship("CandidatePlacementORM", back_populates="candidate", cascade="all, delete-orphan")
    marketing_records = relationship("CandidateMarketingORM", back_populates="candidate", cascade="all, delete-orphan")
    
    preparation_records = relationship("CandidatePreparation", back_populates="candidate")
    # marketing_records = relationship("CandidateMarketingORM", back_populates="candidate")
    
    interview_records = relationship("CandidateInterview", back_populates="candidate")
    placement_records = relationship("CandidatePlacementORM", back_populates="candidate")
    placement_records = relationship("CandidatePlacementORM", foreign_keys="[CandidatePlacementORM.candidate_id]")

    batch = relationship("Batch", back_populates="candidates")
    preparation_records = relationship("CandidatePreparation", back_populates="candidate", cascade="all, delete-orphan" )

# --------------------- Candidate Marketing -----------------
class CandidateMarketingORM(Base):
    __tablename__ = "candidate_marketing"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidate.id"), nullable=False)

    start_date = Column(Date, nullable=False)
    status = Column(Enum("active", "inactive"), nullable=False, default="active")
    last_mod_datetime = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    marketing_manager = Column(Integer, ForeignKey("employee.id"), nullable=True)

    email = Column(String(100), nullable=True)
    password = Column(String(100), nullable=True)
    google_voice_number = Column(String(100), nullable=True)
    priority = Column(Integer, nullable=True)  # integer 1-5
    notes = Column(Text, nullable=True)
    resume_url = Column(String(255), nullable=True)
    move_to_placement = Column(Boolean, default=False)

    # Relationships
    candidate = relationship("CandidateORM", back_populates="marketing_records")
    marketing_manager_obj = relationship("EmployeeORM", foreign_keys=[marketing_manager])

# # -------------------------------------- Candidate Interview -------------------------------

class CandidateInterview(Base):
    __tablename__ = "candidate_interview"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidate.id"), nullable=False)
    candidate = relationship("CandidateORM", back_populates="interviews")

    company = Column(String(200), nullable=False)
    company_type = Column(
        Enum(
            "client",
            "third-party-vendor",
            "implementation-partner",
            "sourcer",
            name="company_type_enum"
        ),
        nullable=True,
        default="client"  
    )

    interviewer_emails = Column(Text, nullable=True)
    interviewer_contact = Column(Text, nullable=True)
    interviewer_linkedin = Column(String(500), nullable=True)
    interview_date = Column(Date, nullable=False)

    mode_of_interview = Column(
        Enum(
            "Virtual", "In Person", "Phone", "Assessment", "AI Interview",
            name="mode_of_interview_enum"
        ),
        nullable=True,
        default="Virtual"  
    )

    type_of_interview = Column(
        Enum(
            "Recruiter Call", "Technical", "HR", "Prep Call",
            name="type_of_interview_enum"
        ),
        nullable=True,
        default="Recruiter Call"  
    )

    transcript = Column(String(500), nullable=True)
    recording_link = Column(String(500), nullable=True)
    backup_recording_url = Column(String(500), nullable=True)  
    job_posting_url = Column(String(500), nullable=True)  

    feedback = Column(
        Enum("Pending", "Positive", "Negative", name="feedback_enum"),
        nullable=True,
        default="Pending"  
    )

    notes = Column(Text, nullable=True)
    last_mod_datetime = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


# -------------------------------------- Candidate Placement -------------------------------

class CandidatePlacementORM(Base):
    __tablename__ = "candidate_placement"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False)

    position = Column(String(255), nullable=True)
    company = Column(String(200), nullable=False)
    placement_date = Column(Date, nullable=False)
    type = Column(Enum('Company', 'Client', 'Vendor', 'Implementation Partner'), nullable=True)
    
    status = Column(Enum('Active', 'Inactive'), nullable=False)

    base_salary_offered = Column(DECIMAL(10, 2), nullable=True)
    benefits = Column(Text, nullable=True)
    fee_paid = Column(DECIMAL(10, 2), nullable=True)
    notes = Column(Text, nullable=True)
    last_mod_datetime = Column(TIMESTAMP, default=None, onupdate=None)

    # priority = Column(Integer, default=99)

    candidate = relationship("CandidateORM", back_populates="placements")

# -------------------------------------- Candidate Preparation -------------------------------


class CandidatePreparation(Base):
    __tablename__ = "candidate_preparation"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidate.id"), nullable=False)

    candidate = relationship(
        "CandidateORM",
        back_populates="preparation_records",
        overlaps="preparations"
    )

    instructor1_id = Column(Integer, ForeignKey("employee.id"), nullable=True)
    instructor2_id = Column(Integer, ForeignKey("employee.id"), nullable=True)
    instructor3_id = Column(Integer, ForeignKey("employee.id"), nullable=True)

    instructor1 = relationship(
        "EmployeeORM", foreign_keys=[instructor1_id], overlaps="instructor1_employee"
    )
    instructor2 = relationship(
        "EmployeeORM", foreign_keys=[instructor2_id], overlaps="instructor2_employee"
    )
    instructor3 = relationship(
        "EmployeeORM", foreign_keys=[instructor3_id], overlaps="instructor3_employee"
    )

    start_date = Column(Date, nullable=True)
    status = Column(Enum("active", "break", "not responding", "inactive"), nullable=False)

    rating = Column(String(50), nullable=True)
    tech_rating = Column(String(50), nullable=True)
    communication = Column(String(50), nullable=True)
    years_of_experience = Column(String(50), nullable=True)
    topics_finished = Column(Text, nullable=True)
    current_topics = Column(Text, nullable=True)
    target_date_of_marketing = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    linkedin = Column(String(255), nullable=True)
    github = Column(String(255), nullable=True)
    resume = Column(String(255), nullable=True)
    last_mod_datetime = Column(TIMESTAMP, nullable=True)
    move_to_mrkt = Column(Boolean, default=False, nullable=False)

# ---------------------------------------------------------------
class EmployeeORM(Base):
    __tablename__ = "employee"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=True)
    email = Column(String(150), nullable=True, unique=True)
    phone = Column(String(150), nullable=True)
    address = Column(String(250), nullable=True)
    state = Column(String(150), nullable=True)
    dob = Column(Date, nullable=True)
    startdate = Column(Date, nullable=True)
    instructor = Column(Integer, nullable=True)
    enddate = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(Integer, nullable=True)
    aadhaar = Column(String(20), nullable=True, unique=True)
    

class CandidateStatus(str, enum.Enum):
    active = "active"
    break_ = "break"
    not_responding = "not responding"
    inactive = "inactive"




# -------------------- Enums --------------------


    
class VendorContactExtractsORM(Base):
    __tablename__ = "vendor_contact_extracts"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True, unique=False)
    phone = Column(String(50), nullable=True)
    linkedin_id = Column(String(255), nullable=True)
    company_name = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    moved_to_vendor = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    linkedin_internal_id = Column(String(255))

# -------------------- ORM: vendor-daily-activity --------------------
class YesNoEnum(str, enum.Enum):
    YES = "YES"
    NO = "NO"

class DailyVendorActivityORM(Base):
    __tablename__ = "vendor_daily_activity"

    activity_id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendor.id"), nullable=False)
    application_date = Column(Date, nullable=True)
    linkedin_connected = Column(SQLAEnum(YesNoEnum), nullable=True)
    contacted_on_linkedin = Column(SQLAEnum(YesNoEnum), nullable=True)
    notes = Column(String(1000), nullable=True)
    employee_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CourseContent(Base):
    __tablename__ = "course_content"

    id = Column(Integer, primary_key=True, index=True)
    Fundamentals = Column(String(255), nullable=True)
    AIML = Column(String(255), nullable=False)
    UI = Column(String(255), nullable=True)
    QE = Column(String(255), nullable=True)



class CourseMaterial(Base):
    __tablename__ = "course_material"

    id = Column(Integer, primary_key=True, index=True)
    subjectid = Column(Integer, nullable=False, default=0)
    courseid = Column(Integer, nullable=False)
    name = Column(String(250), nullable=False)
    description = Column(String(500))
    type = Column(String(1), nullable=False, default='P')
    link = Column(String(500), nullable=False)
    sortorder = Column(Integer, nullable=False, default=9999)
    


# ----------------------Resources--------------------


class Course(Base):
    __tablename__ = "course"
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(255))
    alias = Column(String(100), unique=True)
    description = Column(Text, nullable=True)  
    syllabus = Column(Text, nullable=True)     
    lastmoddatetime = Column(DateTime, default=datetime.now, onupdate=datetime.now) 
    subjects = relationship("CourseSubject", back_populates="course")
    batches = relationship("Batch", back_populates="course")

class Subject(Base):
    __tablename__ = "subject"
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(255))
    description = Column(String(300), nullable=False)  
    lastmoddatetime = Column(DateTime, default=datetime.now, onupdate=datetime.now)  
    course_subjects = relationship("CourseSubject", back_populates="subject")
    recordings = relationship("Recording", back_populates="subject")
    recordings = relationship("Recording", back_populates="subject_rel")  




class CourseSubject(Base):
    __tablename__ = "course_subject"
    subject_id = Column(Integer, ForeignKey("subject.id"), primary_key=True)
    course_id = Column(Integer, ForeignKey("course.id"), primary_key=True)
    lastmoddatetime = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    course = relationship("Course", back_populates="subjects")
    subject = relationship("Subject", back_populates="course_subjects")

    # --------------------------------------------------------

class Batch(Base):
    __tablename__ = "batch"


    batchid = Column(Integer, primary_key=True, index=True, autoincrement=True)
    batchname = Column(String(100), nullable=False)
    orientationdate = Column(Date, nullable=True)
    subject = Column(String(45), nullable=False, default="ML")
    startdate = Column(Date, nullable=True)
    enddate = Column(Date, nullable=True)
    courseid = Column(Integer, ForeignKey("course.id"), nullable=True)

    course = relationship("Course", back_populates="batches")
    recording_batches = relationship("RecordingBatch", back_populates="batch")

    candidates = relationship("CandidateORM", back_populates="batch")



class Recording(Base):
    __tablename__ = "recording"
    id = Column(Integer, primary_key=True, index=True)
    batchname = Column(String(255))
    description = Column(Text)
    type = Column(String(50))
    classdate = Column(DateTime, nullable=True)
    link = Column(String(1024))
    videoid = Column(String(255))
    subject = Column(String(255))
    filename = Column(String(255))
    # lastmoddatetime = Column(DateTime)
    new_subject_id = Column(Integer, ForeignKey("subject.id"))

    subject_rel = relationship("Subject", back_populates="recordings")  
    recording_batches = relationship("RecordingBatch", back_populates="recording")



class RecordingBatch(Base):
    __tablename__ = "recording_batch"
    recording_id = Column(Integer, ForeignKey("recording.id"), primary_key=True)
    batch_id = Column(Integer, ForeignKey("batch.batchid"), primary_key=True)
    
    recording = relationship("Recording", back_populates="recording_batches")
    batch = relationship("Batch", back_populates="recording_batches")


# ----------------Sessions ---------------------
class Session(Base):
    __tablename__ = "session"
    sessionid = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    link = Column(String(1024))
    videoid = Column(String(255))

    type = Column(String(50))
    sessiondate = Column(DateTime)
    lastmoddatetime = Column(DateTime)
    # subject_id = Column(Integer, ForeignKey("subject.id"))
    subject_id = Column(Integer, nullable=False, default=0)
    # subject = relationship("Subject", back_populates="sessions")
    subject = Column(String(45))

    #-------------------Internal documents--------------------
class InternalDocument(Base):
    __tablename__ = "internal_documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), nullable=False)
    description = Column(String(500), nullable=True)
    filename = Column(String(300), nullable=False)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
