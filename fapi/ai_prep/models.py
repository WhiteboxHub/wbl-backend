"""
SQLAlchemy ORM Models for AIPrep
================================
Implements V134 DDL Schema (4 simplified tables):
1. ai_prep_question_bank
2. ai_prep_assessment
3. ai_prep_assessment_data
4. ai_prep_assessment_report

Plus operational models for media and analysis tasks:
- ai_prep_media_files
- ai_prep_analysis_runs
"""
import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, DateTime,
    ForeignKey, Enum as SQLEnum, JSON
)
from sqlalchemy.orm import relationship
from fapi.db.models import Base



# ==========================================
# Enums
# ==========================================
class AssessmentStatusEnum(str, enum.Enum):
    TESTING = "TESTING"
    IN_PROGRESS = "IN_PROGRESS"
    EVALUATING = "EVALUATING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AssessmentTypeEnum(str, enum.Enum):
    TECHNICAL = "TECHNICAL"
    SYSTEM_DESIGN = "SYSTEM_DESIGN"
    BEHAVIORAL = "BEHAVIORAL"
    INTRO = "INTRO"
    GENERAL = "GENERAL"


class AssessmentMediaTypeEnum(str, enum.Enum):
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"
    VIDEO_AUDIO = "VIDEO_AUDIO"


class AnalysisRunStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ==========================================
# 1. Question Bank Model
# ==========================================
class AiPrepQuestionBank(Base):
    __tablename__ = "ai_prep_question_bank"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    category = Column(String(64), nullable=False, index=True)
    subcategory = Column(String(64), nullable=True, index=True)
    difficulty_level = Column(String(32), nullable=True)
    question_text = Column(Text, nullable=False)
    relevant_skills = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# ==========================================
# 2. Assessment Session Model
# ==========================================
class AiPrepAssessment(Base):
    __tablename__ = "ai_prep_assessment"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    candidate_id = Column(Integer, nullable=False, index=True)
    assessment_type = Column(String(64), default=AssessmentTypeEnum.TECHNICAL.value, nullable=False)
    assessment_mode = Column(String(32), default=AssessmentMediaTypeEnum.VIDEO.value, nullable=False)
    status = Column(String(32), default=AssessmentStatusEnum.IN_PROGRESS.value, nullable=False, index=True)
    job_description = Column(Text, nullable=True)
    youtube_url = Column(String(512), nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    assessment_data = relationship("AiPrepAssessmentData", back_populates="assessment", uselist=False, cascade="all, delete-orphan")
    assessment_report = relationship("AiPrepAssessmentReport", back_populates="assessment", uselist=False, cascade="all, delete-orphan")
    media_files = relationship("AiPrepMediaFile", back_populates="assessment", uselist=False, cascade="all, delete-orphan")
    analysis_runs = relationship("AiPrepAnalysisRun", back_populates="assessment", cascade="all, delete-orphan")


# ==========================================
# 3. Assessment Data Model (Telemetry/Input)
# ==========================================
class AiPrepAssessmentData(Base):
    __tablename__ = "ai_prep_assessment_data"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessment.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    questions = Column(JSON, nullable=True)
    transcript = Column(Text, nullable=True)
    audio_telemetry = Column(JSON, nullable=True)
    video_telemetry = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship
    assessment = relationship("AiPrepAssessment", back_populates="assessment_data")


# ==========================================
# 4. Assessment Report Model (LLM Output)
# ==========================================
class AiPrepAssessmentReport(Base):
    __tablename__ = "ai_prep_assessment_report"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessment.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    audio_evaluation = Column(JSON, nullable=True)
    video_evaluation = Column(JSON, nullable=True)
    transcript_evaluation = Column(JSON, nullable=True)
    composite_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship
    assessment = relationship("AiPrepAssessment", back_populates="assessment_report")


# ==========================================
# Operational Support Models
# ==========================================
class AiPrepMediaFile(Base):
    __tablename__ = "ai_prep_media_files"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessment.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    audio_file_path = Column(String(512), nullable=True)
    video_file_path = Column(String(512), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship
    assessment = relationship("AiPrepAssessment", back_populates="media_files")


class AiPrepAnalysisRun(Base):
    __tablename__ = "ai_prep_analysis_runs"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessment.id", ondelete="CASCADE"), nullable=False, index=True)
    run_type = Column(String(64), nullable=False)
    status = Column(String(32), default=AnalysisRunStatusEnum.PENDING.value, nullable=False)
    celery_task_id = Column(String(128), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship
    assessment = relationship("AiPrepAssessment", back_populates="analysis_runs")
