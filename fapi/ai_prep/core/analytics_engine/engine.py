"""
Analytics Engine for AI Prep Assessment Platform.
Pure business logic for calculating candidate performance trends, averages,
and score breakdowns across historical assessment attempts.

Zero Database queries or Network calls are made inside this engine.
"""

from typing import List, Dict, Any, Optional


class AnalyticsEngine:
    """
    Pure Core Engine for aggregating historical assessment data and computing analytics.
    """

    @staticmethod
    def calculate_candidate_analytics(
        historical_attempts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Computes aggregate metrics, trends, and summary insights across a candidate's past attempts.

        :param historical_attempts: List of dictionaries, each containing:
            - assessment_id (int)
            - assessment_type (str)
            - created_at (str/datetime)
            - audio_telemetry (dict)
            - video_telemetry (dict)
            - report (dict with audio_evaluation, video_evaluation, transcript_evaluation)
        :return: Aggregated analytics summary dictionary.
        """
        if not historical_attempts:
            return {
                "total_assessments": 0,
                "average_wpm": 0.0,
                "average_silence_ratio_pct": 0.0,
                "average_technical_score": 0.0,
                "average_communication_score": 0.0,
                "score_trends": [],
                "wpm_trends": [],
                "top_strengths": [],
                "top_improvements": [],
            }

        total_attempts = len(historical_attempts)
        wpm_list: List[float] = []
        silence_list: List[float] = []
        tech_scores: List[float] = []
        comm_scores: List[float] = []
        score_trends: List[Dict[str, Any]] = []
        wpm_trends: List[Dict[str, Any]] = []
        all_strengths: List[str] = []
        all_improvements: List[str] = []

        for attempt in historical_attempts:
            asm_id = attempt.get("assessment_id") or attempt.get("id")
            created_at = str(attempt.get("created_at", ""))

            # 1. Audio Telemetry Aggregation
            audio_tel = attempt.get("audio_telemetry") or {}
            wpm = audio_tel.get("words_per_minute") or audio_tel.get("speaking_pace_wpm")
            if wpm is not None:
                wpm_list.append(float(wpm))
                wpm_trends.append({"assessment_id": asm_id, "wpm": float(wpm), "date": created_at})

            silence = audio_tel.get("silence_ratio_pct")
            if silence is not None:
                silence_list.append(float(silence))

            # 2. Evaluation Report Aggregation
            report = attempt.get("report") or attempt.get("assessment_report") or {}
            transcript_eval = report.get("transcript_evaluation") or {}
            scores_breakdown = transcript_eval.get("scores_breakdown") or {}

            # Technical Score (AI Engineering / Core Engineering average)
            ai_eng = scores_breakdown.get("ai_engineering", {}).get("score")
            core_eng = scores_breakdown.get("core_engineering", {}).get("score")
            
            attempt_tech_score: Optional[float] = None
            if ai_eng is not None and core_eng is not None:
                attempt_tech_score = (float(ai_eng) + float(core_eng)) / 2.0
            elif ai_eng is not None:
                attempt_tech_score = float(ai_eng)
            elif core_eng is not None:
                attempt_tech_score = float(core_eng)

            if attempt_tech_score is not None:
                tech_scores.append(attempt_tech_score)
                score_trends.append({
                    "assessment_id": asm_id,
                    "score": round(attempt_tech_score, 1),
                    "date": created_at,
                })

            # Non-Technical / Communication Score
            non_tech = scores_breakdown.get("non_technical", {}).get("score")
            if non_tech is not None:
                comm_scores.append(float(non_tech))

            # Strengths & Improvements Aggregation
            tech_analysis = transcript_eval.get("technical_analysis") or {}
            strengths = tech_analysis.get("strengths") or []
            if isinstance(strengths, list):
                all_strengths.extend([str(s) for s in strengths])

            improvements = tech_analysis.get("areas_for_improvement") or []
            if isinstance(improvements, list):
                all_improvements.extend([str(imp) for imp in improvements])

        # 3. Calculate Final Means
        avg_wpm = round(sum(wpm_list) / len(wpm_list), 1) if wpm_list else 0.0
        avg_silence = round(sum(silence_list) / len(silence_list), 1) if silence_list else 0.0
        avg_tech = round(sum(tech_scores) / len(tech_scores), 1) if tech_scores else 0.0
        avg_comm = round(sum(comm_scores) / len(comm_scores), 1) if comm_scores else 0.0

        # Deduplicate top strengths and improvements
        unique_strengths = list(dict.fromkeys(all_strengths))[:5]
        unique_improvements = list(dict.fromkeys(all_improvements))[:5]

        return {
            "total_assessments": total_attempts,
            "average_wpm": avg_wpm,
            "average_silence_ratio_pct": avg_silence,
            "average_technical_score": avg_tech,
            "average_communication_score": avg_comm,
            "score_trends": score_trends,
            "wpm_trends": wpm_trends,
            "top_strengths": unique_strengths,
            "top_improvements": unique_improvements,
        }
