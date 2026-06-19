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
* **Cross case** -- for the same conflict theme, how a curated set of comparable cases
  resolved the analogous tension. The case set is fixed (chosen for clean,
  current-architecture extractions) so a walkthrough renders identically, but every
  edge shown is read live from that case's committed TTL. No prose is hard-coded.

Predicates are matched by local name so the service is robust to namespace form.
"""

import logging
from pathlib import Path

import rdflib
from rdflib import RDFS

from app.services.ontserve.ontserve_config import get_ontserve_base_path

logger = logging.getLogger(__name__)

TRIO = {"competesWith", "prevailsOver", "defeasibleUnder"}

# Curated cross-case comparison sets, keyed by conflict theme. ``case_ids`` is the
# fixed selection (current-architecture, Pellet-consistent extractions); the edges
# themselves are read live from each case's committed TTL, so the panel is real data
# and only the case selection is pinned for a stable demonstration.
CURATED_BANDS = {
    "Faithful Agent": {
        "label": "A faithful-agent duty yields to a public-protection obligation",
        "defeated_contains": "Faithful Agent",
        "case_ids": [8, 76, 71, 86],
    },
}


def _ontologies_dir() -> Path:
    return get_ontserve_base_path() / "ontologies"


def case_ttl_path(case_id: int) -> Path:
    return _ontologies_dir() / f"proethica-case-{case_id}.ttl"


_GRAPH_CACHE = {}


def _load_graph(case_id: int) -> rdflib.Graph:
    path = case_ttl_path(case_id)
    if not path.exists():
        # A missing committed TTL is a genuine state (not every case is extracted),
        # surfaced to the caller rather than silently substituted.
        raise FileNotFoundError(f"No committed ontology for case {case_id}: {path}")
    # Cache the parsed graph per (path, mtime) so a single view render that reads the
    # same case TTL more than once does not re-parse it. Read-only use only.
    key = (str(path), path.stat().st_mtime_ns)
    g = _GRAPH_CACHE.get(key)
    if g is None:
        g = rdflib.Graph()
        g.parse(str(path), format="turtle")
        _GRAPH_CACHE[key] = g
    return g


def _local(uri) -> str:
    s = str(uri)
    return s.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _label(g, uri) -> str:
    lbl = g.value(uri, RDFS.label)
    return str(lbl) if lbl else _local(uri).replace("_", " ")


def _trio_edges(g):
    """Return (competes_pairs, prevails, defeasible) from a case graph.

    competes_pairs: set of frozenset({label_a, label_b})
    prevails:       list of (winner_label, loser_label)
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
            prevails.append((_label(g, s), _label(g, o)))
        elif ln == "defeasibleUnder":
            defeasible.setdefault(_label(g, s), []).append(_label(g, o))
    return competes, prevails, defeasible


def _entity_index(g, case_id):
    """Build label(lowercased) -> hover entry from a committed case graph, for attaching
    OntServe definition popovers to the entity labels the view renders. Definition prefers
    skos:definition, falls back to rdfs:comment; type is proeth:conceptCategory; the
    OntServe target is the case ontology. Predicates matched by local name (namespace-robust)."""
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
            elif ln == "conceptCategory" and not cat:
                cat = str(o)
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


def get_case_conflicts(case_id: int) -> dict:
    g = _load_graph(case_id)
    competes, prevails, defeasible = _trio_edges(g)

    seen = set()
    conflicts = []
    for winner, loser in prevails:
        if (winner, loser) in seen:
            continue
        seen.add((winner, loser))
        conflicts.append({
            "winner": winner,
            "loser": loser,
            "contexts": sorted(set(defeasible.get(loser, []))),
            "competes": frozenset((winner, loser)) in competes,
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


def _theme_for_case(conflicts) -> str | None:
    for key, band in CURATED_BANDS.items():
        if any(band["defeated_contains"] in c["loser"] for c in conflicts):
            return key
    return None


def get_cross_case_band(theme_key: str, anchor_case_id: int) -> dict | None:
    band = CURATED_BANDS.get(theme_key)
    if not band:
        return None

    from app.models import Document

    keyword = band["defeated_contains"]
    rows = []
    for cid in band["case_ids"]:
        if cid == anchor_case_id:
            continue
        try:
            g = _load_graph(cid)
        except FileNotFoundError:
            logger.warning("cross-case band: case %s has no committed TTL (skipped)", cid)
            continue
        _competes, prevails, defeasible = _trio_edges(g)
        matches = []
        seen = set()
        for winner, loser in prevails:
            if keyword in loser and (winner, loser) not in seen:
                seen.add((winner, loser))
                matches.append({
                    "winner": winner,
                    "loser": loser,
                    "contexts": sorted(set(defeasible.get(loser, []))),
                })
        if not matches:
            continue
        doc = Document.query.get(cid)
        meta = doc.doc_metadata if (doc and isinstance(doc.doc_metadata, dict)) else {}
        rows.append({
            "case_id": cid,
            "title": doc.title if doc else f"Case {cid}",
            "case_number": meta.get("case_number", ""),
            "matches": matches,
        })
    return {"label": band["label"], "keyword": keyword, "rows": rows}


def refresh_band_index(case_id: int) -> int:
    """Rebuild this case's rows in the cross-case defeasibility index from its committed
    TTL. One row per resolved prevailsOver (winner, loser) pair, with the loser label's
    embedding precomputed. Idempotent (clears the case's existing rows first). Returns the
    number of rows written. Called at commit time after edge materialization."""
    from app.models import db
    from app.models.defeasibility_band_index import DefeasibilityBandIndex
    from app.services.embedding.embedding_service import EmbeddingService

    DefeasibilityBandIndex.query.filter_by(case_id=case_id).delete()

    try:
        g = _load_graph(case_id)
    except FileNotFoundError:
        # No committed TTL -> leave the case with no index rows.
        db.session.commit()
        return 0

    _competes, prevails, defeasible = _trio_edges(g)
    seen = set()
    pairs = []
    for winner, loser in prevails:
        if (winner, loser) in seen:
            continue
        seen.add((winner, loser))
        pairs.append((winner, loser))

    emb = EmbeddingService.get_instance()
    label_vec = {}
    for winner, loser in pairs:
        if loser not in label_vec:
            label_vec[loser] = emb.get_embedding(loser)
        db.session.add(DefeasibilityBandIndex(
            case_id=case_id,
            winner_label=winner,
            loser_label=loser,
            context_labels=sorted(set(defeasible.get(loser, []))),
            loser_embedding=label_vec[loser],
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


def get_cross_case_band_dynamic(anchor_case_id: int, case_data: dict) -> dict | None:
    """Cross-case band assembled from the commit-time index instead of a curated set.

    Ranks every other case's defeated-obligation pattern against the anchor's featured
    conflict by loser-obligation embedding similarity (0.7) plus State-context Jaccard
    overlap (0.3), keeps the best-scoring pattern per case, and returns the top five.
    The band label is generated from the anchor's winner/loser pair. Returns None when
    the anchor has no resolved conflict or the index holds no other cases.
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
        DefeasibilityBandIndex.case_id != anchor_case_id
    ).all()
    if not candidates:
        return None

    anchor_loser = featured["loser"]
    anchor_winner = featured["winner"]
    anchor_ctx = set(featured.get("contexts", []))
    anchor_vec = EmbeddingService.get_instance().get_embedding(anchor_loser)

    best = {}  # case_id -> (score, row)
    for r in candidates:
        sim = _cosine(anchor_vec, r.loser_embedding) if r.loser_embedding else 0.0
        cand_ctx = set(r.context_labels or [])
        union = anchor_ctx | cand_ctx
        jaccard = (len(anchor_ctx & cand_ctx) / len(union)) if union else 0.0
        score = 0.7 * sim + 0.3 * jaccard
        current = best.get(r.case_id)
        if current is None or score > current[0]:
            best[r.case_id] = (score, r)

    top = sorted(best.values(), key=lambda pair: pair[0], reverse=True)[:5]
    rows = []
    for score, r in top:
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
    if not rows:
        return None
    # Generated from the matched pair (no hand-written prose). Kept article-free so it
    # reads correctly whether the labels are common-noun obligations or engineer-prefixed.
    label = f"{anchor_loser} yields to {anchor_winner}"
    return {"label": label, "keyword": anchor_loser, "rows": rows, "dynamic": True}


def build_defeasibility_view(case_id: int) -> dict:
    """Assemble both bands for the case. Raises FileNotFoundError if the case has no
    committed ontology yet."""
    case_data = get_case_conflicts(case_id)
    # A curated theme, when one matches, pins the comparison set for a deterministic
    # walkthrough; otherwise the band is built dynamically from the commit-time index.
    theme = _theme_for_case(case_data["conflicts"])
    if theme:
        cross_case = get_cross_case_band(theme, case_id)
    else:
        cross_case = get_cross_case_band_dynamic(case_id, case_data)

    # Hover lookup over the entities the view renders: the anchor case plus the comparison
    # cases. Each entry links to its own committed OntServe ontology. The anchor case wins
    # on a label collision (cross-case labels are engineer-prefixed, so collisions are rare).
    lookup = {}
    cids = [case_id] + ([r["case_id"] for r in cross_case["rows"]] if cross_case else [])
    for cid in cids:
        try:
            g = _load_graph(cid)
        except FileNotFoundError:
            continue
        for key, entry in _entity_index(g, cid).items():
            lookup.setdefault(key, entry)

    return {
        "case_conflicts": case_data,
        "theme": theme,
        "cross_case": cross_case,
        "entity_lookup": lookup,
    }
