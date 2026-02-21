"""
Step 4 Phase 3: Decision Point Synthesis Routes

Handles decision point synthesis with Q&C alignment:
- Individual synthesis (non-streaming)
- Streaming synthesis with real-time progress showing E1-E3, alignment, LLM stages
"""

import json
import logging
import os
import uuid
from datetime import datetime
from flask import jsonify, Response, stream_with_context

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.utils.llm_utils import get_llm_client
from app.utils.environment_auth import auth_required_for_llm
from app.routes.scenario_pipeline.step4_config import (
    STEP4_SECTION_TYPE, STEP4_DEFAULT_MODEL, STEP4_POWERFUL_MODEL,
)

from app.services.decision_point_synthesizer import (
    DecisionPointSynthesizer,
    synthesize_decision_points,
    Phase3SynthesisResult,
    SynthesisTrace
)
from app.domains import get_domain_config
from app.services.provenance_service import get_provenance_service

logger = logging.getLogger(__name__)


def register_phase3_routes(bp, get_all_case_entities, load_phase2_data):
    """Register Phase 3 decision point synthesis routes on the blueprint.

    Args:
        bp: The Flask Blueprint to register routes on
        get_all_case_entities: Function to get all entities for a case
        load_phase2_data: Function to load Phase 2 data (Q&C, question emergence, etc.)
    """

    @bp.route('/case/<int:case_id>/synthesize_phase3', methods=['POST'])
    @auth_required_for_llm
    def synthesize_phase3_individual(case_id):
        """
        Run Phase 3 decision point synthesis (non-streaming).
        Returns canonical decision points with Q&C alignment scores.
        """
        try:
            case = Document.query.get_or_404(case_id)

            # Load Phase 2 data
            phase2_data = load_phase2_data(case_id)

            questions = phase2_data.get('questions', [])
            conclusions = phase2_data.get('conclusions', [])
            question_emergence = phase2_data.get('question_emergence', [])
            resolution_patterns = phase2_data.get('resolution_patterns', [])

            if not questions:
                return jsonify({
                    'success': False,
                    'error': 'No questions found - run Phase 2 extraction first'
                }), 400

            # Run Phase 3 synthesis
            result = synthesize_decision_points(
                case_id=case_id,
                questions=questions,
                conclusions=conclusions,
                question_emergence=question_emergence,
                resolution_patterns=resolution_patterns,
                domain='engineering',
                skip_llm=False
            )

            # Save extraction prompt for provenance (always save, even with 0 candidates)
            session_id = result.extraction_session_id or str(uuid.uuid4())
            try:
                if result.llm_prompt:
                    prompt_text = result.llm_prompt[:10000]
                    raw_response = result.llm_response[:10000] if result.llm_response else ''
                else:
                    # No LLM output (E1-E3 found 0 AND LLM fallback didn't produce results)
                    prompt_text = f'Phase 3 Decision Point Synthesis (E1-E3 Algorithmic Composition)\n\nE1-E3 Algorithm found 0 matching candidates.\nLLM fallback using causal_normative_links was attempted.'
                    raw_response = f'Phase 3 Result:\n- Algorithmic candidates: 0\n- Canonical decision points: {result.canonical_count}'

                extraction_prompt = ExtractionPrompt(
                    case_id=case_id,
                    concept_type='phase3_decision_synthesis',
                    step_number=4,
                    section_type=STEP4_SECTION_TYPE,
                    prompt_text=prompt_text,
                    llm_model=STEP4_DEFAULT_MODEL if result.llm_prompt else 'algorithmic',
                    extraction_session_id=session_id,
                    raw_response=raw_response,
                    results_summary=json.dumps({
                        'canonical_count': result.canonical_count,
                        'candidates_count': result.candidates_count,
                        'high_alignment_count': result.high_alignment_count
                    })
                )
                db.session.add(extraction_prompt)
                db.session.commit()
            except Exception as e:
                logger.warning(f"Could not save Phase 3 prompt: {e}")

            return jsonify({
                'success': True,
                'canonical_count': result.canonical_count,
                'candidates_count': result.candidates_count,
                'high_alignment_count': result.high_alignment_count,
                'canonical_decision_points': [dp.to_dict() for dp in result.canonical_decision_points],
                'alignment_scores': [s.to_dict() for s in result.alignment_scores],
                'llm_trace': {
                    'prompt': result.llm_prompt[:2000] if result.llm_prompt else None,
                    'response': result.llm_response[:2000] if result.llm_response else None
                }
            })

        except Exception as e:
            logger.error(f"Phase 3 synthesis failed for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/synthesize_phase3_stream', methods=['POST'])
    @auth_required_for_llm
    def synthesize_phase3_streaming(case_id):
        """
        Run Phase 3 decision point synthesis with SSE streaming.
        Shows real-time progress through E1, E2, E3, alignment scoring, and LLM stages.
        """

        def sse_msg(data):
            return f"data: {json.dumps(data)}\n\n"

        def generate():
            try:
                case = Document.query.get_or_404(case_id)

                yield sse_msg({
                    'stage': 'START',
                    'progress': 0,
                    'messages': ['Starting Phase 3: Decision Point Synthesis...']
                })

                # Load Phase 2 data
                yield sse_msg({
                    'stage': 'LOADING_PHASE2',
                    'progress': 5,
                    'messages': ['Loading Phase 2 data (Q&C, analysis)...']
                })

                phase2_data = load_phase2_data(case_id)
                questions = phase2_data.get('questions', [])
                conclusions = phase2_data.get('conclusions', [])
                question_emergence = phase2_data.get('question_emergence', [])
                resolution_patterns = phase2_data.get('resolution_patterns', [])

                if not questions:
                    yield sse_msg({
                        'stage': 'ERROR',
                        'progress': 100,
                        'messages': ['No questions found - run Phase 2 extraction first'],
                        'error': True
                    })
                    return

                yield sse_msg({
                    'stage': 'PHASE2_LOADED',
                    'progress': 10,
                    'messages': [
                        f'Loaded {len(questions)} questions, {len(conclusions)} conclusions',
                        f'{len(question_emergence)} question emergence analyses'
                    ]
                })

                # Stage 3.1: E1-E3 Algorithmic Composition
                yield sse_msg({
                    'stage': 'STAGE_3_1_E1',
                    'progress': 15,
                    'messages': ['Stage 3.1: Running E1 - Obligation Coverage Analysis...']
                })

                from app.services.entity_analysis import (
                    get_obligation_coverage,
                    get_action_option_map,
                    compose_decision_points
                )

                # E1 - Pass Q&C for LLM fallback if algorithmic approach fails
                coverage = get_obligation_coverage(
                    case_id, 'engineering',
                    questions=questions,
                    conclusions=conclusions
                )
                obl_count = len(coverage.obligations) if hasattr(coverage, 'obligations') else 0
                decision_relevant = coverage.decision_relevant_count

                e1_messages = [f'E1 complete: {obl_count} obligations, {decision_relevant} decision-relevant']
                if coverage.used_llm_fallback:
                    e1_messages.append('(Used LLM to identify decision-relevant obligations)')

                yield sse_msg({
                    'stage': 'STAGE_3_1_E1_DONE',
                    'progress': 25,
                    'messages': e1_messages,
                    'e1_result': f'{obl_count} obligations',
                    'used_llm_fallback': coverage.used_llm_fallback,
                    'e1_llm_trace': coverage.llm_traces[0].to_dict() if coverage.llm_traces else None
                })

                # E2
                yield sse_msg({
                    'stage': 'STAGE_3_1_E2',
                    'progress': 30,
                    'messages': ['Running E2 - Action-Option Mapping...']
                })

                action_map = get_action_option_map(case_id, 'engineering')
                action_sets = len(action_map.action_sets) if hasattr(action_map, 'action_sets') else 0

                yield sse_msg({
                    'stage': 'STAGE_3_1_E2_DONE',
                    'progress': 40,
                    'messages': [f'E2 complete: {action_sets} action sets mapped'],
                    'e2_result': f'{action_sets} action sets'
                })

                # E3 - Pass coverage and action_map to avoid re-running E1/E2
                yield sse_msg({
                    'stage': 'STAGE_3_1_E3',
                    'progress': 45,
                    'messages': ['Running E3 - Decision Point Composition...']
                })

                candidates = compose_decision_points(
                    case_id, 'engineering',
                    coverage_matrix=coverage,
                    action_map=action_map
                )
                candidates_count = len(candidates.decision_points)

                yield sse_msg({
                    'stage': 'STAGE_3_1_DONE',
                    'progress': 50,
                    'messages': [f'Stage 3.1 complete: {candidates_count} candidate decision points'],
                    'e3_result': f'{candidates_count} candidates'
                })

                # Track E1-E3 composition in PROV-O timeline
                prov = get_provenance_service()
                e1e3_session = f"phase3_e1e3_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                with prov.track_activity(
                    activity_type='composition',
                    activity_name='phase3_e1e3_algorithmic',
                    case_id=case_id,
                    session_id=e1e3_session,
                    agent_type='algorithmic',
                    agent_name='e1_e3_composer',
                    execution_plan={
                        'e1_obligations': obl_count,
                        'e1_decision_relevant': decision_relevant,
                        'e1_used_llm_fallback': coverage.used_llm_fallback if hasattr(coverage, 'used_llm_fallback') else False,
                        'e2_action_sets': action_sets,
                        'e3_candidates': candidates_count
                    }
                ) as e1e3_activity:
                    prov.record_extraction_results(
                        results={'candidates': candidates_count, 'method': 'E1-E3 algorithmic'},
                        activity=e1e3_activity,
                        entity_type='algorithmic_candidates',
                        metadata={'obligations': obl_count, 'action_sets': action_sets}
                    )

                if candidates_count == 0:
                    # LLM fallback using causal_normative_links (unified with synthesize_decision_points)
                    yield sse_msg({
                        'stage': 'E3_LLM_FALLBACK',
                        'progress': 52,
                        'messages': [
                            'No algorithmic candidates - using LLM fallback with causal links',
                            'Loading causal_normative_links from Phase 2 rich analysis...'
                        ]
                    })

                    # Use the unified fallback from decision_point_synthesizer
                    synthesizer = DecisionPointSynthesizer(domain_config=get_domain_config('engineering'))
                    canonical_points, llm_prompt, llm_response = synthesizer._llm_generate_from_causal_links(
                        case_id, questions, conclusions, question_emergence, resolution_patterns
                    )

                    if canonical_points:
                        yield sse_msg({
                            'stage': 'E3_LLM_FALLBACK_DONE',
                            'progress': 60,
                            'messages': [f'LLM fallback generated {len(canonical_points)} decision points from causal links'],
                            'e3_llm_trace': {
                                'stage': 'E3_causal_link_fallback',
                                'prompt': llm_prompt[:2000] if llm_prompt else None,
                                'response': llm_response[:2000] if llm_response else None
                            }
                        })

                        # Store the generated decision points
                        session_id = f"phase3_llm_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        synthesizer._store_canonical_points(case_id, canonical_points, session_id)

                        # Save prompt for provenance
                        try:
                            extraction_prompt = ExtractionPrompt(
                                case_id=case_id,
                                concept_type='phase3_decision_synthesis',
                                step_number=4,
                                section_type=STEP4_SECTION_TYPE,
                                prompt_text=llm_prompt[:10000] if llm_prompt else 'LLM fallback with causal links',
                                llm_model=STEP4_DEFAULT_MODEL,
                                extraction_session_id=session_id,
                                raw_response=llm_response[:10000] if llm_response else '',
                                results_summary=json.dumps({
                                    'canonical_count': len(canonical_points),
                                    'candidates_count': 0,
                                    'used_llm_fallback': True,
                                    'fallback_source': 'causal_normative_links'
                                })
                            )
                            db.session.add(extraction_prompt)
                            db.session.commit()
                        except Exception as e:
                            logger.warning(f"Could not save Phase 3 fallback prompt: {e}")

                        yield sse_msg({
                            'stage': 'COMPLETE',
                            'progress': 100,
                            'messages': [
                                f'Phase 3 complete (LLM fallback): {len(canonical_points)} decision points',
                                'Used causal_normative_links from Phase 2 rich analysis'
                            ],
                            'canonical_count': len(canonical_points),
                            'used_llm_fallback': True,
                            'canonical_decision_points': [dp.to_dict() for dp in canonical_points],
                            'llm_trace': {
                                'stage': 'E3_causal_link_fallback',
                                'prompt': llm_prompt if llm_prompt else None,
                                'response': llm_response if llm_response else None
                            }
                        })
                        return
                    else:
                        yield sse_msg({
                            'stage': 'ERROR',
                            'progress': 100,
                            'messages': [
                                'LLM fallback produced no decision points',
                                'Check that causal_normative_links exist from Phase 2 rich analysis'
                            ],
                            'error': True
                        })
                        return

                # Stage 3.2: Q&C Alignment Scoring
                yield sse_msg({
                    'stage': 'STAGE_3_2',
                    'progress': 55,
                    'messages': ['Stage 3.2: Scoring candidates against Q&C using Toulmin analysis...']
                })

                synthesizer = DecisionPointSynthesizer(domain_config=get_domain_config('engineering'))
                alignment_scores = synthesizer._score_qc_alignment(
                    candidates.decision_points,
                    questions,
                    conclusions,
                    question_emergence
                )

                high_alignment = sum(1 for s in alignment_scores if s.total_score > 0.5)

                yield sse_msg({
                    'stage': 'STAGE_3_2_DONE',
                    'progress': 65,
                    'messages': [
                        f'Stage 3.2 complete: {high_alignment}/{len(alignment_scores)} candidates scored > 0.5',
                        'Scores based on obligation-warrant, action-data, role involvement, conclusion alignment'
                    ],
                    'alignment_result': f'{high_alignment}/{len(alignment_scores)} high alignment'
                })

                # Track Q&C alignment in PROV-O timeline
                qc_session = f"phase3_qc_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                with prov.track_activity(
                    activity_type='alignment',
                    activity_name='phase3_qc_alignment',
                    case_id=case_id,
                    session_id=qc_session,
                    agent_type='algorithmic',
                    agent_name='toulmin_alignment_scorer',
                    execution_plan={
                        'candidates_scored': len(alignment_scores),
                        'high_alignment_count': high_alignment,
                        'threshold': 0.5
                    }
                ) as qc_activity:
                    top_scores = sorted(alignment_scores, key=lambda x: x.total_score, reverse=True)[:5]
                    prov.record_extraction_results(
                        results={
                            'high_alignment': high_alignment,
                            'total_scored': len(alignment_scores),
                            'top_scores': [{'id': s.candidate_id, 'score': s.total_score} for s in top_scores]
                        },
                        activity=qc_activity,
                        entity_type='alignment_scores',
                        metadata={'method': 'Toulmin analysis'}
                    )

                # Stage 3.3: LLM Refinement
                yield sse_msg({
                    'stage': 'STAGE_3_3',
                    'progress': 70,
                    'messages': ['Stage 3.3: Running LLM refinement with Toulmin structure...']
                })

                canonical_points, llm_prompt, llm_response, enrichment_result = synthesizer._llm_refine(
                    case_id,
                    candidates.decision_points,
                    alignment_scores,
                    questions,
                    conclusions,
                    question_emergence,
                    resolution_patterns
                )

                # Build enrichment info for provenance
                mcp_info = {}
                if enrichment_result:
                    mcp_info = {
                        'mcp_resolved': enrichment_result.mcp_resolved_count,
                        'local_resolved': enrichment_result.local_resolved_count,
                        'not_found': enrichment_result.not_found_count,
                        'entities': [e['label'] for e in enrichment_result.resolution_log if e.get('found')]
                    }

                yield sse_msg({
                    'stage': 'STAGE_3_3_DONE',
                    'progress': 85,
                    'messages': [f'Stage 3.3 complete: {len(canonical_points)} decision points'],
                    'llm_result': f'{len(canonical_points)} decision points',
                    'mcp_enrichment': mcp_info
                })

                # Stage 3.4: Storage
                yield sse_msg({
                    'stage': 'STAGE_3_4',
                    'progress': 90,
                    'messages': ['Stage 3.4: Storing decision points...']
                })

                session_id = f"phase3_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                # Build synthesis trace for provenance_metadata
                synthesis_trace = SynthesisTrace(
                    synthesis_started=datetime.now().isoformat(),
                    synthesis_completed=datetime.now().isoformat(),
                    algorithmic_candidates_count=candidates_count,
                    high_alignment_count=high_alignment,
                    canonical_points_produced=len(canonical_points),
                    llm_model=STEP4_DEFAULT_MODEL,
                    llm_prompt_length=len(llm_prompt) if llm_prompt else 0,
                    llm_response_length=len(llm_response) if llm_response else 0,
                    mcp_server_url=os.environ.get("ONTSERVE_MCP_URL", "http://localhost:8082")
                )
                if enrichment_result:
                    synthesis_trace.entities_resolved = enrichment_result.resolution_log
                    synthesis_trace.mcp_resolved_count = enrichment_result.mcp_resolved_count
                    synthesis_trace.local_resolved_count = enrichment_result.local_resolved_count
                    synthesis_trace.entities_not_found = enrichment_result.not_found_count
                synthesis_trace.alignment_scores_summary = [
                    {"candidate_id": s.candidate_id, "score": s.total_score}
                    for s in sorted(alignment_scores, key=lambda x: x.total_score, reverse=True)[:5]
                ]

                synthesizer._store_canonical_points(case_id, canonical_points, session_id, synthesis_trace)

                # Track provenance - one activity per stage for clear timeline
                prov = get_provenance_service()

                # Track MCP Entity Resolution as separate activity
                if enrichment_result and (enrichment_result.mcp_resolved_count > 0 or enrichment_result.local_resolved_count > 0):
                    with prov.track_activity(
                        activity_type='enrichment',
                        activity_name='phase3_mcp_entity_resolution',
                        case_id=case_id,
                        session_id=session_id,
                        agent_type='mcp_service',
                        agent_name='ontserve_mcp',
                        execution_plan={
                            'mcp_resolved': enrichment_result.mcp_resolved_count,
                            'local_resolved': enrichment_result.local_resolved_count,
                            'not_found': enrichment_result.not_found_count,
                            'total_uris': len(enrichment_result.resolution_log)
                        }
                    ) as mcp_activity:
                        # Record resolved entities as extraction results
                        prov.record_extraction_results(
                            results={
                                'resolved_entities': [
                                    {'uri': e['uri'], 'label': e['label'], 'source': e['source']}
                                    for e in enrichment_result.resolution_log if e.get('found')
                                ]
                            },
                            activity=mcp_activity,
                            entity_type='mcp_resolved_entities',
                            metadata={'mcp_server': os.environ.get("ONTSERVE_MCP_URL", "http://localhost:8082")}
                        )

                # Track LLM Refinement as separate activity
                with prov.track_activity(
                    activity_type='synthesis',
                    activity_name='phase3_llm_refinement',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='llm_model',
                    agent_name=STEP4_DEFAULT_MODEL,
                    execution_plan={
                        'input_candidates': candidates_count,
                        'high_alignment_candidates': high_alignment,
                        'output_decision_points': len(canonical_points)
                    }
                ) as llm_activity:
                    if llm_prompt:
                        prompt_entity = prov.record_prompt(llm_prompt[:5000], llm_activity, entity_name='phase3_refinement_prompt')
                        if llm_response:
                            prov.record_response(llm_response[:5000], llm_activity, derived_from=prompt_entity, entity_name='phase3_refinement_response')

                # Track final storage as separate activity
                with prov.track_activity(
                    activity_type='storage',
                    activity_name='phase3_decision_points_stored',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='system',
                    agent_name='decision_point_synthesizer',
                    execution_plan={
                        'canonical_count': len(canonical_points),
                        'stored_to': 'temporary_rdf_storage'
                    }
                ) as storage_activity:
                    prov.record_extraction_results(
                        results={
                            'decision_points': [dp.focus_id for dp in canonical_points],
                            'total_stored': len(canonical_points)
                        },
                        activity=storage_activity,
                        entity_type='canonical_decision_points',
                        metadata={'session_id': session_id}
                    )

                # Save extraction prompt for UI
                if llm_prompt:
                    extraction_prompt = ExtractionPrompt(
                        case_id=case_id,
                        concept_type='phase3_decision_synthesis',
                        step_number=4,
                        section_type=STEP4_SECTION_TYPE,
                        prompt_text=llm_prompt[:10000],
                        llm_model=STEP4_DEFAULT_MODEL,
                        extraction_session_id=session_id,
                        raw_response=llm_response[:10000] if llm_response else '',
                        results_summary=json.dumps({
                            'canonical_count': len(canonical_points),
                            'candidates_count': candidates_count,
                            'high_alignment_count': high_alignment,
                            # E1-E3 intermediate results for UI restoration
                            'e1_obligations': obl_count,
                            'e1_decision_relevant': decision_relevant,
                            'e2_action_sets': action_sets,
                            'e3_candidates': candidates_count
                        })
                    )
                    db.session.add(extraction_prompt)
                    db.session.commit()

                # Final result
                yield sse_msg({
                    'stage': 'COMPLETE',
                    'progress': 100,
                    'messages': [
                        f'Phase 3 complete!',
                        f'{candidates_count} candidates -> {len(canonical_points)} decision points',
                        f'{high_alignment} candidates had high Q&C alignment (> 0.5)'
                    ],
                    'canonical_count': len(canonical_points),
                    'candidates_count': candidates_count,
                    'high_alignment_count': high_alignment,
                    'canonical_decision_points': [dp.to_dict() for dp in canonical_points],
                    'alignment_scores': [s.to_dict() for s in alignment_scores[:10]],  # Top 10
                    'llm_trace': {
                        'prompt': llm_prompt if llm_prompt else None,
                        'response': llm_response if llm_response else None
                    },
                    'synthesis_trace': synthesis_trace.to_dict() if synthesis_trace else None
                })

            except Exception as e:
                logger.error(f"Phase 3 streaming synthesis failed for case {case_id}: {e}")
                import traceback
                traceback.print_exc()
                yield sse_msg({
                    'stage': 'ERROR',
                    'progress': 100,
                    'messages': [f'Error: {str(e)}'],
                    'error': True
                })

        return Response(stream_with_context(generate()), mimetype='text/event-stream')

    @bp.route('/case/<int:case_id>/phase3_results', methods=['GET'])
    def get_phase3_results(case_id):
        """
        Load existing Phase 3 canonical decision points.
        """
        try:
            canonical_points = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='canonical_decision_point'
            ).all()

            results = []
            for cp in canonical_points:
                if cp.rdf_json_ld:
                    results.append(cp.rdf_json_ld)
                else:
                    results.append({
                        'focus_id': cp.entity_label,
                        'description': cp.entity_definition,
                        'entity_uri': cp.entity_uri
                    })

            # Get last extraction prompt for metadata (check both regular and fallback)
            last_prompt = ExtractionPrompt.query.filter(
                ExtractionPrompt.case_id == case_id,
                ExtractionPrompt.concept_type.in_(['phase3_decision_synthesis', 'phase3_e3_llm_fallback'])
            ).order_by(ExtractionPrompt.created_at.desc()).first()

            summary = {}
            if last_prompt and last_prompt.results_summary:
                # results_summary is a JSON column - already a dict
                if isinstance(last_prompt.results_summary, dict):
                    summary = last_prompt.results_summary
                elif isinstance(last_prompt.results_summary, str):
                    try:
                        summary = json.loads(last_prompt.results_summary)
                    except json.JSONDecodeError:
                        pass

            # Build LLM trace if available
            llm_trace = None
            if last_prompt and (last_prompt.prompt_text or last_prompt.raw_response):
                llm_trace = {
                    'prompt': last_prompt.prompt_text,
                    'response': last_prompt.raw_response
                }

            # Get synthesis trace from provenance_metadata of first decision point
            synthesis_trace = None
            first_dp = canonical_points[0] if canonical_points else None
            if first_dp and first_dp.provenance_metadata:
                synthesis_trace = first_dp.provenance_metadata

            return jsonify({
                'success': True,
                'canonical_count': len(results),
                'canonical_decision_points': results,
                'candidates_count': summary.get('candidates_count', 0),
                'high_alignment_count': summary.get('high_alignment_count', 0),
                'last_synthesis': last_prompt.created_at.isoformat() if last_prompt else None,
                'llm_trace': llm_trace,
                'synthesis_trace': synthesis_trace,
                # E1-E3 intermediate results for UI badges
                'e1_obligations': summary.get('e1_obligations', 0),
                'e1_decision_relevant': summary.get('e1_decision_relevant', 0),
                'e2_action_sets': summary.get('e2_action_sets', 0),
                'e3_candidates': summary.get('e3_candidates', 0)
            })

        except Exception as e:
            logger.error(f"Failed to load Phase 3 results for case {case_id}: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
