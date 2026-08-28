import json
import logging
from fapi.ai_prep.workers.celery_app import celery_app
from fapi.ai_prep.models import RunTypeEnum, RunStatusEnum, AiPrepReportORM, CoachingBandEnum, AiPrepAssessmentORM
from fapi.ai_prep.crud.runs import create_analysis_run, update_analysis_run_status
from fapi.ai_prep.services.storage_service import get_storage_service
from fapi.db.database import SessionLocal
from fapi.ai_prep.services.llm_client import call_llm
from fapi.ai_prep.services.report_validator import validate_report_json
from fapi.ai_prep.services.prompt_service import assemble_prompt


logger = logging.getLogger("wbl.ai_prep.workers.llm")


def score_to_band(overall_score: int) -> CoachingBandEnum:
    """Map composite score to coaching band per Contract 1."""
    if overall_score >= 85:
        return CoachingBandEnum.EXCELLENT
    elif overall_score >= 70:
        return CoachingBandEnum.STRONG
    elif overall_score >= 55:
        return CoachingBandEnum.DEVELOPING
    else:
        return CoachingBandEnum.NEEDS_WORK


@celery_app.task(bind=True, max_retries=3, queue="ai_prep")
def llm_analysis_task(self, assessment_id: int):
    """
    LLM Analysis Worker stub: Generates coaching report JSON conforming to Contract 3,
    calculates composite score, assigns coaching band, and writes raw LLM output to storage.
    """
    logger.info("Executing LLM Analysis Task for assessment %s", assessment_id)
    db = SessionLocal()
    run = create_analysis_run(db, assessment_id, RunTypeEnum.LLM, celery_task_id=getattr(self.request, "id", None))

    try:
        assessment = db.query(AiPrepAssessmentORM).filter(AiPrepAssessmentORM.id == assessment_id).first()
        if not assessment:
            raise ValueError(f"Assessment {assessment_id} not found")

        # 1. Assemble dynamic prompt from DB context (transcript, questions, audio metrics)
        system_prompt, user_prompt = assemble_prompt(db, assessment_id)

        # 2. Call candidate's configured LLM (GPT-4o or Claude)
        raw_llm_output = call_llm(
            db=db,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            assessment_id=assessment_id,
            candidate_id=assessment.candidate_id,
        )

        # 3. Validate raw JSON output against Contract 3 schema
        report_data = validate_report_json(raw_llm_output)

        # Calculate overall score per formula: (AI*0.40) + (Core*0.30) + (NonTech*0.20) + (Biz*0.10)
        sb = report_data["scores_breakdown_json"]
        overall = (
            sb["ai_engineering"]["score"] * 0.40 +
            sb["core_engineering"]["score"] * 0.30 +
            sb["non_technical"]["score"] * 0.20 +
            sb["business_acumen"]["score"] * 0.10
        )
        overall_score = int(round(overall))
        coaching_band = score_to_band(overall_score)

        # Save raw JSON to storage
        raw_storage_path = f"ai-prep/{assessment.candidate_id}/{assessment_id}/llm_response.json"
        storage = get_storage_service()
        storage.upload_bytes(raw_storage_path, json.dumps(report_data).encode(), content_type="application/json")

        # Save report to ai_prep_reports
        existing_report = db.query(AiPrepReportORM).filter(AiPrepReportORM.assessment_id == assessment_id).first()
        if existing_report:
            existing_report.overall_score = overall_score
            existing_report.coaching_band = coaching_band
            existing_report.scores_breakdown_json = report_data["scores_breakdown_json"]
            existing_report.technical_analysis_json = report_data["technical_analysis_json"]
            existing_report.non_technical_analysis_json = report_data["non_technical_analysis_json"]
            existing_report.coaching_suggestions_json = report_data["coaching_suggestions_json"]
            existing_report.signal_timeline_json = report_data["signal_timeline_json"]
            existing_report.transcript_evidence_json = report_data["transcript_evidence_json"]
            existing_report.gaps_to_validate_json = report_data["gaps_to_validate_json"]
            existing_report.improvements_json = report_data["improvements_json"]
            existing_report.raw_llm_response_path = raw_storage_path
        else:
            rep = AiPrepReportORM(
                assessment_id=assessment_id,
                overall_score=overall_score,
                coaching_band=coaching_band,
                scores_breakdown_json=report_data["scores_breakdown_json"],
                technical_analysis_json=report_data["technical_analysis_json"],
                non_technical_analysis_json=report_data["non_technical_analysis_json"],
                coaching_suggestions_json=report_data["coaching_suggestions_json"],
                signal_timeline_json=report_data["signal_timeline_json"],
                transcript_evidence_json=report_data["transcript_evidence_json"],
                gaps_to_validate_json=report_data["gaps_to_validate_json"],
                improvements_json=report_data["improvements_json"],
                raw_llm_response_path=raw_storage_path
            )
            db.add(rep)
        db.commit()

        update_analysis_run_status(db, run.id, RunStatusEnum.COMPLETED)
        return {"assessment_id": assessment_id, "status": "COMPLETED", "overall_score": overall_score, "coaching_band": coaching_band.value}

    except Exception as exc:
        logger.error("LLM Task failed for assessment %s: %s", assessment_id, exc)
        update_analysis_run_status(db, run.id, RunStatusEnum.FAILED, error_message=str(exc))
        raise self.retry(exc=exc, countdown=2 ** getattr(self.request, "retries", 1) * 30)

    finally:
        db.close()
