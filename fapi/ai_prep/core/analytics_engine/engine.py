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

            # 1. Audio Telemetry & Audio Evaluation Aggregation
            audio_tel = attempt.get("audio_telemetry") or {}
            report = attempt.get("report") or attempt.get("assessment_report") or {}
            audio_eval = report.get("audio_evaluation") or attempt.get("audio_evaluation") or {}
            if isinstance(audio_eval, dict) and "audio_evaluation" in audio_eval and isinstance(audio_eval["audio_evaluation"], dict):
                audio_eval = audio_eval["audio_evaluation"]

            wpm = (
                audio_tel.get("words_per_minute")
                or audio_tel.get("speaking_pace_wpm")
                or audio_tel.get("wpm")
            )
            if wpm is None and isinstance(audio_eval, dict):
                factors = audio_eval.get("factors") or {}
                if isinstance(factors, dict):
                    pace = factors.get("pace") or {}
                    if isinstance(pace, dict):
                        wpm = pace.get("wpm_recorded")

            if wpm is not None:
                try:
                    wpm_val = float(wpm)
                    if wpm_val > 0:
                        wpm_list.append(wpm_val)
                        wpm_trends.append({"assessment_id": asm_id, "wpm": round(wpm_val, 1), "date": created_at})
                except (ValueError, TypeError):
                    pass

            silence = audio_tel.get("silence_ratio_pct")
            if silence is None:
                silence = audio_tel.get("silence_ratio")
            if silence is None and isinstance(audio_eval, dict):
                factors = audio_eval.get("factors") or {}
                if isinstance(factors, dict):
                    fluency = factors.get("fluency") or factors.get("silence") or {}
                    if isinstance(fluency, dict):
                        silence = fluency.get("silence_ratio_pct")
            if silence is not None:
                try:
                    silence_list.append(float(silence))
                except (ValueError, TypeError):
                    pass

            # 2. Evaluation Report Aggregation
            transcript_eval = report.get("transcript_evaluation") or attempt.get("transcript_evaluation") or {}
            intro_eval = {}
            if isinstance(transcript_eval, dict):
                if "intro_evaluation" in transcript_eval and isinstance(transcript_eval["intro_evaluation"], dict):
                    intro_eval = transcript_eval["intro_evaluation"]
                elif "overall_assessment" in transcript_eval:
                    intro_eval = transcript_eval

            scores_breakdown = {}
            if isinstance(transcript_eval, dict):
                scores_breakdown = (
                    transcript_eval.get("scores_breakdown")
                    or transcript_eval.get("scores_breakdown_json")
                    or {}
                )
            if not scores_breakdown and isinstance(intro_eval, dict):
                scores_breakdown = (
                    intro_eval.get("scores_breakdown")
                    or intro_eval.get("scores_breakdown_json")
                    or {}
                )

            READINESS_BAND_SCORES = {
                "STRONG": 90.0,
                "GOOD": 75.0,
                "NEEDS_POLISH": 60.0,
                "WEAK": 40.0,
                "NOT_READY": 30.0,
                "NOT_MENTIONED": 20.0,
            }

            # Technical / Overall Score
            attempt_tech_score: Optional[float] = None
            if isinstance(scores_breakdown, dict) and scores_breakdown:
                ai_eng = scores_breakdown.get("ai_engineering", {}).get("score")
                core_eng = scores_breakdown.get("core_engineering", {}).get("score")
                if ai_eng is not None and core_eng is not None:
                    attempt_tech_score = (float(ai_eng) + float(core_eng)) / 2.0
                elif ai_eng is not None:
                    attempt_tech_score = float(ai_eng)
                elif core_eng is not None:
                    attempt_tech_score = float(core_eng)

            # Fallback to intro_evaluation overall_assessment / overall_score / readiness
            if attempt_tech_score is None and isinstance(intro_eval, dict) and intro_eval:
                oa = intro_eval.get("overall_assessment") or {}
                if isinstance(oa, dict):
                    raw_sc = oa.get("overall_score") or oa.get("score")
                    if raw_sc is not None:
                        try:
                            attempt_tech_score = float(raw_sc)
                        except (ValueError, TypeError):
                            pass
                    elif oa.get("readiness"):
                        r_key = str(oa.get("readiness")).upper().strip()
                        attempt_tech_score = READINESS_BAND_SCORES.get(r_key)

                if attempt_tech_score is None:
                    raw_sc = intro_eval.get("overall_score") or intro_eval.get("score")
                    if raw_sc is not None:
                        try:
                            attempt_tech_score = float(raw_sc)
                        except (ValueError, TypeError):
                            pass
                    elif intro_eval.get("readiness"):
                        r_key = str(intro_eval.get("readiness")).upper().strip()
                        attempt_tech_score = READINESS_BAND_SCORES.get(r_key)

            # Fallback to report overall_score
            if attempt_tech_score is None:
                raw_sc = (
                    report.get("overall_score")
                    or attempt.get("overall_score")
                    or attempt.get("score")
                )
                if raw_sc is not None:
                    try:
                        attempt_tech_score = float(raw_sc)
                    except (ValueError, TypeError):
                        pass

            if attempt_tech_score is not None:
                tech_scores.append(attempt_tech_score)
                score_trends.append({
                    "assessment_id": asm_id,
                    "score": round(attempt_tech_score, 1),
                    "date": created_at,
                })

            # Non-Technical / Communication Score
            attempt_comm_score: Optional[float] = None
            if isinstance(scores_breakdown, dict) and scores_breakdown:
                non_tech = (
                    scores_breakdown.get("non_technical", {}).get("score")
                    or scores_breakdown.get("communication", {}).get("score")
                )
                if non_tech is not None:
                    try:
                        attempt_comm_score = float(non_tech)
                    except (ValueError, TypeError):
                        pass

            if attempt_comm_score is None and isinstance(intro_eval, dict) and intro_eval:
                iq = intro_eval.get("introduction_quality") or {}
                if isinstance(iq, dict):
                    raw_comm = iq.get("score")
                    if raw_comm is not None:
                        try:
                            attempt_comm_score = float(raw_comm)
                        except (ValueError, TypeError):
                            pass
                    else:
                        # Extract qualitative bands: clarity, coherence
                        comm_bands = []
                        for band_key in ["clarity", "coherence", "personal_ownership"]:
                            b_val = str(iq.get(band_key) or "").upper().strip()
                            if b_val in READINESS_BAND_SCORES:
                                comm_bands.append(READINESS_BAND_SCORES[b_val])
                        if comm_bands:
                            attempt_comm_score = sum(comm_bands) / len(comm_bands)

            if attempt_comm_score is None and attempt_tech_score is not None:
                attempt_comm_score = attempt_tech_score

            if attempt_comm_score is not None:
                comm_scores.append(attempt_comm_score)

            # Strengths & Improvements Aggregation
            DUMMY_VALUES = {"none", "n/a", "na", "-", "null", "nil", "no information provided.", "no information provided"}

            def _extract_items(source: Any) -> List[str]:
                if not source or not isinstance(source, list):
                    return []
                out = []
                for item in source:
                    if isinstance(item, str):
                        s = item.strip()
                        if s and s.lower() not in DUMMY_VALUES:
                            out.append(s)
                    elif isinstance(item, dict):
                        text_val = (
                            item.get("guidance")
                            or item.get("suggested_addition")
                            or item.get("observation")
                            or item.get("what_is_missing")
                            or item.get("topic")
                            or item.get("title")
                            or item.get("point")
                            or item.get("text")
                        )
                        if text_val and isinstance(text_val, str):
                            s = text_val.strip()
                            if s and s.lower() not in DUMMY_VALUES:
                                out.append(s)
                return out

            # Strengths
            tech_analysis = transcript_eval.get("technical_analysis") if isinstance(transcript_eval, dict) else {}
            if isinstance(tech_analysis, dict):
                all_strengths.extend(_extract_items(tech_analysis.get("strengths")))
            if isinstance(intro_eval, dict):
                all_strengths.extend(_extract_items(intro_eval.get("strongest_points")))
            if isinstance(report, dict):
                all_strengths.extend(_extract_items(report.get("strengths")))

            # Improvements
            if isinstance(tech_analysis, dict):
                all_improvements.extend(_extract_items(tech_analysis.get("areas_for_improvement")))
            if isinstance(intro_eval, dict):
                all_improvements.extend(_extract_items(intro_eval.get("priority_improvements")))
                all_improvements.extend(_extract_items(intro_eval.get("critical_gaps")))
            if isinstance(report, dict):
                all_improvements.extend(_extract_items(report.get("improvements")))
                all_improvements.extend(_extract_items(report.get("areas_for_improvement")))

        # 3. Calculate Final Means
        avg_wpm = round(sum(wpm_list) / len(wpm_list), 1) if wpm_list else 0.0
        avg_silence = round(sum(silence_list) / len(silence_list), 1) if silence_list else 0.0
        avg_tech = round(sum(tech_scores) / len(tech_scores), 1) if tech_scores else 0.0
        avg_comm = round(sum(comm_scores) / len(comm_scores), 1) if comm_scores else 0.0

        # Deduplicate top strengths and improvements preserving order
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
