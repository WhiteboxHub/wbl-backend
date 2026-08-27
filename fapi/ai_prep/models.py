from datetime import datetime
import enum
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime,
    ForeignKey, JSON, Numeric, BigInteger, Enum as SQLEnum, CheckConstraint, Index
)
from sqlalchemy.orm import relationship
from fapi.db.models import Base, CandidateORM


# ----------------------------------------------------------------------
# Enums
# ----------------------------------------------------------------------
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
    PAUSED = "PAUSED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class QuestionCategoryEnum(str, enum.Enum):
    TECHNICAL = "TECHNICAL"
    SYSTEM_DESIGN = "SYSTEM_DESIGN"
    BEHAVIORAL = "BEHAVIORAL"
    RECRUITER = "RECRUITER"
    HIRING_MANAGER = "HIRING_MANAGER"
    GENERAL = "GENERAL"


class DifficultyLevelEnum(str, enum.Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    EXPERT = "EXPERT"


QuestionDifficultyEnum = DifficultyLevelEnum


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


class RunTypeEnum(str, enum.Enum):
    STT = "STT"
    AUDIO = "AUDIO"
    VISION = "VISION"
    LLM = "LLM"
    YOUTUBE_UPLOAD = "YOUTUBE_UPLOAD"
    FULL = "FULL"


AnalysisRunTypeEnum = RunTypeEnum


class RunStatusEnum(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


AnalysisRunStatusEnum = RunStatusEnum


class DeletionRequestStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ----------------------------------------------------------------------
# 1. Candidate Resume Table
# ----------------------------------------------------------------------
class CandidateResume(Base):
    __tablename__ = "candidate_resumes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False)
    resume_file_path = Column(String(512), nullable=True)
    parsed_json = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    assessments = relationship("AiPrepAssessmentORM", back_populates="candidate_resume")


CandidateResumeORM = CandidateResume


# ----------------------------------------------------------------------
# 2. Question Bank
# ----------------------------------------------------------------------
class AiPrepQuestionBankORM(Base):
    __tablename__ = "ai_prep_question_bank"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(SQLEnum(QuestionCategoryEnum), nullable=False)
    sub_category = Column(String(100), nullable=False)
    difficulty_level = Column(SQLEnum(DifficultyLevelEnum), nullable=False, default=DifficultyLevelEnum.MEDIUM)
    question_text = Column(Text, nullable=False)
    ideal_answer_rubric = Column(Text, nullable=True)
    relevant_skills_json = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    assessment_questions = relationship("AiPrepAssessmentQuestionORM", back_populates="question")

    __table_args__ = (
        Index("idx_qb_category_diff", "category", "difficulty_level"),
        Index("idx_qb_active", "is_active"),
    )


AiPrepQuestionBank = AiPrepQuestionBankORM


# ----------------------------------------------------------------------
# 3. Assessments
# ----------------------------------------------------------------------
class AiPrepAssessmentORM(Base):
    __tablename__ = "ai_prep_assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False)
    candidate_resume_id = Column(Integer, ForeignKey("candidate_resumes.id", ondelete="SET NULL"), nullable=True)
    assessment_type = Column(SQLEnum(AssessmentTypeEnum), nullable=False)
    assessment_mode = Column(SQLEnum(AssessmentModeEnum), nullable=False, default=AssessmentModeEnum.VIDEO_AUDIO)
    status = Column(SQLEnum(AssessmentStatusEnum), nullable=False, default=AssessmentStatusEnum.TESTING)
    attempt_number = Column(Integer, nullable=False, default=1)
    job_description_text = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    candidate = relationship("CandidateORM", foreign_keys=[candidate_id], lazy="joined")
    candidate_resume = relationship("CandidateResume", back_populates="assessments")
    questions = relationship("AiPrepAssessmentQuestionORM", back_populates="assessment", cascade="all, delete-orphan")
    hardware_checks = relationship("AiPrepHardwareCheckORM", back_populates="assessment", cascade="all, delete-orphan")
    media_files = relationship("AiPrepMediaFileORM", back_populates="assessment", cascade="all, delete-orphan")
    transcripts = relationship("AiPrepTranscriptORM", back_populates="assessment", cascade="all, delete-orphan")
    vision_telemetry = relationship("AiPrepVisionTelemetryORM", back_populates="assessment", cascade="all, delete-orphan")
    audio_telemetry = relationship("AiPrepAudioTelemetryORM", back_populates="assessment", cascade="all, delete-orphan")
    report = relationship("AiPrepReportORM", back_populates="assessment", uselist=False, cascade="all, delete-orphan")
    share_grants = relationship("AiPrepShareGrantORM", back_populates="assessment", cascade="all, delete-orphan")
    analysis_runs = relationship("AiPrepAnalysisRunORM", back_populates="assessment", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_ass_candidate", "candidate_id"),
        Index("idx_ass_status", "status"),
        Index("idx_ass_type", "assessment_type"),
    )


AiPrepAssessment = AiPrepAssessmentORM


# ----------------------------------------------------------------------
# 4. Assessment Questions Join Table
# ----------------------------------------------------------------------
class AiPrepAssessmentQuestionORM(Base):
    __tablename__ = "ai_prep_assessment_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("ai_prep_question_bank.id", ondelete="RESTRICT"), nullable=False)
    order_index = Column(Integer, nullable=False, default=1)
    candidate_answer_transcript = Column(Text, nullable=True)
    question_score = Column(Integer, nullable=True)
    feedback_text = Column(Text, nullable=True)

    assessment = relationship("AiPrepAssessmentORM", back_populates="questions")
    question = relationship("AiPrepQuestionBankORM", back_populates="assessment_questions")

    __table_args__ = (
        CheckConstraint("question_score IS NULL OR (question_score >= 0 AND question_score <= 100)", name="chk_aq_score"),
        Index("idx_aq_assessment", "assessment_id"),
        Index("idx_aq_question", "question_id"),
    )


AiPrepAssessmentQuestion = AiPrepAssessmentQuestionORM


# ----------------------------------------------------------------------
# 5. Hardware Checks Table
# ----------------------------------------------------------------------
class AiPrepHardwareCheckORM(Base):
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

    assessment = relationship("AiPrepAssessmentORM", back_populates="hardware_checks")

    __table_args__ = (
        Index("idx_hw_assessment", "assessment_id"),
    )


AiPrepHardwareCheck = AiPrepHardwareCheckORM


# ----------------------------------------------------------------------
# 6. Media Files Table
# ----------------------------------------------------------------------
class AiPrepMediaFileORM(Base):
    __tablename__ = "ai_prep_media_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id", ondelete="CASCADE"), nullable=False)
    audio_file_path = Column(String(512), nullable=False)
    video_file_path = Column(String(512), nullable=True)
    duration_seconds = Column(Integer, nullable=False, default=0)
    file_size_bytes = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    assessment = relationship("AiPrepAssessmentORM", back_populates="media_files")

    __table_args__ = (
        Index("idx_media_assessment", "assessment_id"),
    )


AiPrepMediaFile = AiPrepMediaFileORM


# ----------------------------------------------------------------------
# 7. Transcripts Table
# ----------------------------------------------------------------------
class AiPrepTranscriptORM(Base):
    __tablename__ = "ai_prep_transcripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id", ondelete="CASCADE"), nullable=False)
    transcript_text = Column(Text, nullable=False)
    word_timestamps_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    assessment = relationship("AiPrepAssessmentORM", back_populates="transcripts")

    __table_args__ = (
        Index("idx_tx_assessment", "assessment_id"),
    )


AiPrepTranscript = AiPrepTranscriptORM


# ----------------------------------------------------------------------
# 8. Vision Telemetry Table
# ----------------------------------------------------------------------
class AiPrepVisionTelemetryORM(Base):
    __tablename__ = "ai_prep_vision_telemetry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id", ondelete="CASCADE"), nullable=False)
    face_visible_pct = Column(Numeric(5, 2), nullable=False, default=0.00)
    head_nods_count = Column(Integer, nullable=False, default=0)
    frame_stability_score = Column(Numeric(5, 2), nullable=False, default=0.00)
    snapshots_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    assessment = relationship("AiPrepAssessmentORM", back_populates="vision_telemetry")

    __table_args__ = (
        CheckConstraint("face_visible_pct >= 0.00 AND face_visible_pct <= 100.00", name="chk_vision_face_pct"),
        CheckConstraint("frame_stability_score >= 0.00 AND frame_stability_score <= 100.00", name="chk_vision_stability"),
        Index("idx_vision_assessment", "assessment_id"),
    )


AiPrepVisionTelemetry = AiPrepVisionTelemetryORM


# ----------------------------------------------------------------------
# 9. Audio Telemetry Table
# ----------------------------------------------------------------------
class AiPrepAudioTelemetryORM(Base):
    __tablename__ = "ai_prep_audio_telemetry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id", ondelete="CASCADE"), nullable=False)
    avg_volume_db = Column(Numeric(5, 2), nullable=False, default=0.00)
    background_noise_level = Column(SQLEnum(BackgroundNoiseLevelEnum), nullable=False, default=BackgroundNoiseLevelEnum.LOW)
    clipping_detected = Column(Boolean, nullable=False, default=False)
    silence_ratio_pct = Column(Numeric(5, 2), nullable=False, default=0.00)
    filler_words_per_min = Column(Integer, nullable=False, default=0)
    speaking_pace_wpm = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    assessment = relationship("AiPrepAssessmentORM", back_populates="audio_telemetry")

    __table_args__ = (
        CheckConstraint("silence_ratio_pct >= 0.00 AND silence_ratio_pct <= 100.00", name="chk_audio_silence"),
        Index("idx_audio_assessment", "assessment_id"),
    )


AiPrepAudioTelemetry = AiPrepAudioTelemetryORM


# ----------------------------------------------------------------------
# 10. Reports Table
# ----------------------------------------------------------------------
class AiPrepReportORM(Base):
    __tablename__ = "ai_prep_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id", ondelete="CASCADE"), unique=True, nullable=False)
    overall_score = Column(Integer, nullable=False)
    coaching_band = Column(SQLEnum(CoachingBandEnum), nullable=False)
    formula_explanation = Column(String(255), default="(AI_Eng*0.40)+(Core_Eng*0.30)+(Non_Tech*0.20)+(Biz*0.10)")
    scores_breakdown_json = Column(JSON, nullable=False)
    technical_analysis_json = Column(JSON, nullable=False)
    non_technical_analysis_json = Column(JSON, nullable=False)
    coaching_suggestions_json = Column(JSON, nullable=True)
    signal_timeline_json = Column(JSON, nullable=True)
    transcript_evidence_json = Column(JSON, nullable=True)
    gaps_to_validate_json = Column(JSON, nullable=True)
    improvements_json = Column(JSON, nullable=True)
    raw_llm_response_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    assessment = relationship("AiPrepAssessmentORM", back_populates="report")

    __table_args__ = (
        CheckConstraint("overall_score >= 0 AND overall_score <= 100", name="chk_rep_score"),
    )


AiPrepReport = AiPrepReportORM


# ----------------------------------------------------------------------
# 11. Privacy Consents Table (immutable audit log)
# ----------------------------------------------------------------------
class AiPrepConsentORM(Base):
    __tablename__ = "ai_prep_consents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False)
    consent_type = Column(SQLEnum(ConsentTypeEnum), nullable=False)
    consented = Column(Boolean, nullable=False, default=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    consented_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_consent_candidate_type", "candidate_id", "consent_type"),
    )


AiPrepConsent = AiPrepConsentORM


# ----------------------------------------------------------------------
# 12. Share Grants Table
# ----------------------------------------------------------------------
class AiPrepShareGrantORM(Base):
    __tablename__ = "ai_prep_share_grants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id", ondelete="CASCADE"), nullable=False)
    shared_by_candidate_id = Column(Integer, ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False)
    share_token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    assessment = relationship("AiPrepAssessmentORM", back_populates="share_grants")

    __table_args__ = (
        Index("idx_share_assessment", "assessment_id"),
    )


AiPrepShareGrant = AiPrepShareGrantORM


# ----------------------------------------------------------------------
# 13. Deletion Requests Table
# ----------------------------------------------------------------------
class AiPrepDeletionRequestORM(Base):
    __tablename__ = "ai_prep_deletion_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False)
    requested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(SQLEnum(DeletionRequestStatusEnum), nullable=False, default=DeletionRequestStatusEnum.PENDING)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_del_candidate", "candidate_id"),
    )


AiPrepDeletionRequest = AiPrepDeletionRequestORM


# ----------------------------------------------------------------------
# 14. Audit Events Table
# ----------------------------------------------------------------------
class AiPrepAuditEventORM(Base):
    __tablename__ = "ai_prep_audit_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidate.id", ondelete="SET NULL"), nullable=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(100), nullable=False)
    actor_id = Column(Integer, nullable=True)
    actor_role = Column(String(50), nullable=True)
    details_json = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_audit_candidate", "candidate_id"),
        Index("idx_audit_assessment", "assessment_id"),
        Index("idx_audit_event_type", "event_type"),
        Index("idx_audit_created", "created_at"),
    )


AiPrepAuditEvent = AiPrepAuditEventORM


# ----------------------------------------------------------------------
# 15. Analysis Runs Table (Celery Task Execution History)
# ----------------------------------------------------------------------
class AiPrepAnalysisRunORM(Base):
    __tablename__ = "ai_prep_analysis_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("ai_prep_assessments.id", ondelete="CASCADE"), nullable=False)
    run_type = Column(SQLEnum(RunTypeEnum), nullable=False)
    status = Column(SQLEnum(RunStatusEnum), nullable=False, default=RunStatusEnum.QUEUED)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    celery_task_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    assessment = relationship("AiPrepAssessmentORM", back_populates="analysis_runs")

    __table_args__ = (
        Index("idx_run_assessment", "assessment_id"),
        Index("idx_run_status", "status"),
    )


AiPrepAnalysisRun = AiPrepAnalysisRunORM
