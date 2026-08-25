from collections import Counter
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fapi.ai_prep.models import AiPrepAssessment, AiPrepReport, AiPrepAudioTelemetry, AssessmentStatusEnum
from fapi.ai_prep.schemas import DashboardResponse, ExecutiveSummary, RadarChartData, CommunicationTimepoint

def get_sub_score(scores: dict, category: str, subkey: str, default: float = 0.0) -> float:
    """Safely navigate scores_breakdown_json to retrieve nested sub-scores without crashing."""
    if not isinstance(scores, dict):
        return default
    cat_data = scores.get(category)
    if not isinstance(cat_data, dict):
        return default
    sub_scores = cat_data.get("sub_scores")
    if not isinstance(sub_scores, dict):
        return default
    val = sub_scores.get(subkey)
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def get_candidate_dashboard_metrics(db: Session, candidate_id: int) -> DashboardResponse:
    # Get all assessments for this candidate
    all_assessments = db.query(AiPrepAssessment).filter(
        AiPrepAssessment.candidate_id == candidate_id
    ).order_by(AiPrepAssessment.created_at.asc()).all()

    total_assessments = len(all_assessments)
    completed_assessments = [a for a in all_assessments if a.status == AssessmentStatusEnum.COMPLETED]
    completed_count = len(completed_assessments)

    if not completed_assessments:
        # Return default empty dashboard if no completed assessments
        return DashboardResponse(
            executive_summary=ExecutiveSummary(
                total_assessments=total_assessments,
                completed=0,
                latest_coaching_band=None,
                band_trend=[],
                average_overall_score=0.0
            ),
            radar=RadarChartData(),
            communication_trend=[]
        )

    completed_ids = [a.id for a in completed_assessments]

    # --- 1. Executive Summary & Radar Chart (from Reports) ---
    reports = db.query(AiPrepReport).filter(AiPrepReport.assessment_id.in_(completed_ids)).all()
    reports_map = {r.assessment_id: r for r in reports}
    
    total_score = 0
    coaching_bands = []
    
    radar_totals = {
        "llm_architecture": 0.0,
        "rag_systems": 0.0,
        "ml_fundamentals": 0.0,
        "system_design": 0.0,
        "code_quality": 0.0,
        "ai_ethics": 0.0
    }
    reports_with_breakdown = 0

    # Sort assessments chronologically by created_at to compute band trend correctly
    sorted_completed = sorted(completed_assessments, key=lambda a: a.created_at)

    for a in sorted_completed:
        r = reports_map.get(a.id)
        if r:
            total_score += r.overall_score
            if r.coaching_band:
                coaching_bands.append(r.coaching_band)
            
            if r.scores_breakdown_json:
                reports_with_breakdown += 1
                
                # Fetch LLM and RAG subscores
                radar_totals["llm_architecture"] += get_sub_score(r.scores_breakdown_json, "ai_engineering", "llm_knowledge")
                radar_totals["rag_systems"] += get_sub_score(r.scores_breakdown_json, "ai_engineering", "rag_understanding")
                
                # Check for algorithms or ml_fundamentals fallback
                ml_val = get_sub_score(r.scores_breakdown_json, "core_engineering", "algorithms")
                if ml_val == 0.0:
                    ml_val = get_sub_score(r.scores_breakdown_json, "core_engineering", "ml_fundamentals")
                radar_totals["ml_fundamentals"] += ml_val
                
                # System design and code quality
                radar_totals["system_design"] += get_sub_score(r.scores_breakdown_json, "core_engineering", "system_design")
                radar_totals["code_quality"] += get_sub_score(r.scores_breakdown_json, "core_engineering", "code_quality")
                
                # AI Ethics or evaluation_methodology fallback
                ethics_val = get_sub_score(r.scores_breakdown_json, "ai_engineering", "ethics")
                if ethics_val == 0.0:
                    ethics_val = get_sub_score(r.scores_breakdown_json, "ai_engineering", "evaluation_methodology")
                radar_totals["ai_ethics"] += ethics_val

    avg_score = total_score / len(reports) if reports else 0.0
    latest_coaching_band = coaching_bands[-1] if coaching_bands else None

    if reports_with_breakdown > 0:
        for key in radar_totals:
            radar_totals[key] = round(radar_totals[key] / reports_with_breakdown, 2)

    exec_summary = ExecutiveSummary(
        total_assessments=total_assessments,
        completed=completed_count,
        latest_coaching_band=latest_coaching_band,
        band_trend=coaching_bands,
        average_overall_score=round(avg_score, 2)
    )

    radar_chart = RadarChartData(**radar_totals)

    # --- 2. Communication Analytics (Time-series from AudioTelemetry) ---
    telemetry = db.query(AiPrepAudioTelemetry).filter(
        AiPrepAudioTelemetry.assessment_id.in_(completed_ids)
    ).all()
    
    # Map telemetry to assessment creation date for the time-series
    assessment_date_map = {a.id: a.created_at for a in completed_assessments}
    
    trend_data = []
    for t in telemetry:
        dt = assessment_date_map.get(t.assessment_id)
        if dt:
            trend_data.append(CommunicationTimepoint(
                assessment_id=t.assessment_id,
                date=dt,
                wpm=t.speaking_pace_wpm,
                filler_per_min=t.filler_words_per_min,
                silence_pct=float(t.silence_ratio_pct)
            ))
    
    # Sort chronologically by date
    trend_data.sort(key=lambda x: x.date)

    return DashboardResponse(
        executive_summary=exec_summary,
        radar=radar_chart,
        communication_trend=trend_data
    )
