"""State-anchored edge materialization (DB-driven, embedding-resolved).

The state extractor produces class-level linkage fields that encode the
methodology's semi-algorithmic, literature-grounded relationships:

  - obligation_activation  (S->O):  which obligations a state makes applicable
  - action_constraints     (S->Cs): which constraints a state activates
  - activation_conditions  (Event Calculus): the events that initiate the state
  - termination_conditions (Event Calculus): the events that end the state
  - principle_transformation (S->P->O): how the state transforms a principle

These were extracted but never wired into anything: dropped at commit and unused
downstream, while the defeasibility/RPO extractors re-derived overlapping
relationships from scratch. This applier WIRES THEM IN. It reads the extracted
state fields from temporary_rdf_storage (the class-level linkage fields are not in
the committed TTL; triggering_event and terminated_by are also kept as literals),
resolves each free-text description to the matching case individual via embedding
similarity, and materializes first-class proeth-core edges with PROV-O provenance:

  S proeth-core:activatesObligation O
  S proeth-core:activatesConstraint Cs
  S proeth-core:activatedByEvent     E
  S proeth-core:terminatedByEvent    E

plus a proeth:principleTransformation annotation carrying the S->P->O narrative
(also fed to the RPO derivation as grounding; see rpo_edges).

Case 24-1 review (October 2026) rules carried here:

  - the class row of an individual is found by its stateClass literal or its
    matched_ontology_uri, never by an embedding over the other class rows; an
    individual whose class row was deleted keeps its own trigger and
    termination fields and inherits no class-level linkage
  - activation and termination candidates include Actions as well as Events; a
    selected Action is emitted in the Event Calculus direction (Action
    initiates / terminates State), since activatedByEvent and terminatedByEvent
    range over Event
  - only the individual's terminated_by feeds terminatedByEvent (class-level
    termination_conditions are hypothetical), and a literal that begins "Not
    terminated" / "Not fully terminated" resolves to nothing
  - a sequence-aware coherence check drops an activation that precedes the
    state's own trigger and a termination that a later happening contradicts
  - an obligation_activation description that cites a code section resolves by
    provision match against the obligations' text references before the
    embedding shortlist, a description that names a duty with no lexically
    matching individual resolves to nothing, and select diagnostics are
    persisted for every unresolved request

Best-effort, like the other appliers: failures are logged and returned, never
raised, so edge materialization can never fail a commit. Unresolved descriptions
are logged with their best similarity (no silent drops).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from rdflib import Graph, Literal, Namespace, RDF, URIRef

# The embedding / graph / shortlist / LLM-select / provenance primitives now live in
# the shared edge_resolution module (moved verbatim, de-duplicated across the appliers).
# Re-imported here so the historical state_edges import surface is preserved: sibling
# appliers, time_anchor (_safe_frag), and the unit tests import these names off
# state_edges, and that keeps resolving to the one shared implementation.
from app.services.extraction.edge_resolution import (  # noqa: F401  (re-exported)
    _candidate_pool,
    _cosine,
    _embed,
    _embedding_service,
    _individuals_in_category,
    _label,
    _lit,
    _llm_select as _llm_select_generic,
    _norm,
    _resolve,
    _safe_frag,
    _shortlist,
    emit_edge_prov,
    remove_edge_prov,
)
from app.services.extraction.edge_coherence import (
    FLUENT_PROV_PREFIX,
    GENERIC_DUTY_WORDS,
    STATE_PROV_PREFIX,
    activation_precedes_trigger,
    later_happening_citing_state,
    lexical_candidates,
    names_duty,
)

logger = logging.getLogger(__name__)

CORE = Namespace("http://proethica.org/ontology/core#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
PROV = Namespace("http://www.w3.org/ns/prov#")
PROETH_PROV = Namespace("http://proethica.org/provenance#")

# Cosine thresholds for resolving a free-text linkage description to a case
# individual, calibrated on 483 descriptions across cases 5/7/8/15/17 (the local
# all-MiniLM-L6-v2 model). Two regimes were found: abstract obligation/constraint
# descriptions match their specific individual (whose label carries actor names,
# diluting the cosine) at ~0.85-0.90 precision down to ~0.53; event resolution is
# noisier (activation/termination conditions are often hypothetical and the
# embedding is polarity-blind, e.g. "risk mitigated" matches the risk-emergence
# event), so it needs a higher bar (~0.60). Unresolved descriptions are logged
# with their best similarity.
EMBED_MATCH_MIN = 0.53  # default / obligation+constraint resolution
_FIELD_THRESHOLD = {
    "activatesObligation": 0.53,
    "activatesConstraint": 0.53,
    "activatedByEvent": 0.60,
    "terminatedByEvent": 0.60,
}

# Hybrid resolution: embedding shortlists the top-K candidates above a low floor
# (cheap pre-filter that keeps the LLM prompt small), then one batched LLM call
# per case selects the right candidate (or "none") with direction/polarity
# awareness that embedding cosines lack. Falls back to the calibrated embedding
# threshold above if the LLM is unavailable.
SHORTLIST_FLOOR = 0.40
SHORTLIST_K = 5

_PROP_SEMANTICS = {
    "activatesObligation": "the OBLIGATION this state makes applicable (S->O)",
    "activatesConstraint": "the CONSTRAINT this state activates (S->Cs)",
    "activatedByEvent": "the HAPPENING (event or action) whose occurrence STARTS/initiates this state",
    "terminatedByEvent": "the HAPPENING (event or action) whose occurrence ENDS/terminates this state",
}

# A selected Action cannot be the target of activatedByEvent / terminatedByEvent
# (range Event); the same transition is emitted in the Event Calculus direction.
_ACTION_REDIRECT = {"activatedByEvent": "initiates", "terminatedByEvent": "terminates"}
_PROPS = ("activatesObligation", "activatesConstraint", "activatedByEvent", "terminatedByEvent")

_NOT_TERMINATED = re.compile(r"^\s*not\s+(?:fully\s+|yet\s+)?terminated\b", re.I)


def _is_not_terminated(literal: str) -> bool:
    """A terminated_by literal that says the state persists ("Not terminated",
    "Not fully terminated ...") names no terminator and short-circuits resolution."""
    return bool(_NOT_TERMINATED.match(literal or ""))


# --- batched LLM confirm/select (the hybrid precision layer) ----------------

def _build_select_prompt(items: List[Dict[str, Any]]) -> str:
    blocks = []
    for it in items:
        cands = "; ".join(f"{i + 1}) {lbl[:90]}" for i, (iri, lbl, sim) in enumerate(it["shortlist"]))
        blocks.append(
            f"[{it['id']}] {_PROP_SEMANTICS.get(it['prop'], it['prop'])}\n"
            f"  description: \"{(it['desc'] or '')[:200]}\"\n"
            f"  candidates: {cands}"
        )
    return (
        "For each REQUEST, choose the ONE candidate its description refers to, or "
        "\"none\" when no candidate truly fits.\n"
        "Respect DIRECTION and POLARITY: a 'STARTS/initiates' request needs the "
        "happening whose occurrence brings the state into being; an 'ENDS/terminates' "
        "request needs the happening that removes it. Do NOT match an ending or "
        "mitigation condition to an onset event merely because they share a topic "
        "(e.g. 'risk is mitigated' is NOT 'risk emerges'). Choose \"none\" when the "
        "description is hypothetical, when it says the state persists, or when no "
        "candidate genuinely matches; \"none\" is always an acceptable answer.\n\n"
        "REQUESTS:\n" + "\n\n".join(blocks) +
        "\n\nOUTPUT strict JSON only, one entry per request id: "
        "{\"<id>\": <candidate number>|\"none\", ...}\n"
        "The mapping must be the TOP-LEVEL JSON object (no wrapper key) and "
        "must include an entry for EVERY request id above."
    )


def _llm_select(items: List[Dict[str, Any]], client=None, model=None, diag=None):
    """Map each item id -> chosen candidate IRI (or None) via a 3-vote majority
    on the default tier. Returns the selection dict, or None if the LLM is
    unavailable / every vote fails (the caller then falls back to the
    embedding threshold).

    Calibration (2026-07-11, the activatesObligation-instability fix; measured
    in a controlled 5x-repeatability experiment on cases 58 and 9):

    - Tier: default (Sonnet), NOT fast. The tiers sit at different operating
      points, not just different noise levels -- on case 9 the fast tier chose
      ZERO activatesObligation targets in all five runs while the default tier
      chose the same two in all five (matching the committed gold graph). Same
      direction-reading failure family that moved resource_edges' multi-select
      off the fast tier.
    - Votes: 3, per-item strict majority. Both tiers flip run to run as single
      calls (2-4 distinct selection sets of 5 at temperature 0.0), so voting,
      not tier choice, is what pins the modal judgment. The three identical
      prompts share a cached prefix, so the marginal cost is ~2 cache reads.
    """
    return _llm_select_generic(items, _build_select_prompt, client=client, model=model,
                               model_tier="default", votes=3, diag=diag)


# --- temp_rdf (DB) linkage read --------------------------------------------

def _state_linkage_from_db(case_id: int):
    """(state_classes, state_individuals) linkage data from temporary_rdf_storage.

    The class-level linkage fields are not committed to the TTL, so they are read
    here from the extraction rows. Class rows carry their entity_uri and
    individual rows their matched_ontology_uri, so an individual can be joined to
    its class row by identity when the stateClass literal does not match."""
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    def _props(row):
        return ((row.rdf_json_ld or {}).get("properties") or {})

    def _list(props, *keys):
        for k in keys:
            v = props.get(k)
            if v:
                return v if isinstance(v, list) else [v]
        return []

    def _str(props, *keys):
        vals = _list(props, *keys)
        return str(vals[0]) if vals else ""

    rows = TemporaryRDFStorage.query.filter_by(case_id=case_id, extraction_type="states").all()
    classes, individuals = [], []
    for r in rows:
        p = _props(r)
        if r.storage_type == "class":
            classes.append({
                "label": r.entity_label or "",
                "uri": getattr(r, "entity_uri", None) or "",
                "definition": r.entity_definition or "",
                "obligation_activation": [str(x) for x in _list(p, "obligationActivation", "obligation_activation")],
                "action_constraints": [str(x) for x in _list(p, "actionConstraints", "action_constraints")],
                "activation_conditions": [str(x) for x in _list(p, "activationConditions", "activation_conditions")],
                "termination_conditions": [str(x) for x in _list(p, "terminationConditions", "termination_conditions")],
                "principle_transformation": _str(p, "principleTransformation", "principle_transformation"),
            })
        elif r.storage_type == "individual":
            individuals.append({
                "label": r.entity_label or "",
                "definition": r.entity_definition or "",
                "state_class": _str(p, "stateClass", "state_class"),
                "matched_ontology_uri": getattr(r, "matched_ontology_uri", None) or "",
                "triggering_event": _str(p, "triggeringEvent", "triggering_event"),
                "terminated_by": _str(p, "terminatedBy", "terminated_by"),
            })
    return classes, individuals


def _best_class(indiv: Dict[str, Any], classes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The class row an individual belongs to, by its own evidence only: the
    stateClass literal (normalized label match), then the matched_ontology_uri
    (identity with the class row's uri, or its fragment against the class label).
    When the individual names no class at all and a single class row exists, that
    row is taken. Otherwise None: an individual whose class row was deleted (an
    auto merge) inherits no linkage from a neighbouring class, which is what an
    embedding fallback did on case 8 (Confirmed Runoff Risk Finding received the
    principleTransformation and activation edges of Public Safety Risk State)."""
    sc = _norm(indiv.get("state_class") or "")
    if sc:
        for c in classes:
            if _norm(c.get("label") or "") == sc:
                return c
    uri = (indiv.get("matched_ontology_uri") or "").strip()
    if uri:
        frag = _norm(uri.rsplit("#", 1)[-1].rsplit("/", 1)[-1])
        for c in classes:
            c_uri = (c.get("uri") or "").strip()
            if c_uri and c_uri == uri:
                return c
            if c_uri and _norm(c_uri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]) == frag:
                return c
            if frag and _norm(c.get("label") or "") == frag:
                return c
    if not sc and not uri and len(classes) == 1:
        return classes[0]
    return None


# --- provenance (idempotent, mirrors defeasibility/relationship prov) -------
# emit_edge_prov / remove_edge_prov / _safe_frag now live in edge_resolution and are
# re-imported above; only the state-specific label/comment wrapper stays here.

def _emit_prov(g: Graph, case_id: int, subj, prop: str, obj, desc: str,
               method: str = "embedding shortlist + LLM select") -> None:
    emit_edge_prov(g, case_id, STATE_PROV_PREFIX, prop, subj, obj, desc,
                   f"State edge ({prop})",
                   f"property={prop}; description resolved to the endpoint by {method}")


def _emit_state_edge(g: Graph, case_id: int, res: Dict[str, Any], subj, prop: str, tgt,
                     desc: str, method: str = "embedding shortlist + LLM select") -> Optional[str]:
    """Add the resolved edge. An Action target of activatedByEvent / terminatedByEvent
    is emitted as Action initiates / terminates State (the Event Calculus direction,
    under the fluent family's provenance prefix so the fluent coherence passes
    govern it). Returns the property local name emitted, or None when the edge
    already existed."""
    if prop in _ACTION_REDIRECT and (tgt, RDF.type, CORE.Action) in g:
        fprop = _ACTION_REDIRECT[prop]
        if (tgt, CORE[fprop], subj) in g:
            return None
        g.add((tgt, CORE[fprop], subj))
        emit_edge_prov(
            g, case_id, FLUENT_PROV_PREFIX, fprop, tgt, subj, desc,
            f"Fluent edge ({fprop})",
            f"property={fprop}; the state's {prop} description named an Action, so the "
            "transition is emitted in the Event Calculus direction (activatedByEvent / "
            f"terminatedByEvent range over Event); description resolved by {method}")
        res[fprop] = res.get(fprop, 0) + 1
        return fprop
    if (subj, CORE[prop], tgt) in g:
        return None
    g.add((subj, CORE[prop], tgt))
    _emit_prov(g, case_id, subj, prop, tgt, desc, method)
    res[prop] += 1
    return prop


def _remove_state_edge(g: Graph, case_id: int, res: Dict[str, Any], subj, prop_emitted: str, tgt) -> None:
    """Remove an edge this run emitted (either direction) with its provenance."""
    if prop_emitted in ("initiates", "terminates"):
        g.remove((tgt, CORE[prop_emitted], subj))
        remove_edge_prov(g, case_id, FLUENT_PROV_PREFIX, prop_emitted, tgt, subj)
    else:
        g.remove((subj, CORE[prop_emitted], tgt))
        remove_edge_prov(g, case_id, STATE_PROV_PREFIX, prop_emitted, subj, tgt)
    res[prop_emitted] = max(0, res.get(prop_emitted, 0) - 1)
    res["incoherent_dropped"] += 1


# --- provision match + duty-name guard (activatesObligation) ----------------

def _obligation_provisions(g: Graph, provision_texts: Optional[Dict[str, str]] = None) -> Dict[URIRef, Set[str]]:
    """Obligation individual -> the nspe fragments its literals attest: dotted codes
    found in its textReferences / obligationStatement / caseContext, plus, when
    ``provision_texts`` (fragment -> provision sentence) is supplied, every
    provision whose sentence a text reference quotes."""
    from app.services.extraction.provision_citation_resolver import extract_provision_fragments
    from app.services.extraction.edge_coherence import evidence_is_verbatim
    out: Dict[URIRef, Set[str]] = {}
    for o in _individuals_in_category(g, "Obligation"):
        frags: Set[str] = set()
        refs = [str(x) for x in g.objects(o, PROETH.textReferences)]
        for pred in (PROETH.textReferences, PROETH.obligationStatement, PROETH.caseContext):
            for lit in g.objects(o, pred):
                frags.update(extract_provision_fragments(str(lit)))
        if provision_texts and refs:
            for frag, text in provision_texts.items():
                if text and any(evidence_is_verbatim(r, text) or evidence_is_verbatim(text, r)
                                for r in refs):
                    frags.add(frag)
        if frags:
            out[o] = frags
    return out


def _load_provision_texts(frags: Set[str]) -> Dict[str, str]:
    """fragment -> NSPE provision text from the live guideline_sections table (best
    effort: an empty mapping outside an app context or without a database)."""
    if not frags:
        return {}
    try:
        from app.models.guideline_section import GuidelineSection
        out: Dict[str, str] = {}
        for row in GuidelineSection.query.filter_by(guideline_id=1).all():
            frag = (row.section_code or "").replace(".", "_")
            if frag in frags and row.section_text:
                out[frag] = row.section_text
        return out
    except Exception:  # noqa: BLE001
        return {}


def _persist_select_diagnostics(case_id: int, diag: Dict[str, Any], res: Dict[str, Any],
                                items: List[Dict[str, Any]],
                                unresolved: List[Dict[str, Any]],
                                saver: Optional[Callable[..., Any]] = None) -> bool:
    """Persist the select prompt, the raw votes, and one record per unresolved
    request (property, description, reason, shortlist) as an extraction_prompts
    history row. Previously written only when a whole property family resolved
    zero, which left a single wrong or missing pick undiagnosable after the
    once-only rebuild. Best-effort: never fails the applier."""
    if not unresolved:
        return False
    zero_props = [p for p in _PROPS if res[p] == 0 and any(it["prop"] == p for it in items)]
    try:
        if saver is None:
            from app.models.extraction_prompt import ExtractionPrompt
            saver = ExtractionPrompt.save_prompt
        saver(
            case_id=case_id, concept_type="state_edges_select",
            prompt_text=(diag.get("prompt")
                         or "(no select prompt was issued: every unresolved request failed "
                            "before the model)"),
            # 'temporal' is the section bucket the valid_section_type check
            # constraint provides for the edge/temporal layer.
            step_number=0, section_type="temporal",
            llm_model=str(diag.get("model") or ""),
            results_summary={
                "resolver": res.get("resolver"),
                "zero_resolved_props": zero_props,
                "counts": {p: res[p] for p in _PROPS},
                "items": len(items), "unresolved": res["unresolved"],
                "unresolved_requests": unresolved[:200],
            },
            raw_response="\n\n=== VOTE ===\n\n".join(diag.get("raws") or [])[:200000],
        )
        return True
    except Exception:  # noqa: BLE001
        # Roll back or the failed INSERT poisons the shared session for every
        # later query in this commit (the similarity_service archetype).
        try:
            from app.models import db
            db.session.rollback()
        except Exception:  # noqa: BLE001
            pass
        logger.warning("state_edges: select diagnostics persistence failed (best-effort)",
                       exc_info=True)
        return False


# --- main applier ----------------------------------------------------------

def apply_state_edges(case_id: int, ttl_path, write_back: bool = True,
                      threshold: float = EMBED_MATCH_MIN, use_llm: bool = True,
                      llm_client=None, model=None,
                      diagnostics_saver: Optional[Callable[..., Any]] = None,
                      provision_text_loader: Optional[Callable[[Set[str]], Dict[str, str]]] = None
                      ) -> Dict[str, Any]:
    """Materialize state-anchored edges on a just-written case TTL (in place).

    Reads the extracted state linkage fields from temporary_rdf_storage, resolves
    each free-text description to a case individual (embedding shortlist + one
    batched LLM confirm/select per case; embedding-threshold fallback when the LLM
    is unavailable or use_llm=False), and adds the proeth-core State edges +
    provenance. Returns per-property counts, the resolver used, and the number of
    unresolved descriptions (logged individually and persisted as diagnostics)."""
    ttl_path = Path(ttl_path)
    res: Dict[str, Any] = {
        "case_id": case_id, "status": "ok", "resolver": None,
        "activatesObligation": 0, "activatesConstraint": 0,
        "activatedByEvent": 0, "terminatedByEvent": 0,
        "initiates": 0, "terminates": 0,
        "principleTransformation": 0, "unresolved": 0,
        "class_unresolved": 0, "not_terminated": 0, "provision_matched": 0,
        "incoherent_dropped": 0, "diagnostics_persisted": False,
    }
    try:
        classes, individuals = _state_linkage_from_db(case_id)
    except Exception as e:
        logger.warning("state_edges: could not read temp_rdf for case %s: %s", case_id, e)
        return {"case_id": case_id, "status": "no_db", "error": str(e)}
    if not classes and not individuals:
        return {"case_id": case_id, "status": "no_state_data"}

    g = Graph()
    g.parse(str(ttl_path), format="turtle")
    svc = _embedding_service()

    # Activation / termination candidates are the happenings: Events AND Actions
    # (case 8: "Client insists on proceeding without added safeguards" names the
    # Action Safeguard_Refusal; an Event-only pool forced the wrong Event).
    happening_pool = (_candidate_pool(g, svc, "Event", ["eventclass", "description"])
                      + _candidate_pool(g, svc, "Action", ["description"]))
    pools = {
        "activatesObligation": _candidate_pool(g, svc, "Obligation", ["obligationstatement", "obligationclass"]),
        "activatesConstraint": _candidate_pool(g, svc, "Constraint", ["constraintstatement", "constraintclass"]),
        "activatedByEvent": happening_pool,
        "terminatedByEvent": happening_pool,
    }
    obligation_labels = {iri: _label(g, iri) for iri, _t, _e in pools["activatesObligation"]}

    state_iris: Dict[str, URIRef] = {}
    for ind in _individuals_in_category(g, "State"):
        state_iris.setdefault(_norm(_label(g, ind)), ind)

    # Provision match grounding: the obligations' attested code sections, plus the
    # provision sentences for the codes the activation descriptions cite.
    from app.services.extraction.provision_citation_resolver import extract_provision_fragments
    cited: Set[str] = set()
    for c in classes:
        for d in c["obligation_activation"]:
            cited.update(extract_provision_fragments(d))
    loader = provision_text_loader or _load_provision_texts
    obligation_provisions = _obligation_provisions(g, loader(cited) if cited else None)

    # Pass A: build resolution items (description + embedding shortlist).
    items: List[Dict[str, Any]] = []
    unresolved_requests: List[Dict[str, Any]] = []
    direct: List[Dict[str, Any]] = []   # deterministic resolutions (provision match)
    next_id = 1

    def _unresolved(prop, desc, reason, shortlist=None):
        res["unresolved"] += 1
        unresolved_requests.append({
            "prop": prop, "desc": (desc or "")[:300], "reason": reason,
            "shortlist": [str(lbl)[:90] for _i, lbl, _s in (shortlist or [])]})
        logger.info("state_edges: %s unresolved (%s): %r", prop, reason, (desc or "")[:80])

    def _collect(subj, prop, descs, is_trigger=False):
        nonlocal next_id
        pool = pools[prop]
        for desc in descs:
            if not desc:
                continue
            if prop == "activatesObligation":
                frags = set(extract_provision_fragments(desc))
                if frags:
                    hits = [o for o, fr in obligation_provisions.items() if fr & frags]
                    if len(hits) == 1:
                        direct.append({"subj": subj, "prop": prop, "desc": desc, "tgt": hits[0],
                                       "method": "provision match against the obligation's "
                                                 "text references (no embedding or LLM)"})
                        res["provision_matched"] += 1
                        continue
                    if len(hits) > 1:
                        pool = [p for p in pool if p[0] in set(hits)]
                if names_duty(desc):
                    cands = set(lexical_candidates(desc, obligation_labels, drop=GENERIC_DUTY_WORDS))
                    if not cands:
                        _unresolved(prop, desc, "names a duty with no extracted individual")
                        continue
                    pool = [p for p in pool if p[0] in cands]
            sl = _shortlist(svc, desc, pool, SHORTLIST_FLOOR, SHORTLIST_K)
            if not sl:
                _unresolved(prop, desc, f"no candidate above floor {SHORTLIST_FLOOR:.2f}")
                continue
            items.append({"id": next_id, "prop": prop, "subj": subj, "desc": desc,
                          "shortlist": sl, "is_trigger": is_trigger})
            next_id += 1

    for indiv in individuals:
        subj = state_iris.get(_norm(indiv["label"]))
        if subj is None:
            continue  # state individual not present in the committed graph
        cls = _best_class(indiv, classes)
        if cls is None:
            res["class_unresolved"] += 1
            logger.info("state_edges: no class row for state %r (stateClass=%r, matched=%r); "
                        "class-level linkage skipped", indiv["label"][:80],
                        indiv.get("state_class"), indiv.get("matched_ontology_uri"))
        else:
            _collect(subj, "activatesObligation", cls["obligation_activation"])
            _collect(subj, "activatesConstraint", cls["action_constraints"])
            _collect(subj, "activatedByEvent", cls["activation_conditions"])
            if cls["principle_transformation"] and (subj, PROETH.principleTransformation, None) not in g:
                g.add((subj, PROETH.principleTransformation, Literal(cls["principle_transformation"])))
                # The applier runs after the serializer wrote the synthesisLiteral
                # marker, so the marker is extended here or it under-reports this
                # kept literal (correspondence audit T2).
                g.add((subj, PROETH_PROV.synthesisLiteral, Literal("principleTransformation")))
                res["principleTransformation"] += 1
        if indiv["triggering_event"]:
            _collect(subj, "activatedByEvent", [indiv["triggering_event"]], is_trigger=True)
        # Only the individual's own terminated_by feeds termination: the class-level
        # termination_conditions are hypothetical ("would end if ..."), and a literal
        # that says the state persists names no terminator.
        if indiv["terminated_by"]:
            if _is_not_terminated(indiv["terminated_by"]):
                res["not_terminated"] += 1
                logger.info("state_edges: %r is not terminated (%r); no termination request",
                            indiv["label"][:80], indiv["terminated_by"][:80])
            else:
                _collect(subj, "terminatedByEvent", [indiv["terminated_by"]])

    # Pass B: batched LLM confirm/select over the shortlists (hybrid precision
    # layer; 3-vote majority on the default tier since the 2026-07-11
    # calibration); embedding-threshold fallback when the LLM is unavailable.
    diag: Dict[str, Any] = {}
    selections = _llm_select(items, client=llm_client, model=model, diag=diag) if use_llm else None
    res["resolver"] = "llm" if selections is not None else "embedding"

    # Pass C: emit the resolved edges + provenance.
    for d in direct:
        _emit_state_edge(g, case_id, res, d["subj"], d["prop"], d["tgt"], d["desc"], d["method"])

    emitted_starts: Dict[URIRef, List[tuple]] = {}   # subj -> [(prop_emitted, tgt, is_trigger)]
    emitted_ends: Dict[URIRef, List[tuple]] = {}
    trigger_target: Dict[URIRef, URIRef] = {}
    for it in items:
        subj, prop, desc, sl = it["subj"], it["prop"], it["desc"], it["shortlist"]
        if selections is not None:
            tgt = selections.get(str(it["id"]))
        else:
            thr = _FIELD_THRESHOLD.get(prop, threshold)
            tgt = sl[0][0] if (sl and sl[0][2] >= thr) else None
        if tgt is None:
            _unresolved(prop, desc, f"select answered none (resolver={res['resolver']})", sl)
            continue
        if it.get("is_trigger"):
            trigger_target[subj] = tgt
        emitted = _emit_state_edge(g, case_id, res, subj, prop, tgt, desc)
        if prop == "activatedByEvent":
            emitted_starts.setdefault(subj, []).append((emitted, tgt, bool(it.get("is_trigger"))))
        elif prop == "terminatedByEvent":
            emitted_ends.setdefault(subj, []).append((emitted, tgt))

    # Sequence-aware coherence: an activation cannot precede the state's own
    # trigger (case 8: a class-level condition resolved to an event seven steps
    # earlier than the trigger), and a state a later happening cites as holding
    # is not terminated earlier.
    for subj, starts in emitted_starts.items():
        trig = trigger_target.get(subj)
        if trig is None:
            continue
        for prop_emitted, tgt, is_trigger in starts:
            if is_trigger or prop_emitted is None or tgt == trig:
                continue
            if activation_precedes_trigger(g, tgt, trig):
                _remove_state_edge(g, case_id, res, subj, prop_emitted, tgt)
                logger.info("state_edges: dropped activation of %s by %s: it precedes the "
                            "state's trigger %s", _safe_frag(subj), _safe_frag(tgt), _safe_frag(trig))
    for subj, ends in emitted_ends.items():
        for prop_emitted, tgt in ends:
            if prop_emitted is None:
                continue
            later = later_happening_citing_state(g, subj, tgt)
            if later is not None:
                _remove_state_edge(g, case_id, res, subj, prop_emitted, tgt)
                logger.info("state_edges: dropped termination of %s by %s: the later happening "
                            "%s cites the state as holding", _safe_frag(subj), _safe_frag(tgt),
                            _safe_frag(later))

    # Diagnosability (case 24-1 review): persist the select prompt, the raw votes,
    # and every unresolved request, not only a whole-family zero outcome.
    if unresolved_requests:
        res["diagnostics_persisted"] = _persist_select_diagnostics(
            case_id, diag, res, items, unresolved_requests, saver=diagnostics_saver)

    added = sum(res[k] for k in ("activatesObligation", "activatesConstraint",
                                 "activatedByEvent", "terminatedByEvent",
                                 "initiates", "terminates", "principleTransformation"))
    if write_back and (added or res["incoherent_dropped"]):
        g.serialize(destination=str(ttl_path), format="turtle")
    return res
