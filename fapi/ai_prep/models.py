import enum
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, Integer, String, Enum as SQLAEnum, DateTime, Boolean,
    Float, BigInteger, Text, ForeignKey, JSON
)
from sqlalchemy.orm import relationship

# Base import from central database model module to bind with SQLAlchemy Metadata
from fapi.db.models import Base


# =====================================================================
# 1. AIPREP ENUMS
# =====================================================================

class QuestionCategoryEnum(str, enum.Enum):
    TECHNICAL = "TECHNICAL"
    SYSTEM_DESIGN = "SYSTEM_DESIGN"
    BEHAVIORAL = "BEHAVIORAL"
    RECRUITER = "RECRUITER"
    HIRING_MANAGER = "HIRING_MANAGER"
    GENERAL = "GENERAL"


class QuestionDifficultyEnum(str, enum.Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    EXPERT = "EXPERT"


class AssessmentTypeEnum(str, enum.Enum):
    GENERAL_INTRO = "GENERAL_INTRO"
    JOB_DESCRIPTION_INTRO = "JOB_DESCRIPTION_INTRO"
    RECRUITER = "RECRUITER"
    HIRING_MANAGER = "HIRING_MANAGER"
    TECHNICAL = "TECHNICAL"
    SYSTEM_DESIGN = "SYSTEM_DESIGN"
    HR = "HR"


class AssessmentModeEnum(str, enum.Enum):
    VIDEO_AUDIO = "VIDEO_AUDIO"
    AUDIO_ONLY = "AUDIO_ONLY"


class AssessmentStatusEnum(str, enum.Enum):
    TESTING = "TESTING"
    IN_PROGRESS = "IN_PROGRESS"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BackgroundNoiseLevelEnum(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class CoachingBandEnum(str, enum.Enum):
    EXCELLENT = "EXCELLENT"
    STRONG = "STRONG"
    DEVELOPING = "DEVELOPING"
    NEEDS_WORK = "NEEDS_WORK"


class ConsentTypeEnum(str, enum.Enum):
    VIDEO_ANALYTICS = "VIDEO_ANALYTICS"
    DATA_RETENTION = "DATA_RETENTION"
    TERMS_OF_SERVICE = "TERMS_OF_SERVICE"


class DeletionRequestStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AnalysisRunTypeEnum(str, enum.Enum):
    STT = "STT"
    AUDIO = "AUDIO"
    VISION = "VISION"
    LLM = "LLM"
    FULL = "FULL"


class AnalysisRunStatusEnum(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# =====================================================================
# 2. AIPREP SQLALCHEMY ORM MODELS (14 TABLES)
# =====================================================================


# 1. Candidate Resume Table
class CandidateResume(Base):
    __tablename__ = "candidate_resumes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False)
    resume_file_path = Column(String(512), nullable=True)
    parsed_json = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    assessments = relationship("AiPrepAssessment", back_populates="candidate_resume")


# 2. Question Bank Table
class AiPrepQuestionBank(Base):
    __tablename__ = "ai_prep_question_bank"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(SQLAEnum(QuestionCategoryEnum), nullable=False)
    sub_category = Column(String(100), nullable=False)
    difficulty_level = Column(SQLAEnum(QuestionDifficultyEnum), nullable=False, default=QuestionDifficultyEnum.MEDIUM)
    question_text = Column(Text, nullable=False)
    ideal_answer_rubric = Column(Text, nullable=True)
    relevant_skills_json = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    assessment_questions = relationship("AiPrepAssessmentQuestion", back_populates="question")


# 3. Assessment Sessions Table
class AiPrepAssessment(Base):
    __tablename__ = "ai_prep_assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False)
    candidate_resume_id = Column(Integer, ForeignKey("candidate_resumes.id", ondelete="SET NULL"), nullable=True)
    assessment_type = Column(SQLAEnum(AssessmentTypeEnum), nullable=False)
    assessment_mode = Column(SQLAEnum(AssessmentModeEnum), nullable=False, default=AssessmentModeEnum.VIDEO_AUDIO)
    status = Column(SQLAEnum(AssessmentStatusEnum), nullable=False, default=AssessmentStatusEnum.TESTING)
    attempt_number = Column(Integer, nullable=False, default=1)
    job_description_text = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    candidate_resume = relationship("CandidateResume", back_populates="assessments")
    questions = relationship("AiPrepAssessmentQuestion", back_populates="assessment", cascade="all, delete-orphan")
    hardware_checks = relationship("AiPrepHardwareCheck", back_populates="assessment", cascade="all, delete-orphan")
    media_files = relationship("AiPrepMediaFile", back_populates="assessment", cascade="all, delete-orphan")
    transcripts = relationship("AiPrepTranscript", back_populates="assessment", cascade="all, delete-orphan")
    vision_telemetry = relationship("AiPrepVisionTelemetry", back_populates="assessment", cascade="all, delete-orphan")
    audio_telemetry = relationship("AiPrepAudioTelemetry", back_populates="assessment", cascade="all, delete-orphan")
    report = relationship("AiPrepReport", back_populates="assessment", uselist=False, cascade="all, delete-orphan")
    share_grants = relationship("AiPrepShareGrant", back_populates="assessment", cascade="all, delete-orphan")
    analysis_runs = relationship("AiPrepAnalysisRun", back_populates="assessment", cascade="all, delete-orphan")


# 4. Assessment Questions Join Table
class AiPrepAssessmentQuestion(Base):
    __tablename__ = "ai_prep_assessment_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("ai_prep_question_bank.id", ondelete="RESTRICT"), nullable=False)
    order_index = Column(Integer, nullable=False)

    assessment = relationship("AiPrepAssessment", back_populates="questions")
    question = relationship("AiPrepQuestionBank", back_populates="assessment_questions")


# 5. Hardware Checks Table
class AiPrepHardwareCheck(Base):
    __tablename__ = "ai_prep_hardware_checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id", ondelete="CASCADE"), nullable=False)
    browser_info = Column(String(255), nullable=True)
    os_info = Column(String(255), nullable=True)
    camera_permission = Column(Boolean, nullable=False, default=False)
    mic_permission = Column(Boolean, nullable=False, default=False)
    speaker_ok = Column(Boolean, nullable=False, default=False)
    bandwidth_kbps = Column(Integer, nullable=False, default=0)
    yolo_model_enabled = Column(Boolean, nullable=False, default=False)
    tested_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    assessment = relationship("AiPrepAssessment", back_populates="hardware_checks")


# 6. Media Files Table
class AiPrepMediaFile(Base):
    __tablename__ = "ai_prep_media_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id", ondelete="CASCADE"), nullable=False)
    audio_file_path = Column(String(512), nullable=False)
    video_file_path = Column(String(512), nullable=True)
    duration_seconds = Column(Integer, nullable=False, default=0)
    file_size_bytes = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    assessment = relationship("AiPrepAssessment", back_populates="media_files")


# 7. Transcripts Table
class AiPrepTranscript(Base):
    __tablename__ = "ai_prep_transcripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id", ondelete="CASCADE"), nullable=False)
    transcript_text = Column(Text, nullable=False)
    word_timestamps_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    assessment = relationship("AiPrepAssessment", back_populates="transcripts")


# 8. Vision Telemetry Table
class AiPrepVisionTelemetry(Base):
    __tablename__ = "ai_prep_vision_telemetry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id", ondelete="CASCADE"), nullable=False)
    face_visible_pct = Column(Float, nullable=False, default=0.0)
    head_nods_count = Column(Integer, nullable=False, default=0)
    frame_stability_score = Column(Float, nullable=False, default=0.0)
    snapshots_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    assessment = relationship("AiPrepAssessment", back_populates="vision_telemetry")


# 9. Audio Telemetry Table
class AiPrepAudioTelemetry(Base):
    __tablename__ = "ai_prep_audio_telemetry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id", ondelete="CASCADE"), nullable=False)
    avg_volume_db = Column(Float, nullable=False, default=0.0)
    background_noise_level = Column(SQLAEnum(BackgroundNoiseLevelEnum), nullable=False, default=BackgroundNoiseLevelEnum.LOW)
    clipping_detected = Column(Boolean, nullable=False, default=False)
    silence_ratio_pct = Column(Float, nullable=False, default=0.0)
    filler_words_per_min = Column(Integer, nullable=False, default=0)
    speaking_pace_wpm = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    assessment = relationship("AiPrepAssessment", back_populates="audio_telemetry")


# 10. Reports Table
class AiPrepReport(Base):
    __tablename__ = "ai_prep_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id", ondelete="CASCADE"), nullable=False, unique=True)
    overall_score = Column(Integer, nullable=False)
    coaching_band = Column(SQLAEnum(CoachingBandEnum), nullable=False)
    formula_explanation = Column(Text, nullable=True)
    scores_breakdown_json = Column(JSON, nullable=False)
    technical_analysis_json = Column(JSON, nullable=False)
    non_technical_analysis_json = Column(JSON, nullable=False)
    coaching_suggestions_json = Column(JSON, nullable=True)
    signal_timeline_json = Column(JSON, nullable=True)
    transcript_evidence_json = Column(JSON, nullable=True)
    gaps_to_validate_json = Column(JSON, nullable=True)
    improvements_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    assessment = relationship("AiPrepAssessment", back_populates="report")


# 11. Privacy Consents Table
class AiPrepConsent(Base):
    __tablename__ = "ai_prep_consents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False)
    consent_type = Column(SQLAEnum(ConsentTypeEnum), nullable=False)
    consented = Column(Boolean, nullable=False, default=True)
    consented_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)


# 12. Share Grants Table
class AiPrepShareGrant(Base):
    __tablename__ = "ai_prep_share_grants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id", ondelete="CASCADE"), nullable=False)
    shared_by_candidate_id = Column(Integer, ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False)
    share_token = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    assessment = relationship("AiPrepAssessment", back_populates="share_grants")


# 13. Deletion Requests Table
class AiPrepDeletionRequest(Base):
    __tablename__ = "ai_prep_deletion_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False)
    requested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(SQLAEnum(DeletionRequestStatusEnum), nullable=False, default=DeletionRequestStatusEnum.PENDING)
    notes = Column(Text, nullable=True)


# 14. Audit Events Table
class AiPrepAuditEvent(Base):
    __tablename__ = "ai_prep_audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(100), nullable=False)
    candidate_id = Column(Integer, ForeignKey("candidate.id", ondelete="SET NULL"), nullable=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id", ondelete="SET NULL"), nullable=True)
    actor_id = Column(Integer, nullable=True)
    actor_role = Column(String(50), nullable=True)
    details_json = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# 15. Analysis Runs Table
class AiPrepAnalysisRun(Base):
    __tablename__ = "ai_prep_analysis_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id", ondelete="CASCADE"), nullable=False)
    run_type = Column(SQLAEnum(AnalysisRunTypeEnum), nullable=False)
    status = Column(SQLAEnum(AnalysisRunStatusEnum), nullable=False, default=AnalysisRunStatusEnum.QUEUED)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    celery_task_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    assessment = relationship("AiPrepAssessment", back_populates="analysis_runs")
