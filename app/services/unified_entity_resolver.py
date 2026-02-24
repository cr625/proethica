"""
Unified Entity Resolver - Resolves entities from both case storage and base ontology.

Provides a single interface for entity lookups across:
- Case-specific entities from TemporaryRDFStorage
- Base ontology classes from OntServe MCP

Case entities take precedence over base ontology when URIs match.
"""

import logging
import re
import time
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Cache for OntServe entities (shared across instances)
_ontserve_cache = {
    'entities': None,
    'timestamp': 0
}
ONTSERVE_CACHE_TTL = 600  # 10 minutes


class UnifiedEntityResolver:
    """Resolves entities from both case storage and base ontology."""

    # Map extraction types to pass numbers
    PASS_MAP = {
        'roles': 1, 'states': 1, 'resources': 1,
        'principles': 2, 'obligations': 2, 'constraints': 2, 'capabilities': 2,
        'temporal_dynamics_enhanced': 3, 'actions': 3, 'events': 3,
        'code_provision_reference': 4, 'ethical_question': 4, 'ethical_conclusion': 4,
        'causal_normative_link': 4, 'question_emergence': 4, 'resolution_pattern': 4,
        'canonical_decision_point': 4
    }

    # Map entity types to display categories
    ENTITY_TYPE_MAP = {
        'Role': 'roles',
        'State': 'states',
        'Resource': 'resources',
        'Principle': 'principles',
        'Obligation': 'obligations',
        'Constraint': 'constraints',
        'Capability': 'capabilities',
        'Action': 'actions',
        'Event': 'events',
    }

    def __init__(self, case_id: int = None):
        """
        Initialize resolver.

        Args:
            case_id: Optional case ID for case-specific entity resolution
        """
        self.case_id = case_id
        self._lookup_cache = None
        self._label_index = None

    def get_lookup_dict(self) -> Dict[str, Dict]:
        """
        Build unified lookup dictionary.

        Returns dict keyed by URI with:
        - label: Display name
        - definition: Description text
        - entity_type: Role/State/Principle/etc
        - extraction_type: Original extraction type
        - source: 'case' or 'ontology'
        - source_pass: 1-4 or None for ontology
        """
        if self._lookup_cache is not None:
            return self._lookup_cache

        lookup = {}

        # 1. Load OntServe base classes (lower precedence)
        ontserve_entities = self._get_ontserve_entities()
        for uri, data in ontserve_entities.items():
            lookup[uri] = {
                **data,
                'source': 'ontology',
                'source_pass': None
            }

        # 2. Load case entities (higher precedence, overwrites)
        if self.case_id:
            case_entities = self._get_case_entities()
            for uri, data in case_entities.items():
                lookup[uri] = {
                    **data,
                    'source': 'case'
                }

        # 3. Build label-based index for text matching
        self._build_label_index(lookup)

        self._lookup_cache = lookup
        return lookup

    def get_label_index(self) -> Dict[str, Dict]:
        """
        Get label-based index for text matching.

        Returns dict keyed by lowercase label -> entity data
        """
        if self._label_index is None:
            self.get_lookup_dict()  # Builds label index
        return self._label_index or {}

    def resolve(self, uri_or_label: str) -> Optional[Dict]:
        """
        Resolve a single entity by URI or label.

        Args:
            uri_or_label: Entity URI or display label

        Returns:
            Entity data dict or None if not found
        """
        lookup = self.get_lookup_dict()

        # Try URI first
        if uri_or_label in lookup:
            return lookup[uri_or_label]

        # Try label index
        label_index = self.get_label_index()
        label_key = uri_or_label.lower().strip()
        if label_key in label_index:
            return label_index[label_key]

        return None

    def _get_ontserve_entities(self) -> Dict[str, Dict]:
        """
        Fetch all proethica ontology entities from OntServe.

        Uses cached data if available and not expired.
        """
        global _ontserve_cache

        # Check cache
        now = time.time()
        if (_ontserve_cache['entities'] is not None and
                now - _ontserve_cache['timestamp'] < ONTSERVE_CACHE_TTL):
            logger.debug("Using cached OntServe entities")
            return _ontserve_cache['entities']

        # Fetch from OntServe
        entities = {}
        try:
            from app.services.external_mcp_client import get_external_mcp_client
            client = get_external_mcp_client()

            # Fetch each category
            category_methods = [
                ('get_all_role_entities', 'roles'),
                ('get_all_state_entities', 'states'),
                ('get_all_resource_entities', 'resources'),
                ('get_all_principle_entities', 'principles'),
                ('get_all_obligation_entities', 'obligations'),
                ('get_all_constraint_entities', 'constraints'),
                ('get_all_capability_entities', 'capabilities'),
                ('get_all_action_entities', 'actions'),
                ('get_all_event_entities', 'events'),
            ]

            for method_name, entity_type in category_methods:
                try:
                    method = getattr(client, method_name, None)
                    if method:
                        items = method()
                        for item in items:
                            uri = item.get('uri', '')
                            if uri:
                                entities[uri] = {
                                    'label': item.get('label', item.get('name', '')),
                                    'definition': item.get('description', item.get('comment', '')),
                                    'entity_type': entity_type,
                                    'extraction_type': entity_type,
                                    'uri': uri,
                                    'is_published': True,
                                    'source_pass': None,
                                }
                except Exception as e:
                    logger.warning(f"Failed to fetch {entity_type} from OntServe: {e}")

            logger.info(f"Fetched {len(entities)} entities from OntServe")

        except Exception as e:
            logger.warning(f"Failed to connect to OntServe: {e}")

        # Update cache
        _ontserve_cache['entities'] = entities
        _ontserve_cache['timestamp'] = now

        return entities

    def _get_case_entities(self) -> Dict[str, Dict]:
        """
        Fetch all entities for current case from TemporaryRDFStorage.
        """
        if not self.case_id:
            return {}

        from app.models import TemporaryRDFStorage

        entities = TemporaryRDFStorage.query.filter_by(case_id=self.case_id).all()
        lookup = {}

        for entity in entities:
            source_pass = self.PASS_MAP.get(entity.extraction_type, 0)

            # Get definition from database field first, then fall back to RDF fields
            definition = entity.entity_definition or ''
            if not definition and entity.rdf_json_ld and isinstance(entity.rdf_json_ld, dict):
                rdf = entity.rdf_json_ld
                # Try standard RDF fields first
                definition = (
                    rdf.get('proeth:description') or
                    rdf.get('description') or
                    rdf.get('rdfs:comment') or
                    rdf.get('proeth-scenario:ethicalTension') or
                    ''
                )
                # For Pass 1-2 entities, try properties fields
                if not definition and rdf.get('properties'):
                    props = rdf.get('properties', {})
                    if props.get('caseInvolvement'):
                        inv = props.get('caseInvolvement')
                        definition = inv[0] if isinstance(inv, list) else inv
                    elif props.get('hasEthicalTension'):
                        tension = props.get('hasEthicalTension')
                        definition = tension[0] if isinstance(tension, list) else tension
                # Try source_text as last resort
                if not definition and rdf.get('source_text'):
                    definition = rdf.get('source_text')
                # For competing priorities
                if not definition and rdf.get('proeth:hasCompetingPriorities'):
                    cp = rdf.get('proeth:hasCompetingPriorities', {})
                    if isinstance(cp, dict):
                        definition = cp.get('proeth:priorityConflict', '')

            entity_data = {
                'label': entity.entity_label,
                'definition': definition,
                'entity_type': entity.entity_type,
                'extraction_type': entity.extraction_type,
                'is_published': entity.is_published,
                'source_pass': source_pass,
                'provenance': entity.provenance_metadata or {},
                'uri': entity.entity_uri,
                # Additional RDF metadata for richer display
                'rdf_agent': entity.rdf_json_ld.get('proeth:hasAgent') if entity.rdf_json_ld else None,
                'rdf_temporal': entity.rdf_json_ld.get('proeth:temporalMarker') if entity.rdf_json_ld else None
            }

            # Index by URI if available
            if entity.entity_uri:
                lookup[entity.entity_uri] = entity_data

                # Also index by URI prefix (without trailing suffixes)
                if '#' in entity.entity_uri:
                    fragment = entity.entity_uri.split('#')[-1]
                    base_url = entity.entity_uri.rsplit('#', 1)[0]
                    # Strip common suffixes that get added during extraction
                    for suffix in ['_Design', '_Engineer', '_No', '_Ber', '_Failed', '_Contractor']:
                        if fragment.endswith(suffix):
                            truncated_uri = f"{base_url}#{fragment[:-len(suffix)]}"
                            if truncated_uri not in lookup:
                                lookup[truncated_uri] = entity_data

            # Create synthetic short-form URI keys for matching
            if entity.entity_label:
                label_key = re.sub(r'[^\w\s]', '', entity.entity_label)
                label_key = label_key.replace(' ', '_')
                short_uri = f"case-{self.case_id}#{label_key}"
                lookup[short_uri] = entity_data

                # Also try without underscores
                camel_key = label_key.replace('_', '')
                short_uri_camel = f"case-{self.case_id}#{camel_key}"
                if short_uri_camel not in lookup:
                    lookup[short_uri_camel] = entity_data

        return lookup

    def _build_label_index(self, lookup: Dict[str, Dict]) -> None:
        """
        Build label-based index for text matching.

        Creates index mapping lowercase labels to entity data.
        Skips entries with empty definitions (they produce useless popovers).
        """
        self._label_index = {}

        for uri, data in lookup.items():
            label = data.get('label', '')
            definition = data.get('definition', '')
            if not label:
                continue
            # Skip ontology entries with no definition -- these are stale
            # concepts that produce "No definition available" popovers
            if not definition and data.get('source') == 'ontology':
                continue

            # Lowercase for case-insensitive matching
            label_key = label.lower().strip()
            # Case entities take precedence
            if label_key not in self._label_index or data.get('source') == 'case':
                self._label_index[label_key] = data

            # Also index without underscores
            label_no_underscore = label_key.replace('_', ' ')
            if label_no_underscore != label_key:
                if label_no_underscore not in self._label_index or data.get('source') == 'case':
                    self._label_index[label_no_underscore] = data

    @staticmethod
    def clear_ontserve_cache():
        """Clear the OntServe cache to force refresh."""
        global _ontserve_cache
        _ontserve_cache['entities'] = None
        _ontserve_cache['timestamp'] = 0
        logger.info("Cleared OntServe entity cache")


def get_unified_entity_lookup(case_id: int = None) -> Dict[str, Dict]:
    """
    Convenience function to get unified entity lookup dictionary.

    Args:
        case_id: Optional case ID for case-specific entities

    Returns:
        Unified lookup dictionary
    """
    resolver = UnifiedEntityResolver(case_id=case_id)
    return resolver.get_lookup_dict()
