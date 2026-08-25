"""Prompt template — General Introduction (unstructured, no JD required).

Assessment focus
----------------
Unstructured introductory conversation.  The candidate has no JD to align
to; they simply introduce themselves and discuss their background.

Scoring weights (relative, per coaching spec):
- non_technical     — HEAVIEST: clarity, structure, confidence, delivery
- business_acumen   — HEAVY: career story coherence, goal articulation
- ai_engineering    — LIGHT: do NOT penalise for untouched topics; only
                      credit genuine signal if the candidate raises it.
- core_engineering  — LIGHT: same as ai_engineering above.

Exports: SYSTEM, USER_TEMPLATE
"""

from fapi.ai_prep.prompts.base import BASE_SYSTEM_PROMPT, OUTPUT_FORMAT_SPEC

_SYSTEM_ADDENDUM = """\

ASSESSMENT TYPE: GENERAL INTRODUCTION (unstructured, no job description)

SCORING GUIDANCE FOR THIS TYPE:
- non_technical and business_acumen are the PRIMARY scoring dimensions.
  Weight your sub-scores and coaching feedback accordingly.
- ai_engineering and core_engineering sub-scores should reflect ONLY
  technical content the candidate voluntarily raised.  If the candidate
  did not discuss technical topics, these dimensions should score in the
  DEVELOPING or NEEDS_WORK band — do NOT penalise for omission in your
  coaching narrative; simply note the gap as an improvement opportunity.
- Focus coaching on: story clarity, self-presentation, career narrative
  coherence, confidence, vocal delivery, and communication structure.\
"""

SYSTEM: str = BASE_SYSTEM_PROMPT + _SYSTEM_ADDENDUM

USER_TEMPLATE: str = """\
CANDIDATE INTRODUCTION SESSION TRANSCRIPT
==========================================

QUESTIONS ASKED:
{questions}

FULL TRANSCRIPT:
{transcript}

AUDIO METRICS:
- Speaking pace:          {wpm} WPM (target: 120-160)
- Filler words per min:   {filler_per_min}
- Silence ratio:          {silence_pct}%
- Average volume:         {avg_db} dB
- Background noise:       {noise_level}

""" + OUTPUT_FORMAT_SPEC
