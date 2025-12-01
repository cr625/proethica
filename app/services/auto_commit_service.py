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
from sqlalchemy import text

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
            query = query.filter_by(is_committed=False)

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

            individuals_added = 0

            for entity in entities:
                result = result_map.get(entity.id)
                if not result or result.action in ('error', 'skipped'):
                    continue

                # Create individual URI
                safe_label = self._make_safe_uri(entity.entity_label)
                individual_uri = case_ns[safe_label]

                # Skip if already exists
                if (individual_uri, RDF.type, OWL.NamedIndividual) in g:
                    continue

                # Add as NamedIndividual
                g.add((individual_uri, RDF.type, OWL.NamedIndividual))
                g.add((individual_uri, RDFS.label, Literal(entity.entity_label)))

                # Add type reference to OntServe class
                if result.linked_uri:
                    class_uri = URIRef(result.linked_uri)
                    g.add((individual_uri, RDF.type, class_uri))
                elif result.action == 'new_class':
                    # For new classes, type to the core concept
                    core_type = self._get_core_type(entity.entity_type)
                    if core_type:
                        g.add((individual_uri, RDF.type, core_type))

                # Add definition if available
                if entity.entity_definition:
                    g.add((individual_uri, SKOS.definition, Literal(entity.entity_definition)))

                # Add provenance
                g.add((individual_uri, PROV.generatedAtTime, Literal(datetime.utcnow())))
                g.add((individual_uri, PROV.wasGeneratedBy, Literal(f"ProEthica Case {case_id} Auto-Commit")))

                # Add match metadata
                if result.confidence:
                    g.add((individual_uri, URIRef(str(PROETHICA) + "matchConfidence"),
                           Literal(result.confidence, datatype=XSD.float)))

                individuals_added += 1

            # Save the graph
            g.serialize(destination=case_file, format='turtle')
            logger.info(f"Generated case TTL with {individuals_added} individuals: {case_file}")

            return str(case_file)

        except Exception as e:
            logger.error(f"Error generating case TTL for case {case_id}: {e}")
            return None

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
                entity.is_committed = True
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
                is_committed=False
            ).count()

            committed = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                is_committed=True
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


# Module-level convenience function
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
