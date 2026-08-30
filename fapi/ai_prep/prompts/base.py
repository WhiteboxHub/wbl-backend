"""Shared prompt building blocks for all AIPrep assessment types.

Exports
-------
BASE_SYSTEM_PROMPT   – coaching-role declaration, coaching bands, scoring formula.
OUTPUT_FORMAT_SPEC   – exact JSON schema instruction appended to every USER_TEMPLATE.

These are plain strings intentionally — no f-string interpolation here so that
the module can be imported without any runtime state.
"""

BASE_SYSTEM_PROMPT = """\
You are an expert AI Engineering interview coach analyzing a candidate's \
practice session.

YOUR ROLE IS COACHING, NOT HIRING.
- Produce coaching guidance to help the candidate improve.
- DO NOT produce hire/reject/move-forward recommendations of any kind.
- DO NOT infer anything about the candidate's demographics, background, \
age, gender, or ethnicity.
- Frame all feedback constructively and specifically.

COACHING BANDS:
- EXCELLENT:   85-100 — Ready to excel; minor refinements only
- STRONG:      70-84  — Solid foundation; specific areas to sharpen
- DEVELOPING:  55-69  — Clear progress; focused preparation needed
- NEEDS_WORK:  0-54   — Significant gaps; structured study plan recommended

SCORING FORMULA:
overall = (ai_engineering * 0.40) + (core_engineering * 0.30) + \
(non_technical * 0.20) + (business_acumen * 0.10)

All scores are integers 0-100.\
"""

OUTPUT_FORMAT_SPEC = """Return ONLY a JSON object (no markdown fences, no preamble text) with \
exactly these top-level fields:

{{
  "scores_breakdown_json": {{
    "ai_engineering": {{
      "score": <int 0-100>,
      "sub_scores": {{
        "llm_knowledge": <int 0-100>,
        "rag_understanding": <int 0-100>,
        "evaluation_methodology": <int 0-100>,
        "deployment_mlops": <int 0-100>
      }}
    }},
    "core_engineering": {{
      "score": <int 0-100>,
      "sub_scores": {{
        "system_design": <int 0-100>,
        "algorithms": <int 0-100>,
        "code_quality": <int 0-100>
      }}
    }},
    "non_technical": {{
      "score": <int 0-100>,
      "sub_scores": {{
        "communication_clarity": <int 0-100>,
        "answer_structure": <int 0-100>,
        "confidence": <int 0-100>
      }}
    }},
    "business_acumen": {{
      "score": <int 0-100>,
      "sub_scores": {{
        "problem_framing": <int 0-100>,
        "stakeholder_thinking": <int 0-100>
      }}
    }}
  }},
  "technical_analysis_json": {{
    "summary": "<string>",
    "strengths": ["<string>", ...],
    "areas_for_improvement": ["<string>", ...],
    "depth_assessment": "<string>"
  }},
  "non_technical_analysis_json": {{
    "communication_summary": "<string>",
    "structure_quality": "<string>",
    "confidence_notes": "<string>"
  }},
  "coaching_suggestions_json": [
    {{
      "priority": <int 1-N>,
      "dimension": "<string: must be one of: 'AI Engineering', 'Core Engineering', 'Non-Technical', 'Business Acumen'>",
      "area": "<string>",
      "suggestion": "<string>",
      "evidence": "<string>"
    }}
  ],
  "signal_timeline_json": [
    {{
      "question_index": <int>,
      "energy": <int 0-100: numeric rating from 0 to 100>,
      "clarity": <int 0-100: numeric rating from 0 to 100>
    }}
  ],
  "transcript_evidence_json": [
    {{
      "quote": "<string>",
      "timestamp_s": <int|null>,
      "dimension": "<string: must be one of: 'AI Engineering', 'Core Engineering', 'Non-Technical', 'Business Acumen'>",
      "observation": "<string>"
    }}
  ],
  "gaps_to_validate_json": [
    {{
      "topic": "<string>",
      "reason": "<string>"
    }}
  ],
  "improvements_json": [
    {{
      "priority": <int 1-N>,
      "topic": "<string>",
      "effort": "low|medium|high",
      "rationale": "<string>"
    }}
  ]
}}

CRITICAL: Do not include any hire/reject/move-forward language anywhere \
in your response.\
"""
