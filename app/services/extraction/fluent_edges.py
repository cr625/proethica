"""Fluent-transition edge materialization (DB-driven, embedding-resolved).

The Event Calculus (Kowalski & Sergot 1986; Berreby et al. 2017) represents change by
having a happening Initiate or Terminate a fluent. In ProEthica a happening is an Action
(volitional) or an Event (non-volitional), and a fluent is a State. The Step-3 temporal
extraction now names, per happening, the States it brings into / takes out of holding:

  proeth:initiates  [ "Public Safety Risk", "Project Suspended" ]
  proeth:terminates [ ... ]

This applier WIRES THOSE IN. It reads the initiates / terminates label lists from each
temporal individual in temporary_rdf_storage, resolves each named State to the matching
case proeth-core:State individual, and materialises a first-class object property with
PROV-O provenance:

  Action/Event proeth-core:initiates  State
  Action/Event proeth-core:terminates State

This restores the fluent as the middle term between the temporal components and the
normative ones: an Action/Event initiates a State, and the State activatesObligation /
activatesConstraint (existing core State edges). It generalises the State-side
activatedByEvent / terminatedByEvent (Event-only) to both happening kinds in the canonical
happening -> State direction.

Structurally identical to state_affects_edges.py / participant_edges.py: embedding
shortlist over the candidate pool (here the case States) + one batched LLM multi-select per
edge-type, with an embedding-threshold fallback. The subject is the happening individual,
resolved by label within the Action/Event categories. Range is State (one of the nine
disjoint categories); the unified domain/range guard validates that subject reaches Action
or Event and object reaches State, dropping any mis-typed edge. Best-effort: failures are
logged and returned, never raised. A State label that matches no case State yields no edge.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

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
PROV = Namespace("http://www.w3.org/ns/prov#")

EMBED_MATCH_MIN = 0.50
SHORTLIST_FLOOR = 0.30
SHORTLIST_K = 8

# proeth-core property local name -> the temporal-row field carrying the State labels.
_FLUENT_SPECS = (
    ("initiates", ("proeth:initiates", "initiates")),
    ("terminates", ("proeth:terminates", "terminates")),
)


def _happenings_from_db(case_id: int) -> List[Dict[str, Any]]:
    """[{label, initiates:[...], terminates:[...]}] for each Step-3 temporal individual
    (Action or Event) that names at least one initiated or terminated State. Read from the
    temporal_dynamics_enhanced rows, whose rdf_json_ld stores the JSON-LD entity directly
    (proeth: keys at top level, not under a 'properties' wrapper like pass 1/2)."""
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    rows = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type="temporal_dynamics_enhanced", storage_type="individual"
    ).all()
    out = []
    for r in rows:
        rdf = r.rdf_json_ld or {}
        at_type = rdf.get("@type", "") or ""
        if "Action" not in at_type and "Event" not in at_type:
            continue  # skip causal_chains / allen_relations / timeline

        def _labels(keys):
            for k in keys:
                v = rdf.get(k)
                if v:
                    vals = v if isinstance(v, list) else [v]
                    return [str(x).strip() for x in vals if str(x).strip()]
            return []

        initiates = _labels(("proeth:initiates", "initiates"))
        terminates = _labels(("proeth:terminates", "terminates"))
        if initiates or terminates:
            out.append({
                "label": r.entity_label or rdf.get("rdfs:label", ""),
                "initiates": initiates,
                "terminates": terminates,
            })
    return out


def _build_fluent_prompt(prop: str):
    verb = "INITIATES (brings into holding)" if prop == "initiates" else "TERMINATES (ends)"

    def builder(items: List[Dict[str, Any]]) -> str:
        blocks = []
        for it in items:
            cands = "; ".join(
                f"{i + 1}) {lbl[:90]}" for i, (iri, lbl, sim) in enumerate(it["shortlist"])
            )
            blocks.append(
                f"[{it['id']}] happening: \"{(it.get('subj_label') or '')[:120]}\"\n"
                f"  states it {prop}: \"{(it['desc'] or '')[:220]}\"\n"
                f"  candidate states: {cands}"
            )
        return (
            f"Each REQUEST gives a happening (an action or event) in an engineering-ethics "
            f"case and the STATES (fluents) text saying which conditions it {verb}, plus the "
            "candidate STATES in that case.\n"
            f"For each request, choose ALL candidate states that the happening {verb}. The "
            "text may name several states, one, or none.\n"
            "Choose NONE (an empty list) when a named condition does not correspond to any "
            "listed case state (the state was not separately extracted, or the text names an "
            "obligation/constraint rather than a state).\n\n"
            "REQUESTS:\n" + "\n\n".join(blocks) +
            "\n\nOUTPUT strict JSON only, one entry per request id, each value a JSON array "
            "of the chosen candidate numbers (use [] for none): {\"<id>\": [<n>, ...], ...}"
        )
    return builder


def _emit_prov(g: Graph, case_id: int, prop: str, subj, obj, desc: str) -> None:
    case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")
    prov_iri = case_ns["fluent_edge_provenance_" + _safe_frag(subj) + "_" + prop + "_" + _safe_frag(obj)]
    if (prov_iri, RDF.type, PROV.Derivation) in g:
        return
    g.add((prov_iri, RDF.type, PROV.Derivation))
    g.add((prov_iri, PROV.wasDerivedFrom, subj))
    g.add((prov_iri, PROV.wasDerivedFrom, obj))
    g.add((prov_iri, RDFS.label, Literal(f"Fluent edge ({prop})")))
    if desc:
        g.add((prov_iri, PROV.value, Literal(str(desc))))
    g.add((prov_iri, RDFS.comment, Literal(
        f"property={prop}; happening's {prop} state text resolved to the case State(s) by "
        "embedding shortlist + LLM multi-select (Event Calculus fluent transition)")))


def apply_fluent_edges(case_id: int, ttl_path, write_back: bool = True,
                       threshold: float = EMBED_MATCH_MIN, use_llm: bool = True,
                       llm_client=None, model=None) -> Dict[str, Any]:
    """Materialize Action/Event -> State (initiates / terminates) edges on a committed case
    TTL. Reads each Step-3 happening's initiates / terminates State labels from
    temporary_rdf_storage, resolves them to the case proeth-core:State individuals
    (embedding shortlist + batched LLM multi-select per property; embedding-threshold
    fallback), and adds the edges + provenance. Returns per-property counts."""
    ttl_path = Path(ttl_path)
    res: Dict[str, Any] = {"case_id": case_id, "status": "ok", "total": 0}
    try:
        happenings = _happenings_from_db(case_id)
    except Exception as e:
        logger.warning("fluent_edges: temp_rdf read failed for case %s: %s", case_id, e)
        return {"case_id": case_id, "status": "no_db", "error": str(e)}
    if not happenings:
        return {"case_id": case_id, "status": "no_fluent_transitions"}

    g = Graph()
    g.parse(str(ttl_path), format="turtle")
    svc = _embedding_service()

    # Object pool: the case States (fluents). Match text is label + a couple narrative fields.
    state_pool = _candidate_pool(g, svc, "State", ["stateClass", "caseContext"])
    if not state_pool:
        return {"case_id": case_id, "status": "no_states"}

    # Subject map: happening individuals (Action or Event) by normalized label.
    happening_iris: Dict[str, URIRef] = {}
    for cat in ("Action", "Event"):
        for ind in _individuals_in_category(g, cat):
            happening_iris.setdefault(_norm(_label(g, ind)), ind)

    for prop, _fields in _FLUENT_SPECS:
        items: List[Dict[str, Any]] = []
        next_id = 1
        unresolved = 0
        for h in happenings:
            labels = h.get(prop) or []
            if not labels:
                continue
            subj = happening_iris.get(_norm(h["label"]))
            if subj is None:
                logger.info("fluent_edges[%s]: happening %r not in committed graph; skipped",
                            prop, (h["label"] or "")[:80])
                continue
            desc = "; ".join(labels)
            sl = _shortlist(svc, desc, state_pool, SHORTLIST_FLOOR, SHORTLIST_K)
            if not sl:
                unresolved += 1
                logger.info("fluent_edges[%s]: no State above floor %.2f for %r",
                            prop, SHORTLIST_FLOOR, desc[:80])
                continue
            items.append({"id": next_id, "subj": subj, "desc": desc,
                          "subj_label": h["label"], "shortlist": sl})
            next_id += 1

        selections = _llm_select_multi(
            items, client=llm_client, model=model, prompt_builder=_build_fluent_prompt(prop)
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
                if (subj, CORE[prop], tgt) in g:
                    continue
                g.add((subj, CORE[prop], tgt))
                _emit_prov(g, case_id, prop, subj, tgt, desc)
                edges += 1
        res[prop] = {"edges": edges, "resolver": resolver, "unresolved": unresolved}

    total = sum(v.get("edges", 0) for v in res.values() if isinstance(v, dict))
    res["total"] = total
    if write_back and total:
        g.serialize(destination=str(ttl_path), format="turtle")
    return res
