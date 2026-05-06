"""
CoderPad: builds validation prompts and maps model output to API fields.

Core HTTP + prompts live in :mod:`fapi.utils.openai_llm`.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from fapi.db.schemas import TestCase
from fapi.utils.openai_llm import DEFAULT_MODEL, openai_chat_with_prompts

CODERPAD_VALIDATE_SYSTEM_PROMPT = (
    "You are an expert programming tutor. Output only valid JSON as specified by the user."
)


def _build_validation_user_prompt(
    problem_statement: str,
    code: str,
    language: str,
    test_cases: Optional[List[TestCase]],
) -> str:
    tests_payload: List[Dict[str, Any]] = []
    if test_cases:
        for tc in test_cases:
            row: Dict[str, Any] = {
                "input": tc.input,
                "expected_output": tc.expected_output,
                "description": tc.description,
                "locked": tc.locked,
            }
            ao = tc.actual_output
            if ao is not None and str(ao).strip() != "":
                row["actual_output"] = ao
            tests_payload.append(row)

    if tests_payload:
        tests_block = json.dumps(tests_payload, ensure_ascii=False, indent=2)
        tests_section = f"Each item includes `expected_output` (authoritative) and, when the candidate ran tests, `actual_output` (stdout). Compare them per test.\n\n```json\n{tests_block}\n```"
    else:
        tests_section = (
            "(No test cases were provided in this request — evaluate using the problem statement "
            "and code quality only.)"
        )

    return f"""You are reviewing a coding exercise submission.

## Problem statement
{problem_statement}

## Language
{language}

## Candidate code
```
{code}
```

## Test cases
{tests_section}

## Instructions
1. Decide whether the code correctly addresses the problem statement.
2. For each test with both expected and actual output, state whether they match (trim/format differences may be acceptable if the problem allows).
3. If there are no tests, still judge whether the code plausibly solves the stated problem.
4. Respond with **JSON only** (no markdown fences), using this exact shape:
{{
  "passed": <true or false>,
  "summary": "<one or two sentences>",
  "feedback": "<detailed feedback for the learner>",
  "confidence": "<low|medium|high>"
}}
"""


def _parse_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def llm_validate_code_submission(
    *,
    problem_statement: str,
    code: str,
    language: str,
    test_cases: Optional[List[TestCase]],
    openai_api_key: str,
    model: str = DEFAULT_MODEL,
) -> Dict[str, Any]:
    """
    Validate a submission: builds prompts, calls :func:`openai_chat_with_prompts`, parses JSON.

    Returns dict with keys: passed, summary, feedback, confidence, raw_model_text, error (optional).
    """
    key = (openai_api_key or "").strip()
    if not key:
        return {
            "passed": None,
            "summary": "",
            "feedback": "",
            "confidence": None,
            "raw_model_text": None,
            "error": "OpenAI API key is required",
        }


    user_prompt = _build_validation_user_prompt(problem_statement, code, language, test_cases)
    result = openai_chat_with_prompts(
        system_prompt=CODERPAD_VALIDATE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        api_key=key,
        model=model,
        temperature=0.2,
        max_tokens=2000,
        timeout=90.0,
    )

    if result.error:
        return {
            "passed": None,
            "summary": "",
            "feedback": "",
            "confidence": None,
            "raw_model_text": None,
            "error": result.error,
        }

    content = result.content or ""
    parsed = _parse_json_from_text(content)
    if not parsed:
        return {
            "passed": None,
            "summary": "Could not parse model output",
            "feedback": content[:8000],
            "confidence": None,
            "raw_model_text": content,
            "error": None,
        }

    return {
        "passed": parsed.get("passed"),
        "summary": str(parsed.get("summary", "") or ""),
        "feedback": str(parsed.get("feedback", "") or ""),
        "confidence": parsed.get("confidence"),
        "raw_model_text": content,
        "error": None,
    }


CODERPAD_GENERATE_SYSTEM_PROMPT = (
    "You are an expert programming assignment creator. "
    "Given a topic, generate a complete coding problem with a description, starter code, and test cases. "
    "Output MUST be pure JSON with no markdown fences, matching the requested schema."
)

def llm_generate_question_from_topic(
    *,
    topic: str,
    language: str = "python",
    openai_api_key: str,
    model: str = DEFAULT_MODEL,
) -> Dict[str, Any]:
    key = (openai_api_key or "").strip()
    if not key:
        return {"error": "OpenAI API key is required"}
    
    user_prompt = f"""Generate a coding problem based on the following topic: "{topic}".
The target programming language is {language}.

Format requirements for `problem_statement`:
- Use rich HTML formatting in the style of LeetCode or HackerRank.
- Start with a clear problem description wrapped in appropriate <p> tags.
- Include an "Examples" section with at least two examples (Input, Output, and Explanation). Use <pre> or <code> blocks and <strong> text for clarity.
- Include a "Constraints" section (e.g., as a <ul> list).
- Ensure the formatting uses proper spacing and alignment, utilizing HTML tags.

Output EXACTLY this JSON format and no accompanying text:
{{
  "title": "<A concise title for the assignment>",
  "problem_statement": "<The richly formatted HTML string containing the description, examples, and constraints.>",
  "starter_code": "<Initial code template for the candidate to start with. Should include function signature.>",
  "language": "{language}",
  "test_cases": [
    {{
      "input": "<string of input, or empty if args are passed in code directly>",
      "expected_output": "<string of expected output when the function is run>",
      "description": "<short description of what this tests>",
      "locked": false
    }}
  ]
}}
Ensure you generate 3 to 5 test cases. Ensure starter_code has necessary imports and a working function signature.
"""

    result = openai_chat_with_prompts(
        system_prompt=CODERPAD_GENERATE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        api_key=key,
        model=model,
        temperature=0.3,
        max_tokens=3000,
        timeout=90.0,
    )

    if result.error:
        return {"error": result.error}

    content = result.content or ""
    parsed = _parse_json_from_text(content)
    if not parsed:
        return {"error": "Could not parse model output as JSON. Output was: " + content[:200]}

    return {
        "title": parsed.get("title", ""),
        "problem_statement": parsed.get("problem_statement", ""),
        "starter_code": parsed.get("starter_code", ""),
        "language": parsed.get("language", language),
        "test_cases": parsed.get("test_cases", []),
        "error": None,
    }

