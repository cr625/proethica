"""
TTL-level driver for defeasibility edge extraction.

This module sits between `DefeasibilityEdgeExtractor` (the LLM call) and
the rdflib serialization that produces case ontology TTL files. It is
shared by the corpus backfill driver and the live commit pipeline
(`auto_commit_service._generate_case_ttl`), which can opt-in to running
defeasibility extraction immediately after a case TTL is written.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import PROV, RDF, RDFS, XSD

from .defeasibility_edges import DefeasibilityEdgeExtractor
from .enhanced_prompts_defeasibility import (
    NarrativeContext,
    ObligationContext,
    StateContext,
)
from .schemas import DefeasibilityEdge

logger = logging.getLogger(__name__)


PROETH = Namespace("http://proethica.org/ontology/intermediate#")
PROETH_CORE = Namespace("http://proethica.org/ontology/core#")

# The extraction_prompts row that produced a defeasibility layer is the
# prov:Activity its derivation nodes point at (prov:wasGeneratedBy), so a graph
# can be checked against the active record (case-8 review, L2).
PROV_RECORD_BASE = "http://proethica.org/provenance/extraction_prompts/"
DEFEASIBILITY_PROV_PREFIX = "defeasibility_edge_provenance_"
_TRIO_PREDICATES = (PROETH_CORE.competesWith, PROETH_CORE.prevailsOver,
                    PROETH_CORE.defeasibleUnder)

# Datatype fields harvested for defeasibility narrative on any individual
# (typically Principles, Constraints, sometimes Obligations themselves).
# The canonical names are all-lowercase and must stay stable. This is the
# narrative HARVEST set, a proper subset of the DefeasibilityEdge source_field
# Literal (schemas.py), which also admits obligationstatement and casecontext,
# sourced from the obligation context blocks (_format_obligations), not from
# this harvest.
NARRATIVE_FIELDS = (
    "tensionresolution",
    "balancingwith",
    "interpretation",
    "concreteexpression",
    "constraintstatement",
)

# Committed case TTLs carry these fields under two predicate spellings: the
# all-lowercase forms above (older emitters) and the camelCase forms the
# current commit path writes (proeth:concreteExpression,
# proeth:constraintStatement, ...). Harvesting only the lowercase spelling
# silently dropped most of the available narrative (case-7 run 21: 14 of 22
# fragments lost; run 19: 16 of 27), starving the prompt's verbatim-grounding
# constraint. Every spelling is queried; NarrativeContext.source_field keeps
# the canonical lowercase name.
NARRATIVE_PREDICATE_SPELLINGS: Dict[str, Tuple[str, ...]] = {
    "tensionresolution": ("tensionresolution", "tensionResolution"),
    "balancingwith": ("balancingwith", "balancingWith"),
    "interpretation": ("interpretation",),
    "concreteexpression": ("concreteexpression", "concreteExpression"),
    "constraintstatement": ("constraintstatement", "constraintStatement"),
}


@dataclass
class CaseEntities:
    case_id: int
    obligations: List[ObligationContext]
    states: List[StateContext]
    narratives: List[NarrativeContext]


# ---------------------------------------------------------------------------
# rdflib helpers
# ---------------------------------------------------------------------------

def _lit(g: Graph, subj: URIRef, predicate: str) -> Optional[str]:
    pred_uri = PROETH[predicate]
    for o in g.objects(subj, pred_uri):
        if isinstance(o, Literal):
            return str(o)
    return None


def _label(g: Graph, subj: URIRef) -> str:
    for o in g.objects(subj, RDFS.label):
        if isinstance(o, Literal):
            return str(o)
    return str(subj).rsplit("#", 1)[-1]


def _individuals_in_category(g: Graph, category: str) -> List[URIRef]:
    # Read the materialized direct rdf:type proeth-core:<Category> (CMT-1), one
    # hop, rather than the retired proeth:conceptCategory literal.
    return [s for s in g.subjects(RDF.type, PROETH_CORE[category])
            if isinstance(s, URIRef)]


# ---------------------------------------------------------------------------
# Parse + emit
# ---------------------------------------------------------------------------

def _obligated_party_from_edges(g: Graph, s) -> str:
    """obligatedParty context from the materialized proeth-core:obligatedParty
    object edges, label-resolved. The commit never writes the proeth:obligatedParty
    literal shadow (CMT-3), so the former literal read silently yielded nothing on
    committed graphs (the dead-read class fixed for the R->P->O pass 2026-07-06)."""
    labels = []
    for tgt in g.objects(s, PROETH_CORE.obligatedParty):
        lbl = g.value(tgt, RDFS.label)
        labels.append(str(lbl) if lbl else str(tgt).split("#")[-1])
    return "; ".join(sorted(labels))


def _state_class_from_types(g: Graph, s) -> str:
    """State-kind context from the non-core proeth:* rdf:type locals (CMT-3: the
    class IS the rdf:type; the proeth:stateClass literal shadow is never written)."""
    locals_ = sorted(str(t).split("#")[-1] for t in g.objects(s, RDF.type)
                     if str(t).startswith(str(PROETH)))
    return "; ".join(locals_)


def parse_case_graph(g: Graph, case_id: int) -> CaseEntities:
    """Extract obligation, state, and narrative entries from a parsed graph."""
    obligations = [
        ObligationContext(
            iri=str(s),
            label=_label(g, s),
            statement=_lit(g, s, "obligationStatement"),
            case_context=_lit(g, s, "caseContext"),
            obligated_party=_obligated_party_from_edges(g, s),
            temporal_scope=_lit(g, s, "temporalScope"),
            compliance_status=_lit(g, s, "complianceStatus"),
        )
        for s in _individuals_in_category(g, "Obligation")
    ]
    states = [
        StateContext(
            iri=str(s),
            label=_label(g, s),
            state_class=_state_class_from_types(g, s),
            triggering_event=_lit(g, s, "triggeringEvent"),
            subject=_lit(g, s, "subject"),
        )
        for s in _individuals_in_category(g, "State")
    ]

    narratives: List[NarrativeContext] = []
    seen: Set[Tuple[str, str, str]] = set()
    for field in NARRATIVE_FIELDS:
        for spelling in NARRATIVE_PREDICATE_SPELLINGS[field]:
            pred = PROETH[spelling]
            for s, _, o in g.triples((None, pred, None)):
                if not isinstance(o, Literal):
                    continue
                text = str(o).strip()
                if not text:
                    continue
                key = (str(s), field, text)
                if key in seen:
                    # Same value asserted under both spellings on one subject.
                    continue
                seen.add(key)
                narratives.append(
                    NarrativeContext(
                        source_iri=str(s),
                        source_label=_label(g, s) if isinstance(s, URIRef) else str(s),
                        source_field=field,
                        text=text,
                    )
                )
    return CaseEntities(
        case_id=case_id,
        obligations=obligations,
        states=states,
        narratives=narratives,
    )


def parse_case_ttl(ttl_path: Path, case_id: int) -> CaseEntities:
    g = Graph()
    g.parse(ttl_path, format="turtle")
    return parse_case_graph(g, case_id)


def extraction_record_iri(record_id) -> Optional[URIRef]:
    """IRI of an extraction_prompts row, the activity a derivation node points
    at through prov:wasGeneratedBy. None when the record id is unknown (a
    replay without an app context)."""
    if record_id is None:
        return None
    return URIRef(f"{PROV_RECORD_BASE}{int(record_id)}")


def derivation_iri(case_id: int, ed: DefeasibilityEdge) -> URIRef:
    """Content-addressed derivation-node IRI of one edge (endpoints plus
    predicate); the same edge re-derived by a later run maps to the same node."""
    return URIRef(
        f"http://proethica.org/ontology/case/{case_id}#"
        f"{DEFEASIBILITY_PROV_PREFIX}"
        f"{_safe_frag(ed.subject_iri)}_{ed.predicate}_"
        f"{_safe_frag(ed.object_iri)}"
    )


def _layer_prefix(case_id: int) -> str:
    return f"http://proethica.org/ontology/case/{case_id}#{DEFEASIBILITY_PROV_PREFIX}"


def _write_derivation_node(g: Graph, prov_iri: URIRef, ed: DefeasibilityEdge,
                           subj: URIRef, obj: URIRef, generated_at: str,
                           record_iri: Optional[URIRef]) -> None:
    """Write the derivation node from the CURRENT edge, replacing every triple
    the node carried. A re-derivation therefore never leaves an earlier run's
    source field, confidence, quote, endpoints or timestamp on the node (case
    8 carried the 2026-07-08 content under a 2026-07-10 active record)."""
    g.remove((prov_iri, None, None))
    g.add((prov_iri, RDF.type, PROV.Derivation))
    g.add((prov_iri, PROV.wasDerivedFrom, subj))
    g.add((prov_iri, PROV.wasDerivedFrom, obj))
    if ed.source_individual_iri:
        g.add((prov_iri, PROV.wasDerivedFrom, URIRef(ed.source_individual_iri)))
    g.add((prov_iri, RDFS.label, Literal(
        f"Defeasibility edge from {ed.source_field}"
    )))
    g.add((prov_iri, PROV.value, Literal(ed.source_text)))
    g.add((prov_iri, RDFS.comment, Literal(
        f"source_field={ed.source_field}; confidence={ed.confidence}"
    )))
    g.add((prov_iri, PROV.generatedAtTime, Literal(generated_at, datatype=XSD.dateTime)))
    if record_iri is not None:
        g.add((prov_iri, PROV.wasGeneratedBy, record_iri))
    # resolutionKind marks the resolution itself; competesWith records the
    # competition and defeasibleUnder the licensing context, neither of
    # which asserts a resolution mode.
    if ed.predicate == "prevailsOver":
        g.add((prov_iri, PROETH.resolutionKind, Literal("override")))


def add_edges_to_graph(
    g: Graph, edges: List[DefeasibilityEdge], case_id: int,
    record_iri: Optional[URIRef] = None, stats: Optional[Dict[str, int]] = None,
) -> int:
    """Add object-property triples + PROV-O provenance to the graph.

    An edge whose triple already exists is not re-added, but its derivation
    node IS rewritten from the current edge (label, comment, prov:value,
    prov:wasDerivedFrom, prov:generatedAtTime, prov:wasGeneratedBy), so the
    provenance always describes the run that last asserted the edge.
    ``record_iri`` (the extraction_prompts row of this run) is recorded as
    prov:wasGeneratedBy on every node when known.

    Returns the number of object-property triples newly added (excludes
    provenance triples). ``stats``, when given, receives triples_added,
    derivations_created and derivations_refreshed, so callers report what was
    written separately from what the model emitted.
    """
    added = created = refreshed = 0
    now = datetime.now(timezone.utc).isoformat()
    for ed in edges:
        subj = URIRef(ed.subject_iri)
        obj = URIRef(ed.object_iri)
        pred = PROETH_CORE[ed.predicate]

        if (subj, pred, obj) not in g:
            g.add((subj, pred, obj))
            added += 1

        prov_iri = derivation_iri(case_id, ed)
        existed = (prov_iri, None, None) in g
        _write_derivation_node(g, prov_iri, ed, subj, obj, now, record_iri)
        if existed:
            refreshed += 1
        else:
            created += 1
    if stats is not None:
        stats.update({"triples_added": added, "derivations_created": created,
                      "derivations_refreshed": refreshed})
    return added


def remove_defeasibility_layer(g: Graph, case_id: int) -> Dict[str, int]:
    """Remove the case's defeasibility layer in place: every competesWith /
    prevailsOver / defeasibleUnder triple and every derivation node this module
    minted (the ``defeasibility_edge_provenance_`` IRIs). Re-applying the
    current run's edges afterwards leaves a graph that reflects exactly that
    run."""
    triples = 0
    for pred in _TRIO_PREDICATES:
        for s, o in list(g.subject_objects(pred)):
            g.remove((s, pred, o))
            triples += 1
    prefix = _layer_prefix(case_id)
    nodes = {s for s in g.subjects(None, None)
             if isinstance(s, URIRef) and str(s).startswith(prefix)}
    for node in nodes:
        g.remove((node, None, None))
    return {"triples_removed": triples, "derivations_removed": len(nodes)}


def layer_derivations(g: Graph, case_id: int) -> List[URIRef]:
    """The case's defeasibility derivation nodes, sorted."""
    prefix = _layer_prefix(case_id)
    return sorted({s for s in g.subjects(RDF.type, PROV.Derivation)
                   if isinstance(s, URIRef) and str(s).startswith(prefix)})


def stale_derivations(g: Graph, case_id: int, record_iri: Optional[URIRef]) -> List[URIRef]:
    """Derivation nodes of the case's defeasibility layer that do not point at
    ``record_iri`` through prov:wasGeneratedBy: content an earlier run wrote
    that the current record does not describe. Empty when ``record_iri`` is
    None (nothing to check against)."""
    if record_iri is None:
        return []
    return [node for node in layer_derivations(g, case_id)
            if record_iri not in set(g.objects(node, PROV.wasGeneratedBy))]


def active_extraction_record_id(case_id: int) -> Optional[int]:
    """Id of the active extraction_prompts row for the case's defeasibility
    pass, or None outside an app context / without a row."""
    try:
        from flask import has_app_context
        if not has_app_context():
            return None
        from app.models.extraction_prompt import ExtractionPrompt
        row = ExtractionPrompt.get_active_prompt(case_id, "defeasibility_edges", "synthesis")
        return int(row.id) if row is not None else None
    except Exception as e:  # noqa: BLE001 - best-effort lookup
        logger.debug("Case %s: active defeasibility record lookup failed: %s", case_id, e)
        return None


def verify_graph_reflects_active_record(g: Graph, case_id: int,
                                        active_record_id: Optional[int] = None) -> Dict[str, Any]:
    """Check that every derivation node of the case's defeasibility layer was
    generated by the active extraction_prompts row. ``active_record_id`` may be
    supplied (tests, scripts); otherwise the row is looked up."""
    rid = active_record_id if active_record_id is not None else active_extraction_record_id(case_id)
    if rid is None:
        return {"checked": False, "reason": "no active extraction record available"}
    stale = stale_derivations(g, case_id, extraction_record_iri(rid))
    return {"checked": True, "active_record_id": rid,
            "reflects_active_record": not stale,
            "stale_derivations": [str(s) for s in stale]}


def _safe_frag(iri: str) -> str:
    frag = iri.rsplit("#", 1)[-1]
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in frag)[:60]


def count_edges(g: Graph) -> Dict[str, int]:
    return {
        "competesWith": sum(1 for _ in g.triples(
            (None, PROETH_CORE.competesWith, None))),
        "prevailsOver": sum(1 for _ in g.triples(
            (None, PROETH_CORE.prevailsOver, None))),
        "defeasibleUnder": sum(1 for _ in g.triples(
            (None, PROETH_CORE.defeasibleUnder, None))),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def apply_defeasibility_edges(
    case_id: int,
    ttl_path: Path,
    extractor: Optional[DefeasibilityEdgeExtractor] = None,
    write_back: bool = True,
    replace_prior: bool = True,
) -> Dict[str, Any]:
    """Run defeasibility extraction over one case TTL.

    Parses the TTL, identifies obligation/state individuals + narrative
    context, calls the LLM, adds object-property triples + PROV-O
    provenance, optionally re-serializes the file.

    A re-derivation replaces the prior layer (``replace_prior``, the default):
    the earlier run's trio triples and derivation nodes are removed before the
    current edges are applied, so the graph reflects exactly the run recorded
    in extraction_prompts. With ``replace_prior=False`` existing nodes are
    refreshed in place and any derivation an earlier run left that this run
    did not re-derive makes the applier refuse to write back (status
    ``stale_derivations``): a newer active record the graph does not reflect
    is never persisted (case-8 review, L2).

    Args:
        case_id: Numeric case identifier (used for prov IRI minting).
        ttl_path: Path to the case TTL on disk. Read with rdflib.parse;
            written back with rdflib.serialize when write_back is True.
        extractor: Optional pre-built DefeasibilityEdgeExtractor. A new
            one is constructed by default. Inject one to share an LLM
            client across many calls.
        write_back: If True, the modified graph is serialized back to
            ttl_path. Set to False for previewing.
        replace_prior: Remove the case's existing defeasibility layer before
            applying this run's edges (default). False refreshes in place and
            refuses to persist a layer that still carries stale derivations.

    Returns:
        A status dict with one of: ok, dry_run, no_edges, stale_derivations,
        insufficient_obligations, missing_ttl. Successful runs include
        edge counts (edges_emitted is the model output, triples_added what
        reached the graph).
    """
    if not ttl_path.exists():
        return {"case_id": case_id, "status": "missing_ttl"}

    g = Graph()
    g.parse(ttl_path, format="turtle")

    entities = parse_case_graph(g, case_id)
    if len(entities.obligations) < 2:
        return {
            "case_id": case_id,
            "status": "insufficient_obligations",
            "obligations": len(entities.obligations),
        }

    if extractor is None:
        extractor = DefeasibilityEdgeExtractor()

    edges = extractor.extract(
        case_id=case_id,
        obligations=entities.obligations,
        states=entities.states,
        additional_narratives=entities.narratives,
    )
    model_used = extractor._resolve_model()
    if not edges:
        # Run-21 F2a was undiagnosable post hoc: a clean-parse-empty response
        # leaves no parser/filter warning and the raw response was never
        # recorded. Log it (truncated) so an anomalous zero is inspectable.
        raw = (extractor.last_raw_response or "").strip()
        logger.warning(
            "Case %s: defeasibility extractor returned ZERO edges "
            "(model=%s, %d obligations, %d states, %d narrative fragments); "
            "raw response (truncated): %r",
            case_id, model_used, len(entities.obligations),
            len(entities.states), len(entities.narratives), raw[:500],
        )
    record_id = _persist_extraction_record(case_id, extractor, model_used, len(edges))
    record_iri = extraction_record_iri(record_id)
    if not edges:
        res = {
            "case_id": case_id,
            "status": "no_edges",
            "obligations": len(entities.obligations),
            "states": len(entities.states),
            "narratives": len(entities.narratives),
            "extraction_record_id": record_id,
        }
        prior = layer_derivations(g, case_id)
        if prior:
            # The graph is left untouched (a zero yield may be a model failure,
            # see the warning above), but the state is reported: the layer on
            # disk describes an earlier run, not the record this run wrote.
            res["prior_layer_derivations"] = len(prior)
            res["reflects_active_record"] = False
            logger.warning(
                "Case %s: zero edges this run; the graph keeps %d defeasibility "
                "derivation node(s) from an earlier run that extraction record %s "
                "does not describe", case_id, len(prior), record_id,
            )
        return res

    pre = count_edges(g)
    removed = remove_defeasibility_layer(g, case_id) if replace_prior else None
    stats: Dict[str, int] = {}
    added = add_edges_to_graph(g, edges, case_id, record_iri=record_iri, stats=stats)
    stale = stale_derivations(g, case_id, record_iri)
    if stale:
        logger.error(
            "Case %s: %d defeasibility derivation node(s) were not generated by "
            "extraction record %s and this run did not re-derive them; refusing "
            "to write a layer the active record does not describe: %s",
            case_id, len(stale), record_id, [str(s).rsplit('#', 1)[-1] for s in stale],
        )
        return {
            "case_id": case_id,
            "status": "stale_derivations",
            "obligations": len(entities.obligations),
            "states": len(entities.states),
            "narratives": len(entities.narratives),
            "edges_emitted": len(edges),
            "triples_added": added,
            "extraction_record_id": record_id,
            "stale_derivations": [str(s) for s in stale],
        }
    post = count_edges(g)

    if write_back:
        g.bind("proeth", PROETH)
        g.bind("proeth-core", PROETH_CORE)
        g.bind("prov", PROV)
        g.serialize(destination=str(ttl_path), format="turtle")

    res = {
        "case_id": case_id,
        "status": "ok",
        "obligations": len(entities.obligations),
        "states": len(entities.states),
        "narratives": len(entities.narratives),
        "edges_emitted": len(edges),
        "triples_added": added,
        "derivations_created": stats.get("derivations_created", 0),
        "derivations_refreshed": stats.get("derivations_refreshed", 0),
        "extraction_record_id": record_id,
        "reflects_active_record": True,
        "pre_counts": pre,
        "post_counts": post,
    }
    if removed is not None:
        res["prior_layer_removed"] = removed
    return res


def _persist_extraction_record(
    case_id: int, extractor: DefeasibilityEdgeExtractor,
    model: str, edges_emitted: int,
) -> Optional[int]:
    """Store the defeasibility prompt + raw LLM response in extraction_prompts
    (concept_type='defeasibility_edges'), mirroring the per-pass records the
    concept extractors write via store_extraction_result. Best-effort like the
    rest of the applier family: a persistence failure (e.g. no app/DB context
    in a standalone replay script) is logged and never fails the applier.

    section_type must satisfy the extraction_prompts valid_section_type CHECK
    constraint (facts/discussion/questions/conclusions/dissenting_opinion/
    references/synthesis/temporal). 'synthesis' is what the other commit-time
    mechanical passes use; concept_type='defeasibility_edges' disambiguates.
    The initial 'edges' value violated the constraint, and the session left
    un-rolled-back poisoned every later applier in the same materialization
    (case-7 blocker-fix recommit, 2026-07-02) -- hence the rollback below."""
    try:
        from app.models.extraction_prompt import ExtractionPrompt
        record = ExtractionPrompt.save_prompt(
            case_id=case_id,
            concept_type="defeasibility_edges",
            prompt_text=extractor.last_prompt or "",
            step_number=0,
            section_type="synthesis",
            llm_model=model,
            raw_response=extractor.last_raw_response,
            results_summary={"edges_emitted": edges_emitted},
        )
        record_id = getattr(record, "id", None)
        return int(record_id) if record_id is not None else None
    except Exception as e:
        logger.warning(
            "Case %s: could not persist defeasibility prompt/response to "
            "extraction_prompts: %s", case_id, e,
        )
        # A failed flush leaves the shared scoped session in a pending-rollback
        # state; without an explicit rollback every subsequent DB read in this
        # materialization (state_edges temp_rdf reads, RPO template load,
        # cites_provision, band index) raises PendingRollbackError.
        try:
            from app.models import db
            db.session.rollback()
        except Exception:
            pass
        return None
