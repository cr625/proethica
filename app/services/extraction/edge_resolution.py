"""Shared resolver primitives for the embedding-resolved edge appliers.

A committed case TTL carries individuals + their subClassOf-core chains but no
relational layer. The "Architecture-B" edge appliers (state / resource /
state-affects / participant / fluent / obligation / temporal-relation /
requires-capability / causal)
all follow one template: read a relationship-label field from
``temporary_rdf_storage`` -> build a candidate pool of individuals in a target
category -> shortlist by embedding cosine -> confirm/select via one batched LLM
call (with an embedding-threshold fallback) -> emit the edge triple + a PROV-O
``prov:Derivation`` node.

This module is the SINGLE HOME for the primitives that template shares. The
helpers were previously split across ``state_edges`` (embedding + graph + the
single-select LLM + the provenance emitter/remover) and ``resource_edges`` (the
Agent pool + the multi-select LLM). They are MOVED here verbatim -- the resolver
logic is unchanged; this only unifies and de-duplicates the home. The surviving
bespoke modules re-export from here (``state_edges._embed``,
``time_anchor._safe_frag``), so their historical import surfaces keep resolving;
the other per-family modules were deleted with the registry migration.

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
    # Split CamelCase boundaries (lower-to-upper transitions) BEFORE lowercasing,
    # so "EthicalDilemmaState" and "Ethical Dilemma State" normalize identically.
    # Extracted state_class fields and committed class labels arrive in both
    # spellings; without the split an individual resolves to the wrong class
    # (states NEW-1: wrong principleTransformation copied). Already-spaced,
    # underscored, and hyphenated labels are unaffected.
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s or "")
    return re.sub(r"\s+", " ", s.lower().replace("_", " ").replace("-", " ")).strip()


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

# Below this batch size an all-"none" selection is a plausible judgment; at or
# above it (run 21: 34 items, 0 resolved, where an identical-prompt replay on
# the identical model resolved 28) it is treated as an anomalous generation:
# retry once, then fall back to the calibrated embedding thresholds so a single
# bad generation can never zero a whole edge family.
ALLNONE_RETRY_MIN_ITEMS = 5


def _resolved_count(selections: Dict[str, Any], items: List[Dict[str, Any]]) -> int:
    """How many items the selection mapping resolves to a candidate (missing
    ids count as unresolved, matching the caller's ``selections.get`` read)."""
    return sum(1 for it in items if selections.get(str(it["id"])) is not None)


def _coerce_choice(v: Any, item: Dict[str, Any]):
    """One raw selection value -> shortlist IRI or None (explicit rejection).

    Tolerates the shapes select models actually emit: an int, a numeric string
    or float ("2", 2.0), the explicit "none"/""/0/null rejections, or the
    candidate LABEL echoed back instead of its number (full or 90-char
    prompt-truncated form). An unrecognized shape is logged at WARNING --
    previously it collapsed to a silent None, which made a format-drifted
    response indistinguishable from an all-none judgment (run-21 F2b)."""
    shortlist = item["shortlist"]
    if v is None:
        return None
    if isinstance(v, bool):
        logger.warning("edge_resolution: select item %s got boolean %r; treating as none",
                       item.get("id"), v)
        return None
    if isinstance(v, str):
        s = v.strip()
        if s.lower() in ("none", "0", ""):
            return None
        try:
            f = float(s)
        except ValueError:
            folded = s.casefold()
            for iri, lbl, _sim in shortlist:
                lbl_fold = str(lbl).casefold().strip()
                if folded == lbl_fold or folded == lbl_fold[:90]:
                    return iri
            logger.warning(
                "edge_resolution: select item %s got unrecognized value %r "
                "(not a number, 'none', or a candidate label); treating as none",
                item.get("id"), s[:120])
            return None
        v = f
    if isinstance(v, (int, float)):
        if isinstance(v, float) and not v.is_integer():
            logger.warning("edge_resolution: select item %s got non-integer %r; treating as none",
                           item.get("id"), v)
            return None
        n = int(v)
        if 1 <= n <= len(shortlist):
            return shortlist[n - 1][0]
        logger.warning("edge_resolution: select item %s chose out-of-range candidate %d "
                       "(shortlist has %d); treating as none",
                       item.get("id"), n, len(shortlist))
        return None
    logger.warning("edge_resolution: select item %s got unrecognized value type %s; "
                   "treating as none", item.get("id"), type(v).__name__)
    return None


def _map_selection_data(data: Dict[str, Any], items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Parsed JSON object -> {item id: IRI or None}, with format tolerance."""
    by_id = {str(it["id"]): it for it in items}
    # Tolerate a single-key wrapper object whose value is the real mapping
    # (e.g. {"selections": {...}}); an unrecognized wrapper previously yielded
    # an empty mapping, indistinguishable from all-none.
    if len(data) == 1:
        (k, v), = data.items()
        if isinstance(v, dict) and str(k) not in by_id:
            logger.warning("edge_resolution: unwrapping select response wrapper key %r", k)
            data = v
    out: Dict[str, Any] = {}
    unknown_keys: List[str] = []
    for k, v in data.items():
        it = by_id.get(str(k))
        if it is None:
            unknown_keys.append(str(k))
            continue
        out[str(k)] = _coerce_choice(v, it)
    if unknown_keys:
        logger.warning("edge_resolution: select returned %d key(s) matching no request id: %s",
                       len(unknown_keys), unknown_keys[:10])
    return out


def _select_attempt(client, model, prompt: str, items: List[Dict[str, Any]],
                    cache_prompt: bool = False, diag: Optional[Dict[str, Any]] = None):
    """One streamed select call. Returns the mapped selection dict, or None
    when the response is not a JSON object (the caller falls back).

    ``cache_prompt`` marks the prompt as a cached prefix -- set by the
    multi-vote path, whose votes re-send this identical prompt within seconds
    (vote 1 writes, later votes read at ~0.1x). ``diag`` collects the raw
    responses for the zero-outcome diagnosability record."""
    from app.utils.llm_utils import direct_call_params, extract_json_from_response
    content = ([{"type": "text", "text": prompt, "cache_control": {"type": "ephemeral"}}]
               if cache_prompt else prompt)
    chunks: List[str] = []
    with client.messages.stream(
        **direct_call_params(model, max_tokens=4096, temperature=0.0),
        system=("You select the single matching entity for each request, "
                "respecting the relation's direction and polarity. Output strict JSON only."),
        messages=[{"role": "user", "content": content}],
    ) as stream:
        for t in stream.text_stream:
            chunks.append(t)
    raw = "".join(chunks)
    logger.debug("edge_resolution: select raw response (%d chars): %r", len(raw), raw[:2000])
    if diag is not None:
        diag.setdefault("raws", []).append(raw)
    data = extract_json_from_response(raw)
    if not isinstance(data, dict):
        logger.warning("edge_resolution: select response parsed to %s, not a JSON object",
                       type(data).__name__)
        return None
    return _map_selection_data(data, items)


def _llm_select(items: List[Dict[str, Any]], prompt_builder, client=None, model=None,
                model_tier: str = "fast", votes: int = 1,
                diag: Optional[Dict[str, Any]] = None):
    """Map each item id -> ONE chosen candidate IRI (or None) via LLM call(s).

    Returns the selection dict, or None if the LLM is unavailable / the call fails
    (the caller then falls back to the embedding threshold). ``prompt_builder``
    receives the items list and returns the user prompt; ``model_tier`` picks the
    default model when ``model`` is not supplied.

    ``votes`` > 1 runs that many independent attempts on the IDENTICAL prompt
    (cached prefix: vote 1 writes, later votes read) and takes the per-item
    strict majority -- a candidate is chosen only when more than half of the
    successful votes pick it, else the item resolves to none. This is the
    activatesObligation-instability calibration (2026-07-11): a controlled
    5x-repeatability experiment showed BOTH single-call tiers flip run to run
    (2-4 distinct selection sets of 5), so a lone call cannot be stable
    regardless of tier; majority voting pins the modal judgment. Under voting,
    an all-none MAJORITY is accepted as the answer (three independent
    judgments already guard the one-flaky-call case the single-vote all-none
    retry exists for; overriding them with embedding thresholds would undo
    the precision layer). ``diag`` collects {prompt, model, raws} for the
    zero-outcome diagnosability record.

    Run-21 hardening (F2b) on the single-vote path is unchanged: raw logged at
    DEBUG, unknown shapes WARN instead of silent None, wrapper unwrap, and an
    all-none selection over >= ALLNONE_RETRY_MIN_ITEMS items retried once then
    handed to the caller's calibrated embedding fallback (return None)."""
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
        if diag is not None:
            diag["prompt"] = prompt
            diag["model"] = model

        if votes > 1:
            ballots = []
            for _ in range(votes):
                out = _select_attempt(client, model, prompt, items,
                                      cache_prompt=True, diag=diag)
                if out is not None:
                    ballots.append(out)
            if not ballots:
                return None
            merged: Dict[str, Any] = {}
            need = len(ballots) // 2 + 1
            for it in items:
                key = str(it["id"])
                tally: Dict[Any, int] = {}
                for b in ballots:
                    v = b.get(key)
                    tally[v] = tally.get(v, 0) + 1
                winner, count = max(tally.items(), key=lambda kv: kv[1])
                merged[key] = winner if count >= need else None
            if _resolved_count(merged, items) == 0:
                logger.warning(
                    "edge_resolution: %d-vote majority resolved 0 of %d items "
                    "(accepted as the answer; unanimous-none across votes)",
                    len(ballots), len(items))
            return merged

        out = _select_attempt(client, model, prompt, items, diag=diag)
        if out is None:
            return None
        if len(items) >= ALLNONE_RETRY_MIN_ITEMS and _resolved_count(out, items) == 0:
            logger.warning(
                "edge_resolution: select resolved 0 of %d items (all-none); retrying once",
                len(items))
            out = _select_attempt(client, model, prompt, items, diag=diag)
            if out is None:
                return None
            if _resolved_count(out, items) == 0:
                logger.warning(
                    "edge_resolution: select all-none again on retry (%d items); "
                    "falling back to the calibrated embedding thresholds", len(items))
                return None
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
        from app.utils.llm_utils import direct_call_params
        with client.messages.stream(
            **direct_call_params(model, max_tokens=4096, temperature=0.0),
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
    """Shared PROV-O Derivation emitter for a materialized (subj, prop, obj) edge --
    the single home for the provenance-node shape the edge-applier family used to
    copy-paste eight times (rule of three). ``prefix`` is the LITERAL provenance-IRI
    prefix the family uses (e.g. ``"state_edge_provenance_"``); the node IRI is
    ``case#<prefix><safe_frag(subj)>_<prop>_<safe_frag(obj)>`` -- byte-identical to the
    pre-consolidation scheme, and idempotent. The per-family ``label``/``comment`` stay
    local config and are passed through; only the node-shape logic is centralized.
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
