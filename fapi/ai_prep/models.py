"""
SQLAlchemy ORM Models for AIPrep
================================
Implements V134 DDL Schema (4 primary tables):
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
    Column, Integer, BigInteger, String, Text, Boolean, Float, DateTime,
    ForeignKey, Enum as SQLEnum, JSON, func, CheckConstraint
)
from sqlalchemy.orm import relationship, synonym
from fapi.db.models import Base

# Import single source of truth enums from schemas
from fapi.ai_prep.schemas import (
    AssessmentStatusEnum,
    AssessmentCategoryEnum,
    AssessmentTypeEnum,
    MediaTypeEnum,
    AssessmentMediaTypeEnum,
    DifficultyLevelEnum,
    EngineOperationEnum,
    AnalysisRunStatusEnum,
)


# ==========================================
# 1. Question Bank Model
# ==========================================
class AiPrepQuestionBank(Base):
    __tablename__ = "ai_prep_question_bank"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    category = Column(String(64), nullable=False, index=True)
    subcategory = Column(String(64), nullable=True, index=True)
    sub_category = synonym("subcategory")
    difficulty_level = Column(String(32), nullable=True, default=DifficultyLevelEnum.MEDIUM.value)
    question_text = Column(Text, nullable=False)
    relevant_skills = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), onupdate=datetime.utcnow, nullable=False)


AiPrepQuestionBankORM = AiPrepQuestionBank


# ==========================================
# 2. Assessment Session Model
# ==========================================
class AiPrepAssessment(Base):
    __tablename__ = "ai_prep_assessment"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    candidate_id = Column(BigInteger, nullable=False, index=True)
    assessment_type = Column(String(64), default=AssessmentCategoryEnum.TECHNICAL.value, nullable=False, index=True)
    assessment_mode = Column(String(32), default=MediaTypeEnum.VIDEO.value, nullable=False)
    media_type = synonym("assessment_mode")
    status = Column(String(32), default=AssessmentStatusEnum.IN_PROGRESS.value, nullable=False, index=True)
    job_description = Column(Text, nullable=True)
    youtube_url = Column(String(512), nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), onupdate=datetime.utcnow, nullable=False)

    # Relationships
    assessment_data = relationship("AiPrepAssessmentData", back_populates="assessment", uselist=False, cascade="all, delete-orphan", foreign_keys="[AiPrepAssessmentData.assessment_id]")
    assessment_report = relationship("AiPrepAssessmentReport", back_populates="assessment", uselist=False, cascade="all, delete-orphan", foreign_keys="[AiPrepAssessmentReport.assessment_id]")
    media_files = relationship("AiPrepMediaFile", back_populates="assessment", uselist=False, cascade="all, delete-orphan", foreign_keys="[AiPrepMediaFile.assessment_id]")
    analysis_runs = relationship("AiPrepAnalysisRun", back_populates="assessment", cascade="all, delete-orphan", foreign_keys="[AiPrepAnalysisRun.assessment_id]")

    def __getitem__(self, key):
        if hasattr(self, key):
            val = getattr(self, key)
            if hasattr(val, "value"):
                return val.value
            return val
        raise KeyError(key)

    def __contains__(self, key):
        return hasattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


AiPrepAssessmentORM = AiPrepAssessment


# ==========================================
# 3. Assessment Data Model (Telemetry/Input)
# ==========================================
class AiPrepAssessmentData(Base):
    __tablename__ = "ai_prep_assessment_data"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessment.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    questions = Column(JSON, nullable=True)
    transcript = Column(JSON, nullable=True)
    audio_telemetry = Column(JSON, nullable=True)
    video_telemetry = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), onupdate=datetime.utcnow, nullable=False)

    # Relationship
    assessment = relationship("AiPrepAssessment", back_populates="assessment_data", foreign_keys=[assessment_id])


AiPrepAssessmentDataORM = AiPrepAssessmentData


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
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), onupdate=datetime.utcnow, nullable=False)

    # Relationship
    assessment = relationship("AiPrepAssessment", back_populates="assessment_report", foreign_keys=[assessment_id])


AiPrepAssessmentReportORM = AiPrepAssessmentReport


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
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), onupdate=datetime.utcnow, nullable=False)

    # Relationship
    assessment = relationship("AiPrepAssessment", back_populates="media_files", foreign_keys=[assessment_id])


class AiPrepAnalysisRun(Base):
    __tablename__ = "ai_prep_analysis_runs"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessment.id", ondelete="CASCADE"), nullable=False, index=True)
    run_type = Column(String(64), nullable=False)
    status = Column(String(32), default=AnalysisRunStatusEnum.PENDING.value, nullable=False)
    celery_task_id = Column(String(128), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), onupdate=datetime.utcnow, nullable=False)

    # Relationship
    assessment = relationship("AiPrepAssessment", back_populates="analysis_runs", foreign_keys=[assessment_id])
