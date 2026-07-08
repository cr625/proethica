"""Defeasibility resolution view service.

Assembles the data behind the obligation-conflict resolution view. The defeasibility
trio (``competesWith`` / ``prevailsOver`` / ``defeasibleUnder``) lives only in the
committed per-case ontology TTL, not in any relational table, so this service reads
the authoritative serialized graph directly with rdflib.

Two bands are produced:

* **This case** -- every resolved obligation competition in the case: which obligation
  prevailed, which yielded, and the State context under which the yielding obligation
  is defeasible. Plus the board conclusions and the action-level obligation violations
  that record the resolution.
* **Cross case** -- how comparable cases resolved a similar tension, ranked from the
  commit-time band index by the pairwise metric in _band_score (both obligations of
  the resolved pair plus the licensing context, in embedding space), floored by
  MIN_BAND_SCORE, and restricted to fresh-architecture cases. No prose is hard-coded;
  the band is deterministic between commits.

Predicates are matched by local name so the service is robust to namespace form.
"""

import logging

import rdflib
from rdflib import RDFS

from app.services.entity.committed_case_graph import case_ttl_path, load_case_graph

logger = logging.getLogger(__name__)

TRIO = {"competesWith", "prevailsOver", "defeasibleUnder"}

_CORE_NS = "http://proethica.org/ontology/core#"
_NINE_CATEGORIES = {"Role", "Principle", "Obligation", "State", "Resource",
                    "Action", "Event", "Capability", "Constraint"}

def _local(uri) -> str:
    s = str(uri)
    return s.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _label(g, uri) -> str:
    lbl = g.value(uri, RDFS.label)
    return str(lbl) if lbl else _local(uri).replace("_", " ")


def _trio_edges(g):
    """Return (competes_pairs, prevails, defeasible) from a case graph.

    competes_pairs: set of frozenset({label_a, label_b})
    prevails:       list of (winner_label, loser_label, winner_uri, loser_uri)
    defeasible:     dict loser_label -> [state_label]
    """
    competes = set()
    prevails = []
    defeasible = {}
    for s, p, o in g:
        ln = _local(p)
        if ln not in TRIO:
            continue
        if ln == "competesWith":
            competes.add(frozenset((_label(g, s), _label(g, o))))
        elif ln == "prevailsOver":
            prevails.append((_label(g, s), _label(g, o), s, o))
        elif ln == "defeasibleUnder":
            defeasible.setdefault(_label(g, s), []).append(_label(g, o))
    return competes, prevails, defeasible


def _entity_index(g, case_id):
    """Build label(lowercased) -> hover entry from a committed case graph, for attaching
    OntServe definition popovers to the entity labels the view renders. Definition prefers
    skos:definition, falls back to rdfs:comment; type is the materialized direct
    rdf:type proeth-core:<Category> (CMT-1); the OntServe target is the case ontology.
    Predicates matched by local name (namespace-robust)."""
    target = f"proethica-case-{case_id}"
    labels = {}
    for s, p, o in g:
        if _local(p) == "label":
            labels.setdefault(s, str(o))
    out = {}
    for s, lbl in labels.items():
        defn_skos = defn_comment = cat = ""
        for _s, p, o in g.triples((s, None, None)):
            ln = _local(p)
            if ln == "definition" and not defn_skos:
                defn_skos = str(o)
            elif ln == "comment" and not defn_comment:
                defn_comment = str(o)
            elif ln == "type" and not cat and str(o).startswith(_CORE_NS) \
                    and _local(o) in _NINE_CATEGORIES:
                cat = _local(o)
        frag = str(s).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
        exact = frag.replace("_", " ").lower() == lbl.lower()
        key = lbl.lower()
        prev = out.get(key)
        # When two entities share a display label (e.g. an Obligation and a like-named
        # Capability), keep the one whose URI fragment matches the label exactly -- that is
        # the primary entity the defeasibility edges reference, not the typed variant.
        if prev is not None and prev["_exact"] and not exact:
            continue
        out[key] = {
            "label": lbl,
            "definition": defn_skos or defn_comment,
            "entityType": cat,
            "source": "case",
            "uri": str(s),
            "ontologyTarget": target,
            "_exact": exact,
        }
    for entry in out.values():
        entry.pop("_exact", None)
    return out


def _conclusions(g):
    """Board conclusion texts, deduped and ordered by conclusionNumber so the primary
    findings (1, 2, ...) lead and any higher-numbered interpretive refinements follow."""
    items = []
    seen = set()
    for s, p, o in g:
        if _local(p) != "conclusionText":
            continue
        text = str(o).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        num = None
        for _s2, p2, o2 in g.triples((s, None, None)):
            if _local(p2) == "conclusionNumber":
                try:
                    num = int(str(o2))
                except (TypeError, ValueError):
                    num = None
                break
        items.append((num, text))
    # Exclude the synthetic interpretive refinements (numbered >= 100), which extend
    # beyond the board's explicit rulings; keep the primary board findings.
    items = [(n, t) for (n, t) in items if n is None or n < 100]
    items.sort(key=lambda t: (t[0] is None, t[0] if t[0] is not None else 0))
    return [t[1] for t in items]


def _violations(g):
    out = []
    for s, p, o in g:
        if _local(p) == "violatesObligation":
            out.append({"action": _label(g, s), "obligation": _label(g, o)})
    return out


def _featured_index(conflicts):
    """Pick the conflict to foreground: prefer a reporting/disclosure winner (the
    bridge from a duty-to-disclose entry), else the first resolved conflict."""
    for i, c in enumerate(conflicts):
        if "Report" in c["winner"] or "Disclos" in c["winner"]:
            return i
    return 0 if conflicts else None


def case_has_conflicts(case_id: int) -> bool:
    """Whether the committed case graph carries any obligation-competition edge
    (prevailsOver or competesWith), i.e. whether the conflicts view has content.
    False when the case has no committed ontology. defeasibleUnder alone does not
    count: it enriches a conflict but cannot render one by itself."""
    try:
        g = load_case_graph(case_id)
    except FileNotFoundError:
        return False
    return any(_local(p) in ("prevailsOver", "competesWith") for p in g.predicates())


def get_case_conflicts(case_id: int) -> dict:
    g = load_case_graph(case_id)
    competes, prevails, defeasible = _trio_edges(g)

    # The reified edge node the commit pipeline mints for each prevailsOver
    # (defeasibility_edge_provenance_<S>_prevailsOver_<O>): when present in the
    # graph, the conflict links to its OntServe entity page -- the triple as a
    # first-class, auditable thing (endpoints + grounding quote + confidence),
    # not just the two endpoint entities. _safe_frag is the pipeline's own
    # fragment rule, imported so the constructed IRI always matches the minted one.
    from app.services.extraction.defeasibility_pipeline import _safe_frag

    seen = set()
    conflicts = []
    # Sorted so the conflict order (and with it the featured fallback and the
    # cross-case band anchor) is stable across processes: _trio_edges iterates
    # the rdflib graph, whose order is hash-randomized per process.
    for winner, loser, w_uri, l_uri in sorted(prevails):
        if (winner, loser) in seen:
            continue
        seen.add((winner, loser))
        frag = (f"defeasibility_edge_provenance_{_safe_frag(str(w_uri))}"
                f"_prevailsOver_{_safe_frag(str(l_uri))}")
        prov_uri = rdflib.URIRef(
            f"http://proethica.org/ontology/case/{case_id}#{frag}")
        has_prov = (prov_uri, None, None) in g
        conflicts.append({
            "winner": winner,
            "loser": loser,
            "contexts": sorted(set(defeasible.get(loser, []))),
            "competes": frozenset((winner, loser)) in competes,
            "ontserve_triple_path": (
                f"/entity/proethica-case-{case_id}/{frag}" if has_prov else None),
            # Generic duty concepts the endpoints instantiate -- the level at
            # which resolutions recur across cases (type-level patterns).
            "winner_type": _intermediate_type(g, w_uri),
            "loser_type": _intermediate_type(g, l_uri),
        })

    resolved_pairs = {frozenset((c["winner"], c["loser"])) for c in conflicts}
    unresolved = sorted(
        sorted(pair) for pair in competes if pair not in resolved_pairs
    )

    featured = _featured_index(conflicts)
    for i, c in enumerate(conflicts):
        c["featured"] = (i == featured)

    return {
        "conflicts": conflicts,
        "unresolved": unresolved,
        "conclusions": _conclusions(g),
        "violations": _violations(g),
    }


# Fresh-architecture commit marker: every entity committed through the current
# pipeline carries proeth-prov:synthesisLiteral rows; legacy prior-extraction
# TTLs have none. Used to gate which index rows the dynamic band may rank.
_FRESH_MARKER = rdflib.URIRef("http://proethica.org/provenance#synthesisLiteral")


def _context_text(labels) -> str | None:
    """Canonical text form of a defeasibleUnder context-label set for embedding:
    sorted and '; '-joined, so refresh-time and query-time embeddings agree."""
    return "; ".join(sorted(labels)) if labels else None


_INTERMEDIATE_NS = "http://proethica.org/ontology/intermediate#"


def _intermediate_type(g, uri) -> str | None:
    """The individual's intermediate-class type local name (the generic duty
    concept, e.g. FaithfulAgentObligation) -- the unit at which resolutions
    recur across cases. Individuals carry one; sorted-joined if ever several."""
    locals_ = sorted(
        str(t).rsplit("#", 1)[-1]
        for t in g.objects(uri, rdflib.RDF.type)
        if str(t).startswith(_INTERMEDIATE_NS)
    )
    return "; ".join(locals_) if locals_ else None


def _type_display(type_local: str | None) -> str | None:
    """FaithfulAgentObligation -> 'Faithful Agent Obligation' for prose."""
    import re
    if not type_local:
        return None
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", type_local)


def refresh_band_index(case_id: int) -> int:
    """Rebuild this case's rows in the cross-case defeasibility index from its committed
    TTL. One row per resolved prevailsOver (winner, loser) pair, with embeddings of both
    obligation labels and of the joined defeasibleUnder context labels precomputed
    (pairwise ranking, 2026-07-08). Rows are marked fresh when the TTL carries the
    fresh-architecture proeth-prov:synthesisLiteral marker; only fresh rows enter the
    dynamic band. Idempotent (clears the case's existing rows first). Returns the number
    of rows written. Called at commit time after edge materialization."""
    from app.models import db
    from app.models.defeasibility_band_index import DefeasibilityBandIndex
    from app.services.embedding.embedding_service import EmbeddingService

    DefeasibilityBandIndex.query.filter_by(case_id=case_id).delete()

    try:
        g = load_case_graph(case_id)
    except FileNotFoundError:
        # No committed TTL -> leave the case with no index rows.
        db.session.commit()
        return 0

    _competes, prevails, defeasible = _trio_edges(g)
    seen = set()
    pairs = []
    for winner, loser, w_uri, l_uri in prevails:
        if (winner, loser) in seen:
            continue
        seen.add((winner, loser))
        pairs.append((winner, loser, w_uri, l_uri))

    fresh = next(g.triples((None, _FRESH_MARKER, None)), None) is not None
    emb = EmbeddingService.get_instance()
    label_vec = {}

    def _vec(text):
        if text not in label_vec:
            label_vec[text] = emb.get_embedding(text)
        return label_vec[text]

    for winner, loser, w_uri, l_uri in pairs:
        contexts = sorted(set(defeasible.get(loser, [])))
        ctx_txt = _context_text(contexts)
        db.session.add(DefeasibilityBandIndex(
            case_id=case_id,
            winner_label=winner,
            loser_label=loser,
            context_labels=contexts,
            loser_embedding=_vec(loser),
            winner_embedding=_vec(winner),
            context_embedding=_vec(ctx_txt) if ctx_txt else None,
            winner_type=_intermediate_type(g, w_uri),
            loser_type=_intermediate_type(g, l_uri),
            fresh=fresh,
        ))
    db.session.commit()
    return len(pairs)


def _cosine(a, b) -> float:
    import numpy as np
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# Band-2 score floor: candidates below it are omitted and the view says no
# sufficiently similar resolution is indexed, instead of showing top-5
# regardless of similarity (2026-07-08 review: the floorless loser-only metric
# surfaced 0.36-scoring legacy matches under a "same tension" heading).
MIN_BAND_SCORE = 0.45


def _band_score(anchor_vecs: dict, row) -> float | None:
    """Pairwise tension similarity between the anchor conflict and one index row.

    A tension is the PAIR of obligations, so both endpoints are matched with equal
    weight, plus the licensing context in embedding space:

        score = 0.7 * (0.5*cos(winner) + 0.5*cos(loser)) + 0.3 * cos(contexts)

    The 0.7/0.3 structure-vs-context split carries over from the loser-only metric
    this replaces (2026-07-08 review: the winner was ignored, and exact-label Jaccard
    over case-minted context labels was structurally inert -- 3 of 566 context labels
    in the whole index recurred across cases). The context term is 0 when either side
    has no defeasibleUnder contexts. Returns None for rows predating the pairwise
    columns (no winner embedding), which the caller skips.
    """
    if row.loser_embedding is None or row.winner_embedding is None:
        return None
    pair = 0.5 * _cosine(anchor_vecs["winner"], row.winner_embedding) \
        + 0.5 * _cosine(anchor_vecs["loser"], row.loser_embedding)
    ctx = 0.0
    if anchor_vecs.get("context") is not None and row.context_embedding is not None:
        ctx = _cosine(anchor_vecs["context"], row.context_embedding)
    return 0.7 * pair + 0.3 * ctx


def get_cross_case_band_dynamic(anchor_case_id: int, case_data: dict) -> dict | None:
    """Cross-case band assembled from the commit-time index instead of a curated set.

    Ranks every other fresh-architecture case's resolved tension against the anchor's
    featured conflict with the pairwise metric in _band_score, keeps the best-scoring
    pattern per case, applies the MIN_BAND_SCORE floor, and returns up to five rows.
    Only fresh index rows are ranked: legacy prior-extraction patterns carry
    citation-bearing labels and predate the entity contract, and are excluded until
    the 119-case rebuild re-commits them. The band label is generated from the
    anchor's winner/loser pair. Returns None when the anchor has no resolved conflict
    or the index holds no other fresh cases; returns a band with empty rows when
    candidates exist but none clears the floor (the view renders that state
    explicitly).
    """
    conflicts = case_data.get("conflicts") or []
    featured = next((c for c in conflicts if c.get("featured")),
                    conflicts[0] if conflicts else None)
    if not featured:
        return None

    from app.models import Document
    from app.models.defeasibility_band_index import DefeasibilityBandIndex
    from app.services.embedding.embedding_service import EmbeddingService

    candidates = DefeasibilityBandIndex.query.filter(
        DefeasibilityBandIndex.case_id != anchor_case_id,
        DefeasibilityBandIndex.fresh.is_(True),
    ).all()
    if not candidates:
        return None

    anchor_loser = featured["loser"]
    anchor_winner = featured["winner"]
    emb = EmbeddingService.get_instance()
    anchor_ctx_txt = _context_text(featured.get("contexts", []))
    anchor_vecs = {
        "winner": emb.get_embedding(anchor_winner),
        "loser": emb.get_embedding(anchor_loser),
        "context": emb.get_embedding(anchor_ctx_txt) if anchor_ctx_txt else None,
    }

    best = {}  # case_id -> (score, row)
    for r in candidates:
        score = _band_score(anchor_vecs, r)
        if score is None:
            continue
        current = best.get(r.case_id)
        if current is None or score > current[0]:
            best[r.case_id] = (score, r)

    top = sorted(best.values(), key=lambda pair: pair[0], reverse=True)[:5]
    rows = []
    for score, r in top:
        if score < MIN_BAND_SCORE:
            continue
        doc = Document.query.get(r.case_id)
        meta = doc.doc_metadata if (doc and isinstance(doc.doc_metadata, dict)) else {}
        rows.append({
            "case_id": r.case_id,
            "title": doc.title if doc else f"Case {r.case_id}",
            "case_number": meta.get("case_number", ""),
            "matches": [{
                "winner": r.winner_label,
                "loser": r.loser_label,
                "contexts": sorted(r.context_labels or []),
            }],
            "score": round(score, 3),
        })
    # Type-level recurrence: exact match on the generic duty concepts the
    # endpoints instantiate (winner_type / loser_type). Types are shared
    # vocabulary across cases, so this needs no embedding and no floor, and it
    # surfaces the patterns the similarity ranking cannot: the same duty TYPE
    # yielding in another case, or appearing on the OPPOSITE side of a
    # resolution (the context-indexed defeasibility the learning claim needs).
    def _case_refs(pred):
        seen_ids, refs = set(), []
        for r in candidates:
            if r.case_id in seen_ids or not pred(r):
                continue
            seen_ids.add(r.case_id)
            doc = Document.query.get(r.case_id)
            meta = doc.doc_metadata if (doc and isinstance(doc.doc_metadata, dict)) else {}
            refs.append({"case_id": r.case_id,
                         "case_number": meta.get("case_number", ""),
                         "title": doc.title if doc else f"Case {r.case_id}"})
        return refs

    lt, wt = featured.get("loser_type"), featured.get("winner_type")
    type_patterns = {
        "loser_type": lt,
        "loser_type_display": _type_display(lt),
        "winner_type": wt,
        "winner_type_display": _type_display(wt),
        "loser_yields_in": _case_refs(lambda r: lt and r.loser_type == lt) if lt else [],
        "loser_prevails_in": _case_refs(lambda r: lt and r.winner_type == lt) if lt else [],
        "winner_yields_in": _case_refs(lambda r: wt and r.loser_type == wt) if wt else [],
        "winner_prevails_in": _case_refs(lambda r: wt and r.winner_type == wt) if wt else [],
    }
    type_patterns["any"] = any(
        type_patterns[k] for k in
        ("loser_yields_in", "loser_prevails_in", "winner_yields_in", "winner_prevails_in"))

    # Generated from the matched pair (no hand-written prose). Kept article-free so it
    # reads correctly whether the labels are common-noun obligations or engineer-prefixed.
    label = f"{anchor_loser} yields to {anchor_winner}"
    return {"label": label, "keyword": anchor_loser, "rows": rows,
            "floor": MIN_BAND_SCORE, "dynamic": True,
            "type_patterns": type_patterns}


def build_defeasibility_view(case_id: int) -> dict:
    """Assemble both bands for the case. Raises FileNotFoundError if the case has no
    committed ontology yet."""
    case_data = get_case_conflicts(case_id)
    # 2026-07-08: the former CURATED_BANDS theme path (a pinned "Faithful Agent"
    # comparison set) was retired -- it pinned legacy prior-extraction cases the
    # dynamic band deliberately excludes, and preempted better dynamic matches.
    # The dynamic band is deterministic between commits (commit-time index +
    # sorted conflict order), which covers the stable-walkthrough purpose.
    cross_case = get_cross_case_band_dynamic(case_id, case_data)

    # Hover lookup over the entities the view renders: the anchor case plus the comparison
    # cases. Each entry links to its own committed OntServe ontology. The anchor case wins
    # on a label collision (cross-case labels are engineer-prefixed, so collisions are rare).
    lookup = {}
    cids = [case_id] + ([r["case_id"] for r in cross_case["rows"]] if cross_case else [])
    for cid in cids:
        try:
            g = load_case_graph(cid)
        except FileNotFoundError:
            continue
        for key, entry in _entity_index(g, cid).items():
            lookup.setdefault(key, entry)

    return {
        "case_conflicts": case_data,
        "cross_case": cross_case,
        "entity_lookup": lookup,
        # The whole competition structure rendered on the OntServe side (the
        # Obligation Competition panel on the case-ontology page).
        "ontserve_panel_path": f"/ontology/proethica-case-{case_id}#section-competition",
    }
