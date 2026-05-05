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
from typing import Any, Dict, List, Optional

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

# Datatype fields that may carry defeasibility narrative on any individual
# (typically Principles, Constraints, sometimes Obligations themselves).
NARRATIVE_FIELDS = (
    "tensionresolution",
    "balancingwith",
    "interpretation",
    "concreteexpression",
    "constraintstatement",
)


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
    cat_lit = Literal(category)
    found: List[URIRef] = []
    for s, _, _ in g.triples((None, PROETH.conceptCategory, cat_lit)):
        if isinstance(s, URIRef):
            found.append(s)
    return found


# ---------------------------------------------------------------------------
# Parse + emit
# ---------------------------------------------------------------------------

def parse_case_graph(g: Graph, case_id: int) -> CaseEntities:
    """Extract obligation, state, and narrative entries from a parsed graph."""
    obligations = [
        ObligationContext(
            iri=str(s),
            label=_label(g, s),
            statement=_lit(g, s, "obligationstatement"),
            case_context=_lit(g, s, "casecontext"),
            obligated_party=_lit(g, s, "obligatedparty"),
            temporal_scope=_lit(g, s, "temporalscope"),
        )
        for s in _individuals_in_category(g, "Obligation")
    ]
    states = [
        StateContext(
            iri=str(s),
            label=_label(g, s),
            state_class=_lit(g, s, "stateclass"),
            triggering_event=_lit(g, s, "triggeringevent"),
            subject=_lit(g, s, "subject"),
        )
        for s in _individuals_in_category(g, "State")
    ]

    narratives: List[NarrativeContext] = []
    for field in NARRATIVE_FIELDS:
        pred = PROETH[field]
        for s, _, o in g.triples((None, pred, None)):
            if not isinstance(o, Literal):
                continue
            text = str(o).strip()
            if not text:
                continue
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


def add_edges_to_graph(
    g: Graph, edges: List[DefeasibilityEdge], case_id: int,
) -> int:
    """Add object-property triples + PROV-O provenance to the graph.

    Returns the number of object-property triples newly added (excludes
    provenance triples on the derivation node).
    """
    added = 0
    for ed in edges:
        subj = URIRef(ed.subject_iri)
        obj = URIRef(ed.object_iri)
        pred = PROETH_CORE[ed.predicate]

        if (subj, pred, obj) in g:
            continue
        g.add((subj, pred, obj))
        added += 1

        prov_iri = URIRef(
            f"http://proethica.org/ontology/case/{case_id}#"
            f"defeasibility_edge_provenance_"
            f"{_safe_frag(ed.subject_iri)}_{ed.predicate}_"
            f"{_safe_frag(ed.object_iri)}"
        )
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
        g.add((prov_iri, PROV.generatedAtTime, Literal(
            datetime.now(timezone.utc).isoformat(), datatype=XSD.dateTime,
        )))
    return added


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
) -> Dict[str, Any]:
    """Run defeasibility extraction over one case TTL.

    Parses the TTL, identifies obligation/state individuals + narrative
    context, calls the LLM, adds object-property triples + PROV-O
    provenance, optionally re-serializes the file.

    Args:
        case_id: Numeric case identifier (used for prov IRI minting).
        ttl_path: Path to the case TTL on disk. Read with rdflib.parse;
            written back with rdflib.serialize when write_back is True.
        extractor: Optional pre-built DefeasibilityEdgeExtractor. A new
            one is constructed by default. Inject one to share an LLM
            client across many calls.
        write_back: If True, the modified graph is serialized back to
            ttl_path. Set to False for previewing.

    Returns:
        A status dict with one of: ok, dry_run, no_edges,
        insufficient_obligations, missing_ttl. Successful runs include
        edge counts.
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
    if not edges:
        return {
            "case_id": case_id,
            "status": "no_edges",
            "obligations": len(entities.obligations),
            "states": len(entities.states),
        }

    pre = count_edges(g)
    added = add_edges_to_graph(g, edges, case_id)
    post = count_edges(g)

    if write_back:
        g.bind("proeth", PROETH)
        g.bind("proeth-core", PROETH_CORE)
        g.bind("prov", PROV)
        g.serialize(destination=str(ttl_path), format="turtle")

    return {
        "case_id": case_id,
        "status": "ok",
        "obligations": len(entities.obligations),
        "states": len(entities.states),
        "edges_emitted": len(edges),
        "triples_added": added,
        "pre_counts": pre,
        "post_counts": post,
    }
