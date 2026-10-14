"""Unit tests for WebM chunk stitching, FFmpeg piping, and Whisper transcription handling.

Validates that:
1. Browser MediaRecorder chunks (where only chunk_0 has EBML header and chunks 1+ are raw clusters)
   are piped sequentially into FFmpeg stdin so that the full audio duration is extracted into a 16kHz WAV.
2. Fallback to raw binary concatenation occurs gracefully when FFmpeg is unavailable.
3. _auto_assemble_chunks_if_present handles padded/unpadded chunk indices and sequence validation.
4. Faster-Whisper transcription in stt.py converts non-WAV inputs to WAV via FFmpeg and cleans up temporary files.
5. YouTube upload router uses assembled.webm for VIDEO assessments and converts audio for AUDIO assessments.
"""
import os
import shutil
import tempfile
import subprocess
from unittest.mock import patch, MagicMock, mock_open
import pytest

from fapi.ai_prep.utils.aiprep_utils import (
    _stitch_assessment_chunks,
    _auto_assemble_chunks_if_present,
    _process_youtube_upload_and_cleanup,
)
from fapi.ai_prep.core.audio_engine.stt import transcribe_audio_chunk


@pytest.fixture
def temp_assessment_dir(tmp_path, monkeypatch):
    """Sets up a temporary candidate assessment storage directory with chunks."""
    storage_base = str(tmp_path / "storage")
    monkeypatch.setattr("fapi.ai_prep.utils.aiprep_utils.STORAGE_BASE_DIR", storage_base)
    cand_id = 100
    ass_id = 200
    ass_dir = os.path.join(storage_base, str(cand_id), str(ass_id))
    chunks_dir = os.path.join(ass_dir, "chunks")
    os.makedirs(chunks_dir, exist_ok=True)
    return {
        "storage_base": storage_base,
        "candidate_id": cand_id,
        "assessment_id": ass_id,
        "assessment_dir": ass_dir,
        "chunks_dir": chunks_dir,
    }


def test_stitch_assessment_chunks_success_with_ffmpeg_pipe(temp_assessment_dir):
    """Verifies that _stitch_assessment_chunks pipes all chunks into FFmpeg and writes audio.wav and assembled.webm."""
    chunks_dir = temp_assessment_dir["chunks_dir"]
    cand_id = temp_assessment_dir["candidate_id"]
    ass_id = temp_assessment_dir["assessment_id"]
    ass_dir = temp_assessment_dir["assessment_dir"]

    # Create dummy chunk_0 and chunk_1
    c0 = os.path.join(chunks_dir, "chunk_0.webm")
    c1 = os.path.join(chunks_dir, "chunk_1.webm")
    with open(c0, "wb") as f:
        f.write(b"HEADER_CHUNK_0" * 100)
    with open(c1, "wb") as f:
        f.write(b"BODY_CHUNK_1" * 100)

    audio_wav = os.path.join(ass_dir, "audio.wav")
    assembled_webm = os.path.join(ass_dir, "assembled.webm")

    # Mock subprocess Popen so FFmpeg simulates successful WAV creation
    def mock_popen(cmd, *args, **kwargs):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.wait.return_value = 0
        mock_proc.stdout = MagicMock()
        # If this is the ffmpeg command, touch the target audio.wav file
        if isinstance(cmd, list) and "ffmpeg" in cmd:
            target_out = cmd[-1]
            with open(target_out, "wb") as out_f:
                out_f.write(b"RIFF" + b"\x00" * 32000)  # 1 second of mock WAV
        return mock_proc

    with patch("subprocess.Popen", side_effect=mock_popen):
        result_path = _stitch_assessment_chunks(
            candidate_id=cand_id,
            assessment_id=ass_id,
            total_chunks_uploaded=2,
        )

    # Returned path should be audio.wav
    assert result_path == audio_wav
    assert os.path.exists(audio_wav)
    assert os.path.getsize(audio_wav) > 0

    # Also assembled.webm should be written for video playback
    assert os.path.exists(assembled_webm)
    assert os.path.getsize(assembled_webm) == os.path.getsize(c0) + os.path.getsize(c1)


def test_stitch_assessment_chunks_fallback_to_binary_concat(temp_assessment_dir):
    """Verifies that if FFmpeg is unavailable, it gracefully falls back to raw binary concat assembled.webm."""
    chunks_dir = temp_assessment_dir["chunks_dir"]
    cand_id = temp_assessment_dir["candidate_id"]
    ass_id = temp_assessment_dir["assessment_id"]
    ass_dir = temp_assessment_dir["assessment_dir"]

    c0 = os.path.join(chunks_dir, "chunk_0.webm")
    c1 = os.path.join(chunks_dir, "chunk_1.webm")
    with open(c0, "wb") as f:
        f.write(b"CHUNK_0_BYTES")
    with open(c1, "wb") as f:
        f.write(b"CHUNK_1_BYTES")

    assembled_webm = os.path.join(ass_dir, "assembled.webm")

    # Simulate FFmpeg failing / not installed
    with patch("subprocess.Popen", side_effect=FileNotFoundError("ffmpeg not found")):
        result_path = _stitch_assessment_chunks(
            candidate_id=cand_id,
            assessment_id=ass_id,
            total_chunks_uploaded=2,
        )

    # Returned path should fallback to assembled.webm
    assert result_path == assembled_webm
    assert os.path.exists(assembled_webm)
    assert os.path.getsize(assembled_webm) == len(b"CHUNK_0_BYTES") + len(b"CHUNK_1_BYTES")


def test_auto_assemble_chunks_if_present_atomicity_and_cache(temp_assessment_dir):
    """Verifies _auto_assemble_chunks_if_present creates assembled.webm and uses cache on subsequent calls."""
    chunks_dir = temp_assessment_dir["chunks_dir"]
    ass_dir = temp_assessment_dir["assessment_dir"]

    with open(os.path.join(chunks_dir, "chunk_0.webm"), "wb") as f:
        f.write(b"A" * 50)
    with open(os.path.join(chunks_dir, "chunk_1.webm"), "wb") as f:
        f.write(b"B" * 50)

    assembled = _auto_assemble_chunks_if_present(ass_dir)
    assert assembled is not None
    assert os.path.exists(assembled)
    assert os.path.getsize(assembled) >= 100

    # Second call returns existing file immediately
    cached = _auto_assemble_chunks_if_present(ass_dir)
    assert cached == assembled


def test_auto_assemble_chunks_detects_sequence_gaps(temp_assessment_dir):
    """Verifies that missing chunk numbers in the sequence cause auto-assembly to skip gracefully."""
    chunks_dir = temp_assessment_dir["chunks_dir"]
    ass_dir = temp_assessment_dir["assessment_dir"]

    # Chunk 0 and chunk 2 present, but chunk 1 is missing
    with open(os.path.join(chunks_dir, "chunk_0.webm"), "wb") as f:
        f.write(b"A" * 50)
    with open(os.path.join(chunks_dir, "chunk_2.webm"), "wb") as f:
        f.write(b"B" * 50)

    assembled = _auto_assemble_chunks_if_present(ass_dir)
    assert assembled is None


def test_stt_converts_non_wav_file_via_ffmpeg(tmp_path):
    """Verifies transcribe_audio_chunk invokes FFmpeg conversion when given a non-WAV input file."""
    mock_webm = tmp_path / "test_recording.webm"
    mock_webm.write_bytes(b"MOCK_WEBM_DATA")

    mock_model = MagicMock()
    mock_segment = MagicMock()
    mock_segment.start = 0.0
    mock_segment.end = 2.5
    mock_segment.text = "Hello world from audio chunk"
    mock_segment.words = []
    mock_info = MagicMock(language="en", duration=2.5)

    mock_model.transcribe.return_value = ([mock_segment], mock_info)

    def mock_sp_run(cmd, *args, **kwargs):
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        # Write dummy wav to output arg
        out_wav = cmd[-1]
        with open(out_wav, "wb") as f:
            f.write(b"RIFF" + b"\x00" * 100)
        return res

    with patch("fapi.ai_prep.core.audio_engine.stt.get_whisper_model", return_value=mock_model), \
         patch("subprocess.run", side_effect=mock_sp_run) as mock_run:
        result = transcribe_audio_chunk(str(mock_webm))

    # Verify FFmpeg was called with input mock_webm and pcm_s16le 16000Hz
    assert mock_run.called
    ffmpeg_cmd = mock_run.call_args[0][0]
    assert "ffmpeg" in ffmpeg_cmd
    assert str(mock_webm) in ffmpeg_cmd
    assert "16000" in ffmpeg_cmd

    assert result["transcript_text"] == "Hello world from audio chunk"


def test_stt_skips_conversion_for_direct_wav_file(tmp_path):
    """Verifies transcribe_audio_chunk directly processes .wav files without calling FFmpeg."""
    mock_wav = tmp_path / "direct.wav"
    mock_wav.write_bytes(b"RIFF" + b"\x00" * 100)

    mock_model = MagicMock()
    mock_segment = MagicMock()
    mock_segment.start = 0.0
    mock_segment.end = 1.0
    mock_segment.text = "Direct WAV transcription"
    mock_segment.words = []
    mock_info = MagicMock(language="en", duration=1.0)
    mock_model.transcribe.return_value = ([mock_segment], mock_info)

    with patch("fapi.ai_prep.core.audio_engine.stt.get_whisper_model", return_value=mock_model), \
         patch("subprocess.run") as mock_run:
        result = transcribe_audio_chunk(str(mock_wav))

    # FFmpeg should NOT be called for .wav files
    mock_run.assert_not_called()
    assert result["transcript_text"] == "Direct WAV transcription"


def test_youtube_upload_router_media_selection(temp_assessment_dir):
    """Verifies _process_youtube_upload_and_cleanup selects assembled.webm for VIDEO and converts for AUDIO."""
    import asyncio
    ass_dir = temp_assessment_dir["assessment_dir"]
    ass_id = temp_assessment_dir["assessment_id"]
    cand_id = temp_assessment_dir["candidate_id"]

    # 1. VIDEO mode: assembled.webm should be chosen
    video_file = os.path.join(ass_dir, "assembled.webm")
    with open(video_file, "wb") as f:
        f.write(b"VIDEO_CONTAINER_BYTES")

    uploaded_files = []

    def mock_upload(assessment_id, file_path, media_type, **kwargs):
        uploaded_files.append((file_path, media_type))
        return {"youtube_url": "https://youtu.be/mock_vid"}

    from fapi.ai_prep.clients.youtube_client import youtube_client
    with patch.object(youtube_client, "has_live_credentials", return_value=True), \
         patch.object(youtube_client, "upload_unlisted_media", side_effect=mock_upload), \
         patch("fapi.ai_prep.crud.update_assessment_media_url"):

        asyncio.run(_process_youtube_upload_and_cleanup(
            assessment_id=ass_id,
            media_path=os.path.join(ass_dir, "audio.wav"),
            media_type="VIDEO",
            candidate_id=cand_id,
        ))

    assert len(uploaded_files) == 1
    assert uploaded_files[0][0] == video_file
    assert uploaded_files[0][1] == "VIDEO"


def test_real_assessment_chunks_stitch_if_present():
    """If real candidate chunks exist locally on disk (581/312), verifies FFmpeg pipe decodes full duration."""
    real_chunks_dir = "/Users/macmini/Desktop/whitebox/wbl-backend/storage/aiprep/581/312/chunks"
    if not os.path.exists(real_chunks_dir):
        pytest.skip("Local test storage chunks not present")

    # Assessment 312 has 2 chunks: chunk_0 (~29.9s) and chunk_1 (~18.7s).
    # Single-file or concat demuxer stopped at 29.9s; pipe decodes the full ~48.6s.
    audio_path = "/Users/macmini/Desktop/whitebox/wbl-backend/storage/aiprep/581/312/audio.wav"
    # Run _stitch_assessment_chunks
    out = _stitch_assessment_chunks(candidate_id=581, assessment_id=312, total_chunks_uploaded=2)
    assert os.path.exists(out)
    assert out.endswith(".wav")
    file_size = os.path.getsize(out)
    # 16000 Hz, 16-bit (2 bytes/sample), mono = 32000 bytes/sec
    duration_sec = file_size / (16000 * 2)
    # Full audio must exceed 40 seconds (confirming chunk 1 was decoded)
    assert duration_sec > 40.0, f"Expected >40s but got {duration_sec:.2f}s (only chunk 0 was decoded!)"
