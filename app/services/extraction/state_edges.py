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
state fields from temporary_rdf_storage (they are not in the committed TTL),
resolves each free-text description to the matching case individual via embedding
similarity, and materializes first-class proeth-core edges with PROV-O provenance:

  S proeth-core:activatesObligation O
  S proeth-core:activatesConstraint Cs
  S proeth-core:activatedByEvent     E
  S proeth-core:terminatedByEvent    E

plus a proeth:principleTransformation annotation carrying the S->P->O narrative
(also fed to the RPO derivation as grounding; see rpo_edges).

Best-effort, like the other appliers: failures are logged and returned, never
raised, so edge materialization can never fail a commit. Unresolved descriptions
are logged with their best similarity (no silent drops).
"""
from __future__ import annotations

import logging
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import XSD

logger = logging.getLogger(__name__)

CORE = Namespace("http://proethica.org/ontology/core#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
PROV = Namespace("http://www.w3.org/ns/prov#")

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


# --- embedding helpers -----------------------------------------------------

def _embedding_service():
    from app.services.embedding_service import EmbeddingService
    return EmbeddingService.get_instance()


def _embed(svc, text: str) -> Optional[List[float]]:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return svc.get_embedding(text)
    except Exception as e:  # never raise out of an applier
        logger.warning("state_edges: embedding failed for %r: %s", text[:60], e)
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
    return [s for s, _, _ in g.triples((None, PROETH.conceptCategory, Literal(category)))]


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


# --- temp_rdf (DB) linkage read --------------------------------------------

def _state_linkage_from_db(case_id: int):
    """(state_classes, state_individuals) linkage data from temporary_rdf_storage.

    The class-level linkage fields are not committed to the TTL, so they are read
    here from the extraction rows."""
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
                "triggering_event": _str(p, "triggeringEvent", "triggering_event"),
                "terminated_by": _str(p, "terminatedBy", "terminated_by"),
            })
    return classes, individuals


# --- provenance (idempotent, mirrors defeasibility/relationship prov) -------

def _safe_frag(iri) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", str(iri).split("#")[-1])


def _emit_prov(g: Graph, case_id: int, subj, prop: str, obj, desc: str) -> None:
    case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")
    prov_iri = case_ns["state_edge_provenance_" + _safe_frag(subj) + "_" + prop + "_" + _safe_frag(obj)]
    if (prov_iri, RDF.type, PROV.Derivation) in g:
        return
    g.add((prov_iri, RDF.type, PROV.Derivation))
    g.add((prov_iri, PROV.wasDerivedFrom, subj))
    g.add((prov_iri, PROV.wasDerivedFrom, obj))
    g.add((prov_iri, RDFS.label, Literal(f"State edge ({prop})")))
    if desc:
        g.add((prov_iri, PROV.value, Literal(str(desc))))
    g.add((prov_iri, RDFS.comment, Literal(f"property={prop}; resolved by embedding similarity")))


# --- main applier ----------------------------------------------------------

def apply_state_edges(case_id: int, ttl_path, write_back: bool = True,
                      threshold: float = EMBED_MATCH_MIN) -> Dict[str, Any]:
    """Materialize state-anchored edges on a just-written case TTL (in place).

    Reads the extracted state linkage fields from temporary_rdf_storage, resolves
    each description to a case individual by embedding similarity, and adds the
    proeth-core State edges + provenance. Returns per-property counts and the
    number of unresolved descriptions (logged individually)."""
    ttl_path = Path(ttl_path)
    res: Dict[str, Any] = {
        "case_id": case_id, "status": "ok",
        "activatesObligation": 0, "activatesConstraint": 0,
        "activatedByEvent": 0, "terminatedByEvent": 0,
        "principleTransformation": 0, "unresolved": 0,
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

    obl_pool = _candidate_pool(g, svc, "Obligation", ["obligationstatement", "obligationclass"])
    cons_pool = _candidate_pool(g, svc, "Constraint", ["constraintstatement", "constraintclass"])
    evt_pool = _candidate_pool(g, svc, "Event", ["eventclass", "description"])

    state_iris: Dict[str, URIRef] = {}
    for ind in _individuals_in_category(g, "State"):
        state_iris.setdefault(_norm(_label(g, ind)), ind)

    class_emb = [(c, _embed(svc, (c["label"] + " . " + c["definition"]))) for c in classes]

    def _best_class(indiv):
        sc = _norm(indiv["state_class"])
        for c in classes:
            if sc and _norm(c["label"]) == sc:
                return c
        if len(classes) == 1:
            return classes[0]
        iv = _embed(svc, indiv["label"] + " . " + indiv["definition"])
        if not iv:
            return None
        best, bs = None, -1.0
        for c, ce in class_emb:
            if not ce:
                continue
            sim = _cosine(iv, ce)
            if sim > bs:
                best, bs = c, sim
        return best

    def _emit(subj, prop, desc, pool):
        thr = _FIELD_THRESHOLD.get(prop, threshold)
        tgt, sim = _resolve(svc, desc, pool, thr)
        if tgt is None:
            res["unresolved"] += 1
            logger.info("state_edges: %s unresolved (best sim %.2f < %.2f): %r", prop, sim, thr, (desc or "")[:80])
            return
        if (subj, CORE[prop], tgt) in g:
            return
        g.add((subj, CORE[prop], tgt))
        _emit_prov(g, case_id, subj, prop, tgt, desc)
        res[prop] += 1

    for indiv in individuals:
        subj = state_iris.get(_norm(indiv["label"]))
        if subj is None:
            continue  # state individual not present in the committed graph
        cls = _best_class(indiv)
        if cls is None:
            continue
        for desc in cls["obligation_activation"]:
            _emit(subj, "activatesObligation", desc, obl_pool)
        for desc in cls["action_constraints"]:
            _emit(subj, "activatesConstraint", desc, cons_pool)
        init_descs = list(cls["activation_conditions"])
        if indiv["triggering_event"]:
            init_descs.append(indiv["triggering_event"])
        for desc in init_descs:
            _emit(subj, "activatedByEvent", desc, evt_pool)
        term_descs = list(cls["termination_conditions"])
        if indiv["terminated_by"]:
            term_descs.append(indiv["terminated_by"])
        for desc in term_descs:
            _emit(subj, "terminatedByEvent", desc, evt_pool)
        if cls["principle_transformation"] and (subj, PROETH.principleTransformation, None) not in g:
            g.add((subj, PROETH.principleTransformation, Literal(cls["principle_transformation"])))
            res["principleTransformation"] += 1

    added = sum(res[k] for k in ("activatesObligation", "activatesConstraint",
                                 "activatedByEvent", "terminatedByEvent", "principleTransformation"))
    if write_back and added:
        g.serialize(destination=str(ttl_path), format="turtle")
    return res
