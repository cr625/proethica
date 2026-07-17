"""Unified search: OntServe ontology entity lane for the case search page.

Increment 1 of the unified-semantic-search plan: lexical entity search against
the OntServe database over the sanctioned direct cross-DB channel (see
docs-internal/architecture/ontserve-boundary.md). Semantic (pgvector) ranking
is added in increment 2; this module is its seam.

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

_CASE_ONTOLOGY_RE = re.compile(r'^proethica-case-(\d+)$')

_ENTITY_SEARCH_SQL = text("""
    SELECT oe.uri, oe.label, oe.comment, oe.entity_type, oe.parent_uri,
           o.name AS ontology_name, o.ontology_type
    FROM ontology_entities oe
    JOIN ontologies o ON o.id = oe.ontology_id
    WHERE oe.label IS NOT NULL
      AND (LOWER(oe.label) LIKE LOWER(:pattern)
           OR LOWER(oe.comment) LIKE LOWER(:pattern))
      AND (oe.properties->>'deprecated') IS DISTINCT FROM 'true'
    ORDER BY
        CASE WHEN LOWER(oe.label) = LOWER(:exact) THEN 0 ELSE 1 END,
        CASE WHEN o.ontology_type = 'case' THEN 1 ELSE 0 END,
        CASE oe.entity_type WHEN 'class' THEN 0 WHEN 'property' THEN 1 ELSE 2 END,
        LENGTH(oe.label)
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
    """Entity lane of the unified search. The engine is created lazily and is
    injectable for tests."""

    def __init__(self, engine=None):
        self._engine = engine

    @property
    def engine(self):
        if self._engine is None:
            self._engine = create_engine(get_ontserve_db_url())
        return self._engine

    def search_entities(self, query, limit=12):
        """Lexical entity search over all OntServe ontologies.

        Returns a list of dicts (deduplicated by URI, base ontologies winning
        over case copies) ready for template rendering. Raises on DB failure;
        the route decides how to surface the error.
        """
        query = (query or '').strip()
        if not query:
            return []

        web_url = get_ontserve_web_url().rstrip('/')
        with self.engine.connect() as conn:
            rows = conn.execute(_ENTITY_SEARCH_SQL, {
                'pattern': f'%{query}%',
                'exact': query,
                # Overfetch so URI-level dedup still fills the page.
                'limit': limit * 3,
            }).fetchall()

        results = []
        seen_uris = set()
        for row in rows:
            uri, label, comment, entity_type, parent_uri, onto_name, onto_type = row
            if uri in seen_uris:
                continue
            seen_uris.add(uri)
            category = derive_category(parent_uri, label)
            fragment = uri.rsplit('#', 1)[1] if '#' in uri else uri.rsplit('/', 1)[1]
            results.append({
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
            })
            if len(results) >= limit:
                break
        return results
