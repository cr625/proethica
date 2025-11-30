"""
Case Entity Storage Service

Manages temporary storage and versioning of extracted entities from cases
using the NSPE structure (Facts, Questions, Discussion, References, Conclusion, Dissenting Opinion).

This service extends the TemporaryConcept infrastructure for case-specific entity extraction
and provides integration with OntServe for permanent storage.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from sqlalchemy import and_, or_

from app.models import db
from app.models.temporary_concept import TemporaryConcept
from app.models import Document
from app.services.provenance_service import get_provenance_service
from app.services.external_mcp_client import get_external_mcp_client

logger = logging.getLogger(__name__)


class CaseEntityStorageService:
    """
    Service for managing case-specific entity extraction, temporary storage, and versioning.

    Supports the NSPE case structure:
    - Facts: Environmental context and situational elements (Roles, States, Resources)
    - Questions: Ethical dilemmas and decision points
    - Discussion: Analysis and reasoning (Principles, Obligations, Constraints, Capabilities)
    - References: Code citations and precedents
    - Conclusion: Recommendations and decisions (Actions, Events)
    - Dissenting Opinion: Alternative perspectives (if present)
    """

    # NSPE Case Section Types
    NSPE_SECTIONS = {
        'facts': {
            'label': 'Facts',
            'description': 'Environmental context and situational elements',
            'primary_entities': ['Role', 'State', 'Resource'],
            'extraction_pass': 'contextual_framework'
        },
        'questions': {
            'label': 'Questions',
            'description': 'Ethical dilemmas and decision points',
            'primary_entities': ['Principle', 'Obligation'],
            'extraction_pass': 'normative_requirements'
        },
        'discussion': {
            'label': 'Discussion',
            'description': 'Analysis and reasoning',
            'primary_entities': ['Principle', 'Obligation', 'Constraint', 'Capability'],
            'extraction_pass': 'normative_requirements'
        },
        'references': {
            'label': 'NSPE Code of Ethics References',
            'description': 'Code citations and precedents',
            'primary_entities': ['Resource', 'Principle', 'Obligation'],
            'extraction_pass': 'contextual_framework'
        },
        'conclusion': {
            'label': 'Conclusion',
            'description': 'Recommendations and decisions',
            'primary_entities': ['Action', 'Event'],
            'extraction_pass': 'temporal_dynamics'
        },
        'dissenting': {
            'label': 'Dissenting Opinion',
            'description': 'Alternative perspectives',
            'primary_entities': ['Principle', 'Action'],
            'extraction_pass': 'temporal_dynamics'
        }
    }

    @staticmethod
    def create_case_session_id(case_id: int, section_type: str, extraction_pass: str = None) -> str:
        """
        Create a unique session ID for a case entity extraction session.

        Args:
            case_id: ID of the case being processed
            section_type: NSPE section type (facts, questions, discussion, etc.)
            extraction_pass: Optional extraction pass identifier

        Returns:
            Unique session identifier following pattern: case{id}_{section}_{pass}_{timestamp}_{uuid}
        """
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        unique_id = str(uuid.uuid4())[:8]

        if extraction_pass:
            return f"case{case_id}_{section_type}_{extraction_pass}_{timestamp}_{unique_id}"
        else:
            return f"case{case_id}_{section_type}_{timestamp}_{unique_id}"

    @staticmethod
    def store_extracted_entities(
        entities: List[Dict[str, Any]],
        case_id: int,
        section_type: str,
        session_id: Optional[str] = None,
        extraction_metadata: Optional[Dict] = None,
        provenance_activity = None,
        expires_in_days: int = 30  # Longer expiration for cases
    ) -> Tuple[str, List[TemporaryConcept]]:
        """
        Store extracted entities in temporary storage for review.

        Args:
            entities: List of extracted entities from LLM
            case_id: Case ID
            section_type: NSPE section type
            session_id: Optional session ID (generated if not provided)
            extraction_metadata: Extraction session metadata
            provenance_activity: PROV-O activity for tracking
            expires_in_days: Days until cleanup

        Returns:
            Tuple of (session_id, list of created TemporaryConcept records)
        """
        if not session_id:
            extraction_pass = extraction_metadata.get('extraction_pass') if extraction_metadata else None
            session_id = CaseEntityStorageService.create_case_session_id(
                case_id, section_type, extraction_pass
            )

        # Validate section type
        if section_type not in CaseEntityStorageService.NSPE_SECTIONS:
            logger.warning(f"Unknown section type: {section_type}. Using 'discussion' as fallback.")
            section_type = 'discussion'

        section_info = CaseEntityStorageService.NSPE_SECTIONS[section_type]

        # Get case document
        case_doc = Document.query.get(case_id)
        if not case_doc:
            raise ValueError(f"Case {case_id} not found")

        # Default world_id to 1 (Engineering) if not specified
        world_id = getattr(case_doc, 'world_id', 1)

        created_concepts = []
        timestamp = datetime.utcnow()

        # Prepare provenance service
        prov = get_provenance_service() if provenance_activity else None

        for entity in entities:
            # Enhanced concept data structure for case entities
            concept_data = {
                # Core entity information
                'label': entity.get('label', ''),
                'description': entity.get('description', ''),
                'category': entity.get('category', entity.get('type', 'Entity')),
                'confidence': entity.get('confidence', 0.8),

                # Case-specific information
                'case_id': case_id,
                'section_type': section_type,
                'section_info': section_info,
                'nspe_context': True,

                # Extraction metadata
                'extraction_metadata': extraction_metadata or {},
                'source_text': entity.get('source_text', ''),
                'extraction_reasoning': entity.get('reasoning', ''),

                # Entity-specific enhanced fields
                **{k: v for k, v in entity.items() if k.startswith(('role_', 'resource_', 'principle_', 'obligation_', 'action_', 'event_', 'state_', 'capability_', 'constraint_'))},

                # Review workflow
                'is_new': entity.get('is_new', True),
                'ontology_match': entity.get('ontology_match'),
                'selected': True,  # Default to selected for review
                'edited': False,
                'review_notes': '',

                # Versioning
                'version': 1,
                'previous_versions': []
            }

            # Create temporary concept record
            temp_concept = TemporaryConcept(
                document_id=case_id,
                world_id=world_id,
                session_id=session_id,
                concept_data=concept_data,
                status='pending',
                extraction_method='llm_case_extraction',
                extraction_timestamp=timestamp,
                expires_at=timestamp + timedelta(days=expires_in_days),
                created_by=f"case_extraction_{extraction_metadata.get('model_used', 'unknown') if extraction_metadata else 'unknown'}",
                extra_metadata={
                    'case_session': True,
                    'nspe_section': section_type,
                    'extraction_pass': section_info['extraction_pass'],
                    'primary_entities': section_info['primary_entities'],
                    'extraction_metadata': extraction_metadata or {}
                }
            )

            db.session.add(temp_concept)
            created_concepts.append(temp_concept)

            # Record provenance if available
            if prov and provenance_activity:
                try:
                    prov.record_entity(
                        entity_content=concept_data,
                        activity=provenance_activity,
                        entity_name=f"temp_entity_{entity.get('label', 'unknown')}",
                        metadata={
                            'entity_type': 'temporary_case_entity',
                            'case_id': case_id,
                            'section_type': section_type,
                            'session_id': session_id,
                            'temp_concept_id': temp_concept.id if hasattr(temp_concept, 'id') else None
                        }
                    )
                except Exception as prov_error:
                    logger.warning(f"Failed to record provenance: {prov_error}, continuing without provenance")

        try:
            db.session.commit()
            logger.info(f"Stored {len(created_concepts)} entities for case {case_id}, section {section_type}, session {session_id}")

            return session_id, created_concepts

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to store entities: {e}")
            raise

    @staticmethod
    def get_case_session_entities(
        case_id: int,
        session_id: str,
        status: str = 'pending'
    ) -> List[TemporaryConcept]:
        """Get all entities for a specific case extraction session."""
        return TemporaryConcept.query.filter_by(
            document_id=case_id,
            session_id=session_id,
            status=status
        ).order_by(TemporaryConcept.id).all()

    @staticmethod
    def get_case_entities_by_section(
        case_id: int,
        section_type: str,
        status: str = 'pending'
    ) -> List[TemporaryConcept]:
        """Get all entities for a case section across all sessions."""
        return TemporaryConcept.query.filter(
            and_(
                TemporaryConcept.document_id == case_id,
                TemporaryConcept.status == status,
                TemporaryConcept.concept_data['section_type'].astext == section_type
            )
        ).order_by(TemporaryConcept.extraction_timestamp.desc()).all()

    @staticmethod
    def get_all_case_entities(
        case_id: int,
        status: str = 'pending',
        group_by_section: bool = True
    ) -> Dict[str, List[TemporaryConcept]]:
        """Get all entities for a case, optionally grouped by section."""
        entities = TemporaryConcept.query.filter_by(
            document_id=case_id,
            status=status
        ).order_by(TemporaryConcept.extraction_timestamp.desc()).all()

        if not group_by_section:
            return {'all': entities}

        grouped = {}
        for entity in entities:
            section = entity.concept_data.get('section_type', 'unknown')
            if section not in grouped:
                grouped[section] = []
            grouped[section].append(entity)

        return grouped

    @staticmethod
    def update_entity_selection(
        temp_concept_id: int,
        selected: bool,
        review_notes: str = '',
        modified_by: str = 'user'
    ) -> bool:
        """Update entity selection status during review."""
        concept = TemporaryConcept.query.get(temp_concept_id)
        if not concept:
            return False

        concept.concept_data['selected'] = selected
        concept.concept_data['review_notes'] = review_notes
        concept.modified_by = modified_by
        concept.last_modified = datetime.utcnow()

        if selected:
            concept.status = 'reviewed'

        db.session.commit()
        return True

    @staticmethod
    def commit_selected_entities_to_ontserve(
        case_id: int,
        session_ids: List[str] = None,
        commit_all_reviewed: bool = False
    ) -> Dict[str, Any]:
        """
        Commit selected/reviewed entities to OntServe permanent storage.

        Args:
            case_id: Case ID
            session_ids: Specific sessions to commit (None = all sessions)
            commit_all_reviewed: Whether to commit all reviewed entities

        Returns:
            Dictionary with commitment results
        """
        try:
            # Get entities to commit
            query = TemporaryConcept.query.filter_by(document_id=case_id)

            if session_ids:
                query = query.filter(TemporaryConcept.session_id.in_(session_ids))

            if commit_all_reviewed:
                query = query.filter_by(status='reviewed')
            else:
                query = query.filter(
                    and_(
                        TemporaryConcept.concept_data['selected'].astext == 'true',
                        TemporaryConcept.status.in_(['pending', 'reviewed'])
                    )
                )

            entities_to_commit = query.all()

            if not entities_to_commit:
                return {
                    'success': True,
                    'committed_count': 0,
                    'message': 'No entities found to commit'
                }

            # Group entities by section for organized storage
            sections = {}
            for entity in entities_to_commit:
                section_type = entity.concept_data.get('section_type', 'discussion')
                if section_type not in sections:
                    sections[section_type] = []
                sections[section_type].append(entity)

            # Connect to OntServe and store entities
            mcp_client = get_external_mcp_client()
            committed_results = []

            for section_type, section_entities in sections.items():
                # Prepare entities for OntServe storage
                ontserve_entities = []
                for temp_entity in section_entities:
                    concept_data = temp_entity.concept_data
                    ontserve_entities.append({
                        'label': concept_data.get('label', ''),
                        'description': concept_data.get('description', ''),
                        'category': concept_data.get('category', 'Entity'),
                        'confidence': concept_data.get('confidence', 0.8),
                        'extraction_metadata': {
                            'temp_concept_id': temp_entity.id,
                            'session_id': temp_entity.session_id,
                            'extraction_method': temp_entity.extraction_method,
                            'nspe_section': section_type,
                            **concept_data.get('extraction_metadata', {})
                        }
                    })

                # Store in OntServe via MCP
                result = mcp_client.call_tool('store_extracted_entities', {
                    'case_id': str(case_id),
                    'section_type': section_type,
                    'entities': ontserve_entities,
                    'extraction_session': {
                        'session_id': entities_to_commit[0].session_id,
                        'timestamp': datetime.utcnow().isoformat(),
                        'committed_from_temp_storage': True,
                        'temp_entity_count': len(section_entities)
                    }
                })

                committed_results.append({
                    'section_type': section_type,
                    'entity_count': len(section_entities),
                    'ontserve_result': result
                })

                # Mark entities as committed
                for temp_entity in section_entities:
                    temp_entity.mark_committed()

            return {
                'success': True,
                'committed_count': len(entities_to_commit),
                'sections': committed_results,
                'case_id': case_id
            }

        except Exception as e:
            logger.error(f"Failed to commit entities to OntServe: {e}")
            return {
                'success': False,
                'error': str(e),
                'committed_count': 0
            }

    @staticmethod
    def create_entity_extraction_session_summary(case_id: int, session_id: str) -> Dict[str, Any]:
        """Create a summary of an extraction session for review."""
        entities = CaseEntityStorageService.get_case_session_entities(case_id, session_id)

        if not entities:
            return {'error': 'No entities found for session'}

        # Group by category
        categories = {}
        total_confidence = 0

        for entity in entities:
            category = entity.concept_data.get('category', 'Unknown')
            if category not in categories:
                categories[category] = []
            categories[category].append(entity)
            total_confidence += entity.concept_data.get('confidence', 0.8)

        section_type = entities[0].concept_data.get('section_type', 'unknown')
        section_info = CaseEntityStorageService.NSPE_SECTIONS.get(section_type, {})

        return {
            'session_id': session_id,
            'case_id': case_id,
            'section_type': section_type,
            'section_info': section_info,
            'total_entities': len(entities),
            'categories': {cat: len(ents) for cat, ents in categories.items()},
            'average_confidence': total_confidence / len(entities) if entities else 0,
            'extraction_timestamp': entities[0].extraction_timestamp.isoformat(),
            'extraction_method': entities[0].extraction_method,
            'status_summary': {
                'pending': sum(1 for e in entities if e.status == 'pending'),
                'reviewed': sum(1 for e in entities if e.status == 'reviewed'),
                'selected': sum(1 for e in entities if e.concept_data.get('selected', False))
            }
        }

    @staticmethod
    def clear_extraction_pass(
        case_id: int,
        extraction_pass: str,
        section_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Clear all uncommitted entities for a specific extraction pass and optional section.

        Used when re-running extraction to avoid duplicates.

        Args:
            case_id: Case ID
            extraction_pass: 'pass1', 'pass2', or 'pass3'
            section_type: Optional section filter ('facts', 'discussion', etc.)

        Returns:
            Dict with success status and cleared counts
        """
        try:
            from app.models import TemporaryRDFStorage, ExtractionPrompt
            from app.models.document_concept_annotation import DocumentConceptAnnotation

            # Map pass to extraction_type for RDF storage
            # Note: Pass 3 uses 'temporal_dynamics_enhanced' as extraction_type for all entities
            # Note: Pass 4 stores synthesis results (code provisions, questions, conclusions) + precedent references
            pass_extraction_types = {
                'pass1': ['roles', 'states', 'resources'],
                'pass2': ['principles', 'obligations', 'constraints', 'capabilities'],
                'pass3': ['temporal_dynamics_enhanced'],  # Single extraction type for all temporal entities
                'pass4': ['code_provision_reference', 'ethical_question', 'ethical_conclusion', 'precedent_case_reference']  # Synthesis results + precedent references
            }

            # Map pass to concept_type for ExtractionPrompt
            pass_prompt_types = {
                'pass1': ['roles', 'states', 'resources'],
                'pass2': ['principles', 'obligations', 'constraints', 'capabilities'],
                'pass3': ['actions', 'events', 'actions_events'],  # Prompt types used in Step 3
                'pass4': ['whole_case_synthesis']  # Whole case synthesis prompt
            }

            extraction_types = pass_extraction_types.get(extraction_pass)
            prompt_types = pass_prompt_types.get(extraction_pass)

            # Check if pass is unknown (None means not in dictionary)
            if extraction_types is None or prompt_types is None:
                return {
                    'success': False,
                    'error': f'Unknown extraction pass: {extraction_pass}'
                }

            # Pass 4 has no RDF entities (empty list is valid)
            # Continue with clearing prompts only

            cleared_stats = {
                'temporary_concepts': 0,
                'rdf_triples': 0,
                'extraction_prompts': 0,
                'synthesis_annotations': 0,  # Text span annotations for Step 4
                'types_cleared': extraction_types,
                'section_type': section_type
            }

            # Get session IDs for section if specified
            section_session_ids = None
            if section_type:
                section_prompts = ExtractionPrompt.query.filter_by(
                    case_id=case_id,
                    section_type=section_type
                ).all()
                section_session_ids = {p.extraction_session_id for p in section_prompts if p.extraction_session_id}
                logger.info(f"Clearing {extraction_pass} from {section_type} section (sessions: {section_session_ids})")

            # 1. Clear temporary concepts
            concept_query = TemporaryConcept.query.filter_by(document_id=case_id)
            if section_type:
                # Filter by section in concept_data JSON
                concept_query = concept_query.filter(
                    TemporaryConcept.concept_data['section_type'].astext == section_type
                )

            # Count and delete
            cleared_stats['temporary_concepts'] = concept_query.count()
            concept_query.delete(synchronize_session='fetch')

            # 2. Clear RDF storage for specified extraction types (BOTH committed and uncommitted)
            for extraction_type in extraction_types:
                rdf_query = db.session.query(TemporaryRDFStorage).filter_by(
                    case_id=case_id,
                    extraction_type=extraction_type
                    # NOTE: Clearing both committed and uncommitted entities
                )

                # Filter by extraction session IDs from prompts
                if section_session_ids:
                    rdf_query = rdf_query.filter(
                        TemporaryRDFStorage.extraction_session_id.in_(section_session_ids)
                    )

                type_count = rdf_query.count()
                cleared_stats['rdf_triples'] += type_count
                rdf_query.delete(synchronize_session='fetch')

            # 3. Delete extraction prompts
            # NOTE: We delete prompts for ALL sections for this pass,
            # because when clearing a pass we want to clear all prompts for that pass
            for prompt_type in prompt_types:
                prompt_query = db.session.query(ExtractionPrompt).filter_by(
                    case_id=case_id,
                    concept_type=prompt_type
                )

                # Count and delete (no section filter - clear all prompts for this extraction type)
                prompt_count = prompt_query.count()
                cleared_stats['extraction_prompts'] += prompt_count
                prompt_query.delete(synchronize_session='fetch')

            # 4. For Pass 4: Clear synthesis annotations (text span mappings)
            if extraction_pass == 'pass4':
                annotation_query = db.session.query(DocumentConceptAnnotation).filter_by(
                    document_type='case',
                    document_id=case_id,
                    ontology_name='step4_synthesis'
                )

                annotation_count = annotation_query.count()
                cleared_stats['synthesis_annotations'] = annotation_count
                annotation_query.delete(synchronize_session='fetch')

                logger.info(f"Cleared {annotation_count} synthesis annotations for case {case_id}")

            db.session.commit()

            total_cleared = (cleared_stats['temporary_concepts'] +
                           cleared_stats['rdf_triples'] +
                           cleared_stats['extraction_prompts'] +
                           cleared_stats['synthesis_annotations'])

            section_label = section_type.replace('_', ' ').title() if section_type else 'all sections'
            message = f"Cleared {total_cleared} items from {extraction_pass.upper()} ({section_label})"

            logger.info(f"Cleared {extraction_pass} for case {case_id}: {cleared_stats}")

            return {
                'success': True,
                'message': message,
                'cleared_stats': cleared_stats,
                'total_cleared': total_cleared
            }

        except Exception as e:
            import traceback
            logger.error(f"Error clearing {extraction_pass} for case {case_id}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            db.session.rollback()
            return {
                'success': False,
                'error': str(e),
                'total_cleared': 0
            }

    @staticmethod
    def has_extraction_been_run(
        case_id: int,
        extraction_pass: str,
        section_type: Optional[str] = None
    ) -> bool:
        """
        Check if an extraction pass has been run before for this case/section.

        Used to show warning about re-running causing duplicates.

        Args:
            case_id: Case ID
            extraction_pass: 'pass1', 'pass2', or 'pass3'
            section_type: Optional section filter

        Returns:
            True if extraction has been run before
        """
        try:
            from app.models import TemporaryRDFStorage

            # Map pass to extraction_type for RDF storage
            # Note: Pass 3 uses 'temporal_dynamics_enhanced' as extraction_type for all entities
            # Note: Pass 4 stores synthesis results (code provisions, questions, conclusions) + precedent references
            pass_extraction_types = {
                'pass1': ['roles', 'states', 'resources'],
                'pass2': ['principles', 'obligations', 'constraints', 'capabilities'],
                'pass3': ['temporal_dynamics_enhanced'],  # Single extraction type for all temporal entities
                'pass4': ['code_provision_reference', 'ethical_question', 'ethical_conclusion', 'precedent_case_reference']  # Synthesis results + precedent references
            }

            extraction_types = pass_extraction_types.get(extraction_pass)
            if extraction_types is None:  # Unknown pass
                return False

            # Check if any RDF entities exist for this pass
            query = db.session.query(TemporaryRDFStorage).filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.extraction_type.in_(extraction_types)
            )

            # Add section filter if specified
            if section_type:
                from app.models import ExtractionPrompt
                section_prompts = ExtractionPrompt.query.filter_by(
                    case_id=case_id,
                    section_type=section_type
                ).all()
                section_session_ids = {p.extraction_session_id for p in section_prompts if p.extraction_session_id}

                if section_session_ids:
                    query = query.filter(
                        TemporaryRDFStorage.extraction_session_id.in_(section_session_ids)
                    )

            return query.first() is not None

        except Exception as e:
            logger.error(f"Error checking extraction status: {e}")
            return False