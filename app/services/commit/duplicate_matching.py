"""
Duplicate-matching mixin for AutoCommitService.

Extracted verbatim from auto_commit_service.py (god-file split PHASE 2 Step
2.5): the OntServe-class duplicate lookup path (exact label, substring, and
pgvector-embedding tiers). AutoCommitService gains DuplicateMatchingMixin as
a base class so every self._method(...) call site is unaffected.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import create_engine, text

from app.services.extraction.entity_matcher import (
    EntityMatcher,
    semantic_type_markers as _semantic_type_markers,
)
from app.services.ontserve.ontserve_config import get_ontserve_db_url

logger = logging.getLogger(__name__)


class DuplicateMatchingMixin:
    """OntServe-class duplicate lookup: exact label, substring, and
    pgvector-embedding cascade tiers."""

    def _check_duplicate(
        self, label: str, entity_type: str, definition: str = ""
    ) -> Optional[Tuple[str, float]]:
        """Find an existing OntServe class equivalent to the candidate.

        Tries exact label match, then substring match with a URI-marker
        type filter, then falls back to pgvector cosine similarity.
        Returns ``(uri, confidence)`` or ``None``. Confidence is 1.0 for
        exact label, 0.87 for substring, and the cosine score for the
        embedding path.

        Matcher unification 2026-06: the category guard markers
        (``_semantic_type_markers``), the embedding threshold
        (``EMBEDDING_MATCH_MIN`` == ``entity_matcher.MEDIUM_BAND_MIN``) and the
        embedding tier + bands are now sourced from ``entity_matcher`` (the
        embedding fallback runs through ``EntityMatcher.match``). The exact and
        substring tiers are kept INLINE with the original ``lower().strip()``
        normalization rather than routed through ``EntityMatcher.match``:
        BEHAVIOR-PRESERVING NOTE -- the matcher uses
        ``entity_matcher.normalize_label`` which additionally drops a trailing
        parenthetical and collapses whitespace. Over the live data this would
        flip at least one decision (a candidate "... (X)" whose paren-stripped
        form equals the existing class "NSPE Code of Ethics" would newly
        exact-match), so the parenthetical-preserving normalization is retained
        here and only the embedding tier / guard / bands are unified.
        """
        # Load OntServe classes if not cached
        if self._ontserve_classes_cache is None:
            self._load_ontserve_classes()

        if not self._ontserve_classes_cache:
            return None

        # Normalize label for comparison
        normalized_label = label.lower().strip()

        # Category guard: an entity may only reuse a class of its own D-tuple
        # category. Without this, a Constraint/Principle entity can match an
        # Obligation-named class by label, producing one class IRI that two
        # individuals would type to under conflicting materialized core categories
        # and an OWL-DL disjointness clash (proeth-core AllDisjointClasses). See
        # KI2026 corpus-consistency repair.
        type_markers = _semantic_type_markers(entity_type)

        def _category_ok(uri: str) -> bool:
            return not type_markers or any(m in uri for m in type_markers)

        # First try exact label match (category-guarded)
        for uri, class_info in self._ontserve_classes_cache.items():
            if class_info.get('label', '').lower().strip() == normalized_label:
                if not _category_ok(uri):
                    continue
                logger.info(f"Found exact label match for '{label}': {uri}")
                return uri, 1.0

        # Try partial match (label contains or is contained), gated by the
        # same URI-substring type filter the embedding path uses.
        for uri, class_info in self._ontserve_classes_cache.items():
            class_label = class_info.get('label', '').lower().strip()
            if normalized_label in class_label or class_label in normalized_label:
                if type_markers and not any(m in uri for m in type_markers):
                    continue
                logger.info(f"Found partial label match for '{label}': {uri}")
                return uri, 0.87

        # Embedding-based similarity fallback, via the shared cascade. The
        # pgvector query (with the URI-marker filter, LIMIT 1, ivfflat.probes)
        # stays here as the injected embedding_search; EntityMatcher applies the
        # MEDIUM floor and the bands. The deterministic tiers above already ran,
        # so the matcher is given an empty corpus and only its embedding tier
        # fires. The injected search already SQL-filters by marker, so the
        # matcher's defensive category guard (URI-marker, chain_resolver=None) is
        # a redundant no-op on the returned row -- behavior identical to the old
        # single-row threshold check.
        return self._check_embedding_duplicate(label, definition, entity_type)

    def _check_embedding_duplicate(
        self, label: str, definition: str, entity_type: str
    ) -> Optional[Tuple[str, float]]:
        """Nearest pgvector cosine match via the shared cascade.

        Preserves the original ``(label, definition, entity_type) ->
        (uri, cosine) | None`` contract. The pgvector query lives in the
        injected ``_embedding_search``; ``EntityMatcher`` (embedding-only, empty
        corpus) applies the MEDIUM floor (== EMBEDDING_MATCH_MIN) and the rubric
        bands. The injected search already SQL-filters by the URI marker, so the
        matcher's defensive URI-marker guard (chain_resolver=None) is a redundant
        no-op on the returned row -- identical to the old single-row threshold
        check.

        Rubric bands (ICCBR paper Section 3.3):
          HIGH   cosine >= 0.85       -> caller applies auto-link logic
          MEDIUM 0.70 <= c < 0.85     -> caller applies review-flag logic
          below  0.70                  -> None (novel class)
        """
        from app.services.extraction.reference_sheet import get_sheet
        matcher = EntityMatcher(
            embedding_search=self._embedding_search,
            alias_resolver=get_sheet().build_alias_resolver(),  # canonical reference-sheet reuse
        )
        result = matcher.match(
            label, entity_type, corpus=[], candidate_definition=definition,
        )
        if result is None:
            return None
        return result.uri, result.score

    def _embedding_search(
        self, label: str, definition: Optional[str], entity_type: Optional[str]
    ) -> List[Tuple[str, str, float]]:
        """Injected embedding tier for EntityMatcher: pgvector nearest cosine.

        Embeds 'label: definition' with all-MiniLM-L6-v2 and runs a single
        cosine query against ``ontology_entities.embedding`` (vector(384)
        with an IVFFlat cosine index already in place). The candidate's
        semantic type narrows the search to URIs containing the matching
        marker ('Obligation', 'Capability', etc.). Returns a best-first list of
        ``(uri, label, cosine)`` (here at most one row, mirroring the original
        ``LIMIT 1`` single-candidate behavior); the matcher applies the MEDIUM
        floor (== EMBEDDING_MATCH_MIN) and the rubric bands.

        Rubric bands (ICCBR paper Section 3.3):
          HIGH   cosine >= 0.85       -> caller applies auto-link logic
          MEDIUM 0.70 <= c < 0.85     -> caller applies review-flag logic
          below  0.70                  -> dropped by the matcher (novel class)
        """
        try:
            from app.services.embedding.embedding_service import EmbeddingService
            embedding_service = EmbeddingService.get_instance()

            candidate_text = f"{label}: {definition}" if definition else label
            raw = embedding_service._get_local_embedding(candidate_text)
            vec = list(raw) if not isinstance(raw, list) else raw

            # Build optional URI substring filter for the semantic type.
            markers = _semantic_type_markers(entity_type)
            params: Dict[str, Any] = {"vec": vec}
            if markers:
                like_clauses = []
                for i, marker in enumerate(markers):
                    key = f"m{i}"
                    like_clauses.append(f"uri LIKE :{key}")
                    params[key] = f"%{marker}%"
                marker_sql = "AND (" + " OR ".join(like_clauses) + ")"
            else:
                marker_sql = ""

            sql = text(f"""
                SELECT uri, label,
                       1 - (embedding <=> CAST(:vec AS vector)) AS cosine
                FROM ontology_entities
                WHERE entity_type = 'class'
                  AND uri LIKE 'http://proethica.org/ontology/%'
                  AND uri NOT LIKE 'http://proethica.org/ontology/core#%'
                  AND embedding IS NOT NULL
                  AND properties->>'deprecated' IS DISTINCT FROM 'true'
                  {marker_sql}
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT 1
            """)

            engine = create_engine(get_ontserve_db_url())
            with engine.connect() as conn:
                # Probe every list so the IVFFlat lookup is exact, not approximate.
                conn.execute(text("SET LOCAL ivfflat.probes = 100"))
                row = conn.execute(sql, params).fetchone()

            if row is None:
                return []
            cosine = float(row.cosine)
            logger.info(
                "Embedding candidate: '%s' (%s) -> %s (cosine=%.3f)",
                label, entity_type, row.uri, cosine,
            )
            return [(row.uri, row.label, cosine)]

        except Exception as e:
            from app.utils.dev_guard import fail_loud_in_dev
            fail_loud_in_dev(e, "Embedding duplicate check failed -- a swallowed error reads as "
                                "'no match' and mints a new (possibly duplicate) class")
            logger.warning("Embedding duplicate check failed: %s", e)
            return []

    def _load_ontserve_classes(self):
        """Load OntServe classes from database for duplicate checking."""
        try:
            # Query OntServe's ontology_entities table for proethica classes
            # Restrict to class entities outside the core namespace. The
            # duplicate matcher decides whether a proposed class collides with
            # an existing one, so individuals and properties only add noise.
            # core# holds the bare D-tuple base classes (Obligation, Capability,
            # etc.) which would always trip the substring matcher trivially;
            # candidates are by definition more specific than those.
            query = text("""
                SELECT uri, label, entity_type, comment
                FROM ontology_entities
                WHERE uri LIKE 'http://proethica.org/ontology/%'
                  AND uri NOT LIKE 'http://proethica.org/ontology/core#%'
                  AND entity_type = 'class'
                  -- Same serving-side deprecation predicate as the category
                  -- inventories (concept_manager) and the web hierarchy/search:
                  -- the matcher must never link a fresh extraction to retired
                  -- vocabulary (owl:deprecated classes stay resolvable, but are
                  -- not match candidates).
                  AND properties->>'deprecated' IS DISTINCT FROM 'true'
            """)

            # Use a separate connection to ontserve database
            ontserve_engine = create_engine(get_ontserve_db_url())

            with ontserve_engine.connect() as conn:
                result = conn.execute(query)
                self._ontserve_classes_cache = {}

                for row in result:
                    self._ontserve_classes_cache[row[0]] = {
                        'label': row[1],
                        'type': row[2],
                        'definition': row[3]
                    }

                logger.info(f"Loaded {len(self._ontserve_classes_cache)} OntServe classes")

        except Exception as e:
            from app.utils.dev_guard import fail_loud_in_dev
            fail_loud_in_dev(e, "OntServe class cache failed to load -- an empty cache reads as "
                                "'no existing classes' and mints EVERY entity as new (no dedup)")
            logger.warning(f"Could not load OntServe classes: {e}")
            self._ontserve_classes_cache = {}
