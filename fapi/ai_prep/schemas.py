"""Pydantic Schemas and Master JSON Contracts for AI Prep Tool (Complete 26 Endpoints Suite)."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AssessmentTypeEnum(str, Enum):
    INTRO = "INTRO"
    JD_INTRO = "JD_INTRO"
    RECRUITER = "RECRUITER"
    HIRING_MANAGER = "HIRING_MANAGER"
    SYSTEM_DESIGN = "SYSTEM_DESIGN"
    TECHNICAL = "TECHNICAL"


class MediaTypeEnum(str, Enum):
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"


class AssessmentStatusEnum(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    EVALUATING = "EVALUATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DifficultyLevelEnum(str, Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    EXPERT = "EXPERT"


# ---------------------------------------------------------------------------
# Assessment Types Schemas (Category 1)
# ---------------------------------------------------------------------------

class AssessmentTypeBase(BaseModel):
    code: str = Field(..., description="Unique assessment type code identifier (e.g. INTRO, SYSTEM_DESIGN)")
    title: str = Field(..., description="Display title for the assessment type")
    description: Optional[str] = Field(None, description="Detailed overview of what the assessment covers")
    category: str = Field(default="GENERAL", description="Category grouping")
    time_estimate_mins: int = Field(default=15, description="Estimated duration in minutes")
    is_active: bool = Field(default=True, description="Whether this assessment type is enabled")


class AssessmentTypeCreate(AssessmentTypeBase):
    pass


class AssessmentTypeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    time_estimate_mins: Optional[int] = None
    is_active: Optional[bool] = None


class AssessmentTypeResponse(AssessmentTypeBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AssessmentTypeListResponse(BaseModel):
    items: List[AssessmentTypeResponse]
    total: int


# ---------------------------------------------------------------------------
# Pre-Flight Readiness Schemas (Category 2)
# ---------------------------------------------------------------------------

class LLMKeyStatusResponse(BaseModel):
    status: str = Field(..., description="'valid' or 'failure'")
    is_configured: bool = Field(..., description="True if a valid LLM key is ready")
    provider: Optional[str] = None
    model: Optional[str] = None
    voice_enabled: bool = False
    message: Optional[str] = None
    available_models: List[str] = Field(default_factory=list)


class ResumeStatusResponse(BaseModel):
    status: str = Field(..., description="'valid' or 'failure'")
    has_resume: bool = Field(..., description="Whether candidate has a resume on file")
    has_parsed_json: bool = Field(..., description="Whether structured JSON is parsed")
    candidate_name: Optional[str] = None
    current_title: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    message: Optional[str] = None


class PreAssessmentCheckResponse(BaseModel):
    eligible: bool = Field(..., description="True if candidate meets all prerequisites to start assessment")
    candidate_id: int
    llm_check: LLMKeyStatusResponse
    resume_check: ResumeStatusResponse
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Assessment Execution Schemas (Category 3)
# ---------------------------------------------------------------------------

class CreateAssessmentRequest(BaseModel):
    candidate_id: Optional[int] = Field(None, description="Candidate ID (auto-resolved from session if candidate)")
    assessment_type: AssessmentTypeEnum = Field(default=AssessmentTypeEnum.INTRO, description="Assessment type code")
    media_type: MediaTypeEnum = Field(default=MediaTypeEnum.VIDEO, description="Recording media mode")
    job_description: Optional[str] = Field(None, description="Optional job description for tailored assessments")


class CreateAssessmentResponse(BaseModel):
    id: int
    assessment_uuid: Optional[str] = None
    status: str = Field(default="IN_PROGRESS")
    started_at: datetime
    assessment_type: Optional[str] = None
    media_type: Optional[str] = None
    questions: Optional[List[Dict[str, Any]]] = None

    class Config:
        from_attributes = True


class SubmitAssessmentRequest(BaseModel):
    transcript: Optional[Dict[str, Any]] = None
    audio_telemetry: Optional[Dict[str, Any]] = None
    video_telemetry: Optional[Dict[str, Any]] = None
    questions: Optional[List[Dict[str, Any]]] = None


class SubmitAssessmentDataRequest(BaseModel):
    questions: List[Dict[str, Any]] = Field(..., description="List of questions answered")
    transcript: Dict[str, Any] = Field(..., description="Transcript payload with full_text and segments")
    audio_telemetry: Dict[str, Any] = Field(..., description="Audio metrics: words_per_minute, silence_ratio_pct, etc.")
    video_telemetry: Dict[str, Any] = Field(..., description="Video metrics: face_visible_pct, head_nods_count, etc.")


class SubmitAssessmentDataResponse(BaseModel):
    message: str = "Data saved successfully"


class UpdateMediaURLRequest(BaseModel):
    youtube_url: str = Field(..., description="Public/unlisted video or audio streaming URL")


class UpdateMediaURLResponse(BaseModel):
    id: int
    youtube_url: str


class TriggerEvaluationResponse(BaseModel):
    id: int
    status: str = Field(default="EVALUATING")


class AssessmentListItem(BaseModel):
    id: int
    assessment_uuid: Optional[str] = None
    candidate_id: Optional[int] = None
    assessment_type: str
    media_type: str
    status: str
    youtube_url: Optional[str] = None
    started_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AssessmentListResponse(BaseModel):
    items: List[AssessmentListItem]
    total: int


class AssessmentDetailResponse(BaseModel):
    id: int
    assessment_uuid: Optional[str] = None
    candidate_id: int
    assessment_type: str
    media_type: str
    status: str
    job_description: Optional[str] = None
    youtube_url: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    data: Optional[Dict[str, Any]] = None
    report: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Media Ingestion & BE2 Chunk Upload Schemas (Category 4)
# ---------------------------------------------------------------------------

class ChunkUploadResponse(BaseModel):
    success: bool
    assessment_id: int
    chunk_number: int
    bytes_written: int
    total_uploaded: int
    is_ready_for_assembly: bool
    message: str


class ChunkStatusResponse(BaseModel):
    assessment_id: int
    total_chunks: Optional[int] = None
    total_chunks_expected: Optional[int] = None
    uploaded_chunks: List[int] = Field(default_factory=list)
    uploaded_chunks_count: int = 0
    uploaded_chunk_numbers: List[int] = Field(default_factory=list)
    missing_chunks: List[int] = Field(default_factory=list)
    missing_chunk_numbers: List[int] = Field(default_factory=list)
    is_complete: bool = False
    is_ready_for_assembly: bool = False


class AssembleMediaRequest(BaseModel):
    total_chunks: int = Field(default=1, description="Expected total number of chunks")


class AssembleMediaResponse(BaseModel):
    success: bool
    assessment_id: int
    status: str
    media_path: Optional[str] = None
    audio_path: Optional[str] = None
    message: str


class LocalMediaUploadResponse(BaseModel):
    success: bool
    assessment_id: int
    file_path: str
    media_type: str
    message: str


class StorageInfoResponse(BaseModel):
    storage_dir: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    assessment_count: int


# ---------------------------------------------------------------------------
# Progress & SSE Streaming Schemas (Category 5)
# ---------------------------------------------------------------------------

class ProcessingStatusResponse(BaseModel):
    assessment_id: int
    status: str
    step: Optional[str] = None
    progress_pct: Optional[float] = 0.0
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Admin / Question Bank Schemas (Category 6)
# ---------------------------------------------------------------------------

class QuestionCreateRequest(BaseModel):
    category: AssessmentTypeEnum = Field(..., description="Target assessment category")
    sub_category: Optional[str] = Field(None, description="Optional subcategory / topic")
    difficulty_level: DifficultyLevelEnum = Field(default=DifficultyLevelEnum.MEDIUM, description="Difficulty rating")
    question_text: str = Field(..., description="Question prompt text")
    ideal_answer_rubric: Optional[str] = Field(None, description="Evaluation rubric guidelines")
    is_active: bool = Field(default=True, description="Whether question is active")


class QuestionUpdateRequest(BaseModel):
    category: Optional[AssessmentTypeEnum] = None
    sub_category: Optional[str] = None
    difficulty_level: Optional[DifficultyLevelEnum] = None
    question_text: Optional[str] = None
    ideal_answer_rubric: Optional[str] = None
    is_active: Optional[bool] = None


class QuestionResponse(BaseModel):
    id: int
    category: str
    sub_category: Optional[str] = None
    difficulty_level: str
    question_text: str
    ideal_answer_rubric: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class QuestionListResponse(BaseModel):
    items: List[QuestionResponse]
    total: int
