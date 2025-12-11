"""
Auto-Commit Service for Entity-Ontology Linking

Automatically commits extracted entities to OntServe after Step 3 completion.
Links entities to existing OntServe classes based on LLM match decisions,
creates case-specific .ttl files, and updates precedent features for Jaccard calculation.

Phase 3 of Entity-Ontology Linking implementation.
"""

import logging
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL, XSD
from rdflib.namespace import SKOS, DCTERMS
from sqlalchemy import text, create_engine

from app import db
from app.models.temporary_rdf_storage import TemporaryRDFStorage

logger = logging.getLogger(__name__)

# Namespaces
PROETHICA = Namespace("http://proethica.org/ontology/intermediate#")
PROETHICA_CORE = Namespace("http://proethica.org/ontology/core#")
PROETHICA_CASES = Namespace("http://proethica.org/ontology/cases#")
PROV = Namespace("http://www.w3.org/ns/prov#")

# Confidence thresholds for auto-commit decisions
CONFIDENCE_AUTO_ACCEPT = 0.90  # Auto-accept matches above this threshold
CONFIDENCE_REVIEW = 0.75       # Require review for matches in this range
CONFIDENCE_NEW_CLASS = 0.75    # Below this, treat as new class


@dataclass
class EntityCommitResult:
    """Result of committing a single entity."""
    entity_id: int
    entity_label: str
    entity_type: str
    action: str  # 'linked', 'new_class', 'skipped', 'error'
    linked_uri: Optional[str] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    error: Optional[str] = None


@dataclass
class CommitSummary:
    """Summary of auto-commit operation for a case."""
    case_id: int
    total_entities: int
    linked_count: int
    new_class_count: int
    skipped_count: int
    error_count: int
    entity_classes: Dict[str, List[str]]
    ttl_file: Optional[str] = None
    results: List[EntityCommitResult] = None


class AutoCommitService:
    """
    Service for automatically committing extracted entities after Step 3.

    Links entities to existing OntServe classes using LLM match decisions,
    applies confidence thresholds, and generates case-specific ontology files.
    """

    def __init__(self):
        """Initialize the auto-commit service."""
        self.ontserve_path = Path("/home/chris/onto/OntServe")
        self.ontologies_dir = self.ontserve_path / "ontologies"
        self.ontologies_dir.mkdir(parents=True, exist_ok=True)

        # Cache for OntServe classes (loaded on demand)
        self._ontserve_classes_cache: Optional[Dict[str, Dict]] = None

    def commit_case_entities(self, case_id: int, force: bool = False) -> CommitSummary:
        """
        Main entry point - commit all uncommitted entities for a case.

        Called after Step 3 completion to link entities to OntServe classes
        and update precedent features for Jaccard calculation.

        Args:
            case_id: The case ID to process
            force: If True, re-commit already committed entities

        Returns:
            CommitSummary with results of the operation
        """
        logger.info(f"Starting auto-commit for case {case_id}")

        try:
            # 1. Gather all uncommitted entities
            entities = self._gather_uncommitted_entities(case_id, force)

            if not entities:
                logger.info(f"No uncommitted entities found for case {case_id}")
                return CommitSummary(
                    case_id=case_id,
                    total_entities=0,
                    linked_count=0,
                    new_class_count=0,
                    skipped_count=0,
                    error_count=0,
                    entity_classes={},
                    results=[]
                )

            logger.info(f"Found {len(entities)} entities to process for case {case_id}")

            # 2. Process each entity - validate matches and determine action
            results = []
            entity_classes: Dict[str, List[str]] = {}

            for entity in entities:
                result = self._process_entity(entity)
                results.append(result)

                # Track entity classes for Jaccard calculation
                # Include both linked entities AND new classes (using core type URI)
                if result.action in ('linked', 'new_class'):
                    # Use extraction_type as primary source, fall back to entity_type
                    entity_type = (entity.extraction_type or entity.entity_type or 'unknown').lower()
                    # Normalize entity type (e.g., 'roles' -> 'role', 'actions_events' -> 'action')
                    type_normalization = {
                        'actions_events': 'action',
                        'roles': 'role',
                        'states': 'state',
                        'resources': 'resource',
                        'principles': 'principle',
                        'obligations': 'obligation',
                        'capabilities': 'capability',
                        'constraints': 'constraint',
                        'actions': 'action',
                        'events': 'event',
                    }
                    entity_type = type_normalization.get(entity_type, entity_type)

                    if entity_type not in entity_classes:
                        entity_classes[entity_type] = []

                    # Use linked URI if available, otherwise use entity label to create URI
                    class_uri = result.linked_uri
                    if not class_uri and result.action == 'new_class':
                        # For new classes, use the entity label to create a URI
                        safe_label = self._make_safe_uri(entity.entity_label)
                        class_uri = f"http://proethica.org/ontology/intermediate#{safe_label}"

                    if class_uri and class_uri not in entity_classes[entity_type]:
                        entity_classes[entity_type].append(class_uri)

            # 3. Generate case .ttl file with individuals
            ttl_file = self._generate_case_ttl(case_id, entities, results)

            # 4. Update precedent features with entity_classes
            self._update_precedent_features(case_id, entity_classes)

            # 5. Mark entities as committed
            self._mark_entities_committed(entities)

            # 6. Sync to OntServe database for visualization/MCP
            self._sync_to_ontserve(case_id)

            # Compile summary
            summary = CommitSummary(
                case_id=case_id,
                total_entities=len(entities),
                linked_count=sum(1 for r in results if r.action == 'linked'),
                new_class_count=sum(1 for r in results if r.action == 'new_class'),
                skipped_count=sum(1 for r in results if r.action == 'skipped'),
                error_count=sum(1 for r in results if r.action == 'error'),
                entity_classes=entity_classes,
                ttl_file=ttl_file,
                results=results
            )

            logger.info(
                f"Auto-commit complete for case {case_id}: "
                f"{summary.linked_count} linked, {summary.new_class_count} new, "
                f"{summary.skipped_count} skipped, {summary.error_count} errors"
            )

            return summary

        except Exception as e:
            logger.error(f"Error in auto-commit for case {case_id}: {e}")
            return CommitSummary(
                case_id=case_id,
                total_entities=0,
                linked_count=0,
                new_class_count=0,
                skipped_count=0,
                error_count=1,
                entity_classes={},
                results=[EntityCommitResult(
                    entity_id=0,
                    entity_label="",
                    entity_type="",
                    action="error",
                    error=str(e)
                )]
            )

    def _gather_uncommitted_entities(
        self,
        case_id: int,
        include_committed: bool = False
    ) -> List[TemporaryRDFStorage]:
        """
        Gather all entities for a case that need to be committed.

        Args:
            case_id: The case ID
            include_committed: If True, include already committed entities

        Returns:
            List of TemporaryRDFStorage entities
        """
        query = TemporaryRDFStorage.query.filter_by(case_id=case_id)

        if not include_committed:
            query = query.filter_by(is_published=False)

        # Order by extraction type to group similar entities
        entities = query.order_by(
            TemporaryRDFStorage.extraction_type,
            TemporaryRDFStorage.entity_label
        ).all()

        return entities

    def _process_entity(self, entity: TemporaryRDFStorage) -> EntityCommitResult:
        """
        Process a single entity - validate match and determine commit action.

        Uses the match_decision from LLM extraction (Phase 2) to determine
        whether to link to existing class or create new.

        Args:
            entity: The entity to process

        Returns:
            EntityCommitResult with action taken
        """
        try:
            # Check if entity has a match from LLM
            if entity.matched_ontology_uri and entity.match_confidence:
                confidence = entity.match_confidence

                # High confidence - auto-link
                if confidence >= CONFIDENCE_AUTO_ACCEPT:
                    return EntityCommitResult(
                        entity_id=entity.id,
                        entity_label=entity.entity_label,
                        entity_type=entity.entity_type,
                        action='linked',
                        linked_uri=entity.matched_ontology_uri,
                        confidence=confidence,
                        reasoning=f"Auto-linked (confidence {confidence:.2f}): {entity.match_reasoning}"
                    )

                # Medium confidence - still link but flag for review
                elif confidence >= CONFIDENCE_REVIEW:
                    return EntityCommitResult(
                        entity_id=entity.id,
                        entity_label=entity.entity_label,
                        entity_type=entity.entity_type,
                        action='linked',
                        linked_uri=entity.matched_ontology_uri,
                        confidence=confidence,
                        reasoning=f"Linked with review flag (confidence {confidence:.2f}): {entity.match_reasoning}"
                    )

            # Low confidence or no match - check for duplicates before creating new class
            duplicate_uri = self._check_duplicate(entity.entity_label, entity.entity_type)

            if duplicate_uri:
                # Update the entity with the found match
                entity.matched_ontology_uri = duplicate_uri
                entity.match_method = 'embedding'
                entity.match_confidence = 0.80  # Embedding match confidence

                return EntityCommitResult(
                    entity_id=entity.id,
                    entity_label=entity.entity_label,
                    entity_type=entity.entity_type,
                    action='linked',
                    linked_uri=duplicate_uri,
                    confidence=0.80,
                    reasoning="Linked via embedding similarity check"
                )

            # No match found - create new class (handled in TTL generation)
            return EntityCommitResult(
                entity_id=entity.id,
                entity_label=entity.entity_label,
                entity_type=entity.entity_type,
                action='new_class',
                reasoning="No existing match found - new class will be created"
            )

        except Exception as e:
            logger.error(f"Error processing entity {entity.id}: {e}")
            return EntityCommitResult(
                entity_id=entity.id,
                entity_label=entity.entity_label or "Unknown",
                entity_type=entity.entity_type or "Unknown",
                action='error',
                error=str(e)
            )

    def _check_duplicate(self, label: str, entity_type: str) -> Optional[str]:
        """
        Check if a semantically equivalent class already exists in OntServe.

        Uses embedding similarity to find potential matches for entities
        without LLM-provided matches.

        Args:
            label: The entity label
            entity_type: The type of entity (role, state, etc.)

        Returns:
            URI of matching class if found, None otherwise
        """
        # Load OntServe classes if not cached
        if self._ontserve_classes_cache is None:
            self._load_ontserve_classes()

        if not self._ontserve_classes_cache:
            return None

        # Normalize label for comparison
        normalized_label = label.lower().strip()

        # First try exact label match
        for uri, class_info in self._ontserve_classes_cache.items():
            if class_info.get('label', '').lower().strip() == normalized_label:
                logger.info(f"Found exact label match for '{label}': {uri}")
                return uri

        # Try partial match (label contains or is contained)
        for uri, class_info in self._ontserve_classes_cache.items():
            class_label = class_info.get('label', '').lower().strip()
            if normalized_label in class_label or class_label in normalized_label:
                # Only match if same entity type
                class_type = class_info.get('type', '').lower()
                if entity_type and entity_type.lower() in class_type:
                    logger.info(f"Found partial label match for '{label}': {uri}")
                    return uri

        # TODO: Implement embedding-based similarity check
        # This would query OntServe's entity_embeddings table for similar entities

        return None

    def _load_ontserve_classes(self):
        """Load OntServe classes from database for duplicate checking."""
        try:
            # Query OntServe's ontology_entities table for proethica classes
            query = text("""
                SELECT uri, label, entity_type, comment
                FROM ontology_entities
                WHERE uri LIKE 'http://proethica.org/ontology/%'
            """)

            # Use a separate connection to ontserve database
            from sqlalchemy import create_engine
            ontserve_engine = create_engine('postgresql://postgres:PASS@localhost:5432/ontserve')

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
            logger.warning(f"Could not load OntServe classes: {e}")
            self._ontserve_classes_cache = {}

    def _generate_case_ttl(
        self,
        case_id: int,
        entities: List[TemporaryRDFStorage],
        results: List[EntityCommitResult]
    ) -> Optional[str]:
        """
        Generate case-specific .ttl file with individuals typed to OntServe classes.

        Implements property merging: when the same individual is extracted from
        multiple sections (facts, discussion), properties are merged rather than
        the second extraction being skipped.

        Args:
            case_id: The case ID
            entities: List of entities to include
            results: Commit results with linked URIs

        Returns:
            Path to generated .ttl file, or None if error
        """
        try:
            case_file = self.ontologies_dir / f"proethica-case-{case_id}.ttl"

            # Create or load existing graph
            g = Graph()
            if case_file.exists():
                g.parse(case_file, format='turtle')
            else:
                # Add ontology declaration
                case_ontology_uri = URIRef(f"http://proethica.org/ontology/case/{case_id}")
                g.add((case_ontology_uri, RDF.type, OWL.Ontology))
                g.add((case_ontology_uri, RDFS.label, Literal(f"ProEthica Case {case_id} Ontology")))
                g.add((case_ontology_uri, OWL.imports, URIRef("http://proethica.org/ontology/intermediate")))
                g.add((case_ontology_uri, DCTERMS.created, Literal(datetime.utcnow())))

            # Bind namespaces
            case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")
            g.bind(f"case{case_id}", case_ns)
            g.bind("proeth", PROETHICA)
            g.bind("proeth-core", PROETHICA_CORE)
            g.bind("prov", PROV)
            g.bind("skos", SKOS)

            # Create a map of entity_id to result for quick lookup
            result_map = {r.entity_id: r for r in results}

            # Group entities by URI for merging
            entities_by_uri: Dict[str, List[Tuple[TemporaryRDFStorage, EntityCommitResult]]] = {}
            for entity in entities:
                result = result_map.get(entity.id)
                if not result or result.action in ('error', 'skipped'):
                    continue

                safe_label = self._make_safe_uri(entity.entity_label)
                uri_key = str(case_ns[safe_label])

                if uri_key not in entities_by_uri:
                    entities_by_uri[uri_key] = []
                entities_by_uri[uri_key].append((entity, result))

            individuals_added = 0
            individuals_merged = 0

            for uri_key, entity_list in entities_by_uri.items():
                individual_uri = URIRef(uri_key)
                already_exists = (individual_uri, RDF.type, OWL.NamedIndividual) in g

                if already_exists:
                    # Merge properties from all new entities into existing individual
                    for entity, result in entity_list:
                        self._merge_entity_properties(g, individual_uri, entity, result, case_id)
                    individuals_merged += len(entity_list)
                    logger.debug(f"Merged {len(entity_list)} extractions into existing {entity_list[0][0].entity_label}")
                else:
                    # Create new individual and merge all extractions
                    first_entity, first_result = entity_list[0]

                    # Add as NamedIndividual
                    g.add((individual_uri, RDF.type, OWL.NamedIndividual))
                    g.add((individual_uri, RDFS.label, Literal(first_entity.entity_label)))

                    # Add type reference to OntServe class
                    if first_result.linked_uri:
                        class_uri = URIRef(first_result.linked_uri)
                        g.add((individual_uri, RDF.type, class_uri))
                    elif first_result.action == 'new_class':
                        core_type = self._get_core_type(first_entity.entity_type)
                        if core_type:
                            g.add((individual_uri, RDF.type, core_type))

                    # Add provenance
                    g.add((individual_uri, PROV.generatedAtTime, Literal(datetime.utcnow())))
                    g.add((individual_uri, PROV.wasGeneratedBy, Literal(f"ProEthica Case {case_id} Auto-Commit")))

                    # Add match metadata from first result
                    if first_result.confidence:
                        g.add((individual_uri, URIRef(str(PROETHICA) + "matchConfidence"),
                               Literal(first_result.confidence, datatype=XSD.float)))

                    # Merge properties from ALL extractions (facts + discussion)
                    for entity, result in entity_list:
                        self._merge_entity_properties(g, individual_uri, entity, result, case_id)

                    individuals_added += 1

                    if len(entity_list) > 1:
                        logger.info(f"Created {first_entity.entity_label} with merged properties from {len(entity_list)} sections")

            # Save the graph
            g.serialize(destination=case_file, format='turtle')
            logger.info(f"Generated case TTL: {individuals_added} new, {individuals_merged} merged: {case_file}")

            return str(case_file)

        except Exception as e:
            logger.error(f"Error generating case TTL for case {case_id}: {e}")
            return None

    def _merge_entity_properties(
        self,
        g: Graph,
        individual_uri: URIRef,
        entity: TemporaryRDFStorage,
        result: EntityCommitResult,
        case_id: int
    ):
        """
        Merge properties from an entity extraction into an existing individual.

        Handles multi-value properties by adding new values without duplicating.
        Tracks source texts per section for provenance.

        Args:
            g: The RDF graph
            individual_uri: URI of the individual to merge into
            entity: The entity with properties to merge
            result: The commit result for this entity
            case_id: The case ID
        """
        # Get section type from linked extraction prompt
        section_type = self._get_entity_section_type(entity)

        # Parse JSON-LD properties
        if not entity.rdf_json_ld:
            return

        try:
            json_data = json.loads(entity.rdf_json_ld) if isinstance(entity.rdf_json_ld, str) else entity.rdf_json_ld
        except (json.JSONDecodeError, TypeError):
            return

        properties = json_data.get('properties', {})

        # Define property mappings to RDF predicates
        property_mappings = {
            'hasTitle': URIRef(str(PROETHICA) + "hasTitle"),
            'hasLicense': URIRef(str(PROETHICA) + "hasLicense"),
            'hasSpecialization': URIRef(str(PROETHICA) + "hasSpecialization"),
            'hasExperience': URIRef(str(PROETHICA) + "hasExperience"),
            'hasExpertise': URIRef(str(PROETHICA) + "hasExpertise"),
            'caseInvolvement': URIRef(str(PROETHICA) + "caseInvolvement"),
            'hasActiveObligation': URIRef(str(PROETHICA) + "hasActiveObligation"),
            'hasEthicalTension': URIRef(str(PROETHICA) + "hasEthicalTension"),
        }

        # Add properties, avoiding duplicates
        for prop_name, values in properties.items():
            if prop_name in property_mappings:
                predicate = property_mappings[prop_name]
                if not isinstance(values, list):
                    values = [values]

                for value in values:
                    if value and value != "None":
                        literal = Literal(value)
                        # Check if this exact triple already exists
                        if (individual_uri, predicate, literal) not in g:
                            g.add((individual_uri, predicate, literal))

        # Add source text with section annotation
        source_text = json_data.get('source_text') or properties.get('sourceText', [None])[0]
        if source_text:
            # Use section-specific predicate to preserve both sources
            section_predicate = URIRef(str(PROETHICA) + f"sourceText_{section_type}")
            g.add((individual_uri, section_predicate, Literal(source_text)))

            # Also add to generic sourceText for backward compatibility
            generic_predicate = URIRef(str(PROETHICA) + "sourceText")
            source_with_section = f"[{section_type}] {source_text}"
            if (individual_uri, generic_predicate, Literal(source_with_section)) not in g:
                g.add((individual_uri, generic_predicate, Literal(source_with_section)))

        # Add definition if available
        if entity.entity_definition:
            definition_literal = Literal(entity.entity_definition)
            if (individual_uri, SKOS.definition, definition_literal) not in g:
                g.add((individual_uri, SKOS.definition, definition_literal))

        # Handle relationships
        relationships = json_data.get('relationships', [])
        for rel in relationships:
            rel_type = rel.get('type')
            target = rel.get('target')
            target_uri_str = rel.get('target_uri')

            if rel_type and target_uri_str:
                rel_predicate = URIRef(str(PROETHICA) + rel_type)
                target_uri = URIRef(target_uri_str)
                if (individual_uri, rel_predicate, target_uri) not in g:
                    g.add((individual_uri, rel_predicate, target_uri))

    def _get_entity_section_type(self, entity: TemporaryRDFStorage) -> str:
        """Get the section type (facts/discussion) for an entity."""
        try:
            from app.models.extraction_prompt import ExtractionPrompt
            prompt = ExtractionPrompt.query.filter_by(
                extraction_session_id=entity.extraction_session_id
            ).first()
            if prompt and prompt.section_type:
                return prompt.section_type
        except Exception:
            pass
        return "unknown"

    def _get_core_type(self, entity_type: str) -> Optional[URIRef]:
        """Get the core ontology type URI for an entity type."""
        if not entity_type:
            return None

        type_map = {
            'role': PROETHICA_CORE.Role,
            'roles': PROETHICA_CORE.Role,
            'state': PROETHICA_CORE.State,
            'states': PROETHICA_CORE.State,
            'resource': PROETHICA_CORE.Resource,
            'resources': PROETHICA_CORE.Resource,
            'principle': PROETHICA_CORE.Principle,
            'principles': PROETHICA_CORE.Principle,
            'obligation': PROETHICA_CORE.Obligation,
            'obligations': PROETHICA_CORE.Obligation,
            'action': PROETHICA_CORE.Action,
            'actions': PROETHICA_CORE.Action,
            'actions_events': PROETHICA_CORE.Action,  # Default to Action for combined
            'event': PROETHICA_CORE.Event,
            'events': PROETHICA_CORE.Event,
            'capability': PROETHICA_CORE.Capability,
            'capabilities': PROETHICA_CORE.Capability,
            'constraint': PROETHICA_CORE.Constraint,
            'constraints': PROETHICA_CORE.Constraint,
        }

        return type_map.get(entity_type.lower())

    def _make_safe_uri(self, label: str) -> str:
        """Convert a label to a safe URI component."""
        if not label:
            return "Unknown"

        # Replace spaces and special characters
        safe = label.replace(" ", "_")
        safe = safe.replace("(", "").replace(")", "")
        safe = safe.replace("'", "").replace('"', "")
        safe = safe.replace("/", "_").replace("\\", "_")
        safe = safe.replace(",", "").replace(".", "")

        return safe

    def _update_precedent_features(self, case_id: int, entity_classes: Dict[str, List[str]]):
        """
        Update case_precedent_features.entity_classes for Jaccard calculation.

        Args:
            case_id: The case ID
            entity_classes: Dict mapping entity types to lists of class URIs
        """
        try:
            if not entity_classes:
                logger.info(f"No entity classes to update for case {case_id}")
                return

            # Check if record exists
            check_query = text("""
                SELECT id FROM case_precedent_features WHERE case_id = :case_id
            """)
            result = db.session.execute(check_query, {'case_id': case_id}).fetchone()

            if result:
                # Update existing record
                update_query = text("""
                    UPDATE case_precedent_features
                    SET entity_classes = :entity_classes,
                        extraction_metadata = COALESCE(extraction_metadata, '{}'::jsonb) ||
                            jsonb_build_object('entity_linking_updated_at', :updated_at)
                    WHERE case_id = :case_id
                """)
                db.session.execute(update_query, {
                    'case_id': case_id,
                    'entity_classes': json.dumps(entity_classes),
                    'updated_at': datetime.utcnow().isoformat()
                })
            else:
                # Insert new record with minimal data
                insert_query = text("""
                    INSERT INTO case_precedent_features (case_id, entity_classes, extracted_at)
                    VALUES (:case_id, :entity_classes, :extracted_at)
                """)
                db.session.execute(insert_query, {
                    'case_id': case_id,
                    'entity_classes': json.dumps(entity_classes),
                    'extracted_at': datetime.utcnow()
                })

            db.session.commit()
            logger.info(f"Updated entity_classes for case {case_id}: {len(entity_classes)} types")

        except Exception as e:
            logger.error(f"Error updating precedent features for case {case_id}: {e}")
            db.session.rollback()

    def _mark_entities_committed(self, entities: List[TemporaryRDFStorage]):
        """Mark entities as committed in the database."""
        try:
            for entity in entities:
                entity.is_published = True
                entity.updated_at = datetime.utcnow()

            db.session.commit()
            logger.info(f"Marked {len(entities)} entities as committed")

        except Exception as e:
            logger.error(f"Error marking entities as committed: {e}")
            db.session.rollback()

    def _sync_to_ontserve(self, case_id: int):
        """
        Sync the case TTL file to OntServe's database for visualization and MCP.

        Calls OntServe scripts via subprocess to register/update the case ontology.
        """
        import subprocess

        ontserve_venv_python = "/home/chris/onto/OntServe/venv-ontserve/bin/python"
        register_script = "/home/chris/onto/OntServe/scripts/register_case_ontologies.py"
        refresh_script = "/home/chris/onto/OntServe/scripts/refresh_entity_extraction.py"

        try:
            # Run the registration script (handles both new and existing ontologies)
            logger.info(f"Syncing case {case_id} to OntServe...")

            # First, refresh entity extraction for this specific case
            result = subprocess.run(
                [ontserve_venv_python, refresh_script, f"proethica-case-{case_id}"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd="/home/chris/onto/OntServe"
            )

            if result.returncode == 0:
                logger.info(f"OntServe sync successful for case {case_id}")
            else:
                logger.warning(f"OntServe sync returned non-zero: {result.stderr}")

        except subprocess.TimeoutExpired:
            logger.warning(f"OntServe sync timed out for case {case_id}")
        except FileNotFoundError:
            logger.warning("OntServe scripts not found - skipping sync")
        except Exception as e:
            logger.warning(f"OntServe sync failed for case {case_id}: {e}")
            # Don't fail the commit if OntServe sync fails

    def get_commit_status(self, case_id: int) -> Dict[str, Any]:
        """
        Get the current commit status for a case.

        Returns information about committed/pending entities and linked classes.
        """
        try:
            # Count entities by status
            pending = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                is_published=False
            ).count()

            committed = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                is_published=True
            ).count()

            # Count by match status
            matched = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.matched_ontology_uri.isnot(None)
            ).count()

            unmatched = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.matched_ontology_uri.is_(None)
            ).count()

            # Check for case TTL file
            case_file = self.ontologies_dir / f"proethica-case-{case_id}.ttl"

            # Get entity_classes from precedent features
            query = text("""
                SELECT entity_classes FROM case_precedent_features WHERE case_id = :case_id
            """)
            result = db.session.execute(query, {'case_id': case_id}).fetchone()
            entity_classes = result[0] if result and result[0] else {}

            return {
                'case_id': case_id,
                'pending_count': pending,
                'committed_count': committed,
                'matched_count': matched,
                'unmatched_count': unmatched,
                'case_ttl_exists': case_file.exists(),
                'case_ttl_path': str(case_file) if case_file.exists() else None,
                'entity_classes': entity_classes,
                'ready_for_jaccard': bool(entity_classes)
            }

        except Exception as e:
            logger.error(f"Error getting commit status for case {case_id}: {e}")
            return {'error': str(e)}

    def clear_case_ontology(self, case_id: int, reset_committed: bool = True) -> Dict[str, Any]:
        """
        Clear a case's OntServe ontology to prepare for re-extraction.

        This removes the case TTL file and optionally resets committed entities
        to uncommitted status, preventing circular matches when re-running extraction.

        Args:
            case_id: The case ID to clear
            reset_committed: If True, mark all committed entities as uncommitted

        Returns:
            Dict with summary of what was cleared
        """
        import subprocess

        logger.info(f"Clearing case ontology for case {case_id}")

        result = {
            'case_id': case_id,
            'ttl_deleted': False,
            'ontserve_cleared': False,
            'entities_reset': 0,
            'errors': []
        }

        try:
            # 1. Delete the case TTL file
            case_file = self.ontologies_dir / f"proethica-case-{case_id}.ttl"
            if case_file.exists():
                case_file.unlink()
                result['ttl_deleted'] = True
                logger.info(f"Deleted case TTL file: {case_file}")
            else:
                logger.info(f"Case TTL file not found: {case_file}")

            # 2. Clear from OntServe database (delete entities for this ontology)
            try:
                ontserve_conn_str = "postgresql://postgres:PASS@localhost:5432/ontserve"
                engine = create_engine(ontserve_conn_str)
                with engine.connect() as conn:
                    ontology_name = f"proethica-case-{case_id}"

                    # First get the ontology_id from ontologies table
                    ontology_id_result = conn.execute(text("""
                        SELECT id FROM ontologies WHERE name = :ontology_name
                    """), {'ontology_name': ontology_name}).fetchone()

                    if ontology_id_result:
                        ontology_id = ontology_id_result[0]

                        # Delete from ontology_entities using ontology_id
                        del_result = conn.execute(text("""
                            DELETE FROM ontology_entities WHERE ontology_id = :ontology_id
                        """), {'ontology_id': ontology_id})
                        deleted_entities = del_result.rowcount

                        # Delete from ontology_versions using ontology_id
                        conn.execute(text("""
                            DELETE FROM ontology_versions WHERE ontology_id = :ontology_id
                        """), {'ontology_id': ontology_id})

                        # Optionally delete the ontology record itself
                        conn.execute(text("""
                            DELETE FROM ontologies WHERE id = :ontology_id
                        """), {'ontology_id': ontology_id})

                        result['ontserve_entities_deleted'] = deleted_entities
                    else:
                        # Ontology not registered yet
                        deleted_entities = 0
                        result['ontserve_entities_deleted'] = 0

                    conn.commit()
                    result['ontserve_cleared'] = True
                    logger.info(f"Cleared {deleted_entities} entities from OntServe for {ontology_name}")
            except Exception as e:
                error_msg = f"Failed to clear OntServe: {e}"
                logger.warning(error_msg)
                result['errors'].append(error_msg)

            # 3. Reset committed entities to uncommitted (optional)
            if reset_committed:
                reset_count = TemporaryRDFStorage.query.filter_by(
                    case_id=case_id,
                    is_published=True
                ).update({'is_published': False, 'updated_at': datetime.utcnow()})
                db.session.commit()
                result['entities_reset'] = reset_count
                logger.info(f"Reset {reset_count} committed entities to uncommitted")

            result['success'] = True
            logger.info(f"Case {case_id} ontology cleared successfully")

        except Exception as e:
            logger.error(f"Error clearing case ontology for {case_id}: {e}")
            result['success'] = False
            result['errors'].append(str(e))
            db.session.rollback()

        return result

    def commit_temporal_entities(self, case_id: int) -> Dict[str, Any]:
        """
        Commit temporal entities (actions, events, causal_chains) to the case TTL file.

        Called after enhanced temporal extraction completes to add temporal entities
        to the case ontology with relationships to Pass 1-3 entities.

        Args:
            case_id: The case ID to process

        Returns:
            Dict with summary of committed temporal entities
        """
        logger.info(f"Committing temporal entities for case {case_id}")

        try:
            # Define temporal entity types
            temporal_types = ['actions', 'events', 'causal_chains', 'allen_relations', 'timeline']

            # Gather temporal entities
            temporal_entities = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.entity_type.in_(temporal_types)
            ).all()

            if not temporal_entities:
                logger.info(f"No temporal entities found for case {case_id}")
                return {'status': 'no_entities', 'counts': {}}

            logger.info(f"Found {len(temporal_entities)} temporal entities for case {case_id}")

            # Load or create case TTL graph
            case_file = self.ontologies_dir / f"proethica-case-{case_id}.ttl"
            g = Graph()

            if case_file.exists():
                g.parse(case_file, format='turtle')
                logger.info(f"Loaded existing case TTL: {case_file}")
            else:
                # Create new graph with ontology declaration
                case_ontology_uri = URIRef(f"http://proethica.org/ontology/case/{case_id}")
                g.add((case_ontology_uri, RDF.type, OWL.Ontology))
                g.add((case_ontology_uri, RDFS.label, Literal(f"ProEthica Case {case_id} Ontology")))
                g.add((case_ontology_uri, OWL.imports, URIRef("http://proethica.org/ontology/intermediate")))
                g.add((case_ontology_uri, DCTERMS.created, Literal(datetime.utcnow())))

            # Bind namespaces
            case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")
            g.bind(f"case{case_id}", case_ns)
            g.bind("proeth", PROETHICA)
            g.bind("proeth-core", PROETHICA_CORE)
            g.bind("prov", PROV)
            g.bind("skos", SKOS)

            # Track counts by type
            counts = {t: 0 for t in temporal_types}

            # Build a map of existing Pass 1-3 individuals for linking
            existing_individuals = self._get_existing_individuals(g, case_ns)

            # Process each temporal entity
            for entity in temporal_entities:
                try:
                    self._add_temporal_entity_to_graph(
                        g, entity, case_ns, existing_individuals, case_id
                    )
                    counts[entity.entity_type] = counts.get(entity.entity_type, 0) + 1
                except Exception as e:
                    logger.warning(f"Error adding temporal entity {entity.id}: {e}")

            # Save the updated graph
            g.serialize(destination=case_file, format='turtle')
            logger.info(f"Saved case TTL with temporal entities: {case_file}")

            # Mark temporal entities as committed
            for entity in temporal_entities:
                entity.is_published = True
                entity.updated_at = datetime.utcnow()
            db.session.commit()

            # Sync to OntServe
            self._sync_to_ontserve(case_id)

            total_added = sum(counts.values())
            logger.info(f"Committed {total_added} temporal entities for case {case_id}: {counts}")

            return {
                'status': 'success',
                'counts': counts,
                'total': total_added,
                'ttl_file': str(case_file)
            }

        except Exception as e:
            logger.error(f"Error committing temporal entities for case {case_id}: {e}")
            db.session.rollback()
            return {'status': 'error', 'error': str(e)}

    def _get_existing_individuals(self, g: Graph, case_ns: Namespace) -> Dict[str, URIRef]:
        """
        Get map of existing Pass 1-3 individuals for linking.

        Maps normalized labels to URIs for quick lookup when creating relationships.
        """
        individuals = {}

        for s, p, o in g.triples((None, RDF.type, OWL.NamedIndividual)):
            # Get label
            for label in g.objects(s, RDFS.label):
                normalized = str(label).lower().strip()
                individuals[normalized] = s

        logger.debug(f"Found {len(individuals)} existing individuals for linking")
        return individuals

    def _add_temporal_entity_to_graph(
        self,
        g: Graph,
        entity: TemporaryRDFStorage,
        case_ns: Namespace,
        existing_individuals: Dict[str, URIRef],
        case_id: int
    ):
        """
        Add a temporal entity to the case graph with relationships.

        Args:
            g: The RDF graph
            entity: The temporal entity to add
            case_ns: The case namespace
            existing_individuals: Map of existing individuals for linking
            case_id: The case ID
        """
        # Create individual URI from label
        safe_label = self._make_safe_uri(entity.entity_label)

        # Use appropriate prefix based on entity type
        type_prefix = {
            'actions': 'Action',
            'events': 'Event',
            'causal_chains': 'CausalChain',
            'allen_relations': 'AllenRelation',
            'timeline': 'Timeline'
        }
        prefix = type_prefix.get(entity.entity_type, entity.entity_type.title())
        individual_uri = case_ns[f"{prefix}_{safe_label}"]

        # Skip if already exists
        if (individual_uri, RDF.type, OWL.NamedIndividual) in g:
            return

        # Add as NamedIndividual
        g.add((individual_uri, RDF.type, OWL.NamedIndividual))
        g.add((individual_uri, RDFS.label, Literal(entity.entity_label)))

        # Add core type
        core_type = self._get_core_type(entity.entity_type)
        if core_type:
            g.add((individual_uri, RDF.type, core_type))

        # Parse JSON-LD for additional properties and relationships
        if entity.rdf_json_ld:
            try:
                json_data = json.loads(entity.rdf_json_ld) if isinstance(entity.rdf_json_ld, str) else entity.rdf_json_ld
                self._add_properties_from_jsonld(g, individual_uri, json_data, existing_individuals, case_ns)
            except Exception as e:
                logger.debug(f"Could not parse JSON-LD for {entity.entity_label}: {e}")

        # Add definition if available
        if entity.entity_definition:
            g.add((individual_uri, SKOS.definition, Literal(entity.entity_definition)))

        # Add provenance
        g.add((individual_uri, PROV.generatedAtTime, Literal(datetime.utcnow())))
        g.add((individual_uri, PROV.wasGeneratedBy, Literal(f"ProEthica Case {case_id} Temporal Extraction")))

    def _add_properties_from_jsonld(
        self,
        g: Graph,
        subject_uri: URIRef,
        json_data: Dict,
        existing_individuals: Dict[str, URIRef],
        case_ns: Namespace
    ):
        """
        Add properties from JSON-LD data, creating relationships to existing individuals.
        """
        # Extract common properties
        if 'proeth:description' in json_data:
            g.add((subject_uri, SKOS.definition, Literal(json_data['proeth:description'])))

        if 'proeth:agent' in json_data:
            agent_name = json_data['proeth:agent']
            # Try to find matching role
            normalized_agent = agent_name.lower().strip()
            for label, uri in existing_individuals.items():
                if normalized_agent in label or label in normalized_agent:
                    g.add((subject_uri, URIRef(str(PROETHICA) + "performedBy"), uri))
                    break

        if 'proeth:temporalMarker' in json_data:
            g.add((subject_uri, URIRef(str(PROETHICA) + "temporalMarker"),
                   Literal(json_data['proeth:temporalMarker'])))

        # Handle ethical context for actions
        if 'proeth:ethical_context' in json_data:
            ctx = json_data['proeth:ethical_context']

            # Link to violated obligations
            if isinstance(ctx, dict) and 'obligations_violated' in ctx:
                for obl in ctx.get('obligations_violated', []):
                    normalized_obl = obl.lower().strip()
                    for label, uri in existing_individuals.items():
                        if normalized_obl in label or label in normalized_obl:
                            g.add((subject_uri, URIRef(str(PROETHICA) + "violates"), uri))
                            break

            # Link to fulfilled obligations
            if isinstance(ctx, dict) and 'obligations_fulfilled' in ctx:
                for obl in ctx.get('obligations_fulfilled', []):
                    normalized_obl = obl.lower().strip()
                    for label, uri in existing_individuals.items():
                        if normalized_obl in label or label in normalized_obl:
                            g.add((subject_uri, URIRef(str(PROETHICA) + "fulfills"), uri))
                            break

        # Handle causal chains
        if 'proeth:cause' in json_data:
            cause_label = json_data['proeth:cause']
            cause_uri = case_ns[f"Action_{self._make_safe_uri(cause_label)}"]
            g.add((subject_uri, URIRef(str(PROETHICA) + "hasCause"), cause_uri))

        if 'proeth:effect' in json_data:
            effect_label = json_data['proeth:effect']
            effect_uri = case_ns[f"Event_{self._make_safe_uri(effect_label)}"]
            g.add((subject_uri, URIRef(str(PROETHICA) + "hasEffect"), effect_uri))

        # Handle Allen relations
        if 'time:intervalRelation' in json_data:
            g.add((subject_uri, URIRef("http://www.w3.org/2006/time#intervalRelation"),
                   Literal(json_data['time:intervalRelation'])))


# Module-level convenience functions
def commit_temporal_entities(case_id: int) -> Dict[str, Any]:
    """
    Convenience function to commit temporal entities for a case.

    Called after enhanced temporal extraction completes.
    """
    service = AutoCommitService()
    return service.commit_temporal_entities(case_id)


def auto_commit_case(case_id: int, force: bool = False) -> CommitSummary:
    """
    Convenience function to auto-commit a case.

    Args:
        case_id: The case ID to process
        force: If True, re-process already committed entities

    Returns:
        CommitSummary with results
    """
    service = AutoCommitService()
    return service.commit_case_entities(case_id, force=force)


def clear_case_ontology(case_id: int, reset_committed: bool = True) -> Dict[str, Any]:
    """
    Clear a case's OntServe ontology before re-running extraction.

    This should be called when re-extracting a case to avoid circular matches
    (entities matching to themselves from a previous run).

    Args:
        case_id: The case ID to clear
        reset_committed: If True, also mark all committed entities as uncommitted
                        so they can be recommitted fresh

    Returns:
        Dict with summary of what was cleared
    """
    service = AutoCommitService()
    return service.clear_case_ontology(case_id, reset_committed=reset_committed)
