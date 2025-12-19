"""
Step 4 Complete Synthesis - Streaming Endpoint

Runs all 4 phases of case synthesis with SSE streaming:
- Phase 2: Analytical Extraction (provisions, Q&C, transformation, rich analysis)
- Phase 3: Decision Point Synthesis (E1-E3 + LLM refinement)
- Phase 4: Narrative Construction (timeline, scenario seeds, insights)

Returns progress updates via Server-Sent Events.
Uses CaseSynthesizer service for actual synthesis logic.
"""

import json
import logging
import uuid
from datetime import datetime
from flask import Response, stream_with_context

from app.models import Document, ExtractionPrompt, db
from app.utils.environment_auth import auth_required_for_llm

logger = logging.getLogger(__name__)


def register_complete_synthesis_routes(bp, build_entity_foundation, load_canonical_points,
                                       load_conclusions, get_transformation_type, load_causal_links):
    """
    Register complete synthesis streaming route.

    Args:
        bp: Flask Blueprint
        build_entity_foundation: Function to build EntityFoundation
        load_canonical_points: Function to load Phase 3 decision points
        load_conclusions: Function to load conclusions
        get_transformation_type: Function to get transformation classification
        load_causal_links: Function to load causal-normative links
    """

    @bp.route('/case/<int:case_id>/synthesize_complete_stream', methods=['POST'])
    @auth_required_for_llm
    def synthesize_complete_streaming(case_id):
        """
        Execute complete four-phase synthesis with SSE streaming.

        Uses CaseSynthesizer service methods internally but streams
        progress updates via SSE for real-time UI feedback.

        Phases:
        1. Entity Foundation - verify entities from Passes 1-3
        2. Analytical Extraction - provisions, Q&C, transformation, rich analysis
        3. Decision Point Synthesis - E1-E3 composition + LLM refinement
        4. Narrative Construction - timeline and scenario seeds
        """

        def sse_msg(data):
            return f"data: {json.dumps(data)}\n\n"

        def generate():
            try:
                from app.services.case_synthesizer import CaseSynthesizer
                from app.services.narrative import construct_phase4_narrative
                from app.services.precedent import update_precedent_features_from_phase4
                from app.services.decision_point_synthesizer import synthesize_decision_points

                case = Document.query.get_or_404(case_id)
                synthesizer = CaseSynthesizer()

                # =====================================================================
                # START
                # =====================================================================
                yield sse_msg({
                    'stage': 'START',
                    'progress': 0,
                    'messages': ['Starting Complete Four-Phase Synthesis...']
                })

                # =====================================================================
                # PHASE 1: Entity Foundation (verification only)
                # =====================================================================
                yield sse_msg({
                    'stage': 'PHASE_1_START',
                    'progress': 2,
                    'messages': ['Phase 1: Verifying Entity Foundation (Passes 1-3)...']
                })

                foundation = synthesizer._build_entity_foundation(case_id)
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
                    'stage': 'PHASE_1_COMPLETE',
                    'progress': 5,
                    'messages': [f'Phase 1 complete: {entity_count} entities from Passes 1-3'],
                    'result': {'entity_count': entity_count}
                })

                # Update phase indicator
                yield sse_msg({
                    'stage': 'PHASE_2_INDICATOR',
                    'progress': 5,
                    'messages': ['Activating Phase 2...']
                })

                # =====================================================================
                # PHASE 2A: Code Provisions
                # =====================================================================
                yield sse_msg({
                    'stage': 'PART_A_START',
                    'progress': 8,
                    'messages': ['Phase 2A: Loading Code Provisions...']
                })

                provisions = synthesizer._load_provisions(case_id)

                yield sse_msg({
                    'stage': 'PART_A_COMPLETE',
                    'progress': 15,
                    'messages': [f'Loaded {len(provisions)} code provisions'],
                    'result': {'provision_count': len(provisions)}
                })

                # =====================================================================
                # PHASE 2B: Questions & Conclusions
                # =====================================================================
                yield sse_msg({
                    'stage': 'PART_B_START',
                    'progress': 18,
                    'messages': ['Phase 2B: Loading Questions & Conclusions...']
                })

                questions, conclusions = synthesizer._load_qc(case_id)

                yield sse_msg({
                    'stage': 'PART_B_COMPLETE',
                    'progress': 28,
                    'messages': [
                        f'Loaded {len(questions)} ethical questions',
                        f'Loaded {len(conclusions)} board conclusions'
                    ],
                    'result': {
                        'question_count': len(questions),
                        'conclusion_count': len(conclusions)
                    }
                })

                # =====================================================================
                # PHASE 2C: Transformation Classification
                # =====================================================================
                yield sse_msg({
                    'stage': 'PART_C_START',
                    'progress': 30,
                    'messages': ['Phase 2C: Loading Transformation Type...']
                })

                transformation_type = synthesizer._get_transformation_type(case_id)

                yield sse_msg({
                    'stage': 'TRANSFORMATION_COMPLETE',
                    'progress': 35,
                    'messages': [f'Transformation type: {transformation_type}'],
                    'result': {'transformation_type': transformation_type}
                })

                # =====================================================================
                # PHASE 2D: Rich Analysis
                # =====================================================================
                yield sse_msg({
                    'stage': 'RICH_ANALYSIS_START',
                    'progress': 38,
                    'messages': ['Phase 2D: Running Rich Analysis...']
                })

                yield sse_msg({
                    'stage': 'RICH_ANALYSIS_CAUSAL',
                    'progress': 42,
                    'messages': ['Analyzing causal-normative links...']
                })

                yield sse_msg({
                    'stage': 'RICH_ANALYSIS_QUESTIONS',
                    'progress': 46,
                    'messages': ['Analyzing question emergence...']
                })

                yield sse_msg({
                    'stage': 'RICH_ANALYSIS_RESOLUTION',
                    'progress': 50,
                    'messages': ['Analyzing resolution patterns...']
                })

                causal_links, question_emergence, resolution_patterns, _ = synthesizer._run_rich_analysis(
                    case_id, foundation, provisions, questions, conclusions
                )

                yield sse_msg({
                    'stage': 'RICH_ANALYSIS_COMPLETE',
                    'progress': 55,
                    'messages': [
                        f'Rich analysis complete:',
                        f'  - {len(causal_links)} causal-normative links',
                        f'  - {len(question_emergence)} question emergence patterns',
                        f'  - {len(resolution_patterns)} resolution patterns'
                    ],
                    'result': {
                        'causal_links_count': len(causal_links),
                        'question_emergence_count': len(question_emergence),
                        'resolution_patterns_count': len(resolution_patterns)
                    }
                })

                # Update phase indicator
                yield sse_msg({
                    'stage': 'PHASE_3_INDICATOR',
                    'progress': 55,
                    'messages': ['Activating Phase 3...']
                })

                # =====================================================================
                # PHASE 3: Decision Point Synthesis
                # =====================================================================
                yield sse_msg({
                    'stage': 'DECISION_SYNTHESIS_START',
                    'progress': 58,
                    'messages': ['Phase 3: Synthesizing Decision Points (E1-E3 + LLM)...']
                })

                yield sse_msg({
                    'stage': 'DECISION_E1',
                    'progress': 62,
                    'messages': ['E1: Analyzing obligation coverage...']
                })

                yield sse_msg({
                    'stage': 'DECISION_E2',
                    'progress': 66,
                    'messages': ['E2: Mapping actions to options with moral intensity...']
                })

                yield sse_msg({
                    'stage': 'DECISION_E3',
                    'progress': 70,
                    'messages': ['E3: Composing decision points from entities...']
                })

                # Convert dataclass lists to dicts for the synthesizer
                qe_dicts = [qe.to_dict() for qe in question_emergence]
                rp_dicts = [rp.to_dict() for rp in resolution_patterns]

                phase3_result = synthesize_decision_points(
                    case_id=case_id,
                    questions=questions,
                    conclusions=conclusions,
                    question_emergence=qe_dicts,
                    resolution_patterns=rp_dicts,
                    domain=synthesizer.domain.name,
                    skip_llm=False
                )

                canonical_points = phase3_result.canonical_decision_points

                yield sse_msg({
                    'stage': 'DECISION_SYNTHESIS_COMPLETE',
                    'progress': 75,
                    'messages': [
                        f'Phase 3 complete:',
                        f'  - {len(canonical_points)} canonical decision points',
                        f'  - LLM refinement applied'
                    ],
                    'result': {
                        'decision_point_count': len(canonical_points)
                    }
                })

                # Update phase indicator
                yield sse_msg({
                    'stage': 'PHASE_4_INDICATOR',
                    'progress': 75,
                    'messages': ['Activating Phase 4...']
                })

                # =====================================================================
                # PHASE 4: Narrative Construction
                # =====================================================================
                yield sse_msg({
                    'stage': 'NARRATIVE_START',
                    'progress': 78,
                    'messages': ['Phase 4: Constructing Narrative Elements...']
                })

                # Get causal links for narrative
                causal_links_for_narrative = load_causal_links(case_id)

                yield sse_msg({
                    'stage': 'NARRATIVE_ELEMENTS',
                    'progress': 82,
                    'messages': ['Stage 4.1: Extracting narrative elements (characters, events, conflicts)...']
                })

                yield sse_msg({
                    'stage': 'NARRATIVE_TIMELINE',
                    'progress': 86,
                    'messages': ['Stage 4.2: Constructing entity-grounded timeline (Event Calculus)...']
                })

                yield sse_msg({
                    'stage': 'NARRATIVE_SEEDS',
                    'progress': 90,
                    'messages': ['Stage 4.3: Generating scenario seeds for Step 5...']
                })

                yield sse_msg({
                    'stage': 'NARRATIVE_INSIGHTS',
                    'progress': 94,
                    'messages': ['Stage 4.4: Deriving insights and patterns...']
                })

                # Run full Phase 4 pipeline
                phase4_result = construct_phase4_narrative(
                    case_id=case_id,
                    foundation=foundation,
                    canonical_points=canonical_points,
                    conclusions=conclusions,
                    transformation_type=transformation_type,
                    causal_normative_links=causal_links_for_narrative,
                    use_llm=True
                )

                # Save Phase 4 extraction prompt for provenance
                session_id = str(uuid.uuid4())
                extraction_prompt = ExtractionPrompt(
                    case_id=case_id,
                    concept_type='phase4_narrative',
                    step_number=4,
                    section_type='synthesis',
                    prompt_text=f"Complete Synthesis - Phase 4 Narrative Construction",
                    llm_model='claude-sonnet-4-20250514',
                    extraction_session_id=session_id,
                    raw_response=json.dumps(phase4_result.to_dict()),
                    results_summary=json.dumps(phase4_result.summary())
                )
                db.session.add(extraction_prompt)
                db.session.commit()

                # Update precedent features
                try:
                    update_precedent_features_from_phase4(
                        case_id=case_id,
                        narrative_result=phase4_result,
                        transformation_type=transformation_type
                    )
                except Exception as e:
                    logger.warning(f"Failed to update precedent features: {e}")

                yield sse_msg({
                    'stage': 'NARRATIVE_COMPLETE',
                    'progress': 98,
                    'messages': [
                        f'Phase 4 complete:',
                        f'  - {len(phase4_result.narrative_elements.characters)} characters',
                        f'  - {len(phase4_result.timeline.events)} timeline events',
                        f'  - {len(phase4_result.scenario_seeds.branches)} scenario branches'
                    ],
                    'result': {
                        'characters_count': len(phase4_result.narrative_elements.characters),
                        'events_count': len(phase4_result.timeline.events),
                        'branches_count': len(phase4_result.scenario_seeds.branches)
                    }
                })

                # =====================================================================
                # COMPLETE
                # =====================================================================
                yield sse_msg({
                    'stage': 'COMPLETE',
                    'progress': 100,
                    'messages': [
                        'Four-Phase Synthesis Complete!',
                        f'Ready for Step 5: Scenario Exploration'
                    ],
                    'result': {
                        'provisions': len(provisions),
                        'questions': len(questions),
                        'conclusions': len(conclusions),
                        'transformation_type': transformation_type,
                        'decision_points': len(canonical_points),
                        'characters': len(phase4_result.narrative_elements.characters),
                        'timeline_events': len(phase4_result.timeline.events)
                    }
                })

            except Exception as e:
                logger.error(f"Complete synthesis failed for case {case_id}: {e}")
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
                'X-Accel-Buffering': 'no'
            }
        )

    return {
        'synthesize_complete_streaming': synthesize_complete_streaming
    }
