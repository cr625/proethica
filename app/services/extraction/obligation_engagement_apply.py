"""Reclassify Action obligation engagement (fulfills/violates/raises) for a case.

Single source of truth shared by:
  * the live Step-2 pipeline hook (`run_step2_task`, study-corrections A3), and
  * the corpus backfill driver (`docs-internal/scripts/backfill_obligation_engagement.py`).

Step-2 extraction tags each Action's obligations as either fulfilled or violated.
That binary misses the common case where an Action merely *raises* (activates) an
obligation without yet fulfilling or violating it. This pass asks the
ObligationEngagementExtractor to re-partition each Action's obligations into
fulfills / violates / raises, seeing the actions in chronological order
(`proeth:temporalSequence`) so the engagement reads as a narrative chain.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DISCUSSION_MAX_CHARS = 6000


def _is_action(at_type: str) -> bool:
    return "Action" in (at_type or "")


def _load_discussion(case_id: int) -> str:
    from app.models.document_section import DocumentSection
    sec = (
        DocumentSection.query
        .filter_by(document_id=case_id, section_type="discussion")
        .first()
    )
    if not sec or not sec.content:
        return ""
    return sec.content[:DISCUSSION_MAX_CHARS]


def _load_case_title(case_id: int) -> str:
    from app.models.document import Document
    doc = Document.query.get(case_id)
    return doc.title if doc else f"Case {case_id}"


def _norm(s: str) -> str:
    """Normalize obligation strings as the extractor validator does."""
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def _reconcile_to_pool(ctx, pa):
    """Reconcile the LLM partition to the Action's own input pool (deterministic).

    Keeps the LLM's bucket choice for every obligation that is IN the pool
    (fulfills + violates + existing raises), drops any extra the LLM invented
    (e.g. an obligation carried from another Action), and restores any pool
    obligation the LLM dropped to its original bucket. Guarantees the result is
    valid (union == pool, no duplicates), so the case always gets its raises
    buckets instead of none. Returns (fulfills, violates, raises) of original
    strings.
    """
    disp = {}          # norm -> original input string (the pool is the input)
    orig_bucket = {}   # norm -> 'fulfills' | 'violates' | 'raises'
    for o in ctx.fulfills:
        n = _norm(o); disp.setdefault(n, o); orig_bucket.setdefault(n, "fulfills")
    for o in ctx.violates:
        n = _norm(o); disp.setdefault(n, o); orig_bucket.setdefault(n, "violates")
    for o in (getattr(ctx, "raises", None) or []):
        n = _norm(o); disp.setdefault(n, o); orig_bucket.setdefault(n, "raises")

    llm_bucket = {}    # norm -> first bucket the LLM placed it in
    for o in pa.fulfills:
        llm_bucket.setdefault(_norm(o), "fulfills")
    for o in pa.violates:
        llm_bucket.setdefault(_norm(o), "violates")
    for o in pa.raises:
        llm_bucket.setdefault(_norm(o), "raises")

    out = {"fulfills": [], "violates": [], "raises": []}
    for n, original in disp.items():
        out[llm_bucket.get(n, orig_bucket[n])].append(original)
    return out["fulfills"], out["violates"], out["raises"]


def apply_obligation_engagement(
    case_id: int,
    extractor: Optional[Any] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Re-partition Action obligations into fulfills/violates/raises.

    Returns a status dict: ``status`` in {ok, dry_run, no_actions}.
    Constructs a default ObligationEngagementExtractor when none is supplied.
    """
    from app.models import db
    from app.models.temporary_rdf_storage import TemporaryRDFStorage
    from app.services.extraction.obligation_engagement import ActionEngagementContext
    from sqlalchemy.orm.attributes import flag_modified

    rows = (
        TemporaryRDFStorage.query
        .filter_by(case_id=case_id, extraction_type="temporal_dynamics_enhanced")
        .order_by(TemporaryRDFStorage.id)
        .all()
    )

    actions: List[ActionEngagementContext] = []
    iri_to_row: Dict[str, Any] = {}
    for r in rows:
        rdf = r.rdf_json_ld or {}
        if not _is_action(rdf.get("@type", "") or ""):
            continue
        iri = rdf.get("@id", "")
        if not iri:
            continue
        fulfills_raw = rdf.get("proeth:fulfillsObligation", []) or []
        violates_raw = rdf.get("proeth:violatesObligation", []) or []
        raises_raw = rdf.get("proeth:raisesObligation", []) or []
        if not isinstance(fulfills_raw, list):
            fulfills_raw = []
        if not isinstance(violates_raw, list):
            violates_raw = []
        if not isinstance(raises_raw, list):
            raises_raw = []
        if not fulfills_raw and not violates_raw and not raises_raw:
            continue
        seq = rdf.get("proeth:temporalSequence")
        try:
            seq_int = int(seq) if seq is not None else None
        except (TypeError, ValueError):
            seq_int = None
        actions.append(
            ActionEngagementContext(
                iri=iri,
                label=r.entity_label or rdf.get("rdfs:label", "") or "",
                description=rdf.get("proeth:description", "") or "",
                sequence=seq_int,
                fulfills=list(fulfills_raw),
                violates=list(violates_raw),
                raises=list(raises_raw),
            )
        )
        iri_to_row[iri] = r

    if not actions:
        return {"case_id": case_id, "status": "no_actions"}

    actions.sort(key=lambda a: (a.sequence is None, a.sequence or 0))

    if dry_run:
        return {
            "case_id": case_id,
            "status": "dry_run",
            "actions": len(actions),
            "obligations": sum(len(a.fulfills) + len(a.violates) for a in actions),
        }

    if extractor is None:
        from app.services.extraction.obligation_engagement import ObligationEngagementExtractor
        extractor = ObligationEngagementExtractor()

    # Lenient: get the parsed partition even if it does not validate, then
    # reconcile each Action to its own input pool below. This replaces the prior
    # behaviour where a single validation failure (e.g. the LLM carrying an
    # obligation across actions, which the system prompt invites) raised and the
    # caller swallowed it, writing NO raises buckets for the whole case.
    result = extractor.extract(
        case_id=case_id,
        case_title=_load_case_title(case_id),
        actions=actions,
        discussion_excerpt=_load_discussion(case_id),
        strict=False,
    )

    rows_updated = 0
    raises_emitted = 0
    moved_from_fulfills = 0
    moved_from_violates = 0
    pa_by_iri = {pa.action_iri: pa for pa in result.actions}

    for ctx in actions:
        pa = pa_by_iri.get(ctx.iri)
        if pa is None:
            continue
        row = iri_to_row[ctx.iri]
        rdf = dict(row.rdf_json_ld or {})

        # Reconcile the LLM partition to this Action's own input pool so the
        # result is always valid (drops cross-action extras, restores drops).
        f_out, v_out, r_out = _reconcile_to_pool(ctx, pa)

        old_fulfills = {_norm(s) for s in ctx.fulfills}
        old_violates = {_norm(s) for s in ctx.violates}
        new_raises_set = {_norm(s) for s in r_out}
        moved_from_fulfills += len(old_fulfills & new_raises_set)
        moved_from_violates += len(old_violates & new_raises_set)

        rdf["proeth:fulfillsObligation"] = f_out
        rdf["proeth:violatesObligation"] = v_out
        rdf["proeth:raisesObligation"] = r_out
        row.rdf_json_ld = rdf
        flag_modified(row, "rdf_json_ld")
        rows_updated += 1
        raises_emitted += len(r_out)

    db.session.commit()

    return {
        "case_id": case_id,
        "status": "ok",
        "actions": len(actions),
        "rows_updated": rows_updated,
        "raises_emitted": raises_emitted,
        "moved_from_fulfills": moved_from_fulfills,
        "moved_from_violates": moved_from_violates,
        "rationale": result.rationale,
    }
