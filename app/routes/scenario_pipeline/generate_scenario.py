"""
Scenario Generation from Extracted Entities

Generates interactive teaching scenarios from fully-analyzed cases using
Server-Sent Events (SSE) for real-time progress streaming.

Follows the proven pattern from step3_enhanced.py (temporal dynamics extraction).
"""

from flask import Response, jsonify
import json
import logging
from datetime import datetime

from app.models import Document
from app.services.scenario_generation.orchestrator import ScenarioGenerationOrchestrator
from app.utils.environment_auth import auth_required_for_llm

logger = logging.getLogger(__name__)


@auth_required_for_llm
def generate_scenario_from_case(case_id):
    """
    Generate interactive scenario with real-time progress streaming.

    Uses Server-Sent Events (SSE) to stream progress through all 9 stages:
    1. Data Collection
    2. Timeline Construction
    3. Participant Mapping
    4. Decision Point Identification
    5. Causal Chain Integration
    6. Normative Framework Integration
    7. Scenario Assembly
    8. Interactive Model Generation
    9. Validation

    Args:
        case_id: Case ID to generate scenario from

    Returns:
        SSE response stream with progress updates
    """
    try:
        logger.info(f"[Scenario Gen] Starting generation for case {case_id}")

        # Verify case exists and check eligibility BEFORE generator
        # (database operations must happen in request context)
        case = Document.query.get_or_404(case_id)

        # Create orchestrator and check eligibility
        orchestrator = ScenarioGenerationOrchestrator()
        eligibility = orchestrator.check_eligibility(case_id)

        if not eligibility.eligible:
            logger.error(f"[Scenario Gen] Case {case_id} not eligible: {eligibility.summary}")
            return jsonify({
                'error': 'Case not eligible',
                'summary': eligibility.summary,
                'details': eligibility.to_dict()
            }), 400

        # Collect data BEFORE generator (database operations)
        logger.info(f"[Scenario Gen] Collecting data for case {case_id}")
        data = orchestrator.collector.collect_all_data(case_id)
        entity_count = sum(len(entities) for entities in data.merged_entities.values())

        logger.info(f"[Scenario Gen] Data collection complete: {entity_count} entities")

        # Build timeline BEFORE generator (database operations)
        logger.info(f"[Scenario Gen] Building timeline for case {case_id}")
        timeline = orchestrator.timeline_constructor.build_timeline(case_id)
        logger.info(f"[Scenario Gen] Timeline built: {len(timeline.entries)} entries")

        def generate():
            """Generator for Server-Sent Events"""
            try:
                logger.info(f"[Scenario Gen] Starting SSE stream for case {case_id}")

                # Send initial event
                yield f"data: {json.dumps({
                    'stage': 'init',
                    'stage_number': 0,
                    'progress': 0,
                    'message': 'Initializing scenario generation...',
                    'case_id': case_id,
                    'case_title': case.title,
                    'eligibility': eligibility.to_dict(),
                    'timestamp': datetime.utcnow().isoformat()
                })}\n\n"

                # Stage 1: Data Collection (already complete)
                yield f"data: {json.dumps({
                    'stage': 'data_collection',
                    'stage_number': 1,
                    'progress': 10,
                    'message': f'Data collection complete: {entity_count} entities',
                    'data': {
                        'temporary_entities': sum(len(e) for e in data.temporary_entities.values()),
                        'committed_entities': sum(len(e) for e in data.committed_entities.values()),
                        'merged_entities': entity_count,
                        'entity_types': list(data.merged_entities.keys())
                    },
                    'timestamp': datetime.utcnow().isoformat()
                })}\n\n"

                # Stage 2: Timeline Construction (already complete)
                yield f"data: {json.dumps({
                    'stage': 'timeline_construction',
                    'stage_number': 2,
                    'progress': 30,
                    'message': 'Building chronological timeline from temporal dynamics...',
                    'timestamp': datetime.utcnow().isoformat()
                })}\n\n"

                # Timeline already built before generator
                timeline_dict = timeline.to_dict()

                yield f"data: {json.dumps({
                    'stage': 'timeline_construction',
                    'stage_number': 2,
                    'progress': 35,
                    'message': f'Timeline built with {len(timeline.entries)} timepoints across {len(timeline.phases)} phases',
                    'data': timeline_dict,
                    'timestamp': datetime.utcnow().isoformat()
                })}\n\n"

                # Stage 3: Participant Mapping
                yield f"data: {json.dumps({
                    'stage': 'participant_mapping',
                    'stage_number': 3,
                    'progress': 40,
                    'message': 'Extracting character profiles from roles...',
                    'timestamp': datetime.utcnow().isoformat()
                })}\n\n"

                roles = data.get_entities_by_type('Role')
                if not roles:
                    roles = data.get_entities_by_type('Roles')

                # Map participants (includes LLM enhancement)
                yield f"data: {json.dumps({
                    'stage': 'participant_mapping',
                    'stage_number': 3,
                    'progress': 42,
                    'message': f'Building profiles for {len(roles)} participants...',
                    'timestamp': datetime.utcnow().isoformat()
                })}\n\n"

                participant_result = orchestrator.participant_mapper.map_participants(
                    roles,
                    timeline_data=timeline.to_dict() if timeline else None
                )

                # LLM enhancement progress
                yield f"data: {json.dumps({
                    'stage': 'participant_mapping',
                    'stage_number': 3,
                    'progress': 45,
                    'message': 'Enhancing character arcs with LLM...',
                    'timestamp': datetime.utcnow().isoformat()
                })}\n\n"

                # Save to database
                yield f"data: {json.dumps({
                    'stage': 'participant_mapping',
                    'stage_number': 3,
                    'progress': 48,
                    'message': 'Saving character profiles to database...',
                    'timestamp': datetime.utcnow().isoformat()
                })}\n\n"

                saved_count = orchestrator.participant_mapper.save_to_database(
                    case_id=case_id,
                    result=participant_result,
                    llm_model='claude-sonnet-4-5-20250929'
                )

                participant_summary = participant_result.to_dict()
                yield f"data: {json.dumps({
                    'stage': 'participant_mapping',
                    'stage_number': 3,
                    'progress': 50,
                    'message': f'Created {len(participant_result.participants)} character profiles with enhanced arcs',
                    'data': participant_summary,
                    'details': {
                        'saved_to_database': saved_count,
                        'protagonist': participant_result.protagonist_id,
                        'llm_enhanced': participant_result.llm_enrichment is not None,
                        'has_teaching_notes': participant_result.teaching_notes is not None
                    },
                    'timestamp': datetime.utcnow().isoformat()
                })}\n\n"

                # Stage 4: Decision Point Identification
                yield f"data: {json.dumps({
                    'stage': 'decision_identification',
                    'stage_number': 4,
                    'progress': 55,
                    'message': 'Identifying decision points from actions and questions...',
                    'timestamp': datetime.utcnow().isoformat()
                })}\n\n"

                # Get actions and questions
                actions_entities = data.get_entities_by_type('actions')
                if not actions_entities:
                    actions_entities = data.get_entities_by_type('Action')

                questions_entities = data.get_entities_by_type('questions')
                if not questions_entities:
                    questions_entities = data.get_entities_by_type('Question')

                # Identify decision points
                decision_result = orchestrator.decision_identifier.identify_decisions(
                    actions=actions_entities,
                    questions=questions_entities,
                    timeline_data=timeline.to_dict() if timeline else None,
                    participants=participant_result.participants if participant_result else None,
                    synthesis_data=data.synthesis_data
                )

                decision_summary = decision_result.to_dict()
                yield f"data: {json.dumps({
                    'stage': 'decision_identification',
                    'stage_number': 4,
                    'progress': 60,
                    'message': f'Identified {decision_result.total_decisions} decision points',
                    'data': decision_summary,
                    'timestamp': datetime.utcnow().isoformat()
                })}\n\n"

                # Stage 5-9: Quick placeholders
                stages = [
                    ('causal_integration', 5, 65, 70, 'Linking decision consequences...'),
                    ('normative_integration', 6, 75, 80, 'Integrating ethical framework...'),
                    ('scenario_assembly', 7, 85, 90, 'Assembling complete scenario...'),
                    ('model_generation', 8, 93, 95, 'Creating interactive models...'),
                    ('validation', 9, 97, 99, 'Validating scenario quality...')
                ]

                for stage_name, stage_num, progress_start, progress_end, message in stages:
                    yield f"data: {json.dumps({
                        'stage': stage_name,
                        'stage_number': stage_num,
                        'progress': progress_start,
                        'message': message,
                        'timestamp': datetime.utcnow().isoformat()
                    })}\n\n"

                    yield f"data: {json.dumps({
                        'stage': stage_name,
                        'stage_number': stage_num,
                        'progress': progress_end,
                        'message': f'{message} (Stage {stage_num} placeholder)',
                        'timestamp': datetime.utcnow().isoformat()
                    })}\n\n"

                # Completion
                result = {
                    'success': True,
                    'case_id': case_id,
                    'entity_count': entity_count,
                    'stages_completed': 9,
                    'status': 'complete_placeholder',
                    'message': 'Pipeline executed successfully (Stages 2-9 are placeholders)',
                    'note': 'This is a proof-of-concept. Full implementation coming in Weeks 2-6.'
                }

                yield f"data: {json.dumps({
                    'stage': 'complete',
                    'stage_number': 10,
                    'progress': 100,
                    'message': 'Scenario generation pipeline complete!',
                    'result': result,
                    'timestamp': datetime.utcnow().isoformat()
                })}\n\n"

                logger.info(f"[Scenario Gen] Successfully completed generation for case {case_id}")

            except Exception as e:
                logger.error(f"[Scenario Gen] Error during generation: {str(e)}", exc_info=True)
                yield f"data: {json.dumps({
                    'stage': 'error',
                    'stage_number': -1,
                    'progress': 0,
                    'message': f'Error: {str(e)}',
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                })}\n\n"

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        logger.error(f"[Scenario Gen] Failed to initialize: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500
