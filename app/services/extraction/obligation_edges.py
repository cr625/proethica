"""Action normative-engagement edge materialization (DB-driven, embedding-resolved).

Grounds the Step-3 Action's normative engagement to the ACTUAL case Obligation and
Principle individuals. The temporal extraction names, per Action, the obligations it
fulfills / violates / raises and the principles that guide it, as free-text label lists:

  proeth:fulfillsObligation [ "NSPE Professional Obligation III.7.a., ..." ]
  proeth:violatesObligation [ ... ]
  proeth:raisesObligation   [ ... ]   (added by the obligation_engagement reclassifier)
  proeth:guidedByPrinciple  [ ... ]

Before this applier those lists persisted ONLY as dangling proeth:fulfillsObligationText /
violatesObligationText / guidedByPrincipleText datatype literals (the commit serializer
demotes a literal sitting on an owl:ObjectProperty to a <local>Text sibling). They named
obligations/principles in free text that matched no extracted individual, so the Action's
normative engagement was disconnected from the obligation and principle entities extracted
in Steps 1-2.

This applier WIRES THEM IN. It reads the four label lists off each Action row in
temporary_rdf_storage, resolves each named obligation/principle to the matching case
proeth-core:Obligation / proeth-core:Principle individual, and materialises a first-class
object property with PROV-O provenance:

  Action proeth-core:fulfillsObligation Obligation
  Action proeth:violatesObligation      Obligation
  Action proeth:raisesObligation        Obligation
  Action proeth:guidedByPrinciple       Principle

This completes the Event-Calculus loop the fluent and state appliers begin: an Action
initiates a State (fluent_edges), the State activatesObligation / activatesConstraint the
real O/Cs (state_edges), and the Action fulfills / violates / raises THAT SAME obligation
individual. The three-bucket fulfills / violates / raises split is the obligation-engagement
reclassification (Sarmiento et al. 2023, NESS causal responsibility; Berreby et al. 2017,
obligations as fulfilled/violated fluents; Dennis et al. 2016, defeasible obligations put
in force). The Text literals remain as raw-LLM-text provenance, exactly as initiatesText
coexists with proeth-core:initiates.

Domain Action, range Obligation / Principle, all four within the nine disjoint categories,
so the unified domain/range guard validates BOTH endpoints and drops any mis-resolved edge
(stronger than the Agent-ranged participant/affects edges, whose range is unconstrained).
fulfillsObligation is declared in proeth-core (with an intermediate equivalent); the other
three are declared in proeth-intermediate, so each edge uses its declaring namespace.

Structurally identical to fluent_edges.py / state_affects_edges.py: embedding shortlist
over the candidate pool + one batched LLM multi-select per edge-type, with an
embedding-threshold fallback. Best-effort: failures are logged and returned, never raised.
A label that matches no case individual yields no edge. No-op for cases with no committed
Action individuals.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef

from app.services.extraction.state_edges import (
    _candidate_pool,
    _embedding_service,
    _individuals_in_category,
    _label,
    _norm,
    _safe_frag,
    _shortlist,
)
from app.services.extraction.resource_edges import _llm_select_multi

logger = logging.getLogger(__name__)

CORE = Namespace("http://proethica.org/ontology/core#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
PROV = Namespace("http://www.w3.org/ns/prov#")

EMBED_MATCH_MIN = 0.50
SHORTLIST_FLOOR = 0.30
SHORTLIST_K = 8

# Per-edge specification, evaluated in order. Each entry:
#   (property local name, declaring namespace, target core category,
#    temp-row JSON-LD field keys carrying the label list,
#    pool match fields read off the candidate individual in the committed graph)
# fulfillsObligation lives in proeth-core (canonical, matches state_edges); the other
# three are proeth-intermediate-only. The committed graph stores the narrative fields in
# camelCase (obligationStatement, principleClass), so the pool uses those exact names.
_NORMATIVE_SPECS: Tuple[Tuple[str, Namespace, str, Tuple[str, ...], List[str]], ...] = (
    ("fulfillsObligation", CORE, "Obligation",
     ("proeth:fulfillsObligation", "fulfillsObligation"),
     ["obligationStatement", "obligationClass"]),
    ("violatesObligation", PROETH, "Obligation",
     ("proeth:violatesObligation", "violatesObligation"),
     ["obligationStatement", "obligationClass"]),
    ("raisesObligation", PROETH, "Obligation",
     ("proeth:raisesObligation", "raisesObligation"),
     ["obligationStatement", "obligationClass"]),
    ("guidedByPrinciple", PROETH, "Principle",
     ("proeth:guidedByPrinciple", "guidedByPrinciple"),
     ["principleClass", "interpretation", "concreteExpression"]),
)

_VERB = {
    "fulfillsObligation": "FULFILS (directly satisfies)",
    "violatesObligation": "VIOLATES (directly breaches)",
    "raisesObligation": "RAISES (puts in force / at stake, resolved later)",
    "guidedByPrinciple": "is GUIDED BY (the principle directing it)",
}


def _actions_from_db(case_id: int) -> List[Dict[str, Any]]:
    """[{label, fulfillsObligation:[...], violatesObligation:[...], raisesObligation:[...],
    guidedByPrinciple:[...]}] for each Step-3 ACTION individual that names at least one
    obligation or principle. Read from the temporal_dynamics_enhanced rows, whose
    rdf_json_ld stores the JSON-LD entity directly (proeth: keys at top level)."""
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    rows = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type="temporal_dynamics_enhanced", storage_type="individual"
    ).all()
    out = []
    for r in rows:
        rdf = r.rdf_json_ld or {}
        at_type = rdf.get("@type", "") or ""
        # Domain of all four properties is Action; events route through the fluent path.
        if "Action" not in at_type:
            continue

        def _labels(keys):
            for k in keys:
                v = rdf.get(k)
                if v:
                    vals = v if isinstance(v, list) else [v]
                    return [str(x).strip() for x in vals if str(x).strip()]
            return []

        rec = {"label": r.entity_label or rdf.get("rdfs:label", "")}
        any_field = False
        for prop, _ns, _cat, field_keys, _pool_fields in _NORMATIVE_SPECS:
            labels = _labels(field_keys)
            rec[prop] = labels
            any_field = any_field or bool(labels)
        if any_field:
            out.append(rec)
    return out


def _build_normative_prompt(prop: str):
    verb = _VERB.get(prop, prop)
    target = "PRINCIPLE" if prop == "guidedByPrinciple" else "OBLIGATION"

    def builder(items: List[Dict[str, Any]]) -> str:
        blocks = []
        for it in items:
            cands = "; ".join(
                f"{i + 1}) {lbl[:90]}" for i, (iri, lbl, sim) in enumerate(it["shortlist"])
            )
            blocks.append(
                f"[{it['id']}] action: \"{(it.get('subj_label') or '')[:120]}\"\n"
                f"  {target}(s) it {prop}: \"{(it['desc'] or '')[:240]}\"\n"
                f"  candidate {target.lower()}s: {cands}"
            )
        return (
            f"Each REQUEST gives an ACTION in an engineering-ethics case and the "
            f"{target} text saying which {target.lower()}(s) the action {verb}, plus the "
            f"candidate {target.lower()}s extracted from that case.\n"
            f"For each request, choose ALL candidate {target.lower()}s that the action "
            f"{prop}. The text may name several, one, or none.\n"
            f"Choose NONE (an empty list) when a named {target.lower()} does not correspond "
            f"to any listed candidate (it was not separately extracted, or the text is a "
            f"general phrase rather than one of the case's {target.lower()}s). Match on the "
            f"substance of the duty/principle, not on shared wording alone.\n\n"
            "REQUESTS:\n" + "\n\n".join(blocks) +
            "\n\nOUTPUT strict JSON only, one entry per request id, each value a JSON array "
            "of the chosen candidate numbers (use [] for none): {\"<id>\": [<n>, ...], ...}"
        )
    return builder


def _emit_prov(g: Graph, case_id: int, prop: str, subj, obj, desc: str) -> None:
    case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")
    prov_iri = case_ns["normative_edge_provenance_" + _safe_frag(subj) + "_" + prop + "_" + _safe_frag(obj)]
    if (prov_iri, RDF.type, PROV.Derivation) in g:
        return
    g.add((prov_iri, RDF.type, PROV.Derivation))
    g.add((prov_iri, PROV.wasDerivedFrom, subj))
    g.add((prov_iri, PROV.wasDerivedFrom, obj))
    g.add((prov_iri, RDFS.label, Literal(f"Normative edge ({prop})")))
    if desc:
        g.add((prov_iri, PROV.value, Literal(str(desc))))
    g.add((prov_iri, RDFS.comment, Literal(
        f"property={prop}; action's {prop} text resolved to the case "
        "Obligation/Principle individual(s) by embedding shortlist + LLM multi-select "
        "(obligation-engagement grounding)")))


def apply_obligation_edges(case_id: int, ttl_path, write_back: bool = True,
                           threshold: float = EMBED_MATCH_MIN, use_llm: bool = True,
                           llm_client=None, model=None) -> Dict[str, Any]:
    """Materialize Action -> Obligation/Principle (fulfills / violates / raises /
    guidedByPrinciple) edges on a committed case TTL. Reads each Step-3 Action's normative
    label lists from temporary_rdf_storage, resolves them to the case proeth-core:Obligation
    / Principle individuals (embedding shortlist + batched LLM multi-select per property;
    embedding-threshold fallback), and adds the edges + provenance. Returns per-property
    counts."""
    ttl_path = Path(ttl_path)
    res: Dict[str, Any] = {"case_id": case_id, "status": "ok", "total": 0}
    try:
        actions = _actions_from_db(case_id)
    except Exception as e:
        logger.warning("obligation_edges: temp_rdf read failed for case %s: %s", case_id, e)
        return {"case_id": case_id, "status": "no_db", "error": str(e)}
    if not actions:
        return {"case_id": case_id, "status": "no_normative_engagement"}

    g = Graph()
    g.parse(str(ttl_path), format="turtle")
    svc = _embedding_service()

    # Subject map: Action individuals by normalized label (domain Action for all four).
    action_iris: Dict[str, URIRef] = {}
    for ind in _individuals_in_category(g, "Action"):
        action_iris.setdefault(_norm(_label(g, ind)), ind)
    if not action_iris:
        return {"case_id": case_id, "status": "no_actions"}

    # Object pools, one per target category, built once and reused across specs.
    pools: Dict[str, Any] = {}

    for prop, ns, target_cat, _fields, pool_fields in _NORMATIVE_SPECS:
        if target_cat not in pools:
            pools[target_cat] = _candidate_pool(g, svc, target_cat, pool_fields)
        pool = pools[target_cat]
        if not pool:
            res[prop] = {"edges": 0, "status": f"no_{target_cat.lower()}s"}
            continue

        items: List[Dict[str, Any]] = []
        next_id = 1
        unresolved = 0
        for a in actions:
            labels = a.get(prop) or []
            if not labels:
                continue
            subj = action_iris.get(_norm(a["label"]))
            if subj is None:
                logger.info("obligation_edges[%s]: action %r not in committed graph; skipped",
                            prop, (a["label"] or "")[:80])
                continue
            desc = "; ".join(labels)
            sl = _shortlist(svc, desc, pool, SHORTLIST_FLOOR, SHORTLIST_K)
            if not sl:
                unresolved += 1
                logger.info("obligation_edges[%s]: no %s above floor %.2f for %r",
                            prop, target_cat, SHORTLIST_FLOOR, desc[:80])
                continue
            items.append({"id": next_id, "subj": subj, "desc": desc,
                          "subj_label": a["label"], "shortlist": sl})
            next_id += 1

        selections = _llm_select_multi(
            items, client=llm_client, model=model, prompt_builder=_build_normative_prompt(prop)
        ) if use_llm else None
        resolver = "llm" if selections is not None else "embedding"

        edges = 0
        for it in items:
            subj, desc, sl = it["subj"], it["desc"], it["shortlist"]
            if selections is not None:
                targets = selections.get(str(it["id"])) or []
            else:
                targets = [iri for iri, _lbl, sim in sl if sim >= threshold]
            if not targets:
                unresolved += 1
                continue
            for tgt in targets:
                if (subj, ns[prop], tgt) in g:
                    continue
                g.add((subj, ns[prop], tgt))
                _emit_prov(g, case_id, prop, subj, tgt, desc)
                edges += 1
        res[prop] = {"edges": edges, "resolver": resolver, "unresolved": unresolved}

    total = sum(v.get("edges", 0) for v in res.values() if isinstance(v, dict))
    res["total"] = total
    if write_back and total:
        g.serialize(destination=str(ttl_path), format="turtle")
    return res
