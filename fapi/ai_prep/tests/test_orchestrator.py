"""
Orchestrator Layer Tests — AssessmentOrchestrator only.

Tests DB + engine communication logic with mocked CRUD, LLM orchestrator, and engines.
No real DB or HTTP calls are made.

NOT covered here (Srimanth's responsibility):
  - LLMOrchestrator tests (orchestrator/llm_orchestrator.py)
  - LLM Client tests (clients/llm_client.py)
  - ScoresEngine tests (core/scores_engine/)
"""
import asyncio
import json
import secrets
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fapi.ai_prep.orchestrator import assessment_orchestrator
from fapi.ai_prep.core.assessment_engine.engine import AssessmentEngine


# =============================================================================
# Fixtures & Helpers
# =============================================================================

def _make_mock_assessment(
    assessment_id=1, candidate_id=1001, status="IN_PROGRESS",
    assessment_type="INTRO", media_type="VIDEO",
):
    a = MagicMock()
    a.id = assessment_id
    a.candidate_id = candidate_id
    a.status = status
    a.assessment_type = assessment_type
    a.media_type = media_type
    a.job_description = "Senior AI Engineer"
    return a


def _make_mock_data_record(questions=None, transcript=None, audio=None, video=None):
    d = MagicMock()
    d.questions = questions if questions is not None else [{"question_text": "Explain RAG", "id": 1}]
    d.transcript = transcript if transcript is not None else {"full_text": "RAG is retrieval augmented generation."}
    d.audio_telemetry = audio if audio is not None else {"speaking_duration_seconds": 120.0, "words_per_minute": 130}
    d.video_telemetry = video if video is not None else {"is_video_mode": True, "face_visible_pct": 95.0}
    return d


def _make_valid_eval_result():
    """Simulates the dict returned by llm_orchestrator.run_evaluation()."""
    return {
        "transcript_evaluation": {
            "overall_assessment": {"readiness": "GOOD", "score": 82.0}
        },
        "audio_evaluation": {
            "summary": {"overall_readiness": "GOOD"}
        },
        "video_evaluation": None,
    }


# =============================================================================
# AssessmentOrchestrator — Context Loading
# =============================================================================


class TestAssessmentOrchestratorLoadContext:

    def test_raises_if_assessment_not_found(self):
        db = MagicMock()
        with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.crud") as mock_crud:
            mock_crud.get_assessment_by_id.return_value = None
            with pytest.raises(ValueError, match="not found"):
                assessment_orchestrator._load_assessment_context(db, assessment_id=999)

    def test_returns_flat_dict_with_all_keys(self):
        db = MagicMock()
        with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.crud") as mock_crud:
            mock_crud.get_assessment_by_id.return_value = _make_mock_assessment()
            mock_crud.get_assessment_data_by_assessment_id.return_value = _make_mock_data_record()
            mock_crud.get_candidate_llm_config.return_value = {
                "is_configured": True, "api_key": secrets.token_urlsafe(16), "provider": "openai", "model": "gpt-4o"
            }
            mock_crud.get_candidate_resume_json.return_value = {"skills": ["Python"]}

            ctx = assessment_orchestrator._load_assessment_context(db, assessment_id=1)

        assert ctx["assessment_id"] == 1
        assert ctx["candidate_id"] == 1001
        assert ctx["assessment_type"] == "INTRO"
        assert ctx["llm_config"]["is_configured"] is True
        assert "is_video_mode" in ctx["video_telemetry"]
        assert "questions" in ctx
        assert "transcript" in ctx
        assert "audio_telemetry" in ctx
        assert "resume_json" in ctx

    def test_sets_is_video_mode_true_for_video_media_type(self):
        db = MagicMock()
        with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.crud") as mock_crud:
            mock_crud.get_assessment_by_id.return_value = _make_mock_assessment(media_type="VIDEO")
            mock_crud.get_assessment_data_by_assessment_id.return_value = _make_mock_data_record(
                video={}  # no is_video_mode yet
            )
            mock_crud.get_candidate_llm_config.return_value = {"is_configured": True, "api_key": secrets.token_urlsafe(16)}
            mock_crud.get_candidate_resume_json.return_value = None

            ctx = assessment_orchestrator._load_assessment_context(db, 1)

        assert ctx["video_telemetry"]["is_video_mode"] is True

    def test_sets_is_video_mode_false_for_audio_media_type(self):
        db = MagicMock()
        with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.crud") as mock_crud:
            mock_crud.get_assessment_by_id.return_value = _make_mock_assessment(media_type="AUDIO")
            mock_crud.get_assessment_data_by_assessment_id.return_value = _make_mock_data_record(
                video={}  # no is_video_mode
            )
            mock_crud.get_candidate_llm_config.return_value = {"is_configured": True, "api_key": secrets.token_urlsafe(16)}
            mock_crud.get_candidate_resume_json.return_value = None

            ctx = assessment_orchestrator._load_assessment_context(db, 1)

        assert ctx["video_telemetry"]["is_video_mode"] is False

    def test_handles_missing_data_record_gracefully(self):
        """No telemetry data yet — should use empty dicts, not crash."""
        db = MagicMock()
        with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.crud") as mock_crud:
            mock_crud.get_assessment_by_id.return_value = _make_mock_assessment()
            mock_crud.get_assessment_data_by_assessment_id.return_value = None
            mock_crud.get_candidate_llm_config.return_value = {"is_configured": True, "api_key": secrets.token_urlsafe(16)}
            mock_crud.get_candidate_resume_json.return_value = None

            ctx = assessment_orchestrator._load_assessment_context(db, 1)

        assert ctx["questions"] == []
        assert ctx["transcript"] == {}
        assert ctx["audio_telemetry"] == {}


# =============================================================================
# AssessmentOrchestrator — Full Evaluation Pipeline
# =============================================================================


class TestAssessmentOrchestratorFullEvaluation:

    def test_fails_and_marks_failed_when_llm_config_is_none(self):
        """Rule 1: When get_candidate_llm_config returns None, mark FAILED and raise ValueError without AttributeError."""
        db = MagicMock()
        with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.crud") as mock_crud, \
             patch("fapi.ai_prep.orchestrator.assessment_orchestrator.llm_orchestrator") as mock_llm_orch:
            mock_crud.get_assessment_by_id.return_value = _make_mock_assessment()
            mock_crud.get_assessment_data_by_assessment_id.return_value = _make_mock_data_record()
            mock_crud.get_candidate_llm_config.return_value = None  # None returned!
            mock_crud.get_candidate_resume_json.return_value = None
            mock_crud.update_assessment_status.return_value = None

            with pytest.raises(ValueError, match="no active LLM"):
                asyncio.run(
                    assessment_orchestrator.run_full_evaluation(db, assessment_id=1)
                )

            # Assessment must be marked FAILED
            mock_crud.update_assessment_status.assert_called_with(db, 1, "FAILED")
            # LLM orchestrator should not be invoked
            mock_llm_orch.run_evaluation.assert_not_called()

    def test_fails_and_marks_failed_when_no_llm_key(self):
        db = MagicMock()
        with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.crud") as mock_crud:
            mock_crud.get_assessment_by_id.return_value = _make_mock_assessment()
            mock_crud.get_assessment_data_by_assessment_id.return_value = _make_mock_data_record()
            mock_crud.get_candidate_llm_config.return_value = {
                "is_configured": False, "api_key": None
            }
            mock_crud.get_candidate_resume_json.return_value = None
            mock_crud.update_assessment_status.return_value = None

            with pytest.raises(ValueError, match="no active LLM"):
                asyncio.run(
                    assessment_orchestrator.run_full_evaluation(db, assessment_id=1)
                )

            # Assessment must be marked FAILED when LLM config is missing
            mock_crud.update_assessment_status.assert_called_with(db, 1, "FAILED")

    def test_marks_failed_when_llm_orchestrator_raises(self):
        db = MagicMock()
        with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.crud") as mock_crud, \
             patch("fapi.ai_prep.orchestrator.assessment_orchestrator.llm_orchestrator") as mock_llm_orch:

            mock_crud.get_assessment_by_id.return_value = _make_mock_assessment()
            mock_crud.get_assessment_data_by_assessment_id.return_value = _make_mock_data_record()
            mock_crud.get_candidate_llm_config.return_value = {
                "is_configured": True, "api_key": secrets.token_urlsafe(16)
            }
            mock_crud.get_candidate_resume_json.return_value = None
            mock_crud.update_assessment_status.return_value = None

            mock_llm_orch.run_evaluation = AsyncMock(side_effect=RuntimeError("LLM API down"))

            with pytest.raises(RuntimeError, match="LLM API down"):
                asyncio.run(
                    assessment_orchestrator.run_full_evaluation(db, assessment_id=1)
                )

            mock_crud.update_assessment_status.assert_called_with(db, 1, "FAILED")

    def test_marks_failed_when_save_assessment_report_raises(self):
        """When save_assessment_report raises an exception, the assessment failure path is triggered."""
        db = MagicMock()
        with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.crud") as mock_crud, \
             patch("fapi.ai_prep.orchestrator.assessment_orchestrator.llm_orchestrator") as mock_llm_orch:

            mock_crud.get_assessment_by_id.return_value = _make_mock_assessment()
            mock_crud.get_assessment_data_by_assessment_id.return_value = _make_mock_data_record()
            mock_crud.get_candidate_llm_config.return_value = {
                "is_configured": True, "api_key": secrets.token_urlsafe(16)
            }
            mock_crud.get_candidate_resume_json.return_value = None
            mock_crud.save_assessment_report.side_effect = RuntimeError("Report persistence failure")
            mock_crud.update_assessment_status.return_value = None

            mock_llm_orch.run_evaluation = AsyncMock(return_value=_make_valid_eval_result())

            with pytest.raises(RuntimeError, match="Report persistence failure"):
                asyncio.run(
                    assessment_orchestrator.run_full_evaluation(db, assessment_id=1)
                )

            mock_crud.update_assessment_status.assert_called_with(db, 1, "FAILED")

    def test_marks_failed_when_marking_completed_raises(self):
        """When updating status to COMPLETED fails, attempt to mark FAILED and re-raise original exception."""
        db = MagicMock()
        with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.crud") as mock_crud, \
             patch("fapi.ai_prep.orchestrator.assessment_orchestrator.llm_orchestrator") as mock_llm_orch:

            mock_crud.get_assessment_by_id.return_value = _make_mock_assessment()
            mock_crud.get_assessment_data_by_assessment_id.return_value = _make_mock_data_record()
            mock_crud.get_candidate_llm_config.return_value = {
                "is_configured": True, "api_key": secrets.token_urlsafe(16)
            }
            mock_crud.get_candidate_resume_json.return_value = None
            mock_crud.save_assessment_report.return_value = MagicMock()
            mock_crud.update_assessment_status.side_effect = [RuntimeError("DB Status Write Failure"), None]

            mock_llm_orch.run_evaluation = AsyncMock(return_value=_make_valid_eval_result())

            with pytest.raises(RuntimeError, match="DB Status Write Failure"):
                asyncio.run(
                    assessment_orchestrator.run_full_evaluation(db, assessment_id=1)
                )

            assert mock_crud.update_assessment_status.call_args_list[-1][0] == (db, 1, "FAILED")

    def test_success_path_saves_report_and_marks_completed(self):
        db = MagicMock()
        with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.crud") as mock_crud, \
             patch("fapi.ai_prep.orchestrator.assessment_orchestrator.llm_orchestrator") as mock_llm_orch:

            mock_crud.get_assessment_by_id.return_value = _make_mock_assessment()
            mock_crud.get_assessment_data_by_assessment_id.return_value = _make_mock_data_record()
            mock_crud.get_candidate_llm_config.return_value = {
                "is_configured": True, "api_key": secrets.token_urlsafe(16), "provider": "openai"
            }
            mock_crud.get_candidate_resume_json.return_value = None
            mock_crud.save_assessment_report.return_value = MagicMock()
            mock_crud.update_assessment_status.return_value = MagicMock()

            mock_llm_orch.run_evaluation = AsyncMock(return_value=_make_valid_eval_result())

            result = asyncio.run(
                assessment_orchestrator.run_full_evaluation(db, assessment_id=1)
            )

        assert result["assessment_id"] == 1
        assert result["status"] == "COMPLETED"
        assert "report" in result
        mock_crud.save_assessment_report.assert_called_once()
        mock_crud.update_assessment_status.assert_called_with(db, 1, "COMPLETED")

    def test_report_structure_persisted_without_overall_score(self):
        """Rule 5: Persisted report contains transcript, audio, video evals and does NOT contain overall_score."""
        db = MagicMock()
        with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.crud") as mock_crud, \
             patch("fapi.ai_prep.orchestrator.assessment_orchestrator.llm_orchestrator") as mock_llm_orch:

            mock_crud.get_assessment_by_id.return_value = _make_mock_assessment()
            mock_crud.get_assessment_data_by_assessment_id.return_value = _make_mock_data_record()
            mock_crud.get_candidate_llm_config.return_value = {
                "is_configured": True, "api_key": secrets.token_urlsafe(16)
            }
            mock_crud.get_candidate_resume_json.return_value = None
            mock_crud.save_assessment_report.return_value = MagicMock()
            mock_crud.update_assessment_status.return_value = MagicMock()

            mock_llm_orch.run_evaluation = AsyncMock(return_value=_make_valid_eval_result())

            result = asyncio.run(
                assessment_orchestrator.run_full_evaluation(db, assessment_id=1)
            )

        saved_report = mock_crud.save_assessment_report.call_args[0][2]
        assert "transcript_evaluation" in saved_report
        assert "audio_evaluation" in saved_report
        assert "video_evaluation" in saved_report
        assert "overall_score" not in saved_report
        assert "overall_score" not in result


# =============================================================================
# AssessmentOrchestrator — Question Selection
# =============================================================================


class TestAssessmentOrchestratorQuestionSelection:

    def test_delegates_selection_to_assessment_engine(self):
        db = MagicMock()
        mock_q = MagicMock()
        mock_q.id = 1
        mock_q.category = "INTRO"
        mock_q.sub_category = None
        mock_q.difficulty_level = "MEDIUM"
        mock_q.question_text = "Tell me about yourself."
        mock_q.is_active = True

        with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.crud") as mock_crud:
            mock_crud.list_questions.return_value = ([mock_q], 1)
            result = assessment_orchestrator.get_questions_for_assessment(db, "INTRO", limit=5)

        assert len(result) == 1
        assert result[0]["category"] == "INTRO"
        # Candidate question schema must be clean
        assert "question_text" in result[0]

    def test_normalizes_assessment_type_variations_before_db_query(self):
        """Rule 2: TECHNICAL, technical, Technical,  TECHNICAL  must all query DB with canonical TECHNICAL."""
        db = MagicMock()
        variations = ["TECHNICAL", "technical", "Technical", " TECHNICAL "]

        with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.crud") as mock_crud:
            mock_crud.list_questions.return_value = ([], 0)

            for var in variations:
                assessment_orchestrator.get_questions_for_assessment(db, var)
                mock_crud.list_questions.assert_called_with(
                    db, category="TECHNICAL", is_active=True, limit=200
                )

    def test_returns_empty_list_when_no_questions_in_db(self):
        db = MagicMock()
        with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.crud") as mock_crud:
            mock_crud.list_questions.return_value = ([], 0)
            result = assessment_orchestrator.get_questions_for_assessment(db, "TECHNICAL")
        assert result == []

    def test_crud_called_with_correct_category_and_active_flag(self):
        db = MagicMock()
        with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.crud") as mock_crud:
            mock_crud.list_questions.return_value = ([], 0)
            assessment_orchestrator.get_questions_for_assessment(db, "SYSTEM_DESIGN")
        mock_crud.list_questions.assert_called_once_with(
            db, category="SYSTEM_DESIGN", is_active=True, limit=200
        )


# =============================================================================
# AssessmentOrchestrator — Eligibility Check
# =============================================================================


class TestAssessmentOrchestratorEligibility:

    def test_eligible_candidate_returns_eligible_true(self):
        db = MagicMock()
        with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.crud") as mock_crud:
            mock_crud.check_candidate_llm_key.return_value = {
                "status": "valid", "is_configured": True
            }
            mock_crud.check_candidate_resume.return_value = {
                "status": "valid", "has_resume": True
            }
            result = assessment_orchestrator.check_candidate_eligibility(db, candidate_id=1001)

        assert result["eligible"] is True
        assert result["candidate_id"] == 1001
        assert "llm_check" in result
        assert "resume_check" in result
        assert "message" in result

    def test_ineligible_candidate_returns_eligible_false(self):
        db = MagicMock()
        with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.crud") as mock_crud:
            mock_crud.check_candidate_llm_key.return_value = {
                "status": "failure", "is_configured": False
            }
            mock_crud.check_candidate_resume.return_value = {
                "status": "failure", "has_resume": False
            }
            result = assessment_orchestrator.check_candidate_eligibility(db, candidate_id=1002)

        assert result["eligible"] is False

    def test_crud_called_with_correct_candidate_id(self):
        db = MagicMock()
        with patch("fapi.ai_prep.orchestrator.assessment_orchestrator.crud") as mock_crud:
            mock_crud.check_candidate_llm_key.return_value = {"status": "valid", "is_configured": True}
            mock_crud.check_candidate_resume.return_value = {"status": "valid", "has_resume": True}
            assessment_orchestrator.check_candidate_eligibility(db, candidate_id=5555)

        mock_crud.check_candidate_llm_key.assert_called_once_with(db, 5555)
        mock_crud.check_candidate_resume.assert_called_once_with(db, 5555)


# =============================================================================
# AssessmentOrchestrator — Helper: _extract_transcript_text
# =============================================================================


class TestExtractTranscriptText:

    def test_extracts_full_text(self):
        text = assessment_orchestrator._extract_transcript_text({"full_text": "Hello world"})
        assert text == "Hello world"

    def test_extracts_text_alias(self):
        text = assessment_orchestrator._extract_transcript_text({"text": "Alternate key"})
        assert text == "Alternate key"

    def test_extracts_transcript_text_alias(self):
        text = assessment_orchestrator._extract_transcript_text({"transcript_text": "Third alias"})
        assert text == "Third alias"

    def test_returns_empty_string_for_empty_dict(self):
        text = assessment_orchestrator._extract_transcript_text({})
        assert text == ""

    def test_returns_empty_string_for_none(self):
        text = assessment_orchestrator._extract_transcript_text(None)
        assert text == ""

    def test_strips_whitespace(self):
        text = assessment_orchestrator._extract_transcript_text({"full_text": "  hello  "})
        assert text == "hello"
