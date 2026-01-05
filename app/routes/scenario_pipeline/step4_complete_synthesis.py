"""
Step 4 Complete Synthesis - Streaming Endpoint

Runs all 4 phases of case synthesis with SSE streaming:
- Phase 2: Analytical Extraction (provisions, Q&C, transformation, rich analysis)
- Phase 3: Decision Point Synthesis (E1-E3 + LLM refinement)
- Phase 4: Narrative Construction (timeline, scenario seeds, insights)

Returns progress updates via Server-Sent Events.
Uses the unified synthesis module for extraction.
"""

import json
import logging
import uuid
from datetime import datetime
from flask import Response, stream_with_context

from app.models import Document, ExtractionPrompt, db
from app.utils.environment_auth import auth_required_for_llm
from app.utils.llm_utils import get_llm_client

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
                from app.services.synthesis import Phase2Extractor

                case = Document.query.get_or_404(case_id)
                synthesizer = CaseSynthesizer()
                llm_client = get_llm_client()

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

                # =====================================================================
                # PHASE 2: Analytical Extraction using unified extractor
                # =====================================================================
                yield sse_msg({
                    'stage': 'PHASE_2_INDICATOR',
                    'progress': 5,
                    'messages': ['Activating Phase 2 Analytical Extraction...']
                })

                # Use the unified Phase2Extractor which matches the individual SSE endpoints
                phase2_extractor = Phase2Extractor(case_id, llm_client)

                # Forward all Phase 2 events to the client
                phase2_result = None
                for event in phase2_extractor.extract_streaming():
                    # Scale progress: Phase 2 runs from 5% to 55%
                    scaled_progress = 5 + int(event.progress * 0.50)

                    yield sse_msg({
                        'stage': f'PHASE_2_{event.stage}',
                        'progress': scaled_progress,
                        'messages': event.messages,
                        'result': event.result if event.result else None
                    })

                    # Check for error
                    if event.error:
                        yield sse_msg({
                            'stage': 'ERROR',
                            'progress': 100,
                            'messages': event.messages,
                            'error': True
                        })
                        return

                # Get final Phase 2 result
                phase2_result = phase2_extractor._result

                # Extract data from Phase 2 result for use in later phases
                provisions = phase2_result.provisions
                questions = phase2_result.questions
                conclusions = phase2_result.conclusions
                transformation_type = phase2_result.transformation_type
                causal_links = phase2_result.causal_links
                question_emergence = phase2_result.question_emergence
                resolution_patterns = phase2_result.resolution_patterns

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

                # Question emergence and resolution patterns are already dicts from Phase2Extractor
                # No conversion needed

                phase3_result = synthesize_decision_points(
                    case_id=case_id,
                    questions=questions,
                    conclusions=conclusions,
                    question_emergence=question_emergence,
                    resolution_patterns=resolution_patterns,
                    domain=synthesizer.domain.name,
                    skip_llm=False
                )

                canonical_points = phase3_result.canonical_decision_points

                # Save Phase 3 ExtractionPrompt for UI display (always save, even with 0 candidates)
                try:
                    if phase3_result.llm_prompt:
                        prompt_text = phase3_result.llm_prompt[:10000]
                        raw_response = phase3_result.llm_response[:10000] if phase3_result.llm_response else ''
                    else:
                        # No LLM output (E1-E3 found 0 AND LLM fallback didn't produce results)
                        prompt_text = f'Phase 3 Decision Point Synthesis (E1-E3 Algorithmic Composition)\n\nE1-E3 Algorithm found 0 matching candidates.\nLLM fallback using causal_normative_links was attempted but produced no results.'
                        raw_response = f'Phase 3 Result:\n- Algorithmic candidates: 0\n- Canonical decision points: {phase3_result.canonical_count}'

                    phase3_prompt = ExtractionPrompt(
                        case_id=case_id,
                        concept_type='phase3_decision_synthesis',
                        step_number=4,
                        section_type='synthesis',
                        prompt_text=prompt_text,
                        llm_model='claude-sonnet-4-20250514' if phase3_result.llm_prompt else 'algorithmic',
                        extraction_session_id=str(uuid.uuid4()),
                        raw_response=raw_response,
                        results_summary=json.dumps({
                            'canonical_count': phase3_result.canonical_count,
                            'candidates_count': phase3_result.candidates_count,
                            'high_alignment_count': phase3_result.high_alignment_count
                        })
                    )
                    db.session.add(phase3_prompt)
                    db.session.commit()
                except Exception as e:
                    logger.warning(f"Could not save Phase 3 prompt: {e}")

                yield sse_msg({
                    'stage': 'DECISION_SYNTHESIS_COMPLETE',
                    'progress': 75,
                    'messages': [
                        f'Phase 3 complete:',
                        f'  - {len(canonical_points)} canonical decision points',
                        f'  - LLM refinement applied'
                    ],
                    'result': {
                        'decision_point_count': len(canonical_points),
                        'canonical_decision_points': [dp.to_dict() for dp in canonical_points]
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

                # Extract actual LLM prompts from llm_traces
                actual_prompts = []
                if hasattr(phase4_result, 'llm_traces') and phase4_result.llm_traces:
                    for trace in phase4_result.llm_traces:
                        if isinstance(trace, dict) and trace.get('prompt'):
                            stage = trace.get('stage', 'UNKNOWN')
                            actual_prompts.append(f"=== {stage} ===\n{trace['prompt']}")

                prompt_text = "\n\n".join(actual_prompts) if actual_prompts else "Complete Synthesis - Phase 4 Narrative Construction"
                if len(prompt_text) > 10000:
                    prompt_text = prompt_text[:9950] + "\n... [truncated]"

                extraction_prompt = ExtractionPrompt(
                    case_id=case_id,
                    concept_type='phase4_narrative',
                    step_number=4,
                    section_type='synthesis',
                    prompt_text=prompt_text,
                    llm_model='claude-sonnet-4-20250514',
                    extraction_session_id=session_id,
                    raw_response=json.dumps(phase4_result.to_dict()),
                    results_summary=json.dumps(phase4_result.summary())
                )
                db.session.add(extraction_prompt)

                # Also save whole_case_synthesis prompt to mark case as "analyzed"
                # This is checked by cases.py to determine pipeline_status
                synthesis_summary = {
                    'provisions_count': len(provisions),
                    'questions_count': len(questions),
                    'conclusions_count': len(conclusions),
                    'transformation_type': transformation_type,
                    'decision_points_count': len(canonical_points),
                    'characters_count': len(phase4_result.narrative_elements.characters),
                    'timeline_events_count': len(phase4_result.timeline.events),
                    'scenario_branches_count': len(phase4_result.scenario_seeds.branches)
                }
                whole_case_prompt = ExtractionPrompt(
                    case_id=case_id,
                    concept_type='whole_case_synthesis',
                    step_number=4,
                    section_type='synthesis',
                    prompt_text='Complete Four-Phase Synthesis',
                    llm_model='claude-sonnet-4-20250514',
                    extraction_session_id=session_id,
                    raw_response=json.dumps(synthesis_summary),
                    results_summary=json.dumps(synthesis_summary)
                )
                db.session.add(whole_case_prompt)
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

                # Stream LLM traces if any
                if phase4_result.llm_traces:
                    yield sse_msg({
                        'stage': 'NARRATIVE_LLM_TRACES',
                        'progress': 96,
                        'messages': [f'Phase 4: {len(phase4_result.llm_traces)} LLM interactions captured'],
                        'llm_traces': phase4_result.llm_traces
                    })

                yield sse_msg({
                    'stage': 'NARRATIVE_COMPLETE',
                    'progress': 98,
                    'messages': [
                        f'Phase 4 complete:',
                        f'  - {len(phase4_result.narrative_elements.characters)} characters',
                        f'  - {len(phase4_result.timeline.events)} timeline events',
                        f'  - {len(phase4_result.scenario_seeds.branches)} scenario branches',
                        f'  - {len(phase4_result.llm_traces)} LLM traces'
                    ],
                    'result': {
                        'characters_count': len(phase4_result.narrative_elements.characters),
                        'events_count': len(phase4_result.timeline.events),
                        'branches_count': len(phase4_result.scenario_seeds.branches),
                        'llm_traces_count': len(phase4_result.llm_traces)
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
                        'Case analysis is complete.'
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
