"""Service to dynamically assemble prompts for all 7 AIPrep assessment types."""
from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from fapi.ai_prep.models import (
    AiPrepAssessmentORM,
    AiPrepTranscriptORM,
    AiPrepAudioTelemetryORM,
    AssessmentTypeEnum,
)
from fapi.ai_prep.prompts import (
    general_intro,
    jd_intro,
    recruiter,
    hiring_manager,
    technical,
    system_design,
    hr,
)

logger = logging.getLogger("aiprep.prompt_service")

PROMPT_MODULE_MAP = {
    AssessmentTypeEnum.GENERAL_INTRO: general_intro,
    AssessmentTypeEnum.JOB_DESCRIPTION_INTRO: jd_intro,
    AssessmentTypeEnum.RECRUITER: recruiter,
    AssessmentTypeEnum.HIRING_MANAGER: hiring_manager,
    AssessmentTypeEnum.TECHNICAL: technical,
    AssessmentTypeEnum.SYSTEM_DESIGN: system_design,
    AssessmentTypeEnum.HR: hr,
}


def assemble_prompt(db: Session, assessment_id: int) -> tuple[str, str]:
    """Fetches DB context for the assessment and generates (system_prompt, user_prompt)."""
    assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
    if not assessment:
        raise ValueError(f"Assessment {assessment_id} not found")

    # 1. Format questions asked
    questions_list = [
        f"Q{aq.order_index}: {aq.question.question_text}"
        for aq in sorted(assessment.questions, key=lambda x: x.order_index)
        if aq.question
    ]
    questions_text = "\n".join(questions_list) if questions_list else "No pre-set questions; continuous self-introduction."

    # 2. Fetch transcript from ai_prep_transcripts
    tx = db.query(AiPrepTranscriptORM).filter(AiPrepTranscriptORM.assessment_id == assessment_id).first()
    transcript_text = tx.transcript_text if (tx and tx.transcript_text) else "No transcript recorded for this session."

    # 3. Fetch audio telemetry metrics
    audio = db.query(AiPrepAudioTelemetryORM).filter(AiPrepAudioTelemetryORM.assessment_id == assessment_id).first()
    wpm = int(audio.speaking_pace_wpm) if (audio and audio.speaking_pace_wpm) else 135
    filler_per_min = int(audio.filler_words_per_min) if (audio and audio.filler_words_per_min) else 2
    silence_pct = float(audio.silence_ratio_pct) if (audio and audio.silence_ratio_pct) else 8.0
    avg_db = float(audio.avg_volume_db) if (audio and audio.avg_volume_db) else -18.0
    noise_level = audio.background_noise_level.value.lower() if (audio and audio.background_noise_level) else "low"

    # 4. Resolve prompt module
    prompt_module = PROMPT_MODULE_MAP.get(assessment.assessment_type, general_intro)
    system_prompt = prompt_module.SYSTEM

    # 5. Format user template
    format_kwargs = {
        "questions": questions_text,
        "transcript": transcript_text,
        "wpm": wpm,
        "filler_per_min": filler_per_min,
        "silence_pct": silence_pct,
        "avg_db": avg_db,
        "noise_level": noise_level,
    }

    if assessment.assessment_type == AssessmentTypeEnum.JOB_DESCRIPTION_INTRO:
        format_kwargs["jd_text"] = assessment.job_description_text or "No specific job description provided."

    user_prompt = prompt_module.USER_TEMPLATE.format(**format_kwargs)
    return system_prompt, user_prompt
