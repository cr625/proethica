"""
Temporal Commit Service for ProEthica Enhanced Temporal Dynamics

Handles committing temporal entities (Actions, Events, Allen Relations, Causal Chains, Timeline)
to OntServe permanent storage with proper RDF representation.
"""

import logging
from typing import Dict, Any
from datetime import datetime

from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.services.ontserve_commit_service import OntServeCommitService

logger = logging.getLogger(__name__)


class TemporalCommitService:
    """Service for committing temporal dynamics entities to OntServe."""

    def __init__(self):
        """Initialize the temporal commit service."""
        self.ontserve_commit = OntServeCommitService()

    def commit_temporal_entities(self, case_id: int) -> Dict[str, Any]:
        """
        Commit all temporal dynamics entities to OntServe.

        Args:
            case_id: The case ID

        Returns:
            Dictionary with commit results
        """
        try:
            # Get all temporal dynamics entities
            temporal_entities = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='temporal_dynamics_enhanced',
                is_committed=False
            ).all()

            if not temporal_entities:
                return {
                    'success': False,
                    'error': 'No uncommitted temporal entities found for this case'
                }

            # Separate entities by type for targeted commitment
            entity_ids_by_type = {
                'actions': [],
                'events': [],
                'allen_relations': [],
                'causal_chains': [],
                'timeline': []
            }

            for entity in temporal_entities:
                entity_type = entity.entity_type
                if entity_type in entity_ids_by_type:
                    entity_ids_by_type[entity_type].append(entity.id)

            # Commit all entities using the existing OntServe commit service
            all_entity_ids = [entity.id for entity in temporal_entities]

            logger.info(f"Committing {len(all_entity_ids)} temporal entities for case {case_id}")
            logger.info(f"  Actions: {len(entity_ids_by_type['actions'])}")
            logger.info(f"  Events: {len(entity_ids_by_type['events'])}")
            logger.info(f"  Allen Relations: {len(entity_ids_by_type['allen_relations'])}")
            logger.info(f"  Causal Chains: {len(entity_ids_by_type['causal_chains'])}")
            logger.info(f"  Timeline: {len(entity_ids_by_type['timeline'])}")

            # Use the existing commit service
            commit_result = self.ontserve_commit.commit_selected_entities(case_id, all_entity_ids)

            if commit_result['success']:
                # Build detailed result
                result = {
                    'success': True,
                    'message': f"Successfully committed {len(all_entity_ids)} temporal entities to OntServe",
                    'result': {
                        'actions_committed': len(entity_ids_by_type['actions']),
                        'events_committed': len(entity_ids_by_type['events']),
                        'allen_relations_committed': len(entity_ids_by_type['allen_relations']),
                        'causal_chains_committed': len(entity_ids_by_type['causal_chains']),
                        'timeline_committed': len(entity_ids_by_type['timeline']),
                        'total_committed': len(all_entity_ids),
                        'classes_committed': commit_result.get('classes_committed', 0),
                        'individuals_committed': commit_result.get('individuals_committed', 0)
                    }
                }

                if commit_result.get('errors'):
                    result['warnings'] = commit_result['errors']

                return result
            else:
                return {
                    'success': False,
                    'error': commit_result.get('error', 'Unknown error during commit')
                }

        except Exception as e:
            logger.error(f"Error committing temporal entities: {e}")
            return {
                'success': False,
                'error': str(e)
            }
