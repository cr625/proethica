"""Causal-chain edge materialization (DB-driven, embedding-resolved).

The Step-3 causal analysis (Stage 5) names, per CausalChain, the cause, the effect, and
the responsible agent(s) as free-text labels:

  proeth:cause             "Confidential Review Instruction"
  proeth:effect            "Peer Review Blocked"
  proeth:responsibleAgent  "Owner (primary); Engineer A (proximate); Engineer B (...)"

Those labels are the labels of the case Action/Event and Agent individuals, but until now
they persisted only as dangling literals (demoted to proeth:causeText / effectText /
responsibleAgentText once the properties became object properties), so the causal chain
was not wired into the graph. This applier WIRES IT IN: it reads each CausalChain row's
cause / effect / responsibleAgent labels from temporary_rdf_storage, resolves cause/effect
to the matching case Action or Event individual and responsibleAgent to the case Agent
individual(s), and materialises first-class edges with PROV-O provenance:

  CausalChain proeth:cause            Action|Event
  CausalChain proeth:effect           Action|Event
  CausalChain proeth:responsibleAgent Agent

This is a fidelity refinement, not a relocation: the causal chain is the canonical
irreducible-extraction content (the NESS analysis cannot be rebuilt from the graph), so it
stays in extraction; this links its endpoints into the graph so the chain is traversable.

Structurally identical to fluent_edges.py / obligation_edges.py: embedding shortlist over
the candidate pool + a batched LLM select per property. The subject is the CausalChain
individual resolved by normalized rdfs:label (its label is "cause -> effect"; the
committed URI derives from it). cause/effect resolve against the Action+Event pool (range
Action/Event, both disjoint categories -> the unified guard validates the object);
responsibleAgent resolves against the Agent pool (range Agent, outside the nine, range
clause skipped). CausalChain is a non-core domain, so the guard's domain clause is
empty-set and never drops on the subject. Best-effort: failures are logged, never raised.
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
from app.services.extraction.resource_edges import _agent_pool, _llm_select_multi

logger = logging.getLogger(__name__)

CORE = Namespace("http://proethica.org/ontology/core#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
PROV = Namespace("http://www.w3.org/ns/prov#")

EMBED_MATCH_MIN = 0.50
SHORTLIST_FLOOR = 0.30
SHORTLIST_K = 8

# (property local, pool key 'happening'|'agent', verb shown to the LLM)
_CAUSAL_SPECS = (
    ("cause", "happening", "is the CAUSE (the action or event that brings the chain about)"),
    ("effect", "happening", "is the EFFECT / outcome (the action or event the chain produces)"),
    ("responsibleAgent", "agent", "bear(s) responsibility for the chain"),
)


def _causal_from_db(case_id: int) -> List[Dict[str, Any]]:
    """[{label, cause, effect, responsibleAgent}] for each Step-3 CausalChain individual
    that names at least one of those fields. Read from temporary_rdf_storage; the temporal
    rows store proeth: keys at the top level of rdf_json_ld."""
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    rows = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type="temporal_dynamics_enhanced", storage_type="individual"
    ).all()
    out = []
    for r in rows:
        rdf = r.rdf_json_ld or {}
        if "CausalChain" not in (rdf.get("@type", "") or ""):
            continue

        def _val(key):
            v = rdf.get(f"proeth:{key}")
            if isinstance(v, list):
                return "; ".join(str(x).strip() for x in v if str(x).strip())
            return str(v).strip() if v not in (None, "") else ""

        rec = {
            "label": r.entity_label or rdf.get("rdfs:label", ""),
            "cause": _val("cause"),
            "effect": _val("effect"),
            "responsibleAgent": _val("responsibleAgent"),
        }
        if rec["cause"] or rec["effect"] or rec["responsibleAgent"]:
            out.append(rec)
    return out


def _build_causal_prompt(prop: str, verb: str):
    def builder(items: List[Dict[str, Any]]) -> str:
        blocks = []
        for it in items:
            cands = "; ".join(
                f"{i + 1}) {lbl[:90]}" for i, (iri, lbl, sim) in enumerate(it["shortlist"])
            )
            blocks.append(
                f"[{it['id']}] causal chain: \"{(it.get('subj_label') or '')[:120]}\"\n"
                f"  text naming what {verb}: \"{(it['desc'] or '')[:200]}\"\n"
                f"  candidates: {cands}"
            )
        return (
            f"Each REQUEST gives a causal chain in an engineering-ethics case and the text "
            f"naming what {verb}, plus the candidate individuals in that case.\n"
            "For cause/effect choose the ONE candidate that the text refers to; for the "
            "responsible agent choose ALL candidates the text names. Choose NONE (an empty "
            "list) when no candidate genuinely matches.\n\n"
            "REQUESTS:\n" + "\n\n".join(blocks) +
            "\n\nOUTPUT strict JSON only, one entry per request id, each value a JSON array "
            "of the chosen candidate numbers (use [] for none): {\"<id>\": [<n>, ...], ...}"
        )
    return builder


def _emit_prov(g: Graph, case_id: int, prop: str, subj, obj, desc: str) -> None:
    case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")
    prov_iri = case_ns["causal_edge_provenance_" + _safe_frag(subj) + "_" + prop + "_" + _safe_frag(obj)]
    if (prov_iri, RDF.type, PROV.Derivation) in g:
        return
    g.add((prov_iri, RDF.type, PROV.Derivation))
    g.add((prov_iri, PROV.wasDerivedFrom, subj))
    g.add((prov_iri, PROV.wasDerivedFrom, obj))
    g.add((prov_iri, RDFS.label, Literal(f"Causal edge ({prop})")))
    if desc:
        g.add((prov_iri, PROV.value, Literal(str(desc))))
    g.add((prov_iri, RDFS.comment, Literal(
        f"property={prop}; causal chain's {prop} text resolved to the case "
        "individual(s) by embedding shortlist + LLM select")))


def apply_causal_edges(case_id: int, ttl_path, write_back: bool = True,
                       threshold: float = EMBED_MATCH_MIN, use_llm: bool = True,
                       llm_client=None, model=None) -> Dict[str, Any]:
    """Materialize CausalChain -> Action/Event (cause/effect) and CausalChain -> Agent
    (responsibleAgent) edges on a committed case TTL. Reads each Step-3 CausalChain row's
    labels from temporary_rdf_storage and resolves them (embedding shortlist + batched LLM
    select; embedding-threshold fallback). Returns per-property counts."""
    ttl_path = Path(ttl_path)
    res: Dict[str, Any] = {"case_id": case_id, "status": "ok", "total": 0}
    try:
        chains = _causal_from_db(case_id)
    except Exception as e:
        logger.warning("causal_edges: temp_rdf read failed for case %s: %s", case_id, e)
        return {"case_id": case_id, "status": "no_db", "error": str(e)}
    if not chains:
        return {"case_id": case_id, "status": "no_causal_chains"}

    g = Graph()
    g.parse(str(ttl_path), format="turtle")
    svc = _embedding_service()

    # Subject map: CausalChain individuals by normalized label (typed proeth:CausalChain,
    # not via conceptCategory, so resolve by rdf:type).
    chain_iris: Dict[str, URIRef] = {}
    for ind in g.subjects(RDF.type, PROETH.CausalChain):
        chain_iris.setdefault(_norm(_label(g, ind)), ind)
    if not chain_iris:
        return {"case_id": case_id, "status": "no_committed_chains"}

    # Object pools: the case happenings (Action + Event) for cause/effect; the case Agents
    # for responsibleAgent. Built once.
    happening_pool = (
        _candidate_pool(g, svc, "Action", []) + _candidate_pool(g, svc, "Event", [])
    )
    agent_pool = _agent_pool(g, svc)

    for prop, pool_key, verb in _CAUSAL_SPECS:
        pool = happening_pool if pool_key == "happening" else agent_pool
        if not pool:
            res[prop] = {"edges": 0, "status": f"no_{pool_key}s"}
            continue

        items: List[Dict[str, Any]] = []
        next_id = 1
        unresolved = 0
        for c in chains:
            desc = c.get(prop) or ""
            if not desc:
                continue
            subj = chain_iris.get(_norm(c["label"]))
            if subj is None:
                logger.info("causal_edges[%s]: chain %r not in committed graph; skipped",
                            prop, (c["label"] or "")[:80])
                continue
            sl = _shortlist(svc, desc, pool, SHORTLIST_FLOOR, SHORTLIST_K)
            if not sl:
                unresolved += 1
                continue
            items.append({"id": next_id, "subj": subj, "desc": desc,
                          "subj_label": c["label"], "shortlist": sl})
            next_id += 1

        selections = _llm_select_multi(
            items, client=llm_client, model=model, prompt_builder=_build_causal_prompt(prop, verb)
        ) if use_llm else None

        edges = 0
        for it in items:
            subj, desc, sl = it["subj"], it["desc"], it["shortlist"]
            if selections is not None:
                targets = selections.get(str(it["id"])) or []
            else:
                targets = [iri for iri, _lbl, sim in sl if sim >= threshold]
            # cause/effect are single-valued: keep only the first selected target.
            if prop in ("cause", "effect") and targets:
                targets = targets[:1]
            if not targets:
                unresolved += 1
                continue
            for tgt in targets:
                if (subj, PROETH[prop], tgt) in g:
                    continue
                g.add((subj, PROETH[prop], tgt))
                _emit_prov(g, case_id, prop, subj, tgt, desc)
                edges += 1
        res[prop] = {"edges": edges, "resolver": "llm" if selections is not None else "embedding",
                     "unresolved": unresolved}

    total = sum(v.get("edges", 0) for v in res.values() if isinstance(v, dict))
    res["total"] = total
    if write_back and total:
        g.serialize(destination=str(ttl_path), format="turtle")
    return res


def _events_causedby_from_db(case_id: int) -> List[Dict[str, Any]]:
    """[{label, caused_by}] for each Step-3 Event individual that names a causing action.
    caused_by is the converter's legacy IRI (http://proethica.org/cases/<id>#Action_<frag>)."""
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    rows = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type="temporal_dynamics_enhanced", storage_type="individual"
    ).all()
    out = []
    for r in rows:
        rdf = r.rdf_json_ld or {}
        if "Event" not in (rdf.get("@type", "") or ""):
            continue
        cba = rdf.get("proeth:causedByAction")
        if isinstance(cba, list):
            cba = cba[0] if cba else None
        if cba:
            out.append({"label": r.entity_label or rdf.get("rdfs:label", ""), "caused_by": str(cba)})
    return out


def apply_event_cause_edges(case_id: int, ttl_path, write_back: bool = True) -> Dict[str, Any]:
    """Materialize Event proeth:causedByAction Action edges on a committed case TTL.

    The converter emits causedByAction as a legacy-scheme IRI (#Action_<frag>) that the
    commit serializer skips, so the durable graph lost the event->causing-action link
    (which is NOT always covered by a CausalChain). This resolves it deterministically:
    the legacy fragment minus the Action_ prefix is the committed Action's local name, so
    the edge target is case_ns + that fragment (with a normalized-label fallback). No LLM
    needed -- it is a precise reference, not a fuzzy description. proeth:causedByAction is a
    declared object property (domain Event, range Action); the unified guard validates the
    Action endpoint (registered in ALL_EDGE_RANGE). Best-effort; never raises."""
    ttl_path = Path(ttl_path)
    res: Dict[str, Any] = {"case_id": case_id, "status": "ok", "edges": 0, "unresolved": 0}
    try:
        events = _events_causedby_from_db(case_id)
    except Exception as e:
        logger.warning("event_cause_edges: temp_rdf read failed for case %s: %s", case_id, e)
        return {"case_id": case_id, "status": "no_db", "error": str(e)}
    if not events:
        return {"case_id": case_id, "status": "no_caused_by"}

    g = Graph()
    g.parse(str(ttl_path), format="turtle")

    # Subject map: Event individuals by normalized label. Target maps: committed Action
    # individuals by local-name (exact remap) and by normalized label (fallback).
    event_iris: Dict[str, URIRef] = {}
    for ind in _individuals_in_category(g, "Event"):
        event_iris.setdefault(_norm(_label(g, ind)), ind)
    action_by_local: Dict[str, URIRef] = {}
    action_by_norm: Dict[str, URIRef] = {}
    case_ns = None
    for ind in _individuals_in_category(g, "Action"):
        s = str(ind)
        action_by_local[s.split("#")[-1]] = ind
        action_by_norm.setdefault(_norm(_label(g, ind)), ind)
        if case_ns is None and "#" in s:
            case_ns = s.rsplit("#", 1)[0] + "#"
    if not event_iris or not action_by_local:
        return {"case_id": case_id, "status": "no_events_or_actions"}

    edges = unresolved = 0
    for ev in events:
        subj = event_iris.get(_norm(ev["label"]))
        if subj is None:
            continue
        frag = ev["caused_by"].split("#")[-1]
        if frag.startswith("Action_"):
            frag = frag[len("Action_"):]
        tgt = action_by_local.get(frag) or action_by_norm.get(_norm(frag.replace("_", " ")))
        if tgt is None:
            unresolved += 1
            logger.info("event_cause_edges: caused-by action %r not committed for event %r",
                        frag, (ev["label"] or "")[:80])
            continue
        if (subj, PROETH.causedByAction, tgt) in g:
            continue
        g.add((subj, PROETH.causedByAction, tgt))
        _emit_prov(g, case_id, "causedByAction", subj, tgt, ev["caused_by"])
        edges += 1

    res["edges"], res["unresolved"] = edges, unresolved
    if write_back and edges:
        g.serialize(destination=str(ttl_path), format="turtle")
    return res
