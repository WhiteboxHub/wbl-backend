"""Prompt template — Recruiter Phone Screen.

Assessment focus
----------------
High-level screening call.  Recruiters probe background, logistics,
availability, and role interest — this is NOT a technical bar.

Scoring weights (relative, per coaching spec):
- non_technical   — HEAVY: background summary clarity, professionalism,
                    availability responses, communication style.
- business_acumen — HEAVY: role interest articulation, company knowledge,
                    motivation fit.
- ai_engineering  — LIGHT: only high-level signal; reflect what the
                    candidate stated, not what they were not asked.
- core_engineering — LIGHT: same as ai_engineering.

Tone guidance: this is a screening conversation, not a technical deep-dive.
Coaching feedback should be calibrated accordingly.

Exports: SYSTEM, USER_TEMPLATE
"""

from fapi.ai_prep.prompts.base import BASE_SYSTEM_PROMPT, OUTPUT_FORMAT_SPEC

_SYSTEM_ADDENDUM = """\

ASSESSMENT TYPE: RECRUITER PHONE SCREEN

SCORING GUIDANCE FOR THIS TYPE:
- non_technical and business_acumen are the PRIMARY scoring dimensions.
  The recruiter screen is a communication and fit conversation, not a
  technical evaluation.
- ai_engineering and core_engineering sub-scores should reflect ONLY
  the high-level technical signal the recruiter elicited (e.g. confirming
  a background in ML/AI).  Do not penalise for depth not probed.
- Focus coaching on: background summary clarity, professional presentation,
  enthusiasm and motivation for the role, handling logistics questions
  (availability, compensation expectations), and screening-call pacing.\
"""

SYSTEM: str = BASE_SYSTEM_PROMPT + _SYSTEM_ADDENDUM

USER_TEMPLATE: str = """\
RECRUITER PHONE SCREEN TRANSCRIPT
===================================

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
