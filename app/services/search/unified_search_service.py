"""Unified search: OntServe ontology entity lane for the case search page.

Increments 1-2 of the unified-semantic-search plan: hybrid lexical + semantic
entity search against the OntServe database over the sanctioned direct cross-DB
channel (see docs-internal/architecture/ontserve-boundary.md).

Both ProEthica and OntServe embed with all-MiniLM-L6-v2 (384 dims), so the
query vector computed here is directly comparable to OntServe's
ontology_entities.embedding column. The lexical arm also computes each hit's
cosine distance, so every result with an embedding carries an honest score;
semantic-only hits below MIN_SEMANTIC_SCORE are dropped so that nonsense
queries return an empty lane instead of confident-looking noise.

Results carry the nine-component category (derived from parent_uri, the same
suffix convention OntServe's case_display.py uses) and the canonical component
color from app.concept_meta, plus a link to the OntServe entity page and, for
case-minted entities, the owning case id.
"""

import logging
import re

from sqlalchemy import create_engine, text

from app.concept_meta import CONCEPT_COLORS
from app.services.ontserve.ontserve_config import (
    get_ontserve_db_url,
    get_ontserve_web_url,
)

logger = logging.getLogger(__name__)

# Singular category name -> canonical color (concept_meta keys are plural).
CATEGORY_COLORS = {
    'Role': CONCEPT_COLORS['roles'],
    'State': CONCEPT_COLORS['states'],
    'Resource': CONCEPT_COLORS['resources'],
    'Principle': CONCEPT_COLORS['principles'],
    'Obligation': CONCEPT_COLORS['obligations'],
    'Constraint': CONCEPT_COLORS['constraints'],
    'Capability': CONCEPT_COLORS['capabilities'],
    'Action': CONCEPT_COLORS['actions'],
    'Event': CONCEPT_COLORS['events'],
}

# Floor for hits found ONLY by the semantic arm (no substring match). MiniLM
# cosine similarity of an unrelated short query against entity label+comment
# text typically stays below this; topical matches land well above.
MIN_SEMANTIC_SCORE = 0.35

_CASE_ONTOLOGY_RE = re.compile(r'^proethica-case-(\d+)$')

_COMMON_FILTER = """
    FROM ontology_entities oe
    JOIN ontologies o ON o.id = oe.ontology_id
    WHERE oe.label IS NOT NULL
      AND (oe.properties->>'deprecated') IS DISTINCT FROM 'true'
"""

_LEXICAL_SQL = text(f"""
    SELECT oe.uri, oe.label, oe.comment, oe.entity_type, oe.parent_uri,
           o.name AS ontology_name, o.ontology_type,
           NULL AS distance
    {_COMMON_FILTER}
      AND (LOWER(oe.label) LIKE LOWER(:pattern)
           OR LOWER(oe.comment) LIKE LOWER(:pattern))
    ORDER BY
        CASE WHEN LOWER(oe.label) = LOWER(:exact) THEN 0 ELSE 1 END,
        CASE WHEN o.ontology_type = 'case' THEN 1 ELSE 0 END,
        CASE oe.entity_type WHEN 'class' THEN 0 WHEN 'property' THEN 1 ELSE 2 END,
        LENGTH(oe.label)
    LIMIT :limit
""")

# Same shape as the lexical arm, but with a real per-row distance.
_LEXICAL_SCORED_SQL = text(f"""
    SELECT oe.uri, oe.label, oe.comment, oe.entity_type, oe.parent_uri,
           o.name AS ontology_name, o.ontology_type,
           (oe.embedding <=> CAST(:qvec AS vector)) AS distance
    {_COMMON_FILTER}
      AND (LOWER(oe.label) LIKE LOWER(:pattern)
           OR LOWER(oe.comment) LIKE LOWER(:pattern))
    ORDER BY
        CASE WHEN LOWER(oe.label) = LOWER(:exact) THEN 0 ELSE 1 END,
        CASE WHEN o.ontology_type = 'case' THEN 1 ELSE 0 END,
        CASE oe.entity_type WHEN 'class' THEN 0 WHEN 'property' THEN 1 ELSE 2 END,
        LENGTH(oe.label)
    LIMIT :limit
""")

# DISTINCT ON collapses the many per-case copies of one URI to a single row
# (preferring the base-ontology row) BEFORE the top-k cut; without it the
# nearest-neighbor list is a handful of entities repeated across the 119 case
# ontologies. The corpus is ~50k embedded rows, so the exact scan is cheap.
_SEMANTIC_SQL = text(f"""
    SELECT * FROM (
        SELECT DISTINCT ON (oe.uri)
               oe.uri, oe.label, oe.comment, oe.entity_type, oe.parent_uri,
               o.name AS ontology_name, o.ontology_type,
               (oe.embedding <=> CAST(:qvec AS vector)) AS distance
        {_COMMON_FILTER}
          AND oe.embedding IS NOT NULL
        ORDER BY oe.uri,
                 CASE WHEN o.ontology_type = 'case' THEN 1 ELSE 0 END,
                 (oe.embedding <=> CAST(:qvec AS vector))
    ) deduped
    ORDER BY distance
    LIMIT :limit
""")


def derive_category(parent_uri, label):
    """Map an entity to one of the nine component categories, or None.

    Prefers the parent_uri fragment (exact core name, then suffix match, the
    convention case individuals follow, e.g. intermediate#PublicWelfarePrinciple
    -> Principle); falls back to a label suffix match for base classes whose
    parent is outside the nine (e.g. a BFO ancestor).
    """
    if parent_uri and '#' in parent_uri:
        frag = parent_uri.rsplit('#', 1)[1]
        if frag in CATEGORY_COLORS:
            return frag
        for cat in CATEGORY_COLORS:
            if frag.endswith(cat):
                return cat
    if label:
        compact = label.replace(' ', '')
        for cat in CATEGORY_COLORS:
            if compact.endswith(cat):
                return cat
    return None


def case_id_for(ontology_name):
    """Return the owning case id for a proethica-case-N ontology, else None."""
    m = _CASE_ONTOLOGY_RE.match(ontology_name or '')
    return int(m.group(1)) if m else None


class UnifiedSearchService:
    """Entity lane of the unified search. The engine and embedder are
    injectable for tests."""

    def __init__(self, engine=None, embed_fn=None):
        self._engine = engine
        self._embed_fn = embed_fn

    @property
    def engine(self):
        if self._engine is None:
            self._engine = create_engine(get_ontserve_db_url())
        return self._engine

    def _query_vector(self, query):
        """Return the 384-dim query embedding as a pgvector literal, or None
        (lexical-only degrade, logged loudly per plan decision D5)."""
        try:
            if self._embed_fn is not None:
                vec = self._embed_fn(query)
            else:
                from app.services.embedding.embedding_service import EmbeddingService
                vec = EmbeddingService.get_instance()._get_local_embedding(query)
        except Exception as e:
            logger.warning(f"Query embedding failed; entity lane degrades to lexical-only: {e}")
            return None
        if not vec or len(vec) != 384:
            logger.warning(
                f"Query embedding has dimension {len(vec) if vec else 0}, expected 384; "
                "entity lane degrades to lexical-only")
            return None
        return '[' + ','.join(str(x) for x in vec) + ']'

    def search_entities(self, query, limit=12):
        """Hybrid lexical + semantic entity search over all OntServe ontologies.

        Returns a list of dicts (deduplicated by URI, base ontologies winning
        over case copies) ranked exact-label first, then by semantic score.
        Raises on DB failure; the route decides how to surface the error.
        """
        query = (query or '').strip()
        if not query:
            return []

        qvec = self._query_vector(query)
        overfetch = limit * 3  # URI-level dedup shrinks the raw rows

        with self.engine.connect() as conn:
            if qvec is None:
                lexical = conn.execute(_LEXICAL_SQL, {
                    'pattern': f'%{query}%', 'exact': query, 'limit': overfetch,
                }).fetchall()
                semantic = []
            else:
                lexical = conn.execute(_LEXICAL_SCORED_SQL, {
                    'pattern': f'%{query}%', 'exact': query, 'limit': overfetch,
                    'qvec': qvec,
                }).fetchall()
                semantic = conn.execute(_SEMANTIC_SQL, {
                    'qvec': qvec, 'limit': overfetch,
                }).fetchall()

        return self._merge(query, lexical, semantic, limit)

    def _merge(self, query, lexical, semantic, limit):
        """Dedup by URI (lexical arm first, so its base-over-case ordering
        wins), attach scores, floor semantic-only hits, rank, truncate."""
        web_url = get_ontserve_web_url().rstrip('/')
        query_lower = query.lower()

        merged = {}
        for row, from_lexical in (
                [(r, True) for r in lexical] + [(r, False) for r in semantic]):
            uri = row[0]
            if uri in merged:
                # Keep the first occurrence but adopt a score or the lexical
                # flag the later duplicate contributes.
                entry = merged[uri]
                if entry['score'] is None and row[7] is not None:
                    entry['score'] = max(0.0, 1.0 - float(row[7]))
                entry['lexical'] = entry['lexical'] or from_lexical
                continue
            (_, label, comment, entity_type, parent_uri,
             onto_name, onto_type, distance) = row
            category = derive_category(parent_uri, label)
            fragment = uri.rsplit('#', 1)[1] if '#' in uri else uri.rsplit('/', 1)[1]
            merged[uri] = {
                'uri': uri,
                'label': label,
                'definition': comment,
                'entity_type': entity_type,
                'category': category,
                'color': CATEGORY_COLORS.get(category),
                'ontology_name': onto_name,
                'ontology_type': onto_type,
                'case_id': case_id_for(onto_name),
                'ontserve_url': f'{web_url}/entity/{onto_name}/{fragment}',
                'score': max(0.0, 1.0 - float(distance)) if distance is not None else None,
                'lexical': from_lexical,
                'exact': (label or '').lower() == query_lower,
            }

        results = [
            e for e in merged.values()
            if e['lexical'] or (e['score'] is not None and e['score'] >= MIN_SEMANTIC_SCORE)
        ]
        # Exact label first, then score descending (unscored lexical hits last).
        results.sort(key=lambda e: (
            0 if e['exact'] else 1,
            -(e['score'] if e['score'] is not None else -1.0),
        ))
        return results[:limit]
