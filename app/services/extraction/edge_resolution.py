"""Shared resolver primitives for the embedding-resolved edge appliers.

A committed case TTL carries individuals + their subClassOf-core chains but no
relational layer. The "Architecture-B" edge appliers (state / resource /
state-affects / participant / fluent / obligation / temporal-relation / causal)
all follow one template: read a relationship-label field from
``temporary_rdf_storage`` -> build a candidate pool of individuals in a target
category -> shortlist by embedding cosine -> confirm/select via one batched LLM
call (with an embedding-threshold fallback) -> emit the edge triple + a PROV-O
``prov:Derivation`` node.

This module is the SINGLE HOME for the primitives that template shares. The
helpers were previously split across ``state_edges`` (embedding + graph + the
single-select LLM + the provenance emitter/remover) and ``resource_edges`` (the
Agent pool + the multi-select LLM). They are MOVED here verbatim -- the resolver
logic is unchanged; this only unifies and de-duplicates the home. The original
modules now re-export from here, so every historical import surface
(``state_edges._embed``, ``resource_edges._agent_pool``, ``time_anchor._safe_frag``,
and the per-applier unit tests) keeps resolving to the same callables.

The domain/range guard (``rpo_edges.drop_domain_range_violations`` /
``ALL_EDGE_RANGE``) deliberately stays in ``rpo_edges``; it is referenced, not
duplicated, here.
"""
from __future__ import annotations

import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef

logger = logging.getLogger(__name__)

CORE = Namespace("http://proethica.org/ontology/core#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
PROV = Namespace("http://www.w3.org/ns/prov#")

AGENT_CLASS = CORE.Agent

# The case-scoped NSPE Board Agent minted by edge_spec's Board-pattern fallback
# (invokedBy / citedByAgent). It is deliberately EXCLUDED from _agent_pool so it can
# never be matched as a used_by/availableTo reliance actor or by any other
# embedding/LLM actor resolution; only the deterministic Board-pattern fallback in
# edge_spec.materialize_edge_family reaches it.
BOARD_AGENT_LOCALNAME = "Agent_NSPE_Board"


# --- embedding helpers (moved verbatim from state_edges) -------------------

def _embedding_service():
    from app.services.embedding.embedding_service import EmbeddingService
    return EmbeddingService.get_instance()


def _embed(svc, text: str) -> Optional[List[float]]:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return svc.get_embedding(text)
    except Exception as e:  # never raise out of an applier
        logger.warning("edge_resolution: embedding failed for %r: %s", text[:60], e)
        return None


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().replace("_", " ").replace("-", " ")).strip()


# --- graph helpers (mirror rpo_edges / defeasibility_pipeline) -------------

def _individuals_in_category(g: Graph, category: str) -> List[URIRef]:
    # Read the materialized direct rdf:type proeth-core:<Category> (CMT-1): the
    # commit asserts it on every individual, so the category is one hop away. The
    # retired proeth:conceptCategory literal is no longer consulted.
    return list(g.subjects(RDF.type, CORE[category]))


def _label(g: Graph, ind: URIRef) -> str:
    for o in g.objects(ind, RDFS.label):
        return str(o)
    return str(ind).split("#")[-1]


def _lit(g: Graph, ind: URIRef, name: str) -> str:
    for o in g.objects(ind, PROETH[name]):
        return str(o)
    return ""


def _candidate_pool(g: Graph, svc, category: str, extra_fields: List[str]):
    """[(iri, text, embedding)] for every individual of a core category, using its
    label plus a few narrative fields as the matchable text."""
    pool = []
    for ind in _individuals_in_category(g, category):
        text = _label(g, ind)
        for f in extra_fields:
            v = _lit(g, ind, f)
            if v:
                text += " . " + v
        ev = _embed(svc, text)
        if ev:
            pool.append((ind, text, ev))
    return pool


def _agent_pool(g: Graph, svc) -> List:
    """[(agent_iri, text, embedding)] for every proeth-core:Agent individual, using
    its label plus the labels of the Role facets it bears as matchable text. The
    facet labels let a descriptive `used_by` ("the peer reviewer") still resolve."""
    pool = []
    for ind in g.subjects(RDF.type, AGENT_CLASS):
        if str(ind).rsplit("#", 1)[-1] == BOARD_AGENT_LOCALNAME:
            # Materialized Board Agent: reachable only via the deterministic
            # Board-pattern fallback, never as an embedding/LLM candidate.
            continue
        text = _label(g, ind)
        for facet in g.objects(ind, CORE.hasRole):
            fl = _label(g, facet)
            if fl:
                text += " . " + fl
        ev = _embed(svc, text)
        if ev:
            pool.append((ind, text, ev))
    return pool


def _resolve(svc, description: str, pool, threshold: float) -> Tuple[Optional[URIRef], float]:
    qv = _embed(svc, description)
    if not qv or not pool:
        return None, 0.0
    best, best_sim = None, -1.0
    for iri, _t, ev in pool:
        sim = _cosine(qv, ev)
        if sim > best_sim:
            best, best_sim = iri, sim
    if best is not None and best_sim >= threshold:
        return best, best_sim
    return None, best_sim


def _shortlist(svc, description: str, pool, floor: float, k: int):
    """Top-k (iri, label, sim) candidates above `floor`, best first. The cheap
    embedding pre-filter that keeps the LLM confirm prompt small."""
    qv = _embed(svc, description)
    if not qv or not pool:
        return []
    scored = sorted(((iri, txt, _cosine(qv, ev)) for iri, txt, ev in pool),
                    key=lambda x: -x[2])
    return [(iri, txt, sim) for iri, txt, sim in scored[:k] if sim >= floor]


# --- batched LLM select (single + multi; moved verbatim) --------------------

def _llm_select(items: List[Dict[str, Any]], prompt_builder, client=None, model=None,
                model_tier: str = "fast"):
    """Map each item id -> ONE chosen candidate IRI (or None) via one LLM call.

    Returns the selection dict, or None if the LLM is unavailable / the call fails
    (the caller then falls back to the embedding threshold). ``prompt_builder``
    receives the items list and returns the user prompt; ``model_tier`` picks the
    default model when ``model`` is not supplied (the constrained pick-from-shortlist
    task fits the fast tier).

    Moved verbatim from state_edges._llm_select; only the prompt text was already
    parameterised out via prompt_builder."""
    if not items:
        return {}
    try:
        if client is None:
            from app.utils.llm_utils import get_llm_client
            client = get_llm_client()
        if model is None:
            from model_config import ModelConfig
            model = ModelConfig.get_claude_model(model_tier)
        if not (hasattr(client, "messages") and hasattr(client.messages, "stream")):
            logger.warning("edge_resolution: no Anthropic streaming client; embedding fallback")
            return None
        prompt = prompt_builder(items)
        chunks: List[str] = []
        with client.messages.stream(
            model=model, max_tokens=4096, temperature=0.0,
            system=("You select the single matching entity for each request, "
                    "respecting the relation's direction and polarity. Output strict JSON only."),
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for t in stream.text_stream:
                chunks.append(t)
        from app.utils.llm_utils import extract_json_from_response
        data = extract_json_from_response("".join(chunks))
        if not isinstance(data, dict):
            return None
        by_id = {str(it["id"]): it for it in items}
        out: Dict[str, Any] = {}
        for k, v in data.items():
            it = by_id.get(str(k))
            if it is None:
                continue
            if isinstance(v, str) and v.strip().lower() in ("none", "0", ""):
                out[str(k)] = None
                continue
            try:
                n = int(v)
            except (TypeError, ValueError):
                out[str(k)] = None
                continue
            out[str(k)] = it["shortlist"][n - 1][0] if 1 <= n <= len(it["shortlist"]) else None
        return out
    except Exception as e:
        logger.warning("edge_resolution: LLM select failed (%s); embedding fallback", e)
        return None


def _llm_select_multi(items: List[Dict[str, Any]], client=None, model=None,
                      prompt_builder=None, model_tier: str = "default"):
    """Map each item id -> list of chosen IRIs via one LLM call. Returns the
    selection dict, or None if the LLM is unavailable / the call fails (the caller
    then falls back to the embedding threshold). ``prompt_builder`` lets each applier
    supply its own request wording while reusing the streaming + JSON-parse +
    index-mapping logic here; ``model_tier`` picks the default model.

    Moved verbatim from resource_edges._llm_select_multi (the default tier is Sonnet,
    which reads subject-vs-object reliably on narrative `used_by` text)."""
    if not items:
        return {}
    try:
        if client is None:
            from app.utils.llm_utils import get_llm_client
            client = get_llm_client()
        if model is None:
            from model_config import ModelConfig
            model = ModelConfig.get_claude_model(model_tier)
        if not (hasattr(client, "messages") and hasattr(client.messages, "stream")):
            logger.warning("edge_resolution: no Anthropic streaming client; embedding fallback")
            return None
        prompt = (prompt_builder or _build_multi_select_prompt)(items)
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
        logger.warning("edge_resolution: LLM select failed (%s); embedding fallback", e)
        return None


def _build_multi_select_prompt(items: List[Dict[str, Any]]) -> str:
    """Default resource `used_by` multi-select prompt (moved verbatim from
    resource_edges); the fallback prompt for _llm_select_multi when no builder is
    supplied."""
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


# --- provenance (idempotent; moved verbatim from state_edges) ---------------

def _safe_frag(iri) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", str(iri).split("#")[-1])


def emit_edge_prov(g: Graph, case_id: int, prefix: str, prop: str, subj, obj,
                   desc: str, label: str, comment: str):
    """Shared PROV-O Derivation emitter for a materialised (subj, prop, obj) edge --
    the single home for the provenance-node shape the edge-applier family used to
    copy-paste eight times (rule of three). ``prefix`` is the LITERAL provenance-IRI
    prefix the family uses (e.g. ``"state_edge_provenance_"``); the node IRI is
    ``case#<prefix><safe_frag(subj)>_<prop>_<safe_frag(obj)>`` -- byte-identical to the
    pre-consolidation scheme, and idempotent. The per-family ``label``/``comment`` stay
    local config and are passed through; only the node-shape logic is centralised.
    Returns the node IRI."""
    case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")
    prov_iri = case_ns[prefix + _safe_frag(subj) + "_" + prop + "_" + _safe_frag(obj)]
    if (prov_iri, RDF.type, PROV.Derivation) in g:
        return prov_iri
    g.add((prov_iri, RDF.type, PROV.Derivation))
    g.add((prov_iri, PROV.wasDerivedFrom, subj))
    g.add((prov_iri, PROV.wasDerivedFrom, obj))
    g.add((prov_iri, RDFS.label, Literal(label)))
    if desc:
        g.add((prov_iri, PROV.value, Literal(str(desc))))
    g.add((prov_iri, RDFS.comment, Literal(comment)))
    return prov_iri


def remove_edge_prov(g: Graph, case_id: int, prefix: str, prop: str, subj, obj) -> None:
    """Remove the PROV-O node ``emit_edge_prov`` minted for (subj, prop, obj), so a
    dropped edge leaves no orphan derivation node. Same IRI scheme as emit_edge_prov."""
    case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")
    prov_iri = case_ns[prefix + _safe_frag(subj) + "_" + prop + "_" + _safe_frag(obj)]
    for t in list(g.triples((prov_iri, None, None))):
        g.remove(t)
