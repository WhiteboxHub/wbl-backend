"""Prompt template — JD-Targeted Introduction.

Assessment focus
----------------
Introduction conversation anchored to a specific job description.  Score
ai_engineering and core_engineering based on how well the candidate's
stated experience aligns with JD requirements.

Key coaching dimensions:
- Role alignment (experience ↔ JD requirements)
- Motivation fit (why this role / company)
- Communication quality during the intro

Exports: SYSTEM, USER_TEMPLATE
"""

from fapi.ai_prep.prompts.base import BASE_SYSTEM_PROMPT, OUTPUT_FORMAT_SPEC

_SYSTEM_ADDENDUM = """\

ASSESSMENT TYPE: JD-TARGETED INTRODUCTION

SCORING GUIDANCE FOR THIS TYPE:
- Score ai_engineering and core_engineering based on the degree to which
  the candidate's stated experience and skills align with the requirements
  in the JOB DESCRIPTION provided below.  Penalise notable gaps, credit
  clear direct experience.
- non_technical reflects communication quality, structure, and confidence
  during the targeted intro.
- business_acumen reflects the candidate's articulation of motivation,
  role fit, and career alignment with this specific opportunity.
- Focus coaching on: role alignment clarity, motivation articulation,
  gap awareness, and self-presentation tailored to the JD.\
"""

SYSTEM: str = BASE_SYSTEM_PROMPT + _SYSTEM_ADDENDUM

USER_TEMPLATE: str = """\
JD-TARGETED INTRODUCTION SESSION
==================================

JOB DESCRIPTION:
{jd_text}

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
