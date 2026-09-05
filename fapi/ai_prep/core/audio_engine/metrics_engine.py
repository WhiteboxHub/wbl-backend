"""
Audio Metrics Engine: Central orchestrator combining acoustic signal metrics and STT transcript metrics.
Conforms to contracts/all_json_schemas.json and contracts/end_to_end_flow.md
"""
import os
import logging
from typing import Dict, Any
from .stt import transcribe_audio
from .audio_metrics import calculate_audio_metrics
from .transcript_metrics import calculate_transcript_metrics

logger = logging.getLogger("wbl.ai_prep.audio_engine.metrics_engine")


class AudioMetricsEngine:
    """
    Central orchestration engine for audio telemetry and speech analytics.
    """

    @classmethod
    def process_audio_file(
        cls,
        audio_path: str,
        model_size: str = "base"
    ) -> Dict[str, Any]:
        """
        Processes an audio file end-to-end:
        1. Transcribes via Faster-Whisper -> spoken_content & word_timestamps
        2. Computes Acoustic metrics (RMS dBFS, F0 Pitch, VAD Silence, Noise Level)
        3. Computes Transcript metrics (WPM, Fillers, Pauses, Active Speaking Duration)
        4. Consolidates all metrics into the final audio_telemetry payload.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # 1. Transcribe
        stt_result = transcribe_audio(audio_path=audio_path, model_size=model_size)
        transcript_text = stt_result["transcript_text"]
        word_timestamps = stt_result["word_timestamps"]
        total_duration = stt_result.get("duration", 0.0)

        # 2. Acoustic waveform metrics
        acoustic_metrics = calculate_audio_metrics(audio_path)

        # 3. Transcript speech & timing metrics
        transcript_metrics = calculate_transcript_metrics(
            transcript_text=transcript_text,
            word_timestamps=word_timestamps,
            total_recording_duration=total_duration or acoustic_metrics.get("total_audio_duration_seconds", 0.0),
        )

        # 4. Consolidate Audio Telemetry
        audio_telemetry = {
            "avg_volume_db": acoustic_metrics["avg_volume_db"],
            "mean_pitch_hz": acoustic_metrics["mean_pitch_hz"],
            "silence_ratio": acoustic_metrics["silence_ratio"],
            "background_noise_level": acoustic_metrics["background_noise_level"],
            "clipping_detected": acoustic_metrics["clipping_detected"],
            "filler_rate_per_min": transcript_metrics["filler_rate_per_min"],
            "filler_count": transcript_metrics["filler_count"],
            "filler_breakdown": transcript_metrics["filler_breakdown"],
            "pause_count": transcript_metrics["pause_count"],
            "wpm": transcript_metrics["wpm"],
            "speaking_duration_seconds": transcript_metrics["speaking_duration_seconds"],
            "total_audio_duration_seconds": acoustic_metrics.get("total_audio_duration_seconds", total_duration),
        }

        return {
            "spoken_content": {
                "transcript_text": transcript_text,
                "word_timestamps": word_timestamps,
            },
            "audio_telemetry": audio_telemetry
        }
