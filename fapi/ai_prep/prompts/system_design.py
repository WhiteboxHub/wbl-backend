"""Prompt template — System Design Assessment.

Assessment focus
----------------
Open-ended, verbal architectural reasoning.  There is no single correct
answer; the coach evaluates HOW the candidate thinks through a problem.

Key coaching dimensions:
- Problem decomposition: breaking ambiguous requirements into solvable pieces.
- Architectural soundness: component choices, data flows, interface definitions.
- Trade-off articulation: explicit discussion of CAP theorem, consistency vs.
  availability, sync vs. async, cost vs. latency, build vs. buy.
- Scale & reliability thinking: failure modes, graceful degradation, growth
  projections, SLA/SLO awareness.
- AI-specific design patterns: vector stores, embedding pipelines, inference
  serving, streaming LLMs, async processing, RAG orchestration.

Scoring:
- core_engineering is the HEAVIEST dimension — architectural soundness,
  scalability thinking, system decomposition.
- ai_engineering reflects AI-specific design knowledge: knowing when and how
  to incorporate LLMs, vector search, embedding models, or ML pipelines.
- non_technical: verbal clarity, structured walk-through, ability to handle
  clarifying questions, collaborative thinking.
- business_acumen: awareness of cost, time-to-market, make-vs-buy decisions.

Exports: SYSTEM, USER_TEMPLATE
"""

from fapi.ai_prep.prompts.base import BASE_SYSTEM_PROMPT, OUTPUT_FORMAT_SPEC

_SYSTEM_ADDENDUM = """\

ASSESSMENT TYPE: SYSTEM DESIGN

SCORING GUIDANCE FOR THIS TYPE:
- core_engineering is the PRIMARY dimension.  Score based on:
    • Does the candidate start with clarifying questions (scope, scale,
      constraints) before jumping to solutions?
    • Is the proposed architecture internally consistent?
    • Are failure modes identified and mitigated?
    • Is scale/growth planning addressed (horizontal scaling, sharding,
      caching, CDN, async queues)?
- ai_engineering reflects AI-specific design expertise:
    • Does the candidate know when to use a vector store vs. a relational DB?
    • Can they describe an embedding pipeline end-to-end?
    • Do they understand inference serving trade-offs (batching, GPU memory,
      caching, streaming)?
- non_technical: verbal walk-through quality, whiteboard communication,
  ability to handle ambiguity and iterate on the design when challenged.
- business_acumen: cost-conscious design choices, build-vs-buy awareness,
  time-to-value thinking.
- Credit creative but sound solutions; do not penalise for deviation from
  a "textbook" architecture as long as trade-offs are articulated.
- Focus coaching on: structured problem decomposition, trade-off articulation
  gaps, scale/reliability blind spots, and AI integration patterns.\
"""

SYSTEM: str = BASE_SYSTEM_PROMPT + _SYSTEM_ADDENDUM

USER_TEMPLATE: str = """\
SYSTEM DESIGN SESSION TRANSCRIPT
==================================

QUESTIONS / PROBLEM STATEMENTS:
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
