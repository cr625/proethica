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
from app.services.ontserve.ontserve_config import get_ontserve_base_path, get_ontserve_db_url

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

# Minimum cosine similarity for embedding-based duplicate detection.
# Maps to the rubric MEDIUM band lower bound (ICCBR paper Section 3.3).
# Re-exported from the shared matcher so the threshold lives in ONE place
# (matcher unification 2026-06). Kept as a module name for backward references.
from app.services.extraction.entity_matcher import MEDIUM_BAND_MIN as EMBEDDING_MATCH_MIN  # noqa: E402
from app.services.extraction.entity_matcher import (  # noqa: E402
    CandidateRecord,
    EntityMatcher,
    semantic_type_markers as _semantic_type_markers,
)


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


# Duplicate-matching mixin (duplicate_matching.py, god-file split PHASE 2 Step 2.5).
from app.services.commit.duplicate_matching import DuplicateMatchingMixin  # noqa: E402
# Case-TTL-building mixin (case_ttl_builder.py, god-file split PHASE 2 Step 2.5).
from app.services.commit.case_ttl_builder import CaseTtlBuilderMixin  # noqa: E402


class AutoCommitService(DuplicateMatchingMixin, CaseTtlBuilderMixin):
    """
    Service for automatically committing extracted entities after Step 3.

    Links entities to existing OntServe classes using LLM match decisions,
    applies confidence thresholds, and generates case-specific ontology files.
    """

    def __init__(self):
        """Initialize the auto-commit service."""
        self.ontserve_path = get_ontserve_base_path()
        self.ontologies_dir = self.ontserve_path / "ontologies"
        self.ontologies_dir.mkdir(parents=True, exist_ok=True)

        # Cache for OntServe classes (loaded on demand) - used by exact-label
        # and substring lexical matchers. Embedding lookups go directly to
        # ontology_entities via pgvector and do not consult this cache.
        self._ontserve_classes_cache: Optional[Dict[str, Dict]] = None

        # Whether current commit uses versioned path (set by commit_case_entities)
        self._versioned_commit: bool = True

    def commit_case_entities(self, case_id: int, force: bool = False,
                              versioned: bool = True) -> CommitSummary:
        """
        Main entry point - commit all uncommitted entities for a case.

        Called after Step 3 completion to link entities to OntServe classes
        and update precedent features for Jaccard calculation.

        Args:
            case_id: The case ID to process
            force: If True, re-commit already committed entities
            versioned: If True (default), overwrites TTL file and versions in OntServe DB.
                       If False, merges with existing TTL file (legacy behavior).

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

            # Store versioned flag for use in TTL generation
            self._versioned_commit = versioned

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

            # 3. The canonical case TTL is written downstream by the OntServe
            # versioned writer (commit_case_versioned -> _write_case_ttl_fresh),
            # which builds a fresh graph and OVERWRITES the file. Generating the
            # lean transient TTL eagerly here would just be clobbered, so defer it
            # to the fallback in _sync_to_ontserve (non-versioned, or a
            # versioned-commit failure), where it is actually consumed.
            ttl_file = str(self.ontologies_dir / f"proethica-case-{case_id}.ttl")

            # 4. Update precedent features with entity_classes
            self._update_precedent_features(case_id, entity_classes)

            # 5. Mark entities as committed
            self._mark_entities_committed(entities)

            # 6. Sync to OntServe database for visualization/MCP (writes the final
            # TTL; entities/results let the fallback build the lean TTL if needed).
            self._sync_to_ontserve(case_id, entities, results)

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

        # Exclude explicitly rejected entities (is_selected=False AND is_reviewed=True)
        # Legacy entities with is_selected=False, is_reviewed=False are still included
        query = query.filter(
            db.or_(
                TemporaryRDFStorage.is_selected == True,   # noqa: E712
                TemporaryRDFStorage.is_reviewed == False    # noqa: E712
            )
        )

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
            match = self._check_duplicate(
                entity.entity_label,
                entity.entity_type,
                entity.entity_definition or "",
            )

            if match:
                duplicate_uri, match_confidence = match
                match_method = 'lexical' if match_confidence >= 1.0 else 'embedding'
                band = "auto-link" if match_confidence >= CONFIDENCE_AUTO_ACCEPT else "review-flag"
                entity.matched_ontology_uri = duplicate_uri
                entity.match_method = match_method
                entity.match_confidence = match_confidence

                return EntityCommitResult(
                    entity_id=entity.id,
                    entity_label=entity.entity_label,
                    entity_type=entity.entity_type,
                    action='linked',
                    linked_uri=duplicate_uri,
                    confidence=match_confidence,
                    reasoning=f"Duplicate check ({match_method}, {band}, score={match_confidence:.2f}): {entity.entity_label}",
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

    def _sync_to_ontserve(
        self,
        case_id: int,
        entities: Optional[List[TemporaryRDFStorage]] = None,
        results: Optional[List[EntityCommitResult]] = None,
    ):
        """
        Sync the case TTL file to OntServe's database for visualization and MCP.

        For versioned commits, also stores version history in OntServe concepts table.
        Calls OntServe scripts via subprocess to register/update the case ontology.

        ``entities``/``results`` are the per-entity commit results from
        commit_case_entities; they are used only to build the lean fallback TTL when
        the versioned writer did not persist it. The temporal path calls this
        without them (it wrote its own TTL beforehand).
        """
        from app.services.commit.ontserve_commit_service import OntServeCommitService

        versioned = getattr(self, '_versioned_commit', True)
        versioned_refresh_done = False

        try:
            commit_service = OntServeCommitService()

            # For versioned commits, store version history in OntServe and write
            # the final TTL. commit_case_versioned now materializes edges on the
            # final TTL and syncs disk->DB itself.
            if versioned:
                try:
                    # NOTE: a distinct name from the `entities` parameter (the commit
                    # results) -- this is the published-entity set for the versioned
                    # writer, not the lean-TTL fallback input.
                    published_entities = TemporaryRDFStorage.query.filter_by(
                        case_id=case_id,
                        is_published=True
                    ).all()

                    if published_entities:
                        entity_ids = [e.id for e in published_entities]
                        result = commit_service.commit_case_versioned(case_id, entity_ids)
                        if result.get('success'):
                            logger.info(f"Versioned commit to OntServe DB: v{result.get('new_version')}, "
                                       f"{result.get('versions_superseded')} superseded")
                            versioned_refresh_done = True
                        else:
                            logger.warning(f"Versioned commit warning: {result.get('error')}")
                except Exception as e:
                    logger.warning(f"Versioned commit to OntServe DB failed: {e}")
                    # Fall through to materialize + sync the _generate_case_ttl TTL.

            # Non-versioned path (or versioned-commit failure): the persisted TTL
            # is the one _generate_case_ttl wrote (no edges yet). Materialize the
            # edge layer on it, then sync disk->DB via the shared CLI wrapper.
            if not versioned_refresh_done:
                logger.info(f"Syncing case {case_id} TTL to OntServe...")
                case_file = self.ontologies_dir / f"proethica-case-{case_id}.ttl"
                # Lean fallback TTL: the versioned writer did not persist it (non-
                # versioned mode, or the versioned commit failed). Build it now from
                # the commit results -- deferred from commit_case_entities, where the
                # versioned path would have clobbered it. The temporal path calls
                # _sync_to_ontserve() without results (it wrote its own TTL above),
                # so only (re)generate when results are supplied.
                if entities is not None and results is not None:
                    self._generate_case_ttl(case_id, entities, results)
                try:
                    from app.services.extraction.edge_materialization import materialize_edges_on_ttl
                    materialize_edges_on_ttl(case_id, case_file)
                except Exception as e:
                    logger.exception(f"Edge materialization failed for case {case_id}: {e}")
                # Canonicalization: role+facet decomposition over the committed TTL. Not swallowed
                # (dev: fail loud) so calibration surfaces any issue; idempotent (no-op once canonical).
                # Shared canonicalize + role-axis RE-SWEEP helper: canonicalization can retype a
                # compound role facet onto an axis-sided canonical role, so the guard runs on the
                # post-canonicalization graph. This lean fallback TTL harvested no role_kind
                # signal, so on a provable both-sides conflict the guard keeps the participant
                # side (its documented default, the weaker commitment).
                logger.info(
                    f"Canonicalization for case {case_id}: "
                    f"{commit_service._canonicalize_with_role_axis_resweep(case_id, case_file, {})}"
                )
                sync_result = commit_service._sync_ontology_to_db(f"proethica-case-{case_id}")
                if sync_result.get('success'):
                    logger.info(f"OntServe TTL sync successful for case {case_id}")
                else:
                    logger.warning(f"OntServe sync warning: {sync_result.get('error')}")

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
                engine = create_engine(get_ontserve_db_url())
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
                _title = self._case_title(case_id)
                if _title:
                    g.add((case_ontology_uri, DCTERMS.title, Literal(_title)))
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
