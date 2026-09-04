"""
Orchestrator package for AI Prep Platform.
Exports AssessmentOrchestrator and assessment_orchestrator singleton.
"""

from fapi.ai_prep.orchestrator.assessment_orchestrator import (
    AssessmentOrchestrator,
    assessment_orchestrator,
)

__all__ = ["AssessmentOrchestrator", "assessment_orchestrator"]
