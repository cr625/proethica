"""Temporal (Allen) relation endpoint resolution (DB-driven, embedding-resolved).

The Step-3 temporal pass extracts Allen interval relations between case happenings
and stores each as a reified proeth:TemporalRelation individual whose endpoints are
free-text *timeline phrasings*:

  proeth:fromEntity  "Engineer A preparing the summary memo"
  proeth:toEntity    "City Administrator's request for a recommendation"
  proeth:owlTimeProperty "time:intervalBefore"

Those phrasings are NOT the labels of the committed Action/Event individuals (which
are noun phrases like "Advisory Memo Preparation"), so the former pre-computed
endpoint URIs (rdf_converter's `_safe_id`, 50-char-truncated, legacy namespace)
silently dangled: a measurement on the published baselines found ~33-52% of the
time:* objects pointed at a fragment that exists nowhere in the case graph. A plain
namespace swap could not fix this -- it is a label-space mismatch, not a namespace
mismatch.

This applier WIRES THE ENDPOINTS IN. For each committed TemporalRelation it reads the
clean fromEntity/toEntity labels from temporary_rdf_storage, resolves each to the
matching case Action or Event individual (embedding shortlist + batched LLM select,
mirroring causal_edges.apply_causal_edges), and materialises:

  TemporalRelation proeth:fromEntity   Action|Event   (declared owl:ObjectProperty)
  TemporalRelation proeth:toEntity     Action|Event
  TemporalRelation time:<allen-prop>   <toEntity individual>   (the OWL-Time assertion)

with PROV-O provenance. proeth:fromEntity / proeth:toEntity are declared range
unionOf(Action, Event); the resolver therefore matches ONLY the Action+Event pool, so
a state-like endpoint (e.g. "Engineer A having no contractual relationship with City
B") resolves to nothing and is left unwired+logged rather than asserted against a
disjoint State (which would make the case OWL-DL inconsistent). Both endpoints are
registered in rpo_edges.ALL_EDGE_RANGE, so the unified guard run at the end of
edge materialization drops any mis-resolved edge as a final safety net.

Best-effort: failures are logged, never raised, so this can never fail a commit.
Structurally identical to causal_edges.py.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from rdflib import Graph, Namespace, RDF, URIRef
from rdflib.namespace import TIME

from app.services.extraction.state_edges import (
    _candidate_pool,
    _embedding_service,
    _label,
    _norm,
    _shortlist,
    emit_edge_prov,
)
from app.services.extraction.resource_edges import _llm_select_multi

logger = logging.getLogger(__name__)

PROETH = Namespace("http://proethica.org/ontology/intermediate#")
PROV = Namespace("http://www.w3.org/ns/prov#")

EMBED_MATCH_MIN = 0.50
SHORTLIST_FLOOR = 0.30
SHORTLIST_K = 8

# (property local, the noun shown to the LLM for the endpoint being resolved)
_TR_SPECS = (
    ("fromEntity", "is the SOURCE happening (Entity1 in 'Entity1 [relation] Entity2')"),
    ("toEntity", "is the TARGET happening (Entity2 in 'Entity1 [relation] Entity2')"),
)


def _temporal_relations_from_db(case_id: int) -> List[Dict[str, Any]]:
    """[{label, fromEntity, toEntity, owlprop, evidence}] for each Step-3
    TemporalRelation individual that names at least one endpoint. Read from
    temporary_rdf_storage; the temporal rows store proeth: keys at the top level of
    rdf_json_ld. owlprop is the OWL-Time property name (e.g. "time:intervalBefore")."""
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    rows = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type="temporal_dynamics_enhanced", storage_type="individual"
    ).all()
    out = []
    for r in rows:
        rdf = r.rdf_json_ld or {}
        if "TemporalRelation" not in (rdf.get("@type", "") or ""):
            continue

        def _val(key):
            v = rdf.get(f"proeth:{key}")
            if isinstance(v, list):
                return "; ".join(str(x).strip() for x in v if str(x).strip())
            return str(v).strip() if v not in (None, "") else ""

        rec = {
            "label": r.entity_label or rdf.get("rdfs:label", ""),
            "fromEntity": _val("fromEntity"),
            "toEntity": _val("toEntity"),
            "owlprop": _val("owlTimeProperty"),
            "evidence": _val("evidence"),
        }
        if rec["fromEntity"] or rec["toEntity"]:
            out.append(rec)
    return out


def _build_tr_prompt(prop: str, noun: str):
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


def _emit_prov(g: Graph, case_id: int, prop: str, subj, obj, desc: str) -> None:
    emit_edge_prov(g, case_id, "temporal_relation_edge_provenance_", prop, subj, obj, desc,
                   f"Temporal relation edge ({prop})",
                   f"property={prop}; temporal relation's {prop} text resolved to the case "
                   "Action/Event individual by embedding shortlist + LLM select")


def apply_temporal_relation_edges(case_id: int, ttl_path, write_back: bool = True,
                                  threshold: float = EMBED_MATCH_MIN, use_llm: bool = True,
                                  llm_client=None, model=None) -> Dict[str, Any]:
    """Resolve each reified TemporalRelation's fromEntity/toEntity timeline phrasings
    to the committed Action/Event individuals and materialise the participant edges +
    the OWL-Time triple. Reads endpoint labels from temporary_rdf_storage; resolves
    against the Action+Event pool only (the declared fromEntity/toEntity range).
    Returns per-property counts. Best-effort; never raises."""
    ttl_path = Path(ttl_path)
    res: Dict[str, Any] = {"case_id": case_id, "status": "ok", "total": 0}
    try:
        rels = _temporal_relations_from_db(case_id)
    except Exception as e:
        logger.warning("temporal_relation_edges: temp_rdf read failed for case %s: %s", case_id, e)
        return {"case_id": case_id, "status": "no_db", "error": str(e)}
    if not rels:
        return {"case_id": case_id, "status": "no_temporal_relations"}

    g = Graph()
    g.parse(str(ttl_path), format="turtle")
    svc = _embedding_service()

    # Subject map: committed TemporalRelation individuals by normalized rdfs:label
    # (typed proeth:TemporalRelation; the URI is opaque TemporalRelation_<n>, so match
    # by the readable "entity1 relation entity2" label that equals the temp_rdf row's
    # entity_label).
    rel_iris: Dict[str, URIRef] = {}
    for ind in g.subjects(RDF.type, PROETH.TemporalRelation):
        rel_iris.setdefault(_norm(_label(g, ind)), ind)
    if not rel_iris:
        return {"case_id": case_id, "status": "no_committed_relations"}

    # Object pool: the case happenings (Action + Event). fromEntity/toEntity range is
    # unionOf(Action, Event), so State/other categories are deliberately excluded.
    happening_pool = (
        _candidate_pool(g, svc, "Action", []) + _candidate_pool(g, svc, "Event", [])
    )
    if not happening_pool:
        return {"case_id": case_id, "status": "no_happenings"}

    # Cache the OWL-Time property per relation subject so the time:* triple uses the
    # right predicate after the toEntity is resolved.
    owlprop_by_subj: Dict[URIRef, str] = {}

    for prop, noun in _TR_SPECS:
        items: List[Dict[str, Any]] = []
        next_id = 1
        unresolved = 0
        for c in rels:
            desc = c.get(prop) or ""
            if not desc:
                continue
            subj = rel_iris.get(_norm(c["label"]))
            if subj is None:
                logger.info("temporal_relation_edges[%s]: relation %r not in committed graph; skipped",
                            prop, (c["label"] or "")[:80])
                continue
            owlprop_by_subj.setdefault(subj, c.get("owlprop") or "")
            sl = _shortlist(svc, desc, happening_pool, SHORTLIST_FLOOR, SHORTLIST_K)
            if not sl:
                unresolved += 1
                continue
            items.append({"id": next_id, "subj": subj, "desc": desc,
                          "subj_label": c["label"], "evidence": c.get("evidence") or "",
                          "shortlist": sl})
            next_id += 1

        selections = _llm_select_multi(
            items, client=llm_client, model=model, prompt_builder=_build_tr_prompt(prop, noun)
        ) if use_llm else None

        edges = 0
        for it in items:
            subj, desc, sl = it["subj"], it["desc"], it["shortlist"]
            if selections is not None:
                targets = selections.get(str(it["id"])) or []
            else:
                targets = [iri for iri, _lbl, sim in sl if sim >= threshold]
            # fromEntity/toEntity are single-valued: keep only the first selected target.
            targets = targets[:1]
            if not targets:
                unresolved += 1
                continue
            tgt = targets[0]
            if (subj, PROETH[prop], tgt) not in g:
                g.add((subj, PROETH[prop], tgt))
                _emit_prov(g, case_id, prop, subj, tgt, it.get("evidence") or desc)
                edges += 1
            # Emit the OWL-Time assertion on the relation node once the TARGET (entity2)
            # is resolved (Entity1 [relation] Entity2 -> the relation holds toward
            # Entity2). Preserves the historical relation-node-anchored time:* shape,
            # now pointing at a real individual instead of a dangling fragment.
            if prop == "toEntity":
                owlprop = owlprop_by_subj.get(subj) or ""
                local = owlprop.split(":")[-1] if owlprop else ""
                if local:
                    if (subj, TIME[local], tgt) not in g:
                        g.add((subj, TIME[local], tgt))
        res[prop] = {"edges": edges, "resolver": "llm" if selections is not None else "embedding",
                     "unresolved": unresolved}

    total = sum(v.get("edges", 0) for v in res.values() if isinstance(v, dict))
    res["total"] = total
    if write_back and total:
        g.serialize(destination=str(ttl_path), format="turtle")
    return res
