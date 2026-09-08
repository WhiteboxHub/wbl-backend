# Core Engine 4 — LLM Evaluation Engine (Prompt Builder)


import json
from typing import Any, Dict, Optional


class EvalEngine:
    """
    Core Engine 4: In-memory compiler for evaluation prompts.
    Formats dynamic candidate data into prompt templates for LLM invocation.
    """

    SUPPORTED_TYPES = {
        "INTRO": "intro",
        "JD_INTRO": "jd_intro",
        "RECRUITER": "recruiter",
        "HIRING_MANAGER": "hiring_manager",
        "TECHNICAL": "technical",
        "SYSTEM_DESIGN": "system_design",
    }

    def __init__(self) -> None:
        pass

    def build_prompt(
        self,
        assessment_type: str,
        transcript_text: str,
        audio_telemetry: Optional[Any] = None,
        video_telemetry: Optional[Any] = None,
        ground_truth: Optional[Dict[str, Any]] = None,
        resume_json: Optional[Any] = None,
        timeline_json: Optional[Any] = None,
    ) -> Dict[str, str]:
        """
        Builds and formats the system and user prompts for the specified assessment.

        Args:
            assessment_type: One of the supported assessment types (e.g. INTRO, TECHNICAL).
            transcript_text: Full spoken speech-to-text transcript.
            audio_telemetry: Optional acoustic metrics (evaluated separately).
            video_telemetry: Optional visual metrics (evaluated separately).
            ground_truth: Optional dictionary containing resume, timeline, JD, or questions.
            resume_json: Optional candidate resume or timeline background.
            timeline_json: Optional candidate career timeline.

        Returns:
            Dict conforming to Eval_Engine_Prompt_Output:
            {
                "system_prompt": str,
                "user_prompt": str,
                "response_format": "json_object"
            }
        """
        if not assessment_type:
            raise ValueError("assessment_type is required")
        if not isinstance(transcript_text, str):
            raise ValueError("transcript_text must be a string")

        normalized_type = assessment_type.upper().strip()
        if normalized_type not in self.SUPPORTED_TYPES:
            raise ValueError(
                f"Unsupported assessment_type '{assessment_type}'. "
                f"Must be one of: {sorted(list(self.SUPPORTED_TYPES.keys()))}"
            )

        template_module_name = self.SUPPORTED_TYPES[normalized_type]

        # 1. Format Candidate Timeline / Background (Ground Truth)
        timeline_source = timeline_json or resume_json
        if timeline_source is None and ground_truth:
            timeline_source = (
                ground_truth.get("timeline_json")
                or ground_truth.get("resume_json")
                or ground_truth.get("resume")
            )

        if isinstance(timeline_source, dict):
            timeline_formatted = json.dumps(timeline_source, indent=2)
        elif isinstance(timeline_source, str):
            try:
                parsed_res = json.loads(timeline_source)
                if isinstance(parsed_res, dict):
                    timeline_formatted = json.dumps(parsed_res, indent=2)
                else:
                    timeline_formatted = timeline_source
            except Exception:
                timeline_formatted = timeline_source
        else:
            timeline_formatted = "No candidate timeline/resume background provided."

        # 2. Dispatch to assessment-specific prompt module
        if template_module_name == "intro":
            from fapi.ai_prep.core.llm_evaluation.prompts.intro import (
                SYSTEM_PROMPT,
                USER_PROMPT_TEMPLATE,
            )

            user_prompt = USER_PROMPT_TEMPLATE.format(
                resume_json=timeline_formatted,
                transcript_text=transcript_text.strip() or "[No spoken transcript captured]",
            )

            return {
                "system_prompt": SYSTEM_PROMPT,
                "user_prompt": user_prompt,
                "response_format": "json_object",
            }
        else:
            raise NotImplementedError(
                f"Prompt template for '{normalized_type}' ({template_module_name}) "
                "is scheduled in the roadmap and will be added in upcoming tasks."
            )

    def build_audio_prompt(self, audio_telemetry: Dict[str, Any]) -> Dict[str, str]:
        """
        Builds and formats the system and user prompts for universal audio delivery evaluation.
        """
        from fapi.ai_prep.core.llm_evaluation.prompts.audio_eval import (
            SYSTEM_PROMPT,
            USER_PROMPT_TEMPLATE,
        )

        sanitized = self._sanitize_audio_telemetry(audio_telemetry or {})
        user_prompt = USER_PROMPT_TEMPLATE.format(
            speaking_pace_wpm=sanitized["speaking_pace_wpm"],
            avg_volume_db=sanitized["avg_volume_db"],
            mean_pitch_hz=sanitized["mean_pitch_hz"],
            silence_ratio_pct=sanitized["silence_ratio_pct"],
            filler_rate_per_min=sanitized["filler_rate_per_min"],
            pause_count=sanitized["pause_count"],
            speaking_duration_seconds=sanitized["speaking_duration_seconds"],
            background_noise_level=sanitized["background_noise_level"],
            clipping_detected=sanitized["clipping_detected"],
        )

        return {
            "system_prompt": SYSTEM_PROMPT,
            "user_prompt": user_prompt,
            "response_format": "json_object",
        }

    @staticmethod
    def has_evaluable_audio(audio_telemetry: Optional[Dict[str, Any]]) -> bool:
        """
        Determines whether the provided audio telemetry contains measurable speech activity.
        If speech duration <= 0 or telemetry is empty, returns False to skip LLM token consumption.
        """
        if not audio_telemetry or not isinstance(audio_telemetry, dict):
            return False

        duration = audio_telemetry.get("speaking_duration_seconds")
        if duration is None:
            duration = audio_telemetry.get("duration") or audio_telemetry.get("total_audio_duration_seconds", 0)
        try:
            duration_val = float(duration)
        except (ValueError, TypeError):
            duration_val = 0.0

        if duration_val <= 0:
            return False

        has_pace = float(audio_telemetry.get("speaking_pace_wpm") or audio_telemetry.get("words_per_minute") or audio_telemetry.get("wpm") or 0) > 0
        has_volume = audio_telemetry.get("avg_volume_db") is not None and float(audio_telemetry.get("avg_volume_db", -20.0)) != -20.0
        has_silence = audio_telemetry.get("silence_ratio_pct") is not None or audio_telemetry.get("silence_ratio") is not None

        return duration_val > 0 and (has_pace or has_volume or has_silence)

    @staticmethod
    def build_insufficient_audio_evaluation(speaking_duration: float = 0.0) -> Dict[str, Any]:
        """
        Generates deterministic, contract-compliant INSUFFICIENT_DATA audio evaluation payload.
        Used when no audio recording or 0-second speech is detected, saving 100% of LLM tokens.
        """
        return {
            "audio_evaluation": {
                "summary": {
                    "overall_readiness": "INSUFFICIENT_DATA",
                    "confidence_in_reading": "LOW",
                    "confidence_rationale": "You provided a speaking duration of 0 seconds, which is insufficient for reliable telemetry evaluation.",
                    "executive_summary": "The audio telemetry indicates no measurable speech activity, resulting in insufficient data for evaluation.",
                    "primary_vocal_strength": None,
                    "primary_vocal_gap": None,
                },
                "factors": {
                    "confidence_vocal_presence": {
                        "status": "INSUFFICIENT_DATA",
                        "reliability": "UNRELIABLE",
                        "reliability_note": "Speaking duration is 0 seconds, preventing evaluation.",
                        "observation": "You did not provide any measurable speech activity, making it impossible to assess vocal presence.",
                    },
                    "fluency": {
                        "status": "INSUFFICIENT_DATA",
                        "reliability": "UNRELIABLE",
                        "reliability_note": "Speaking duration is 0 seconds, preventing evaluation.",
                        "observation": "You did not provide any measurable speech activity, making it impossible to assess fluency.",
                    },
                    "pace": {
                        "status": "INSUFFICIENT_DATA",
                        "reliability": "UNRELIABLE",
                        "reliability_note": "Speaking duration is 0 seconds, preventing evaluation.",
                        "wpm_recorded": 0,
                        "observation": "You did not provide any measurable speech activity, making it impossible to assess pace.",
                    },
                    "volume": {
                        "status": "INSUFFICIENT_DATA",
                        "reliability": "UNRELIABLE",
                        "reliability_note": "Speaking duration is 0 seconds, preventing evaluation.",
                        "avg_volume_db": -20.0,
                        "observation": "You did not provide any measurable speech activity, making it impossible to assess volume.",
                    },
                    "filler_word_usage": {
                        "status": "INSUFFICIENT_DATA",
                        "reliability": "UNRELIABLE",
                        "reliability_note": "Speaking duration is 0 seconds, preventing evaluation.",
                        "filler_rate_per_min": 0.0,
                        "observation": "You did not provide any measurable speech activity, making it impossible to assess filler word usage.",
                    },
                    "pausing": {
                        "status": "INSUFFICIENT_DATA",
                        "reliability": "UNRELIABLE",
                        "reliability_note": "Speaking duration is 0 seconds, preventing evaluation.",
                        "silence_ratio_pct": 0.0,
                        "pause_count": 0,
                        "observation": "You did not provide any measurable speech activity, making it impossible to assess pausing.",
                    },
                },
                "recording_environment_context": {
                    "background_noise_level": "LOW",
                    "clipping_detected": False,
                    "speaking_duration_seconds": float(speaking_duration),
                    "noise_impact_observation": "The absence of speech activity means ambient conditions did not influence telemetry reliability.",
                },
                "key_findings": [
                    {
                        "factor": "Confidence",
                        "finding": "No speech activity was detected.",
                        "why_it_matters": "Without speech activity, it is impossible to evaluate communication effectiveness or presence.",
                    }
                ],
            }
        }

    def build_video_prompt(self, video_telemetry: Dict[str, Any]) -> Dict[str, str]:
        """
        Builds and formats the system and user prompts for universal video composure evaluation.
        """
        from fapi.ai_prep.core.llm_evaluation.prompts.video_eval import (
            SYSTEM_PROMPT,
            USER_PROMPT_TEMPLATE,
        )

        sanitized = self._sanitize_video_telemetry(video_telemetry or {})
        user_prompt = USER_PROMPT_TEMPLATE.format(
            face_visibility_pct=sanitized["face_visibility_pct"],
            eye_contact_pct=sanitized["eye_contact_pct"],
            screen_attention_pct=sanitized["screen_attention_pct"],
            distraction_level_pct=sanitized["distraction_level_pct"],
            stress_level=sanitized["stress_level"],
        )

        return {
            "system_prompt": SYSTEM_PROMPT,
            "user_prompt": user_prompt,
            "response_format": "json_object",
        }

    def _sanitize_audio_telemetry(self, raw_audio: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts, validates, and normalizes the 9 acoustic telemetry values with safe fallbacks and alias keys.
        """
        pace = raw_audio.get("speaking_pace_wpm")
        if pace is None:
            pace = raw_audio.get("words_per_minute")
        if pace is None:
            pace = raw_audio.get("wpm", 0)

        vol = raw_audio.get("avg_volume_db", -20.0)
        pitch = raw_audio.get("mean_pitch_hz", 150.0)

        silence = raw_audio.get("silence_ratio_pct")
        if silence is None:
            raw_sil = raw_audio.get("silence_ratio")
            if raw_sil is not None:
                silence = raw_sil * 100.0 if float(raw_sil) <= 1.0 else raw_sil
            else:
                silence = 0.0

        fillers = raw_audio.get("filler_rate_per_min")
        if fillers is None:
            fillers = raw_audio.get("filler_rate", 0.0)

        pauses = raw_audio.get("pause_count")
        if pauses is None:
            pauses = raw_audio.get("pauses", 0)

        duration = raw_audio.get("speaking_duration_seconds", 0.0)
        noise = raw_audio.get("background_noise_level", "LOW")
        clipping = raw_audio.get("clipping_detected", False)

        return {
            "speaking_pace_wpm": int(round(float(pace))) if pace is not None else 0,
            "avg_volume_db": round(float(vol), 1) if vol is not None else -20.0,
            "mean_pitch_hz": round(float(pitch), 1) if pitch is not None else 150.0,
            "silence_ratio_pct": round(float(silence), 1) if silence is not None else 0.0,
            "filler_rate_per_min": round(float(fillers), 1) if fillers is not None else 0.0,
            "pause_count": int(pauses) if pauses is not None else 0,
            "speaking_duration_seconds": round(float(duration), 1) if duration is not None else 0.0,
            "background_noise_level": str(noise).upper() if noise else "LOW",
            "clipping_detected": bool(clipping) if clipping is not None else False,
        }

    def _sanitize_video_telemetry(
        self, raw_video: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Extracts, validates, and normalizes the 5 visual telemetry values.
        Handles audio-only sessions gracefully.
        """
        if not raw_video or not raw_video.get("is_video_mode", False):
            return {
                "is_video_mode": False,
                "face_visibility_pct": 0.0,
                "eye_contact_pct": 0.0,
                "screen_attention_pct": 0.0,
                "distraction_level_pct": 0.0,
                "stress_level": "Normal",
            }

        stress = raw_video.get("stress_level", "Normal")
        if isinstance(stress, (int, float)):
            stress_val = round(float(stress), 1)
        else:
            stress_val = str(stress) if stress else "Normal"

        return {
            "is_video_mode": True,
            "face_visibility_pct": round(float(raw_video.get("face_visibility_pct", 0.0)), 1),
            "eye_contact_pct": round(float(raw_video.get("eye_contact_pct", 0.0)), 1),
            "screen_attention_pct": round(float(raw_video.get("screen_attention_pct", 0.0)), 1),
            "distraction_level_pct": round(float(raw_video.get("distraction_level_pct", 0.0)), 1),
            "stress_level": stress_val,
        }


# Alias for compatibility with contracts
LLMEvaluationEngine = EvalEngine
