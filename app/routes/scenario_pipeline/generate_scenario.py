"""
Scenario Generation from Extracted Entities

Generates interactive teaching scenarios from fully-analyzed cases using
Server-Sent Events (SSE) for real-time progress streaming.

Follows the proven pattern from step3_enhanced.py (temporal dynamics extraction).
"""

from flask import Response, jsonify, current_app
import json
import logging
from datetime import datetime

from app.models import Document
from app.services.scenario_generation.orchestrator import ScenarioGenerationOrchestrator
from app.services.scenario_generation.scenario_enrichment_agent import ScenarioEnrichmentAgent
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

        # Map participants BEFORE generator (database operations)
        logger.info(f"[Scenario Gen] Mapping participants for case {case_id}")
        roles = data.get_entities_by_type('Role')
        if not roles:
            roles = data.get_entities_by_type('Roles')

        participant_result = orchestrator.participant_mapper.map_participants(
            roles,
            timeline_data=timeline.to_dict() if timeline else None
        )

        # Capture case title and content BEFORE save_to_database (which commits and detaches the case object)
        case_title = case.title
        case_content = case.content

        # Save participants to database
        saved_count = orchestrator.participant_mapper.save_to_database(
            case_id=case_id,
            result=participant_result,
            llm_model='claude-sonnet-4-5-20250929'
        )
        logger.info(f"[Scenario Gen] Saved {saved_count} participants to database")

        # Capture the Flask app instance while still in request context
        # (current_app is a proxy that requires context, so get the actual app object)
        app = current_app._get_current_object()

        def generate():
            """Generator for Server-Sent Events"""
            # Maintain Flask application context for database operations in generator
            with app.app_context():
                try:
                    logger.info(f"[Scenario Gen] Starting SSE stream for case {case_id}")

                    # Send initial event
                    yield f"data: {json.dumps({
                        'stage': 'init',
                        'stage_number': 0,
                        'progress': 0,
                        'message': 'Initializing scenario generation...',
                        'case_id': case_id,
                        'case_title': case_title,
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

                    # Stage 2b: Timeline Enrichment (NEW - LLM validation)
                    yield f"data: {json.dumps({
                        'stage': 'timeline_enrichment',
                        'stage_number': '2b',
                        'progress': 36,
                        'message': 'Enriching timeline with case-specific context...',
                        'timestamp': datetime.utcnow().isoformat()
                    })}\n\n"

                    # Initialize enrichment agent
                    from app.utils.llm_utils import get_llm_client
                    from app.services.scenario_generation.models import TimelineEntry
                    llm_client = get_llm_client()
                    enrichment_agent = ScenarioEnrichmentAgent(llm_client)

                    # Enrich timeline entries
                    enrichment_result = enrichment_agent.enrich_timeline(
                        case_id=case_id,
                        case_text=case_content,
                        timeline_entries=timeline.entries,
                        participants=participant_result.participants
                    )

                    # Convert enriched dictionaries back to TimelineEntry objects
                    timeline.entries = [
                        TimelineEntry(**entry_dict)
                        for entry_dict in enrichment_result['enriched_timeline']
                    ]

                    yield f"data: {json.dumps({
                        'stage': 'timeline_enrichment',
                        'stage_number': '2b',
                        'progress': 39,
                        'message': f'Timeline enriched: {len(enrichment_result["enriched_timeline"])} events with context',
                        'data': {
                            'validation_notes': enrichment_result.get('validation_notes', []),
                            'missing_events': len(enrichment_result.get('missing_events', []))
                        },
                        'timestamp': datetime.utcnow().isoformat()
                    })}\n\n"

                    # Stage 3: Participant Mapping (already complete before generator)
                    yield f"data: {json.dumps({
                        'stage': 'participant_mapping',
                        'stage_number': 3,
                        'progress': 40,
                        'message': 'Extracting character profiles from roles...',
                        'timestamp': datetime.utcnow().isoformat()
                    })}\n\n"
    
                    yield f"data: {json.dumps({
                        'stage': 'participant_mapping',
                        'stage_number': 3,
                        'progress': 42,
                        'message': f'Building profiles for {len(roles)} participants...',
                        'timestamp': datetime.utcnow().isoformat()
                    })}\n\n"
    
                    yield f"data: {json.dumps({
                        'stage': 'participant_mapping',
                        'stage_number': 3,
                        'progress': 45,
                        'message': 'Enhancing character arcs with LLM...',
                        'timestamp': datetime.utcnow().isoformat()
                    })}\n\n"
    
                    yield f"data: {json.dumps({
                        'stage': 'participant_mapping',
                        'stage_number': 3,
                        'progress': 48,
                        'message': 'Saving character profiles to database...',
                        'timestamp': datetime.utcnow().isoformat()
                    })}\n\n"
    
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
                            'has_analysis_notes': participant_result.analysis_notes is not None
                        },
                        'timestamp': datetime.utcnow().isoformat()
                    })}\n\n"
    
                    # Stage 4: Decision Point Identification + Institutional Rule Analysis
                    yield f"data: {json.dumps({
                        'stage': 'decision_identification',
                        'stage_number': 4,
                        'progress': 52,
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
    
                    yield f"data: {json.dumps({
                        'stage': 'decision_identification',
                        'stage_number': 4,
                        'progress': 54,
                        'message': 'Loading institutional analysis from Step 4 (Part D)...',
                        'timestamp': datetime.utcnow().isoformat()
                    })}\n\n"
    
                    # REFACTORED: Reference Step 4 analysis from database (no re-analysis)
                    decision_result = orchestrator.decision_identifier.identify_decisions_from_step4_analysis(
                        case_id=case_id,
                        actions=actions_entities,
                        questions=questions_entities,
                        timeline_data=timeline.to_dict() if timeline else None,
                        participants=participant_result.participants if participant_result else None,
                        synthesis_data=data.synthesis_data
                    )
    
                    yield f"data: {json.dumps({
                        'stage': 'decision_identification',
                        'stage_number': 4,
                        'progress': 57,
                        'message': 'Enriching decisions with institutional analysis (Part D)...',
                        'timestamp': datetime.utcnow().isoformat()
                    })}\n\n"
    
                    yield f"data: {json.dumps({
                        'stage': 'decision_identification',
                        'stage_number': 4,
                        'progress': 59,
                        'message': 'Enriching decisions with transformation classification (Part F)...',
                        'timestamp': datetime.utcnow().isoformat()
                    })}\n\n"
    
                    decision_summary = decision_result.to_dict()
                    yield f"data: {json.dumps({
                        'stage': 'decision_identification',
                        'stage_number': 4,
                        'progress': 60,
                        'message': f'Identified {decision_result.total_decisions} decision points with institutional analysis',
                        'data': decision_summary,
                        'details': {
                            'decisions_analyzed': decision_result.total_decisions,
                            'has_institutional_analysis': any(d.institutional_rule_analysis for d in decision_result.decision_points),
                            'has_transformation_analysis': any(d.transformation_analysis for d in decision_result.decision_points)
                        },
                        'timestamp': datetime.utcnow().isoformat()
                    })}\n\n"
    
                    # Stage 5: Causal Chain Integration - Reference Part E (Action-Rule Mapping)
                    yield f"data: {json.dumps({
                        'stage': 'causal_integration',
                        'stage_number': 5,
                        'progress': 65,
                        'message': 'Loading action-rule mapping from Step 4 (Part E)...',
                        'timestamp': datetime.utcnow().isoformat()
                    })}\n\n"
    
                    # Load Part E from database
                    from app.models import db
                    from sqlalchemy import text as sql_text
    
                    action_mapping_query = sql_text("""
                        SELECT
                            actions_taken,
                            actions_not_taken,
                            transformation_points,
                            rule_shifts
                        FROM case_action_mapping
                        WHERE case_id = :case_id
                    """)
    
                    action_mapping_result = db.session.execute(action_mapping_query, {'case_id': case_id}).fetchone()
    
                    if action_mapping_result:
                        yield f"data: {json.dumps({
                            'stage': 'causal_integration',
                            'stage_number': 5,
                            'progress': 70,
                            'message': f'Causal chains loaded: {len(action_mapping_result.actions_taken or [])} actions taken, {len(action_mapping_result.transformation_points or [])} transformation points',
                            'data': {
                                'actions_taken': len(action_mapping_result.actions_taken or []),
                                'actions_not_taken': len(action_mapping_result.actions_not_taken or []),
                                'transformation_points': len(action_mapping_result.transformation_points or []),
                                'rule_shifts': len(action_mapping_result.rule_shifts or [])
                            },
                            'timestamp': datetime.utcnow().isoformat()
                        })}\n\n"
                    else:
                        yield f"data: {json.dumps({
                            'stage': 'causal_integration',
                            'stage_number': 5,
                            'progress': 70,
                            'message': 'No Part E analysis found (run Step 4 first)',
                            'timestamp': datetime.utcnow().isoformat()
                        })}\n\n"
    
                    # Stage 6: Normative Framework - Reference Part F (Transformation Classification)
                    yield f"data: {json.dumps({
                        'stage': 'normative_integration',
                        'stage_number': 6,
                        'progress': 75,
                        'message': 'Loading transformation classification from Step 4 (Part F)...',
                        'timestamp': datetime.utcnow().isoformat()
                    })}\n\n"
    
                    transformation_query = sql_text("""
                        SELECT
                            transformation_type,
                            confidence,
                            symbolic_significance,
                            pattern_name
                        FROM case_transformation
                        WHERE case_id = :case_id
                    """)
    
                    transformation_result = db.session.execute(transformation_query, {'case_id': case_id}).fetchone()
    
                    if transformation_result:
                        yield f"data: {json.dumps({
                            'stage': 'normative_integration',
                            'stage_number': 6,
                            'progress': 80,
                            'message': f'Normative framework integrated: {transformation_result.transformation_type} transformation (confidence: {transformation_result.confidence:.2f})',
                            'data': {
                                'transformation_type': transformation_result.transformation_type,
                                'confidence': transformation_result.confidence,
                                'pattern_name': transformation_result.pattern_name,
                                'symbolic_significance': transformation_result.symbolic_significance[:100] + '...' if len(transformation_result.symbolic_significance or '') > 100 else transformation_result.symbolic_significance
                            },
                            'timestamp': datetime.utcnow().isoformat()
                        })}\n\n"
                    else:
                        yield f"data: {json.dumps({
                            'stage': 'normative_integration',
                            'stage_number': 6,
                            'progress': 80,
                            'message': 'No Part F analysis found (run Step 4 first)',
                            'timestamp': datetime.utcnow().isoformat()
                        })}\n\n"
    
                    # Stage 7: Scenario Assembly - IMPLEMENTED
                    yield f"data: {json.dumps({
                        'stage': 'scenario_assembly',
                        'stage_number': 7,
                        'progress': 82,
                        'message': 'Assembling complete scenario from all components...',
                        'timestamp': datetime.utcnow().isoformat()
                    })}\n\n"

                    from app.services.scenario_generation.scenario_assembler import ScenarioAssembler
                    assembler = ScenarioAssembler()

                    # Collect components for assembly
                    yield f"data: {json.dumps({
                        'stage': 'scenario_assembly',
                        'stage_number': 7,
                        'progress': 84,
                        'message': 'Combining timeline, participants, decisions, and analytical frameworks...',
                        'timestamp': datetime.utcnow().isoformat()
                    })}\n\n"

                    # Convert database results to dicts
                    action_mapping_dict = None
                    if action_mapping_result:
                        action_mapping_dict = {
                            'actions_taken': action_mapping_result.actions_taken,
                            'actions_not_taken': action_mapping_result.actions_not_taken,
                            'transformation_points': action_mapping_result.transformation_points,
                            'rule_shifts': action_mapping_result.rule_shifts
                        }

                    transformation_dict = None
                    if transformation_result:
                        transformation_dict = {
                            'transformation_type': transformation_result.transformation_type,
                            'confidence': transformation_result.confidence,
                            'symbolic_significance': transformation_result.symbolic_significance,
                            'pattern_name': transformation_result.pattern_name
                        }

                    assembled_scenario = assembler.assemble_scenario(
                        case_id=case_id,
                        case_title=case_title,
                        timeline_result=timeline,
                        participant_result=participant_result,
                        decision_result=decision_result,
                        action_mapping=action_mapping_dict,
                        transformation=transformation_dict,
                        entity_summary={'total': entity_count}
                    )

                    yield f"data: {json.dumps({
                        'stage': 'scenario_assembly',
                        'stage_number': 7,
                        'progress': 87,
                        'message': f'Scenario assembled: {assembled_scenario.metadata.total_components} total components',
                        'data': {
                            'total_timepoints': assembled_scenario.metadata.total_timepoints,
                            'total_participants': assembled_scenario.metadata.total_participants,
                            'total_decisions': assembled_scenario.metadata.total_decisions,
                            'completeness_score': assembled_scenario.scenario_data["assembly_info"]["completeness_score"],
                            'stages_included': assembled_scenario.scenario_data["assembly_info"]["stages_included"]
                        },
                        'timestamp': datetime.utcnow().isoformat()
                    })}\n\n"

                    # Save to database (primary storage)
                    yield f"data: {json.dumps({
                        'stage': 'scenario_assembly',
                        'stage_number': 7,
                        'progress': 88,
                        'message': 'Saving scenario to database...',
                        'timestamp': datetime.utcnow().isoformat()
                    })}\n\n"

                    db_saved = assembler.save_to_database(assembled_scenario)

                    if not db_saved:
                        yield f"data: {json.dumps({
                            'stage': 'error',
                            'message': 'Failed to save scenario to database',
                            'timestamp': datetime.utcnow().isoformat()
                        })}\n\n"
                        return

                    yield f"data: {json.dumps({
                        'stage': 'scenario_assembly',
                        'stage_number': 7,
                        'progress': 90,
                        'message': 'Scenario saved to database',
                        'timestamp': datetime.utcnow().isoformat()
                    })}\n\n"

                    # Completion - Stages 8-9 implemented separately
                    # Stage 8: Dynamic viewer (separate route)
                    # Stage 9: Validation (integrated into viewer)
                    result = {
                        'success': True,
                        'case_id': case_id,
                        'entity_count': entity_count,
                        'total_timepoints': assembled_scenario.metadata.total_timepoints,
                        'total_participants': assembled_scenario.metadata.total_participants,
                        'total_decisions': assembled_scenario.metadata.total_decisions,
                        'completeness_score': assembled_scenario.scenario_data['assembly_info']['completeness_score'],
                        'stages_included': assembled_scenario.scenario_data['assembly_info']['stages_included'],
                        'stages_completed': 7,
                        'status': 'complete',
                        'message': 'Scenario assembly complete. Click "View Assembled Scenario" to see the interactive viewer.',
                        'viewer_url': f'/scenario_pipeline/case/{case_id}/scenario'
                    }

                    yield f"data: {json.dumps({
                        'stage': 'complete',
                        'progress': 100,
                        'message': 'Scenario generation complete! Click "View Assembled Scenario" below.',
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
