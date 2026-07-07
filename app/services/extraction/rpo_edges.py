"""
R -> P -> O dependency-chain edge extractor (KI2026 §3 materialization).

Asserts the three Role/Principle/Obligation object properties between
already-extracted typed individuals:

  - proeth-core:hasObligation       Role -> Obligation
  - proeth-core:adheresToPrinciple  Role -> Principle
  - proeth-core:derivedFromPrinciple  Obligation -> Principle  (promoted to core, v2.8.0)

These were declared in the ontology but never materialized in the per-case
TTLs (the link lived only in narrative datatype fields). This module makes the
R->P->O chain SPARQL-traversable per case, with PROV-O provenance attaching
each edge to the verbatim narrative text that justifies it.

Design mirrors defeasibility_edges.py: streaming LLM call, IRI validation
against the supplied entity lists, dedupe. CRITICAL ADDITION: endpoints are
validated by the materialized direct rdf:type proeth-core:<Category> (subject/
object must resolve to the property's rdfs:domain/range category) so edges cannot
force an individual into a disjoint core class -- this preserves the OWL-DL
consistency restored in the KI2026 corpus repair.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from rdflib import Graph, Literal, RDF, RDFS, URIRef, Namespace

from .edge_extractor_base import StreamingEdgeExtractor

logger = logging.getLogger(__name__)

PROETH = Namespace("http://proethica.org/ontology/intermediate#")
PROETH_CORE = Namespace("http://proethica.org/ontology/core#")
PROV = Namespace("http://www.w3.org/ns/prov#")

HAS_OBLIGATION = PROETH_CORE.hasObligation
ADHERES_TO = PROETH_CORE.adheresToPrinciple
DERIVED_FROM = PROETH_CORE.derivedFromPrinciple  # promoted to core (v2.8.0)

# predicate -> (subject category, object category)
_PRED_CATEGORY = {
    "hasObligation": ("Role", "Obligation"),
    "adheresToPrinciple": ("Role", "Principle"),
    "derivedFromPrinciple": ("Obligation", "Principle"),
}
_PRED_URI = {
    "hasObligation": HAS_OBLIGATION,
    "adheresToPrinciple": ADHERES_TO,
    "derivedFromPrinciple": DERIVED_FROM,
}

_RPO_PROMPT_PROPERTIES = ("hasObligation", "adheresToPrinciple", "derivedFromPrinciple")
_OWL_NS = "http://www.w3.org/2002/07/owl#"


def property_axioms_block(core_ttl=None, properties=_RPO_PROMPT_PROPERTIES) -> str:
    """Property axiom blocks (rdf:type incl. characteristics, domain, range,
    label, rdfs:comment), parsed live from proethica-core.ttl at render time so
    prompt text can never drift from the ontology. Hard-coded predecessors
    drifted twice: the R->P->O block kept the pre-v2.10.5 professional-only
    hasObligation wording, and the defeasibility block omitted the prevailsOver
    Asymmetric/Irreflexive characteristics added 2026-05-23 (the constraint
    whose absence produced the case-110 bidirectional artifact). Shared by the
    R->P->O and defeasibility passes (enhanced_prompts_defeasibility delegates
    here). Raises when a block is incomplete (no fallback)."""
    from pathlib import Path
    path = Path(core_ttl) if core_ttl else _default_ontology_paths()[0]
    cg = Graph()
    cg.parse(str(path), format="turtle")
    blocks = []
    for name in properties:
        uri = PROETH_CORE[name]
        dom = cg.value(uri, RDFS.domain)
        rng = cg.value(uri, RDFS.range)
        label = cg.value(uri, RDFS.label)
        comment = cg.value(uri, RDFS.comment)
        if dom is None or rng is None or comment is None:
            raise RuntimeError(
                f"proethica-core.ttl lacks domain/range/comment for {name}")
        extra = sorted(str(t)[len(_OWL_NS):] for t in cg.objects(uri, RDF.type)
                       if str(t).startswith(_OWL_NS) and str(t) != _OWL_NS + "ObjectProperty")
        type_str = ", ".join(["owl:ObjectProperty"] + [f"owl:{t}" for t in extra])
        block = (f"proeth-core:{name} a {type_str} ;\n"
                 f"    rdfs:domain proeth-core:{str(dom).split('#')[-1]} ; "
                 f"rdfs:range proeth-core:{str(rng).split('#')[-1]} ;\n")
        if label is not None:
            block += f'    rdfs:label "{label}"@en ;\n'
        block += f'    rdfs:comment "{comment}"@en .'
        blocks.append(block)
    return "\n\n".join(blocks)

def _load_rpo_template():
    """Load the editable 'rpo_edges' prompt template (prompt editor -> Shared prompts -> Ontology edges
    -> R->P->O edges). A separate function so a test can inject a stub without a DB / app context.
    Raises (no fallback) if unseeded. The property axioms are injected at render time as the
    {{ property_axioms }} system variable, parsed live from proethica-core.ttl
    (property_axioms_block), keeping the ontology as the canonical source."""
    from app.models.extraction_prompt_template import ExtractionPromptTemplate
    tmpl = ExtractionPromptTemplate.get_active_template(0, 'rpo_edges')
    if tmpl is None:
        raise RuntimeError(
            "No 'rpo_edges' prompt template in extraction_prompt_templates. "
            "Seed it: docs-internal/scripts/seed_rpo_edges_template.py")
    return tmpl


@dataclass
class Indiv:
    iri: str
    label: str
    fields: Dict[str, str]


def _individuals_in_category(g: Graph, category: str) -> List[URIRef]:
    # Read the materialized direct rdf:type proeth-core:<Category> (CMT-1), one
    # hop, rather than the retired proeth:conceptCategory literal.
    return list(g.subjects(RDF.type, PROETH_CORE[category]))


def _fields(g: Graph, ind: URIRef, names: List[str]) -> Dict[str, str]:
    d = {}
    for n in names:
        vals = [str(o) for o in g.objects(ind, PROETH[n])]
        if vals:
            d[n] = vals[0]
    return d


def _type_class_context(g: Graph, ind: URIRef) -> Optional[str]:
    """Class context derived from the individual's non-core proeth:* rdf:type.
    The commit never writes the *Class literal shadow (CMT-3: the class IS the
    rdf:type), so a literal read of e.g. proeth:principleClass silently yields
    nothing on committed graphs."""
    locals_ = sorted(str(t).split("#")[-1] for t in g.objects(ind, RDF.type)
                     if str(t).startswith(str(PROETH)))
    return "; ".join(locals_) if locals_ else None


def _invoked_by_context(g: Graph, ind: URIRef) -> Optional[str]:
    """invokedBy context derived from the materialized proeth-core:invokedBy
    object edges, with target labels resolved via rdfs:label in the same graph.
    The commit never writes the proeth:invokedBy literal shadow (CMT-3: a
    RELATION field is materialized as an object-property edge), so a literal
    read silently yields nothing on committed graphs."""
    labels = []
    for tgt in g.objects(ind, PROETH_CORE.invokedBy):
        lbl = g.value(tgt, RDFS.label)
        labels.append(str(lbl) if lbl else str(tgt).split("#")[-1])
    return "; ".join(sorted(labels)) if labels else None


def _actor_edge_context(g: Graph, ind: URIRef) -> Optional[str]:
    """Role relationship context derived from the materialized typed actor
    edges. The commit never writes the proeth:relationships literal (the
    relationships field resolves to the actor-edge family at commit), so a
    literal read silently yields nothing on committed graphs."""
    parts = []
    for pred in ("hasClient", "professionalPeerOf", "employedBy",
                 "reviewsWorkOf", "workReviewedBy"):
        for tgt in g.objects(ind, PROETH_CORE[pred]):
            lbl = g.value(tgt, RDFS.label)
            parts.append(f"{pred} {str(lbl) if lbl else str(tgt).split('#')[-1]}")
    return "; ".join(sorted(parts)) if parts else None


def _obligated_party_context(g: Graph, ind: URIRef) -> Optional[str]:
    """obligatedParty context derived from the materialized proeth-core:obligatedParty
    object edges (the participant family), label-resolved. The commit never
    writes the proeth:obligatedParty literal shadow (CMT-3)."""
    labels = []
    for tgt in g.objects(ind, PROETH_CORE.obligatedParty):
        lbl = g.value(tgt, RDFS.label)
        labels.append(str(lbl) if lbl else str(tgt).split("#")[-1])
    return "; ".join(sorted(labels)) if labels else None


def _derived_from_principle_hints(case_id: int) -> Dict[str, str]:
    """Obligation label -> the obligations prompt's own derived_from_principle
    answer, read from the temp_rdf rows. The commit deliberately skips the
    field (RELATION classification), so without this read the already-paid LLM
    signal is discarded; here it grounds the derivedFromPrinciple derivation
    the same way state principleTransformation does. Empty when temp storage
    has been cleared or the run is TTL-only with no app context (backfill-style
    invocations outside the app; the committed graph is then the sole input)."""
    from flask import has_app_context
    if not has_app_context():
        logger.debug("R->P->O: no app context; skipping derived_from_principle temp hints")
        return {}
    from app.models.temporary_rdf_storage import TemporaryRDFStorage
    hints: Dict[str, str] = {}
    rows = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type="obligations", storage_type="individual").all()
    for r in rows:
        props = ((r.rdf_json_ld or {}).get("properties") or {})
        v = props.get("derivedFromPrinciple") or props.get("derived_from_principle")
        label = (r.entity_label or "").strip()
        if v and label:
            hints[label] = str(v[0]) if isinstance(v, list) else str(v)
    return hints


def gather(g: Graph, case_id: Optional[int] = None) -> Tuple[List[Indiv], List[Indiv], List[Indiv]]:
    def mk(ind, names, derived=None):
        lbl = g.value(ind, RDFS.label)
        fields = dict(derived) if derived else {}
        fields.update(_fields(g, ind, names))
        return Indiv(str(ind), str(lbl) if lbl else str(ind).split("#")[-1], fields)

    def principle_context(ind):
        # principleClass / invokedBy come from the canonical triples (rdf:type
        # and the invokedBy object edges); only appliedTo / concreteExpression
        # remain literal reads.
        ctx = {}
        cls = _type_class_context(g, ind)
        if cls:
            ctx["principleClass"] = cls
        inv = _invoked_by_context(g, ind)
        if inv:
            ctx["invokedBy"] = inv
        return ctx

    def role_context(ind):
        # roleClass / relationships come from the canonical triples (rdf:type
        # and the typed actor edges); caseInvolvement is the literal the commit
        # actually writes (the former caseContext read named a field stored
        # only on other categories).
        ctx = {}
        cls = _type_class_context(g, ind)
        if cls:
            ctx["roleClass"] = cls
        rel = _actor_edge_context(g, ind)
        if rel:
            ctx["relationships"] = rel
        return ctx

    def obligation_context(ind):
        # obligationClass / obligatedParty come from the canonical triples
        # (rdf:type and the participant edges); the temp_rdf hint carries the
        # obligation extractor's own principle linkage as derivation grounding.
        ctx = {}
        cls = _type_class_context(g, ind)
        if cls:
            ctx["obligationClass"] = cls
        party = _obligated_party_context(g, ind)
        if party:
            ctx["obligatedParty"] = party
        lbl = g.value(ind, RDFS.label)
        hint = hints.get(str(lbl).strip()) if lbl else None
        if hint:
            ctx["statedDerivedFromPrinciple"] = hint
        return ctx

    hints = _derived_from_principle_hints(case_id) if case_id is not None else {}
    roles = [mk(r, ["caseInvolvement"], role_context(r)) for r in _individuals_in_category(g, "Role")]
    principles = [mk(p, ["appliedTo", "concreteExpression"], principle_context(p))
                  for p in _individuals_in_category(g, "Principle")]
    obligations = [mk(o, ["obligationStatement"], obligation_context(o))
                   for o in _individuals_in_category(g, "Obligation")]
    return roles, principles, obligations


def _fmt(items: List[Indiv]) -> str:
    if not items:
        return "(none)"
    out = []
    for it in items:
        block = [f"- IRI: <{it.iri}>", f"  label: {it.label}"]
        for k, v in it.fields.items():
            block.append(f"  {k}: {v[:240]}")
        out.append("\n".join(block))
    return "\n\n".join(out)


def _fmt_transformations(transformations) -> str:
    if not transformations:
        return ""
    lines = [f"- {lbl}: {txt[:300]}" for lbl, txt in transformations if txt]
    if not lines:
        return ""
    return (
        "\nSTATE TRANSFORMATIONS (the state extraction's S->P->O account of how a "
        "state turns an abstract principle into a concrete obligation; use as "
        "grounding for derivedFromPrinciple, do NOT invent IRIs from it):\n"
        + "\n".join(lines) + "\n"
    )


def build_prompt(roles, principles, obligations, case_id, state_transformations=None) -> str:
    """Render the R->P->O user prompt from the editable DB template. The per-individual blocks are
    assembled here (via _fmt / _fmt_transformations) and passed as template variables; only the static
    framing lives in the editable template."""
    return _load_rpo_template().render(
        case_id=case_id,
        roles_block=_fmt(roles),
        principles_block=_fmt(principles),
        obligations_block=_fmt(obligations),
        transformations_block=_fmt_transformations(state_transformations),
    )


class RPOEdgeExtractor(StreamingEdgeExtractor):
    """LLM-backed R->P->O dependency-edge extractor.

    LLM plumbing lives in `StreamingEdgeExtractor`; this class supplies the
    system prompt and the endpoint-category validation/dedupe below.
    """

    log_label = "R->P->O"
    default_max_tokens = 32000
    # RPO historically had no try/except around the stream, so a streaming
    # exception propagated to the caller. Preserve that (the swallowing default
    # would otherwise convert it to an empty result).
    swallow_stream_errors = False

    def _system_prompt(self) -> str:
        return _load_rpo_template().render_system(property_axioms=property_axioms_block())

    @staticmethod
    def _recover_partial_edges(raw: str) -> List[Dict[str, Any]]:
        """Salvage edge objects from a truncated JSON response.

        R->P->O edges are flat objects (no nested braces in values), so each
        complete edge survives as a brace-balanced block even when the enclosing
        array was never closed. Uses the shared scan in
        `StreamingEdgeExtractor._iter_flat_json_objects`.
        """
        out: List[Dict[str, Any]] = [
            obj for obj in StreamingEdgeExtractor._iter_flat_json_objects(raw)
            if "predicate" in obj and "subject_iri" in obj
        ]
        if out:
            logger.info("R->P->O partial-recovery salvaged %d edge(s)", len(out))
        return out

    def extract(self, case_id, roles, principles, obligations,
                state_transformations=None) -> List[Dict[str, Any]]:
        if not roles or (not obligations and not principles):
            return []
        raw = self._stream_llm(build_prompt(roles, principles, obligations, case_id,
                                            state_transformations=state_transformations))
        if not raw:
            return []
        from app.utils.llm_utils import extract_json_from_response
        try:
            data = extract_json_from_response(raw)
            edges = data.get("edges", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        except Exception as e:
            logger.warning(
                "Case %s: R->P->O full-JSON parse failed (%s); attempting "
                "per-edge recovery from possibly truncated response", case_id, e,
            )
            edges = self._recover_partial_edges(raw)

        role_iris = {r.iri for r in roles}
        principle_iris = {p.iri for p in principles}
        obligation_iris = {o.iri for o in obligations}
        cat_iris = {"Role": role_iris, "Principle": principle_iris, "Obligation": obligation_iris}

        valid: List[Dict[str, Any]] = []
        seen: Set[Tuple[str, str, str]] = set()
        def _clean(iri):
            # LLMs frequently echo IRIs wrapped in angle brackets / whitespace.
            return (iri or "").strip().lstrip("<").rstrip(">").strip()

        for e in edges:
            pred = e.get("predicate")
            s = _clean(e.get("subject_iri"))
            o = _clean(e.get("object_iri"))
            if pred not in _PRED_CATEGORY or not s or not o:
                continue
            scat, ocat = _PRED_CATEGORY[pred]
            # endpoint-category validation -- prevents disjoint-class clashes
            if s not in cat_iris[scat] or o not in cat_iris[ocat]:
                logger.info("Case %s: dropped %s edge (endpoint category/IRI mismatch)", case_id, pred)
                continue
            key = (pred, s, o)
            if key in seen:
                continue
            seen.add(key)
            valid.append({"predicate": pred, "subject_iri": s, "object_iri": o,
                          "source_text": (e.get("source_text") or "")[:500],
                          "confidence": float(e.get("confidence", 0.7))})
        logger.info("Case %s: R->P->O emitted %d edges", case_id, len(valid))
        return valid


def add_edges_to_graph(g: Graph, edges: List[Dict[str, Any]], case_id: int) -> int:
    case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")
    added = 0
    for i, e in enumerate(edges):
        s = URIRef(e["subject_iri"]); o = URIRef(e["object_iri"]); pred = _PRED_URI[e["predicate"]]
        if (s, pred, o) in g:
            continue
        g.add((s, pred, o))
        added += 1
        prov = case_ns[f"rpo_edge_provenance_{e['predicate']}_{i}"]
        g.add((prov, RDF.type, PROV.Derivation))
        g.add((prov, PROV.wasDerivedFrom, s))
        g.add((prov, PROV.wasDerivedFrom, o))
        if e.get("source_text"):
            g.add((prov, PROV.value, Literal(e["source_text"])))
        g.add((prov, RDFS.label, Literal(f"R->P->O edge: {e['predicate']}")))
    return added


# ---------------------------------------------------------------------------
# Pellet-safety guard + TTL-level applier
# ---------------------------------------------------------------------------
#
# RPOEdgeExtractor.extract validates endpoints against the per-category input
# lists built from the materialized direct rdf:type proeth-core:<Category>. That
# materialized type is a one-hop assertion that can still lag a compound class's
# full type->subClassOf* chain (e.g. an individual whose materialized type was set
# before a later retype). A range-bearing edge on a mis-resolved endpoint would
# force a disjoint core class under the nine-way AllDisjointClasses axiom and the
# case ontology would go OWL-DL inconsistent.
#
# The guard below re-validates the just-emitted edges against the MERGED
# (core + intermediate + case) graph and drops any whose endpoint's resolved
# core category conflicts with the property domain/range. It is the commit-time
# equivalent of OntServe/docs-internal/scripts/repair_rpo_type_violations.py
# (the camera-ready batch repair), folded into the applier so re-extraction can
# never reintroduce the 46-edge class of violations that repair removed.

_CORE_NS = "http://proethica.org/ontology/core#"
_CATEGORY_TO_CORE = {
    cat: URIRef(_CORE_NS + cat)
    for cat in ("Role", "Principle", "Obligation", "State", "Resource",
                "Action", "Event", "Capability", "Constraint")
}
_CORECLASSES = {v: k for k, v in _CATEGORY_TO_CORE.items()}

# predicate URI -> (expected subject core category, expected object core category)
_EDGE_RANGE = {
    HAS_OBLIGATION: ("Role", "Obligation"),
    ADHERES_TO: ("Role", "Principle"),
    DERIVED_FROM: ("Obligation", "Principle"),
}

# Defeasibility object properties (proeth-core) carry domain/range too, so an
# obligation-tagged endpoint whose type chain resolves to a different core class
# makes the case inconsistent the same way a bad R->P->O edge does. The unified
# guard (run once over the final TTL by materialize_edges_on_ttl) covers all six.
_COMPETES_WITH = PROETH_CORE.competesWith
_PREVAILS_OVER = PROETH_CORE.prevailsOver
_DEFEASIBLE_UNDER = PROETH_CORE.defeasibleUnder
_DEFEASIBILITY_RANGE = {
    _COMPETES_WITH: ("Obligation", "Obligation"),
    _PREVAILS_OVER: ("Obligation", "Obligation"),
    _DEFEASIBLE_UNDER: ("Obligation", "State"),
}
# State-anchored properties (proeth-core) materialized by state_edges.py. Their
# targets are embedding-resolved, so a low-confidence match could land on an
# endpoint of the wrong core category; the unified guard drops any such edge.
_STATE_EDGE_RANGE = {
    PROETH_CORE.activatesObligation: ("State", "Obligation"),
    PROETH_CORE.activatesConstraint: ("State", "Constraint"),
    PROETH_CORE.activatedByEvent: ("State", "Event"),
    PROETH_CORE.terminatedByEvent: ("State", "Event"),
}
# Resource-anchored property (proeth-core) materialized by the resource_edges family (edge_spec.py) from
# the resource `used_by` field. Range is Agent, which is NOT one of the nine
# disjoint core categories, so an Agent object resolves to no category and the
# range clause is skipped (kept); the guard still validates the Resource subject,
# dropping any edge whose subject's type chain does not resolve to Resource.
_RESOURCE_EDGE_RANGE = {
    PROETH_CORE.availableTo: ("Resource", "Agent"),
}
# State-anchored actor edge materialized by the state_affects_edges family (edge_spec.py) from the state
# `affectedParties` field. Range is Agent (outside the nine disjoint categories),
# so the object resolves to no category and the range clause is skipped; the guard
# still validates the State subject.
_STATE_AFFECTS_RANGE = {
    PROETH_CORE.affects: ("State", "Agent"),
}
# Participant edges materialized by the participant family (edge_spec) from the
# Pass-2 component 'who' fields (obligatedParty / constrainedEntity / possessedBy /
# invokedBy) plus the actor-edge additions: resource cited_by -> citedByAgent and the
# Step-3 per-action hasAgent -> isPerformedBy. Range is Agent (outside the nine
# disjoint categories), so the object resolves to no category and the range clause is
# skipped; the guard still validates that the subject's type chain resolves to the
# declared component category.
_PARTICIPANT_EDGE_RANGE = {
    PROETH_CORE.obligatedParty: ("Obligation", "Agent"),
    PROETH_CORE.constrainedEntity: ("Constraint", "Agent"),
    PROETH_CORE.possessedBy: ("Capability", "Agent"),
    PROETH_CORE.invokedBy: ("Principle", "Agent"),
    PROETH_CORE.citedByAgent: ("Resource", "Agent"),
    PROETH_CORE.isPerformedBy: ("Action", "Agent"),
}
# Obligation -> Capability requirement edges materialized by the requires_capability
# family (edge_spec) from the capability individuals' requiredForObligations labels
# (core v2.8.0: an obligation presupposes the capacity to discharge it). Both
# endpoints are among the nine disjoint categories, so the guard validates both.
# establishedBy: Constraint proeth:source -> nspe: CodeProvision, materialized by
# provision_citation_resolver.apply_established_by_on_ttl. The declared domain is
# union(Principle, Obligation, Constraint); CodeProvision is outside the nine (and
# the nspe ontology is not loaded into the merged graph), so the object resolves to
# no core category and the range clause is skipped -- the guard still validates the
# P/O/Cs union subject.
_CAPABILITY_PROVISION_RANGE = {
    PROETH_CORE.requiresCapability: ("Obligation", "Capability"),
    PROETH_CORE.establishedBy: ({"Principle", "Obligation", "Constraint"}, "CodeProvision"),
    # containsProvision subjects are code resources (Guideline-chained); the guard resolves
    # to the nine categories only, so Resource is the finest checkable granularity here
    # (the applier's own EthicalCode direct-type restriction carries the Guideline discipline).
    PROETH_CORE.containsProvision: ("Resource", "CodeProvision"),
}
# Fluent transitions materialized by the fluent_edges family (edge_spec.py; Event Calculus initiates/terminates).
# The subject is a happening, which is an Action OR an Event, so the subject slot is a SET
# of allowed categories (the guard normalizes a single string to a singleton, so only these
# need the set form). Object is State. A happening whose type resolves to neither Action nor
# Event, or an object that is not a State, is dropped by the guard.
_FLUENT_EDGE_RANGE = {
    PROETH_CORE.initiates: ({"Action", "Event"}, "State"),
    PROETH_CORE.terminates: ({"Action", "Event"}, "State"),
}
# Action normative-engagement edges materialized by the obligation_edges family (edge_spec.py) from the Step-3
# Action's fulfills / violates / raises obligation labels and guidedByPrinciple labels.
# Domain Action, range Obligation/Principle, both among the nine disjoint categories, so
# the guard validates BOTH endpoints and drops any mis-resolved edge. All four are declared
# in proeth-core: violates/raises/guidedByPrinciple were promoted from intermediate in v2.8.0,
# joining fulfillsObligation, which was already core.
_NORMATIVE_EDGE_RANGE = {
    PROETH_CORE.fulfillsObligation: ("Action", "Obligation"),
    PROETH_CORE.violatesObligation: ("Action", "Obligation"),
    PROETH_CORE.raisesObligation: ("Action", "Obligation"),
    PROETH_CORE.guidedByPrinciple: ("Action", "Principle"),
}
# Causal-chain endpoint edges materialized by causal_edges.py. Domain CausalChain is NOT
# one of the nine disjoint core categories, so the subject resolves to an empty core-set
# and the domain clause never fires (the chain is never dropped on its subject). cause /
# effect range over the happenings (Action OR Event, both disjoint -> the object is
# validated); responsibleAgent range is Agent (outside the nine -> range clause skipped).
_CAUSAL_EDGE_RANGE = {
    PROETH.cause: ("CausalChain", {"Action", "Event"}),
    PROETH.effect: ("CausalChain", {"Action", "Event"}),
    PROETH.responsibleAgent: ("CausalChain", "Agent"),
    # Event -> causing Action (materialized by causal_edges.apply_event_cause_edges from
    # the converter's legacy causedByAction IRI). Both endpoints are disjoint categories,
    # so the guard validates both.
    PROETH.causedByAction: ("Event", "Action"),
    # CausalNormativeLink (reasoning node) -> the Action it analyzes. Subject is a non-D-tuple
    # analysis node (empty domain clause -> never dropped on the subject); range Action.
    PROETH.analyzesAction: ("CausalNormativeLink", "Action"),
}
# Temporal (Allen) relation endpoint edges materialized by the temporal_relation_edges family (edge_spec.py)
# from each reified TemporalRelation's fromEntity/toEntity timeline phrasings. Domain
# TemporalRelation is NOT one of the nine disjoint core categories, so the subject
# resolves to an empty core-set and the domain clause never fires (the relation node is
# never dropped on its subject). Range is the happenings (Action OR Event, both disjoint
# -> the object IS validated), matching the declared owl:ObjectProperty range
# unionOf(Action, Event); a phrasing mis-resolved to a State endpoint is dropped here.
_TEMPORAL_RELATION_RANGE = {
    PROETH.fromEntity: ("TemporalRelation", {"Action", "Event"}),
    PROETH.toEntity: ("TemporalRelation", {"Action", "Event"}),
}
ALL_EDGE_RANGE = {**_EDGE_RANGE, **_DEFEASIBILITY_RANGE, **_STATE_EDGE_RANGE,
                  **_RESOURCE_EDGE_RANGE, **_STATE_AFFECTS_RANGE,
                  **_PARTICIPANT_EDGE_RANGE, **_CAPABILITY_PROVISION_RANGE,
                  **_FLUENT_EDGE_RANGE,
                  **_NORMATIVE_EDGE_RANGE, **_CAUSAL_EDGE_RANGE,
                  **_TEMPORAL_RELATION_RANGE}


def _default_ontology_paths() -> Tuple[Any, Any]:
    """Locate proethica-core.ttl / proethica-intermediate.ttl on the OntServe
    disk relative to this file (/home/chris/onto/OntServe/ontologies)."""
    from pathlib import Path
    onto_root = Path(__file__).resolve().parents[4]  # .../onto
    ont_dir = onto_root / "OntServe" / "ontologies"
    return ont_dir / "proethica-core.ttl", ont_dir / "proethica-intermediate.ttl"


def _add_missing_subclass_declarations(g: Graph) -> int:
    """Mirror pellet_validate._add_missing_subclass_declarations: for each
    LLM-generated class used as rdf:type but lacking an rdfs:subClassOf, derive
    the parent core class from the individual's materialized direct
    rdf:type proeth-core:<Category> (CMT-1) and add it. Classes that already carry
    a real subClassOf (e.g. an intermediate class) are left alone, so their genuine
    chain takes precedence. The retired proeth:conceptCategory literal is no longer
    consulted; the materialized direct type carries the same category one hop away."""
    from rdflib import OWL
    class_categories: Dict[Any, str] = {}
    for ind in g.subjects(RDF.type, OWL.NamedIndividual):
        types = list(g.objects(ind, RDF.type))
        direct = next((_CORECLASSES[t] for t in types if t in _CORECLASSES), None)
        if not direct:
            continue
        for cls in types:
            if cls == OWL.NamedIndividual or cls in _CORECLASSES:
                continue
            if list(g.objects(cls, RDFS.subClassOf)):
                continue
            class_categories.setdefault(cls, direct)
    added = 0
    for cls_uri, cat in class_categories.items():
        core_parent = _CATEGORY_TO_CORE.get(cat)
        if core_parent:
            g.add((cls_uri, RDF.type, OWL.Class))
            g.add((cls_uri, RDFS.subClassOf, core_parent))
            added += 1
    return added


def _build_merged_graph(case_graph: Graph, core_ttl, intermediate_ttl) -> Graph:
    """core + intermediate + intermediate-extended + case, owl:imports stripped,
    missing subclass chains filled from the materialized direct type.

    intermediate-extended carries the "discovered" classes (their established
    subClassOf-core chains) that committed cases type individuals to; loading it
    here means the guard resolves an endpoint's core category the same way the
    persisted case does, falling back to the materialized direct rdf:type only when
    a class chain is absent."""
    from pathlib import Path
    from rdflib import OWL
    g = Graph()
    g.parse(str(core_ttl), format="turtle")
    g.parse(str(intermediate_ttl), format="turtle")
    extended = Path(intermediate_ttl).with_name("proethica-intermediate-extended.ttl")
    if extended.exists():
        g.parse(str(extended), format="turtle")
    for t in case_graph:
        g.add(t)
    for t in list(g.triples((None, OWL.imports, None))):
        g.remove(t)
    _add_missing_subclass_declarations(g)
    return g


def _core_categories(merged: Graph, ind) -> Set[str]:
    """All core categories reachable from an individual via type->subClassOf*."""
    cats: Set[str] = set()
    seen: Set[Any] = set()
    stack = list(merged.objects(ind, RDF.type))
    while stack:
        c = stack.pop()
        if c in seen:
            continue
        seen.add(c)
        if c in _CORECLASSES:
            cats.add(_CORECLASSES[c])
        for sup in merged.objects(c, RDFS.subClassOf):
            stack.append(sup)
    return cats


def drop_domain_range_violations(g: Graph, case_id: int,
                                 core_ttl=None, intermediate_ttl=None,
                                 edge_range=None) -> int:
    """Remove edges from ``g`` (in place) whose endpoint's resolved core category
    violates the property domain/range, plus their PROV-O Derivation nodes.

    ``edge_range`` maps predicate URI -> (subject category, object category) and
    defaults to the three R->P->O properties. Pass ALL_EDGE_RANGE to also guard
    the defeasibility properties (the unified guard used at materialization).

    Endpoints with no resolved core category cannot be proven to violate and are
    kept (mirrors repair_rpo_type_violations). Returns the triples removed."""
    if core_ttl is None or intermediate_ttl is None:
        dc, di = _default_ontology_paths()
        core_ttl = core_ttl or dc
        intermediate_ttl = intermediate_ttl or di
    if edge_range is None:
        edge_range = _EDGE_RANGE

    # A category slot is either a single category string or a set of allowed categories
    # (a union domain/range, e.g. initiates/terminates whose subject may be Action OR
    # Event). Normalize to a set so the disjointness test below is uniform.
    def _allowed(slot):
        return slot if isinstance(slot, (set, frozenset)) else {slot}

    merged = _build_merged_graph(g, core_ttl, intermediate_ttl)
    bad = []
    for pred, (dom_exp, rng_exp) in edge_range.items():
        dom_allowed, rng_allowed = _allowed(dom_exp), _allowed(rng_exp)
        for s, o in merged.subject_objects(pred):
            sc = _core_categories(merged, s)
            oc = _core_categories(merged, o)
            # The nine core categories are mutually disjoint, so an endpoint that
            # reaches ANY core category OTHER than the property's required one would
            # be forced (by the edge's domain/range) into two disjoint categories ->
            # inconsistent. Drop on that condition, not merely when the required
            # category is absent: an endpoint can reach the required category AND a
            # conflicting one (e.g. a class name-collision left it subClassOf both
            # Principle and Capability), which the reasoner still rejects. Endpoints
            # with no resolved core category, or whose required category is outside
            # the nine (e.g. Agent for availableTo/affects), yield an empty set
            # difference and are kept.
            if (sc - dom_allowed) or (oc - rng_allowed):
                bad.append((s, pred, o))
    if not bad:
        return 0

    removed = 0
    badset = set(bad)
    for s, p, o in bad:
        if (s, p, o) in g:
            g.remove((s, p, o))
            removed += 1
    # Drop the dedicated PROV-O Derivation node for each removed edge. Both the
    # R->P->O and defeasibility extractors mint one Derivation per edge with both
    # endpoints as prov:wasDerivedFrom, so match generically on that pair.
    for prov in list(g.subjects(RDF.type, PROV.Derivation)):
        derived = set(g.objects(prov, PROV.wasDerivedFrom))
        for s, p, o in badset:
            if s in derived and o in derived:
                for pp, oo in list(g.predicate_objects(prov)):
                    g.remove((prov, pp, oo))
                    removed += 1
                break
    logger.info("Case %s: dropped %d domain/range-violating edge triple(s) over %d propert(ies)",
                case_id, removed, len(edge_range))
    return removed


def apply_rpo_edges(case_id: int, ttl_path, extractor: Optional["RPOEdgeExtractor"] = None,
                    write_back: bool = True, core_ttl=None, intermediate_ttl=None) -> Dict[str, Any]:
    """Materialize R->P->O dependency edges on one case TTL.

    Mirrors defeasibility_pipeline.apply_defeasibility_edges: parse the TTL,
    gather Role/Principle/Obligation individuals, call the extractor, add the
    edges + PROV-O, then drop any edge that violates domain/range against the
    reasoner-visible type chain, and optionally re-serialize.

    Returns a status dict (one of: missing_ttl, insufficient_entities, no_edges,
    ok). Successful runs include emitted/added/dropped counts.
    """
    from pathlib import Path
    ttl_path = Path(ttl_path)
    if not ttl_path.exists():
        return {"case_id": case_id, "status": "missing_ttl"}

    g = Graph()
    g.parse(str(ttl_path), format="turtle")

    roles, principles, obligations = gather(g, case_id)
    if not roles or (not obligations and not principles):
        return {"case_id": case_id, "status": "insufficient_entities",
                "roles": len(roles), "principles": len(principles),
                "obligations": len(obligations)}

    # Grounding: the state-edge applier (run first) annotates state individuals
    # with proeth:principleTransformation (the S->P->O account). Feed those into
    # the derivedFromPrinciple derivation instead of re-deriving blind.
    state_transformations = []
    for s, t in g.subject_objects(PROETH.principleTransformation):
        lbl = next(g.objects(s, RDFS.label), None)
        state_transformations.append((str(lbl) if lbl else str(s).split("#")[-1], str(t)))

    if extractor is None:
        extractor = RPOEdgeExtractor()
    edges = extractor.extract(case_id, roles, principles, obligations,
                              state_transformations=state_transformations)
    if not edges:
        return {"case_id": case_id, "status": "no_edges",
                "roles": len(roles), "principles": len(principles),
                "obligations": len(obligations)}

    added = add_edges_to_graph(g, edges, case_id)
    dropped = drop_domain_range_violations(g, case_id, core_ttl, intermediate_ttl)

    if write_back:
        g.bind("proeth", PROETH)
        g.bind("proeth-core", PROETH_CORE)
        g.bind("prov", PROV)
        g.serialize(destination=str(ttl_path), format="turtle")

    return {"case_id": case_id, "status": "ok",
            "roles": len(roles), "principles": len(principles),
            "obligations": len(obligations),
            "edges_emitted": len(edges), "triples_added": added,
            "triples_dropped": dropped}
