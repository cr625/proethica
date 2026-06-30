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
_OVERREACH_VOTES = 5
_OVERREACH_DROP_AT = 4   # supermajority of a 5-vote panel: cuts the run-to-run variance a 3/3-unanimous
                         # threshold suffered (a single dissenter no longer blocks a clear over-reach),
                         # while 4/5 keeps false drops near zero. Below 4/5 is flagged, not dropped.


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

    ``entities``: dicts with 'id', 'label', 'definition', 'quotes' (list), 'component' (extraction_type),
    'storage_type' ('class'|'individual'), and 'class_ref' (the class label a duty individual instantiates).
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

    # 2. Over-reach over the surviving duty CLASSES (obligations + constraints), multi-vote. Detection runs
    #    on classes because that is where the canonicalization/injection loop lives. The DROP then cascades
    #    to the duty individuals that instantiate a dropped class (step 2b), so an over-reaching duty does not
    #    survive as a committed individual -- including when the individual matched a PRE-EXISTING (dirty)
    #    class of the same label rather than minting a new one, which the class-only drop would miss.
    duties = [e for e in live
              if (e.get('component') or '').lower() in _DUTY_COMPONENTS
              and (e.get('storage_type') or 'class') == 'class'
              and e.get('id') not in res.dropped_ids]
    overreach_dropped_labels = set()
    if duties:
        overs = detect_overreach(case_text, duties, model=model, votes=_OVERREACH_VOTES)
        for e, v in zip(duties, overs):
            if not v.overreach:
                continue
            if v.votes_for >= _OVERREACH_DROP_AT:
                res.dropped.append((e.get('id'), e.get('label'),
                                    f'over-reach ({v.votes_for}/{v.votes_total}): {v.reason}'))
                overreach_dropped_labels.add(str(e.get('label') or '').strip())
            else:
                res.flagged.append((e.get('id'), e.get('label'), v.reason, v.limiting_quote))

    # 2b. Cascade the over-reach drop to the duty INDIVIDUALS that instantiate a dropped class (matched by
    #     their class_ref label). The class drop alone breaks the loop, but a matched over-reaching individual
    #     would still commit and assert the duty; dropping it keeps the over-reach out of the committed case.
    if overreach_dropped_labels:
        for e in live:
            if e.get('id') in res.dropped_ids:
                continue
            if (e.get('component') or '').lower() in _DUTY_COMPONENTS \
               and (e.get('storage_type') or '') == 'individual' \
               and str(e.get('class_ref') or '').strip() in overreach_dropped_labels:
                res.dropped.append((e.get('id'), e.get('label'),
                                    f"over-reach cascade: instance of dropped class '{e.get('class_ref')}'"))

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


def quotes_of(rdf_json_ld: Dict) -> List[str]:
    """Extract an entity's quote list from temp_rdf rdf_json_ld for the gate input. Prefers the full
    properties.textReferences list, falling back to the primary source_text."""
    jl = rdf_json_ld or {}
    q = (jl.get('properties') or {}).get('textReferences') or []
    if not q and jl.get('source_text'):
        q = [jl['source_text']]
    return [s for s in q if s and str(s).strip()]


def class_ref_of(rdf_json_ld: Dict) -> str:
    """The class label a duty individual instantiates, from temp_rdf rdf_json_ld (properties.*Class), for
    the over-reach cascade -- so an individual whose duty class was dropped for over-reach can be dropped
    with it, even when it matched a pre-existing class of that label rather than minting a new one."""
    props = (rdf_json_ld or {}).get('properties') or {}
    for k in ('obligationClass', 'constraintClass'):
        v = props.get(k)
        if v:
            return str(v[0] if isinstance(v, list) else v).strip()
    return ''


def apply_corrected_quotes(rdf_json_ld: Dict, spans: List[str]) -> Dict:
    """Return a copy of rdf_json_ld with EVERY quote-bearing field replaced by the verified verbatim
    ``spans`` (from GateResult.corrected_quotes). The quote is denormalized across four fields and the
    commit reads more than one (properties.textReferences -> proeth:textReferences; properties.sourceText
    and the top-level source_texts/source_text -> proeth-prov:sourceText), so all are rewritten and no
    paraphrase survives into the committed TTL. source_texts keeps its section keys, each mapped to the
    primary span (per-quote section attribution is not recoverable from the grounding pass; the full set
    is preserved in textReferences)."""
    if not spans:
        return rdf_json_ld
    jl = dict(rdf_json_ld or {})
    props = dict(jl.get('properties') or {})
    props['textReferences'] = list(spans)
    props['sourceText'] = list(spans)
    jl['properties'] = props
    jl['source_text'] = spans[0]
    sections = list((jl.get('source_texts') or {}).keys()) or ['facts']
    jl['source_texts'] = {sec: spans[0] for sec in sections}
    return jl
