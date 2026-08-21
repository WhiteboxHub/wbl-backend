from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict

# Import Enums from our self-contained models file
from fapi.ai_prep.models import (
    QuestionCategoryEnum, QuestionDifficultyEnum, AssessmentTypeEnum,
    AssessmentModeEnum, AssessmentStatusEnum, BackgroundNoiseLevelEnum,
    CoachingBandEnum, ConsentTypeEnum, DeletionRequestStatusEnum,
    AnalysisRunTypeEnum, AnalysisRunStatusEnum
)


# =====================================================================
# AIPREP PYDANTIC VALIDATION SCHEMAS (14 TABLES)
# =====================================================================


# 1. Question Bank Schemas
class QuestionBankCreate(BaseModel):
    category: QuestionCategoryEnum
    sub_category: str
    difficulty_level: QuestionDifficultyEnum = QuestionDifficultyEnum.MEDIUM
    question_text: str
    ideal_answer_rubric: Optional[str] = None
    relevant_skills_json: Optional[List[str]] = None


class QuestionBankResponse(BaseModel):
    id: int
    category: QuestionCategoryEnum
    sub_category: str
    difficulty_level: QuestionDifficultyEnum
    question_text: str
    ideal_answer_rubric: Optional[str] = None
    relevant_skills_json: Optional[List[str]] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# 2. Assessment Question Schema (Single Question in Session)
class AssessmentQuestionSchema(BaseModel):
    id: int
    order_index: int
    question_text: str
    difficulty_level: QuestionDifficultyEnum

    model_config = ConfigDict(from_attributes=True)


# 3. Assessment Create Schema (Request Payload for POST /assessments)
class AssessmentCreate(BaseModel):
    assessment_type: AssessmentTypeEnum
    assessment_mode: AssessmentModeEnum = AssessmentModeEnum.VIDEO_AUDIO
    candidate_resume_id: Optional[int] = None
    job_description_text: Optional[str] = None


# 4. Assessment Response Schema (Response Payload for GET/POST /assessments)
class AssessmentResponse(BaseModel):
    id: int
    candidate_id: int
    assessment_type: AssessmentTypeEnum
    assessment_mode: AssessmentModeEnum
    status: AssessmentStatusEnum
    attempt_number: int
    questions: List[AssessmentQuestionSchema] = []
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    coaching_band: Optional[CoachingBandEnum] = None

    model_config = ConfigDict(from_attributes=True)


# 5. Assessment Status Update Schema (Request Payload for PATCH /assessments/{id}/status)
class AssessmentStatusUpdate(BaseModel):
    status: AssessmentStatusEnum


# 6. Hardware Check Schemas
class HardwareCheckCreate(BaseModel):
    assessment_id: int
    browser_info: Optional[str] = None
    os_info: Optional[str] = None
    camera_permission: bool = False
    mic_permission: bool = False
    speaker_ok: bool = False
    bandwidth_kbps: int = 0
    yolo_model_enabled: bool = False


class HardwareCheckResponse(BaseModel):
    id: int
    assessment_id: int
    browser_info: Optional[str] = None
    os_info: Optional[str] = None
    camera_permission: bool
    mic_permission: bool
    speaker_ok: bool
    bandwidth_kbps: int
    yolo_model_enabled: bool
    tested_at: datetime

    model_config = ConfigDict(from_attributes=True)


# 7. Assessment List Response Schema (Paginated List Response)
class AssessmentListResponse(BaseModel):
    items: List[AssessmentResponse]
    total: int


# 8. Media File Schemas
class MediaFileCreate(BaseModel):
    assessment_id: int
    audio_file_path: str
    video_file_path: Optional[str] = None
    duration_seconds: int = 0
    file_size_bytes: int = 0


class MediaFileResponse(BaseModel):
    id: int
    assessment_id: int
    audio_file_path: str
    video_file_path: Optional[str] = None
    duration_seconds: int
    file_size_bytes: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# 9. Transcript Schemas
class TranscriptCreate(BaseModel):
    assessment_id: int
    transcript_text: str
    word_timestamps_json: Optional[Dict[str, Any]] = None


class TranscriptResponse(BaseModel):
    id: int
    assessment_id: int
    transcript_text: str
    word_timestamps_json: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# 10. Vision Telemetry Schemas
class VisionTelemetryCreate(BaseModel):
    assessment_id: int
    face_visible_pct: float = 0.0
    head_nods_count: int = 0
    frame_stability_score: float = 0.0
    snapshots_json: Optional[List[Dict[str, Any]]] = None


class VisionTelemetryResponse(BaseModel):
    id: int
    assessment_id: int
    face_visible_pct: float
    head_nods_count: int
    frame_stability_score: float
    snapshots_json: Optional[List[Dict[str, Any]]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# 11. Audio Telemetry Schemas
class AudioTelemetryCreate(BaseModel):
    assessment_id: int
    avg_volume_db: float = 0.0
    background_noise_level: BackgroundNoiseLevelEnum = BackgroundNoiseLevelEnum.LOW
    clipping_detected: bool = False
    silence_ratio_pct: float = 0.0
    filler_words_per_min: int = 0
    speaking_pace_wpm: int = 0


class AudioTelemetryResponse(BaseModel):
    id: int
    assessment_id: int
    avg_volume_db: float
    background_noise_level: BackgroundNoiseLevelEnum
    clipping_detected: bool
    silence_ratio_pct: float
    filler_words_per_min: int
    speaking_pace_wpm: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# 12. Report Response Schema
class ReportResponse(BaseModel):
    id: int
    assessment_id: int
    overall_score: int
    coaching_band: CoachingBandEnum
    formula_explanation: Optional[str] = None
    scores_breakdown_json: Dict[str, Any]
    technical_analysis_json: Dict[str, Any]
    non_technical_analysis_json: Dict[str, Any]
    coaching_suggestions_json: Optional[List[str]] = None
    signal_timeline_json: Optional[List[Dict[str, Any]]] = None
    transcript_evidence_json: Optional[List[Dict[str, Any]]] = None
    gaps_to_validate_json: Optional[List[str]] = None
    improvements_json: Optional[List[str]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# 13. User Consent Schemas
class ConsentCreate(BaseModel):
    consent_type: ConsentTypeEnum
    consented: bool = True


class ConsentResponse(BaseModel):
    id: int
    candidate_id: int
    consent_type: ConsentTypeEnum
    consented: bool
    consented_at: datetime
    revoked_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# 14. Share Grant Schemas
class ShareGrantCreate(BaseModel):
    assessment_id: int
    expires_in_days: int = 7


class ShareGrantResponse(BaseModel):
    id: int
    assessment_id: int
    shared_by_candidate_id: int
    share_token: str
    expires_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# 15. Deletion Request Schemas
class DeletionRequestCreate(BaseModel):
    notes: Optional[str] = None


class DeletionRequestResponse(BaseModel):
    id: int
    candidate_id: int
    requested_at: datetime
    completed_at: Optional[datetime] = None
    status: DeletionRequestStatusEnum
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# 16. Analysis Run Schemas
class AnalysisRunCreate(BaseModel):
    assessment_id: int
    run_type: AnalysisRunTypeEnum


class AnalysisRunResponse(BaseModel):
    id: int
    assessment_id: int
    run_type: AnalysisRunTypeEnum
    status: AnalysisRunStatusEnum
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    celery_task_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
