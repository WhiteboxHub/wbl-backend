"""Prompt template — Hiring Manager Interview.

Assessment focus
----------------
Leadership mindset, AI strategy, culture fit, and deeper project discussion.
Deeper than a recruiter screen but not as technically rigorous as a technical
assessment.

Key coaching dimensions:
- Leadership & ownership: decision-making, accountability, team impact.
- AI mindset: strategic use of AI (not just buzzwords), practical AI
  application awareness, staying current.
- Past project depth: design decisions made, trade-offs articulated,
  lessons learned.
- Culture & collaboration: working style, cross-functional interaction,
  conflict navigation.

Scoring:
- core_engineering and ai_engineering receive MODERATE weight — credit them
  when the candidate discusses real project trade-offs, architecture choices,
  or AI-relevant engineering decisions.
- non_technical reflects communication quality, leadership presence, and
  story-telling ability.
- business_acumen reflects strategic AI thinking and organisational awareness.

Exports: SYSTEM, USER_TEMPLATE
"""

from fapi.ai_prep.prompts.base import BASE_SYSTEM_PROMPT, OUTPUT_FORMAT_SPEC

_SYSTEM_ADDENDUM = """\

ASSESSMENT TYPE: HIRING MANAGER INTERVIEW

SCORING GUIDANCE FOR THIS TYPE:
- All four dimensions carry meaningful weight here, unlike the recruiter
  screen.  Balance your scoring across leadership quality, AI strategic
  mindset, engineering depth (when surfaced), and communication.
- ai_engineering: credit AI mindset (e.g. recognising AI trade-offs,
  practical deployment awareness) in addition to pure technical depth.
- core_engineering: credit when the candidate discusses architectural
  decisions, system trade-offs, or engineering judgment from real projects.
- non_technical: leadership presence, storytelling, clarity of thought,
  executive communication style.
- business_acumen: strategic framing of AI opportunities, business impact
  orientation, organisational awareness.
- Focus coaching on: ownership language, depth of project stories (STAR-
  adjacent structure), AI mindset vs. hype, collaboration examples, and
  alignment to the team's engineering culture.\
"""

SYSTEM: str = BASE_SYSTEM_PROMPT + _SYSTEM_ADDENDUM

USER_TEMPLATE: str = """\
HIRING MANAGER INTERVIEW TRANSCRIPT
=====================================

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
