"""
Audio Metrics Engine: Central orchestrator combining acoustic signal metrics and STT transcript metrics.
"""
import os
import logging
from typing import Dict, Any, Optional, List
from .providers import get_transcription_provider, BaseTranscriptionProvider
from .audio_metrics import calculate_audio_metrics
from .transcript_metrics import calculate_transcript_metrics

logger = logging.getLogger("wbl.ai_prep.audio_engine.metrics_engine")


class AudioMetricsEngine:
    """Central orchestration engine for audio telemetry and speech analytics."""

    @classmethod
    def process_audio_file(
        cls,
        audio_path: str,
        model_size: str = "base",
        provider_name: Optional[str] = None,
        precomputed_transcript_text: Optional[str] = None,
        precomputed_word_timestamps: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # 1. Obtain STT results (reuse live results or run once)
        provider: BaseTranscriptionProvider = get_transcription_provider(provider_name)
        logger.info(f"Running transcription using provider: '{provider.provider_name}' on audio: {audio_path}")
        
        stt_result = provider.transcribe(
            audio_path=audio_path,
            model_size=model_size,
            precomputed_transcript_text=precomputed_transcript_text,
            precomputed_word_timestamps=precomputed_word_timestamps,
        )
        transcript_text = stt_result.get("transcript_text", "")
        word_timestamps = stt_result.get("word_timestamps", [])
        total_duration = stt_result.get("duration", 0.0)

        # 2. Acoustic waveform metrics
        acoustic_metrics = calculate_audio_metrics(audio_path)
        actual_total_duration = acoustic_metrics.get("total_audio_duration_seconds", total_duration) or total_duration

        # 3. Transcript speech & timing metrics
        transcript_metrics = calculate_transcript_metrics(
            transcript_text=transcript_text,
            word_timestamps=word_timestamps,
            total_recording_duration=actual_total_duration,
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
            "total_audio_duration_seconds": actual_total_duration,
        }

        # 5. Explicitly discard temporary word timestamps
        del word_timestamps

        return {
            "spoken_content": {
                "transcript_text": transcript_text,
            },
            "audio_telemetry": audio_telemetry
        }
