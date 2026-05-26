"""Apply chronological temporal sequencing to a case's stored timeline rows.

Single source of truth shared by:
  * the live Step-3 pipeline hook (`run_step3_task`, study-corrections A1), and
  * the corpus backfill driver (`docs-internal/scripts/backfill_temporal_sequence.py`).

Reads the case's `temporal_dynamics_enhanced` Action/Event rows, asks the
TemporalSequenceExtractor for a chronological permutation of their IRIs, and
writes a 1-based `proeth:temporalSequence` integer onto each row. The
validation timeline view (`synthesis_view_builder.get_timeline_view`) orders by
this field and falls back to row id when it is absent.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _row_kind(at_type: str) -> str:
    if "Action" in at_type:
        return "action"
    if "Event" in at_type:
        return "event"
    return ""


def apply_temporal_sequence(
    case_id: int,
    extractor: Optional[Any] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Populate `proeth:temporalSequence` on a case's timeline rows.

    Returns a status dict: ``status`` in {ok, dry_run, insufficient_entries},
    plus ``entries`` and (when applied) ``rows_updated`` and ``rationale``.
    Constructs a default TemporalSequenceExtractor when one is not supplied.
    """
    from app.models import db
    from app.models.temporary_rdf_storage import TemporaryRDFStorage
    from app.services.extraction.temporal_sequence import TemporalEntryContext
    from sqlalchemy.orm.attributes import flag_modified

    rows = (
        TemporaryRDFStorage.query
        .filter_by(case_id=case_id, extraction_type="temporal_dynamics_enhanced")
        .order_by(TemporaryRDFStorage.id)
        .all()
    )

    entries: List[TemporalEntryContext] = []
    iri_to_row: Dict[str, Any] = {}
    for r in rows:
        rdf = r.rdf_json_ld or {}
        kind = _row_kind(rdf.get("@type", "") or "")
        if not kind:
            continue
        iri = rdf.get("@id", "")
        if not iri:
            continue
        if iri in iri_to_row:
            logger.warning(
                "case %s: duplicate IRI %s on rows %s and %s; skipping the second",
                case_id, iri, iri_to_row[iri].id, r.id,
            )
            continue
        entries.append(
            TemporalEntryContext(
                iri=iri,
                kind=kind,
                label=r.entity_label or rdf.get("rdfs:label", "") or "",
                temporal_marker=rdf.get("proeth:temporalMarker", "") or "",
                description=rdf.get("proeth:description", "") or "",
            )
        )
        iri_to_row[iri] = r

    if len(entries) < 2:
        return {"case_id": case_id, "status": "insufficient_entries", "entries": len(entries)}

    if dry_run:
        return {"case_id": case_id, "status": "dry_run", "entries": len(entries)}

    if extractor is None:
        from app.services.extraction.temporal_sequence import TemporalSequenceExtractor
        extractor = TemporalSequenceExtractor()

    result = extractor.extract(case_id=case_id, entries=entries)
    iri_to_seq = {iri: i + 1 for i, iri in enumerate(result.ordered_iris)}

    rows_updated = 0
    for iri, seq in iri_to_seq.items():
        row = iri_to_row.get(iri)
        if row is None:
            continue
        rdf = dict(row.rdf_json_ld or {})
        if rdf.get("proeth:temporalSequence") == seq:
            continue
        rdf["proeth:temporalSequence"] = seq
        row.rdf_json_ld = rdf
        flag_modified(row, "rdf_json_ld")
        rows_updated += 1
    db.session.commit()

    return {
        "case_id": case_id,
        "status": "ok",
        "entries": len(entries),
        "rows_updated": rows_updated,
        "rationale": result.rationale,
    }
