"""Prompt template — HR / Behavioural Assessment (STAR format).

Assessment focus
----------------
Behavioural and situational questions evaluated using the STAR method
(Situation, Task, Action, Result).

Key coaching dimensions:
- STAR method usage: does the candidate structure answers with clear
  Situation → Task → Action → Result?  Vague stories with no outcome score low.
- Conflict resolution: does the candidate frame conflicts constructively?
  Look for empathy, de-escalation, and win-win framing.
- Team dynamics: collaboration, cross-functional communication, empathy,
  giving/receiving feedback.
- Work style & adaptability: response to changing priorities, ambiguity
  tolerance, learning agility.
- Growth mindset: how does the candidate frame failures and learning moments?

Scoring:
- non_technical is the HEAVIEST dimension across all 7 assessment types.
  Behavioural communication quality IS the primary signal here.
- business_acumen reflects business awareness in storytelling (understanding
  impact, stakeholder management, prioritisation).
- ai_engineering and core_engineering reflect ONLY incidental technical
  content the candidate mentioned.  Do NOT penalise for absence — this is
  not a technical bar.

Exports: SYSTEM, USER_TEMPLATE
"""

from fapi.ai_prep.prompts.base import BASE_SYSTEM_PROMPT, OUTPUT_FORMAT_SPEC

_SYSTEM_ADDENDUM = """\

ASSESSMENT TYPE: HR / BEHAVIOURAL (STAR FORMAT)

SCORING GUIDANCE FOR THIS TYPE:
- non_technical is the PRIMARY and HEAVIEST dimension.  Sub-scores should
  include STAR structure quality, emotional intelligence, conflict
  resolution style, and communication clarity.
- business_acumen reflects business-oriented framing of behavioural stories:
  impact quantification, stakeholder awareness, priority judgement.
- ai_engineering and core_engineering: score ONLY incidental technical
  content mentioned in stories.  A score of 0 in these dimensions is
  perfectly valid and should NOT be flagged as a gap in this context.
- Coaching should focus on: STAR structure discipline, outcome articulation,
  constructive conflict framing, growth-mindset language, and delivery
  (confidence, pace, emotional control under behavioural probing).
- Flag stories that lack a clear Result as a key coaching opportunity.
- Credit authentic, specific examples; penalise vague generalisations.\
"""

SYSTEM: str = BASE_SYSTEM_PROMPT + _SYSTEM_ADDENDUM

USER_TEMPLATE: str = """\
HR / BEHAVIOURAL ASSESSMENT TRANSCRIPT
========================================

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
