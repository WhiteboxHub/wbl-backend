"""
Assessment Engine — Pure Business Logic Coordinator.

Architecture Rules (MUST NOT VIOLATE):
  - ZERO database calls (no SQLAlchemy sessions, no ORM imports).
  - ZERO network/HTTP calls (no LLM API calls, no external services).
  - ZERO imports from fapi.ai_prep.crud, fapi.db, or any orchestrator layer.
  - All data enters and exits via plain Python dicts and primitives.
  - The ONLY way to communicate with this engine is through the Assessment Orchestrator.

Responsibilities:
  1. Question selection — filter and prepare questions for a given assessment type.
     INTRO and JD_INTRO types always receive exactly 1 question.
  2. Context building — transform raw telemetry/transcript dicts into structured text
     contexts that the LLMEvaluationEngine (Srimanth) can consume.
  3. Candidate eligibility — pure pre-flight rule checks before an assessment starts.
  4. State validation — determine valid state transitions (pure logic, no DB).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class AssessmentEngine:
    """
    Core Engine: Pure in-memory business logic coordinator for AI Prep assessments.

    This class contains no side effects. Every method is a pure transformation:
    given input data → returns output data. No DB, no HTTP, no external state.
    """

    # Assessment types that serve exactly 1 question (intro/jd-intro scope)
    SINGLE_QUESTION_TYPES: set = {"INTRO", "JD_INTRO"}

    # Valid status transitions allowed by business rules
    VALID_TRANSITIONS: Dict[str, List[str]] = {
        "IN_PROGRESS": ["EVALUATING", "FAILED", "CANCELLED"],
        "EVALUATING":  ["COMPLETED", "FAILED"],
        "COMPLETED":   [],
        "FAILED":      [],
        "CANCELLED":   [],
    }
    
    # Number of questions for multi-question assessment types
    MULTI_QUESTION_LIMIT: int = 10

    # Difficulty distribution target counts keyed by readiness band
    DIFFICULTY_DISTRIBUTION: Dict[str, Dict[str, int]] = {
        "STRONG":       {"HARD": 4, "MEDIUM": 4, "EASY": 2},
        "GOOD":         {"HARD": 2, "MEDIUM": 6, "EASY": 2},
        "NEEDS_POLISH": {"HARD": 1, "MEDIUM": 4, "EASY": 5},
        "WEAK":         {"HARD": 0, "MEDIUM": 4, "EASY": 6},
        "DEFAULT":      {"HARD": 2, "MEDIUM": 5, "EASY": 3},
    }

    # Deterministic timing matrix: (difficulty_level, scope) -> seconds
    QUESTION_TIME_LIMIT_MATRIX: Dict[Tuple[str, str], int] = {
        ("EASY", "SPECIFIC"): 60,
        ("EASY", "BROAD"): 90,
        ("MEDIUM", "SPECIFIC"): 90,
        ("MEDIUM", "BROAD"): 150,
        ("HARD", "SPECIFIC"): 120,
        ("HARD", "BROAD"): 210,
    }

    # Total technical interview budget (15 minutes in seconds)
    TECHNICAL_TOTAL_TIME_BUDGET: int = 900

    # Total hiring manager interview budget (15 minutes in seconds)
    HIRING_MANAGER_TOTAL_TIME_BUDGET: int = 900

    # Subject quota allocation (60% AI, 20% SE, 20% DevOps)
    TECHNICAL_SUBJECT_BUDGETS: Dict[str, int] = {
        "AI Engineering": 540,         # 60% of 900s
        "Software Engineering": 180,   # 20% of 900s
        "DevOps and Cloud": 180,       # 20% of 900s
    }

    # Hiring Manager canonical leadership competency budgets (equal 180s split across 5 competencies = 900s total)
    HIRING_MANAGER_COMPETENCY_BUDGETS: Dict[str, int] = {
        "Project Ownership": 180,
        "Technical Roadblocks": 180,
        "Conflict & Collaboration": 180,
        "Trade-offs & Deadlines": 180,
        "Delivery & Excellence": 180,
    }
    HIRING_MANAGER_SUBJECT_BUDGETS: Dict[str, int] = HIRING_MANAGER_COMPETENCY_BUDGETS

    @classmethod
    def normalize_hiring_manager_competency(cls, question: Dict[str, Any]) -> str:
        """
        Normalizes a hiring manager question to one of the 5 canonical leadership competencies:
        'Project Ownership', 'Technical Roadblocks', 'Conflict & Collaboration',
        'Trade-offs & Deadlines', or 'Delivery & Excellence'.
        """
        comp = question.get("competency") or question.get("subject") or question.get("concept") or ""
        text = str(comp).strip()
        lower_comp = text.lower()
        if "project ownership" in lower_comp:
            return "Project Ownership"
        if "technical roadblock" in lower_comp or "roadblock" in lower_comp:
            return "Technical Roadblocks"
        if "conflict" in lower_comp or "collaboration" in lower_comp:
            return "Conflict & Collaboration"
        if "trade-off" in lower_comp or "tradeoff" in lower_comp or "deadline" in lower_comp:
            return "Trade-offs & Deadlines"
        if "delivery" in lower_comp or "excellence" in lower_comp:
            return "Delivery & Excellence"

        combined = (text + " " + str(question.get("question_text") or "")).lower()
        if any(k in combined for k in ("conflict", "collaborat", "stakeholder", "disagree", "cross-functional", "cross functional", "team", "interpersonal", "peer")):
            return "Conflict & Collaboration"
        if any(k in combined for k in ("trade-off", "tradeoff", "deadline", "priorit", "scope", "compromise", "urgent", "timeline")):
            return "Trade-offs & Deadlines"
        if any(k in combined for k in ("roadblock", "challenge", "failure", "incident", "outage", "bottleneck", "bug", "complex", "obstacle", "problem")):
            return "Technical Roadblocks"
        if any(k in combined for k in ("deliver", "excellence", "scale", "impact", "metric", "result", "quality", "execution", "performance")):
            return "Delivery & Excellence"
        return "Project Ownership"


    @classmethod
    def normalize_subject(cls, subject_str: Optional[str]) -> str:
        """
        Normalizes subject string to one of the 3 canonical quota buckets:
        'AI Engineering', 'Software Engineering', or 'DevOps and Cloud'.
        """
        if not subject_str:
            return "AI Engineering"
        s = str(subject_str).strip().lower()
        if any(k in s for k in ("devops", "cloud", "infra", "infrastructure")):
            return "DevOps and Cloud"
        if any(k in s for k in ("software", "core", "backend", "frontend", "system design")):
            return "Software Engineering"
        return "AI Engineering"

    @classmethod
    def get_question_time_limit(cls, question: Dict[str, Any]) -> int:
        """
        Resolves question time limit directly from the backend question record.
        Strictly respects the question's explicit `time_limit_seconds` configured in the backend database.
        Falls back to difficulty mapping only if time_limit_seconds is missing or non-positive.
        """
        explicit = question.get("time_limit_seconds")
        if explicit is not None and isinstance(explicit, int) and explicit > 0:
            return explicit

        diff = str(question.get("difficulty_level") or "MEDIUM").upper().strip()
        scope = str(question.get("scope") or "SPECIFIC").upper().strip()

        if (diff, scope) in cls.QUESTION_TIME_LIMIT_MATRIX:
            return cls.QUESTION_TIME_LIMIT_MATRIX[(diff, scope)]

        if diff == "EASY":
            return 60
        if diff == "HARD":
            return 150

        return 120

    def __init__(self) -> None:
        pass

    # =========================================================================
    # 1. QUESTION SELECTION & ROUND-ROBIN
    # =========================================================================

    def select_questions_for_assessment(
        self,
        assessment_type: str,
        available_questions: List[Dict[str, Any]],
        limit: Optional[int] = None,
        previous_readiness: Optional[str] = None,
        previously_asked_ids: Optional[List[int]] = None,
        sanitize: bool = True,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Selects questions for an assessment type using adaptive distribution."""
        normalized_type = assessment_type.upper().strip()
        excluded_ids = {
            int(qid) if str(qid).isdigit() else qid
            for qid in (previously_asked_ids or [])
        }
        excluded_ids.update({str(qid) for qid in (previously_asked_ids or [])})

        # INTRO and JD_INTRO are single-question assessments
        if normalized_type in self.SINGLE_QUESTION_TYPES:
            return self._select_single_intro_question(
                available_questions, normalized_type, excluded_ids, sanitize=sanitize
            )

        # TECHNICAL: 15-minute time-budgeted algorithm (60/20/20 split)
        if normalized_type == "TECHNICAL":
            selected = self.select_technical_timed_questions(
                available_questions=available_questions,
                target_seconds=self.TECHNICAL_TOTAL_TIME_BUDGET,
                limit=limit,
                previously_asked_ids=excluded_ids,
                weak_question_ids=set(kwargs.get("weak_question_ids") or []),
                concept_ladder=dict(kwargs.get("concept_ladder") or {}),
            )
            return [self._sanitize_question_for_candidate(q) for q in selected] if sanitize else selected

        # HIRING_MANAGER: 15-minute time-budgeted algorithm
        if normalized_type == "HIRING_MANAGER":
            selected = self.select_hiring_manager_timed_questions(
                available_questions=available_questions,
                target_seconds=self.HIRING_MANAGER_TOTAL_TIME_BUDGET,
                limit=limit,
                previously_asked_ids=excluded_ids,
                weak_question_ids=set(kwargs.get("weak_question_ids") or []),
                concept_ladder=dict(kwargs.get("concept_ladder") or {}),
                previous_readiness=previous_readiness,
            )
            return [self._sanitize_question_for_candidate(q) for q in selected] if sanitize else selected

        # Collect all active matching questions for this category
        all_category_questions = [
            q for q in available_questions
            if str(q.get("category", "")).upper() == normalized_type
            and q.get("is_active", True)
        ]

        if not all_category_questions:
            logger.warning("[AssessmentEngine] No questions found for type '%s'.", normalized_type)
            return []

        # Filter out questions already completed in previous attempts
        unseen_matched = [
            q for q in all_category_questions
            if q.get("id") not in excluded_ids
        ]

        if unseen_matched:
            matched = unseen_matched
        else:
            # When candidate has completed all questions in the bank, freshly restart from the beginning
            logger.info(
                "[AssessmentEngine] Candidate has completed all questions for '%s'. Freshly restarting pool from the beginning.",
                normalized_type,
            )
            matched = all_category_questions

        # Recruiter round is a focused 10-15 minute screen (typically 6-8 questions).
        if normalized_type == "RECRUITER":
            max_q = limit if limit is not None else min(8, len(matched))
        else:
            max_q = limit if limit is not None else self.MULTI_QUESTION_LIMIT

        selected = self._select_adaptive_questions(matched, previous_readiness, max_q)
        for q in selected:
            q["time_limit_seconds"] = self.get_question_time_limit(q)

        # For Recruiter screens, ensure high-level overview questions lead the interview
        if normalized_type == "RECRUITER" and selected:
            def _is_introductory(item: Dict[str, Any]) -> bool:
                txt = (item.get("question_text") or "").lower()
                return "high-level overview" in txt or "overview of your background" in txt
            opening_qs = [q for q in selected if _is_introductory(q)]
            rest_qs = [q for q in selected if not _is_introductory(q)]
            if opening_qs:
                selected = opening_qs + rest_qs

        return [self._sanitize_question_for_candidate(q) for q in selected] if sanitize else selected

    def _select_single_intro_question(
        self, questions: List[Dict[str, Any]], category: str, excluded: set, sanitize: bool = True
    ) -> List[Dict[str, Any]]:
        """Handles single-question selection for INTRO / JD_INTRO."""
        matched = [
            q for q in questions
            if str(q.get("category", "")).upper() == category
            and q.get("is_active", True)
            and q.get("id") not in excluded
        ]
        if matched:
            selected = matched[:1]
        else:
            selected = [
                q for q in questions
                if str(q.get("category", "")).upper() == category
                and q.get("is_active", True)
            ][:1]
        for q in selected:
            q["time_limit_seconds"] = self.get_question_time_limit(q)
        return [self._sanitize_question_for_candidate(q) for q in selected] if sanitize else selected

    def _select_adaptive_questions(
        self, matched: List[Dict[str, Any]], readiness: Optional[str], max_q: int
    ) -> List[Dict[str, Any]]:
        """Applies adaptive difficulty and round-robin subcategory selection."""
        import random
        from collections import defaultdict

        dist = self.DIFFICULTY_DISTRIBUTION.get(
            (readiness or "").upper(), self.DIFFICULTY_DISTRIBUTION["DEFAULT"]
        )

        pools: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        for q in matched:
            diff = str(q.get("difficulty_level", "MEDIUM")).upper()
            pools[diff][q.get("sub_category") or "General"].append(q)

        for diff_dict in pools.values():
            for q_list in diff_dict.values():
                random.shuffle(q_list)

        selected: List[Dict[str, Any]] = []
        selected_ids: set = set()

        for diff, target_count in dist.items():
            picked = self._round_robin_pick(pools[diff], target_count, selected_ids)
            selected.extend(picked)

        if len(selected) < max_q:
            remaining = [q for q in matched if q.get("id") not in selected_ids]
            random.shuffle(remaining)
            selected.extend(remaining[: max_q - len(selected)])

        return selected[:max_q]

    def _round_robin_pick(
        self,
        subcat_pools: Dict[str, List[Dict[str, Any]]],
        target_count: int,
        selected_ids: set,
    ) -> List[Dict[str, Any]]:
        """Picks up to target_count questions rotating fairly across sub-categories."""
        import random
        sub_cats = list(subcat_pools.keys())
        if not sub_cats:
            return []

        random.shuffle(sub_cats)
        picked: List[Dict[str, Any]] = []
        cat_idx = 0

        while len(picked) < target_count:
            progress = False
            for _ in range(len(sub_cats)):
                cat = sub_cats[cat_idx % len(sub_cats)]
                cat_idx += 1
                pool = subcat_pools[cat]

                while pool:
                    q = pool.pop(0)
                    if q.get("id") not in selected_ids:
                        picked.append(q)
                        selected_ids.add(q.get("id"))
                        progress = True
                        break

                if len(picked) >= target_count:
                    break

            if not progress:
                break

        return picked

    def select_technical_timed_questions(
        self,
        available_questions: List[Dict[str, Any]],
        target_seconds: int = 900,
        limit: Optional[int] = None,
        previously_asked_ids: Optional[Set[int]] = None,
        weak_question_ids: Optional[Set[int]] = None,
        concept_ladder: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """
        15-Minute Technical Question Selection Algorithm:
        - 60% AI Engineering (~540s)
        - 20% Software Engineering (~180s)
        - 20% DevOps and Cloud (~180s)
        - Mixes BROAD (architectural) and SPECIFIC (tactical) questions.
        - Rotates across concepts to maximize topic diversity.
        - Difficulty Ladder: Serves target difficulty (EASY, MEDIUM, HARD) per concept.
        - Prioritizes weak questions for retry; excludes mastered/previously asked.
        - Ensures total sum of time_limit_seconds <= target_seconds (900s).
        """
        import random
        from collections import defaultdict

        excluded = set(previously_asked_ids or [])
        weak_ids = set(weak_question_ids or [])
        ladder = dict(concept_ladder or {})

        # 1. Filter active technical questions & group by subject
        tech_pool = [
            q for q in available_questions
            if str(q.get("category", "")).upper() == "TECHNICAL"
            and q.get("is_active", True)
        ]
        if not tech_pool:
            logger.warning("[AssessmentEngine] No active TECHNICAL questions found.")
            return []

        subject_pools: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for q in tech_pool:
            subj = self.normalize_subject(q.get("subject"))
            subject_pools[subj].append(q)

        selected: List[Dict[str, Any]] = []
        selected_ids: Set[int] = set()
        current_total_time: int = 0

        # 2. Select questions per subject adhering to quotas
        for subject, budget in self.TECHNICAL_SUBJECT_BUDGETS.items():
            pool = subject_pools.get(subject, [])
            if not pool:
                continue

            subj_questions, subj_time = self._select_subject_block(
                pool=pool,
                budget=budget,
                excluded=excluded,
                weak_ids=weak_ids,
                selected_ids=selected_ids,
                concept_ladder=ladder,
            )
            selected.extend(subj_questions)
            current_total_time += subj_time

        # 3. Global Top-Up: If total < target_seconds, add questions to fill up to 900s
        selected, current_total_time = self._top_up_remaining_seconds(
            tech_pool=tech_pool,
            selected=selected,
            selected_ids=selected_ids,
            excluded=excluded,
            current_total_time=current_total_time,
            target_seconds=target_seconds,
        )

        if limit is not None and limit > 0:
            selected = selected[:limit]

        # Enforce hard target_seconds global cap: trim from end if subject leniency overshoots
        current_total_time = sum(q.get("time_limit_seconds") or self.get_question_time_limit(q) for q in selected)
        while current_total_time > target_seconds and selected:
            removed = selected.pop()
            current_total_time -= (removed.get("time_limit_seconds") or self.get_question_time_limit(removed))

        logger.info(
            "[AssessmentEngine] Technical timed selection complete: %d questions, %d seconds (budget: %d)",
            len(selected), current_total_time, target_seconds,
        )
        return self.sequence_fatigue_aware_order(selected)

    def select_hiring_manager_timed_questions(
        self,
        available_questions: List[Dict[str, Any]],
        target_seconds: int = 900,
        limit: Optional[int] = None,
        previously_asked_ids: Optional[Set[int]] = None,
        weak_question_ids: Optional[Set[int]] = None,
        concept_ladder: Optional[Dict[str, str]] = None,
        previous_readiness: Optional[str] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """
        15-Minute Hiring Manager Question Selection Algorithm (mirrors Technical):
        - Rotates across subjects/competencies adhering to quotas.
        - Prioritizes adaptive difficulty when explicit limit is passed.
        - Fills slack time up to target_seconds (900s).
        - Enforces global target_seconds cap.
        - Returns fatigue-aware cognitive pacing order.
        """
        import random
        from collections import defaultdict

        excluded = set(previously_asked_ids or [])
        weak_ids = set(weak_question_ids or [])
        ladder = dict(concept_ladder or {})

        hm_pool = [
            q for q in available_questions
            if str(q.get("category", "")).upper() == "HIRING_MANAGER"
            and q.get("is_active", True)
        ]
        if not hm_pool:
            logger.warning("[AssessmentEngine] No active HIRING_MANAGER questions found.")
            return []

        # If explicit limit is passed (e.g. In unit tests), honor adaptive difficulty directly
        if limit is not None and limit > 0:
            matched = [q for q in hm_pool if q.get("id") not in excluded] or hm_pool
            selected = self._select_adaptive_questions(matched, previous_readiness, limit)
            for q in selected:
                q["time_limit_seconds"] = self.get_question_time_limit(q)
            return selected[:limit]

        competency_pools: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for q in hm_pool:
            comp = self.normalize_hiring_manager_competency(q)
            competency_pools[comp].append(q)

        selected: List[Dict[str, Any]] = []
        selected_ids: Set[int] = set()
        current_total_time: int = 0

        for competency, budget in self.HIRING_MANAGER_COMPETENCY_BUDGETS.items():
            pool = competency_pools.get(competency, [])
            if not pool:
                continue

            fresh = [q for q in pool if q.get("id") not in excluded]
            candidates = fresh if fresh else pool

            # Prioritize weak questions for retry, then fresh unasked questions
            weak_candidates = [q for q in candidates if q.get("id") in weak_ids]
            normal_candidates = [q for q in candidates if q.get("id") not in weak_ids]
            random.shuffle(weak_candidates)
            random.shuffle(normal_candidates)
            ordered_candidates = weak_candidates + normal_candidates

            comp_time = 0
            for q in ordered_candidates:
                qid = q.get("id")
                if qid in selected_ids:
                    continue
                q_time = self.get_question_time_limit(q)
                if (comp_time + q_time) <= budget:
                    qc = dict(q)
                    qc["time_limit_seconds"] = q_time
                    qc["competency"] = competency
                    selected.append(qc)
                    selected_ids.add(qid)
                    comp_time += q_time

            current_total_time += comp_time

        selected, current_total_time = self._top_up_remaining_seconds(
            tech_pool=hm_pool,
            selected=selected,
            selected_ids=selected_ids,
            excluded=excluded,
            current_total_time=current_total_time,
            target_seconds=target_seconds,
        )

        for q in selected:
            if not q.get("competency"):
                q["competency"] = self.normalize_hiring_manager_competency(q)

        current_total_time = sum(q.get("time_limit_seconds") or self.get_question_time_limit(q) for q in selected)
        while current_total_time > target_seconds and selected:
            removed = selected.pop()
            current_total_time -= (removed.get("time_limit_seconds") or self.get_question_time_limit(removed))

        logger.info(
            "[AssessmentEngine] Hiring Manager timed selection complete: %d questions, %d seconds (budget: %d)",
            len(selected), current_total_time, target_seconds,
        )
        return self.sequence_fatigue_aware_order(selected)

    def _select_subject_block(
        self,
        pool: List[Dict[str, Any]],
        budget: int,
        excluded: Set[int],
        weak_ids: Set[int],
        selected_ids: Set[int],
        concept_ladder: Optional[Dict[str, str]] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Selects questions for a single subject block: warm-up -> broad -> specific rotation with concept ladder."""
        import random

        ladder = dict(concept_ladder or {})
        fresh = [q for q in pool if q.get("id") not in excluded]
        candidates = fresh if fresh else pool

        broad_q = [q for q in candidates if str(q.get("scope", "")).upper() == "BROAD"]
        specific_q = [q for q in candidates if str(q.get("scope", "")).upper() != "BROAD"]
        random.shuffle(broad_q)
        random.shuffle(specific_q)

        # 1. Prioritize weak questions for retry
        # 2. Prioritize questions matching the candidate's target difficulty on that concept ladder
        def _specific_sort_key(q: Dict[str, Any]) -> Tuple[int, int]:
            is_weak = 0 if q.get("id") in weak_ids else 1
            concept = q.get("concept")
            target_diff = ladder.get(concept)
            q_diff = str(q.get("difficulty_level", "")).upper()
            diff_match = 0 if (target_diff and q_diff == target_diff) else 1
            return (is_weak, diff_match)

        specific_q.sort(key=_specific_sort_key)

        subj_selected: List[Dict[str, Any]] = []
        subject_time = 0
        used_concepts: Set[str] = set()

        # Step A: Warm-Up Question (Confidence Builder)
        easy_warmup = [
            q for q in specific_q
            if str(q.get("difficulty_level", "")).upper() == "EASY"
        ]
        for eq in easy_warmup:
            eq_time = self.get_question_time_limit(eq)
            if eq.get("id") not in selected_ids and (subject_time + eq_time) <= budget:
                eq_copy = dict(eq)
                eq_copy["time_limit_seconds"] = eq_time
                subj_selected.append(eq_copy)
                selected_ids.add(eq.get("id"))
                subject_time += eq_time
                if eq.get("concept"):
                    used_concepts.add(eq.get("concept"))
                break

        # Step B: Broad Question (1 architectural question per subject)
        for bq in broad_q:
            b_time = self.get_question_time_limit(bq)
            if bq.get("id") not in selected_ids and (subject_time + b_time) <= budget:
                bq_copy = dict(bq)
                bq_copy["time_limit_seconds"] = b_time
                subj_selected.append(bq_copy)
                selected_ids.add(bq.get("id"))
                subject_time += b_time
                if bq.get("concept"):
                    used_concepts.add(bq.get("concept"))
                break

        # Step C: Specific Questions rotating unique concepts
        available_concepts = {q.get("concept") for q in specific_q if q.get("concept")}
        for sq in specific_q:
            s_id = sq.get("id")
            s_concept = sq.get("concept")
            s_time = self.get_question_time_limit(sq)

            if s_id in selected_ids:
                continue

            if s_concept and s_concept in used_concepts and len(used_concepts) < len(available_concepts):
                continue

            if (subject_time + s_time) <= budget:
                sq_copy = dict(sq)
                sq_copy["time_limit_seconds"] = s_time
                subj_selected.append(sq_copy)
                selected_ids.add(s_id)
                subject_time += s_time
                if s_concept:
                    used_concepts.add(s_concept)

        return subj_selected, subject_time

    def _find_exact_fit(
        self,
        pool: List[Dict[str, Any]],
        target_sum: int,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Finds questions in the unused pool whose durations sum to exactly target_sum
        using a bounded Subset-Sum Dynamic Programming algorithm (O(N * W)).
        Supports exact fits of ANY number of questions (1, 2, 3, 4+).
        """
        if target_sum <= 0:
            return []

        candidates = [q for q in pool if 0 < self.get_question_time_limit(q) <= target_sum]
        if not candidates:
            return None

        # 1. Quick check: Single-question exact match
        for q in candidates:
            if self.get_question_time_limit(q) == target_sum:
                return [q]

        # 2. DP Subset-Sum directly mapping: sum -> List[Question]
        # Bounded by target_sum <= 900 (at most 901 entries in memory).
        # Eliminates backtracking pointers entirely, making broken chains or infinite loops impossible.
        dp: Dict[int, List[Dict[str, Any]]] = {0: []}

        for q in candidates:
            w = self.get_question_time_limit(q)
            new_entries: Dict[int, List[Dict[str, Any]]] = {}
            for s, combo in dp.items():
                ns = s + w
                if ns == target_sum:
                    return combo + [q]
                if ns < target_sum and ns not in dp and ns not in new_entries:
                    new_entries[ns] = combo + [q]

            dp.update(new_entries)

        return None

    def _top_up_remaining_seconds(
        self,
        tech_pool: List[Dict[str, Any]],
        selected: List[Dict[str, Any]],
        selected_ids: Set[int],
        excluded: Set[int],
        current_total_time: int,
        target_seconds: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Fills remaining slack seconds to hit exactly target_seconds (900s)."""
        remaining_seconds = target_seconds - current_total_time
        if remaining_seconds <= 0:
            return selected, current_total_time

        skip_ids = selected_ids | set(excluded or [])
        unused_pool = [q for q in tech_pool if q.get("id") not in skip_ids]
        unused_pool.sort(key=lambda x: 0 if self.normalize_subject(x.get("subject")) == "AI Engineering" else 1)

        # 1. Exact-Fit: Find exact combination to hit spot on 900s
        exact_match = self._find_exact_fit(unused_pool, remaining_seconds)
        if exact_match:
            for q in exact_match:
                q_copy = dict(q)
                q_time = self.get_question_time_limit(q)
                q_copy["time_limit_seconds"] = q_time
                selected.append(q_copy)
                selected_ids.add(q.get("id"))
                current_total_time += q_time
            return selected, current_total_time

        # 2. Fallback: Standard greedy fill if exact combo is mathematically unavailable in pool
        for uq in unused_pool:
            u_time = self.get_question_time_limit(uq)
            if u_time <= remaining_seconds:
                uq_copy = dict(uq)
                uq_copy["time_limit_seconds"] = u_time
                selected.append(uq_copy)
                selected_ids.add(uq.get("id"))
                remaining_seconds -= u_time
                current_total_time += u_time
                if remaining_seconds < 60:
                    break

        return selected, current_total_time

    @classmethod
    def sequence_fatigue_aware_order(cls, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sequences selected technical questions to prevent candidate cognitive fatigue.
        
        Pacing curve:
        1. Openers (Minutes 0-2): EASY SPECIFIC questions to settle in and build momentum.
        2. Mid-Session Peak (Minutes 3-10): Heavy BROAD architectural questions & HARD questions
           placed while candidate cognitive energy is at its highest.
        3. Closers (Minutes 11-15): Crisp SPECIFIC questions (MEDIUM/EASY) to finish strong
           without confronting massive open-ended system design in the final 2 minutes.
        """
        if len(questions) <= 2:
            return questions

        openers: List[Dict[str, Any]] = []
        mid_peak: List[Dict[str, Any]] = []
        closers: List[Dict[str, Any]] = []

        for q in questions:
            is_broad = str(q.get("scope", "")).upper() == "BROAD"
            diff = str(q.get("difficulty_level", "")).upper()

            # Heavy architectural/hard questions go to the mid-session peak
            if is_broad or diff == "HARD":
                mid_peak.append(q)
            # Up to 2 easy specific questions serve as openers/warm-ups
            elif diff == "EASY" and len(openers) < 2:
                openers.append(q)
            # Everything else forms the closing stretch
            else:
                closers.append(q)

        # If no easy openers exist, move the first non-broad question to opener
        if not openers and closers:
            openers.append(closers.pop(0))

        return openers + mid_peak + closers

    def _sanitize_question_for_candidate(self, question: Dict[str, Any]) -> Dict[str, Any]:
        """
        Returns candidate-facing fields from a question dict.
        Internal/admin columns (rubric, evaluation hints, etc.) are excluded.
        """
        qid = question.get("id") or question.get("question_id")
        return {
            "id": qid,
            "question_id": qid,
            "category": question.get("category"),
            "question_text": question.get("question_text", ""),
            "subject": question.get("subject"),
            "concept": question.get("concept"),
            "difficulty_level": question.get("difficulty_level"),
            "time_limit_seconds": self.get_question_time_limit(question),
        }

    # =========================================================================
    # 2. CONTEXT BUILDING
    # =========================================================================

    def build_qa_context(
        self,
        questions: List[Dict[str, Any]],
        transcript: Dict[str, Any],
    ) -> str:
        """
        Builds a structured Q&A context string from submitted questions and transcript.

        Used by the LLMEvaluationEngine to construct the transcript evaluation prompt.

        Args:
            questions:   List of question dicts (from assessment data record).
            transcript:  Transcript dict with 'full_text' (or 'text') key.

        Returns:
            Formatted multi-line string combining questions and transcript text.
        """
        lines: List[str] = []

        if questions:
            lines.append("=== Interview Questions ===")
            for idx, q in enumerate(questions, start=1):
                q_text = q.get("question_text") or q.get("text") or f"Question {idx}"
                q_id = q.get("id") or q.get("question_id") or idx
                difficulty = str(q.get("difficulty_level", "")).upper() or "MEDIUM"
                subject = q.get("subject") or "Unknown"
                concept = q.get("concept") or "Unknown"
                scope = q.get("scope") or "SPECIFIC"

                lines.append(f"Q{idx}")
                lines.append(f"  question_id: {q_id}")
                lines.append(f"  subject: {subject}")
                lines.append(f"  concept: {concept}")
                lines.append(f"  difficulty_level: {difficulty}")
                lines.append(f"  scope: {scope}")
                lines.append(f"  question: {q_text}")

                gt = q.get("ground_truth")
                if isinstance(gt, dict):
                    criteria = gt.get("criteria") or gt.get("key_points") or []
                    keywords = list(gt.get("technical_keywords") or [])
                    # Extract inline technical keywords from acceptable_evidence if top-level list is empty
                    if not keywords and criteria:
                        for c in criteria:
                            if isinstance(c, dict):
                                ev_candidates = c.get("acceptable_evidence") or []
                                if isinstance(ev_candidates, str):
                                    ev_candidates = [ev_candidates]
                                for ev in ev_candidates:
                                    if "Technical keywords:" in ev:
                                        kw_part = ev.split("Technical keywords:", 1)[1].strip().rstrip(".")
                                        for kw in kw_part.split(","):
                                            cleaned = kw.strip().strip("`")
                                            if cleaned and cleaned not in keywords:
                                                keywords.append(cleaned)
                    critical = gt.get("critical_failures") or []
                    lines.append("  ground_truth:")
                    if criteria:
                        lines.append("    criteria:")
                        for c in criteria:
                            if isinstance(c, dict):
                                kp_id = c.get("id") or ""
                                desc = c.get("description") or c.get("point") or ""
                                req = " (required)" if c.get("required") else ""
                                id_prefix = f"[{kp_id}] " if kp_id else ""
                                lines.append(f"      - {id_prefix}{desc}{req}")
                                ev_candidates = c.get("acceptable_evidence") or []
                                if isinstance(ev_candidates, str):
                                    ev_candidates = [ev_candidates]
                                for ev in ev_candidates:
                                    lines.append(f"        * evidence: {ev}")
                            else:
                                lines.append(f"      - {str(c)}")
                    if keywords:
                        lines.append(f"    technical_keywords: {', '.join(keywords)}")
                    if critical:
                        lines.append("    critical_failures:")
                        for cf in critical:
                            lines.append(f"      - {cf}")
                elif gt:
                    lines.append(f"  ground_truth: {gt}")

                lines.append("")
            lines.append("")

        full_text = ""
        if isinstance(transcript, dict):
            full_text = (
                transcript.get("full_text")
                or transcript.get("text")
                or transcript.get("transcript_text")
                or ""
            )

        lines.append("=== Candidate Transcript ===")
        lines.append(full_text.strip() if full_text else "[No transcript provided]")

        return "\n".join(lines)

    def build_audio_context(self, audio_telemetry: Dict[str, Any]) -> str:
        """
        Converts raw audio telemetry dict into a human-readable context string.
        Used by the LLMEvaluationEngine for audio prompt building.

        Args:
            audio_telemetry: Dict with fields like words_per_minute, silence_ratio_pct, etc.

        Returns:
            Formatted audio telemetry summary string.
        """
        if not audio_telemetry or not isinstance(audio_telemetry, dict):
            return "Audio telemetry: [Not available]"

        wpm = (
            audio_telemetry.get("speaking_pace_wpm")
            or audio_telemetry.get("words_per_minute")
            or audio_telemetry.get("wpm")
            or 0
        )
        silence = audio_telemetry.get("silence_ratio_pct", audio_telemetry.get("silence_ratio", 0))
        duration = audio_telemetry.get("speaking_duration_seconds", 0)
        filler_rate = audio_telemetry.get("filler_rate_per_min", audio_telemetry.get("filler_rate", 0))
        pause_count = audio_telemetry.get("pause_count", audio_telemetry.get("pauses", 0))
        avg_volume = audio_telemetry.get("avg_volume_db", -20.0)
        noise_level = audio_telemetry.get("background_noise_level", "LOW")
        clipping = audio_telemetry.get("clipping_detected", False)

        return (
            f"Audio Telemetry Summary:\n"
            f"  Speaking Pace:      {wpm} WPM\n"
            f"  Speaking Duration:  {duration}s\n"
            f"  Silence Ratio:      {silence}%\n"
            f"  Filler Rate:        {filler_rate} per minute\n"
            f"  Pause Count:        {pause_count}\n"
            f"  Average Volume:     {avg_volume} dB\n"
            f"  Background Noise:   {noise_level}\n"
            f"  Clipping Detected:  {clipping}"
        )

    def build_video_context(self, video_telemetry: Dict[str, Any]) -> str:
        """
        Converts raw video telemetry dict into a human-readable context string.
        Used by the LLMEvaluationEngine for video prompt building.

        Args:
            video_telemetry: Dict with fields like face_visible_pct, eye_contact_pct, etc.

        Returns:
            Formatted video telemetry summary string.
        """
        if not video_telemetry or not isinstance(video_telemetry, dict):
            return "Video telemetry: [Not available]"

        is_video = video_telemetry.get("is_video_mode", False)
        if not is_video:
            return "Video telemetry: [Audio-only session — no video data]"

        face_pct = video_telemetry.get("face_visible_pct", video_telemetry.get("face_detection_pct", 0))
        eye_contact = video_telemetry.get("eye_contact_pct", 0)
        screen_attention = video_telemetry.get("screen_attention_pct", 0)
        distraction = video_telemetry.get("distraction_level_pct", 0)
        stress = video_telemetry.get("stress_level", "Normal")
        head_nods = video_telemetry.get("head_nods_count", 0)

        return (
            f"Video Telemetry Summary:\n"
            f"  Face Visibility:    {face_pct}%\n"
            f"  Eye Contact:        {eye_contact}%\n"
            f"  Screen Attention:   {screen_attention}%\n"
            f"  Distraction Level:  {distraction}%\n"
            f"  Stress Level:       {stress}\n"
            f"  Head Nods:          {head_nods}"
        )

    # =========================================================================
    # 3. ELIGIBILITY CHECKS (pure logic, no DB)
    # =========================================================================

    def is_candidate_eligible(
        self,
        llm_check: Optional[Dict[str, Any]],
        resume_check: Optional[Dict[str, Any]],
    ) -> bool:
        """
        Pure business rule: candidate is eligible only if both LLM key
        and resume are configured and valid. Safely handles None inputs.

        Args:
            llm_check:    Result dict from crud.check_candidate_llm_key() (or None).
            resume_check: Result dict from crud.check_candidate_resume() (or None).

        Returns:
            True if candidate passes all prerequisite checks.
        """
        llm_dict = llm_check or {}
        resume_dict = resume_check or {}

        llm_ok = bool(llm_dict.get("is_configured")) and llm_dict.get("status") == "valid"
        resume_ok = bool(resume_dict.get("has_resume")) and resume_dict.get("status") == "valid"
        return llm_ok and resume_ok

    def compute_eligibility_message(
        self,
        llm_check: Optional[Dict[str, Any]],
        resume_check: Optional[Dict[str, Any]],
    ) -> str:
        """
        Generates a human-readable eligibility summary message. Safely handles None inputs.
        """
        llm_dict = llm_check or {}
        resume_dict = resume_check or {}

        issues = []
        if not llm_dict.get("is_configured"):
            issues.append("LLM API key not configured")
        if not resume_dict.get("has_resume"):
            issues.append("Resume not uploaded")

        if not issues:
            return "Candidate meets all prerequisites. Ready to start assessment."
        return "Candidate is not ready: " + "; ".join(issues) + "."

    # =========================================================================
    # 4. STATE VALIDATION (pure logic, no DB)
    # =========================================================================

    def is_valid_transition(self, current_status: str, target_status: str) -> bool:
        """
        Returns True if transitioning from current_status → target_status is allowed.

        Valid transitions:
          IN_PROGRESS  → EVALUATING | FAILED
          EVALUATING   → COMPLETED  | FAILED
          COMPLETED    → (terminal — no transitions)
          FAILED       → (terminal — no transitions)
        """
        allowed = self.VALID_TRANSITIONS.get(current_status.upper(), [])
        return target_status.upper() in allowed



# Module-level alias for compatibility with orchestrator imports
AssessmentBusinessEngine = AssessmentEngine

__all__ = ["AssessmentEngine", "AssessmentBusinessEngine"]
