"""Participant-edge materialization (DB-driven, embedding-resolved).

Each Pass-2 normative component carries an extracted field naming the actor it
bears on. Until now these were committed only as opaque literals (and, for the
'who' fields, read by rpo_edges / the defeasibility pipeline as string context),
never as graph structure:

  Obligation  proeth:obligatedParty    "Engineer B"      -> who bears the obligation
  Constraint  proeth:constrainedEntity "Engineer A"      -> who/what is constrained
  Capability  proeth:possessedBy       "Engineer A"      -> who possesses the capability
  Principle   proeth:invokedBy         ["Engineer A", .. ] -> who invokes the principle

This applier WIRES THEM IN. For each component it reads the field from
temporary_rdf_storage, resolves the named party (or parties) to the matching case
proeth-core:Agent individual(s), and materializes a first-class object property
with PROV-O provenance, e.g.

  Obligation proeth-core:obligatedParty Agent

The wire-in is ADDITIVE: the literal is left in place, because rpo_edges.gather and
defeasibility_pipeline.parse_case_graph read obligatedParty / invokedBy off the
committed graph as string context. This only ADDS the reasoner-visible,
SPARQL-queryable edge.

Structurally identical to state_affects_edges.py (State affects Agent) and
resource_edges.py (Resource availableTo Agent): an embedding shortlist over the
case Agents (cheap pre-filter) followed by one batched LLM multi-select per
edge-type, with an embedding-threshold fallback when the LLM is unavailable. The
range is Agent, which is outside the nine disjoint D-tuple categories, so a
Component -> Agent edge cannot introduce a disjointness clash (the unified
domain/range guard run by edge_materialization still validates the component
subject and drops any edge whose subject's type chain resolves to the wrong
category). possessedBy is declared owl:inverseOf hasCapability in proethica-core.

Best-effort, like the other appliers: failures are logged and returned, never
raised, so edge materialization can never fail a commit. Unresolved descriptions
are logged with their best similarity (no silent drops). A generic or
institutional party that matches no case Agent correctly yields no edge.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from rdflib import Graph, Namespace, URIRef

# Reuse the established embedding/graph primitives + the Agent pool and the batched
# multi-select LLM driver from the sibling appliers. Only the participant-specific
# read, prompt wording, and apply loop live here.
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

# Same regime as resource_edges / state_affects_edges: the candidate pool is the
# case Agents (few, clean), party names are short, so the shortlist floor is low
# (every Agent reaches the LLM) and the LLM is the precision layer; the
# embedding-only fallback keeps Agents at or above EMBED_MATCH_MIN.
EMBED_MATCH_MIN = 0.50
SHORTLIST_FLOOR = 0.30
SHORTLIST_K = 8


@dataclass(frozen=True)
class _ParticipantSpec:
    """One Component -> Agent participant edge."""
    extraction_type: str            # temporary_rdf_storage.extraction_type
    category: str                   # core category of the subject component
    prop: str                       # proeth-core property local name
    fields: Tuple[str, ...]         # candidate property keys in temp_rdf (camel + snake)
    noun: str                       # human noun for the prompt ("obligation", ...)
    relation: str                   # how the prompt phrases the actor relation


# The four Pass-2 participant edges. Ca/Cs flip guarded by the explicit category.
PARTICIPANT_SPECS: Tuple[_ParticipantSpec, ...] = (
    _ParticipantSpec(
        "obligations", "Obligation", "obligatedParty",
        ("obligatedParty", "obligated_party"),
        "obligation", "BEARS the obligation (is the duty-bearer)",
    ),
    _ParticipantSpec(
        "constraints", "Constraint", "constrainedEntity",
        ("constrainedEntity", "constrained_entity"),
        "constraint", "is CONSTRAINED by it (whose conduct it limits)",
    ),
    _ParticipantSpec(
        "capabilities", "Capability", "possessedBy",
        ("possessedBy", "possessed_by"),
        "capability", "POSSESSES the capability",
    ),
    _ParticipantSpec(
        "principles", "Principle", "invokedBy",
        ("invokedBy", "invoked_by"),
        "principle", "INVOKES the principle (appeals to it to justify or evaluate conduct)",
    ),
)


def _parties_from_db(case_id: int, spec: _ParticipantSpec) -> List[Dict[str, str]]:
    """[{label, desc}] for individuals of this spec's extraction_type carrying a
    non-empty participant field, read from temporary_rdf_storage. The field is
    committed only as a (potentially bug-lowercased) literal, so the clean
    camelCase value is read here from the extraction rows. A list-valued field
    (invokedBy) is joined with '; ' so the multi-select resolver can pick several
    agents, mirroring state_affects affectedParties."""
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    def _props(row):
        return ((row.rdf_json_ld or {}).get("properties") or {})

    rows = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type=spec.extraction_type, storage_type="individual"
    ).all()
    out: List[Dict[str, str]] = []
    for r in rows:
        p = _props(r)
        raw = None
        for k in spec.fields:
            v = p.get(k)
            if v:
                raw = v
                break
        if raw is None:
            continue
        if isinstance(raw, list):
            parties = [str(x).strip() for x in raw if str(x).strip()]
        else:
            parties = [str(raw).strip()] if str(raw).strip() else []
        if parties:
            out.append({"label": r.entity_label or "", "desc": "; ".join(parties)})
    return out


def _build_participant_prompt(spec: _ParticipantSpec):
    def builder(items: List[Dict[str, Any]]) -> str:
        blocks = []
        for it in items:
            cands = "; ".join(
                f"{i + 1}) {lbl[:90]}" for i, (iri, lbl, sim) in enumerate(it["shortlist"])
            )
            blocks.append(
                f"[{it['id']}] {spec.noun}: \"{(it.get('subj_label') or '')[:120]}\"\n"
                f"  party text: \"{(it['desc'] or '')[:220]}\"\n"
                f"  candidate agents: {cands}"
            )
        return (
            f"Each REQUEST gives the party text of a {spec.noun} in an "
            "engineering-ethics case, plus the candidate AGENTS in that case.\n"
            f"For each request, choose ALL candidate agents that the party text "
            f"identifies as the agent(s) who {spec.relation}. A text may name "
            "several agents, one, or none.\n"
            "Choose NONE (an empty list) when the named party is a generic group "
            "not among the candidates (e.g. 'the public', 'society'), an institution "
            "not among the candidates, a non-agent thing, or otherwise not one of the "
            "listed case agents.\n\n"
            "REQUESTS:\n" + "\n\n".join(blocks) +
            "\n\nOUTPUT strict JSON only, one entry per request id, each value a JSON "
            "array of the chosen candidate numbers (use [] for none): "
            "{\"<id>\": [<n>, ...], ...}"
        )
    return builder


def _emit_prov(g: Graph, case_id: int, prop: str, subj, obj, desc: str) -> None:
    emit_edge_prov(g, case_id, "participant_edge_provenance_", prop, subj, obj, desc,
                   f"Participant edge ({prop})",
                   f"property={prop}; component party text resolved to the case Agent(s) "
                   "by embedding shortlist + LLM select")


def _apply_one_spec(g: Graph, svc, pool, case_id: int, spec: _ParticipantSpec,
                    threshold: float, use_llm: bool, llm_client, model,
                    res: Dict[str, Any]) -> None:
    """Resolve + emit edges for one participant spec on the shared graph `g`."""
    try:
        parties = _parties_from_db(case_id, spec)
    except Exception as e:
        logger.warning("participant_edges: temp_rdf read failed for %s case %s: %s",
                       spec.extraction_type, case_id, e)
        res[spec.prop] = {"error": str(e)}
        return
    if not parties:
        res[spec.prop] = {"edges": 0, "status": "no_parties"}
        return

    subj_iris: Dict[str, URIRef] = {}
    for ind in _individuals_in_category(g, spec.category):
        subj_iris.setdefault(_norm(_label(g, ind)), ind)

    items: List[Dict[str, Any]] = []
    next_id = 1
    unresolved = 0
    for pr in parties:
        subj = subj_iris.get(_norm(pr["label"]))
        if subj is None:
            logger.info("participant_edges[%s]: %r not in committed graph; skipped",
                        spec.prop, pr["label"][:80])
            continue
        desc = pr["desc"]
        sl = _shortlist(svc, desc, pool, SHORTLIST_FLOOR, SHORTLIST_K)
        if not sl:
            unresolved += 1
            logger.info("participant_edges[%s]: party has no Agent above floor %.2f: %r",
                        spec.prop, SHORTLIST_FLOOR, desc[:80])
            continue
        items.append({
            "id": next_id, "subj": subj, "desc": desc,
            "subj_label": pr["label"], "shortlist": sl,
        })
        next_id += 1

    selections = _llm_select_multi(
        items, client=llm_client, model=model, prompt_builder=_build_participant_prompt(spec)
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
            logger.info("participant_edges[%s]: party unresolved (resolver=%s): %r",
                        spec.prop, resolver, desc[:80])
            continue
        for tgt in targets:
            if (subj, CORE[spec.prop], tgt) in g:
                continue
            g.add((subj, CORE[spec.prop], tgt))
            _emit_prov(g, case_id, spec.prop, subj, tgt, desc)
            edges += 1

    res[spec.prop] = {"edges": edges, "resolver": resolver, "unresolved": unresolved}


def apply_participant_edges(case_id: int, ttl_path, write_back: bool = True,
                            threshold: float = EMBED_MATCH_MIN, use_llm: bool = True,
                            llm_client=None, model=None) -> Dict[str, Any]:
    """Materialize the four Component -> Agent participant edges on a just-written
    case TTL (obligatedParty, constrainedEntity, possessedBy, invokedBy).

    The graph is parsed once and the case Agent pool built once; each spec is then
    resolved (embedding shortlist + one batched LLM multi-select per spec, with an
    embedding-threshold fallback) and its edges + provenance added in place. Returns
    a per-property result dict plus the total edge count."""
    ttl_path = Path(ttl_path)
    res: Dict[str, Any] = {"case_id": case_id, "status": "ok", "total": 0}

    g = Graph()
    g.parse(str(ttl_path), format="turtle")
    svc = _embedding_service()
    pool = _agent_pool(g, svc)
    if not pool:
        return {"case_id": case_id, "status": "no_agents"}

    for spec in PARTICIPANT_SPECS:
        _apply_one_spec(g, svc, pool, case_id, spec, threshold, use_llm,
                        llm_client, model, res)

    total = sum(v.get("edges", 0) for v in res.values() if isinstance(v, dict))
    res["total"] = total
    if write_back and total:
        g.serialize(destination=str(ttl_path), format="turtle")
    return res
