"""Consolidated entity matcher for extraction dedup / ontology linking.

Single source of truth for the entity-matching cascade that was previously
duplicated across four mechanisms:

  - ``auto_commit_service._check_duplicate`` / ``_check_embedding_duplicate``
    (the commit path: corpus = OntServe ``ontology_entities``, embedding via
    pgvector cosine). This is the richest mechanism and defines the canonical
    cascade: exact -> substring (type-marker gated) -> embedding, with rubric
    bands HIGH>=0.85 / MEDIUM>=0.70 / else novel, and the
    ``_SEMANTIC_TYPE_TO_MARKERS`` URI-substring category guard.
  - ``entity_reconciliation_service`` ``_normalize_label`` / ``_compute_similarity``
    (the within-case reconcile path) -- normalization + the 0.70 candidate
    threshold.
  - ``unified_dual_extractor._labels_match`` (exact normalized equality) and
    ``_reject_cross_category_match`` (curated subClassOf* chain category guard).

The component is pure: importing it requires no Flask app context and it holds
no DB dependency. The embedding tier is injected as a callable so the pgvector
query (commit path) or the in-memory cosine (reconcile path) stays in the
caller while the matcher owns the cascade, the category guard, and the bands.

Relation to the ``Matcher`` Protocol in ``base.py``: that Protocol is
batch-shaped (``match(candidates, *, world_id) -> List[MatchedConcept]``) and
ontology/world oriented. ``EntityMatcher.match`` here is the per-candidate
primitive a batch ``Matcher`` would call once per candidate; it returns a
richer ``MatchResult`` (method + band) than ``MatchedConcept`` carries. A thin
batch adapter conforming to the Protocol can wrap this without changing it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Thresholds and bands (canonical values, replicated from the four mechanisms)
# ---------------------------------------------------------------------------

# Rubric band cutoffs (ICCBR paper Section 3.3; auto_commit_service ~:450).
HIGH_BAND_MIN = 0.85
MEDIUM_BAND_MIN = 0.70  # == EMBEDDING_MATCH_MIN == LLM_CANDIDATE_THRESHOLD

# Fixed scores for the deterministic tiers (auto_commit_service._check_duplicate).
EXACT_SCORE = 1.0
SUBSTRING_SCORE = 0.87


class Band(Enum):
    """Rubric band a match score falls in."""
    HIGH = "high"      # cosine/score >= 0.85   -> auto-link
    MEDIUM = "medium"  # 0.70 <= score < 0.85   -> review-flag
    NONE = "none"      # < 0.70                 -> novel class


def band_for(score: float) -> Band:
    """Map a similarity score to its rubric band."""
    if score >= HIGH_BAND_MIN:
        return Band.HIGH
    if score >= MEDIUM_BAND_MIN:
        return Band.MEDIUM
    return Band.NONE


# ---------------------------------------------------------------------------
# Normalization (the single, most-thorough normalization)
# ---------------------------------------------------------------------------

_PAREN_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")
_WS_RE = re.compile(r"\s+")


def normalize_label(s: Optional[str]) -> str:
    """Canonical label normalization for matching.

    Most-thorough union of the three prior normalizations:
      - lowercase + strip                       (all three)
      - drop a single trailing parenthetical    (reconciliation _normalize_label)
      - collapse internal whitespace runs       (new; subsumes the
        underscore/hyphen handling implicitly via callers that pre-clean)

    Note vs prior copies: ``unified_dual._labels_match`` additionally replaced
    '_' and '-' with spaces. This normalization does NOT, to stay faithful to
    the reconciliation/auto_commit majority (which only lowercase+strip+paren).
    Callers that need separator folding should pre-clean; the lead must validate
    the unified_dual call sites where '_'/'-' folding mattered.
    """
    if not s:
        return ""
    s = s.lower().strip()
    s = _PAREN_SUFFIX_RE.sub("", s)
    s = _WS_RE.sub(" ", s)
    return s.strip()


# ---------------------------------------------------------------------------
# Category guard
# ---------------------------------------------------------------------------

# D-tuple semantic type -> URI-substring marker(s) for ProEthica class URIs.
# ProEthica class URIs use the singular form (FaithfulAgentObligation), so
# plural inputs collapse to the same marker. Kept as data (verbatim from
# auto_commit_service._SEMANTIC_TYPE_TO_MARKERS).
SEMANTIC_TYPE_TO_MARKERS: Dict[str, List[str]] = {
    'role':         ['Role'],
    'roles':        ['Role'],
    'principle':    ['Principle'],
    'principles':   ['Principle'],
    'obligation':   ['Obligation'],
    'obligations':  ['Obligation'],
    'state':        ['State'],
    'states':       ['State'],
    'resource':     ['Resource'],
    'resources':    ['Resource'],
    'action':       ['Action'],
    'actions':      ['Action'],
    'event':        ['Event'],
    'events':       ['Event'],
    'capability':   ['Capability'],
    'capabilities': ['Capability'],
    'constraint':   ['Constraint'],
    'constraints':  ['Constraint'],
}


def semantic_type_markers(category: Optional[str]) -> List[str]:
    """URI-substring marker(s) for a D-tuple semantic type.

    Falls back to the title-cased input for types outside the nine D-tuple
    components (verbatim from auto_commit_service._semantic_type_markers).
    """
    if not category:
        return []
    return SEMANTIC_TYPE_TO_MARKERS.get(category.lower(), [category.title()])


def category_compatible(
    candidate_category: Optional[str],
    target_uri_or_category: Optional[str],
    *,
    chain_resolver: Optional[Callable[[str], Optional[str]]] = None,
    marker_fallback: bool = True,
) -> bool:
    """Whether a candidate of ``candidate_category`` may match ``target``.

    Consolidates both prior category guards:

      1. URI-substring marker guard (auto_commit_service): when ``target`` is a
         class URI, it is compatible only if it contains one of the candidate
         category's D-tuple markers.
      2. Curated subClassOf* chain guard (unified_dual._reject_cross_category_match):
         when a ``chain_resolver`` is injected, the target's resolved core
         category must equal the candidate's. The resolver is authoritative; an
         unresolvable target (resolver returns None) is left compatible (cannot
         prove a conflict), matching the prior "leave the match in place"
         behavior.

    ``target_uri_or_category`` may be a full class URI or a bare core-category
    name; both forms are accepted by the marker check (substring) and by the
    resolver (which reduces a URI to its local name).

    ``marker_fallback`` (default True, the matcher's behavior) controls what
    happens when the chain resolver cannot place the target. With it on, an
    unresolved target falls through to the Tier-1 marker substring guard. With it
    OFF (chain-only mode), the resolver is the SOLE authority: an unresolved
    target is left compatible. Chain-only fits a bare, not-yet-registered label
    (e.g. an LLM-proposed generalization like ``EnvironmentalEngineer``, which
    carries no ``Role`` marker substring and would be wrongly rejected by Tier 1).

    A candidate with no category imposes no constraint (returns True), as in the
    prior guards (empty markers => no filter).
    """
    if not candidate_category:
        return True

    # Tier 2 (authoritative): curated-chain core category, when available.
    if chain_resolver is not None and target_uri_or_category:
        chain_cat = chain_resolver(target_uri_or_category)
        if chain_cat is not None:
            cand_markers = semantic_type_markers(candidate_category)
            # Compare on the marker token so plural/singular candidate input
            # ('roles' -> 'Role') lines up with the resolved core name ('Role').
            return chain_cat in cand_markers or chain_cat == candidate_category.title()
        if not marker_fallback:
            return True  # chain-only: an unresolvable target cannot prove a conflict
        # chain unresolved -> fall through to the marker guard (cannot prove a
        # conflict from the chain alone).

    # Tier 1: URI-substring marker guard.
    markers = semantic_type_markers(candidate_category)
    if not markers:
        return True
    target = target_uri_or_category or ""
    # A bare core-category name (no URI markers) is compatible iff it equals one
    # of the candidate's markers; a URI is compatible iff it contains one.
    return any(m in target for m in markers)


# ---------------------------------------------------------------------------
# Result and corpus contracts
# ---------------------------------------------------------------------------

@dataclass
class MatchResult:
    """A single resolved match from the cascade."""
    uri: str
    label: str
    score: float
    method: str  # 'exact' | 'substring' | 'embedding'
    band: Band


# A corpus record for the deterministic (exact/substring) tiers. Embedding is
# optional and unused by this matcher (the embedding tier is injected); it is
# part of the contract so a caller can carry it for its own injected search.
@dataclass
class CandidateRecord:
    uri: str
    label: str
    category: Optional[str] = None
    embedding: Optional[Sequence[float]] = None


# Injected embedding search: (label, definition, candidate_category) ->
# ranked [(uri, label, cosine)], best first. The caller owns the actual
# similarity computation (pgvector on the commit path, in-memory cosine on the
# reconcile path) and may pre-filter by category; the matcher still re-applies
# the category guard defensively.
EmbeddingSearch = Callable[
    [str, Optional[str], Optional[str]],
    Sequence[Tuple[str, str, float]],
]


# ---------------------------------------------------------------------------
# The matcher
# ---------------------------------------------------------------------------

class EntityMatcher:
    """Canonical exact -> substring -> embedding cascade with a category guard.

    The category guard is applied at every tier: a match incompatible with the
    candidate's category is never returned. ``match`` returns None when nothing
    clears the MEDIUM floor (0.70).
    """

    def __init__(
        self,
        *,
        embedding_search: Optional[EmbeddingSearch] = None,
        chain_resolver: Optional[Callable[[str], Optional[str]]] = None,
        alias_resolver: Optional[Callable[[str], Optional[tuple]]] = None,
    ):
        """
        Args:
            embedding_search: optional injected embedding tier. Omit to disable
                the embedding fallback (deterministic-only matching).
            chain_resolver: optional curated subClassOf* core-category resolver
                (e.g. ``category_resolver.resolve_core_category``). When given,
                the category guard uses the authoritative chain category and
                falls back to the URI-marker guard only when the chain is
                unknown.
            alias_resolver: optional curated synonym->canonical resolver, a
                callable(label) -> (canonical_uri, canonical_label) | None, built
                from the reference sheet (``ReferenceSheet.build_alias_resolver``).
                When given, a curated alias deterministically reuses the canonical
                class (it fires after exact equality and before the fuzzy tiers),
                so a known synonym or a do-not-mint compound never reaches the
                embedding tier or mints a new class. Omit to disable (default).
        """
        self._embedding_search = embedding_search
        self._chain_resolver = chain_resolver
        self._alias_resolver = alias_resolver

    # -- guard helper --

    def _compatible(self, candidate_category: Optional[str], target: Optional[str]) -> bool:
        return category_compatible(
            candidate_category, target, chain_resolver=self._chain_resolver,
        )

    # -- cascade --

    def match(
        self,
        candidate_label: str,
        candidate_category: Optional[str],
        *,
        corpus: Sequence[CandidateRecord],
        candidate_definition: Optional[str] = None,
    ) -> Optional[MatchResult]:
        """Resolve the best match for a candidate, or None below the MEDIUM floor.

        Cascade (category-guarded at every tier):
          1. exact     -> normalized label equality, score 1.0
          1.5 alias    -> curated synonym/do-not-mint -> canonical class (reference
             sheet), score 1.0; only when an ``alias_resolver`` is injected.
          2. substring -> normalized containment (either direction), score 0.87
          3. embedding -> delegated to the injected ``embedding_search``; the
             returned cosine is the score, gated at the MEDIUM floor.
        """
        norm_cand = normalize_label(candidate_label)

        # Tier 1: exact normalized equality.
        if norm_cand:
            for rec in corpus:
                if normalize_label(rec.label) != norm_cand:
                    continue
                if not self._compatible(candidate_category, rec.uri):
                    continue
                return MatchResult(
                    uri=rec.uri, label=rec.label, score=EXACT_SCORE,
                    method='exact', band=band_for(EXACT_SCORE),
                )

        # Tier 1.5: curated alias (reference sheet) -> deterministic canonical reuse.
        # A synonym or a same-category do-not-mint compound resolves to the canonical class before any
        # fuzzy tier, so it is reused rather than minted. The guard here uses the sheet's AUTHORITATIVE
        # component (not the IRI-marker / chain guard): the sheet curated the canonical's category, and the
        # target class may not be in the ontology yet, so trusting the sheet is both correct and necessary.
        if self._alias_resolver is not None and norm_cand:
            hit = self._alias_resolver(candidate_label)
            if hit:
                alias_uri, alias_label, alias_component = hit
                if (candidate_category is None or alias_component is None
                        or normalize_label(candidate_category) == normalize_label(alias_component)):
                    return MatchResult(
                        uri=alias_uri, label=alias_label, score=EXACT_SCORE,
                        method='alias', band=band_for(EXACT_SCORE),
                    )

        # Tier 2: substring containment (either direction), category-gated.
        if norm_cand:
            for rec in corpus:
                norm_rec = normalize_label(rec.label)
                if not norm_rec:
                    continue
                if norm_cand in norm_rec or norm_rec in norm_cand:
                    if not self._compatible(candidate_category, rec.uri):
                        continue
                    return MatchResult(
                        uri=rec.uri, label=rec.label, score=SUBSTRING_SCORE,
                        method='substring', band=band_for(SUBSTRING_SCORE),
                    )

        # Tier 3: injected embedding search.
        if self._embedding_search is not None:
            results = self._embedding_search(
                candidate_label, candidate_definition, candidate_category,
            ) or []
            for uri, label, cosine in results:
                score = float(cosine)
                if score < MEDIUM_BAND_MIN:
                    # Results are best-first; nothing below clears the floor.
                    break
                if not self._compatible(candidate_category, uri):
                    continue
                return MatchResult(
                    uri=uri, label=label, score=score,
                    method='embedding', band=band_for(score),
                )

        return None
