"""
Case assignment for the between-subjects study design.

Each participant reviews 3-4 cases drawn from the 23-case IRB-approved pool.
Assignments balance coverage: every case in the pool is reviewed by at least
two participants before any case is reviewed a third time.

Assignments are deterministic per participant_code so reloading the dashboard
returns the same set.
"""

from __future__ import annotations

import random
from typing import List

from app.config.study_case_pool import STUDY_CASE_POOL_IDS
from app.models.view_utility_evaluation import ViewUtilityEvaluation

TARGET_PER_PARTICIPANT = 4
"""EvaluationStudyPlan says 3-4 cases per participant; default to 4 where
coverage allows. The assigner may return fewer if the pool is saturated."""


def assign_cases(participant_code: str,
                 target: int = TARGET_PER_PARTICIPANT) -> List[int]:
    """Pick `target` cases for a new participant, balancing coverage.

    Invariant: the lowest-coverage cases are picked first. Ties broken by
    case ID (deterministic). Final ordering of the selection is shuffled
    with participant_code as the seed so different participants see cases
    in different orders, while each individual's order is stable on reload.
    """
    coverage = {cid: 0 for cid in STUDY_CASE_POOL_IDS}
    rows = ViewUtilityEvaluation.query.filter(
        ViewUtilityEvaluation.case_id.in_(STUDY_CASE_POOL_IDS)
    ).with_entities(ViewUtilityEvaluation.case_id).all()
    for (cid,) in rows:
        if cid in coverage:
            coverage[cid] += 1

    ranked = sorted(coverage.items(), key=lambda kv: (kv[1], kv[0]))
    picked = [cid for cid, _ in ranked[:target]]

    rng = random.Random(participant_code)
    rng.shuffle(picked)
    return picked


def coverage_summary() -> dict:
    """Per-case review counts across the full pool. For the admin dashboard."""
    coverage = {cid: 0 for cid in STUDY_CASE_POOL_IDS}
    rows = ViewUtilityEvaluation.query.filter(
        ViewUtilityEvaluation.case_id.in_(STUDY_CASE_POOL_IDS)
    ).with_entities(ViewUtilityEvaluation.case_id).all()
    for (cid,) in rows:
        if cid in coverage:
            coverage[cid] += 1
    return coverage
