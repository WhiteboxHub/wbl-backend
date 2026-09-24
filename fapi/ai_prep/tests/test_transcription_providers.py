import os
import pytest
from unittest.mock import patch, MagicMock
from fapi.ai_prep.core.audio_engine.providers import (
    get_transcription_provider,
    WhisperTranscriptionProvider,
    SocketTranscriptionProvider,
    BrowserTranscriptionProvider,
    InvalidProviderConfigError,
    TranscriptionProviderError,
)
from fapi.ai_prep.core.audio_engine.metrics_engine import AudioMetricsEngine


def test_provider_factory_selection():
    # Whisper selection
    p1 = get_transcription_provider("whisper")
    assert isinstance(p1, WhisperTranscriptionProvider)

    # Socket selection
    p2 = get_transcription_provider("socket")
    assert isinstance(p2, SocketTranscriptionProvider)

    # Browser selection
    p3 = get_transcription_provider("browser")
    assert isinstance(p3, BrowserTranscriptionProvider)


def test_invalid_provider_raises_error():
    with pytest.raises(InvalidProviderConfigError):
        get_transcription_provider("unsupported_provider_xyz")

def test_socket_provider_raises_when_not_connected():
    provider = SocketTranscriptionProvider()
    with pytest.raises(TranscriptionProviderError):
        provider.transcribe(audio_path="dummy.wav")


def test_whisper_provider_missing_file_raises():
    provider = WhisperTranscriptionProvider()
    with pytest.raises(FileNotFoundError):
        provider.transcribe(audio_path="non_existent_file_123.wav")


def test_browser_provider_empty_string():
    provider = BrowserTranscriptionProvider()
    res = provider.transcribe(precomputed_transcript_text="")
    assert res["transcript_text"] == ""
    assert res["word_timestamps"] == []



@patch("fapi.ai_prep.core.audio_engine.providers.transcribe_audio")
def test_whisper_provider_transcribe(mock_stt, tmp_path):
    mock_audio = tmp_path / "sample.wav"
    mock_audio.write_bytes(b"RIFF dummy wav data")

    mock_stt.return_value = {
        "transcript_text": "Hello world this is a test.",
        "word_timestamps": [{"word": "Hello", "start": 0.0, "end": 0.5}],
        "duration": 2.5
    }

    provider = WhisperTranscriptionProvider()
    res = provider.transcribe(audio_path=str(mock_audio))

    assert res["transcript_text"] == "Hello world this is a test."
    assert len(res["word_timestamps"]) == 1
    assert res["duration"] == 2.5


def test_browser_provider_transcribe():
    provider = BrowserTranscriptionProvider()
    precomputed_text = "I am speaking in the browser."
    precomputed_words = [{"word": "I", "start": 0.0, "end": 0.2}]
    
    res = provider.transcribe(
        precomputed_transcript_text=precomputed_text,
        precomputed_word_timestamps=precomputed_words,
        duration=3.0
    )
    assert res["transcript_text"] == precomputed_text
    assert res["word_timestamps"] == precomputed_words


@patch("fapi.ai_prep.core.audio_engine.metrics_engine.calculate_audio_metrics")
@patch("fapi.ai_prep.core.audio_engine.metrics_engine.calculate_transcript_metrics")
@patch("fapi.ai_prep.core.audio_engine.providers.transcribe_audio")
def test_audio_metrics_engine_pipeline(mock_stt, mock_t_metrics, mock_a_metrics, tmp_path):
    mock_audio = tmp_path / "sample.wav"
    mock_audio.write_bytes(b"RIFF dummy wav")

    mock_stt.return_value = {
        "transcript_text": "Test transcript",
        "word_timestamps": [{"word": "Test", "start": 0.0, "end": 0.5}],
        "duration": 5.0
    }
    mock_a_metrics.return_value = {
        "avg_volume_db": -20.0,
        "mean_pitch_hz": 150.0,
        "silence_ratio": 0.1,
        "background_noise_level": "LOW",
        "clipping_detected": False,
        "total_audio_duration_seconds": 5.0
    }
    mock_t_metrics.return_value = {
        "filler_rate_per_min": 0.0,
        "filler_count": 0,
        "filler_breakdown": {},
        "pause_count": 0,
        "wpm": 120.0,
        "speaking_duration_seconds": 4.5
    }

    result = AudioMetricsEngine.process_audio_file(
        audio_path=str(mock_audio),
        provider_name="whisper"
    )

    assert result["spoken_content"]["transcript_text"] == "Test transcript"
    assert result["audio_telemetry"]["wpm"] == 120.0
    assert result["audio_telemetry"]["avg_volume_db"] == -20.0
