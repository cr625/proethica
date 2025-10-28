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

                # Stage 2: Timeline Construction (Placeholder)
                yield f"data: {json.dumps({
                    'stage': 'timeline_construction',
                    'stage_number': 2,
                    'progress': 30,
                    'message': 'Building chronological timeline from temporal dynamics...',
                    'timestamp': datetime.utcnow().isoformat()
                })}\n\n"

                # Placeholder timeline info
                yield f"data: {json.dumps({
                    'stage': 'timeline_construction',
                    'stage_number': 2,
                    'progress': 35,
                    'message': 'Timeline construction (Stage 2 placeholder)',
                    'data': {
                        'status': 'placeholder',
                        'actions': len(data.temporal_dynamics.actions),
                        'events': len(data.temporal_dynamics.events)
                    },
                    'timestamp': datetime.utcnow().isoformat()
                })}\n\n"

                # Stage 3: Participant Mapping (Placeholder)
                yield f"data: {json.dumps({
                    'stage': 'participant_mapping',
                    'stage_number': 3,
                    'progress': 45,
                    'message': 'Creating character profiles from role entities...',
                    'timestamp': datetime.utcnow().isoformat()
                })}\n\n"

                roles = data.get_entities_by_type('Role')
                yield f"data: {json.dumps({
                    'stage': 'participant_mapping',
                    'stage_number': 3,
                    'progress': 50,
                    'message': f'Identified {len(roles)} roles (Stage 3 placeholder)',
                    'data': {
                        'roles_identified': len(roles),
                        'role_names': [role.label for role in roles[:5]]
                    },
                    'timestamp': datetime.utcnow().isoformat()
                })}\n\n"

                # Stage 4: Decision Point Identification (Placeholder)
                yield f"data: {json.dumps({
                    'stage': 'decision_identification',
                    'stage_number': 4,
                    'progress': 55,
                    'message': 'Identifying decision points from actions and questions...',
                    'timestamp': datetime.utcnow().isoformat()
                })}\n\n"

                yield f"data: {json.dumps({
                    'stage': 'decision_identification',
                    'stage_number': 4,
                    'progress': 60,
                    'message': f'Found {len(data.temporal_dynamics.actions)} actions (Stage 4 placeholder)',
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
