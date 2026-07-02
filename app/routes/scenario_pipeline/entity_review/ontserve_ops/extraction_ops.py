"""Refresh-committed, commit-temporal, review-enhanced-temporal, clear-and-rerun, check-extraction."""
import logging
from datetime import datetime

from flask import render_template, request, jsonify, redirect, url_for, flash
from app.models import Document, db, TemporaryRDFStorage
from app.services.entity.case_entity_storage_service import CaseEntityStorageService
from app.services.extraction.field_classification import group_properties
from app.utils.environment_auth import (
    auth_optional,
    auth_required_for_write
)

logger = logging.getLogger(__name__)


def register_ontserve_extraction_ops(bp):
    @bp.route('/case/<int:case_id>/entities/refresh_committed', methods=['POST'])
    @auth_required_for_write  # Require auth for write operations
    def refresh_committed_from_ontserve(case_id):
        """Refresh committed entities with live data from OntServe.

        This addresses synchronization issues by pulling the latest versions
        of committed entities from OntServe and updating ProEthica's records.
        Also removes entities that have been deleted from OntServe.
        """
        try:
            from app.services.ontserve.ontserve_data_fetcher import OntServeDataFetcher

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
            from app.services.commit.temporal_commit_service import TemporalCommitService

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
                    # Surface every field convert_action_to_rdf emits so this review
                    # faithfully represents the extraction. The obligation engagement
                    # post-step splits the pool into three buckets (fulfills / violates
                    # / raises); showing only fulfills hid two thirds of that analysis.
                    # foreseenUnintendedEffects and the obligation buckets are lists;
                    # temporalSequence is an int. (competing_priorities was dropped from
                    # Step-3 extraction 2026-06-01 -- no consumer; tension is in the
                    # defeasibility edges.)
                    actions.append({
                        'field_groups': group_properties(rdf_data),
                        'id': entity.id,
                        'label': entity.entity_label,
                        'uri': entity.entity_uri,
                        'description': rdf_data.get('proeth:description', ''),
                        'agent': rdf_data.get('proeth:hasAgent', ''),
                        'event_role_context': rdf_data.get('proeth:eventRoleContext', ''),
                        'temporal_marker': rdf_data.get('proeth:temporalMarker', ''),
                        'temporal_sequence': rdf_data.get('proeth:temporalSequence'),
                        'mental_state': rdf_data.get('proeth:hasMentalState', ''),
                        'intended_outcome': rdf_data.get('proeth:intendedOutcome', ''),
                        'foreseen_unintended_effects': rdf_data.get('proeth:foreseenUnintendedEffects', []),
                        'fulfills_obligation': rdf_data.get('proeth:fulfillsObligation', []),
                        'violates_obligation': rdf_data.get('proeth:violatesObligation', []),
                        'raises_obligation': rdf_data.get('proeth:raisesObligation', []),
                        'guided_by_principle': rdf_data.get('proeth:guidedByPrinciple', []),
                        'within_competence': rdf_data.get('proeth:withinCompetence', False),
                        'requires_capability': rdf_data.get('proeth:requiresCapability', []),
                        # Event Calculus fluent transitions: the States this action brings
                        # into / takes out of holding (committed as proeth-core:initiates /
                        # terminates edges). temporal_extent = OWL-Time instant|interval.
                        'initiates': rdf_data.get('proeth:initiates', []),
                        'terminates': rdf_data.get('proeth:terminates', []),
                        'temporal_extent': rdf_data.get('proeth:temporalExtent', ''),
                        'rdf_json': rdf_data
                    })

                elif 'Event' in entity_type:
                    # Field names match what convert_event_to_rdf actually emits
                    # (rdf_converter.py). event_type is the Event Calculus agent-caused /
                    # exogenous / automatic distinction (Berreby et al. 2017); severity is a
                    # heuristic triage indicator (renamed from emergency_status 2026-05-31,
                    # NOT a formal ontology category). The duplicate urgency_level field and
                    # the direct proeth:activatesConstraint / proeth:createsObligation event
                    # links were dropped 2026-05-31 (urgency_level always equalled severity;
                    # the norm links were redundant with the grounded initiates -> State ->
                    # activatesConstraint/activatesObligation path). The event now carries its
                    # world-change as initiates / terminates.
                    events.append({
                        'field_groups': group_properties(rdf_data),
                        'id': entity.id,
                        'label': entity.entity_label,
                        'uri': entity.entity_uri,
                        'description': rdf_data.get('proeth:description', ''),
                        'temporal_marker': rdf_data.get('proeth:temporalMarker', ''),
                        'temporal_sequence': rdf_data.get('proeth:temporalSequence'),
                        'event_type': rdf_data.get('proeth:eventType', ''),
                        'severity': rdf_data.get('proeth:severity', ''),
                        'causes_state_change': rdf_data.get('proeth:causesStateChange', ''),
                        'caused_by_action': rdf_data.get('proeth:causedByAction', ''),
                        # Event Calculus fluent transitions (proeth-core:initiates /
                        # terminates edges at commit). temporal_extent = OWL-Time instant|interval.
                        'initiates': rdf_data.get('proeth:initiates', []),
                        'terminates': rdf_data.get('proeth:terminates', []),
                        'temporal_extent': rdf_data.get('proeth:temporalExtent', ''),
                        # Verbatim grounding + confidence (Stage-2 audit convergence with the
                        # seeded events contract).
                        'text_references': rdf_data.get('proeth:textReferences', []),
                        'confidence': rdf_data.get('proeth:confidence'),
                        'rdf_json': rdf_data
                    })

                elif 'CausalChain' in entity_type:
                    causal_chains.append({
                        'field_groups': group_properties(rdf_data),
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

            # Order actions and events chronologically by the temporal-sequence post-step
            # (the same ordering the study timeline uses), falling back to DB id for rows
            # the sequence step has not visited. A large sentinel keeps unsequenced rows last.
            def _seq_key(item):
                seq = item.get('temporal_sequence')
                try:
                    return (0, int(seq))
                except (TypeError, ValueError):
                    return (1, item.get('id') or 0)
            actions.sort(key=_seq_key)
            events.sort(key=_seq_key)

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

            # Build mapping from temporal marker -> entity for timeline display
            timeline_entity_map = {}
            for a in actions:
                marker = a.get('temporal_marker', '')
                if marker:
                    timeline_entity_map[marker] = {'label': a['label'], 'kind': 'action'}
            for e in events:
                marker = e.get('temporal_marker', '')
                if marker:
                    timeline_entity_map[marker] = {'label': e['label'], 'kind': 'event'}

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
                'timeline_entity_map': timeline_entity_map,
                'summary': summary,
                'all_committed': all_committed
            }

            return render_template('entity_review/enhanced_temporal_review.html', **context)

        except Exception as e:
            logger.error(f"Error loading enhanced temporal review for case {case_id}: {e}")
            flash(f"Error loading review page: {str(e)}", 'danger')
            return redirect(url_for('cases.case_pipeline', case_id=case_id))

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
            if extraction_pass in ('pass1', 'pass2', 'pass3'):
                redirect_url = url_for('cases.case_pipeline', case_id=case_id)
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
