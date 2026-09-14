"""Pydantic Schemas and Master JSON Contracts for AI Prep Tool.
Fully compatible with Master Contracts and aiprep-backend branch.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

AssessmentCategoryEnum = Enum(
    "AssessmentCategoryEnum",
    {
        "INTRO": "INTRO",
        "JD_INTRO": "JD_INTRO",
        "RECRUITER": "RECRUITER",
        "HIRING_MANAGER": "HIRING_MANAGER",
        "SYSTEM_DESIGN": "SYSTEM_DESIGN",
        "TECHNICAL": "TECHNICAL",
    },
    type=str,
)

AssessmentTypeEnum = AssessmentCategoryEnum

MediaTypeEnum = Enum(
    "MediaTypeEnum",
    {
        "VIDEO": "VIDEO",
        "AUDIO": "AUDIO",
    },
    type=str,
)

AssessmentMediaTypeEnum = MediaTypeEnum

AssessmentStatusEnum = Enum(
    "AssessmentStatusEnum",
    {
        "IN_PROGRESS": "IN_PROGRESS",
        "EVALUATING": "EVALUATING",
        "COMPLETED": "COMPLETED",
        "FAILED": "FAILED",
    },
    type=str,
)

DifficultyLevelEnum = Enum(
    "DifficultyLevelEnum",
    {
        "EASY": "EASY",
        "MEDIUM": "MEDIUM",
        "HARD": "HARD",
        "EXPERT": "EXPERT",
    },
    type=str,
)

EngineOperationEnum = Enum(
    "EngineOperationEnum",
    {
        "START": "START",
        "SUBMIT": "SUBMIT",
        "CANCEL": "CANCEL",
    },
    type=str,
)


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
    assessment_type: AssessmentCategoryEnum = Field(default=AssessmentCategoryEnum.INTRO, description="Assessment type code")
    media_type: MediaTypeEnum = Field(default=MediaTypeEnum.VIDEO, description="Recording media mode")
    job_description: Optional[str] = Field(None, description="Optional job description for tailored assessments")


class CreateAssessmentResponse(BaseModel):
    id: int
    assessment_uuid: Optional[str] = None
    status: str = Field(default="IN_PROGRESS")
    started_at: Optional[datetime] = None
    assessment_type: Optional[str] = None
    media_type: Optional[str] = None
    job_description: Optional[str] = None
    youtube_url: Optional[str] = None
    questions: Optional[List[Dict[str, Any]]] = None

    class Config:
        from_attributes = True


AssessmentResponse = CreateAssessmentResponse


class SubmitAssessmentRequest(BaseModel):
    transcript: Optional[Dict[str, Any]] = None
    audio_telemetry: Optional[Dict[str, Any]] = None
    video_telemetry: Optional[Dict[str, Any]] = None
    questions: Optional[List[Dict[str, Any]]] = None


class SubmitAssessmentDataRequest(BaseModel):
    questions: List[Dict[str, Any]] = Field(default_factory=list, description="List of questions answered")
    transcript: Dict[str, Any] = Field(default_factory=dict, description="Transcript payload with full_text and segments")
    audio_telemetry: Dict[str, Any] = Field(default_factory=dict, description="Audio metrics: words_per_minute, silence_ratio_pct, etc.")
    video_telemetry: Dict[str, Any] = Field(default_factory=dict, description="Video metrics: face_visible_pct, head_nods_count, etc.")


class SubmitAssessmentDataResponse(BaseModel):
    message: str = "Data saved successfully"


class UpdateMediaURLRequest(BaseModel):
    youtube_url: str = Field(..., description="Public/unlisted video or audio streaming URL")


UpdateMediaUrlRequest = UpdateMediaURLRequest


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
    job_description: Optional[str] = None
    youtube_url: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AssessmentListResponse(BaseModel):
    items: List[AssessmentListItem] = Field(default_factory=list)
    total: int


class AssessmentDetailResponse(BaseModel):
    id: int
    assessment_uuid: Optional[str] = None
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


class AssessmentDataResponse(BaseModel):
    id: Optional[int] = None
    assessment_id: int
    questions: Optional[List[Dict[str, Any]]] = None
    transcript: Optional[Dict[str, Any]] = None
    audio_telemetry: Optional[Dict[str, Any]] = None
    video_telemetry: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AssessmentReportResponse(BaseModel):
    id: Optional[int] = None
    assessment_id: int
    audio_evaluation: Optional[Dict[str, Any]] = None
    video_evaluation: Optional[Dict[str, Any]] = None
    transcript_evaluation: Optional[Dict[str, Any]] = None
    overall_score: Optional[float] = None
    report_data: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True



# ---------------------------------------------------------------------------
# Media Ingestion & BE2 Chunk Upload Schemas (Category 4)
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
    sub_category: Optional[str] = Field(None, description="Optional subcategory / topic")
    difficulty_level: DifficultyLevelEnum = Field(default=DifficultyLevelEnum.MEDIUM, description="Difficulty rating")
    question_text: str = Field(..., description="Question prompt text")
    ideal_answer_rubric: Optional[str] = Field(None, description="Evaluation rubric guidelines")
    is_active: bool = Field(default=True, description="Whether question is active")


    @model_validator(mode="after")
    def enforce_subcategory_constraint(self):
        cat_val = self.category.value if hasattr(self.category, "value") else str(self.category)
        if cat_val != "TECHNICAL":
            self.sub_category = None
        elif not self.sub_category:
            self.sub_category = "General"
        return self


QuestionBankCreateRequest = QuestionCreateRequest


class QuestionUpdateRequest(BaseModel):
    category: Optional[AssessmentCategoryEnum] = None
    sub_category: Optional[str] = None
    difficulty_level: Optional[DifficultyLevelEnum] = None
    question_text: Optional[str] = None
    ideal_answer_rubric: Optional[str] = None
    is_active: Optional[bool] = None


QuestionBankUpdateRequest = QuestionUpdateRequest


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
