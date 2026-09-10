"""Pydantic Schemas and enums for AI Prep Tool.
Strictly derived from Migration V134 DDL — enums match DB ENUM values exactly.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Domain Enums — values match DDL ENUM literals exactly
# ---------------------------------------------------------------------------

class AssessmentCategoryEnum(str, Enum):
    INTRO = "INTRO"
    JD_INTRO = "JD_INTRO"
    RECRUITER = "RECRUITER"
    HIRING_MANAGER = "HIRING_MANAGER"
    SYSTEM_DESIGN = "SYSTEM_DESIGN"
    TECHNICAL = "TECHNICAL"


# Alias used in some places
AssessmentTypeEnum = AssessmentCategoryEnum


class MediaTypeEnum(str, Enum):
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"


# Alias
AssessmentMediaTypeEnum = MediaTypeEnum


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


class EngineOperationEnum(str, Enum):
    START = "START"
    SUBMIT = "SUBMIT"
    CANCEL = "CANCEL"


# ---------------------------------------------------------------------------
# Assessment Types Schemas (Category 1)
# ---------------------------------------------------------------------------

class AssessmentTypeBase(BaseModel):
    code: str = Field(..., description="Unique assessment type code (e.g. INTRO, SYSTEM_DESIGN)")
    title: str = Field(..., description="Display title")
    description: Optional[str] = Field(None, description="Overview of what the assessment covers")
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
    eligible: bool = Field(..., description="True if candidate meets all prerequisites")
    candidate_id: int
    llm_check: LLMKeyStatusResponse
    resume_check: ResumeStatusResponse
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Assessment Execution Schemas (Category 3)
# ---------------------------------------------------------------------------

class CreateAssessmentRequest(BaseModel):
    candidate_id: Optional[int] = Field(None, description="Candidate ID (auto-resolved from session if candidate)")
    assessment_type: AssessmentCategoryEnum = Field(default=AssessmentCategoryEnum.INTRO)
    media_type: MediaTypeEnum = Field(default=MediaTypeEnum.VIDEO)
    job_description: Optional[str] = Field(None, description="Optional JD for tailored assessments")


class CreateAssessmentResponse(BaseModel):
    id: int
    status: str = Field(default="IN_PROGRESS")
    started_at: Optional[datetime] = None
    assessment_type: Optional[str] = None
    media_type: Optional[str] = None
    questions: Optional[List[Dict[str, Any]]] = None

    class Config:
        from_attributes = True


# Alias
AssessmentResponse = CreateAssessmentResponse


class SubmitAssessmentRequest(BaseModel):
    transcript: Optional[Dict[str, Any]] = None
    audio_telemetry: Optional[Dict[str, Any]] = None
    video_telemetry: Optional[Dict[str, Any]] = None
    questions: Optional[List[Dict[str, Any]]] = None


class SubmitAssessmentDataRequest(BaseModel):
    questions: List[Dict[str, Any]] = Field(default_factory=list)
    transcript: Dict[str, Any] = Field(default_factory=dict)
    audio_telemetry: Dict[str, Any] = Field(default_factory=dict)
    video_telemetry: Dict[str, Any] = Field(default_factory=dict)


class SubmitAssessmentDataResponse(BaseModel):
    message: str = "Data saved successfully"


class UpdateMediaURLRequest(BaseModel):
    youtube_url: str = Field(..., description="Public/unlisted video or audio streaming URL")


# Alias
UpdateMediaUrlRequest = UpdateMediaURLRequest


class UpdateMediaURLResponse(BaseModel):
    id: int
    youtube_url: str


class TriggerEvaluationResponse(BaseModel):
    id: int
    status: str = Field(default="EVALUATING")


class AssessmentListItem(BaseModel):
    id: int
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
    items: List[AssessmentListItem] = Field(default_factory=list)
    total: int


class AssessmentDetailResponse(BaseModel):
    id: int
    candidate_id: int
    assessment_type: str
    media_type: str
    status: str
    job_description: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    youtube_url: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    data: Optional[Dict[str, Any]] = None
    report: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Media Ingestion & Chunk Upload Schemas (Category 4)
# ---------------------------------------------------------------------------

class ChunkUploadResponse(BaseModel):
    chunk_number: int
    status: str = "uploaded"
    storage_path: Optional[str] = None
    bytes_written: Optional[int] = None
    total_uploaded: Optional[int] = None
    total_chunks: Optional[int] = None
    is_ready_for_assembly: Optional[bool] = False
    message: Optional[str] = None


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
    total_chunks: int = Field(default=1, ge=1, description="Total number of chunks to assemble")


class AssembleMediaResponse(BaseModel):
    assessment_id: int
    status: str
    assembled_video_path: Optional[str] = None
    extracted_audio_path: Optional[str] = None
    file_size_bytes: Optional[int] = 0
    dispatched_tasks: List[str] = Field(default_factory=list)
    media_path: Optional[str] = None
    audio_path: Optional[str] = None
    message: Optional[str] = None


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
    progress_percentage: Optional[int] = 0
    active_step: Optional[str] = None
    tasks: Dict[str, str] = Field(default_factory=dict)
    youtube_url: Optional[str] = None
    error_message: Optional[str] = None
    step: Optional[str] = None
    progress_pct: Optional[float] = 0.0
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Admin / Question Bank Schemas (Category 6)
# ---------------------------------------------------------------------------

class QuestionCreateRequest(BaseModel):
    category: AssessmentCategoryEnum = Field(..., description="Target assessment category")
    sub_category: Optional[str] = Field(None, description="Optional sub-category (required when category=TECHNICAL)")
    difficulty_level: DifficultyLevelEnum = Field(default=DifficultyLevelEnum.MEDIUM)
    question_text: str = Field(..., description="Question prompt text")
    is_active: bool = Field(default=True)

    @model_validator(mode="after")
    def validate_subcategory(self):
        if self.category == AssessmentCategoryEnum.TECHNICAL and not self.sub_category:
            raise ValueError("sub_category is required when category is TECHNICAL")
        if self.category != AssessmentCategoryEnum.TECHNICAL and self.sub_category is not None:
            self.sub_category = None
        return self


# Alias
QuestionBankCreateRequest = QuestionCreateRequest


class QuestionUpdateRequest(BaseModel):
    category: Optional[AssessmentCategoryEnum] = None
    sub_category: Optional[str] = None
    difficulty_level: Optional[DifficultyLevelEnum] = None
    question_text: Optional[str] = None
    is_active: Optional[bool] = None


# Alias
QuestionBankUpdateRequest = QuestionUpdateRequest


class QuestionResponse(BaseModel):
    id: int
    category: str
    sub_category: Optional[str] = None
    difficulty_level: str
    question_text: str
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Alias
QuestionBankResponse = QuestionResponse


class QuestionListResponse(BaseModel):
    items: List[QuestionResponse] = Field(default_factory=list)
    total: int


# ---------------------------------------------------------------------------
# Assessment Engine & Core Sub-Engine Domain Contracts
# ---------------------------------------------------------------------------

class QuestionItemContract(BaseModel):
    question_id: int
    question_text: str
    category: Optional[str] = None
    sub_category: Optional[str] = None
    difficulty_level: Optional[str] = None


class TranscriptDataContract(BaseModel):
    full_text: str = ""
    segments: List[Dict[str, Any]] = Field(default_factory=list)


class AudioEnginePayload(BaseModel):
    audio_telemetry: Dict[str, Any]


class AudioEngineOutput(BaseModel):
    audio_context: str


class VideoEnginePayload(BaseModel):
    video_telemetry: Dict[str, Any]


class VideoEngineOutput(BaseModel):
    video_context: str


class EvalEnginePayload(BaseModel):
    audio_context: Optional[str] = ""
    video_context: Optional[str] = ""
    qa_context: str


class EvalEnginePromptOutput(BaseModel):
    system_prompt: str
    user_prompt: str
    response_format: str = "json_object"


class ScoresEnginePayload(BaseModel):
    raw_llm_json_string: str


class ParsedReportOutput(BaseModel):
    audio_evaluation: Dict[str, Any] = Field(default_factory=dict)
    video_evaluation: Dict[str, Any] = Field(default_factory=dict)
    transcript_evaluation: Dict[str, Any] = Field(default_factory=dict)


class ScoresEngineOutput(BaseModel):
    is_valid: bool
    parsed_report: Optional[ParsedReportOutput] = None
    error: Optional[str] = None
