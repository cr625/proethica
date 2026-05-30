"""Resource-anchored edge materialization (DB-driven, embedding-resolved).

The resource extractor produces, per resource individual, a free-text `used_by`
field naming who used the resource in the case, e.g.

  "Engineer B"                     -> one actor
  "Engineer B and Engineer A"      -> two actors
  "Engineer B, Engineer A, Owner"  -> three actors
  "NSPE Board of Ethical Review"   -> an institution / analyst, not a case actor
  "Clients and engineers in ..."   -> a generic class, not a specific actor

Until now this field was committed only as an opaque literal (proeth:usedby, the
name lowercased by the commit-time _camelCase bug) and consumed by nothing. This
applier WIRES IT IN. It reads `used_by` from temporary_rdf_storage, resolves each
named actor to the matching case proeth-core:Agent individual, and materializes a
first-class object property with PROV-O provenance:

  Resource proeth-core:availableTo Agent

(availableTo was already declared in proethica-core but unused; its range was
broadened Role -> Agent on 2026-05-30 so it targets the actor, consistent with the
Agent model where hasRole / hasCapability / performsAction are all Agent-anchored.)

Resolution mirrors state_edges.py: an embedding shortlist (cheap pre-filter over
the case Agents) followed by one batched LLM confirm/select per case, with an
embedding-threshold fallback when the LLM is unavailable. The one difference is
that a single `used_by` value can name SEVERAL actors, so the LLM is asked to
select ALL matching candidates (multi-select), not one. Institutional / analyst /
generic users have no matching Agent and correctly yield no edge.

Best-effort, like the other appliers: failures are logged and returned, never
raised, so edge materialization can never fail a commit. Unresolved descriptions
are logged with their best similarity (no silent drops).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef

# Reuse the stable embedding/graph primitives from the state-edge applier (the
# established template for embedding-resolved appliers) instead of duplicating
# them. Only the resource-specific logic (Agent pool, used_by read, multi-select
# LLM, provenance, the apply driver) lives here.
from app.services.extraction.state_edges import (
    _embed,
    _embedding_service,
    _individuals_in_category,
    _label,
    _norm,
    _safe_frag,
    _shortlist,
)

logger = logging.getLogger(__name__)

CORE = Namespace("http://proethica.org/ontology/core#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
PROV = Namespace("http://www.w3.org/ns/prov#")

AGENT_CLASS = CORE.Agent
AVAILABLE_TO = "availableTo"  # proeth-core property local name

# Resolution thresholds. The candidate pool is the case's Agents (typically 2-5),
# and `used_by` values are bare actor names, so the embedding signal is strong and
# clean. The shortlist floor is kept low so EVERY case Agent reaches the LLM (it
# must see "Owner" as a candidate to include it for "Engineer B, Engineer A,
# Owner"); the LLM is the precision layer. The embedding-only fallback selects all
# shortlisted Agents at or above EMBED_MATCH_MIN.
EMBED_MATCH_MIN = 0.50
SHORTLIST_FLOOR = 0.30
SHORTLIST_K = 8


# --- candidate pool: the case Agents ---------------------------------------

def _agent_pool(g: Graph, svc) -> List:
    """[(agent_iri, text, embedding)] for every proeth-core:Agent individual, using
    its label plus the labels of the Role facets it bears as matchable text. The
    facet labels let a descriptive `used_by` ("the peer reviewer") still resolve."""
    pool = []
    for ind in g.subjects(RDF.type, AGENT_CLASS):
        text = _label(g, ind)
        for facet in g.objects(ind, CORE.hasRole):
            fl = _label(g, facet)
            if fl:
                text += " . " + fl
        ev = _embed(svc, text)
        if ev:
            pool.append((ind, text, ev))
    return pool


# --- used_by read from temporary_rdf_storage (DB) --------------------------

def _resource_usage_from_db(case_id: int) -> List[Dict[str, str]]:
    """[{label, used_by, definition}] for resource individuals carrying a non-empty
    `used_by`, read from temporary_rdf_storage. The field is committed only as an
    opaque (bug-lowercased) literal, so the clean camelCase value is read here from
    the extraction rows rather than parsed back out of the TTL."""
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    def _props(row):
        return ((row.rdf_json_ld or {}).get("properties") or {})

    def _str(props, *keys):
        for k in keys:
            v = props.get(k)
            if v:
                if isinstance(v, list):
                    return str(v[0]) if v else ""
                return str(v)
        return ""

    rows = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type="resources", storage_type="individual"
    ).all()
    out = []
    for r in rows:
        p = _props(r)
        used_by = _str(p, "usedBy", "used_by")
        if used_by.strip():
            out.append({
                "label": r.entity_label or "",
                "used_by": used_by,
                "definition": r.entity_definition or "",
            })
    return out


# --- batched multi-select LLM (the hybrid precision layer) ------------------

def _build_multi_select_prompt(items: List[Dict[str, Any]]) -> str:
    blocks = []
    for it in items:
        cands = "; ".join(
            f"{i + 1}) {lbl[:90]}" for i, (iri, lbl, sim) in enumerate(it["shortlist"])
        )
        blocks.append(
            f"[{it['id']}] resource: \"{(it.get('resource_label') or '')[:120]}\"\n"
            f"  used_by text: \"{(it['desc'] or '')[:220]}\"\n"
            f"  candidate agents: {cands}"
        )
    return (
        "Each REQUEST gives the `used_by` text of a professional resource (a code, "
        "precedent, standard, or agreement) in an engineering-ethics case, plus the "
        "candidate AGENTS in that case.\n"
        "For each request, choose ALL candidate agents that the text identifies as "
        "USERS of the resource (the parties who rely on, invoke, or are governed by "
        "it). A `used_by` text may name several agents, one, or none.\n"
        "Choose NONE (an empty list) when the user is an institution or analyst NOT "
        "among the candidates (e.g. 'NSPE Board of Ethical Review'), when the text is "
        "a generic class rather than a specific case actor (e.g. 'clients and "
        "engineers in design-build contexts'), or when an agent is merely mentioned "
        "as the SUBJECT being analyzed rather than a user of the resource.\n\n"
        "REQUESTS:\n" + "\n\n".join(blocks) +
        "\n\nOUTPUT strict JSON only, one entry per request id, each value a JSON "
        "array of the chosen candidate numbers (use [] for none): "
        "{\"<id>\": [<n>, ...], ...}"
    )


def _llm_select_multi(items: List[Dict[str, Any]], client=None, model=None):
    """Map each item id -> list of chosen Agent IRIs via one LLM call. Returns the
    selection dict, or None if the LLM is unavailable / the call fails (the caller
    then falls back to the embedding threshold)."""
    if not items:
        return {}
    try:
        if client is None:
            from app.utils.llm_utils import get_llm_client
            client = get_llm_client()
        if model is None:
            # Constrained pick-from-shortlist task: the fast tier (Haiku) fits; a
            # heavier model adds nothing over a small multi-select prompt.
            from model_config import ModelConfig
            model = ModelConfig.get_claude_model("fast")
        if not (hasattr(client, "messages") and hasattr(client.messages, "stream")):
            logger.warning("resource_edges: no Anthropic streaming client; embedding fallback")
            return None
        prompt = _build_multi_select_prompt(items)
        chunks: List[str] = []
        with client.messages.stream(
            model=model, max_tokens=4096, temperature=0.0,
            system=("You select all matching agents for each request, distinguishing "
                    "users of a resource from institutions, generic classes, and "
                    "agents merely analyzed. Output strict JSON only."),
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for t in stream.text_stream:
                chunks.append(t)
        from app.utils.llm_utils import extract_json_from_response
        data = extract_json_from_response("".join(chunks))
        if not isinstance(data, dict):
            return None
        by_id = {str(it["id"]): it for it in items}
        out: Dict[str, List[URIRef]] = {}
        for k, v in data.items():
            it = by_id.get(str(k))
            if it is None:
                continue
            chosen: List[URIRef] = []
            # Accept a list of numbers; tolerate a bare number or "none"/"".
            if isinstance(v, str):
                v = [] if v.strip().lower() in ("none", "", "0") else [v]
            if not isinstance(v, list):
                v = [v]
            for n in v:
                try:
                    idx = int(n)
                except (TypeError, ValueError):
                    continue
                if 1 <= idx <= len(it["shortlist"]):
                    iri = it["shortlist"][idx - 1][0]
                    if iri not in chosen:
                        chosen.append(iri)
            out[str(k)] = chosen
        return out
    except Exception as e:
        logger.warning("resource_edges: LLM select failed (%s); embedding fallback", e)
        return None


# --- provenance (idempotent, mirrors state/defeasibility prov) --------------

def _emit_prov(g: Graph, case_id: int, subj, obj, desc: str) -> None:
    case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")
    prov_iri = case_ns["resource_edge_provenance_" + _safe_frag(subj) + "_" + AVAILABLE_TO + "_" + _safe_frag(obj)]
    if (prov_iri, RDF.type, PROV.Derivation) in g:
        return
    g.add((prov_iri, RDF.type, PROV.Derivation))
    g.add((prov_iri, PROV.wasDerivedFrom, subj))
    g.add((prov_iri, PROV.wasDerivedFrom, obj))
    g.add((prov_iri, RDFS.label, Literal(f"Resource edge ({AVAILABLE_TO})")))
    if desc:
        g.add((prov_iri, PROV.value, Literal(str(desc))))
    g.add((prov_iri, RDFS.comment, Literal(
        "property=availableTo; resource used_by text resolved to the case Agent(s) "
        "by embedding shortlist + LLM multi-select")))


# --- main applier ----------------------------------------------------------

def apply_resource_edges(case_id: int, ttl_path, write_back: bool = True,
                         threshold: float = EMBED_MATCH_MIN, use_llm: bool = True,
                         llm_client=None, model=None) -> Dict[str, Any]:
    """Materialize Resource -> Agent (availableTo) edges on a just-written case TTL.

    Reads each resource individual's `used_by` from temporary_rdf_storage, resolves
    the named actor(s) to the case's proeth-core:Agent individuals (embedding
    shortlist + one batched LLM multi-select per case; embedding-threshold fallback
    when the LLM is unavailable or use_llm=False), and adds availableTo edges +
    provenance. Returns the edge count, the resolver used, and the number of
    unresolved descriptions (logged individually)."""
    ttl_path = Path(ttl_path)
    res: Dict[str, Any] = {
        "case_id": case_id, "status": "ok", "resolver": None,
        "availableTo": 0, "unresolved": 0,
    }
    try:
        resources = _resource_usage_from_db(case_id)
    except Exception as e:
        logger.warning("resource_edges: could not read temp_rdf for case %s: %s", case_id, e)
        return {"case_id": case_id, "status": "no_db", "error": str(e)}
    if not resources:
        return {"case_id": case_id, "status": "no_resource_usage"}

    g = Graph()
    g.parse(str(ttl_path), format="turtle")
    svc = _embedding_service()

    pool = _agent_pool(g, svc)
    if not pool:
        return {"case_id": case_id, "status": "no_agents"}

    # Map each resource individual (by normalized label) to its committed IRI.
    resource_iris: Dict[str, URIRef] = {}
    for ind in _individuals_in_category(g, "Resource"):
        resource_iris.setdefault(_norm(_label(g, ind)), ind)

    # Pass A: build resolution items (used_by text + embedding shortlist of Agents).
    items: List[Dict[str, Any]] = []
    next_id = 1
    for r in resources:
        subj = resource_iris.get(_norm(r["label"]))
        if subj is None:
            logger.info("resource_edges: resource %r not in committed graph; skipped", r["label"][:80])
            continue
        desc = r["used_by"]
        sl = _shortlist(svc, desc, pool, SHORTLIST_FLOOR, SHORTLIST_K)
        if not sl:
            res["unresolved"] += 1
            logger.info("resource_edges: used_by has no Agent above floor %.2f: %r",
                        SHORTLIST_FLOOR, desc[:80])
            continue
        items.append({
            "id": next_id, "subj": subj, "desc": desc,
            "resource_label": r["label"], "shortlist": sl,
        })
        next_id += 1

    # Pass B: batched LLM multi-select; embedding-threshold fallback otherwise.
    selections = _llm_select_multi(items, client=llm_client, model=model) if use_llm else None
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
            logger.info("resource_edges: used_by unresolved (resolver=%s): %r",
                        res["resolver"], desc[:80])
            continue
        for tgt in targets:
            if (subj, CORE[AVAILABLE_TO], tgt) in g:
                continue
            g.add((subj, CORE[AVAILABLE_TO], tgt))
            _emit_prov(g, case_id, subj, tgt, desc)
            res["availableTo"] += 1

    if write_back and res["availableTo"]:
        g.serialize(destination=str(ttl_path), format="turtle")
    return res
