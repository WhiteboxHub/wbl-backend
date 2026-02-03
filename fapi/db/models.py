from decimal import Decimal
from typing import Optional, List, Literal
from datetime import time, date, datetime
from sqlalchemy import Column, Integer, String, Enum, DateTime, UniqueConstraint, Boolean, Date, DECIMAL, BigInteger, Text, ForeignKey, TIMESTAMP, Enum as SQLAEnum, func, text, JSON, Index, FetchedValue
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import declarative_base, relationship
import enum
from fapi.db.schemas import PositionTypeEnum, EmploymentModeEnum, PositionStatusEnum, ProcessingStatusEnum

Base = declarative_base()



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
    lastmoddatetime = Column(
        TIMESTAMP, server_default=func.now(), onupdate=func.now())
    enddate = Column(Date, default="1990-01-01")
    googleId = Column(String(255))
    reset_token = Column(String(255))
    token_expiry = Column(DateTime)
    role = Column(String(100))
    visa_status = Column(
        SQLAEnum(
            'US_CITIZEN', 'GREEN_CARD', 'GC_EAD', 'I485_EAD', 'I140_APPROVED',
            'F1', 'F1_OPT', 'F1_CPT', 'J1', 'J1_AT', 'H1B', 'H1B_TRANSFER',
            'H1B_CAP_EXEMPT', 'H4', 'H4_EAD', 'L1A', 'L1B', 'L2', 'L2_EAD',
            'O1', 'TN', 'E3', 'E3_EAD', 'E2', 'E2_EAD', 'TPS_EAD', 'ASYLUM_EAD',
            'REFUGEE_EAD', 'DACA_EAD',
            name='visa_status_enum'
        ),
        nullable=True
    )
    notes = Column(Text)



# ------------------------------------------- Leads----------------------------------------
class LeadORM(Base):
    __tablename__ = "lead"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(255))
    entry_date = Column(DateTime)
    phone = Column(String(20))
    email = Column(String(255), nullable=False)
    workstatus = Column(
        SQLAEnum(
            'US_CITIZEN', 'GREEN_CARD', 'GC_EAD', 'I485_EAD', 'I140_APPROVED',
            'F1', 'F1_OPT', 'F1_CPT', 'J1', 'J1_AT', 'H1B', 'H1B_TRANSFER',
            'H1B_CAP_EXEMPT', 'H4', 'H4_EAD', 'L1A', 'L1B', 'L2', 'L2_EAD',
            'O1', 'TN', 'E3', 'E3_EAD', 'E2', 'E2_EAD', 'TPS_EAD', 'ASYLUM_EAD',
            'REFUGEE_EAD', 'DACA_EAD',
            name='visa_status_enum'
        ),
        nullable=True
    )
    status = Column(String(45), nullable=False, server_default="Open")
    secondary_email = Column(String(255))
    secondary_phone = Column(String(20))
    address = Column(String(255))
    closed_date = Column(Date)
    notes = Column(String(500))
    massemail_unsubscribe = Column(Boolean, nullable=True)
    massemail_email_sent = Column(Boolean, nullable=True)
    moved_to_candidate = Column(Boolean, server_default='0')
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
    status = Column(Enum('active', 'inactive', 'discontinued',
                    'break', 'closed', name='status_enum'), nullable=True)
    workstatus = Column(
        SQLAEnum(
            'US_CITIZEN', 'GREEN_CARD', 'GC_EAD', 'I485_EAD', 'I140_APPROVED',
            'F1', 'F1_OPT', 'F1_CPT', 'J1', 'J1_AT', 'H1B', 'H1B_TRANSFER',
            'H1B_CAP_EXEMPT', 'H4', 'H4_EAD', 'L1A', 'L1B', 'L2', 'L2_EAD',
            'O1', 'TN', 'E3', 'E3_EAD', 'E2', 'E2_EAD', 'TPS_EAD', 'ASYLUM_EAD',
            'REFUGEE_EAD', 'DACA_EAD',
            name='visa_status_enum'
        ),
        nullable=True
    )
    education = Column(String(200), nullable=True)
    workexperience = Column(String(200), nullable=True)
    ssn = Column(String(11), nullable=True)
    agreement = Column(String(1), default="N", nullable=True)
    secondaryemail = Column(String(100), nullable=True)
    secondaryphone = Column(String(45), nullable=True)
    address = Column(String(300), nullable=True)
    zip_code = Column(String(20), nullable=True)
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
    candidate_folder = Column(String(500), nullable=True)
    move_to_prep = Column(Boolean, default=False)


    interviews = relationship(
        "CandidateInterview", back_populates="candidate", cascade="all, delete-orphan")
    preparations = relationship(
        "CandidatePreparation", back_populates="candidate", cascade="all, delete-orphan")
    placements = relationship(
        "CandidatePlacementORM", back_populates="candidate", cascade="all, delete-orphan")
    marketing_records = relationship(
        "CandidateMarketingORM", back_populates="candidate", cascade="all, delete-orphan")

    # Extra relationship aliases with 'overlaps' to satisfy SQLAlchemy warnings
    preparation_records = relationship(
        "CandidatePreparation", back_populates="candidate")
    interview_records = relationship(
        "CandidateInterview", back_populates="candidate", overlaps="interviews")
    placement_records = relationship(
        "CandidatePlacementORM", foreign_keys="[CandidatePlacementORM.candidate_id]")

    batch = relationship("Batch", back_populates="candidates")

# --------------------- Candidate Marketing -----------------


class CandidateMarketingORM(Base):
    __tablename__ = "candidate_marketing"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidate.id"), nullable=False)

    start_date = Column(Date, nullable=False)
    status = Column(Enum("active", "inactive"),
                    nullable=False, default="active")
    last_mod_datetime = Column(
        TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    marketing_manager = Column(
        Integer, ForeignKey("employee.id"), nullable=True)

    imap_password = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    password = Column(String(100), nullable=True)
    priority = Column(Integer, nullable=True)
    google_voice_number = Column(String(100), nullable=True)
    linkedin_username = Column(String(100), nullable=True)
    linkedin_passwd = Column(String(100), nullable=True)
    linkedin_premium_end_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    resume_url = Column(String(255), nullable=True)
    move_to_placement = Column(Boolean, default=False)
    mass_email = Column(Boolean, nullable=False, server_default="0")
    candidate_intro = Column(Text, nullable=True)

    # Relationships
    candidate = relationship(
        "CandidateORM", back_populates="marketing_records")
    marketing_manager_obj = relationship(
        "EmployeeORM", foreign_keys=[marketing_manager])
    # email_logs = relationship(
    #     "EmailActivityLogORM", back_populates="marketing", cascade="all, delete-orphan")
# # -------------------------------------- Candidate Interview -------------------------------


class CandidateInterview(Base):
    __tablename__ = "candidate_interview"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidate.id"), nullable=False)
    candidate = relationship("CandidateORM", back_populates="interviews", overlaps="interview_records")

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
    position_id = Column(BigInteger, ForeignKey("position.id", ondelete="SET NULL"), nullable=True)
    last_mod_datetime = Column(
        TIMESTAMP, server_default=func.now(), onupdate=func.now())

    position = relationship("PositionORM")


# -------------------------------------- Candidate Placement -------------------------------

class CandidatePlacementORM(Base):
    __tablename__ = "candidate_placement"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey(
        "candidate.id", ondelete="CASCADE"), nullable=False)

    position = Column(String(255), nullable=True)
    company = Column(String(200), nullable=False)
    placement_date = Column(Date, nullable=False)
    type = Column(Enum('Company', 'Client', 'Vendor',
                  'Implementation Partner'), nullable=True)

    status = Column(Enum('Active', 'Inactive'), nullable=False)
    no_of_installments = Column(
        Enum('1', '2', '3', '4', '5', name="installment_enum"),
        nullable=True
    )

    base_salary_offered = Column(DECIMAL(10, 2), nullable=True)
    benefits = Column(Text, nullable=True)
    fee_paid = Column(DECIMAL(10, 2), nullable=True)
    notes = Column(Text, nullable=True)
    last_mod_datetime = Column(TIMESTAMP, default=None, onupdate=None)

    candidate = relationship("CandidateORM", back_populates="placements", overlaps="placement_records")

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

    start_date = Column(Date, nullable=False, server_default="CURRENT_DATE")
    status = Column(Enum("active", "inactive"),
                    nullable=False, default="active")

    rating = Column(Enum("excellent", "very good", "good",
                    "average", "need to improve"), nullable=True)
    communication = Column(Enum("excellent", "very good",
                           "good", "average", "need to improve"), nullable=True)
    years_of_experience = Column(Integer, nullable=True)

    target_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    # linkedin_id = Column(String(255), nullable=True)
    github_url = Column(String(255), nullable=True)
    resume_url = Column(String(255), nullable=True)
    last_mod_datetime = Column(TIMESTAMP, nullable=True)
    move_to_mrkt = Column(Boolean, default=False, nullable=False)

# ---------------------------------------------------------------

# -----------------------------Placement_Fee_Collection---------------------------------

class AmountCollectedEnum(str, enum.Enum):
    yes = "yes"
    no = "no"

class PlacementFeeCollection(Base):
    __tablename__ = "placement_fee_collection"

    id = Column(Integer, primary_key=True, autoincrement=True)
    placement_id = Column(Integer, ForeignKey("candidate_placement.id"), nullable=False)
    installment_id = Column(Integer, nullable=True)
    deposit_date = Column(Date, nullable=True)
    deposit_amount = Column(DECIMAL(10, 2), nullable=True)
    amount_collected = Column(Enum(AmountCollectedEnum), nullable=False, default=AmountCollectedEnum.no)
    lastmod_user_id = Column(Integer, nullable=True)
    last_mod_date = Column(
        TIMESTAMP,
        nullable=True,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )


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
    # status = Column(Integer, nullable=True)
    status = Column(Integer)
    aadhaar = Column(String(20), nullable=True, unique=True)
    tasks = relationship("EmployeeTaskORM", back_populates="employee")

    tasks = relationship("EmployeeTaskORM", back_populates="employee")

# Class EmployeeTaskORM moved to below ProjectORM to support relationship


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
    extraction_date = Column(DateTime, nullable=True)
    source_email = Column(String(255), nullable=True)
    notes = Column(String(500), nullable=True)
    job_source = Column(String(100), nullable=True)

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
    extraction_date = Column(DateTime, nullable=True)
    source_email = Column(String(255), nullable=True)
    contacted_on_linkedin = Column(SQLAEnum(YesNoEnum), nullable=True)
    notes = Column(String(1000), nullable=True)
    employee_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---------linkedin_activity_log----------------------
class LinkedInActivityLogORM(Base):
    __tablename__ = "linkedin_activity_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(
        Integer,
        ForeignKey("candidate_marketing.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_email = Column(String(100), nullable=True)
    activity_type = Column(
        Enum('extraction', 'connection', name='activity_type'), nullable=False)
    linkedin_profile_url = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    company_name = Column(String(255), nullable=True)
    status = Column(Enum('success', 'failed', name='status'),
                    server_default='success')
    message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

# ---------------------------------------------------------------------


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
    lastmoddatetime = Column(
        DateTime, default=datetime.now, onupdate=datetime.now)
    subjects = relationship("CourseSubject", back_populates="course")
    batches = relationship("Batch", back_populates="course")


class Subject(Base):
    __tablename__ = "subject"
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(255))
    description = Column(String(300), nullable=False)
    lastmoddatetime = Column(
        DateTime, default=datetime.now, onupdate=datetime.now)
    course_subjects = relationship("CourseSubject", back_populates="subject")
    recordings = relationship("Recording", back_populates="subject")
    recordings = relationship("Recording", back_populates="subject_rel")


class CourseSubject(Base):
    __tablename__ = "course_subject"
    subject_id = Column(Integer, ForeignKey("subject.id"), primary_key=True)
    course_id = Column(Integer, ForeignKey("course.id"), primary_key=True)
    lastmoddatetime = Column(
        DateTime, default=datetime.now, onupdate=datetime.now)

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
    # batchname = Column(String(255))
    description = Column(Text)
    type = Column(String(50))
    classdate = Column(DateTime, nullable=True)
    link = Column(String(1024))
    videoid = Column(String(255))
    subject = Column(String(255))
    filename = Column(String(255))
    lastmoddatetime = Column(DateTime)
    backup_url = Column(String(400))
    new_subject_id = Column(Integer, ForeignKey("subject.id"))

    subject_rel = relationship("Subject", back_populates="recordings")
    recording_batches = relationship(
        "RecordingBatch", back_populates="recording", cascade="all, delete-orphan")


class RecordingBatch(Base):
    __tablename__ = "recording_batch"
    recording_id = Column(Integer, ForeignKey(
        "recording.id"), primary_key=True)
    batch_id = Column(Integer, ForeignKey("batch.batchid"), primary_key=True)

    recording = relationship("Recording", back_populates="recording_batches")
    batch = relationship("Batch", back_populates="recording_batches")


# ----------------Sessions ---------------------
class Session(Base):
    __tablename__ = "session"
    sessionid = Column(Integer, primary_key=True, index=True)
    title = Column(String(500))
    status = Column(String(45), nullable=False)
    link = Column(String(1024))
    videoid = Column(String(255))
    backup_url = Column(String(200))
    type = Column(String(50))
    sessiondate = Column(DateTime)
    lastmoddatetime = Column(DateTime)
    # subject_id = Column(Integer, ForeignKey("subject.id"))
    subject_id = Column(Integer, nullable=False, default=0)
    # subject = relationship("Subject", back_populates="sessions")
    subject = Column(String(45))
    notes = Column(String(100))
  # -------------------Internal documents--------------------


class InternalDocument(Base):
    __tablename__ = "internal_documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), nullable=False)
    description = Column(String(500), nullable=True)
    # filename = Column(String(300), nullable=False)
    file = Column(String(1024), nullable=True)


# -------------------- Job Types --------------------
class JobTypeORM(Base):
    __tablename__ = "job_types"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    unique_id = Column(String(100), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    job_owner_1 = Column(Integer, ForeignKey("employee.id"), nullable=True)
    job_owner_2 = Column(Integer, ForeignKey("employee.id"), nullable=True)
    job_owner_3 = Column(Integer, ForeignKey("employee.id"), nullable=True)
    category = Column(Enum("manual", "automation", name="job_type_category"), nullable=False, server_default="manual")
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    lastmod_date_time = Column(TIMESTAMP, server_default=func.current_timestamp(
    ), onupdate=func.current_timestamp())
    lastmod_user_id = Column(Integer, ForeignKey("employee.id"), nullable=True)


# -------------------- Job Activity Log --------------------
class JobActivityLogORM(Base):
    __tablename__ = "job_activity_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_type_id = Column(Integer, ForeignKey("job_types.id"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("candidate.id"), nullable=True)
    employee_id = Column(Integer, ForeignKey("employee.id"), nullable=True)
    activity_date = Column(Date, nullable=False)
    activity_count = Column(Integer, default=0)
    notes = Column(Text, nullable=True)
    lastmod_user_id = Column(Integer, ForeignKey("employee.id"), nullable=True)
    lastmod_date_time = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )

    # Relationships
    job_type = relationship("JobTypeORM")
    candidate = relationship("CandidateORM")
    employee = relationship("EmployeeORM", foreign_keys=[employee_id])
    lastmod_user = relationship("EmployeeORM", foreign_keys=[lastmod_user_id])


# -------------------- Job Automation Keywords --------------------
class JobAutomationKeywordORM(Base):
    __tablename__ = "job_automation_keywords"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    category = Column(String(50), nullable=False, comment="blocked_personal_domain, allowed_staffing_domain, etc.")
    source = Column(String(50), nullable=False, server_default="email_extractor", comment="Which extractor uses this")
    keywords = Column(Text, nullable=False, comment="Comma-separated: gmail.com,yahoo.com,outlook.com")
    match_type = Column(
        Enum("exact", "contains", "regex", name="match_type_enum"),
        nullable=False,
        server_default="contains",
        comment="How to match"
    )
    action = Column(
        Enum("allow", "block", name="action_enum"),
        server_default="block",
        comment="allow or block"
    )
    priority = Column(Integer, server_default="100", comment="Lower = higher priority. Allowlist=1, Blocklist=100")
    context = Column(Text, nullable=True, comment="Why this filter exists")
    is_active = Column(Boolean, server_default="1")
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )



class CompanyHRContact(Base):
    __tablename__ = "company_hr_contacts"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255))
    email = Column(String(255), unique=True, index=True)
    phone = Column(String(50))
    company_name = Column(String(255))
    location = Column(String(500))
    job_title = Column(String(255))
    is_immigration_team = Column(Boolean, default=False)
    extraction_date = Column(TIMESTAMP, server_default=func.now())



# -------------------- Projects --------------------
class ProjectORM(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner = Column(String(150), nullable=False)
    start_date = Column(Date, nullable=False)
    target_end_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    priority = Column(Enum('Low', 'Medium', 'High', 'Critical'), default='Medium')
    status = Column(Enum('Planned', 'In Progress', 'Completed', 'On Hold', 'Cancelled'), default='Planned')
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    tasks = relationship("EmployeeTaskORM", back_populates="project")


class EmployeeTaskORM(Base):
    __tablename__ = "employee_task"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employee.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    task = Column(String(255), nullable=False)
    assigned_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=True)
    status = Column(Enum("pending", "in_progress", "completed", "blocked"), default="pending")
    priority = Column(Enum("low", "medium", "high", "urgent"), default="medium")
    notes = Column(Text, nullable=True)
    
    employee = relationship("EmployeeORM", back_populates="tasks")
    project = relationship("ProjectORM", back_populates="tasks")


# -------------------- Email Sender Engine --------------------
class EmailSenderEngineORM(Base):
    __tablename__ = "email_sender_engine"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    engine_name = Column(String(100), nullable=False)
    provider = Column(String(30), nullable=False)  # smtp | aws_ses | sendgrid | mailgun
    is_active = Column(Boolean, nullable=False, server_default="1")
    priority = Column(Integer, nullable=False, server_default="1")
    credentials_json = Column(Text, nullable=False)  # Use Text for JSON content compatibility
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


# -------------------- Job Definition --------------------
class JobDefinitionORM(Base):
    __tablename__ = "job_definition"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, server_default="ACTIVE")
    candidate_marketing_id = Column(Integer, ForeignKey("candidate_marketing.id", ondelete="CASCADE"), nullable=False)
    config_json = Column(Text, nullable=True)  # JSON stored as TEXT
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.current_timestamp())

    # Relationships
    candidate_marketing = relationship("CandidateMarketingORM")
    schedules = relationship("JobScheduleORM", back_populates="job_definition", cascade="all, delete-orphan")
    runs = relationship("JobRunORM", back_populates="job_definition")


# -------------------- Job Schedule --------------------
class JobScheduleORM(Base):
    __tablename__ = "job_schedule"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_definition_id = Column(BigInteger, ForeignKey("job_definition.id", ondelete="CASCADE"), nullable=False)
    timezone = Column(String(64), nullable=False, server_default="America/Los_Angeles")
    frequency = Column(String(20), nullable=False)
    interval_value = Column(Integer, nullable=False, server_default="1")
    next_run_at = Column(TIMESTAMP, nullable=False)
    last_run_at = Column(TIMESTAMP, nullable=True)
    lock_token = Column(String(64), nullable=True)
    lock_expires_at = Column(TIMESTAMP, nullable=True)
    enabled = Column(Boolean, nullable=False, server_default="1")
    manually_triggered = Column(Boolean, nullable=False, server_default="0")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.current_timestamp())

    # Relationships
    job_definition = relationship("JobDefinitionORM", back_populates="schedules")
    runs = relationship("JobRunORM", back_populates="job_schedule")


# -------------------- Job Run --------------------
class JobRunORM(Base):
    __tablename__ = "job_run"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_definition_id = Column(BigInteger, ForeignKey("job_definition.id"), nullable=False)
    job_schedule_id = Column(BigInteger, ForeignKey("job_schedule.id"), nullable=False)
    run_status = Column(String(20), nullable=False, server_default="RUNNING")
    started_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())
    finished_at = Column(TIMESTAMP, nullable=True)
    items_total = Column(Integer, server_default="0")
    items_succeeded = Column(Integer, server_default="0")
    items_failed = Column(Integer, server_default="0")
    error_message = Column(Text, nullable=True)
    details_json = Column(Text, nullable=True)  # JSON stored as TEXT

    # Relationships
    job_definition = relationship("JobDefinitionORM", back_populates="runs")
    job_schedule = relationship("JobScheduleORM", back_populates="runs")


# -------------------- Job Request --------------------
class JobRequestORM(Base):
    __tablename__ = "job_request"
    __table_args__ = (
        UniqueConstraint('job_type', 'candidate_marketing_id', 'status', name='uq_jobreq'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_type = Column(String(50), nullable=False)
    candidate_marketing_id = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, server_default="PENDING")
    requested_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())
    processed_at = Column(TIMESTAMP, nullable=True)


# -------------------- Outreach Contact --------------------
class OutreachContactORM(Base):
    __tablename__ = "outreach_contacts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True)
    email_lc = Column(String(255), server_default=FetchedValue(), unique=True)
    source_type = Column(String(50))  # CAMPAIGN | MANUAL | CSV
    source_id = Column(Integer, nullable=True)
    status = Column(String(30), nullable=False, server_default="active")
    unsubscribe_flag = Column(Boolean, nullable=False, server_default="0")
    unsubscribe_at = Column(TIMESTAMP, nullable=True)
    unsubscribe_reason = Column(String(255), nullable=True)
    bounce_flag = Column(Boolean, nullable=False, server_default="0")
    complaint_flag = Column(Boolean, nullable=False, server_default="0")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


class RawPositionORM(Base):
    __tablename__ = "raw_position"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidate.id"), nullable=True)
    source = Column(String(50), nullable=False,
                    comment='linkedin, email, job_board, scraper')
    source_uid = Column(String(255), nullable=True,
                        comment='external job id or message id')
    extracted_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now())
    extractor_version = Column(String(50), nullable=True)
    raw_title = Column(String(500), nullable=True)
    raw_company = Column(String(255), nullable=True)
    raw_location = Column(String(255), nullable=True)
    raw_zip = Column(String(20), nullable=True)
    raw_description = Column(Text, nullable=True)
    raw_contact_info = Column(
        Text, nullable=True, comment='emails, phones, linkedin, free text')
    raw_notes = Column(Text, nullable=True,
                       comment='any additional extractor notes')
    raw_payload = Column(
        JSON, nullable=True, comment='full extractor payload if available')
    processing_status = Column(SQLAEnum(ProcessingStatusEnum),
                               nullable=False, server_default='new')
    error_message = Column(Text, nullable=True)
    processed_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False,
                        server_default=func.now())

    __table_args__ = (
        Index('idx_source_uid', 'source', 'source_uid'),
        Index('idx_processing_status', 'processing_status'),
        Index('idx_extracted_at', 'extracted_at'),
    )


class PositionORM(Base):
    __tablename__ = "position"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    normalized_title = Column(
        String(255), nullable=True, comment='standardized role name')
    company_name = Column(String(255), nullable=False)
    company_id = Column(Integer, nullable=True,
                        comment='future reference to company table')
    position_type = Column(SQLAEnum(PositionTypeEnum), nullable=True)
    employment_mode = Column(SQLAEnum(EmploymentModeEnum), nullable=True)
    source = Column(String(50), nullable=False,
                    comment='linkedin, job_board, vendor, email')
    source_uid = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    zip = Column(String(20), nullable=True)
    country = Column(String(100), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    contact_linkedin = Column(String(255), nullable=True)
    job_url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(SQLAEnum(PositionStatusEnum),
                    nullable=False, server_default='open')
    confidence_score = Column(DECIMAL(
        5, 2), nullable=True, comment='extraction or matching confidence')
    created_from_raw_id = Column(BigInteger, ForeignKey(
        "raw_position.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint('source', 'source_uid', name='uniq_source_job'),
    )
