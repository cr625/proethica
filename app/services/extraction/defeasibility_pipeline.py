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
    _persist_extraction_record(case_id, extractor, model_used, len(edges))
    if not edges:
        return {
            "case_id": case_id,
            "status": "no_edges",
            "obligations": len(entities.obligations),
            "states": len(entities.states),
            "narratives": len(entities.narratives),
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
        "narratives": len(entities.narratives),
        "edges_emitted": len(edges),
        "triples_added": added,
        "pre_counts": pre,
        "post_counts": post,
    }


def _persist_extraction_record(
    case_id: int, extractor: DefeasibilityEdgeExtractor,
    model: str, edges_emitted: int,
) -> None:
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
        ExtractionPrompt.save_prompt(
            case_id=case_id,
            concept_type="defeasibility_edges",
            prompt_text=extractor.last_prompt or "",
            step_number=0,
            section_type="synthesis",
            llm_model=model,
            raw_response=extractor.last_raw_response,
            results_summary={"edges_emitted": edges_emitted},
        )
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
