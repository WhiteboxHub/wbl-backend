from collections import Counter
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fapi.ai_prep.models import AiPrepAssessment, AiPrepReport, AiPrepAudioTelemetry, AssessmentStatusEnum
from fapi.ai_prep.schemas import DashboardResponse, ExecutiveSummary, RadarChartData, CommunicationTimepoint, DashboardAssessment

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

def get_candidate_dashboard_metrics(
    db: Session,
    candidate_id: int,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None
) -> DashboardResponse:
    # Get all assessments for this candidate inside the date range
    query = db.query(AiPrepAssessment).filter(
        AiPrepAssessment.candidate_id == candidate_id
    )
    if from_date:
        query = query.filter(AiPrepAssessment.created_at >= from_date)
    if to_date:
        query = query.filter(AiPrepAssessment.created_at <= to_date)
        
    all_assessments = query.order_by(AiPrepAssessment.created_at.asc()).all()

    total_assessments = len(all_assessments)
    completed_assessments = [a for a in all_assessments if a.status == AssessmentStatusEnum.COMPLETED]
    completed_count = len(completed_assessments)
    completed_ids = [a.id for a in completed_assessments]

    # Query reports for completed assessments to get scores & bands
    reports = db.query(AiPrepReport).filter(AiPrepReport.assessment_id.in_(completed_ids)).all() if completed_ids else []
    reports_map = {r.assessment_id: r for r in reports}

    # Map the assessments to DashboardAssessment schema for the history table
    dashboard_assessments = [
        DashboardAssessment(
            id=a.id,
            assessment_type=a.assessment_type,
            status=a.status,
            coaching_band=reports_map[a.id].coaching_band if a.id in reports_map else None,
            overall_score=reports_map[a.id].overall_score if a.id in reports_map else None,
            created_at=a.created_at
        )
        for a in all_assessments
    ]

    if not completed_assessments:
        # Return default empty dashboard if no completed assessments
        return DashboardResponse(
            executive_summary=ExecutiveSummary(
                total_assessments=total_assessments,
                completed=0,
                latest_coaching_band=None,
                band_trend=[],
                average_overall_score=0.0,
                assessments=dashboard_assessments
            ),
            radar=RadarChartData(),
            communication_trend=[]
        )

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
                
                # Fetch radar scores using model's encapsulated logic
                r_scores = r.get_normalized_radar_scores()
                if r_scores:
                    radar_totals["llm_architecture"] += r_scores.get("llm_architecture", 0.0)
                    radar_totals["rag_systems"] += r_scores.get("rag_systems", 0.0)
                    radar_totals["ml_fundamentals"] += r_scores.get("ml_fundamentals", 0.0)
                    radar_totals["system_design"] += r_scores.get("system_design", 0.0)
                    radar_totals["code_quality"] += r_scores.get("code_quality", 0.0)
                    radar_totals["ai_ethics"] += r_scores.get("ai_ethics", 0.0)

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
        average_overall_score=round(avg_score, 2),
        assessments=dashboard_assessments
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
