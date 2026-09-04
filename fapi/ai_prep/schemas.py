"""
Pydantic Request & Response Schemas for AIPrep
==============================================
Defines strict data contracts for:
- Assessment Lifecycle
- Chunk Upload & Assembly (BE2)
- Telemetry & LLM Evaluations
- Analytics & Reports
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from fapi.ai_prep.models import AssessmentStatusEnum, AssessmentTypeEnum, AssessmentMediaTypeEnum


# =====================================================================
# Assessment Lifecycle Schemas
# =====================================================================
class CreateAssessmentRequest(BaseModel):
    assessment_type: AssessmentTypeEnum = Field(default=AssessmentTypeEnum.TECHNICAL, description="Category of assessment")
    assessment_mode: AssessmentMediaTypeEnum = Field(default=AssessmentMediaTypeEnum.VIDEO, description="VIDEO or AUDIO")
    candidate_id: Optional[int] = Field(default=None, description="Optional candidate id override")
    candidate_resume_id: Optional[int] = Field(default=None, description="Optional resume id")
    job_description_text: Optional[str] = Field(default=None, description="Target job description")
    job_description: Optional[str] = Field(default=None, description="Alias for job description")


class AssessmentResponse(BaseModel):
    id: int
    candidate_id: int
    assessment_type: str
    assessment_mode: str
    status: str
    job_description: Optional[str] = None
    youtube_url: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AssessmentListResponse(BaseModel):
    total: int
    items: List[AssessmentResponse]


class UpdateAssessmentStatusRequest(BaseModel):
    status: AssessmentStatusEnum


class UpdateAssessmentMediaRequest(BaseModel):
    youtube_url: str


# =====================================================================
# Media Ingestion & Chunking Schemas (BE2)
# =====================================================================
class ChunkUploadResponse(BaseModel):
    chunk_number: int
    status: str = "uploaded"
    storage_path: Optional[str] = None
    total_chunks: Optional[int] = None


class ChunksStatusResponse(BaseModel):
    assessment_id: int
    uploaded_chunks: List[int]
    missing_chunks: List[int]
    total_chunks_expected: Optional[int] = None
    is_ready_for_assembly: bool


class AssembleMediaRequest(BaseModel):
    assessment_id: int
    total_chunks: int = Field(gt=0, description="Total expected number of chunks")


class AssembleMediaResponse(BaseModel):
    assessment_id: int
    status: str
    task_id: Optional[str] = None
    message: str


class ProcessingStatusResponse(BaseModel):
    assessment_id: int
    status: str
    progress_percentage: int
    current_step: str
    error_message: Optional[str] = None
    youtube_url: Optional[str] = None


# =====================================================================
# Operational Media & Task Runs Schemas (BE2)
# =====================================================================
class MediaFileResponse(BaseModel):
    id: int
    assessment_id: int
    audio_file_path: Optional[str] = None
    video_file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None

    class Config:
        from_attributes = True


class AnalysisRunResponse(BaseModel):
    id: int
    assessment_id: int
    run_type: str
    status: str
    celery_task_id: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True

