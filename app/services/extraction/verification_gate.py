"""Per-case verification gate: the commit-time chokepoint.

Runs the verifier on a case's entities AFTER extraction but BEFORE they are committed and
canonicalized into the extended ontology (wired in run_commit_task, just before
commit_selected_entities -> _commit_classes_to_intermediate writes discoveredInCase to disk). Two
jobs, matching the two verifier checks:

  - Over-reach (the loop-breaker): a duty whose definition asserts more than the case holds is
    DROPPED at high confidence (votes=3/3) so it never canonicalizes and never gets injected back
    into later extractions. Lower-confidence flags are recorded, not deleted. Runs on the direct
    entity_label / entity_definition columns -- no quote parsing needed.
  - Verbatim grounding: each non-verbatim quote is re-grounded to a confirmed span; an entity whose
    every quote is unsupportable is a fabrication and is dropped. Operates on the entity 'quotes'.

The gate returns a GateResult; the caller applies it (filter the committed entity_ids by `dropped`,
rewrite quotes from `corrected_quotes`). The gate itself is pure: it decides, it does not mutate
temp_rdf, so it is unit-testable on plain dicts.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List

from app.services.extraction.extraction_verifier import verify_and_reground, detect_overreach

logger = logging.getLogger(__name__)

_DUTY_COMPONENTS = {'obligations', 'constraints'}
_OVERREACH_VOTES = 3
_OVERREACH_DROP_AT = 3   # drop only when all votes agree; flag-and-keep below that


@dataclass
class GateResult:
    corrected_quotes: Dict[object, List[str]] = field(default_factory=dict)   # {entity_id: [verbatim spans]}
    dropped: List[tuple] = field(default_factory=list)                        # [(entity_id, label, reason)]
    flagged: List[tuple] = field(default_factory=list)                        # [(entity_id, label, reason, limiting_quote)]
    report: Dict = field(default_factory=dict)

    @property
    def dropped_ids(self) -> set:
        return {d[0] for d in self.dropped}


def verify_case_entities(entities: List[Dict], case_text: str, case_id, model: str = 'claude-opus-4-8') -> GateResult:
    """Decide the commit fate of a case's entities.

    ``entities``: dicts with 'id', 'label', 'definition', 'quotes' (list), 'component' (extraction_type).
    Returns a GateResult; the caller applies the drops and quote rewrites. Pure / no side effects."""
    res = GateResult()

    # 0. Null/empty labels -> drop (deterministic).
    live: List[Dict] = []
    for e in entities:
        if not str(e.get('label') or '').strip():
            res.dropped.append((e.get('id'), '(empty label)', 'empty label'))
        else:
            live.append(e)

    # 1. Verbatim grounding over every live entity: re-ground paraphrases, drop full fabrications.
    if live:
        gverdicts = verify_and_reground(case_text, live, model=model)
        for e, v in zip(live, gverdicts):
            if v.unsupported and not v.regrounded and not v.kept_verbatim:
                res.dropped.append((e.get('id'), e.get('label'), 'fabrication: no quote has a supporting span'))
            elif v.regrounded or v.unsupported:
                # the quote set changed (some re-grounded and/or some unsupported dropped)
                res.corrected_quotes[e.get('id')] = v.kept_verbatim + v.regrounded

    # 2. Over-reach over the surviving duty CLASSES (obligations + constraints), multi-vote. Restricted
    #    to classes because only classes canonicalize into the extended ontology -- that is where the
    #    injection feedback loop lives. An over-reaching individual is a per-case quality issue, not a
    #    loop one, and is left to the verbatim/backfill pass.
    duties = [e for e in live
              if (e.get('component') or '').lower() in _DUTY_COMPONENTS
              and (e.get('storage_type') or 'class') == 'class'
              and e.get('id') not in res.dropped_ids]
    if duties:
        overs = detect_overreach(case_text, duties, model=model, votes=_OVERREACH_VOTES)
        for e, v in zip(duties, overs):
            if not v.overreach:
                continue
            if v.votes_for >= _OVERREACH_DROP_AT:
                res.dropped.append((e.get('id'), e.get('label'),
                                    f'over-reach ({v.votes_for}/{v.votes_total}): {v.reason}'))
            else:
                res.flagged.append((e.get('id'), e.get('label'), v.reason, v.limiting_quote))

    res.report = {
        'case_id': case_id,
        'entities': len(entities),
        'requoted': len(res.corrected_quotes),
        'dropped': len(res.dropped),
        'flagged': len(res.flagged),
        'dropped_detail': [{'label': l, 'reason': r} for _, l, r in res.dropped],
        'flagged_detail': [{'label': l, 'reason': r, 'limit': q} for _, l, r, q in res.flagged],
    }
    logger.info(f"[verification-gate] case {case_id}: {len(res.corrected_quotes)} re-grounded, "
                f"{len(res.dropped)} dropped, {len(res.flagged)} flagged")
    return res
