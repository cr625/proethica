"""OWL-Time anchor materialization (deterministic).

The Step-3 converter records, per happening (Action or Event), a proeth:temporalExtent
literal classifying it as a point ("instant") or extended ("interval") occurrence. The
proper OWL-Time representation of "this happening occurs at this time" is a time:hasTime
link to a time:Instant (point) or time:ProperInterval (extended) temporal entity
(Cox & Little 2017). The commit serializer emits only literal and IRI property values and
drops nested-dict blank nodes, so the time entity cannot be a nested anonymous node; this
applier mints it as a first-class individual with its own IRI and links the happening to it.

  Action/Event  time:hasTime  case:time_<happening>   (a time:Instant | time:ProperInterval)

This is deterministic (no LLM, no DB): it reads proeth:temporalExtent off the committed
graph, mints one time entity per happening, and labels it with the happening's textual
temporal marker. The relational ordering remains carried by the Allen-relation individuals
(time:interval*) and the discrete order by proeth:temporalSequence. time:hasTime, time:Instant
and time:ProperInterval are outside the nine disjoint D-tuple categories, so the anchor adds
no disjointness risk and is invisible to the domain/range guard. Idempotent: a happening that
already has a time:hasTime is skipped. Best-effort, like the other materialization steps.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from rdflib import Graph, Literal, Namespace, RDF, RDFS

from app.services.extraction.state_edges import _safe_frag

logger = logging.getLogger(__name__)

PROETH = Namespace("http://proethica.org/ontology/intermediate#")
TIME = Namespace("http://www.w3.org/2006/time#")

_EXTENT_TYPE = {"interval": TIME.ProperInterval, "instant": TIME.Instant}


def apply_time_anchors(case_id: int, ttl_path, write_back: bool = True) -> Dict[str, Any]:
    """Mint a time:Instant / time:ProperInterval individual for each happening carrying a
    proeth:temporalExtent and link it via time:hasTime. Returns the count added."""
    ttl_path = Path(ttl_path)
    g = Graph()
    g.parse(str(ttl_path), format="turtle")
    case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")

    added = 0
    for subj, ext in list(g.subject_objects(PROETH.temporalExtent)):
        if (subj, TIME.hasTime, None) in g:
            continue  # idempotent
        extent = str(ext).strip().lower()
        ttype = _EXTENT_TYPE.get(extent)
        if ttype is None:
            continue
        tent = case_ns["time_" + _safe_frag(subj)]
        g.add((tent, RDF.type, ttype))
        marker = g.value(subj, PROETH.temporalMarker)
        if marker:
            g.add((tent, RDFS.label, Literal(str(marker))))
        g.add((subj, TIME.hasTime, tent))
        added += 1

    if write_back and added:
        g.serialize(destination=str(ttl_path), format="turtle")
    return {"case_id": case_id, "status": "ok", "time_anchors": added}
