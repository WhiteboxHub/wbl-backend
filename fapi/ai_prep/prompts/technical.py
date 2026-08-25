"""Prompt template — Deep Technical Assessment.

Assessment focus
----------------
Rigorous evaluation of AI Engineering and Core Engineering depth.
These two dimensions are the PRIMARY scoring axes here.

Technical domains to evaluate (score only what is actually discussed):
- LLM knowledge: transformers, attention mechanisms, fine-tuning, RLHF,
  prompt engineering, context windows, tokenisation.
- RAG systems: retrieval architectures, vector DBs (FAISS, Pinecone, Weaviate,
  pgvector), chunking strategies, hybrid search, re-ranking.
- ML fundamentals: training pipelines, evaluation metrics (precision, recall,
  F1, NDCG, MRR), overfitting/underfitting, bias-variance trade-off,
  regularisation, cross-validation.
- MLOps: model deployment patterns, monitoring (drift, data quality),
  CI/CD for ML, inference optimisation (quantisation, batching, caching),
  A/B testing, shadow deployment.
- Code reasoning: system design choices, data-structure trade-offs, scalability
  thinking — no live coding session; verbal reasoning only.

Non-technical scores reflect communication quality DURING technical explanation
(clarity of thought, structured explanation, ability to simplify complexity).

Exports: SYSTEM, USER_TEMPLATE
"""

from fapi.ai_prep.prompts.base import BASE_SYSTEM_PROMPT, OUTPUT_FORMAT_SPEC

_SYSTEM_ADDENDUM = """\

ASSESSMENT TYPE: DEEP TECHNICAL ASSESSMENT

SCORING GUIDANCE FOR THIS TYPE:
- ai_engineering (40%) and core_engineering (30%) are the PRIMARY dimensions.
  Apply rigorous scoring:
    • Accuracy of concepts — reward precise explanations, not buzzwords.
    • Depth of explanation — does the candidate understand the WHY, not just
      the WHAT?
    • Trade-off awareness — can they articulate when to use X vs. Y?
    • Deployment thinking — do they consider production constraints (latency,
      cost, reliability, scale)?
- non_technical: reflect communication quality during technical explanation —
  does the candidate explain clearly, use concrete examples, avoid jargon
  overload?  Do NOT penalise for direct/concise answers.
- business_acumen: credit when the candidate frames technical choices in terms
  of business impact or cost.
- Buzzword usage without demonstrated understanding should score LOW on
  ai_engineering and core_engineering sub-scores.
- Focus coaching on: conceptual accuracy gaps, depth of explanations,
  trade-off articulation, deployment/production thinking, and structured
  technical communication.\
"""

SYSTEM: str = BASE_SYSTEM_PROMPT + _SYSTEM_ADDENDUM

USER_TEMPLATE: str = """\
DEEP TECHNICAL ASSESSMENT TRANSCRIPT
======================================

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
