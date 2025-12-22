"""
Step 4 Phase 4: Narrative Construction Routes

Handles narrative construction with entity-grounded elements:
- Individual synthesis (non-streaming)
- Streaming synthesis with real-time progress through 4.1-4.4 stages

Based on: Berreby et al. (2017) - Declarative Modular Framework for Ethical Reasoning
"""

import json
import logging
import uuid
from datetime import datetime
from flask import jsonify, Response, stream_with_context

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.utils.llm_utils import get_llm_client
from app.utils.environment_auth import auth_required_for_llm

# Phase 4 Narrative Services
from app.services.narrative import (
    construct_phase4_narrative,
    extract_narrative_elements,
    construct_timeline,
    generate_scenario_seeds,
    derive_insights,
    Phase4NarrativeResult
)

# Precedent Features Connector
from app.services.precedent import update_precedent_features_from_phase4

logger = logging.getLogger(__name__)


def register_phase4_routes(bp, build_entity_foundation, load_canonical_points, load_conclusions, get_transformation_type, load_causal_links):
    """Register Phase 4 narrative construction routes on the blueprint.

    Args:
        bp: The Flask Blueprint to register routes on
        build_entity_foundation: Function to build EntityFoundation
        load_canonical_points: Function to load Phase 3 decision points
        load_conclusions: Function to load conclusions
        get_transformation_type: Function to get transformation classification
        load_causal_links: Function to load causal-normative links
    """

    @bp.route('/case/<int:case_id>/construct_phase4', methods=['POST'])
    @auth_required_for_llm
    def construct_phase4_individual(case_id):
        """
        Run Phase 4 narrative construction (non-streaming).
        Returns complete narrative elements, timeline, scenario seeds, and insights.
        """
        try:
            case = Document.query.get_or_404(case_id)

            # Build inputs
            foundation = build_entity_foundation(case_id)
            canonical_points = load_canonical_points(case_id)
            conclusions = load_conclusions(case_id)
            transformation_type = get_transformation_type(case_id)
            causal_links = load_causal_links(case_id)

            if not foundation or foundation.summary()['total'] == 0:
                return jsonify({
                    'success': False,
                    'error': 'No entities found - run Passes 1-3 first'
                }), 400

            # Run Phase 4 pipeline
            result = construct_phase4_narrative(
                case_id=case_id,
                foundation=foundation,
                canonical_points=canonical_points,
                conclusions=conclusions,
                transformation_type=transformation_type,
                causal_normative_links=causal_links,
                use_llm=True
            )

            # Save extraction prompt for provenance
            # raw_response gets full data for Step 5, results_summary gets counts for display
            session_id = str(uuid.uuid4())
            extraction_prompt = ExtractionPrompt(
                case_id=case_id,
                concept_type='phase4_narrative',
                step_number=4,
                section_type='synthesis',
                prompt_text=f"Phase 4 Narrative Construction - {len(result.stages_completed)} stages",
                llm_model='claude-sonnet-4-20250514',
                extraction_session_id=session_id,
                raw_response=json.dumps(result.to_dict()),
                results_summary=json.dumps(result.summary())
            )
            db.session.add(extraction_prompt)
            db.session.commit()

            # Update precedent features with Phase 4 results
            try:
                update_precedent_features_from_phase4(
                    case_id=case_id,
                    narrative_result=result,
                    transformation_type=transformation_type
                )
                logger.info(f"Updated precedent features from Phase 4 for case {case_id}")
            except Exception as e:
                logger.warning(f"Failed to update precedent features from Phase 4: {e}")

            return jsonify({
                'success': True,
                'summary': result.summary(),
                'narrative_elements': result.narrative_elements.summary(),
                'timeline': {
                    'events_count': len(result.timeline.events),
                    'event_trace_preview': result.timeline.to_event_trace()[:500]
                },
                'scenario_seeds': result.scenario_seeds.summary(),
                'insights': result.insights.summary(),
                'stages_completed': result.stages_completed
            })

        except Exception as e:
            logger.error(f"Phase 4 narrative construction failed for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/construct_phase4_stream', methods=['POST'])
    @auth_required_for_llm
    def construct_phase4_streaming(case_id):
        """
        Run Phase 4 narrative construction with SSE streaming.
        Shows real-time progress through 4.1, 4.2, 4.3, 4.4 stages.
        """
        logger.info(f"[Phase 4] construct_phase4_streaming called for case {case_id}")

        def sse_msg(data):
            logger.debug(f"[Phase 4] SSE: {data.get('stage', 'unknown')} - {data.get('progress', 0)}%")
            return f"data: {json.dumps(data)}\n\n"

        def generate():
            try:
                logger.info(f"[Phase 4] Starting generator for case {case_id}")
                case = Document.query.get_or_404(case_id)
                session_id = str(uuid.uuid4())

                yield sse_msg({
                    'stage': 'START',
                    'progress': 0,
                    'messages': ['Starting Phase 4: Narrative Construction...']
                })

                # Load foundation data
                yield sse_msg({
                    'stage': 'LOADING_FOUNDATION',
                    'progress': 5,
                    'messages': ['Loading entity foundation and Phase 2-3 data...']
                })

                foundation = build_entity_foundation(case_id)
                canonical_points = load_canonical_points(case_id)
                conclusions = load_conclusions(case_id)
                transformation_type = get_transformation_type(case_id)
                causal_links = load_causal_links(case_id)

                entity_count = foundation.summary()['total'] if foundation else 0
                if entity_count == 0:
                    yield sse_msg({
                        'stage': 'ERROR',
                        'progress': 100,
                        'messages': ['No entities found - run Passes 1-3 first'],
                        'error': True
                    })
                    return

                yield sse_msg({
                    'stage': 'FOUNDATION_LOADED',
                    'progress': 10,
                    'messages': [
                        f'Loaded {entity_count} entities from Passes 1-3',
                        f'{len(canonical_points)} canonical decision points',
                        f'{len(conclusions)} conclusions'
                    ]
                })

                # Stage 4.1: Narrative Element Extraction
                yield sse_msg({
                    'stage': 'STAGE_4_1',
                    'progress': 15,
                    'messages': ['Stage 4.1: Extracting narrative elements (characters, setting, events, conflicts)...']
                })

                narrative_elements = extract_narrative_elements(
                    case_id=case_id,
                    foundation=foundation,
                    canonical_points=canonical_points,
                    conclusions=conclusions,
                    transformation_type=transformation_type,
                    use_llm=True
                )

                yield sse_msg({
                    'stage': 'STAGE_4_1_DONE',
                    'progress': 30,
                    'messages': [
                        f'Extracted {len(narrative_elements.characters)} characters',
                        f'{len(narrative_elements.events)} events',
                        f'{len(narrative_elements.conflicts)} conflicts',
                        f'{len(narrative_elements.decision_moments)} decision moments'
                    ],
                    'stage_4_1_result': narrative_elements.summary()
                })

                # Stage 4.2: Timeline Construction
                yield sse_msg({
                    'stage': 'STAGE_4_2',
                    'progress': 40,
                    'messages': ['Stage 4.2: Constructing entity-grounded timeline (Event Calculus)...']
                })

                timeline = construct_timeline(
                    case_id=case_id,
                    narrative_elements=narrative_elements,
                    foundation=foundation,
                    causal_normative_links=causal_links,
                    use_llm=True
                )

                yield sse_msg({
                    'stage': 'STAGE_4_2_DONE',
                    'progress': 55,
                    'messages': [
                        f'Constructed timeline with {len(timeline.events)} events',
                        f'{len(timeline.initial_fluents)} initial fluents',
                        f'{len(timeline.causal_links)} causal links',
                        f'{len(timeline.decision_points)} decision point markers'
                    ],
                    'stage_4_2_result': timeline.summary()
                })

                # Stage 4.3: Scenario Seed Generation
                yield sse_msg({
                    'stage': 'STAGE_4_3',
                    'progress': 65,
                    'messages': ['Stage 4.3: Generating scenario seeds for Step 5...']
                })

                scenario_seeds = generate_scenario_seeds(
                    case_id=case_id,
                    narrative_elements=narrative_elements,
                    timeline=timeline,
                    transformation_type=transformation_type,
                    use_llm=True
                )

                yield sse_msg({
                    'stage': 'STAGE_4_3_DONE',
                    'progress': 80,
                    'messages': [
                        f'Generated {len(scenario_seeds.branches)} scenario branches',
                        f'{sum(len(b.options) for b in scenario_seeds.branches)} total options',
                        f'Protagonist: {scenario_seeds.protagonist_label}'
                    ],
                    'stage_4_3_result': scenario_seeds.summary()
                })

                # Stage 4.4: Insight Derivation
                yield sse_msg({
                    'stage': 'STAGE_4_4',
                    'progress': 85,
                    'messages': ['Stage 4.4: Deriving insights and patterns...']
                })

                insights = derive_insights(
                    case_id=case_id,
                    narrative_elements=narrative_elements,
                    timeline=timeline,
                    scenario_seeds=scenario_seeds,
                    transformation_type=transformation_type,
                    use_llm=True
                )

                yield sse_msg({
                    'stage': 'STAGE_4_4_DONE',
                    'progress': 95,
                    'messages': [
                        f'Derived {len(insights.principles_applied)} principles applied',
                        f'{len(insights.patterns)} patterns identified',
                        f'{len(insights.key_takeaways)} key takeaways'
                    ],
                    'stage_4_4_result': insights.summary()
                })

                # Build complete result
                result = Phase4NarrativeResult(
                    case_id=case_id,
                    narrative_elements=narrative_elements,
                    timeline=timeline,
                    scenario_seeds=scenario_seeds,
                    insights=insights,
                    stages_completed=['4.1_narrative_elements', '4.2_timeline', '4.3_scenario_seeds', '4.4_insights'],
                    llm_enhanced=True
                )

                # Save provenance
                # raw_response gets full data for Step 5, results_summary gets counts for display
                try:
                    extraction_prompt = ExtractionPrompt(
                        case_id=case_id,
                        concept_type='phase4_narrative',
                        step_number=4,
                        section_type='synthesis',
                        prompt_text=f"Phase 4 Narrative Construction - streaming",
                        llm_model='claude-sonnet-4-20250514',
                        extraction_session_id=session_id,
                        raw_response=json.dumps(result.to_dict()),
                        results_summary=json.dumps(result.summary())
                    )
                    db.session.add(extraction_prompt)
                    db.session.commit()
                except Exception as e:
                    logger.warning(f"Failed to save Phase 4 provenance: {e}")

                # Update precedent features with Phase 4 results
                try:
                    update_precedent_features_from_phase4(
                        case_id=case_id,
                        narrative_result=result,
                        transformation_type=transformation_type
                    )
                    logger.info(f"Updated precedent features from Phase 4 for case {case_id}")
                except Exception as e:
                    logger.warning(f"Failed to update precedent features from Phase 4: {e}")

                # Final result
                yield sse_msg({
                    'stage': 'COMPLETE',
                    'progress': 100,
                    'messages': ['Phase 4 narrative construction complete!'],
                    'result': {
                        'summary': result.summary(),
                        'timeline_preview': timeline.to_event_trace()[:1000],
                        'opening_context': scenario_seeds.opening_context,
                        'key_takeaways': insights.key_takeaways[:3]
                    }
                })

            except Exception as e:
                logger.error(f"Phase 4 streaming failed for case {case_id}: {e}")
                import traceback
                traceback.print_exc()
                yield sse_msg({
                    'stage': 'ERROR',
                    'progress': 100,
                    'messages': [f'Error: {str(e)}'],
                    'error': True
                })

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )

    @bp.route('/case/<int:case_id>/get_phase4_data')
    def get_phase4_data(case_id):
        """
        Get saved Phase 4 narrative construction results.
        """
        try:
            # Get latest Phase 4 prompt
            prompt = ExtractionPrompt.query.filter_by(
                case_id=case_id,
                concept_type='phase4_narrative'
            ).order_by(ExtractionPrompt.created_at.desc()).first()

            if not prompt or not prompt.raw_response:
                return jsonify({
                    'has_phase4': False,
                    'message': 'No Phase 4 data found - run narrative construction first'
                })

            # Parse full result from raw_response
            result = json.loads(prompt.raw_response) if prompt.raw_response else {}

            return jsonify({
                'has_phase4': True,
                'session_id': prompt.extraction_session_id,
                'timestamp': prompt.created_at.isoformat() if prompt.created_at else None,
                'result': result
            })

        except Exception as e:
            logger.error(f"Error getting Phase 4 data for case {case_id}: {e}")
            return jsonify({
                'has_phase4': False,
                'error': str(e)
            }), 500

    return {
        'construct_phase4_individual': construct_phase4_individual,
        'construct_phase4_streaming': construct_phase4_streaming,
        'get_phase4_data': get_phase4_data
    }
