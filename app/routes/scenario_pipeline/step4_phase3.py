"""
Step 4 Phase 3: Decision Point Synthesis Routes

Handles decision point synthesis with Q&C alignment:
- Individual synthesis (non-streaming)
- Streaming synthesis with real-time progress showing E1-E3, alignment, LLM stages
"""

import json
import logging
import uuid
from datetime import datetime
from flask import jsonify, Response, stream_with_context

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.utils.llm_utils import get_llm_client
from app.utils.environment_auth import auth_required_for_llm

from app.services.decision_point_synthesizer import (
    DecisionPointSynthesizer,
    synthesize_decision_points,
    Phase3SynthesisResult
)
from app.domains import get_domain_config

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

            # Save extraction prompt for provenance
            session_id = result.extraction_session_id or str(uuid.uuid4())
            if result.llm_prompt:
                extraction_prompt = ExtractionPrompt(
                    case_id=case_id,
                    concept_type='phase3_decision_synthesis',
                    step_number=4,
                    section_type='synthesis',
                    prompt_text=result.llm_prompt[:10000] if result.llm_prompt else '',
                    llm_model='claude-sonnet-4-20250514',
                    extraction_session_id=session_id,
                    raw_response=result.llm_response[:10000] if result.llm_response else '',
                    results_summary=json.dumps({
                        'canonical_count': result.canonical_count,
                        'candidates_count': result.candidates_count,
                        'high_alignment_count': result.high_alignment_count
                    })
                )
                db.session.add(extraction_prompt)
                db.session.commit()

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

                # E1
                coverage = get_obligation_coverage(case_id, 'engineering')
                obl_count = len(coverage.obligations) if hasattr(coverage, 'obligations') else 0
                decision_relevant = sum(1 for o in coverage.obligations if getattr(o, 'decision_relevance', 0) > 0) if hasattr(coverage, 'obligations') else 0

                yield sse_msg({
                    'stage': 'STAGE_3_1_E1_DONE',
                    'progress': 25,
                    'messages': [f'E1 complete: {obl_count} obligations, {decision_relevant} decision-relevant'],
                    'e1_result': f'{obl_count} obligations'
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

                # E3
                yield sse_msg({
                    'stage': 'STAGE_3_1_E3',
                    'progress': 45,
                    'messages': ['Running E3 - Decision Point Composition...']
                })

                candidates = compose_decision_points(case_id, 'engineering')
                candidates_count = len(candidates.decision_points)

                yield sse_msg({
                    'stage': 'STAGE_3_1_DONE',
                    'progress': 50,
                    'messages': [f'Stage 3.1 complete: {candidates_count} candidate decision points'],
                    'e3_result': f'{candidates_count} candidates'
                })

                if candidates_count == 0:
                    yield sse_msg({
                        'stage': 'WARNING',
                        'progress': 100,
                        'messages': ['No algorithmic candidates - cannot proceed'],
                        'canonical_count': 0
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

                # Stage 3.3: LLM Refinement
                yield sse_msg({
                    'stage': 'STAGE_3_3',
                    'progress': 70,
                    'messages': ['Stage 3.3: Running LLM refinement with Toulmin structure...']
                })

                canonical_points, llm_prompt, llm_response = synthesizer._llm_refine(
                    case_id,
                    candidates.decision_points,
                    alignment_scores,
                    questions,
                    conclusions,
                    question_emergence,
                    resolution_patterns
                )

                yield sse_msg({
                    'stage': 'STAGE_3_3_DONE',
                    'progress': 85,
                    'messages': [f'Stage 3.3 complete: {len(canonical_points)} decision points'],
                    'llm_result': f'{len(canonical_points)} decision points'
                })

                # Stage 3.4: Storage
                yield sse_msg({
                    'stage': 'STAGE_3_4',
                    'progress': 90,
                    'messages': ['Stage 3.4: Storing decision points...']
                })

                session_id = f"phase3_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                synthesizer._store_canonical_points(case_id, canonical_points, session_id)

                # Save extraction prompt for provenance
                if llm_prompt:
                    extraction_prompt = ExtractionPrompt(
                        case_id=case_id,
                        concept_type='phase3_decision_synthesis',
                        step_number=4,
                        section_type='synthesis',
                        prompt_text=llm_prompt[:10000],
                        llm_model='claude-sonnet-4-20250514',
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
                    }
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

            # Get last extraction prompt for metadata
            last_prompt = ExtractionPrompt.query.filter_by(
                case_id=case_id,
                concept_type='phase3_decision_synthesis'
            ).order_by(ExtractionPrompt.created_at.desc()).first()

            summary = {}
            if last_prompt and last_prompt.results_summary:
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

            return jsonify({
                'success': True,
                'canonical_count': len(results),
                'canonical_decision_points': results,
                'candidates_count': summary.get('candidates_count', 0),
                'high_alignment_count': summary.get('high_alignment_count', 0),
                'last_synthesis': last_prompt.created_at.isoformat() if last_prompt else None,
                'llm_trace': llm_trace,
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
