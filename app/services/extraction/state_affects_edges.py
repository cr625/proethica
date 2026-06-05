"""State-affects edge materialization (DB-driven, embedding-resolved).

The state extractor produces, per state individual, an `affectedParties` list naming
the actors a state bears on, e.g.

  ["Owner", "Engineer A", "Engineer B", "Future occupants and public"]

Until now this was committed only as opaque literals (proeth:affectedparties, the
names lowercased by the commit-time _camelCase bug) and consumed by nothing. This
applier WIRES IT IN: it reads `affectedParties` from temporary_rdf_storage, resolves
each named party to the matching case proeth-core:Agent individual, and materializes
a first-class object property with PROV-O provenance:

  State proeth-core:affects Agent

Structurally this mirrors resource_edges.py (the Resource availableTo applier): a
single state can affect several actors, so resolution is an embedding shortlist over
the case Agents followed by one batched LLM multi-select, with an embedding-threshold
fallback. A generic party ("future occupants and public") matches no Agent and
correctly yields no edge. Best-effort: failures are logged and returned, never raised.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from rdflib import Graph, Namespace, URIRef

# Reuse the embedding/graph primitives from state_edges and the Agent pool +
# multi-select LLM driver from resource_edges (the established multi-select
# Agent-resolution template). Only the affectedParties-specific read and the
# request wording live here.
from app.services.extraction.state_edges import (
    _embedding_service,
    _individuals_in_category,
    _label,
    _norm,
    _shortlist,
    emit_edge_prov,
)
from app.services.extraction.resource_edges import _agent_pool, _llm_select_multi

logger = logging.getLogger(__name__)

CORE = Namespace("http://proethica.org/ontology/core#")
PROV = Namespace("http://www.w3.org/ns/prov#")

AFFECTS = "affects"  # proeth-core property local name

# Same regime as resource_edges: the candidate pool is the case Agents (few, clean),
# party names are short, so the shortlist floor is low (every Agent reaches the LLM)
# and the LLM is the precision layer; the embedding-only fallback keeps Agents at or
# above EMBED_MATCH_MIN.
EMBED_MATCH_MIN = 0.50
SHORTLIST_FLOOR = 0.30
SHORTLIST_K = 8


def _affected_from_db(case_id: int) -> List[Dict[str, Any]]:
    """[{label, parties:[...], desc}] for state individuals carrying a non-empty
    affectedParties, read from temporary_rdf_storage. The clean camelCase list is
    read here from the extraction rows rather than parsed back out of the TTL."""
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    def _props(row):
        return ((row.rdf_json_ld or {}).get("properties") or {})

    rows = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type="states", storage_type="individual"
    ).all()
    out = []
    for r in rows:
        p = _props(r)
        raw = p.get("affectedParties") or p.get("affected_parties") or []
        parties = [str(x).strip() for x in (raw if isinstance(raw, list) else [raw]) if str(x).strip()]
        if parties:
            out.append({
                "label": r.entity_label or "",
                "parties": parties,
                "desc": "; ".join(parties),
            })
    return out


def _build_affects_prompt(items: List[Dict[str, Any]]) -> str:
    blocks = []
    for it in items:
        cands = "; ".join(
            f"{i + 1}) {lbl[:90]}" for i, (iri, lbl, sim) in enumerate(it["shortlist"])
        )
        blocks.append(
            f"[{it['id']}] state: \"{(it.get('state_label') or '')[:120]}\"\n"
            f"  affected parties text: \"{(it['desc'] or '')[:220]}\"\n"
            f"  candidate agents: {cands}"
        )
    return (
        "Each REQUEST gives the `affected parties` of a STATE (a condition or "
        "situation) in an engineering-ethics case, plus the candidate AGENTS in that "
        "case.\n"
        "For each request, choose ALL candidate agents that the affected-parties text "
        "identifies as parties the state bears on (whose situation the state changes). "
        "A text may name several agents, one, or none.\n"
        "Choose NONE (an empty list) when a named party is a generic group not among "
        "the candidates (e.g. 'future occupants and public', 'society'), an institution "
        "not among the candidates, or otherwise not one of the listed case agents.\n\n"
        "REQUESTS:\n" + "\n\n".join(blocks) +
        "\n\nOUTPUT strict JSON only, one entry per request id, each value a JSON "
        "array of the chosen candidate numbers (use [] for none): "
        "{\"<id>\": [<n>, ...], ...}"
    )


def _emit_prov(g: Graph, case_id: int, subj, obj, desc: str) -> None:
    emit_edge_prov(g, case_id, "state_affects_provenance_", AFFECTS, subj, obj, desc,
                   f"State edge ({AFFECTS})",
                   "property=affects; state affectedParties text resolved to the case Agent(s) "
                   "by embedding shortlist + LLM multi-select")


def apply_state_affects_edges(case_id: int, ttl_path, write_back: bool = True,
                              threshold: float = EMBED_MATCH_MIN, use_llm: bool = True,
                              llm_client=None, model=None) -> Dict[str, Any]:
    """Materialize State -> Agent (affects) edges on a just-written case TTL.

    Reads each state individual's affectedParties from temporary_rdf_storage, resolves
    the named parties to the case's proeth-core:Agent individuals (embedding shortlist
    + one batched LLM multi-select per case; embedding-threshold fallback when the LLM
    is unavailable or use_llm=False), and adds affects edges + provenance."""
    ttl_path = Path(ttl_path)
    res: Dict[str, Any] = {
        "case_id": case_id, "status": "ok", "resolver": None,
        "affects": 0, "unresolved": 0,
    }
    try:
        states = _affected_from_db(case_id)
    except Exception as e:
        logger.warning("state_affects_edges: could not read temp_rdf for case %s: %s", case_id, e)
        return {"case_id": case_id, "status": "no_db", "error": str(e)}
    if not states:
        return {"case_id": case_id, "status": "no_affected_parties"}

    g = Graph()
    g.parse(str(ttl_path), format="turtle")
    svc = _embedding_service()

    pool = _agent_pool(g, svc)
    if not pool:
        return {"case_id": case_id, "status": "no_agents"}

    state_iris: Dict[str, URIRef] = {}
    for ind in _individuals_in_category(g, "State"):
        state_iris.setdefault(_norm(_label(g, ind)), ind)

    # Pass A: build resolution items (affected-parties text + Agent shortlist).
    items: List[Dict[str, Any]] = []
    next_id = 1
    for s in states:
        subj = state_iris.get(_norm(s["label"]))
        if subj is None:
            logger.info("state_affects_edges: state %r not in committed graph; skipped", s["label"][:80])
            continue
        desc = s["desc"]
        sl = _shortlist(svc, desc, pool, SHORTLIST_FLOOR, SHORTLIST_K)
        if not sl:
            res["unresolved"] += 1
            logger.info("state_affects_edges: affectedParties has no Agent above floor %.2f: %r",
                        SHORTLIST_FLOOR, desc[:80])
            continue
        items.append({
            "id": next_id, "subj": subj, "desc": desc,
            "state_label": s["label"], "shortlist": sl,
        })
        next_id += 1

    # Pass B: batched LLM multi-select; embedding-threshold fallback otherwise.
    selections = _llm_select_multi(
        items, client=llm_client, model=model, prompt_builder=_build_affects_prompt
    ) if use_llm else None
    res["resolver"] = "llm" if selections is not None else "embedding"

    # Pass C: emit the resolved edges + provenance.
    for it in items:
        subj, desc, sl = it["subj"], it["desc"], it["shortlist"]
        if selections is not None:
            targets = selections.get(str(it["id"])) or []
        else:
            targets = [iri for iri, _lbl, sim in sl if sim >= threshold]
        if not targets:
            res["unresolved"] += 1
            logger.info("state_affects_edges: affectedParties unresolved (resolver=%s): %r",
                        res["resolver"], desc[:80])
            continue
        for tgt in targets:
            if (subj, CORE[AFFECTS], tgt) in g:
                continue
            g.add((subj, CORE[AFFECTS], tgt))
            _emit_prov(g, case_id, subj, tgt, desc)
            res["affects"] += 1

    if write_back and res["affects"]:
        g.serialize(destination=str(ttl_path), format="turtle")
    return res
