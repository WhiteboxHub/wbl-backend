"""Unit tests for the AIPrep LLM connection layer.

Covers:
1. get_candidate_llm_key  — Fernet path, plaintext fallback, no-key error,
                            is_default selection, last_validated_at fallback.
2. call_llm               — OpenAI branching, Anthropic branching,
                            UnsupportedProviderError, CandidateLLMKeyError on
                            auth failure, max_retries=3 set correctly.
3. All 7 prompt files     — USER_TEMPLATE.format() smoke test, no
                            hire/reject/move-forward language.

Tests use unittest + pytest-mock (mocker fixture injected via pytest).
The DB is mocked entirely — no real DB connection required.
"""
from __future__ import annotations

import re
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers — lightweight ORM row stand-ins
# ---------------------------------------------------------------------------


@dataclass
class _FakeLlmKeyRow:
    """Mimics CandidateLlmApiKeyORM for testing without a real DB."""

    id: int
    candidate_id: int
    provider_name: str
    api_key: str
    model_name: Optional[str] = None
    status: str = "active"
    is_default: bool = False
    last_validated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# 1. get_candidate_llm_key
# ---------------------------------------------------------------------------


class TestGetCandidateLlmKey(unittest.TestCase):
    """Tests for fapi.ai_prep.services.candidate_llm_key_service.get_candidate_llm_key."""

    def _make_query_mock(self, rows: list[_FakeLlmKeyRow]):
        """Return a mock DB session whose .query().filter().order_by().all() returns rows."""
        db = MagicMock()
        q = MagicMock()
        db.query.return_value = q
        q.filter.return_value = q
        q.order_by.return_value = q
        q.all.return_value = rows
        return db

    # ------------------------------------------------------------------
    # Fernet-encrypted path
    # ------------------------------------------------------------------

    def test_fernet_decrypt_path(self):
        """A gAAAAA… Fernet token should be transparently decrypted."""
        from cryptography.fernet import Fernet

        # Generate a real Fernet key and encrypt a dummy API key.
        real_fernet_key = Fernet.generate_key()
        f = Fernet(real_fernet_key)
        plaintext_api_key = "sk-openai-test-key-12345"  # pragma: allowlist secret
        encrypted = f.encrypt(plaintext_api_key.encode()).decode()

        row = _FakeLlmKeyRow(
            id=1,
            candidate_id=42,
            provider_name="OpenAI",
            api_key=encrypted,
            model_name="gpt-4o",
            status="active",
            is_default=True,
        )
        db = self._make_query_mock([row])

        with (
            patch("fapi.ai_prep.services.candidate_llm_key_service.get_fernet",
                  return_value=Fernet(real_fernet_key)),
        ):
            from fapi.ai_prep.services.candidate_llm_key_service import get_candidate_llm_key
            result = get_candidate_llm_key(db, 42)

        self.assertEqual(result.api_key, plaintext_api_key)
        self.assertEqual(result.provider_name, "openai")
        self.assertEqual(result.model_name, "gpt-4o")

    # ------------------------------------------------------------------
    # Plaintext fallback path
    # ------------------------------------------------------------------

    def test_plaintext_fallback_path(self):
        """A sk-… plaintext key (non-Fernet) should be returned as-is — no exception raised."""
        plaintext_key = "sk-plaintextkey00000000000000000000"  # pragma: allowlist secret
        row = _FakeLlmKeyRow(
            id=2,
            candidate_id=7,
            provider_name="openai",
            api_key=plaintext_key,
            status="active",
            is_default=True,
        )
        db = self._make_query_mock([row])

        from fapi.ai_prep.services.candidate_llm_key_service import get_candidate_llm_key

        # The sk- prefix is detected as plaintext without any Fernet attempt or log.
        result = get_candidate_llm_key(db, 7)
        self.assertEqual(result.api_key, plaintext_key)
        self.assertEqual(result.provider_name, "openai")

    def test_plaintext_fallback_non_prefix_key_logs_warning(self):
        """A non-Fernet, non-standard-prefix key should log WARNING and return raw value."""
        raw_key = "some-legacy-plaintext-key-xyz"
        row = _FakeLlmKeyRow(
            id=3,
            candidate_id=99,
            provider_name="OpenAI",
            api_key=raw_key,
            status="active",
            is_default=True,
        )
        db = self._make_query_mock([row])

        from cryptography.fernet import Fernet, InvalidToken

        def _fernet_that_fails():
            m = MagicMock()
            m.decrypt.side_effect = InvalidToken()
            return m

        with (
            patch("fapi.ai_prep.services.candidate_llm_key_service.get_fernet",
                  side_effect=_fernet_that_fails),
            self.assertLogs("aiprep.llm", level="WARNING") as cm,
        ):
            from fapi.ai_prep.services.candidate_llm_key_service import get_candidate_llm_key
            result = get_candidate_llm_key(db, 99)

        self.assertEqual(result.api_key, raw_key)
        self.assertTrue(any("not a valid Fernet token" in msg for msg in cm.output))

    # ------------------------------------------------------------------
    # NoCandidateLLMKeyError — no active rows
    # ------------------------------------------------------------------

    def test_no_active_key_raises_error(self):
        """When no active rows exist, NoCandidateLLMKeyError must be raised."""
        db = self._make_query_mock([])

        from fapi.ai_prep.exceptions import NoCandidateLLMKeyError
        from fapi.ai_prep.services.candidate_llm_key_service import get_candidate_llm_key

        with self.assertRaises(NoCandidateLLMKeyError) as ctx:
            get_candidate_llm_key(db, 55)

        self.assertEqual(ctx.exception.candidate_id, 55)

    # ------------------------------------------------------------------
    # is_default selection logic
    # ------------------------------------------------------------------

    def test_is_default_key_preferred_over_newer_non_default(self):
        """With multiple active rows, the one with is_default=True wins."""
        # Row A: newer, not default; Row B: older but default.
        row_a = _FakeLlmKeyRow(
            id=10,
            candidate_id=1,
            provider_name="openai",
            api_key="sk-notdefault",  # pragma: allowlist secret
            status="active",
            is_default=False,
            last_validated_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        row_b = _FakeLlmKeyRow(
            id=5,
            candidate_id=1,
            provider_name="openai",
            api_key="sk-isdefault",  # pragma: allowlist secret
            status="active",
            is_default=True,
            last_validated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        # ORDER BY is_default DESC, last_validated_at DESC — row_b should come first.
        db = self._make_query_mock([row_b, row_a])

        from fapi.ai_prep.services.candidate_llm_key_service import get_candidate_llm_key
        result = get_candidate_llm_key(db, 1)

        self.assertEqual(result.api_key, "sk-isdefault")

    def test_last_validated_at_used_when_no_default(self):
        """When no row is default, the most-recently-validated row wins."""
        older = _FakeLlmKeyRow(
            id=1,
            candidate_id=2,
            provider_name="anthropic",
            api_key="sk-ant-older",  # pragma: allowlist secret
            status="active",
            is_default=False,
            last_validated_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        )
        newer = _FakeLlmKeyRow(
            id=2,
            candidate_id=2,
            provider_name="anthropic",
            api_key="sk-ant-newer",  # pragma: allowlist secret
            status="active",
            is_default=False,
            last_validated_at=datetime(2025, 5, 1, tzinfo=timezone.utc),
        )
        # Simulate ORDER BY returning newer first (is_default both False → last_validated_at wins).
        db = self._make_query_mock([newer, older])

        from fapi.ai_prep.services.candidate_llm_key_service import get_candidate_llm_key
        result = get_candidate_llm_key(db, 2)

        self.assertEqual(result.api_key, "sk-ant-newer")
        self.assertEqual(result.provider_name, "anthropic")

    # ------------------------------------------------------------------
    # Provider normalisation
    # ------------------------------------------------------------------

    def test_claude_alias_normalised_to_anthropic(self):
        row = _FakeLlmKeyRow(
            id=1, candidate_id=3, provider_name="Claude",
            api_key="sk-ant-xyz", status="active", is_default=True,  # pragma: allowlist secret
        )
        db = self._make_query_mock([row])
        from fapi.ai_prep.services.candidate_llm_key_service import get_candidate_llm_key
        result = get_candidate_llm_key(db, 3)
        self.assertEqual(result.provider_name, "anthropic")

    def test_gpt_alias_normalised_to_openai(self):
        row = _FakeLlmKeyRow(
            id=1, candidate_id=4, provider_name="GPT",
            api_key="sk-xyz", status="active", is_default=True,  # pragma: allowlist secret
        )
        db = self._make_query_mock([row])
        from fapi.ai_prep.services.candidate_llm_key_service import get_candidate_llm_key
        result = get_candidate_llm_key(db, 4)
        self.assertEqual(result.provider_name, "openai")


# ---------------------------------------------------------------------------
# 2. call_llm
# ---------------------------------------------------------------------------


class TestCallLlm(unittest.TestCase):
    """Tests for fapi.ai_prep.services.llm_client.call_llm."""

    def _make_db_with_key(self, provider: str, api_key: str, model: Optional[str] = None):
        """Mock db + key service so call_llm receives the given key."""
        key_obj = MagicMock()
        key_obj.provider_name = provider
        key_obj.api_key = api_key
        key_obj.model_name = model
        db = MagicMock()
        return db, key_obj

    # ------------------------------------------------------------------
    # OpenAI branching
    # ------------------------------------------------------------------

    def test_openai_branch_called_correctly(self):
        """call_llm with provider='openai' should instantiate OpenAI client."""
        db, key = self._make_db_with_key("openai", "sk-test", "gpt-4o")

        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"scores_breakdown_json": {}}'
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 200
        mock_usage.total_tokens = 300
        mock_response.usage = mock_usage

        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create.return_value = mock_response

        with (
            patch("fapi.ai_prep.services.llm_client.get_candidate_llm_key", return_value=key),
            patch("fapi.ai_prep.services.llm_client.OpenAI", return_value=mock_openai_client),
        ):
            from fapi.ai_prep.services.llm_client import call_llm
            result = call_llm(db, "sys", "user", 1, 42)

        self.assertIn("scores_breakdown_json", result)

    def test_openai_default_model_used_when_none_stored(self):
        """When model_name is None, 'gpt-4o' must be used for OpenAI."""
        db, key = self._make_db_with_key("openai", "sk-test", None)

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "{}"
        mock_usage = MagicMock(prompt_tokens=10, completion_tokens=10, total_tokens=20)
        mock_response.usage = mock_usage

        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create.return_value = mock_response

        with (
            patch("fapi.ai_prep.services.llm_client.get_candidate_llm_key", return_value=key),
            patch("fapi.ai_prep.services.llm_client.OpenAI", return_value=mock_openai_client),
        ):
            from fapi.ai_prep.services.llm_client import call_llm
            call_llm(db, "sys", "user", 1, 42)

        call_kwargs = mock_openai_client.chat.completions.create.call_args
        self.assertEqual(call_kwargs.kwargs["model"], "gpt-4o")

    def test_openai_max_retries_set_to_3(self):
        """OpenAI client must be constructed with max_retries=3."""
        db, key = self._make_db_with_key("openai", "sk-test", "gpt-4o")

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "{}"
        mock_usage = MagicMock(prompt_tokens=1, completion_tokens=1, total_tokens=2)
        mock_response.usage = mock_usage
        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create.return_value = mock_response

        captured = {}

        def _capture_openai(**kwargs):
            captured.update(kwargs)
            return mock_openai_client

        with (
            patch("fapi.ai_prep.services.llm_client.get_candidate_llm_key", return_value=key),
            patch("fapi.ai_prep.services.llm_client.OpenAI", side_effect=_capture_openai),
        ):
            from fapi.ai_prep.services.llm_client import call_llm
            call_llm(db, "sys", "user", 1, 42)

        self.assertEqual(captured.get("max_retries"), 3)

    # ------------------------------------------------------------------
    # Anthropic branching
    # ------------------------------------------------------------------

    def test_anthropic_branch_called_correctly(self):
        """call_llm with provider='anthropic' should instantiate Anthropic client."""
        db, key = self._make_db_with_key("anthropic", "sk-ant-test", "claude-3-7-sonnet-20250219")

        mock_block = MagicMock()
        mock_block.text = '{"scores_breakdown_json": {}}'
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_usage = MagicMock(input_tokens=50, output_tokens=100)
        mock_response.usage = mock_usage

        mock_anthropic_client = MagicMock()
        mock_anthropic_client.messages.create.return_value = mock_response

        mock_anthropic_module = MagicMock()
        mock_anthropic_module.Anthropic.return_value = mock_anthropic_client
        mock_anthropic_module.AuthenticationError = Exception
        mock_anthropic_module.PermissionDeniedError = Exception

        with (
            patch("fapi.ai_prep.services.llm_client.get_candidate_llm_key", return_value=key),
            patch.dict("sys.modules", {"anthropic": mock_anthropic_module}),
        ):
            from fapi.ai_prep.services.llm_client import call_llm
            result = call_llm(db, "sys", "user", 2, 99)

        self.assertIn("scores_breakdown_json", result)

    def test_anthropic_max_retries_set_to_3(self):
        """Anthropic client must be constructed with max_retries=3."""
        db, key = self._make_db_with_key("anthropic", "sk-ant-test", None)

        mock_block = MagicMock()
        mock_block.text = "{}"
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_usage = MagicMock(input_tokens=1, output_tokens=1)
        mock_response.usage = mock_usage

        mock_anthropic_client = MagicMock()
        mock_anthropic_client.messages.create.return_value = mock_response

        captured = {}

        def _capture_anthropic(**kwargs):
            captured.update(kwargs)
            return mock_anthropic_client

        mock_anthropic_module = MagicMock()
        mock_anthropic_module.Anthropic.side_effect = _capture_anthropic
        mock_anthropic_module.AuthenticationError = Exception
        mock_anthropic_module.PermissionDeniedError = Exception

        with (
            patch("fapi.ai_prep.services.llm_client.get_candidate_llm_key", return_value=key),
            patch.dict("sys.modules", {"anthropic": mock_anthropic_module}),
        ):
            from fapi.ai_prep.services.llm_client import call_llm
            call_llm(db, "sys", "user", 2, 99)

        self.assertEqual(captured.get("max_retries"), 3)

    def test_anthropic_json_instruction_appended_to_system_prompt(self):
        """Anthropic call must have the JSON-only instruction in the system prompt."""
        db, key = self._make_db_with_key("anthropic", "sk-ant-test", None)

        mock_block = MagicMock()
        mock_block.text = "{}"
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_usage = MagicMock(input_tokens=1, output_tokens=1)
        mock_response.usage = mock_usage

        mock_anthropic_client = MagicMock()
        mock_anthropic_client.messages.create.return_value = mock_response

        mock_anthropic_module = MagicMock()
        mock_anthropic_module.Anthropic.return_value = mock_anthropic_client
        mock_anthropic_module.AuthenticationError = Exception
        mock_anthropic_module.PermissionDeniedError = Exception

        with (
            patch("fapi.ai_prep.services.llm_client.get_candidate_llm_key", return_value=key),
            patch.dict("sys.modules", {"anthropic": mock_anthropic_module}),
        ):
            from fapi.ai_prep.services.llm_client import call_llm
            call_llm(db, "MY_SYSTEM_PROMPT", "user", 2, 99)

        call_kwargs = mock_anthropic_client.messages.create.call_args.kwargs
        self.assertIn("MY_SYSTEM_PROMPT", call_kwargs["system"])
        self.assertIn("ONLY valid JSON", call_kwargs["system"])

    # ------------------------------------------------------------------
    # UnsupportedProviderError
    # ------------------------------------------------------------------

    def test_unsupported_provider_raises_error(self):
        """An unknown provider_name must raise UnsupportedProviderError immediately."""
        db, key = self._make_db_with_key("unsupported_provider", "unsupported_key", None)

        from fapi.ai_prep.exceptions import UnsupportedProviderError
        with patch("fapi.ai_prep.services.llm_client.get_candidate_llm_key", return_value=key):
            from fapi.ai_prep.services.llm_client import call_llm
            with self.assertRaises(UnsupportedProviderError) as ctx:
                call_llm(db, "sys", "user", 1, 1)

        self.assertEqual(ctx.exception.provider_name, "unsupported_provider")

    # ------------------------------------------------------------------
    # CandidateLLMKeyError on auth failure
    # ------------------------------------------------------------------

    def test_openai_auth_error_raised_as_candidate_llm_key_error(self):
        """OpenAI AuthenticationError must be caught and re-raised as CandidateLLMKeyError."""
        from openai import AuthenticationError as OpenAIAuthError

        db, key = self._make_db_with_key("openai", "sk-bad", "gpt-4o")

        # Simulate OpenAI raising AuthenticationError.
        mock_openai_client = MagicMock()
        # AuthenticationError requires (message, response, body) — use MagicMock.
        auth_err = MagicMock(spec=OpenAIAuthError)
        auth_err.__str__ = lambda self: "Incorrect API key"
        mock_openai_client.chat.completions.create.side_effect = OpenAIAuthError(
            message="Incorrect API key",
            response=MagicMock(status_code=401, headers={}),
            body=None,
        )

        from fapi.ai_prep.exceptions import CandidateLLMKeyError
        with (
            patch("fapi.ai_prep.services.llm_client.get_candidate_llm_key", return_value=key),
            patch("fapi.ai_prep.services.llm_client.OpenAI", return_value=mock_openai_client),
            self.assertLogs("aiprep.llm", level="WARNING"),
        ):
            from fapi.ai_prep.services.llm_client import call_llm
            with self.assertRaises(CandidateLLMKeyError) as ctx:
                call_llm(db, "sys", "user", 1, 42)

        self.assertEqual(ctx.exception.candidate_id, 42)
        self.assertEqual(ctx.exception.provider_name, "openai")


# ---------------------------------------------------------------------------
# 3. Prompt template smoke tests
# ---------------------------------------------------------------------------


class TestPromptTemplates(unittest.TestCase):
    """Smoke-tests for all 7 prompt template modules."""

    _DUMMY_AUDIO = dict(
        wpm=135,
        filler_per_min=2.1,
        silence_pct=8.5,
        avg_db=-18.0,
        noise_level="low",
        clipping_detected="no",
        face_visible_pct="96.5%",
        frame_stability="92.0%",
        head_nods="12",
    )
    _DUMMY_COMMON = dict(
        questions="Q1: Tell me about yourself.",
        transcript="Candidate: I have 5 years of experience...",
        **_DUMMY_AUDIO,
    )

    def _assert_no_hiring_language(self, text: str, module_name: str) -> None:
        """Fail if affirmative hire/reject/move-forward RECOMMENDATIONS appear in the text.

        We intentionally allow prohibitive phrases like "DO NOT produce hire/reject/
        move-forward recommendations" — these are *required* in the coaching prompts.
        We only flag affirmative recommendations (e.g. "we recommend hiring this
        candidate", "candidate should move forward", "reject this applicant").
        """
        # Match affirmative hiring recommendations — NOT preceded by "do not", "don't",
        # "avoid", or "no" (which would make them prohibitions, not recommendations).
        forbidden = re.compile(
            r"(?<!\bdo not\b )(?<!\bdon't\b )(?<!\bavoid\b )(?<!\bno\b )"
            r"\b(we recommend (?:hiring|moving forward|rejecting)|"
            r"candidate (?:should be hired|should move forward|is rejected)|"
            r"proceed to (?:next round|offer))\b",
            re.IGNORECASE,
        )
        matches = forbidden.findall(text)
        self.assertFalse(
            matches,
            f"{module_name} contains affirmative hiring language: {matches}",
        )

    def _full_text(self, module: Any) -> str:
        return (getattr(module, "SYSTEM", "") or "") + (getattr(module, "USER_TEMPLATE", "") or "")

    # ------------------------------------------------------------------
    # general_intro
    # ------------------------------------------------------------------

    def test_general_intro_format_no_error(self):
        from fapi.ai_prep.prompts import general_intro
        filled = general_intro.USER_TEMPLATE.format(**self._DUMMY_COMMON)
        self.assertGreater(len(filled), 100)

    def test_general_intro_no_hiring_language(self):
        from fapi.ai_prep.prompts import general_intro
        self._assert_no_hiring_language(self._full_text(general_intro), "general_intro")

    # ------------------------------------------------------------------
    # jd_intro
    # ------------------------------------------------------------------

    def test_jd_intro_format_no_error(self):
        from fapi.ai_prep.prompts import jd_intro
        filled = jd_intro.USER_TEMPLATE.format(
            jd_text="Senior ML Engineer role requiring LLM expertise.",
            **self._DUMMY_COMMON,
        )
        self.assertGreater(len(filled), 100)

    def test_jd_intro_no_hiring_language(self):
        from fapi.ai_prep.prompts import jd_intro
        self._assert_no_hiring_language(self._full_text(jd_intro), "jd_intro")

    # ------------------------------------------------------------------
    # recruiter
    # ------------------------------------------------------------------

    def test_recruiter_format_no_error(self):
        from fapi.ai_prep.prompts import recruiter
        filled = recruiter.USER_TEMPLATE.format(**self._DUMMY_COMMON)
        self.assertGreater(len(filled), 100)

    def test_recruiter_no_hiring_language(self):
        from fapi.ai_prep.prompts import recruiter
        self._assert_no_hiring_language(self._full_text(recruiter), "recruiter")

    # ------------------------------------------------------------------
    # hiring_manager
    # ------------------------------------------------------------------

    def test_hiring_manager_format_no_error(self):
        from fapi.ai_prep.prompts import hiring_manager
        filled = hiring_manager.USER_TEMPLATE.format(**self._DUMMY_COMMON)
        self.assertGreater(len(filled), 100)

    def test_hiring_manager_no_hiring_language(self):
        from fapi.ai_prep.prompts import hiring_manager
        self._assert_no_hiring_language(self._full_text(hiring_manager), "hiring_manager")

    # ------------------------------------------------------------------
    # technical
    # ------------------------------------------------------------------

    def test_technical_format_no_error(self):
        from fapi.ai_prep.prompts import technical
        filled = technical.USER_TEMPLATE.format(**self._DUMMY_COMMON)
        self.assertGreater(len(filled), 100)

    def test_technical_no_hiring_language(self):
        from fapi.ai_prep.prompts import technical
        self._assert_no_hiring_language(self._full_text(technical), "technical")

    # ------------------------------------------------------------------
    # system_design
    # ------------------------------------------------------------------

    def test_system_design_format_no_error(self):
        from fapi.ai_prep.prompts import system_design
        filled = system_design.USER_TEMPLATE.format(**self._DUMMY_COMMON)
        self.assertGreater(len(filled), 100)

    def test_system_design_no_hiring_language(self):
        from fapi.ai_prep.prompts import system_design
        self._assert_no_hiring_language(self._full_text(system_design), "system_design")

    # ------------------------------------------------------------------
    # hr
    # ------------------------------------------------------------------

    def test_hr_format_no_error(self):
        from fapi.ai_prep.prompts import hr
        filled = hr.USER_TEMPLATE.format(**self._DUMMY_COMMON)
        self.assertGreater(len(filled), 100)

    def test_hr_no_hiring_language(self):
        from fapi.ai_prep.prompts import hr
        self._assert_no_hiring_language(self._full_text(hr), "hr")

    # ------------------------------------------------------------------
    # Confirm OUTPUT_FORMAT_SPEC is present in every USER_TEMPLATE
    # ------------------------------------------------------------------

    def test_all_templates_include_output_format_spec(self):
        from fapi.ai_prep.prompts.base import OUTPUT_FORMAT_SPEC
        from fapi.ai_prep.prompts import (
            general_intro, hiring_manager, hr, jd_intro, recruiter,
            system_design, technical,
        )
        for mod in (general_intro, hiring_manager, hr, jd_intro, recruiter,
                    system_design, technical):
            with self.subTest(module=mod.__name__):
                self.assertIn(
                    "scores_breakdown_json",
                    mod.USER_TEMPLATE,
                    f"{mod.__name__}.USER_TEMPLATE is missing OUTPUT_FORMAT_SPEC",
                )


if __name__ == "__main__":
    unittest.main()
