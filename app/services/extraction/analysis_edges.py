"""Deterministic analysis-record edge applier (proethica-cases v3.6.0).

Grounds the Step-4 analysis records that previously committed as islands:

- QuestionEmergence  --explainsQuestion-->      EthicalQuestion
- ResolutionPattern  --describesResolutionOf--> EthicalConclusion
- CodeProvisionReference --referencesProvision--> nspe: CodeProvision
- CodeProvisionReference --appliesTo--> any committed case individual
                       (v3.7.0: category-scoped label resolution; the
                       per-application reasoning rides the derivation)
- DecisionPoint      --decidesQuestion / addressesQuestion /
                       alignsWithConclusion / involvesObligation /
                       involvesAction / involvesConstraint / decidedByAgent

The synthesis store keys questions and conclusions POSITIONALLY
(case-<id>#Q<k> / #C<k> = the k-th row of the unordered enumeration in
step4_synthesis_service._load-style queries). Resolution is therefore
position-based over the id-ordered rows, VERIFIED against the carried target
text where the store provides it (question_text / conclusion_text /
aligned_conclusion_text), and every endpoint is existence- and type-checked
in the committed graph (never fabricate an endpoint; misses are reported,
not emitted). Deterministic; no LLM. Best-effort at the registry call site.

check_analysis_record_edges() is the backfill acceptance gate: it recomputes
the full expectation set and reports missing AND extra edges per predicate.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rdflib import Graph, Namespace, RDF, URIRef

from app.services.extraction.edge_resolution import (
    _individuals_in_category,
    emit_edge_prov,
)

logger = logging.getLogger(__name__)

CORE = Namespace("http://proethica.org/ontology/core#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
CASES = Namespace("http://proethica.org/ontology/cases#")
RDFS_NS = Namespace("http://www.w3.org/2000/01/rdf-schema#")

ANALYSIS_PREDICATES = (
    "explainsQuestion", "describesResolutionOf", "referencesProvision",
    "appliesTo",
    "decidesQuestion", "addressesQuestion", "alignsWithConclusion",
    "involvesObligation", "involvesAction", "involvesConstraint",
    "decidedByAgent",
)

# appliesTo target categories: the extraction's entity_type vocabulary mapped
# to the committed rdf:type proeth-core:<Category>. Unknown types are misses,
# never guessed.
_APPLIES_CATEGORIES = {
    "role": "Role", "obligation": "Obligation", "principle": "Principle",
    "state": "State", "resource": "Resource", "capability": "Capability",
    "constraint": "Constraint", "action": "Action", "event": "Event",
    "agent": "Agent",
}

_POS = re.compile(r"#([QC])(\d+)$")
_DIRECT = re.compile(r"#(Question|Conclusion)_(\d+)$")


def _rows(case_id: int, etype: str):
    from app.models import TemporaryRDFStorage
    # Published rows only: an unpublished (uncommitted or retracted) row must
    # not generate edge expectations against the committed graph -- the
    # batch-6 case-98 retraction left phantom expectations here until the
    # committed-individual guard declined them as resolution misses.
    return (TemporaryRDFStorage.query
            .filter_by(case_id=case_id, extraction_type=etype,
                       is_published=True)
            .order_by(TemporaryRDFStorage.id).all())


def _norm_text(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _texts_match(a: str, b: str) -> bool:
    """Normalized equality, tolerating one side being a truncation of the
    other (the store occasionally carries clipped target text)."""
    a, b = _norm_text(a), _norm_text(b)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return len(shorter) >= 40 and longer.startswith(shorter)


def _frag_uri(case_ns: Namespace, raw: Optional[str]) -> Optional[URIRef]:
    """'case-9#Frag' or a full case URI -> the committed case-namespace URI."""
    if not raw or "#" not in raw:
        return None
    return case_ns[raw.rsplit("#", 1)[1]]


def build_expectations(case_id: int, g: Graph) -> Tuple[List[Tuple], List[str]]:
    """The full deterministic edge expectation set for one case.

    Returns (edges, misses) where edges are
    (subject URIRef, predicate localname, object URIRef, source description)
    and misses are human-readable resolution failures (never emitted)."""
    case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")
    edges: List[Tuple] = []
    misses: List[str] = []

    q_rows = _rows(case_id, "ethical_question")
    c_rows = _rows(case_id, "ethical_conclusion")

    committed_q = set(g.subjects(RDF.type, CASES.EthicalQuestion))
    committed_c = set(g.subjects(RDF.type, CASES.EthicalConclusion))
    core_sets = {cat: set(_individuals_in_category(g, cat))
                 for cat in ("Obligation", "Action", "Agent", "Constraint")}

    _cat_label_cache: Dict[str, Dict[str, URIRef]] = {}

    def cat_labels(cat: str) -> Dict[str, URIRef]:
        """Whitespace-normalized rdfs:label -> URI for one core category
        (lazy, cached; the appliesTo resolution's lookup table)."""
        if cat not in _cat_label_cache:
            out: Dict[str, URIRef] = {}
            for s in _individuals_in_category(g, cat):
                for o in g.objects(s, RDFS_NS.label):
                    out.setdefault(_norm_text(str(o)), s)
            _cat_label_cache[cat] = out
        return _cat_label_cache[cat]

    q_by_num = {int((r.rdf_json_ld or {}).get("questionNumber")): (r.rdf_json_ld or {})
                for r in q_rows if (r.rdf_json_ld or {}).get("questionNumber")}
    c_by_num = {int((r.rdf_json_ld or {}).get("conclusionNumber")): (r.rdf_json_ld or {})
                for r in c_rows if (r.rdf_json_ld or {}).get("conclusionNumber")}

    def positional(uri_str: Optional[str], expect_text: Optional[str] = None):
        """Resolve a stored Q/C reference to the committed individual.

        Two key forms: the committed-URI form case-<id>#Question_<n> /
        #Conclusion_<n> (qc_refs, since 2026-07-10) resolves directly by
        number; the legacy positional case-<id>#Q<k>/#C<k> resolves by
        enumeration. Both are existence-checked; text-verified when the
        caller carries the target text."""
        m = _DIRECT.search(uri_str or "")
        if m:
            frag = f"{m.group(1)}_{int(m.group(2))}"
            is_q = m.group(1) == "Question"
            tgt = case_ns[frag]
            if tgt not in (committed_q if is_q else committed_c):
                return None, f"{uri_str}: {frag} not committed/typed"
            if expect_text:
                d = (q_by_num if is_q else c_by_num).get(int(m.group(2)))
                ref_text = (d or {}).get("questionText" if is_q else "conclusionText") or ""
                if d is not None and not _texts_match(expect_text, ref_text):
                    return None, f"{uri_str}: carried text does not match target row text"
            return tgt, None
        m = _POS.search(uri_str or "")
        if not m:
            return None, f"unparseable positional key {uri_str!r}"
        kind, k = m.group(1), int(m.group(2))
        rows, numkey, textkey, cls_set, frag = (
            (q_rows, "questionNumber", "questionText", committed_q, "Question_")
            if kind == "Q" else
            (c_rows, "conclusionNumber", "conclusionText", committed_c, "Conclusion_"))
        if not 1 <= k <= len(rows):
            return None, f"{uri_str}: position {k} outside the {len(rows)}-row store"
        d = rows[k - 1].rdf_json_ld or {}
        if not d.get(numkey):
            return None, f"{uri_str}: target row carries no {numkey}"
        tgt = case_ns[f"{frag}{int(d[numkey])}"]
        if tgt not in cls_set:
            return None, f"{uri_str}: {tgt.rsplit('#')[-1]} not committed/typed"
        if expect_text and not _texts_match(expect_text, d.get(textkey) or ""):
            return None, f"{uri_str}: carried text does not match target row text"
        return tgt, None

    def by_label(cls) -> Dict[str, URIRef]:
        out = {}
        for s in g.subjects(RDF.type, cls):
            for o in g.objects(s, RDFS_NS.label):
                out.setdefault(str(o), s)
        return out

    # --- QuestionEmergence --explainsQuestion--> EthicalQuestion -----------
    qe_by_label = by_label(CASES.QuestionEmergence)
    for row in _rows(case_id, "question_emergence"):
        d = row.rdf_json_ld or {}
        subj = qe_by_label.get(row.entity_label or "")
        if subj is None:
            misses.append(f"QE {row.entity_label!r}: no committed individual")
            continue
        if not d.get("question_uri"):
            misses.append(f"QE {row.entity_label!r}: no question_uri in store")
            continue
        tgt, err = positional(d["question_uri"], d.get("question_text"))
        if err:
            misses.append(f"QE {row.entity_label!r}: {err}")
            continue
        edges.append((subj, "explainsQuestion", tgt, d["question_uri"]))

    # --- ResolutionPattern --describesResolutionOf--> EthicalConclusion ----
    rp_by_label = by_label(CASES.ResolutionPattern)
    for row in _rows(case_id, "resolution_pattern"):
        d = row.rdf_json_ld or {}
        subj = rp_by_label.get(row.entity_label or "")
        if subj is None:
            misses.append(f"RP {row.entity_label!r}: no committed individual")
            continue
        if not d.get("conclusion_uri"):
            misses.append(f"RP {row.entity_label!r}: no conclusion_uri in store")
            continue
        tgt, err = positional(d["conclusion_uri"], d.get("conclusion_text"))
        if err:
            misses.append(f"RP {row.entity_label!r}: {err}")
            continue
        edges.append((subj, "describesResolutionOf", tgt, d["conclusion_uri"]))

    # --- CodeProvisionReference --referencesProvision--> nspe: -------------
    cpr_rows = _rows(case_id, "code_provision_reference")
    if cpr_rows:
        from sqlalchemy import text as sqltext
        from app.models import db
        from app.services.extraction.provision_citation_resolver import (
            ProvisionCitationResolver, valid_fragments_from_codes)
        codes = [r[0] for r in db.session.execute(sqltext(
            "SELECT section_code FROM guideline_sections WHERE guideline_id = 1"
        )).fetchall()]
        resolver = ProvisionCitationResolver(valid_fragments_from_codes(codes))
        cpr_by_label = by_label(CASES.CodeProvisionReference)
        for row in cpr_rows:
            d = row.rdf_json_ld or {}
            subj = cpr_by_label.get(row.entity_label or "")
            if subj is None:
                misses.append(f"CPR {row.entity_label!r}: no committed individual")
                continue
            code = d.get("codeProvision") or row.entity_label or ""
            iri = resolver.resolve(code)
            if not iri:
                misses.append(f"CPR {row.entity_label!r}: {code!r} resolves to no nspe provision")
            else:
                edges.append((subj, "referencesProvision", URIRef(iri), code))

            # --- appliesTo (v3.7.0): the provision's applications ------------
            for item in (d.get("appliesTo") or []):
                if not isinstance(item, dict):
                    continue
                lbl = _norm_text(item.get("entity_label"))
                cat = _APPLIES_CATEGORIES.get(
                    _norm_text(item.get("entity_type")).lower())
                if not lbl or not cat:
                    misses.append(f"CPR {row.entity_label!r}: appliesTo item "
                                  f"without a label/known category")
                    continue
                tgt = cat_labels(cat).get(lbl)
                if tgt is None:
                    misses.append(f"CPR {row.entity_label!r}: appliesTo "
                                  f"{lbl!r} is not a committed {cat}")
                    continue
                reason = _norm_text(item.get("reasoning")) or lbl
                edges.append((subj, "appliesTo", tgt, reason))

    # --- DecisionPoint family ----------------------------------------------
    dp_by_id: Dict[str, URIRef] = {}
    for s in g.subjects(RDF.type, CASES.DecisionPoint):
        for o in g.objects(s, PROETH.decisionPointId):
            dp_by_id.setdefault(str(o), s)
    for row in _rows(case_id, "canonical_decision_point"):
        d = row.rdf_json_ld or {}
        fid = d.get("focus_id") or ""
        subj = dp_by_id.get(fid)
        if subj is None:
            misses.append(f"DP {fid!r}: no committed individual")
            continue

        if d.get("aligned_question_uri"):
            tgt, err = positional(d["aligned_question_uri"],
                                  d.get("aligned_question_text"))
            if err:
                misses.append(f"DP {fid}: decidesQuestion: {err}")
            else:
                edges.append((subj, "decidesQuestion", tgt, d["aligned_question_uri"]))
        for qref in (d.get("addresses_questions") or []):
            tgt, err = positional(qref)
            if err:
                misses.append(f"DP {fid}: addressesQuestion: {err}")
            else:
                edges.append((subj, "addressesQuestion", tgt, qref))
        if d.get("aligned_conclusion_uri"):
            tgt, err = positional(d["aligned_conclusion_uri"],
                                  d.get("aligned_conclusion_text"))
            if err:
                misses.append(f"DP {fid}: alignsWithConclusion: {err}")
            else:
                edges.append((subj, "alignsWithConclusion", tgt,
                              d["aligned_conclusion_uri"]))
        for key, pred, cat in (("obligation_uri", "involvesObligation", "Obligation"),
                               ("role_uri", "decidedByAgent", "Agent"),
                               ("constraint_uri", "involvesConstraint", "Constraint")):
            raw = d.get(key) or ""
            if not raw:
                continue
            if cat == "Agent":
                tgt = _resolve_agent_ref(case_ns, raw, core_sets[cat])
            else:
                tgt = _frag_uri(case_ns, raw)
                if tgt is not None and tgt not in core_sets[cat]:
                    tgt = None
            if tgt is None:
                misses.append(f"DP {fid}: {pred}: {raw!r} not a committed {cat}")
                continue
            edges.append((subj, pred, tgt, raw))
        for aref in (d.get("involved_action_uris") or []):
            tgt = _frag_uri(case_ns, aref)
            if tgt is None or tgt not in core_sets["Action"]:
                misses.append(f"DP {fid}: involvesAction: {aref!r} not a committed Action")
                continue
            edges.append((subj, "involvesAction", tgt, aref))

    return edges, misses


def _resolve_agent_ref(case_ns, raw: str, agents) -> object:
    """Resolve a Phase-3 decidedByAgent reference to a committed Agent.

    Phase-3 refs frequently miss the minted node two ways (batch-1/2/3
    reviews: 27 decision points across 6 cases lost agent linkage in batch 3
    alone): the ref omits the ``Agent_`` prefix the participant minter uses
    ('case-166#Engineer_D' vs 'Agent_Engineer_D'), or names a generic role
    token ('case-92#Engineer') where the committed agent is
    'Agent_Engineer_A'. Resolution order: exact fragment, ``Agent_``-prefixed
    fragment, then a UNIQUE-prefix match on the committed agents' local names
    (minus the Agent_ prefix); an ambiguous generic token (two engineers)
    stays unresolved -- a dangling guess is worse than a recorded miss."""
    tgt = _frag_uri(case_ns, raw)
    if tgt is not None and tgt in agents:
        return tgt
    frag = (raw.split('#')[-1] if '#' in raw else raw).strip()
    if not frag:
        return None
    prefixed = case_ns[f"Agent_{frag}"]
    if prefixed in agents:
        return prefixed
    tok = frag.lower().removeprefix('the_').strip('_')
    if len(tok) < 3:
        return None
    # Token-boundary prefix: 'engineer' must match 'engineer_a' but NOT
    # 'engineering_firm' (case 163: the char-prefix version read the firm as
    # a second engineer and skipped a resolvable reference as ambiguous).
    cands = []
    for a in agents:
        local = str(a).rsplit('#', 1)[-1].lower().removeprefix('agent_')
        if local == tok or local.startswith(tok + '_'):
            cands.append(a)
    return cands[0] if len(cands) == 1 else None


def apply_analysis_record_edges(case_id: int, ttl_path,
                                write_back: bool = True) -> Dict[str, Any]:
    """Emit the expectation set into the case TTL (idempotent)."""
    ttl_path = Path(ttl_path)
    g = Graph()
    g.parse(str(ttl_path), format="turtle")
    edges, misses = build_expectations(case_id, g)
    added = present = 0
    by_pred: Dict[str, int] = {}
    for subj, pred, obj, src in edges:
        if (subj, CASES[pred], obj) in g:
            present += 1
            continue
        g.add((subj, CASES[pred], obj))
        emit_edge_prov(
            g, case_id, "analysis_edge_provenance_", pred, subj, obj, src,
            f"Analysis-record edge ({pred})",
            f"property={pred}; deterministic resolution from the Step-4 "
            "synthesis store (positional key, text-verified where carried, "
            "endpoint existence- and type-checked; no embedding or LLM)")
        added += 1
        by_pred[pred] = by_pred.get(pred, 0) + 1
    if write_back and added:
        g.serialize(destination=str(ttl_path), format="turtle")
    if misses:
        logger.warning("analysis_edges case %s: %d unresolved (first: %s)",
                       case_id, len(misses), misses[0])
    return {"case_id": case_id, "status": "ok", "added": added,
            "present": present, "by_predicate": by_pred, "misses": misses}


def reconstruct_analysis_record_edges(case_id: int, ttl_path) -> Dict[str, Any]:
    """Drop the WHOLE analysis-edge family -- every edge of the ten
    predicates plus every provenance node of the family's IRI prefix -- and
    re-apply from current expectations.

    This is the correct refresh after a LAYER REBUILD replaces analysis
    individuals: the rebuilds remove subjects' outgoing triples, but the
    family's prov nodes are separate subjects and survive as orphans when
    the new generation lacks their edge; and apply() alone re-mints prov
    only for edges it ADDS. Reconstruction guarantees edges == expectations
    and prov == edges (2026-07-10 pilot: an in-place prune corrupted prov;
    this full-family rebuild is the clean path)."""
    ttl_path = Path(ttl_path)
    g = Graph()
    g.parse(str(ttl_path), format="turtle")
    removed_edges = removed_prov = 0
    for pred in ANALYSIS_PREDICATES:
        for s, o in list(g.subject_objects(CASES[pred])):
            g.remove((s, CASES[pred], o))
            removed_edges += 1
    for s in {s for s in g.subjects()
              if "#analysis_edge_provenance_" in str(s)}:
        for t in list(g.triples((s, None, None))):
            g.remove(t)
        removed_prov += 1
    g.serialize(destination=str(ttl_path), format="turtle")
    result = apply_analysis_record_edges(case_id, ttl_path)
    result["reconstructed"] = {"edges_dropped": removed_edges,
                               "prov_dropped": removed_prov}
    return result


def check_analysis_record_edges(case_id: int, ttl_path) -> Dict[str, Any]:
    """Backfill acceptance gate: every expected edge present, no extras."""
    g = Graph()
    g.parse(str(ttl_path), format="turtle")
    edges, misses = build_expectations(case_id, g)
    expected = {(s, CASES[p], o) for s, p, o, _ in edges}
    missing = [f"{p}: {str(s).rsplit('#')[-1]} -> {str(o).rsplit('#')[-1]}"
               for s, p, o, _ in edges if (s, CASES[p], o) not in g]
    extra = []
    for pred in ANALYSIS_PREDICATES:
        for s, o in g.subject_objects(CASES[pred]):
            if (s, CASES[pred], o) not in expected:
                extra.append(f"{pred}: {str(s).rsplit('#')[-1]} -> {str(o).rsplit('#')[-1]}")
    return {"case_id": case_id, "expected": len(edges),
            "missing": missing, "extra": extra, "resolution_misses": misses}
