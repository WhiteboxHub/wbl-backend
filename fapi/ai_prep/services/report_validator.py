import json
from typing import Dict, List, Any, Union, Literal
from pydantic import BaseModel, Field, ValidationError

from fapi.ai_prep.exceptions import ParseError


class CategoryScore(BaseModel):
    score: int = Field(..., ge=0, le=100)
    sub_scores: Dict[str, int]


class ScoresBreakdown(BaseModel):
    ai_engineering: CategoryScore
    core_engineering: CategoryScore
    non_technical: CategoryScore
    business_acumen: CategoryScore


class TechnicalAnalysis(BaseModel):
    summary: str
    strengths: List[str]
    areas_for_improvement: List[str]
    depth_assessment: str | None = None


class NonTechnicalAnalysis(BaseModel):
    communication_summary: str
    structure_quality: str
    confidence_notes: str


class CoachingSuggestion(BaseModel):
    priority: int = Field(..., ge=1)
    dimension: str
    area: str
    suggestion: str
    evidence: str


class SignalTimelinePoint(BaseModel):
    question_index: int
    energy: Union[int, float, str]
    clarity: Union[int, float, str]


class TranscriptEvidence(BaseModel):
    quote: str
    timestamp_s: Union[int, float, None] = None
    dimension: str
    observation: str


class GapToValidate(BaseModel):
    topic: str
    reason: str


class Improvement(BaseModel):
    priority: int = Field(..., ge=1)
    topic: str
    effort: Literal["low", "medium", "high"]
    rationale: str


class LlmReportOutputSchema(BaseModel):
    scores_breakdown_json: ScoresBreakdown
    technical_analysis_json: TechnicalAnalysis
    non_technical_analysis_json: NonTechnicalAnalysis
    coaching_suggestions_json: List[CoachingSuggestion]
    signal_timeline_json: List[SignalTimelinePoint]
    transcript_evidence_json: List[TranscriptEvidence]
    gaps_to_validate_json: List[GapToValidate]
    improvements_json: List[Improvement]


def validate_report_json(raw_output: str) -> dict:
    """Parses and validates LLM raw output against the Contract 3 schema.

    Args:
        raw_output: Raw JSON string from the LLM.

    Returns:
        dict: The validated report dictionary (conforming to Contract 3).

    Raises:
        ParseError: If raw_output is invalid JSON or does not conform to the schema.
    """
    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise ParseError(
            message=f"LLM output is not valid JSON: {str(exc)}",
            original_error=exc
        ) from exc

    try:
        validated = LlmReportOutputSchema.model_validate(data)
        return validated.model_dump()
    except ValidationError as exc:
        # Format the validation error into a readable message listing specific fields
        error_details = []
        for error in exc.errors():
            loc = " -> ".join(str(l) for l in error["loc"])
            msg = error["msg"]
            error_details.append(f"{loc}: {msg}")
        
        detail_msg = "; ".join(error_details)
        raise ParseError(
            message=f"JSON schema validation failed: {detail_msg}",
            original_error=exc
        ) from exc
