# fapi/ai_prep/core/video_processor_engine/video_to_audio.py
import os
import subprocess
import logging
from typing import Optional
from fapi.ai_prep.config import settings

logger = logging.getLogger(__name__)

class AudioExtractionError(Exception):
    """Raised when extracting audio from video fails."""
    pass

def extract_audio_from_video(
    video_path: str,
    output_audio_path: Optional[str] = None,
    sample_rate: int = 16000,
) -> str:
    """
    Extracts a 16kHz mono audio WAV file from a video recording.
    Guarantees output size < 25MB for OpenAI Whisper ingestion.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Input video file not found: {video_path}")

    if output_audio_path is None:
        base, _ = os.path.splitext(video_path)
        output_audio_path = f"{base}_audio.wav"

    ffmpeg_bin = getattr(settings, "FFMPEG_PATH", "ffmpeg")
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", video_path,
        "-vn",                   # Drop video stream
        "-acodec", "pcm_s16le",  # Uncompressed standard 16-bit PCM WAV
        "-ar", str(sample_rate), # 16kHz sample rate optimal for Whisper & AudioDSP
        "-ac", "1",              # Mono channel
        output_audio_path,
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        if res.returncode == 0 and os.path.exists(output_audio_path) and os.path.getsize(output_audio_path) > 0:
            logger.info("Successfully extracted audio from video: %s -> %s (%d bytes)", video_path, output_audio_path, os.path.getsize(output_audio_path))
            return output_audio_path
    except Exception as exc:
        logger.warning("FFmpeg extraction failed (%s), falling back to PyAV demuxer...", exc)

    # PyAV Fallback (if ffmpeg executable is missing on host system)
    try:
        import av
        import soundfile as sf
        import numpy as np

        container = av.open(video_path)
        audio_stream = next((s for s in container.streams if s.type == "audio"), None)
        if audio_stream is None:
            raise AudioExtractionError(f"No audio stream found in video container: {video_path}")

        resampler = av.AudioResampler(format="s16", layout="mono", rate=sample_rate)
        frames = []
        for frame in container.decode(audio_stream):
            for rframe in resampler.resample(frame):
                frames.append(rframe.to_ndarray())

        if not frames:
            raise AudioExtractionError("Decoded audio stream contains zero frames.")

        audio_data = np.concatenate([np.ravel(f) for f in frames], axis=0)
        sf.write(output_audio_path, audio_data, sample_rate, subtype="PCM_16")
        return output_audio_path
    except Exception as pyav_err:
        raise AudioExtractionError(f"Both FFmpeg and PyAV audio extraction failed: {pyav_err}") from pyav_err
