"""
CLI Diagnostic Tool for Testing Live LLM Connections & Token Quotas.
Usage:
    python3 -m fapi.ai_prep.tests.test_llm_connection
Or:
    python3 fapi/ai_prep/tests/test_llm_connection.py
"""

from __future__ import annotations

import asyncio
import getpass
import os
import sys
import unittest
from unittest.mock import patch, AsyncMock

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from fapi.ai_prep.clients.llm_client import test_llm_connection as run_test_llm_connection, detect_provider_from_key


class TestLLMConnection(unittest.TestCase):

    def test_detect_provider_from_key(self):
        self.assertEqual(detect_provider_from_key("sk-proj-12345"), "openai")
        self.assertEqual(detect_provider_from_key("AIzaSy12345"), "gemini")
        self.assertEqual(detect_provider_from_key("gsk_12345"), "groq")
        self.assertEqual(detect_provider_from_key("sk-ant-12345"), "anthropic")

    @patch("fapi.ai_prep.clients.llm_client._execute_http_post", new_callable=AsyncMock)
    def test_mock_llm_connection_diagnostic(self, mock_post):
        mock_post.return_value = (
            {
                "choices": [{"message": {"content": "Hello, world!"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
            {
                "x-ratelimit-remaining-tokens": "1000",
                "x-ratelimit-limit-tokens": "5000",
                "x-ratelimit-remaining-requests": "100",
                "x-ratelimit-reset-requests": "1s",
            },
        )
        import secrets
        res = asyncio.run(run_test_llm_connection(api_key=secrets.token_urlsafe(16), provider="openai"))
        self.assertEqual(res["provider"], "openai")
        self.assertEqual(res["response_text"], "Hello, world!")


async def run_diagnostic():
    print("=" * 70)
    print(" AI PREP PLATFORM — LIVE LLM CONNECTION & TOKEN QUOTA TEST")
    print("=" * 70)

    # 1. Read API key from environment variable or interactive prompt
    api_key = (os.getenv("TEST_API_KEY") or "").strip()
    if not api_key:
        try:
            # Use getpass to hide typing if running in a real TTY, fallback to input
            if sys.stdin.isatty():
                api_key = getpass.getpass("Enter your API key (typing will be hidden): ").strip()
            else:
                api_key = input("Enter your API key: ").strip()
        except Exception:
            api_key = input("Enter your API key: ").strip()

    if not api_key:
        print("\n❌ Error: No API key provided. Aborting test.")
        sys.exit(1)

    provider = detect_provider_from_key(api_key)
    masked_key = api_key[:7] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
    print(f"\n[1] Key Detected       : {masked_key}")
    print(f"[2] Provider Inferred  : {provider.upper()}")
    print("[3] Connecting to LLM API over the internet...")

    try:
        diag = await run_test_llm_connection(api_key=api_key, provider=provider)
    except Exception as err:
        print("\n❌ CONNECTION FAILED:")
        print(f"   Error Type   : {type(err).__name__}")
        print(f"   Error Detail : {err}")
        sys.exit(1)

    print("\n" + "-" * 70)
    print(" ✅ CONNECTION VERIFIED — LIVE LLM RESPONSE RECEIVED")
    print("-" * 70)
    print(f" Provider Tested       : {diag['provider'].upper()}")
    print(f" Model Used            : {diag['model']}")
    print(f" Sample LLM Output     : {diag['response_text']}")

    print("\n" + "=" * 70)
    print(" 📊 TOKEN CONSUMPTION & LEFTOVER QUOTAS")
    print("=" * 70)
    used = diag["tokens_used_this_call"]
    print(f" • Tokens Used (This Call)    : {used['total_tokens']} total ({used['prompt_tokens']} prompt + {used['completion_tokens']} completion)")

    rem_tokens = diag["tokens_remaining"]
    limit_tokens = diag["tokens_limit"]
    if rem_tokens is not None:
        limit_str = f" / {limit_tokens:,}" if limit_tokens else ""
        print(f" • Tokens Remaining (Leftover) : {rem_tokens:,}{limit_str} tokens")
    else:
        print(" • Tokens Remaining (Leftover) : N/A (Provider does not return token balance headers)")

    rem_reqs = diag["requests_remaining"]
    if rem_reqs is not None:
        print(f" • Requests Remaining (Quota)  : {rem_reqs:,} requests")

    reset_time = diag["rate_limit_reset"]
    if reset_time:
        print(f" • Quota Reset Window          : {reset_time}")

    credits = diag.get("account_credits")
    if credits:
        print("\n 💳 ACCOUNT BILLING & BALANCE:")
        print(f" • Total Credit Limit         : ${credits.get('credit_limit_usd', 'N/A')}")
        print(f" • Usage to Date              : ${credits.get('usage_usd', 0.0)}")
        print(f" • Credits Remaining          : ${credits.get('credits_remaining_usd', 'N/A')}")
        print(f" • Free Tier                  : {credits.get('is_free_tier', False)}")

    print("=" * 70)
    print(" 🎉 System is fully operational and ready for live assessments!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(run_diagnostic())

