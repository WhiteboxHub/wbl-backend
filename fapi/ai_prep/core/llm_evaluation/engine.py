# Core Engine 4 — LLM Evaluation Engine (Prompt Builder)


import importlib
import json
import logging
from typing import Any, Dict, Optional

from fapi.ai_prep.core.llm_evaluation.prompts import (
    audio_prompt,
    intro_prompt,
    video_prompt,
)

logger = logging.getLogger(__name__)


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

        # 2. Dispatch to assessment-specific prompt module.
        # Module naming convention: {template_module_name}_prompt.py (e.g. intro_prompt.py).
        # Falls back to intro_prompt when a type-specific module has not been built yet.
        module_path = (
            f"fapi.ai_prep.core.llm_evaluation.prompts.{template_module_name}_prompt"
        )
        try:
            prompt_module = importlib.import_module(module_path)
            _system_prompt: str = prompt_module.SYSTEM_PROMPT
            _user_prompt_template: str = prompt_module.USER_PROMPT_TEMPLATE
            using_fallback = False
        except (ImportError, AttributeError):
            logger.warning(
                "[EvalEngine] No dedicated prompt module for assessment_type='%s' "
                "(looked for '%s'). Falling back to intro_prompt.",
                assessment_type,
                module_path,
            )
            _system_prompt = intro_prompt.SYSTEM_PROMPT
            _user_prompt_template = intro_prompt.USER_PROMPT_TEMPLATE
            using_fallback = True

        user_prompt = _user_prompt_template.format(
            resume_json=timeline_formatted,
            transcript_text=transcript_text.strip() or "[No spoken transcript captured]",
        )

        # Prepend a role-specific header for non-intro types (including fallback cases)
        # so the LLM evaluates the correct interview context.
        adapted_system_prompt = _system_prompt
        if template_module_name != "intro" or using_fallback:
            role_title = normalized_type.replace("_", " ").title()
            adapted_system_prompt = (
                f"You are an expert {role_title} interview evaluator assessing "
                f"candidate responses for a {role_title} round.\n\n"
                + _system_prompt
            )

        return {
            "system_prompt": adapted_system_prompt,
            "user_prompt": user_prompt,
            "response_format": "json_object",
        }

    def build_audio_prompt(self, audio_telemetry: Dict[str, Any]) -> Dict[str, str]:
        """
        Builds and formats the system and user prompts for universal audio delivery evaluation.
        """
        sanitized = self._sanitize_audio_telemetry(audio_telemetry or {})
        user_prompt = audio_prompt.USER_PROMPT_TEMPLATE.format(
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
            "system_prompt": audio_prompt.SYSTEM_PROMPT,
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
            duration = audio_telemetry.get("duration_seconds")
        if duration is None:
            duration = audio_telemetry.get("duration")
        if duration is None:
            duration = audio_telemetry.get("total_audio_duration_seconds", 0.0)
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
        Used when no audio recording, 0-second speech, or telemetry evaluation fallback occurs.
        """
        try:
            dur_val = float(speaking_duration) if speaking_duration and speaking_duration > 0 else 0.0
        except (ValueError, TypeError):
            dur_val = 0.0

        dur_str = f"{int(dur_val)} seconds" if dur_val.is_integer() else f"{dur_val:.1f} seconds"

        if dur_val > 0:
            confidence_rationale = (
                f"You provided a speaking duration of {dur_str}, but audio telemetry was insufficient or could not be evaluated."
            )
            executive_summary = (
                f"Audio telemetry recorded {dur_str} of speech, but data was insufficient for a complete vocal evaluation."
            )
            reliability_note = f"Speaking duration of {dur_str} was insufficient for reliable factor evaluation."
            vocal_obs = f"Telemetry data for {dur_str} did not provide enough reliable signal to assess vocal presence."
            fluency_obs = f"Telemetry data for {dur_str} did not provide enough reliable signal to assess fluency."
            pace_obs = f"Telemetry data for {dur_str} did not provide enough reliable signal to assess pace."
            volume_obs = f"Telemetry data for {dur_str} did not provide enough reliable signal to assess volume."
            filler_obs = f"Telemetry data for {dur_str} did not provide enough reliable signal to assess filler word usage."
            pausing_obs = f"Telemetry data for {dur_str} did not provide enough reliable signal to assess pausing."
            noise_impact = f"Ambient conditions and telemetry reliability could not be fully assessed over the {dur_str} recording."
            key_finding = f"Recorded {dur_str} of audio, but telemetry signal was insufficient for comprehensive analysis."
            why_matters = "A complete audio telemetry stream is necessary to evaluate vocal presence, pacing, and communication clarity."
        else:
            confidence_rationale = "You provided a speaking duration of 0 seconds, which is insufficient for reliable telemetry evaluation."
            executive_summary = "The audio telemetry indicates no measurable speech activity, resulting in insufficient data for evaluation."
            reliability_note = "Speaking duration is 0 seconds, preventing evaluation."
            vocal_obs = "You did not provide any measurable speech activity, making it impossible to assess vocal presence."
            fluency_obs = "You did not provide any measurable speech activity, making it impossible to assess fluency."
            pace_obs = "You did not provide any measurable speech activity, making it impossible to assess pace."
            volume_obs = "You did not provide any measurable speech activity, making it impossible to assess volume."
            filler_obs = "You did not provide any measurable speech activity, making it impossible to assess filler word usage."
            pausing_obs = "You did not provide any measurable speech activity, making it impossible to assess pausing."
            noise_impact = "The absence of speech activity means ambient conditions did not influence telemetry reliability."
            key_finding = "No speech activity was detected."
            why_matters = "Without speech activity, it is impossible to evaluate communication effectiveness or presence."

        return {
            "audio_evaluation": {
                "summary": {
                    "overall_readiness": "INSUFFICIENT_DATA",
                    "confidence_in_reading": "LOW",
                    "confidence_rationale": confidence_rationale,
                    "executive_summary": executive_summary,
                    "primary_vocal_strength": None,
                    "primary_vocal_gap": None,
                },
                "factors": {
                    "confidence_vocal_presence": {
                        "status": "INSUFFICIENT_DATA",
                        "reliability": "UNRELIABLE",
                        "reliability_note": reliability_note,
                        "observation": vocal_obs,
                    },
                    "fluency": {
                        "status": "INSUFFICIENT_DATA",
                        "reliability": "UNRELIABLE",
                        "reliability_note": reliability_note,
                        "observation": fluency_obs,
                    },
                    "pace": {
                        "status": "INSUFFICIENT_DATA",
                        "reliability": "UNRELIABLE",
                        "reliability_note": reliability_note,
                        "wpm_recorded": 0,
                        "observation": pace_obs,
                    },
                    "volume": {
                        "status": "INSUFFICIENT_DATA",
                        "reliability": "UNRELIABLE",
                        "reliability_note": reliability_note,
                        "avg_volume_db": -20.0,
                        "observation": volume_obs,
                    },
                    "filler_word_usage": {
                        "status": "INSUFFICIENT_DATA",
                        "reliability": "UNRELIABLE",
                        "reliability_note": reliability_note,
                        "filler_rate_per_min": 0.0,
                        "observation": filler_obs,
                    },
                    "pausing": {
                        "status": "INSUFFICIENT_DATA",
                        "reliability": "UNRELIABLE",
                        "reliability_note": reliability_note,
                        "silence_ratio_pct": 0.0,
                        "pause_count": 0,
                        "observation": pausing_obs,
                    },
                },
                "recording_environment_context": {
                    "background_noise_level": "LOW",
                    "clipping_detected": False,
                    "speaking_duration_seconds": float(dur_val),
                    "noise_impact_observation": noise_impact,
                },
                "key_findings": [
                    {
                        "factor": "Confidence",
                        "finding": key_finding,
                        "why_it_matters": why_matters,
                    }
                ],
            }
        }

    def build_video_prompt(self, video_telemetry: Dict[str, Any]) -> Dict[str, str]:
        """
        Builds and formats the system and user prompts for universal video composure evaluation.
        """
        sanitized = self._sanitize_video_telemetry(video_telemetry or {})
        user_prompt = video_prompt.USER_PROMPT_TEMPLATE.format(
            face_visibility_pct=sanitized["face_visibility_pct"],
            eye_contact_pct=sanitized["eye_contact_pct"],
            screen_attention_pct=sanitized["screen_attention_pct"],
            distraction_level_pct=sanitized["distraction_level_pct"],
            stress_level=sanitized["stress_level"],
        )

        return {
            "system_prompt": video_prompt.SYSTEM_PROMPT,
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

        # Extract duration first with all common alias keys
        duration = (
            raw_audio.get("speaking_duration_seconds")
            if raw_audio.get("speaking_duration_seconds") is not None
            else raw_audio.get("duration_seconds")
        )
        if duration is None:
            duration = raw_audio.get("duration")
        if duration is None:
            duration = raw_audio.get("total_audio_duration_seconds", 0.0)

        try:
            dur_float = float(duration) if duration is not None else 0.0
        except (ValueError, TypeError):
            dur_float = 0.0

        # Filler words rate calculation with fallback from count
        fillers = raw_audio.get("filler_rate_per_min")
        if fillers is None:
            fillers = raw_audio.get("filler_rate")
        if fillers is None:
            count = raw_audio.get("filler_words_count") or raw_audio.get("filler_count", 0)
            try:
                count_val = float(count) if count is not None else 0.0
            except (ValueError, TypeError):
                count_val = 0.0
            fillers = ((count_val / dur_float) * 60.0) if dur_float > 0 else 0.0

        pauses = raw_audio.get("pause_count")
        if pauses is None:
            pauses = raw_audio.get("pauses", 0)

        noise = raw_audio.get("background_noise_level", "LOW")
        clipping = raw_audio.get("clipping_detected", False)

        return {
            "speaking_pace_wpm": int(round(float(pace))) if pace is not None else 0,
            "avg_volume_db": round(float(vol), 1) if vol is not None else -20.0,
            "mean_pitch_hz": round(float(pitch), 1) if pitch is not None else 150.0,
            "silence_ratio_pct": round(float(silence), 1) if silence is not None else 0.0,
            "filler_rate_per_min": round(float(fillers), 1) if fillers is not None else 0.0,
            "pause_count": int(pauses) if pauses is not None else 0,
            "speaking_duration_seconds": round(dur_float, 1),
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
