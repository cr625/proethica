"""
R -> P -> O dependency-chain edge extractor (KI2026 §3 materialization).

Asserts the three Role/Principle/Obligation object properties between
already-extracted typed individuals:

  - proeth-core:hasObligation       Role -> Obligation
  - proeth-core:adheresToPrinciple  Role -> Principle
  - proeth:derivedFromPrinciple     Obligation -> Principle

These were declared in the ontology but never materialized in the per-case
TTLs (the link lived only in narrative datatype fields). This module makes the
R->P->O chain SPARQL-traversable per case, with PROV-O provenance attaching
each edge to the verbatim narrative text that justifies it.

Design mirrors defeasibility_edges.py: streaming LLM call, IRI validation
against the supplied entity lists, dedupe. CRITICAL ADDITION: endpoints are
validated by conceptCategory (subject/object must be the property's
rdfs:domain/range category) so edges cannot force an individual into a
disjoint core class -- this preserves the OWL-DL consistency restored in the
KI2026 corpus repair.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from rdflib import Graph, Literal, RDF, RDFS, URIRef, Namespace

logger = logging.getLogger(__name__)

PROETH = Namespace("http://proethica.org/ontology/intermediate#")
PROETH_CORE = Namespace("http://proethica.org/ontology/core#")
PROV = Namespace("http://www.w3.org/ns/prov#")

HAS_OBLIGATION = PROETH_CORE.hasObligation
ADHERES_TO = PROETH_CORE.adheresToPrinciple
DERIVED_FROM = PROETH.derivedFromPrinciple

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

PROPERTY_AXIOMS = """\
proeth-core:hasObligation a owl:ObjectProperty ;
    rdfs:domain proeth-core:Role ; rdfs:range proeth-core:Obligation ;
    rdfs:comment "Relates a role to its professional obligations."@en .
proeth-core:adheresToPrinciple a owl:ObjectProperty ;
    rdfs:domain proeth-core:Role ; rdfs:range proeth-core:Principle ;
    rdfs:comment "Relates a role to principles that guide its conduct."@en .
proeth:derivedFromPrinciple a owl:ObjectProperty ;
    rdfs:domain proeth-core:Obligation ; rdfs:range proeth-core:Principle ;
    rdfs:comment "Links obligation to the principle(s) it operationalizes."@en .\
"""

SYSTEM_PROMPT = (
    "You are an R->P->O dependency-chain extractor for the ProEthica D-tuple model. "
    "You link previously extracted Role, Principle, and Obligation individuals using "
    "exactly three proethica object properties. You must NOT invent classes, individuals, "
    "IRIs, or property names. Output STRICT JSON only -- no prose, no markdown fences.\n\n"
    "Property axioms (verbatim from the ontology):\n\n" + PROPERTY_AXIOMS + "\n\n"
    "Hard constraints:\n"
    "  1. predicate is exactly one of: hasObligation, adheresToPrinciple, derivedFromPrinciple.\n"
    "  2. hasObligation: subject is a ROLE iri, object is an OBLIGATION iri.\n"
    "  3. adheresToPrinciple: subject is a ROLE iri, object is a PRINCIPLE iri.\n"
    "  4. derivedFromPrinciple: subject is an OBLIGATION iri, object is a PRINCIPLE iri.\n"
    "  5. subject_iri and object_iri must each appear verbatim in the supplied lists. "
    "Copy them character-for-character.\n"
    "  6. Every edge must be supported by a verbatim source_text drawn from one of the "
    "narrative fields supplied (e.g. an obligation's obligatedparty/obligationstatement, "
    "a principle's invokedby, a role's relationships). Set source_text to that quote.\n"
    "  7. Only assert an edge when the narrative genuinely supports it. Omit speculative links."
)


@dataclass
class Indiv:
    iri: str
    label: str
    fields: Dict[str, str]


def _individuals_in_category(g: Graph, category: str) -> List[URIRef]:
    out = []
    for s, _, _ in g.triples((None, PROETH.conceptCategory, Literal(category))):
        out.append(s)
    return out


def _fields(g: Graph, ind: URIRef, names: List[str]) -> Dict[str, str]:
    d = {}
    for n in names:
        vals = [str(o) for o in g.objects(ind, PROETH[n])]
        if vals:
            d[n] = vals[0]
    return d


def gather(g: Graph) -> Tuple[List[Indiv], List[Indiv], List[Indiv]]:
    def mk(ind, names):
        lbl = g.value(ind, RDFS.label)
        return Indiv(str(ind), str(lbl) if lbl else str(ind).split("#")[-1], _fields(g, ind, names))
    roles = [mk(r, ["roleclass", "casecontext", "relationships"]) for r in _individuals_in_category(g, "Role")]
    principles = [mk(p, ["principleclass", "invokedby", "appliedto", "concreteexpression"])
                  for p in _individuals_in_category(g, "Principle")]
    obligations = [mk(o, ["obligationclass", "obligatedparty", "obligationstatement"])
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
    return (
        f"Extract R->P->O dependency edges for case {case_id}.\n\n"
        f"ROLES (subject of hasObligation / adheresToPrinciple):\n{_fmt(roles)}\n\n"
        f"PRINCIPLES (object of adheresToPrinciple / derivedFromPrinciple):\n{_fmt(principles)}\n\n"
        f"OBLIGATIONS (object of hasObligation; subject of derivedFromPrinciple):\n{_fmt(obligations)}\n\n"
        f"{_fmt_transformations(state_transformations)}"
        "TASK: Assert hasObligation (which role bears which obligation), adheresToPrinciple "
        "(which role is guided by which principle), and derivedFromPrinciple (which obligation "
        "operationalizes which principle), using the narrative fields as evidence. "
        "If no edge is warranted, return an empty edges array.\n\n"
        'OUTPUT (strict JSON): {"edges": [{"predicate": "...", "subject_iri": "...", '
        '"object_iri": "...", "source_text": "...", "confidence": 0.9}]}'
    )


class RPOEdgeExtractor:
    def __init__(self, llm_client=None, model=None, temperature=0.1, max_tokens=32000):
        self._llm_client = llm_client
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def _client(self):
        if self._llm_client is None:
            from app.utils.llm_utils import get_llm_client
            self._llm_client = get_llm_client()
        return self._llm_client

    def _resolve_model(self):
        if self.model:
            return self.model
        # R->P->O is a paper-critical, relational reasoning task and a bounded one
        # call per case, so it runs on the powerful tier (Opus).
        from model_config import ModelConfig
        return ModelConfig.get_claude_model("powerful")

    def _call(self, prompt) -> Optional[str]:
        client = self._client()
        model = self._resolve_model()
        if not (hasattr(client, "messages") and hasattr(client.messages, "stream")):
            logger.error("RPOEdgeExtractor requires an Anthropic streaming client")
            return None
        chunks: List[str] = []
        with client.messages.stream(
            model=model, max_tokens=self.max_tokens, temperature=self.temperature,
            system=SYSTEM_PROMPT, messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for t in stream.text_stream:
                chunks.append(t)
            final_msg = stream.get_final_message()
        if getattr(final_msg, "stop_reason", None) == "max_tokens":
            logger.warning(
                "R->P->O hit max_tokens (%d); response truncated, "
                "partial recovery will be attempted", self.max_tokens,
            )
        return "".join(chunks)

    @staticmethod
    def _recover_partial_edges(raw: str) -> List[Dict[str, Any]]:
        """Salvage edge objects from a truncated JSON response.

        R->P->O edges are flat objects (no nested braces in values), so each
        complete edge is a `{ ... }` block with no inner braces. Scanning for
        such blocks recovers every edge that landed before the max_tokens
        cutoff even when the enclosing array was never closed. Mirrors
        DefeasibilityEdgeExtractor._recover_partial_edges.
        """
        import json as _json
        import re as _re

        out: List[Dict[str, Any]] = []
        for m in _re.finditer(r"\{[^{}]*\}", raw):
            try:
                obj = _json.loads(m.group(0))
            except Exception:
                continue
            if isinstance(obj, dict) and "predicate" in obj and "subject_iri" in obj:
                out.append(obj)
        if out:
            logger.info("R->P->O partial-recovery salvaged %d edge(s)", len(out))
        return out

    def extract(self, case_id, roles, principles, obligations,
                state_transformations=None) -> List[Dict[str, Any]]:
        if not roles or (not obligations and not principles):
            return []
        raw = self._call(build_prompt(roles, principles, obligations, case_id,
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
# RPOEdgeExtractor.extract validates endpoints against the proeth:conceptCategory
# literal. That literal can disagree with the reasoner-visible type->subClassOf*
# chain (e.g. an individual tagged conceptCategory "Principle" whose rdf:type
# resolves through proethica-intermediate to Capability). A range-bearing edge
# then forces the individual into a disjoint core class under the nine-way
# AllDisjointClasses axiom and the case ontology goes OWL-DL inconsistent.
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
# Resource-anchored property (proeth-core) materialized by resource_edges.py from
# the resource `used_by` field. Range is Agent, which is NOT one of the nine
# disjoint core categories, so an Agent object resolves to no category and the
# range clause is skipped (kept); the guard still validates the Resource subject,
# dropping any edge whose subject's type chain does not resolve to Resource.
_RESOURCE_EDGE_RANGE = {
    PROETH_CORE.availableTo: ("Resource", "Agent"),
}
ALL_EDGE_RANGE = {**_EDGE_RANGE, **_DEFEASIBILITY_RANGE, **_STATE_EDGE_RANGE,
                  **_RESOURCE_EDGE_RANGE}


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
    the parent core class from an instance's conceptCategory and add it. Classes
    that already carry a real subClassOf (e.g. an intermediate class) are left
    alone, so their genuine chain takes precedence over the literal."""
    from rdflib import OWL
    class_categories: Dict[Any, str] = {}
    for ind in g.subjects(RDF.type, OWL.NamedIndividual):
        for cls in g.objects(ind, RDF.type):
            if cls == OWL.NamedIndividual:
                continue
            if list(g.objects(cls, RDFS.subClassOf)):
                continue
            if cls not in class_categories:
                cats = list(g.objects(ind, PROETH.conceptCategory))
                if cats:
                    class_categories[cls] = str(cats[0])
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
    missing subclass chains filled from conceptCategory.

    intermediate-extended carries the "discovered" classes (their established
    subClassOf-core chains) that committed cases type individuals to; loading it
    here means the guard resolves an endpoint's core category the same way the
    persisted case does, instead of falling back to the conceptCategory literal."""
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

    merged = _build_merged_graph(g, core_ttl, intermediate_ttl)
    bad = []
    for pred, (dom_exp, rng_exp) in edge_range.items():
        for s, o in merged.subject_objects(pred):
            sc = _core_categories(merged, s)
            oc = _core_categories(merged, o)
            if (sc and dom_exp not in sc) or (oc and rng_exp not in oc):
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

    roles, principles, obligations = gather(g)
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
