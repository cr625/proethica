"""
OntServe Operations Routes

Routes for OntServe integration: refresh, commit temporal entities, auto-commit,
class search, entity matching, and overlap analysis.
"""

import logging
from datetime import datetime

from flask import render_template, request, jsonify, redirect, url_for, flash
from app.models import Document, db, TemporaryRDFStorage
from app.services.case_entity_storage_service import CaseEntityStorageService
from app.utils.environment_auth import (
    auth_optional,
    auth_required_for_write
)

logger = logging.getLogger(__name__)


def register_ontserve_ops_routes(bp):
    """Register OntServe operation routes on the given blueprint."""

    @bp.route('/case/<int:case_id>/entities/refresh_committed', methods=['POST'])
    @auth_required_for_write  # Require auth for write operations
    def refresh_committed_from_ontserve(case_id):
        """Refresh committed entities with live data from OntServe.

        This addresses synchronization issues by pulling the latest versions
        of committed entities from OntServe and updating ProEthica's records.
        Also removes entities that have been deleted from OntServe.
        """
        try:
            from app.services.ontserve_data_fetcher import OntServeDataFetcher

            # Get all committed entities from ProEthica
            committed_entities = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                is_published=True
            ).all()

            if not committed_entities:
                return jsonify({
                    'success': True,
                    'message': 'No committed entities to refresh',
                    'refreshed': 0
                })

            # Convert to dictionary format for comparison
            proethica_entities = [entity.to_dict() for entity in committed_entities]

            # Initialize fetcher and refresh
            fetcher = OntServeDataFetcher()
            refresh_result = fetcher.refresh_committed_entities(case_id, proethica_entities)

            # Update ProEthica records with OntServe data if there are changes
            update_count = 0
            delete_count = 0

            for detail in refresh_result['details']:
                if detail['status'] == 'modified':
                    # Find the entity in ProEthica
                    entity_uri = detail['entity_uri']
                    entity = TemporaryRDFStorage.query.filter_by(
                        case_id=case_id,
                        entity_uri=entity_uri,
                        is_published=True
                    ).first()

                    if entity and 'ontserve_data' in detail:
                        # Update with live data from OntServe
                        ontserve_data = detail['ontserve_data']
                        entity.entity_label = ontserve_data.get('label', entity.entity_label)
                        # Note: parent_uri field doesn't exist in TemporaryRDFStorage
                        # entity.parent_uri = ontserve_data.get('parent_uri')

                        # Update the review notes to track sync
                        sync_note = f"Synced from OntServe at {datetime.utcnow().isoformat()}"
                        if entity.review_notes:
                            entity.review_notes = f"{entity.review_notes}\n{sync_note}"
                        else:
                            entity.review_notes = sync_note

                        update_count += 1

                elif detail['status'] == 'not_found':
                    # Entity was deleted from OntServe, remove from ProEthica
                    entity_uri = detail['entity_uri']
                    entity = TemporaryRDFStorage.query.filter_by(
                        case_id=case_id,
                        entity_uri=entity_uri,
                        is_published=True
                    ).first()

                    if entity:
                        db.session.delete(entity)
                        delete_count += 1
                        logger.info(f"Removed deleted entity {entity_uri} from ProEthica")

            # Commit all updates and deletions
            if update_count > 0 or delete_count > 0:
                db.session.commit()
                logger.info(f"Updated {update_count} entities and removed {delete_count} deleted entities for case {case_id}")

            # Prepare response message
            message_parts = []
            if refresh_result['unchanged'] > 0:
                message_parts.append(f"{refresh_result['unchanged']} unchanged")
            if refresh_result['modified'] > 0:
                message_parts.append(f"{refresh_result['modified']} updated")
            if delete_count > 0:
                message_parts.append(f"{delete_count} removed (deleted from OntServe)")
            elif refresh_result['not_found'] > 0:
                message_parts.append(f"{refresh_result['not_found']} removed (not found in OntServe)")

            message = f"Refreshed {refresh_result['refreshed']} entities: {', '.join(message_parts)}"

            return jsonify({
                'success': True,
                'message': message,
                'result': refresh_result,
                'deleted_count': delete_count
            })

        except Exception as e:
            logger.error(f"Error refreshing committed entities from OntServe: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            })

    @bp.route('/case/<int:case_id>/entities/temporal/commit', methods=['POST'])
    @auth_required_for_write  # Require auth for commit operations
    def commit_temporal_entities(case_id):
        """Commit all temporal dynamics entities to OntServe."""
        try:
            from app.services.temporal_commit_service import TemporalCommitService

            commit_service = TemporalCommitService()
            result = commit_service.commit_temporal_entities(case_id)

            if result['success']:
                return jsonify(result)
            else:
                # Check if this is "already committed" vs actual error
                error_msg = result.get('error', '')
                if 'No uncommitted' in error_msg or 'already committed' in error_msg.lower():
                    # Not an error - entities are already committed
                    return jsonify({
                        'success': True,
                        'message': 'All temporal entities have already been committed',
                        'already_committed': True
                    })
                else:
                    # Actual error
                    return jsonify(result), 500

        except Exception as e:
            logger.error(f"Error committing temporal entities: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/enhanced_temporal/review')
    @auth_optional
    def review_enhanced_temporal(case_id):
        """
        Review page for Enhanced Temporal Dynamics extraction results.

        Displays:
        - Extracted actions and events
        - Temporal markers and Allen relations
        - Timeline visualization with OWL-Time integration
        - Causal chains and NESS test results
        """
        try:
            # Get the case
            case = Document.query.get_or_404(case_id)

            # Get all temporal dynamics entities from database
            temporal_entities = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='temporal_dynamics_enhanced'
            ).all()

            # Separate entities by type
            actions = []
            events = []
            allen_relations = []
            causal_chains = []
            timeline = None

            for entity in temporal_entities:
                entity_dict = entity.to_dict()
                rdf_data = entity.rdf_json_ld or {}
                entity_type = rdf_data.get('@type', '')

                if 'Action' in entity_type:
                    actions.append({
                        'id': entity.id,
                        'label': entity.entity_label,
                        'uri': entity.entity_uri,
                        'description': rdf_data.get('proeth:description', ''),
                        'agent': rdf_data.get('proeth:hasAgent', ''),
                        'temporal_marker': rdf_data.get('proeth:temporalMarker', ''),
                        'mental_state': rdf_data.get('proeth:hasMentalState', ''),
                        'intended_outcome': rdf_data.get('proeth:intendedOutcome', ''),
                        'fulfills_obligation': rdf_data.get('proeth:fulfillsObligation', []),
                        'guided_by_principle': rdf_data.get('proeth:guidedByPrinciple', []),
                        'within_competence': rdf_data.get('proeth:withinCompetence', False),
                        'requires_capability': rdf_data.get('proeth:requiresCapability', []),
                        'rdf_json': rdf_data
                    })

                elif 'Event' in entity_type:
                    events.append({
                        'id': entity.id,
                        'label': entity.entity_label,
                        'uri': entity.entity_uri,
                        'description': rdf_data.get('proeth:description', ''),
                        'affected_entity': rdf_data.get('proeth:affectsEntity', ''),
                        'temporal_marker': rdf_data.get('proeth:temporalMarker', ''),
                        'triggers_state': rdf_data.get('proeth:triggersState', []),
                        'activates_constraint': rdf_data.get('proeth:activatesConstraint', []),
                        'transforms_obligation': rdf_data.get('proeth:transformsObligation', []),
                        'emergency_level': rdf_data.get('proeth:emergencyLevel', ''),
                        'rdf_json': rdf_data
                    })

                elif 'CausalChain' in entity_type:
                    causal_chains.append({
                        'id': entity.id,
                        'cause': rdf_data.get('proeth:cause', ''),
                        'effect': rdf_data.get('proeth:effect', ''),
                        'causal_language': rdf_data.get('proeth:causalLanguage', ''),
                        'necessary_factors': rdf_data.get('proeth:necessaryFactors', []),
                        'sufficient_factors': rdf_data.get('proeth:sufficientFactors', []),
                        'counterfactual': rdf_data.get('proeth:counterfactual', ''),
                        'responsible_agent': rdf_data.get('proeth:responsibleAgent', ''),
                        'responsibility_type': rdf_data.get('proeth:responsibilityType', ''),
                        'within_agent_control': rdf_data.get('proeth:withinAgentControl', False),
                        'causal_sequence': rdf_data.get('proeth:causalSequence', []),
                        'rdf_json': rdf_data
                    })

                elif 'Timeline' in entity.entity_label:
                    timeline = {
                        'id': entity.id,
                        'label': entity.entity_label,
                        'uri': entity.entity_uri,
                        'total_elements': rdf_data.get('proeth:totalElements', 0),
                        'action_count': rdf_data.get('proeth:actionCount', 0),
                        'event_count': rdf_data.get('proeth:eventCount', 0),
                        'timepoints': rdf_data.get('proeth:hasTimepoints', []),
                        'temporal_consistency': rdf_data.get('proeth:temporalConsistency', {}),
                        'rdf_json': rdf_data
                    }

                elif entity.entity_type == 'allen_relations':
                    # Allen relation with OWL-Time mapping
                    allen_relations.append({
                        'id': entity.id,
                        'label': entity.entity_label,
                        'from_entity': rdf_data.get('proeth:fromEntity', ''),
                        'to_entity': rdf_data.get('proeth:toEntity', ''),
                        'relation_type': rdf_data.get('proeth:allenRelation', 'unknown'),
                        'owl_time_property': rdf_data.get('proeth:owlTimeProperty', ''),
                        'owl_time_uri': rdf_data.get('proeth:owlTimeURI', ''),
                        'description': rdf_data.get('proeth:description', ''),
                        'evidence': rdf_data.get('proeth:evidence', ''),
                        'rdf_json': rdf_data
                    })

            extraction_complete = len(temporal_entities) > 0

            # Check commit status
            uncommitted_count = sum(1 for e in temporal_entities if not e.is_published)
            committed_count = sum(1 for e in temporal_entities if e.is_published)
            all_committed = extraction_complete and uncommitted_count == 0

            # Calculate summary statistics
            summary = {
                'total_entities': len(temporal_entities),
                'actions': len(actions),
                'events': len(events),
                'allen_relations': len(allen_relations),
                'causal_chains': len(causal_chains),
                'has_timeline': timeline is not None,
                'committed_count': committed_count,
                'uncommitted_count': uncommitted_count,
                'all_committed': all_committed
            }

            context = {
                'case': case,
                'current_step': 3,
                'step_title': 'Enhanced Temporal Dynamics - Review',
                'extraction_complete': extraction_complete,
                'actions': actions,
                'events': events,
                'allen_relations': allen_relations,
                'causal_chains': causal_chains,
                'timeline': timeline,
                'summary': summary,
                'all_committed': all_committed
            }

            return render_template('entity_review/enhanced_temporal_review.html', **context)

        except Exception as e:
            logger.error(f"Error loading enhanced temporal review for case {case_id}: {e}")
            flash(f"Error loading review page: {str(e)}", 'danger')
            return redirect(url_for('scenario_pipeline.step3', case_id=case_id))

    @bp.route('/case/<int:case_id>/entities/clear_and_rerun/<extraction_pass>', methods=['POST'])
    @auth_required_for_write
    def clear_and_rerun_pass(case_id, extraction_pass):
        """Clear entities for a pass and redirect to extraction."""
        try:
            data = request.get_json() or {}
            section_type = data.get('section_type')

            logger.info(f"clear_and_rerun_pass called: case_id={case_id}, extraction_pass={extraction_pass}, section_type={section_type}")

            # Clear the extraction pass
            result = CaseEntityStorageService.clear_extraction_pass(
                case_id=case_id,
                extraction_pass=extraction_pass,
                section_type=section_type
            )

            if not result['success']:
                logger.error(f"clear_extraction_pass failed: {result}")
                return jsonify(result), 400

            # Determine redirect URL based on pass
            if extraction_pass == 'pass1':
                redirect_url = url_for('scenario_pipeline.step1', case_id=case_id)
            elif extraction_pass == 'pass2':
                redirect_url = url_for('scenario_pipeline.step2', case_id=case_id)
            elif extraction_pass == 'pass3':
                redirect_url = url_for('scenario_pipeline.step3', case_id=case_id)
            elif extraction_pass == 'pass4':
                redirect_url = url_for('step4.step4_synthesis', case_id=case_id)
            else:
                redirect_url = url_for('scenario_pipeline.overview', case_id=case_id)

            return jsonify({
                'success': True,
                'message': result['message'],
                'redirect_url': redirect_url,
                'cleared_stats': result['cleared_stats']
            })

        except Exception as e:
            logger.error(f"Error in clear_and_rerun for case {case_id}: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/case/<int:case_id>/entities/check_extraction/<extraction_pass>')
    @auth_optional
    def check_extraction_status(case_id, extraction_pass):
        """Check if an extraction pass has been run before."""
        try:
            section_type = request.args.get('section_type')

            has_been_run = CaseEntityStorageService.has_extraction_been_run(
                case_id=case_id,
                extraction_pass=extraction_pass,
                section_type=section_type
            )

            return jsonify({
                'success': True,
                'has_been_run': has_been_run,
                'case_id': case_id,
                'extraction_pass': extraction_pass,
                'section_type': section_type
            })

        except Exception as e:
            logger.error(f"Error checking extraction status: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/case/<int:case_id>/entities/auto_commit', methods=['POST'])
    @auth_required_for_write
    def trigger_auto_commit(case_id):
        """
        Manually trigger auto-commit for entity-ontology linking.

        Links extracted entities to OntServe classes based on LLM match decisions,
        generates case TTL file, and updates precedent features for Jaccard calculation.
        """
        try:
            from app.services.auto_commit_service import AutoCommitService

            data = request.get_json() or {}
            force = data.get('force', False)

            auto_commit_service = AutoCommitService()
            result = auto_commit_service.commit_case_entities(case_id, force=force)

            # Convert dataclass to dict for JSON response
            response = {
                'success': True,
                'case_id': result.case_id,
                'total_entities': result.total_entities,
                'linked_count': result.linked_count,
                'new_class_count': result.new_class_count,
                'skipped_count': result.skipped_count,
                'error_count': result.error_count,
                'entity_classes': result.entity_classes,
                'ttl_file': result.ttl_file,
                'message': f"Auto-commit complete: {result.linked_count} linked, {result.new_class_count} new classes"
            }

            # Include detailed results if requested
            if data.get('include_details', False) and result.results:
                response['results'] = [
                    {
                        'entity_id': r.entity_id,
                        'entity_label': r.entity_label,
                        'entity_type': r.entity_type,
                        'action': r.action,
                        'linked_uri': r.linked_uri,
                        'confidence': r.confidence,
                        'reasoning': r.reasoning,
                        'error': r.error
                    }
                    for r in result.results
                ]

            return jsonify(response)

        except Exception as e:
            logger.error(f"Error in auto-commit for case {case_id}: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/entities/auto_commit_status')
    @auth_optional
    def get_auto_commit_status(case_id):
        """
        Get the auto-commit status for a case.

        Returns information about entity matching status and Jaccard readiness.
        """
        try:
            from app.services.auto_commit_service import AutoCommitService

            auto_commit_service = AutoCommitService()
            status = auto_commit_service.get_commit_status(case_id)

            return jsonify({
                'success': True,
                'status': status
            })

        except Exception as e:
            logger.error(f"Error getting auto-commit status for case {case_id}: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/entities/clear_ontology', methods=['POST'])
    @auth_required_for_write
    def clear_case_ontology(case_id):
        """
        Clear a case's OntServe ontology to prepare for re-extraction.

        This removes the case TTL file and resets committed entities,
        preventing circular matches when re-running extraction.

        Should be called before re-running extraction on a case that
        has already been committed to OntServe.
        """
        try:
            from app.services.auto_commit_service import AutoCommitService

            data = request.get_json() or {}
            reset_committed = data.get('reset_committed', True)

            auto_commit_service = AutoCommitService()
            result = auto_commit_service.clear_case_ontology(case_id, reset_committed=reset_committed)

            return jsonify(result)

        except Exception as e:
            logger.error(f"Error clearing case ontology for case {case_id}: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/entities/search_ontserve')
    @auth_optional
    def search_ontserve_classes(case_id):
        """
        Search OntServe for matching classes.

        Used by the match details modal for manual linking.
        """
        try:
            from sqlalchemy import create_engine, text

            query_param = request.args.get('q', '').strip()
            if not query_param:
                return jsonify({
                    'success': False,
                    'error': 'Search query required'
                }), 400

            # Search OntServe database for matching classes
            ontserve_engine = create_engine('postgresql://postgres:PASS@localhost:5432/ontserve')

            with ontserve_engine.connect() as conn:
                # Search by label (case-insensitive)
                search_query = text("""
                    SELECT uri, label, entity_type, comment
                    FROM ontology_entities
                    WHERE uri LIKE 'http://proethica.org/ontology/%'
                    AND (
                        LOWER(label) LIKE LOWER(:search_pattern)
                        OR LOWER(comment) LIKE LOWER(:search_pattern)
                    )
                    ORDER BY
                        CASE WHEN LOWER(label) = LOWER(:exact_match) THEN 0 ELSE 1 END,
                        label
                    LIMIT 20
                """)

                result = conn.execute(search_query, {
                    'search_pattern': f'%{query_param}%',
                    'exact_match': query_param
                })

                results = []
                for row in result:
                    results.append({
                        'uri': row[0],
                        'label': row[1],
                        'entity_type': row[2],
                        'description': row[3]
                    })

            return jsonify({
                'success': True,
                'query': query_param,
                'results': results,
                'count': len(results)
            })

        except Exception as e:
            logger.error(f"Error searching OntServe: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/entities/<int:entity_id>/set_match', methods=['POST'])
    @auth_required_for_write
    def set_entity_match(case_id, entity_id):
        """
        Set or update the match for an entity.

        Used for manual linking from the match details modal.
        """
        try:
            from app.models.temporary_rdf_storage import TemporaryRDFStorage

            data = request.get_json() or {}
            matched_uri = data.get('matched_uri')
            matched_label = data.get('matched_label')
            method = data.get('method', 'manual')
            confidence = data.get('confidence', 1.0)
            reasoning = data.get('reasoning', 'Manually linked by user')

            # Find the entity
            entity = TemporaryRDFStorage.query.filter_by(id=entity_id, case_id=case_id).first()
            if not entity:
                return jsonify({
                    'success': False,
                    'error': 'Entity not found'
                }), 404

            # Update match fields
            entity.matched_ontology_uri = matched_uri
            entity.matched_ontology_label = matched_label
            entity.match_confidence = confidence
            entity.match_method = method
            entity.match_reasoning = reasoning

            db.session.commit()

            logger.info(f"Updated match for entity {entity_id}: {matched_label} ({matched_uri})")

            return jsonify({
                'success': True,
                'entity_id': entity_id,
                'matched_uri': matched_uri,
                'matched_label': matched_label,
                'confidence': confidence,
                'method': method
            })

        except Exception as e:
            logger.error(f"Error setting entity match: {e}")
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/entities/<int:entity_id>/mark_new', methods=['POST'])
    @auth_required_for_write
    def mark_entity_as_new(case_id, entity_id):
        """
        Mark an entity as a new class (clear any existing match).

        Used when the user wants to create a new class instead of linking to existing.
        """
        try:
            from app.models.temporary_rdf_storage import TemporaryRDFStorage

            # Find the entity
            entity = TemporaryRDFStorage.query.filter_by(id=entity_id, case_id=case_id).first()
            if not entity:
                return jsonify({
                    'success': False,
                    'error': 'Entity not found'
                }), 404

            # Clear match fields
            entity.matched_ontology_uri = None
            entity.matched_ontology_label = None
            entity.match_confidence = None
            entity.match_method = 'manual'
            entity.match_reasoning = 'Marked as new class by user'

            db.session.commit()

            logger.info(f"Marked entity {entity_id} as new class")

            return jsonify({
                'success': True,
                'entity_id': entity_id,
                'message': 'Entity marked as new class'
            })

        except Exception as e:
            logger.error(f"Error marking entity as new: {e}")
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/entities/<int:entity_id>/confirm_match', methods=['POST'])
    @auth_required_for_write
    def confirm_entity_match(case_id, entity_id):
        """
        Confirm the current match for an entity.

        Logs the confirmation for future learning and updates confidence to 1.0.
        """
        try:
            from app.models.temporary_rdf_storage import TemporaryRDFStorage
            from app.models.entity_match_confirmation import EntityMatchConfirmation
            from flask_login import current_user

            # Find the entity
            entity = TemporaryRDFStorage.query.filter_by(id=entity_id, case_id=case_id).first()
            if not entity:
                return jsonify({
                    'success': False,
                    'error': 'Entity not found'
                }), 404

            if not entity.matched_ontology_uri:
                return jsonify({
                    'success': False,
                    'error': 'No match to confirm'
                }), 400

            # Log the confirmation
            confirmation = EntityMatchConfirmation(
                case_id=case_id,
                entity_id=entity_id,
                entity_label=entity.entity_label,
                entity_type=entity.entity_type,
                original_match_uri=entity.matched_ontology_uri,
                original_match_label=entity.matched_ontology_label,
                original_confidence=entity.match_confidence,
                original_method=entity.match_method,
                action='confirmed',
                new_match_uri=entity.matched_ontology_uri,
                new_match_label=entity.matched_ontology_label,
                user_id=current_user.id if current_user and hasattr(current_user, 'id') else None
            )
            db.session.add(confirmation)

            # Update entity confidence to 1.0 (user confirmed)
            entity.match_confidence = 1.0
            entity.match_method = 'manual_confirmed'

            db.session.commit()

            logger.info(f"Confirmed match for entity {entity_id}: {entity.matched_ontology_label}")

            return jsonify({
                'success': True,
                'entity_id': entity_id,
                'matched_uri': entity.matched_ontology_uri,
                'matched_label': entity.matched_ontology_label,
                'message': 'Match confirmed'
            })

        except Exception as e:
            logger.error(f"Error confirming entity match: {e}")
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/entities/entity_overlap')
    @auth_optional
    def get_entity_overlap(case_id):
        """
        Get entity class overlap between this case and other cases for Jaccard similarity.

        Returns the entity_classes for this case and overlap statistics with other cases.
        """
        try:
            from sqlalchemy import text

            # Get entity_classes for this case
            query = text("""
                SELECT case_id, entity_classes
                FROM case_precedent_features
                WHERE entity_classes IS NOT NULL
            """)
            results = db.session.execute(query).fetchall()

            if not results:
                return jsonify({
                    'success': True,
                    'case_id': case_id,
                    'entity_classes': {},
                    'overlap_with_cases': [],
                    'message': 'No cases have entity_classes data yet'
                })

            # Find this case's entity classes
            this_case_classes = None
            other_cases = []

            for row in results:
                if row[0] == case_id:
                    this_case_classes = row[1] or {}
                else:
                    other_cases.append({
                        'case_id': row[0],
                        'entity_classes': row[1] or {}
                    })

            if this_case_classes is None:
                return jsonify({
                    'success': True,
                    'case_id': case_id,
                    'entity_classes': {},
                    'overlap_with_cases': [],
                    'message': 'This case has no entity_classes data. Run auto-commit first.'
                })

            # Calculate Jaccard overlap with each other case
            def calculate_jaccard(classes_a, classes_b):
                """Calculate Jaccard similarity across all entity types."""
                all_uris_a = set()
                all_uris_b = set()

                for entity_type, uris in classes_a.items():
                    all_uris_a.update(uris)
                for entity_type, uris in classes_b.items():
                    all_uris_b.update(uris)

                if not all_uris_a and not all_uris_b:
                    return 0.0, []

                intersection = all_uris_a & all_uris_b
                union = all_uris_a | all_uris_b

                if not union:
                    return 0.0, []

                return len(intersection) / len(union), list(intersection)

            overlap_results = []
            for other in other_cases:
                jaccard, shared_uris = calculate_jaccard(this_case_classes, other['entity_classes'])
                if jaccard > 0:  # Only include cases with some overlap
                    overlap_results.append({
                        'case_id': other['case_id'],
                        'jaccard_similarity': round(jaccard, 3),
                        'shared_classes_count': len(shared_uris),
                        'shared_class_uris': shared_uris[:10]  # Limit to first 10 for display
                    })

            # Sort by similarity descending
            overlap_results.sort(key=lambda x: x['jaccard_similarity'], reverse=True)

            return jsonify({
                'success': True,
                'case_id': case_id,
                'entity_classes': this_case_classes,
                'total_classes': sum(len(uris) for uris in this_case_classes.values()),
                'overlap_with_cases': overlap_results,
                'cases_with_overlap': len(overlap_results)
            })

        except Exception as e:
            logger.error(f"Error getting entity overlap for case {case_id}: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
