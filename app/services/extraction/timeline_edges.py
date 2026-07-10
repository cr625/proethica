"""Timeline membership materialization (deterministic).

The Step-3 converter mints one timeline individual per case (committed as
case<id>#Case_<id>_Timeline, rdf:type time:TemporalEntity) whose nested
member structure the commit serializer drops, leaving an edge-less island
carrying only three count literals. This applier links the timeline to its
members with dcterms:hasPart (unordered membership; the ordering stays with
proeth:temporalSequence, the Allen-relation individuals, and the time:hasTime
anchors):

  Case_<id>_Timeline  dcterms:hasPart  <every committed Action/Event individual>

It also refreshes the timeline's proeth:actionCount / eventCount /
totalElements literals from the committed member counts (honest counts: the
extraction-time literals go stale when members are removed, e.g. by the
precedent-Action sweep).

Deterministic (no LLM, no DB): the timeline is resolved by rdf:type
time:TemporalEntity, never by IRI guess (the converter's fragment differs from
the committed safe-label fragment); members are the CMT-1 core Action/Event
individuals, which excludes TemporalRelation, CausalChain, prov Derivation,
and time-anchor nodes. dcterms:hasPart is outside the nine disjoint D-tuple
categories and not in ALL_EDGE_RANGE, so the family is guard-neutral.
Idempotent and best-effort, like the other deterministic appliers.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from rdflib import Graph, Literal, Namespace, RDF, URIRef

from app.services.extraction.edge_resolution import (
    _individuals_in_category,
    emit_edge_prov,
)

logger = logging.getLogger(__name__)

CORE = Namespace("http://proethica.org/ontology/core#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
TIME = Namespace("http://www.w3.org/2006/time#")
DCTERMS = Namespace("http://purl.org/dc/terms/")

PROV_PREFIX = "timeline_edge_provenance_"

_COUNT_PROPS = ("actionCount", "eventCount", "totalElements")


def _frag(iri) -> str:
    return str(iri).rsplit("#", 1)[-1]


def _timeline_and_members(g: Graph) -> Tuple[URIRef, Set[URIRef]]:
    """Resolve THE timeline individual (by rdf:type time:TemporalEntity) and
    its member set (the committed core Action/Event individuals).

    Returns (None, members) when the graph has no timeline, and raises
    ValueError when more than one candidate is typed time:TemporalEntity
    (never guess between them; the caller converts that to a skip)."""
    candidates = set(g.subjects(RDF.type, TIME.TemporalEntity))
    # The time_anchor individuals are typed time:Instant/ProperInterval, not
    # TemporalEntity directly; exclude them defensively should a reasoner-
    # materialized supertype ever be asserted on disk.
    candidates -= set(g.subjects(RDF.type, TIME.Instant))
    candidates -= set(g.subjects(RDF.type, TIME.ProperInterval))
    if len(candidates) > 1:
        raise ValueError(
            "multiple time:TemporalEntity individuals: "
            + ", ".join(sorted(_frag(c) for c in candidates)))
    timeline = candidates.pop() if candidates else None
    members = set(_individuals_in_category(g, "Action"))
    members |= set(_individuals_in_category(g, "Event"))
    members.discard(timeline)
    return timeline, members


def _refresh_counts(g: Graph, timeline: URIRef, members: Set[URIRef]) -> Dict[str, Any]:
    """Set the three count literals to the committed member counts; returns
    {prop: {"from": old, "to": new}} for the literals actually changed."""
    n_actions = sum(1 for m in members if (m, RDF.type, CORE.Action) in g)
    n_events = len(members) - n_actions
    target = {"actionCount": n_actions, "eventCount": n_events,
              "totalElements": len(members)}
    changed: Dict[str, Any] = {}
    for prop in _COUNT_PROPS:
        old = g.value(timeline, PROETH[prop])
        if old is not None and old.toPython() == target[prop]:
            continue
        g.remove((timeline, PROETH[prop], None))
        g.add((timeline, PROETH[prop], Literal(target[prop])))
        changed[prop] = {"from": old.toPython() if old is not None else None,
                         "to": target[prop]}
    return changed


def apply_timeline_haspart(case_id: int, ttl_path, write_back: bool = True) -> Dict[str, Any]:
    """Emit Timeline dcterms:hasPart edges to every committed Action/Event
    individual and refresh the timeline's count literals (idempotent).

    Best-effort: resolution failures return a skipped result, never raise."""
    ttl_path = Path(ttl_path)
    g = Graph()
    g.parse(str(ttl_path), format="turtle")

    try:
        timeline, members = _timeline_and_members(g)
    except ValueError as e:
        logger.warning("timeline_edges case %s: %s", case_id, e)
        return {"case_id": case_id, "status": "skipped", "reason": str(e),
                "added": 0, "present": 0}
    if timeline is None:
        return {"case_id": case_id, "status": "skipped",
                "reason": "no time:TemporalEntity timeline individual",
                "added": 0, "present": 0}

    added = present = 0
    for member in sorted(members):
        if (timeline, DCTERMS.hasPart, member) in g:
            present += 1
            continue
        g.add((timeline, DCTERMS.hasPart, member))
        cat = "Action" if (member, RDF.type, CORE.Action) in g else "Event"
        emit_edge_prov(
            g, case_id, PROV_PREFIX, "hasPart", timeline, member,
            f"committed proeth-core:{cat} individual",
            "Timeline membership edge (hasPart)",
            "property=dcterms:hasPart; deterministic membership: every "
            "committed proeth-core:Action/Event individual is a part of the "
            "case timeline (no embedding or LLM); ordering carried separately "
            "by proeth:temporalSequence / Allen relations / time:hasTime")
        added += 1

    counts_refreshed = _refresh_counts(g, timeline, members)

    if write_back and (added or counts_refreshed):
        g.serialize(destination=str(ttl_path), format="turtle")
    return {"case_id": case_id, "status": "ok", "added": added,
            "present": present, "counts_refreshed": counts_refreshed}


def reconstruct_timeline_haspart(case_id: int, ttl_path) -> Dict[str, Any]:
    """Drop the WHOLE timeline-membership family (every dcterms:hasPart edge
    plus every provenance node of the family's IRI prefix) and re-apply from
    the current committed members.

    The correct refresh after a layer rebuild removes Action/Event
    individuals: apply() alone never drops the edge to a removed member, and
    the family's prov nodes are separate subjects that survive as orphans
    (the 2026-07-10 pilot's in-place-prune lesson; mirrors
    analysis_edges.reconstruct_analysis_record_edges)."""
    ttl_path = Path(ttl_path)
    g = Graph()
    g.parse(str(ttl_path), format="turtle")
    removed_edges = removed_prov = 0
    for s, o in list(g.subject_objects(DCTERMS.hasPart)):
        g.remove((s, DCTERMS.hasPart, o))
        removed_edges += 1
    for s in {s for s in g.subjects() if "#" + PROV_PREFIX in str(s)}:
        for t in list(g.triples((s, None, None))):
            g.remove(t)
        removed_prov += 1
    g.serialize(destination=str(ttl_path), format="turtle")
    result = apply_timeline_haspart(case_id, ttl_path)
    result["reconstructed"] = {"edges_dropped": removed_edges,
                               "prov_dropped": removed_prov}
    return result


def check_timeline_haspart(case_id: int, ttl_path) -> Dict[str, Any]:
    """Acceptance gate: the timeline's dcterms:hasPart out-degree must equal
    the committed Action/Event individual set (compared against the committed
    individuals, never the count literals). Reports missing AND extra edges;
    a stray hasPart from any other subject is reported as extra."""
    g = Graph()
    g.parse(str(ttl_path), format="turtle")
    try:
        timeline, members = _timeline_and_members(g)
    except ValueError as e:
        return {"case_id": case_id, "expected": 0, "missing": [],
                "extra": [f"unresolvable timeline: {e}"]}
    if timeline is None:
        missing = [f"hasPart: (no timeline) -> {_frag(m)}" for m in sorted(members)]
        return {"case_id": case_id, "expected": len(members),
                "missing": missing, "extra": []}
    expected = {(timeline, m) for m in members}
    missing: List[str] = [f"hasPart: {_frag(timeline)} -> {_frag(m)}"
                          for m in sorted(members)
                          if (timeline, DCTERMS.hasPart, m) not in g]
    extra: List[str] = [f"hasPart: {_frag(s)} -> {_frag(o)}"
                        for s, o in sorted(g.subject_objects(DCTERMS.hasPart))
                        if (s, o) not in expected]
    return {"case_id": case_id, "expected": len(members),
            "missing": missing, "extra": extra}
