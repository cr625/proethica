"""Data-driven edge-family framework.

Six of the eight "Architecture-B" embedding-resolved edge appliers (resource,
state-affects, participant, fluent, obligation, temporal-relation) are the SAME
template differing only in data: read a relationship-label field from
``temporary_rdf_storage`` -> build a candidate pool of individuals in a target
category -> shortlist by embedding cosine -> one batched LLM multi-select (with an
embedding-threshold fallback) -> emit the edge triple + a PROV-O Derivation node.

This module expresses each such family as data (``EdgeSpec`` + ``EdgePredicate``)
and runs the template once (``materialize_edge_family``). The resolver primitives it
calls are the shared ones in ``edge_resolution`` (moved verbatim from the original
appliers); this module supplies only the per-family orchestration. ``EDGE_REGISTRY``
lists the six families.

Two families are NOT data-driven and stay as bespoke appliers, because their logic
does not compress to a spec without loss:

  - ``state_edges`` -- resolves a state CLASS to its committed individual
    (``_best_class``), uses PER-FIELD embedding thresholds and a SINGLE-select LLM
    with a direction/polarity prompt, and emits a ``principleTransformation`` literal
    annotation alongside the object edges.
  - ``causal_edges.apply_causal_edges`` -- splits compound cause/effect labels into
    conjuncts (``_split_conjuncts``) and runs a temporal-precedence post-guard that
    drops mis-sequenced edges (and their PROV nodes).

Both already share the unified ``edge_resolution`` primitives; only their drivers
remain hand-written. ``edge_materialization`` calls them alongside the registry loop.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL, TIME

from app.services.extraction.edge_resolution import (
    BOARD_AGENT_LOCALNAME,
    _agent_pool,
    _candidate_pool,
    _embedding_service,
    _individuals_in_category,
    _label,
    _llm_select_multi,
    _norm,
    _shortlist,
    emit_edge_prov,
)

logger = logging.getLogger(__name__)

CORE = Namespace("http://proethica.org/ontology/core#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
PROV = Namespace("http://www.w3.org/ns/prov#")

# Shared resolution regime for the multi-select Agent/category appliers (the value
# already used identically by all six families).
EMBED_MATCH_MIN = 0.50
SHORTLIST_FLOOR = 0.30
SHORTLIST_K = 8


# A row read from temporary_rdf_storage for one subject individual: its committed
# rdfs:label (for matching to the graph) plus, per predicate local name, the list of
# free-text labels to resolve. ``extra`` carries any per-item provenance override
# (temporal_relation passes its `evidence` text; the others leave it empty).
@dataclass
class SubjectRow:
    label: str
    fields: Dict[str, List[str]]
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EdgePredicate:
    """One object property emitted by a family.

    Several predicates can share one subject pool (e.g. fluent initiates/terminates,
    the four obligation predicates). ``subject_category`` overrides the spec default
    when a family's predicates have DIFFERENT subject categories (participant edges:
    obligatedParty on Obligation, possessedBy on Capability, ...)."""
    prop: str                          # property local name
    namespace: Namespace               # declaring namespace (CORE or PROETH)
    fields: Tuple[str, ...]            # temp_rdf JSON-LD / properties keys carrying the label list
    range_category: str                # core category of the candidate pool ("Agent" -> _agent_pool)
    pool_fields: Tuple[str, ...] = ()  # extra match fields read off candidate individuals
    range_union: Tuple[str, ...] = ()  # if set, object pool is the union of these categories
    subject_category: Optional[str] = None  # per-predicate subject category override
    subject_extraction_type: str = ""  # per-predicate temp_rdf extraction_type (participant edges)
    prompt_builder_factory: Optional[Callable[["EdgePredicate", "EdgeSpec"], Callable]] = None
    verb: str = ""                     # human phrasing used by the prompt builder
    target_noun: str = ""              # human noun for the target (prompt wording)
    # Coherence veto: local name of a sibling property (same namespace) whose presence on the
    # SAME (subject, target) pair drops this edge instead of asserting it. Used by the fluent
    # family: a happening must not terminate a state it initiates, so terminates carries
    # veto_if_present="initiates" (initiates is emitted first in predicate order, so a
    # same-run initiates edge is already in the graph when terminates resolves).
    veto_if_present: Optional[str] = None
    # temp_rdf row shape for this predicate's reader rows: "properties" (Pass-1/2
    # storage rows keep fields under a 'properties' wrapper) or "temporal" (Step-3
    # rows store proeth: keys at the TOP level of rdf_json_ld -- the fluent-spec
    # subject convention). Used by _read_participants for isPerformedBy, whose Action
    # subjects live under extraction_type='temporal_dynamics_enhanced'.
    row_shape: str = "properties"
    row_type_filter: Tuple[str, ...] = ()      # @type substrings kept for temporal rows
    # Optional per-party label normalizer applied by the reader BEFORE resolution
    # (e.g. stripping the role parenthetical from a hasAgent literal: "Engineer A
    # (Senior Engineer)" -> "Engineer A"). The stored literal itself is untouched.
    normalize: Optional[Callable[[str], str]] = None
    # Deterministic Board-pattern fallback (invokedBy / citedByAgent ONLY): a party
    # literal matching the NSPE Board pattern is routed to the single case-scoped
    # Board Agent individual instead of the embedding/LLM actor resolution (which can
    # never resolve it: the Board is not an extracted case Agent and is excluded from
    # _agent_pool).
    board_agent_fallback: bool = False
    # Inverted emission: the resolved TARGET is the edge SUBJECT and the row
    # individual is the edge OBJECT. Used by requiresCapability, whose reader rows
    # are Capability individuals while proethica-core declares the property
    # Obligation -> Capability (an obligation presupposes the capacity to discharge
    # it, v2.8.0).
    invert: bool = False


@dataclass(frozen=True)
class EdgeSpec:
    """One edge family expressed as data.

    A family shares ONE subject pool across its predicates (unless a predicate sets
    ``subject_category``), reads its source rows from one temp_rdf extraction_type, and
    emits each predicate via the shared multi-select template."""
    name: str                          # result-dict key / log name
    extraction_type: str               # temporary_rdf_storage.extraction_type to read
    subject_category: str              # default core category of the subject individuals
    predicates: Tuple[EdgePredicate, ...]
    prov_prefix: str                   # literal provenance-IRI prefix (byte-identical to legacy)
    prov_label: Callable[[str], str]   # prop local name -> prov rdfs:label
    prov_comment: Callable[[str], str]  # prop local name -> prov rdfs:comment
    reader: Callable[[int, "EdgeSpec"], List[SubjectRow]]  # temp_rdf reader
    # subject resolution: "category" (materialized direct rdf:type proeth-core:<Category>)
    # | "type" (a specific rdf:type class) | "union" (several core categories collapsed
    # into one label map)
    subject_resolution: str = "category"
    subject_type: Optional[URIRef] = None         # for subject_resolution="type"
    subject_union: Tuple[str, ...] = ()           # for subject_resolution="union"
    pool_kind: str = "category"        # "category" (_candidate_pool) | "agent" (_agent_pool)
    single_valued: bool = False        # keep only the first selected target (fromEntity/toEntity, ...)
    model_tier: str = "default"
    type_filter: Tuple[str, ...] = ()  # @type substrings the temporal reader keeps
    extra_read: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None  # per-row extra fields
    extra_emit: Optional[Callable[[Graph, "EdgeSpec", URIRef, str, URIRef, SubjectRow], None]] = None
    no_data_status: str = "no_data"


# --- subject map + candidate pools -----------------------------------------

def _subject_map(g: Graph, spec: EdgeSpec, category: Optional[str] = None) -> Dict[str, URIRef]:
    """Normalized-label -> committed subject IRI, by the family's resolution strategy.
    ``category`` overrides the spec default (used for per-predicate subject categories)."""
    out: Dict[str, URIRef] = {}
    if spec.subject_resolution == "type":
        inds = g.subjects(RDF.type, spec.subject_type)
    elif spec.subject_resolution == "union":
        inds = []
        for cat in spec.subject_union:
            inds.extend(_individuals_in_category(g, cat))
    else:
        inds = _individuals_in_category(g, category or spec.subject_category)
    for ind in inds:
        out.setdefault(_norm(_label(g, ind)), ind)
    return out


def _pool_for(g: Graph, svc, spec: EdgeSpec, pred: EdgePredicate, cache: Dict[Tuple, Any]):
    """Build (and cache) the candidate pool for a predicate. Agent pools and
    category pools are cached by their distinguishing key so a family with several
    predicates over the same target category builds it once (matches obligation_edges)."""
    if spec.pool_kind == "agent" or pred.range_category == "Agent":
        key = ("agent",)
        if key not in cache:
            cache[key] = _agent_pool(g, svc)
        return cache[key]
    if pred.range_union:
        key = ("union", pred.range_union, pred.pool_fields)
        if key not in cache:
            pool = []
            for cat in pred.range_union:
                pool += _candidate_pool(g, svc, cat, list(pred.pool_fields))
            cache[key] = pool
        return cache[key]
    key = ("cat", pred.range_category, pred.pool_fields)
    if key not in cache:
        cache[key] = _candidate_pool(g, svc, pred.range_category, list(pred.pool_fields))
    return cache[key]


# --- NSPE Board Agent (deterministic Board-pattern actor fallback) ----------
# The Board of Ethical Review authors the analysis, so extraction rarely yields a
# case Agent individual for it (Agent_NSPE* = 0 in both committed case-7 runs) while
# Principle invokedBy / Resource citedBy literals keep naming it and stay unresolved.
# Case 10 is the exception (the Board answers its own conflict question and IS an
# extracted case Agent); _ensure_board_agent reuses such an Agent instead of minting.
# A Board-pattern literal on a board_agent_fallback predicate is resolved
# deterministically to ONE case-scoped Agent individual, minted on first use with
# provenance. The individual is excluded from _agent_pool (edge_resolution), so no
# embedding/LLM resolution -- used_by/availableTo included -- can ever select it.

BOARD_AGENT_LABEL = "NSPE Board of Ethical Review"


def _is_board_literal(text: str) -> bool:
    """True iff a party literal names the NSPE Board of Ethical Review. Matches
    "NSPE Board of Ethical Review" (anywhere in the literal), and the bare forms
    "the Board" / "Board" / "NSPE Board" / "the NSPE Board" only as the WHOLE
    literal, so "State Licensing Board" does not match."""
    s = re.sub(r"\s+", " ", (text or "")).strip().lower().rstrip(".")
    if "board of ethical review" in s:
        return True
    return re.fullmatch(r"(?:the )?(?:nspe )?board", s) is not None


def _ensure_board_agent(g: Graph, case_id: int) -> URIRef:
    """Get-or-create the single case-scoped NSPE Board Agent individual. Typed
    proeth-core:Agent (the range the participant-family edges expect); idempotent
    across predicates and re-materialization runs; carries provenance like the other
    materialized nodes."""
    case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")
    board = case_ns[BOARD_AGENT_LOCALNAME]
    if (board, RDF.type, CORE.Agent) in g:
        return board
    # Extraction can yield a case Agent that IS the Board (case 10); reuse it
    # instead of minting a same-label duplicate that splits the edge targets.
    for existing in sorted(g.subjects(RDF.type, CORE.Agent)):
        lbl = g.value(existing, RDFS.label)
        if lbl is not None and _is_board_literal(str(lbl)):
            return existing
    g.add((board, RDF.type, OWL.NamedIndividual))
    g.add((board, RDF.type, CORE.Agent))
    g.add((board, RDFS.label, Literal(BOARD_AGENT_LABEL)))
    g.add((board, RDFS.comment, Literal(
        "Case-scoped Agent individual materialized at commit for Board-pattern "
        "invokedBy/citedByAgent actor literals. Not extracted from the case text; "
        "excluded from the actor-resolution candidate pools, so it is never offered "
        "to extraction prompts and never matches as a reliance actor "
        "(used_by/availableTo).")))
    g.add((board, PROV.wasAttributedTo, Literal(
        f"Case {case_id} Edge Materialization (Board-pattern actor resolution)")))
    return board


# Strip a trailing role parenthetical from an actor literal before Agent resolution:
# "John Smith (Senior Engineer)" -> "John Smith". Reader-side only; the stored
# hasAgent literal is untouched (edges are additive).
def _strip_role_parenthetical(s: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*$", "", (s or "")).strip()


# --- the template ----------------------------------------------------------

def materialize_edge_family(case_id: int, ttl_path, spec: EdgeSpec, write_back: bool = True,
                            threshold: float = EMBED_MATCH_MIN, use_llm: bool = True,
                            llm_client=None, model=None) -> Dict[str, Any]:
    """Run the embedding-shortlist + batched-LLM-multi-select template for ONE edge
    family (``spec``) over a committed case TTL. Reads the family's source rows from
    temporary_rdf_storage, resolves each predicate's label lists against the target
    pool, and adds the edges + PROV-O provenance. Best-effort: failures return a status
    dict, never raise. Reproduces the per-applier behaviour exactly (same thresholds,
    same prompts, same prov scheme, same dedupe/no-op semantics)."""
    ttl_path = Path(ttl_path)
    res: Dict[str, Any] = {"case_id": case_id, "status": "ok", "total": 0}
    try:
        rows = spec.reader(case_id, spec)
    except Exception as e:
        logger.warning("%s: temp_rdf read failed for case %s: %s", spec.name, case_id, e)
        return {"case_id": case_id, "status": "no_db", "error": str(e)}
    if not rows:
        return {"case_id": case_id, "status": spec.no_data_status}

    g = Graph()
    g.parse(str(ttl_path), format="turtle")
    svc = _embedding_service()

    # Pre-resolve subject maps. When predicates share the spec's subject category a
    # single map is reused; per-predicate overrides get their own map.
    default_map = _subject_map(g, spec)
    if spec.pool_kind == "agent" and not default_map and all(
        p.subject_category is None for p in spec.predicates
    ):
        # No subject individuals of the family category present -> nothing to wire.
        # (resource/state-affects return their own no-subject statuses below via the
        # empty subject map; an empty Agent pool is the meaningful guard.)
        pass

    pool_cache: Dict[Tuple, Any] = {}
    # Agent-pooled families short-circuit when the case has no Agents (matches the
    # original appliers' "no_agents" status).
    if spec.pool_kind == "agent":
        agent_pool = _pool_for(g, svc, spec, spec.predicates[0], pool_cache)
        if not agent_pool:
            return {"case_id": case_id, "status": "no_agents"}

    any_pred_emitted = False
    for pred in spec.predicates:
        subj_map = (default_map if pred.subject_category is None
                    else _subject_map(g, spec, pred.subject_category))
        pool = _pool_for(g, svc, spec, pred, pool_cache)
        if not pool:
            res[pred.prop] = {"edges": 0, "status": f"no_{pred.range_category.lower()}s"}
            continue

        items: List[Dict[str, Any]] = []
        next_id = 1
        unresolved = 0
        # (row subject IRI, verbatim Board literal) pairs deferred to the
        # deterministic Board-pattern fallback (invokedBy / citedByAgent only).
        board_refs: List[Tuple[URIRef, str]] = []
        for row in rows:
            labels = row.fields.get(pred.prop) or []
            if not labels:
                continue
            subj = subj_map.get(_norm(row.label))
            if subj is None:
                logger.info("%s[%s]: subject %r not in committed graph; skipped",
                            spec.name, pred.prop, (row.label or "")[:80])
                continue
            if pred.board_agent_fallback:
                board_refs.extend((subj, lbl) for lbl in labels if _is_board_literal(lbl))
                labels = [lbl for lbl in labels if not _is_board_literal(lbl)]
                if not labels:
                    continue
            desc = "; ".join(labels)
            sl = _shortlist(svc, desc, pool, SHORTLIST_FLOOR, SHORTLIST_K)
            if not sl:
                unresolved += 1
                logger.info("%s[%s]: no %s above floor %.2f for %r",
                            spec.name, pred.prop, pred.range_category, SHORTLIST_FLOOR, desc[:80])
                continue
            item = {"id": next_id, "subj": subj, "desc": desc,
                    "subj_label": row.label, "row": row, "shortlist": sl}
            # Surface the family's prompt-label hints (resource_label / state_label /
            # subj_label / evidence) so the per-family prompt builder finds them under
            # the same key the original applier used.
            for k, v in row.extra.items():
                item.setdefault(k, v)
            items.append(item)
            next_id += 1

        builder = (pred.prompt_builder_factory(pred, spec)
                   if pred.prompt_builder_factory else None)
        selections = _llm_select_multi(
            items, client=llm_client, model=model, prompt_builder=builder,
            model_tier=spec.model_tier,
        ) if use_llm else None
        resolver = "llm" if selections is not None else "embedding"

        edges = 0
        vetoed = 0
        for it in items:
            subj, desc, sl, row = it["subj"], it["desc"], it["shortlist"], it["row"]
            if selections is not None:
                targets = selections.get(str(it["id"])) or []
            else:
                targets = [iri for iri, _lbl, sim in sl if sim >= threshold]
            if spec.single_valued and targets:
                targets = targets[:1]
            if not targets:
                unresolved += 1
                logger.info("%s[%s]: unresolved (resolver=%s): %r",
                            spec.name, pred.prop, resolver, desc[:80])
                continue
            for tgt in targets:
                # invert swaps the emission direction (requiresCapability: the
                # resolved Obligation is the SUBJECT, the row Capability the OBJECT);
                # dedupe, veto, and PROV all operate on the emitted direction.
                s_node, o_node = (tgt, subj) if pred.invert else (subj, tgt)
                if (pred.veto_if_present is not None
                        and (s_node, pred.namespace[pred.veto_if_present], o_node) in g):
                    vetoed += 1
                    logger.warning(
                        "%s[%s]: dropped %s -> %s: the same subject already carries %s to "
                        "this target (incoherent transition; a happening must not %s a "
                        "state it %s)",
                        spec.name, pred.prop, s_node, o_node, pred.veto_if_present,
                        pred.prop, pred.veto_if_present)
                    continue
                if (s_node, pred.namespace[pred.prop], o_node) not in g:
                    g.add((s_node, pred.namespace[pred.prop], o_node))
                    prov_desc = row.extra.get("prov_desc") or desc
                    emit_edge_prov(g, case_id, spec.prov_prefix, pred.prop, s_node, o_node,
                                   prov_desc, spec.prov_label(pred.prop),
                                   spec.prov_comment(pred.prop))
                    edges += 1
                if spec.extra_emit is not None:
                    spec.extra_emit(g, spec, subj, pred.prop, tgt, row)

        # Deterministic Board-pattern fallback: each deferred Board literal becomes an
        # edge to the single case-scoped Board Agent (minted on first use). Additive
        # and idempotent, same PROV shape as the resolved edges, with the verbatim
        # literal as the derivation value.
        board_edges = 0
        for b_subj, b_lit in board_refs:
            board = _ensure_board_agent(g, case_id)
            if (b_subj, pred.namespace[pred.prop], board) not in g:
                g.add((b_subj, pred.namespace[pred.prop], board))
                emit_edge_prov(g, case_id, spec.prov_prefix, pred.prop, b_subj, board,
                               b_lit, spec.prov_label(pred.prop),
                               spec.prov_comment(pred.prop)
                               + "; Board-pattern literal resolved deterministically to "
                                 "the case-scoped NSPE Board Agent")
                edges += 1
                board_edges += 1

        res[pred.prop] = {"edges": edges, "resolver": resolver, "unresolved": unresolved}
        if vetoed:
            res[pred.prop]["vetoed"] = vetoed
        if board_edges:
            res[pred.prop]["board_agent_edges"] = board_edges
        any_pred_emitted = any_pred_emitted or edges > 0

    total = sum(v.get("edges", 0) for v in res.values() if isinstance(v, dict))
    res["total"] = total
    if write_back and total:
        g.serialize(destination=str(ttl_path), format="turtle")
    return res


# ===========================================================================
# Per-family readers (the temp_rdf field mapping; one tiny function per family)
# ===========================================================================

def _props(row):
    return ((row.rdf_json_ld or {}).get("properties") or {})


def _read_resources(case_id: int, spec: EdgeSpec) -> List[SubjectRow]:
    """Resource `used_by` -> availableTo. Pass-1/2 storage_type=individual rows store
    fields under a 'properties' wrapper."""
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    def _str(props, *keys):
        for k in keys:
            v = props.get(k)
            if v:
                return str(v[0]) if isinstance(v, list) else str(v)
        return ""

    rows = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type=spec.extraction_type, storage_type="individual"
    ).all()
    out: List[SubjectRow] = []
    for r in rows:
        p = _props(r)
        used_by = _str(p, "usedBy", "used_by")
        if used_by.strip():
            out.append(SubjectRow(label=r.entity_label or "",
                                  fields={"availableTo": [used_by]},
                                  extra={"resource_label": r.entity_label or ""}))
    return out


def _read_state_affects(case_id: int, spec: EdgeSpec) -> List[SubjectRow]:
    """State `affectedParties` -> affects."""
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    rows = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type=spec.extraction_type, storage_type="individual"
    ).all()
    out: List[SubjectRow] = []
    for r in rows:
        p = _props(r)
        raw = p.get("affectedParties") or p.get("affected_parties") or []
        parties = [str(x).strip() for x in (raw if isinstance(raw, list) else [raw]) if str(x).strip()]
        if parties:
            out.append(SubjectRow(label=r.entity_label or "", fields={"affects": parties},
                                  extra={"state_label": r.entity_label or ""}))
    return out


def _read_participants(case_id: int, spec: EdgeSpec) -> List[SubjectRow]:
    """The Pass-2 'who' fields plus the actor-edge additions (citedByAgent,
    isPerformedBy). Each predicate has its OWN extraction_type and subject category,
    so this reader unions the per-predicate rows, keyed by predicate local name. A
    list field (invokedBy) is joined with '; ' so multi-select can pick several
    agents.

    Row shape is per-predicate: Pass-1/2 rows keep fields under a 'properties'
    wrapper; Step-3 temporal rows (isPerformedBy -- Action subjects are stored under
    extraction_type='temporal_dynamics_enhanced', NOT 'actions') store proeth: keys
    at the TOP level of rdf_json_ld and are @type-filtered, mirroring
    _read_temporal."""
    from app.models.temporary_rdf_storage import TemporaryRDFStorage
    out: List[SubjectRow] = []
    for pred in spec.predicates:
        rows = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type=pred.subject_extraction_type,
            storage_type="individual",
        ).all()
        for r in rows:
            if pred.row_shape == "temporal":
                src = r.rdf_json_ld or {}
                at_type = src.get("@type", "") or ""
                if pred.row_type_filter and not any(t in at_type for t in pred.row_type_filter):
                    continue
                label = r.entity_label or src.get("rdfs:label", "")
            else:
                src = _props(r)
                label = r.entity_label or ""
            raw = None
            for k in pred.fields:
                v = src.get(k)
                if v:
                    raw = v
                    break
            if raw is None:
                continue
            if isinstance(raw, list):
                parties = [str(x).strip() for x in raw if str(x).strip()]
            else:
                parties = [str(raw).strip()] if str(raw).strip() else []
            if pred.normalize is not None:
                parties = [p for p in (pred.normalize(x) for x in parties) if p]
            if parties:
                out.append(SubjectRow(label=label,
                                      fields={pred.prop: parties},
                                      extra={"subj_label": label,
                                             "_pred": pred.prop}))
    return out


def _read_temporal(case_id: int, spec: EdgeSpec) -> List[SubjectRow]:
    """Step-3 temporal rows store proeth: keys at the TOP level of rdf_json_ld (no
    'properties' wrapper). One reader serves fluent, obligation, temporal-relation
    (each filters @type and reads its own predicate fields)."""
    from app.models.temporary_rdf_storage import TemporaryRDFStorage
    rows = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type=spec.extraction_type, storage_type="individual"
    ).all()
    out: List[SubjectRow] = []
    for r in rows:
        rdf = r.rdf_json_ld or {}
        at_type = rdf.get("@type", "") or ""
        if spec.type_filter and not any(t in at_type for t in spec.type_filter):
            continue

        def _labels(keys):
            for k in keys:
                v = rdf.get(k)
                if v:
                    vals = v if isinstance(v, list) else [v]
                    return [str(x).strip() for x in vals if str(x).strip()]
            return []

        fields: Dict[str, List[str]] = {}
        any_field = False
        for pred in spec.predicates:
            labels = _labels(pred.fields)
            fields[pred.prop] = labels
            any_field = any_field or bool(labels)
        if not any_field:
            continue
        extra: Dict[str, Any] = {}
        if spec.extra_read:
            extra.update(spec.extra_read(rdf))
        out.append(SubjectRow(label=r.entity_label or rdf.get("rdfs:label", ""),
                              fields=fields, extra=extra))
    return out


def _read_capability_requirements(case_id: int, spec: EdgeSpec) -> List[SubjectRow]:
    """Capability `requiredForObligations` -> requiresCapability. The row subject is
    the CAPABILITY individual (Pass-2 'properties' wrapper) and the labels name the
    obligations of THIS case whose discharge presupposes it; the emitted edge is
    INVERTED (Obligation -> Capability) to conform to proethica-core's
    requiresCapability domain/range (v2.8.0: an obligation presupposes the capacity
    to discharge it)."""
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    rows = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type=spec.extraction_type, storage_type="individual"
    ).all()
    out: List[SubjectRow] = []
    for r in rows:
        p = _props(r)
        raw = p.get("requiredForObligations") or p.get("required_for_obligations") or []
        labels = [str(x).strip() for x in (raw if isinstance(raw, list) else [raw])
                  if str(x).strip()]
        if labels:
            out.append(SubjectRow(label=r.entity_label or "",
                                  fields={"requiresCapability": labels},
                                  extra={"subj_label": r.entity_label or ""}))
    return out


# --- prompt builders (per family; wrap the existing wording verbatim) -------

def _resource_prompt_factory(pred: EdgePredicate, spec: EdgeSpec):
    from app.services.extraction.edge_resolution import _build_multi_select_prompt
    return _build_multi_select_prompt


def _state_affects_prompt_factory(pred: EdgePredicate, spec: EdgeSpec):
    def builder(items: List[Dict[str, Any]]) -> str:
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
    return builder


def _participant_prompt_factory(pred: EdgePredicate, spec: EdgeSpec):
    noun, relation = pred.target_noun, pred.verb

    def builder(items: List[Dict[str, Any]]) -> str:
        blocks = []
        for it in items:
            cands = "; ".join(
                f"{i + 1}) {lbl[:90]}" for i, (iri, lbl, sim) in enumerate(it["shortlist"])
            )
            blocks.append(
                f"[{it['id']}] {noun}: \"{(it.get('subj_label') or '')[:120]}\"\n"
                f"  party text: \"{(it['desc'] or '')[:220]}\"\n"
                f"  candidate agents: {cands}"
            )
        return (
            f"Each REQUEST gives the party text of a {noun} in an "
            "engineering-ethics case, plus the candidate AGENTS in that case.\n"
            f"For each request, choose ALL candidate agents that the party text "
            f"identifies as the agent(s) who {relation}. A text may name "
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


def _fluent_prompt_factory(pred: EdgePredicate, spec: EdgeSpec):
    prop = pred.prop
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


_OBLIGATION_VERB = {
    "fulfillsObligation": "FULFILS (directly satisfies)",
    "violatesObligation": "VIOLATES (directly breaches)",
    "raisesObligation": "RAISES (puts in force / at stake, resolved later)",
    "guidedByPrinciple": "is GUIDED BY (the principle directing it)",
}


def _obligation_prompt_factory(pred: EdgePredicate, spec: EdgeSpec):
    prop = pred.prop
    verb = _OBLIGATION_VERB.get(prop, prop)
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


def _requires_capability_prompt_factory(pred: EdgePredicate, spec: EdgeSpec):
    def builder(items: List[Dict[str, Any]]) -> str:
        blocks = []
        for it in items:
            cands = "; ".join(
                f"{i + 1}) {lbl[:90]}" for i, (iri, lbl, sim) in enumerate(it["shortlist"])
            )
            blocks.append(
                f"[{it['id']}] capability: \"{(it.get('subj_label') or '')[:120]}\"\n"
                f"  obligation(s) requiring it: \"{(it['desc'] or '')[:240]}\"\n"
                f"  candidate obligations: {cands}"
            )
        return (
            "Each REQUEST gives a CAPABILITY (a professional competence) in an "
            "engineering-ethics case and the text naming the OBLIGATION(s) of that case "
            "whose discharge presupposes the capability, plus the candidate obligations "
            "extracted from that case.\n"
            "For each request, choose ALL candidate obligations that require the "
            "capability (the duty can be discharged only by an agent that possesses it). "
            "The text may name several, one, or none.\n"
            "Choose NONE (an empty list) when a named obligation does not correspond to "
            "any listed candidate (it was not separately extracted, or the text is a "
            "general phrase rather than one of the case's obligations). Match on the "
            "substance of the duty, not on shared wording alone.\n\n"
            "REQUESTS:\n" + "\n\n".join(blocks) +
            "\n\nOUTPUT strict JSON only, one entry per request id, each value a JSON "
            "array of the chosen candidate numbers (use [] for none): "
            "{\"<id>\": [<n>, ...], ...}"
        )
    return builder


def _temporal_prompt_factory(pred: EdgePredicate, spec: EdgeSpec):
    noun = pred.verb

    def builder(items: List[Dict[str, Any]]) -> str:
        blocks = []
        for it in items:
            cands = "; ".join(
                f"{i + 1}) {lbl[:90]}" for i, (iri, lbl, sim) in enumerate(it["shortlist"])
            )
            blocks.append(
                f"[{it['id']}] temporal relation: \"{(it.get('subj_label') or '')[:120]}\"\n"
                f"  text naming the happening that {noun}: \"{(it['desc'] or '')[:200]}\"\n"
                f"  candidate happenings: {cands}"
            )
        return (
            f"Each REQUEST gives a temporal (Allen interval) relation in an "
            f"engineering-ethics case and a free-text phrasing of the happening that "
            f"{noun}, plus the candidate action/event individuals in that case.\n"
            "The phrasing is a paraphrase of one happening (e.g. 'Engineer A preparing "
            "the summary memo' for the action 'Advisory Memo Preparation'). Choose the "
            "ONE candidate that denotes the SAME happening. Choose NONE (an empty list) "
            "when the phrasing describes a state/condition or no candidate is the same "
            "happening -- do NOT force a topical-but-different match.\n\n"
            "REQUESTS:\n" + "\n\n".join(blocks) +
            "\n\nOUTPUT strict JSON only, one entry per request id, each value a JSON "
            "array with the single chosen candidate number (use [] for none): "
            "{\"<id>\": [<n>], ...}"
        )
    return builder


# --- temporal-relation extra-read (owlprop, evidence) + extra-emit (time:) --

def _temporal_relation_extra_read(rdf: Dict[str, Any]) -> Dict[str, Any]:
    def _val(key):
        v = rdf.get(f"proeth:{key}")
        if isinstance(v, list):
            return "; ".join(str(x).strip() for x in v if str(x).strip())
        return str(v).strip() if v not in (None, "") else ""
    evidence = _val("evidence")
    return {"owlprop": _val("owlTimeProperty"), "evidence": evidence,
            "prov_desc": evidence or None}


def _temporal_relation_extra_emit(g: Graph, spec: EdgeSpec, subj, prop, tgt, row: SubjectRow) -> None:
    """Emit the OWL-Time assertion on the relation node once the TARGET (entity2) is
    resolved (Entity1 [relation] Entity2). Preserves the historical relation-node-anchored
    time:* shape, pointing at the real individual."""
    if prop != "toEntity":
        return
    owlprop = row.extra.get("owlprop") or ""
    local = owlprop.split(":")[-1] if owlprop else ""
    if local and (subj, TIME[local], tgt) not in g:
        g.add((subj, TIME[local], tgt))


# ===========================================================================
# THE REGISTRY -- the six data-driven families
# ===========================================================================

# resource_edges: Resource used_by -> availableTo (Agent), multi-select, Sonnet tier.
_RESOURCE_SPEC = EdgeSpec(
    name="resource_edges",
    extraction_type="resources",
    subject_category="Resource",
    predicates=(
        EdgePredicate("availableTo", CORE, ("usedBy", "used_by"), "Agent",
                      prompt_builder_factory=_resource_prompt_factory),
    ),
    prov_prefix="resource_edge_provenance_",
    prov_label=lambda p: f"Resource edge ({p})",
    prov_comment=lambda p: ("property=availableTo; resource used_by text resolved to the case Agent(s) "
                            "by embedding shortlist + LLM multi-select"),
    reader=_read_resources,
    pool_kind="agent",
    no_data_status="no_resource_usage",
)

# state_affects_edges: State affectedParties -> affects (Agent), multi-select.
_STATE_AFFECTS_SPEC = EdgeSpec(
    name="state_affects_edges",
    extraction_type="states",
    subject_category="State",
    predicates=(
        EdgePredicate("affects", CORE, ("affectedParties",), "Agent",
                      prompt_builder_factory=_state_affects_prompt_factory),
    ),
    prov_prefix="state_affects_provenance_",
    prov_label=lambda p: f"State edge ({p})",
    prov_comment=lambda p: ("property=affects; state affectedParties text resolved to the case Agent(s) "
                            "by embedding shortlist + LLM multi-select"),
    reader=_read_state_affects,
    pool_kind="agent",
    no_data_status="no_affected_parties",
)

# participant_edges: the Pass-2 'who' fields plus the actor-edge additions -> Component
# -> Agent. ADDITIVE (the literal stays untouched; this only ADDS the edge). Each
# predicate has its OWN subject category AND its own extraction_type. invokedBy and
# citedByAgent carry the deterministic Board-pattern fallback (the Board authors the
# analysis, so it is never an extracted case Agent); isPerformedBy reads the Step-3
# per-action hasAgent literal from the TEMPORAL rows (fluent-spec subject convention)
# with the role parenthetical stripped before resolution.
_PARTICIPANT_SPEC = EdgeSpec(
    name="participant_edges",
    extraction_type="",  # per-predicate (see subject_extraction_type)
    subject_category="",  # per-predicate
    predicates=(
        EdgePredicate("obligatedParty", CORE, ("obligatedParty", "obligated_party"), "Agent",
                      subject_category="Obligation", subject_extraction_type="obligations",
                      prompt_builder_factory=_participant_prompt_factory,
                      target_noun="obligation",
                      verb="BEARS the obligation (is the duty-bearer)"),
        EdgePredicate("constrainedEntity", CORE, ("constrainedEntity", "constrained_entity"), "Agent",
                      subject_category="Constraint", subject_extraction_type="constraints",
                      prompt_builder_factory=_participant_prompt_factory,
                      target_noun="constraint",
                      verb="is CONSTRAINED by it (whose conduct it limits)"),
        EdgePredicate("possessedBy", CORE, ("possessedBy", "possessed_by"), "Agent",
                      subject_category="Capability", subject_extraction_type="capabilities",
                      prompt_builder_factory=_participant_prompt_factory,
                      target_noun="capability",
                      verb="POSSESSES the capability"),
        EdgePredicate("invokedBy", CORE, ("invokedBy", "invoked_by"), "Agent",
                      subject_category="Principle", subject_extraction_type="principles",
                      prompt_builder_factory=_participant_prompt_factory,
                      target_noun="principle",
                      verb="INVOKES the principle (appeals to it to justify or evaluate conduct)",
                      board_agent_fallback=True),
        # Resource cited_by -> citedByAgent (the citing analytic authority; core
        # v2.6.0 actor-edge family, distinguished from availableTo = reliance).
        EdgePredicate("citedByAgent", CORE, ("citedBy", "cited_by"), "Agent",
                      subject_category="Resource", subject_extraction_type="resources",
                      prompt_builder_factory=_participant_prompt_factory,
                      target_noun="resource",
                      verb="CITED the resource as an authority in their ethical analysis",
                      board_agent_fallback=True),
        # Step-3 per-action hasAgent -> isPerformedBy (core declares the property and
        # the Action someValuesFrom restriction). Action subjects are stored under
        # extraction_type='temporal_dynamics_enhanced', NOT 'actions'.
        EdgePredicate("isPerformedBy", CORE, ("proeth:hasAgent", "hasAgent"), "Agent",
                      subject_category="Action",
                      subject_extraction_type="temporal_dynamics_enhanced",
                      row_shape="temporal", row_type_filter=("Action",),
                      normalize=_strip_role_parenthetical,
                      prompt_builder_factory=_participant_prompt_factory,
                      target_noun="action",
                      verb="PERFORMS the action (carries it out)"),
    ),
    prov_prefix="participant_edge_provenance_",
    prov_label=lambda p: f"Participant edge ({p})",
    prov_comment=lambda p: (f"property={p}; component party text resolved to the case Agent(s) "
                            "by embedding shortlist + LLM select"),
    reader=_read_participants,
    pool_kind="agent",
    no_data_status="no_parties",
)

# fluent_edges: Action/Event initiates|terminates -> State, multi-select, union subject pool.
_FLUENT_SPEC = EdgeSpec(
    name="fluent_edges",
    extraction_type="temporal_dynamics_enhanced",
    subject_category="",  # union
    subject_resolution="union",
    subject_union=("Action", "Event"),
    predicates=(
        EdgePredicate("initiates", CORE, ("proeth:initiates", "initiates"), "State",
                      pool_fields=("stateClass", "caseContext"),
                      prompt_builder_factory=_fluent_prompt_factory),
        EdgePredicate("terminates", CORE, ("proeth:terminates", "terminates"), "State",
                      pool_fields=("stateClass", "caseContext"),
                      prompt_builder_factory=_fluent_prompt_factory,
                      # Coherence guard (Stage-2 audit, Fable case-7 Design_Defect_Discovery
                      # initiated AND terminated the same two states): drop terminates when
                      # the same happening initiates the same state; keep initiates.
                      veto_if_present="initiates"),
    ),
    prov_prefix="fluent_edge_provenance_",
    prov_label=lambda p: f"Fluent edge ({p})",
    prov_comment=lambda p: (f"property={p}; happening's {p} state text resolved to the case State(s) by "
                            "embedding shortlist + LLM multi-select (Event Calculus fluent transition)"),
    reader=_read_temporal,
    no_data_status="no_fluent_transitions",
)

# obligation_edges: Action fulfills/violates/raises Obligation + guidedByPrinciple. All four
# land in CORE: fulfillsObligation was already core, and violates/raises/guidedByPrinciple were
# promoted from intermediate to core in v2.8.0 (the landed-edge namespace is governed here by the
# EdgePredicate namespace arg). The `fields` tuples keep the proeth: temp_rdf carrier-key names,
# which are the Step-3 JSON-LD field convention (unchanged), exactly as the already-core
# initiates/terminates fluent edges keep their proeth: carrier keys.
_OBLIGATION_SPEC = EdgeSpec(
    name="obligation_edges",
    extraction_type="temporal_dynamics_enhanced",
    subject_category="Action",
    type_filter=("Action",),
    predicates=(
        EdgePredicate("fulfillsObligation", CORE,
                      ("proeth:fulfillsObligation", "fulfillsObligation"), "Obligation",
                      pool_fields=("obligationStatement", "obligationClass"),
                      prompt_builder_factory=_obligation_prompt_factory),
        EdgePredicate("violatesObligation", CORE,
                      ("proeth:violatesObligation", "violatesObligation"), "Obligation",
                      pool_fields=("obligationStatement", "obligationClass"),
                      prompt_builder_factory=_obligation_prompt_factory),
        EdgePredicate("raisesObligation", CORE,
                      ("proeth:raisesObligation", "raisesObligation"), "Obligation",
                      pool_fields=("obligationStatement", "obligationClass"),
                      prompt_builder_factory=_obligation_prompt_factory),
        EdgePredicate("guidedByPrinciple", CORE,
                      ("proeth:guidedByPrinciple", "guidedByPrinciple"), "Principle",
                      pool_fields=("principleClass", "interpretation", "concreteExpression"),
                      prompt_builder_factory=_obligation_prompt_factory),
    ),
    prov_prefix="normative_edge_provenance_",
    prov_label=lambda p: f"Normative edge ({p})",
    prov_comment=lambda p: (f"property={p}; action's {p} text resolved to the case "
                            "Obligation/Principle individual(s) by embedding shortlist + LLM multi-select "
                            "(obligation-engagement grounding)"),
    reader=_read_temporal,
    no_data_status="no_normative_engagement",
)

# requires_capability_edges: the capability individuals' requiredForObligations labels
# -> Obligation proeth-core:requiresCapability Capability (INVERTED emission: the row
# subject is the Capability, the resolved Obligation is the edge subject, conforming to
# core v2.8.0 -- an obligation presupposes the capacity to discharge it). Labels resolve
# against the case's committed Obligation individuals only; both endpoint pools are
# built from materialized direct core types, and the unified guard validates both
# (Obligation and Capability are both among the nine disjoint categories).
_REQUIRES_CAPABILITY_SPEC = EdgeSpec(
    name="requires_capability_edges",
    extraction_type="capabilities",
    subject_category="Capability",
    predicates=(
        EdgePredicate("requiresCapability", CORE,
                      ("requiredForObligations", "required_for_obligations"), "Obligation",
                      pool_fields=("obligationStatement", "obligationClass"),
                      prompt_builder_factory=_requires_capability_prompt_factory,
                      invert=True,
                      target_noun="capability",
                      verb="requires the capability (its discharge presupposes it)"),
    ),
    prov_prefix="capability_requirement_provenance_",
    prov_label=lambda p: f"Capability requirement edge ({p})",
    prov_comment=lambda p: ("property=requiresCapability; capability requiredForObligations text "
                            "resolved to the case Obligation(s) by embedding shortlist + LLM "
                            "multi-select; emitted Obligation -> Capability (the obligation "
                            "presupposes the capacity to discharge it)"),
    reader=_read_capability_requirements,
    no_data_status="no_capability_requirements",
)

# temporal_relation_edges: TemporalRelation fromEntity/toEntity -> Action|Event, single-valued,
# subject by rdf:type, plus the time:<allenProp> extra triple on toEntity.
_TEMPORAL_RELATION_SPEC = EdgeSpec(
    name="temporal_relation_edges",
    extraction_type="temporal_dynamics_enhanced",
    subject_category="",  # by rdf:type
    subject_resolution="type",
    subject_type=PROETH.TemporalRelation,
    type_filter=("TemporalRelation",),
    predicates=(
        EdgePredicate("fromEntity", PROETH, ("fromEntity",), "Action",
                      range_union=("Action", "Event"),
                      prompt_builder_factory=_temporal_prompt_factory,
                      verb="is the SOURCE happening (Entity1 in 'Entity1 [relation] Entity2')"),
        EdgePredicate("toEntity", PROETH, ("toEntity",), "Action",
                      range_union=("Action", "Event"),
                      prompt_builder_factory=_temporal_prompt_factory,
                      verb="is the TARGET happening (Entity2 in 'Entity1 [relation] Entity2')"),
    ),
    prov_prefix="temporal_relation_edge_provenance_",
    prov_label=lambda p: f"Temporal relation edge ({p})",
    prov_comment=lambda p: (f"property={p}; temporal relation's {p} text resolved to the case "
                            "Action/Event individual by embedding shortlist + LLM select"),
    reader=_read_temporal,
    single_valued=True,
    extra_read=_temporal_relation_extra_read,
    extra_emit=_temporal_relation_extra_emit,
    no_data_status="no_temporal_relations",
)


EDGE_REGISTRY: List[EdgeSpec] = [
    _RESOURCE_SPEC,
    _STATE_AFFECTS_SPEC,
    _PARTICIPANT_SPEC,
    _REQUIRES_CAPABILITY_SPEC,
    _FLUENT_SPEC,
    _OBLIGATION_SPEC,
    _TEMPORAL_RELATION_SPEC,
]
