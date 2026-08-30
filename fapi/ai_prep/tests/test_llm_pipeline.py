"""Unit and integration tests for Prompt Assembly and the LLM Pipeline Worker."""
import json
import unittest
from unittest.mock import MagicMock, patch

from fapi.ai_prep.models import (
    AiPrepAssessmentORM,
    AiPrepQuestionBankORM,
    AiPrepAssessmentQuestionORM,
    AiPrepTranscriptORM,
    AiPrepAudioTelemetryORM,
    AiPrepVisionTelemetryORM,
    AssessmentTypeEnum,
    AssessmentStatusEnum,
    CoachingBandEnum,
    BackgroundNoiseLevelEnum,
)
from fapi.ai_prep.services.prompt_service import assemble_prompt, PROMPT_MODULE_MAP


SAMPLE_VALID_REPORT = {
    "scores_breakdown_json": {
        "ai_engineering": {"score": 85, "sub_scores": {"llm": 85}},
        "core_engineering": {"score": 80, "sub_scores": {"design": 80}},
        "non_technical": {"score": 75, "sub_scores": {"clarity": 75}},
        "business_acumen": {"score": 70, "sub_scores": {"framing": 70}}
    },
    "technical_analysis_json": {
        "summary": "Solid technical depth",
        "strengths": ["Clear RAG explanation"],
        "areas_for_improvement": ["Fine-tuning depth"]
    },
    "non_technical_analysis_json": {
        "communication_summary": "Clear communication",
        "structure_quality": "High STAR adherence",
        "confidence_notes": "Very confident"
    },
    "coaching_suggestions_json": [
        {
            "priority": 1,
            "dimension": "AI Engineering",
            "area": "RAG",
            "suggestion": "Study RAGAS",
            "evidence": "Mentioned accuracy"
        }
    ],
    "signal_timeline_json": [{"question_index": 1, "energy": 80, "clarity": 85}],
    "transcript_evidence_json": [
        {"quote": "I built RAG", "timestamp_s": 10.5, "dimension": "AI", "observation": "Good"}
    ],
    "gaps_to_validate_json": [{"topic": "Quantization", "reason": "Not discussed"}],
    "improvements_json": [
        {"priority": 1, "topic": "RAG", "effort": "low", "rationale": "High impact"}
    ]
}


class TestPromptAssembly(unittest.TestCase):
    def _create_mock_assessment(self, assessment_type: AssessmentTypeEnum, jd_text: str = None):
        assessment = MagicMock(spec=AiPrepAssessmentORM)
        assessment.id = 101
        assessment.candidate_id = 42
        assessment.assessment_type = assessment_type
        assessment.job_description_text = jd_text

        q1 = MagicMock(spec=AiPrepQuestionBankORM)
        q1.question_text = "Tell me about your RAG architecture."
        aq1 = MagicMock(spec=AiPrepAssessmentQuestionORM)
        aq1.order_index = 1
        aq1.question = q1
        assessment.questions = [aq1]
        return assessment

    def test_assemble_prompt_all_7_types(self):
        """Verify assemble_prompt succeeds without format errors for all 7 assessment types."""
        for ass_type in AssessmentTypeEnum:
            db = MagicMock()
            assessment = self._create_mock_assessment(ass_type, jd_text="Looking for a Senior AI Engineer.")
            
            tx = MagicMock(spec=AiPrepTranscriptORM)
            tx.transcript_text = "I have 5 years of experience building scalable pipelines."
            
            audio = MagicMock(spec=AiPrepAudioTelemetryORM)
            audio.speaking_pace_wpm = 140
            audio.filler_words_per_min = 2
            audio.silence_ratio_pct = 6.5
            audio.avg_volume_db = -16.0
            audio.background_noise_level = BackgroundNoiseLevelEnum.LOW
            audio.clipping_detected = False

            vision = MagicMock(spec=AiPrepVisionTelemetryORM)
            vision.face_visible_pct = 95.0
            vision.frame_stability_score = 90.0
            vision.head_nods_count = 10

            def _query_side_effect(model):
                q = MagicMock()
                if model == AiPrepAssessmentORM:
                    q.filter.return_value.first.return_value = assessment
                elif model == AiPrepTranscriptORM:
                    q.filter.return_value.first.return_value = tx
                elif model == AiPrepAudioTelemetryORM:
                    q.filter.return_value.first.return_value = audio
                elif model == AiPrepVisionTelemetryORM:
                    q.filter.return_value.first.return_value = vision
                return q

            db.query.side_effect = _query_side_effect

            sys_prompt, user_prompt = assemble_prompt(db, 101)
            self.assertIsInstance(sys_prompt, str)
            self.assertIsInstance(user_prompt, str)
            self.assertIn("Tell me about your RAG architecture", user_prompt)
            self.assertIn("scalable pipelines", user_prompt)

    def test_assemble_prompt_fallback_defaults(self):
        """When transcript or audio telemetry is absent, safe defaults should be used."""
        db = MagicMock()
        assessment = self._create_mock_assessment(AssessmentTypeEnum.GENERAL_INTRO)
        assessment.questions = []

        def _query_side_effect(model):
            q = MagicMock()
            if model == AiPrepAssessmentORM:
                q.filter.return_value.first.return_value = assessment
            else:
                q.filter.return_value.first.return_value = None
            return q

        db.query.side_effect = _query_side_effect

        sys_prompt, user_prompt = assemble_prompt(db, 101)
        self.assertIn("No transcript recorded", user_prompt)
        self.assertIn("135 WPM", user_prompt)


class TestLlmWorker(unittest.TestCase):
    @patch("fapi.ai_prep.workers.llm_worker.get_storage_service")
    @patch("fapi.ai_prep.workers.llm_worker.call_llm")
    @patch("fapi.ai_prep.workers.llm_worker.create_analysis_run")
    @patch("fapi.ai_prep.workers.llm_worker.update_analysis_run_status")
    @patch("fapi.ai_prep.workers.llm_worker.SessionLocal")
    def test_llm_analysis_task_end_to_end(
        self, mock_session_local, mock_update_status, mock_create_run, mock_call_llm, mock_get_storage
    ):
        """Test llm_analysis_task completes end-to-end, parses JSON, and updates DB."""
        db = MagicMock()
        mock_session_local.return_value = db

        assessment = MagicMock(spec=AiPrepAssessmentORM)
        assessment.id = 105
        assessment.candidate_id = 42
        assessment.assessment_type = AssessmentTypeEnum.TECHNICAL
        assessment.questions = []

        tx = MagicMock(spec=AiPrepTranscriptORM)
        tx.transcript_text = "I designed a transformer architecture."

        def _query_side_effect(model):
            q = MagicMock()
            if model == AiPrepAssessmentORM:
                q.filter.return_value.first.return_value = assessment
            elif model == AiPrepTranscriptORM:
                q.filter.return_value.first.return_value = tx
            else:
                q.filter.return_value.first.return_value = None
            return q

        db.query.side_effect = _query_side_effect
        mock_call_llm.return_value = json.dumps(SAMPLE_VALID_REPORT)

        storage = MagicMock()
        mock_get_storage.return_value = storage

        from fapi.ai_prep.workers.llm_worker import llm_analysis_task
        res = llm_analysis_task(105)

        self.assertEqual(res["status"], "COMPLETED")
        self.assertIn("overall_score", res)
        self.assertIn("coaching_band", res)
        mock_call_llm.assert_called_once()
        storage.upload_bytes.assert_called_once()
        db.commit.assert_called_once()


class TestMultiProviderLlmClient(unittest.TestCase):
    @patch("fapi.ai_prep.services.llm_client.get_candidate_llm_key")
    @patch("fapi.ai_prep.services.llm_client.OpenAI")
    def test_call_llm_all_openai_compatible_providers(self, mock_openai_cls, mock_get_key):
        """Verify call_llm dispatches correctly with appropriate base_url for all OpenAI-compatible providers."""
        from fapi.ai_prep.services.candidate_llm_key_service import CandidateLLMKey
        from fapi.ai_prep.services.llm_client import call_llm, _PROVIDER_CONFIGS

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content='{"status": "ok"}'))]
        mock_completion.usage = MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        mock_client.chat.completions.create.return_value = mock_completion

        db = MagicMock()
        for provider, config in _PROVIDER_CONFIGS.items():
            mock_get_key.return_value = CandidateLLMKey(
                provider_name=provider,
                api_key="test-api-key",
                model_name=None,
            )

            res = call_llm(
                db=db,
                system_prompt="sys prompt",
                user_prompt="user prompt",
                assessment_id=1,
                candidate_id=42,
            )
            self.assertEqual(res, '{"status": "ok"}')
            # Verify OpenAI client was instantiated with matching base_url
            mock_openai_cls.assert_called_with(
                api_key="test-api-key",
                base_url=config["base_url"],
                max_retries=3,
            )

    @patch("fapi.ai_prep.services.llm_client.get_candidate_llm_key")
    def test_call_llm_unsupported_provider(self, mock_get_key):
        """Verify UnsupportedProviderError is raised for unrecognized providers."""
        from fapi.ai_prep.services.candidate_llm_key_service import CandidateLLMKey
        from fapi.ai_prep.services.llm_client import call_llm
        from fapi.ai_prep.exceptions import UnsupportedProviderError

        mock_get_key.return_value = CandidateLLMKey(
            provider_name="unknown_llm",
            api_key="test-key",
            model_name=None,
        )

        db = MagicMock()
        with self.assertRaises(UnsupportedProviderError):
            call_llm(
                db=db,
                system_prompt="sys",
                user_prompt="usr",
                assessment_id=1,
                candidate_id=42,
            )


if __name__ == "__main__":
    unittest.main()
