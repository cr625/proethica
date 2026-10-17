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

    # URI namespace to ontology_target mapping
    _URI_ONTOLOGY_PATTERNS = [
        (r'http://proethica\.org/ontology/case/(\d+)#', 'proethica-case-{}'),
        (r'http://proethica\.org/ontology/intermediate#', 'proethica-intermediate'),
    ]

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

    # Ontologies that define the shared vocabulary. The MCP category inventory
    # returns one row per ontology that declares a URI; a row from one of these
    # outranks a row for the same URI from any other ontology (a case ontology
    # re-declares the classes it uses without defining them).
    DEFINITIONAL_ONTOLOGIES = (
        'proethica-intermediate', 'proethica-intermediate-extended', 'proethica-core',
    )

    # OntServe substitutes this text for a class without an rdfs:comment. It
    # is not a definition and never reaches the popover layer.
    _PLACEHOLDER_DESCRIPTION = re.compile(r'^\s*ontology class for \w+\.?\s*$', re.IGNORECASE)

    # Leading actor designator of a case-entity label, used when the case has
    # no Agent individual to take the actor from: "Engineer A", "Client W",
    # "Engineer Doe".
    _ACTOR_DESIGNATOR = re.compile(
        r'^((?:[A-Z][a-z]+ [A-Z])'
        r'|(?:(?:Engineer|Client|Contractor|Owner|Employer|Employee|Firm|Company|Developer'
        r'|Architect|Surveyor|Technician|Inspector|Supervisor|Manager|Director|Consultant'
        r'|Student|Professor|Attorney|Doctor|Agency|City|County|Town) [A-Z][a-z]+))'
        r'(?![A-Za-z0-9_])'
    )

    # A cited Board case ("BER Case 76-4"). Case text cites it as "Case 76-4".
    _CITED_CASE_LABEL = re.compile(r'^BER (Case \d{2}-\d{1,2})$', re.IGNORECASE)

    def __init__(self, case_id: int = None, case_source: str = 'working'):
        """
        Initialize resolver.

        Args:
            case_id: Optional case ID for case-specific entity resolution
            case_source: Where case entities are read from. 'working' reads the
                in-progress extraction in TemporaryRDFStorage (pipeline review
                views). 'committed' reads the committed case TTL in OntServe,
                the completed-state record; callers gate on
                committed_case_graph.committed_case_exists first.
        """
        self.case_id = case_id
        self.case_source = case_source
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
            if self.case_source == 'committed':
                case_entities = self._get_committed_case_entities()
            else:
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
            from app.services.ontserve.external_mcp_client import get_external_mcp_client
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

            ranks = {}
            for method_name, entity_type in category_methods:
                try:
                    method = getattr(client, method_name, None)
                    if method:
                        items = method()
                        for item in items:
                            uri = item.get('uri', '')
                            if not uri:
                                continue
                            rank = self._ontserve_row_rank(item)
                            if rank is None or (uri in entities and ranks[uri] >= rank):
                                continue
                            ranks[uri] = rank
                            source_ontology = (self._ontserve_row_source(item)
                                               or self._derive_ontology_target(uri)
                                               or 'proethica-intermediate')
                            entities[uri] = {
                                'label': item.get('label', item.get('name', '')),
                                'definition': self._ontserve_row_description(item),
                                'entity_type': entity_type,
                                'extraction_type': entity_type,
                                'uri': uri,
                                'is_published': True,
                                'source_pass': None,
                                'ontology_target': source_ontology,
                                'ontserve_path': self.compute_ontserve_path(uri, source_ontology),
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

    # Values OntServe writes into the source field of an inventory row that
    # name a table, not an ontology: 'concepts' on a concepts-table row and
    # 'ontology' on an ontology row without an ontology name. Neither is an
    # ontology_target; such a row takes the target of its URI namespace.
    _NON_ONTOLOGY_SOURCES = frozenset({'concepts', 'ontology'})

    @classmethod
    def _ontserve_row_source(cls, item: Dict) -> str:
        """Name of the ontology that declares a category-inventory row, or ''."""
        source = str(item.get('source') or item.get('ontology_name') or '').strip()
        return '' if source.lower() in cls._NON_ONTOLOGY_SOURCES else source

    @staticmethod
    def _ontserve_row_description(item: Dict) -> str:
        return str(item.get('description') or item.get('comment') or '')

    @classmethod
    def _ontserve_row_rank(cls, item: Dict) -> Optional[tuple]:
        """
        Rank a category-inventory row for the base lookup, or None to skip it.

        Rows declared by a case ontology and rows carrying the OntServe
        placeholder description are skipped. Of the rows left for one URI, a
        definitional ontology outranks the rest, then a row with a description
        outranks one without, then the ontology whose namespace the URI
        belongs to outranks another ontology that declares the same URI.
        """
        source = cls._ontserve_row_source(item)
        if source.startswith('proethica-case-'):
            return None
        description = cls._ontserve_row_description(item)
        if cls._PLACEHOLDER_DESCRIPTION.match(description):
            return None
        # Two definitional ontologies can both describe one URI (a class
        # copied into the extended store before the class commit refused
        # base copies). The ontology whose namespace the URI belongs to wins
        # the tie, so the ontology_target does not follow the row order of
        # the inventory.
        owns_namespace = bool(source) and source == cls._derive_ontology_target(str(item.get('uri') or ''))
        return (source in cls.DEFINITIONAL_ONTOLOGIES, bool(description.strip()), owns_namespace)

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
                # Last resort: the entity's own label. (Replaced the action
                # competing_priorities/priorityConflict fallback, dropped 2026-06-01 with
                # that field.)
                if not definition:
                    definition = entity.entity_label or ''

            # Extract textReferences for alias detection
            text_refs = []
            if entity.rdf_json_ld and isinstance(entity.rdf_json_ld, dict):
                props = entity.rdf_json_ld.get('properties', {})
                text_refs = props.get('textReferences', [])

            ont_target = entity.ontology_target or self._derive_ontology_target(entity.entity_uri or '')

            entity_data = {
                'label': entity.entity_label,
                'definition': definition,
                'entity_type': entity.entity_type,
                'extraction_type': entity.extraction_type,
                'is_published': entity.is_published,
                'source_pass': source_pass,
                'provenance': entity.provenance_metadata or {},
                'uri': entity.entity_uri,
                'text_references': text_refs,
                'ontology_target': ont_target,
                'ontserve_path': self.compute_ontserve_path(entity.entity_uri or '', ont_target),
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

    def _get_committed_case_entities(self) -> Dict[str, Dict]:
        """
        Build case-entity entries from the committed case TTL in OntServe.

        Same entry shape as _get_case_entities so the label index, alias
        extraction, and template serialization are shared. Only named
        individuals are indexed; support nodes (prov:Derivation, OWL-Time
        instants) carry no owl:NamedIndividual typing and are skipped.
        Raises FileNotFoundError when the case has no committed ontology.
        """
        from rdflib import RDF, Namespace
        from rdflib.namespace import OWL, RDFS, SKOS
        from app.services.entity.committed_case_graph import load_case_graph

        g = load_case_graph(self.case_id)
        PROETH = Namespace('http://proethica.org/ontology/intermediate#')
        PROETH_PROV = Namespace('http://proethica.org/provenance#')
        core_ns = 'http://proethica.org/ontology/core#'
        ont_target = f'proethica-case-{self.case_id}'

        lookup = {}
        exact_fragment = {}
        for s in g.subjects(RDF.type, OWL.NamedIndividual):
            label = g.value(s, RDFS.label)
            if not label:
                continue
            label = str(label)

            definition = str(
                g.value(s, SKOS.definition)
                or g.value(s, RDFS.comment)
                or g.value(s, PROETH.caseInvolvement)
                or ''
            )

            # Category from the materialized direct core type (CMT-1); analysis-layer
            # individuals (EthicalQuestion, DecisionPoint, ...) fall back to their
            # first non-core type's local name.
            category = ''
            other_type = ''
            for t in g.objects(s, RDF.type):
                tn = str(t)
                if tn.startswith(core_ns) and tn[len(core_ns):] in self.ENTITY_TYPE_MAP:
                    category = tn[len(core_ns):]
                    break
                if t != OWL.NamedIndividual and not other_type:
                    other_type = tn.rsplit('#', 1)[-1].rsplit('/', 1)[-1]
            extraction_type = self.ENTITY_TYPE_MAP.get(category, other_type)

            source_pass = g.value(s, PROETH_PROV.discoveredInStep)
            text_refs = [str(o) for o in g.objects(s, PROETH.textReferences)]
            uri = str(s)

            entity_data = {
                'label': label,
                'definition': definition,
                'entity_type': category or other_type,
                'extraction_type': extraction_type,
                'is_published': True,
                'source_pass': int(source_pass) if source_pass is not None else None,
                'provenance': {},
                'uri': uri,
                'text_references': text_refs,
                'ontology_target': ont_target,
                'ontserve_path': self.compute_ontserve_path(uri, ont_target),
                'rdf_agent': None,
                'rdf_temporal': None,
            }

            # When two individuals share a display label (e.g. an Obligation and a
            # like-named Capability), keep the one whose URI fragment matches the
            # label exactly -- that is the primary entity case text refers to.
            fragment = uri.rsplit('#', 1)[-1]
            exact = fragment.replace('_', ' ').lower() == label.lower()
            key_label = label.lower()
            prior = exact_fragment.get(key_label)
            if prior is not None:
                prior_exact, prior_uri = prior
                if prior_exact and not exact:
                    continue
                if exact and not prior_exact:
                    lookup.pop(prior_uri, None)
            exact_fragment[key_label] = (exact, uri)
            lookup[uri] = entity_data

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
            # Skip entries with no definition -- they produce "No definition
            # available" popovers. Ontology entries: stale concepts. Committed
            # case entries: structural nodes (e.g. Agent individuals), whose
            # label slots are better claimed by the text-grounded aliases of
            # the definition-bearing entities. Working-mode entries always
            # carry a definition (label fallback), so this never drops them.
            if not definition:
                continue

            # Lowercase for case-insensitive matching
            label_key = label.lower().strip()
            self._index_label_key(label_key, data)

            # Also index without underscores
            label_no_underscore = label_key.replace('_', ' ')
            if label_no_underscore != label_key:
                self._index_label_key(label_no_underscore, data)

            # A label that ends in a period (code provision "III.1.b.") is also
            # indexed without it: case text writes "Code section III.1.b requires".
            bare_key = label_key.rstrip('.')
            if bare_key and bare_key != label_key:
                self._index_label_key(bare_key, data)

            # A cited Board case is also indexed as case text cites it ("Case 76-4").
            cited = self._CITED_CASE_LABEL.match(label.strip())
            if cited:
                self._index_label_key(cited.group(1).lower(), data)

        # Extract text-reference-grounded aliases from compound labels
        self._extract_text_aliases(lookup)

        # Post-pass (2026-07-09 walkthrough): definition-less Agent
        # individuals get a minimal entry for labels NOTHING RICHER claims.
        # 'XYZ Consulting Engineers' (an Agent with no definition) had no
        # popover at all, while 'Engineer T' resolved through its
        # definition-bearing Role alias. Ordering matters: this runs after
        # all definition-bearing entries and aliases are indexed, so a rich
        # popover is never displaced by a thin Agent line.
        for uri, data in lookup.items():
            if (data.get('entity_type') or '') != 'Agent' or data.get('definition'):
                continue
            label_key = (data.get('label') or '').lower().strip()
            if not label_key or label_key in self._label_index:
                continue
            agent_entry = dict(data)
            agent_entry['definition'] = 'Participant (Agent) in this case.'
            self._label_index[label_key] = agent_entry

    def _index_label_key(self, key: str, data: Dict) -> None:
        """Add one lookup key; case entities take precedence over ontology entries."""
        if key not in self._label_index or data.get('source') == 'case':
            self._label_index[key] = data

    @classmethod
    def _actor_label(cls, label: str, agent_labels) -> str:
        """
        Actor a case-entity label is about: the longest Agent label that
        prefixes it, else the leading designator of the label itself.
        Empty when the label names no actor ("Public Safety Faithful Agent
        Conflict").
        """
        lowered = label.lower().strip()
        for agent in agent_labels:
            a = agent.lower()
            if lowered == a or lowered.startswith(a + ' '):
                return agent
        m = cls._ACTOR_DESIGNATOR.match(label.strip())
        return m.group(1) if m else ''

    @staticmethod
    def _reference_sentences(text_refs) -> List[str]:
        """Sentences of the text references (split after . ! ?)."""
        sentences = []
        for ref in text_refs:
            sentences.extend(part for part in re.split(r'(?<=[.!?])\s+', str(ref)) if part.strip())
        return sentences

    @staticmethod
    def _phrase_grounded(phrase: str, actor: str, text_refs, ref_sentences) -> bool:
        """
        Whether a sub-phrase of a label is grounded in the entity's text references.

        A reference that is exactly the phrase grounds it. Otherwise a
        reference sentence grounds it only when the sentence contains the
        phrase together with the entity's actor label: a sentence that uses
        the phrase about someone else (a quoted code canon, a precedent recap)
        grounds nothing, and an entity without an actor label is grounded by
        exact references alone.
        """
        if any(str(r).strip().lower() == phrase.lower() for r in text_refs):
            return True
        if not actor:
            return False
        phrase_re = re.compile(r'\b' + re.escape(phrase) + r'\b', re.IGNORECASE)
        actor_re = re.compile(r'(?<![A-Za-z0-9_])' + re.escape(actor) + r'(?![A-Za-z0-9_])',
                              re.IGNORECASE)
        return any(phrase_re.search(sent) and actor_re.search(sent) for sent in ref_sentences)

    def _extract_text_aliases(self, lookup: Dict[str, Dict]) -> None:
        """
        Extract short aliases from entity labels, validated by textReferences.

        Entity labels are compound descriptions (e.g., "Engineer A Engineer in
        Responsible Charge") but case text uses short forms ("Engineer A"). This
        method extracts 2-4 word sub-phrases from labels and keeps only those
        that appear in the entity's textReferences passages. Cross-type filtering
        (2+ entities across 2+ extraction types) eliminates noise.

        Grounding is actor-bound (see _phrase_grounded): the reference sentence
        has to name the entity's actor as well as the phrase. The actors of the
        grounded sources are recorded on the alias entry as alias_actors, and
        the text scanner decorates the alias only in sentences that name one
        of them.
        """
        from collections import defaultdict

        # Stop words that invalidate a sub-phrase at boundaries.
        # Single uppercase letters (A, B, W) are identifiers, not stop words.
        stop_words = {'in', 'of', 'the', 'and', 'for', 'to', 'an', 'or',
                      'by', 'on', 'at', 'is', 'was', 'has', 'had', 'with',
                      'from', 'that', 'this', 'its', 'their', 'over', 'into',
                      'non', 'not', 'no', 'per', 'via', 'between'}

        # phrase -> list of (entity_data, extraction_type) tuples
        phrase_sources = defaultdict(list)
        # Track unique entities per phrase to avoid double-counting from URI variants
        phrase_entity_labels = defaultdict(set)
        # phrase -> actor labels of the entities that ground it
        phrase_actors = defaultdict(set)

        # Actor labels of the case: its Agent individuals, longest first so
        # "Board of Ethical Review" wins over a shorter prefix.
        agent_labels = sorted(
            {d.get('label', '') for d in lookup.values()
             if d.get('source') == 'case' and (d.get('entity_type') or '') == 'Agent'
             and d.get('label')},
            key=len, reverse=True)

        for uri, data in lookup.items():
            if data.get('source') != 'case':
                continue
            label = data.get('label', '')
            text_refs = data.get('text_references', [])
            if not label or not text_refs:
                continue

            words = label.split()
            if len(words) < 3:
                continue  # Need sub-phrase + remaining words

            actor = self._actor_label(label, agent_labels)
            ref_sentences = self._reference_sentences(text_refs)

            # Generate 2-4 word sub-phrases from the label
            for phrase_len in range(2, min(5, len(words))):
                for start in range(len(words) - phrase_len + 1):
                    phrase_words = words[start:start + phrase_len]
                    first_w = phrase_words[0].lower()
                    last_w = phrase_words[-1].lower()

                    # Skip if starts/ends with stop word (but allow single uppercase letters)
                    if first_w in stop_words and len(first_w) > 1:
                        continue
                    if last_w in stop_words and len(last_w) > 1:
                        continue

                    phrase = ' '.join(phrase_words)

                    # Skip if phrase equals the full label
                    if phrase == label:
                        continue

                    # Skip if already in label index as a full label
                    if phrase.lower() in self._label_index:
                        continue

                    # Actor-bound match in the textReferences sentences
                    if self._phrase_grounded(phrase, actor, text_refs, ref_sentences):
                        entity_key = (data.get('label', ''), data.get('extraction_type', ''))
                        if entity_key not in phrase_entity_labels[phrase]:
                            phrase_entity_labels[phrase].add(entity_key)
                            phrase_sources[phrase].append(data)
                            if actor:
                                phrase_actors[phrase].add(actor)

        # Filter: keep phrases referenced by 2+ entities across 2+ extraction types
        validated = {}
        for phrase, sources in phrase_sources.items():
            if len(sources) < 2:
                continue
            types = {d.get('extraction_type') for d in sources}
            if len(types) < 2:
                continue
            # Keep shortest phrase per prefix group
            phrase_lower = phrase.lower()
            skip = False
            for existing in list(validated.keys()):
                existing_lower = existing.lower()
                if phrase_lower.startswith(existing_lower + ' '):
                    skip = True  # Longer version of existing shorter alias
                    break
                if existing_lower.startswith(phrase_lower + ' '):
                    del validated[existing]  # Replace longer with shorter
            if not skip:
                validated[phrase] = sources

        # Type priority: roles first since aliases like "Engineer A" are actors
        type_priority = [
            'roles', 'states', 'principles', 'obligations',
            'constraints', 'capabilities', 'resources'
        ]

        # Add to label index
        for phrase, sources in validated.items():
            key = phrase.lower().strip()
            if key in self._label_index:
                continue

            # Collect all contributing extraction types
            alias_types = sorted({s.get('extraction_type', '') for s in sources})

            # Pick primary type by priority order
            primary_type = alias_types[0]  # fallback
            for t in type_priority:
                if t in alias_types:
                    primary_type = t
                    break

            # Pick best definition from entities of the primary type
            best_def = ''
            primary_source = sources[0]
            for s in sources:
                if s.get('extraction_type') == primary_type:
                    d = s.get('definition', '')
                    if d and (not best_def or len(d) > len(best_def)):
                        best_def = d
                        primary_source = s
            # Fall back to any definition if primary type had none
            if not best_def:
                for s in sources:
                    d = s.get('definition', '')
                    if d and len(d) > len(best_def):
                        best_def = d
                        primary_source = s

            # Contributing entities, for the popover's linked list. Ordered by
            # the same type priority as the primary pick, then label.
            def _type_rank(t):
                return type_priority.index(t) if t in type_priority else len(type_priority)
            alias_entities = [
                {
                    'label': s.get('label', ''),
                    'extraction_type': s.get('extraction_type', ''),
                    'uri': s.get('uri', ''),
                    'ontology_target': s.get('ontology_target', ''),
                }
                for s in sorted(sources, key=lambda s: (_type_rank(s.get('extraction_type', '')),
                                                        s.get('label', '')))
            ]

            self._label_index[key] = {
                'label': phrase,
                'definition': best_def or f'Referenced in {len(sources)} entities',
                'entity_type': primary_source.get('entity_type', ''),
                'extraction_type': primary_type,
                'source': 'case',
                'source_pass': primary_source.get('source_pass'),
                'uri': primary_source.get('uri', ''),
                'is_published': any(s.get('is_published') for s in sources),
                'alias_types': alias_types,
                'alias_entities': alias_entities,
                'alias_actors': sorted(phrase_actors.get(phrase, ())),
                'ontology_target': primary_source.get('ontology_target', ''),
                'ontserve_path': primary_source.get('ontserve_path', ''),
            }

        if validated:
            logger.debug(f"Added {len(validated)} text-grounded aliases: {list(validated.keys())}")

    @classmethod
    def _derive_ontology_target(cls, uri: str) -> str:
        """Derive ontology_target from entity URI when database field is NULL.

        Parses URI namespace to determine which OntServe ontology the entity
        belongs to. Returns empty string if URI pattern is unrecognized.
        """
        if not uri:
            return ''
        for pattern, template in cls._URI_ONTOLOGY_PATTERNS:
            m = re.match(pattern, uri)
            if m:
                return template.format(*m.groups()) if '{}' in template else template
        return ''

    @classmethod
    def compute_ontserve_path(cls, uri: str, ontology_target: str = None) -> str:
        """Compute OntServe entity URL path from URI and optional ontology_target.

        Returns a path like '/entity/proethica-case-7/EngineerARole' or
        empty string if the URI cannot be resolved.
        """
        if not uri or '#' not in uri:
            return ''
        fragment = uri.split('#')[-1]
        if not fragment:
            return ''
        ont_target = ontology_target or cls._derive_ontology_target(uri)
        if not ont_target:
            return ''
        return f'/entity/{ont_target}/{fragment}'

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
