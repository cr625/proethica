"""
Step 4 Rich Analysis Component

Handles rich analysis endpoints for Step 4 case analysis.
Three analyses with academic framework grounding:
1. Causal-Normative Links (Berreby et al. 2017)
2. Question Emergence (McLaren 2003)
3. Resolution Patterns (Harris et al. 2018)
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Callable

from flask import Blueprint, request, jsonify, Response, stream_with_context

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.utils.llm_utils import get_llm_client
from app.utils.environment_auth import auth_required_for_llm
from app.routes.scenario_pipeline.step4_config import (
    STEP4_SECTION_TYPE, STEP4_DEFAULT_MODEL, STEP4_POWERFUL_MODEL,
)

logger = logging.getLogger(__name__)


def register_rich_analysis_routes(bp: Blueprint, get_all_case_entities: Callable):
    """
    Register rich analysis routes on the provided blueprint.

    Args:
        bp: The Flask blueprint to register routes on
        get_all_case_entities: Helper function to load entities for a case
    """

    @bp.route('/case/<int:case_id>/extract_rich_analysis_stream', methods=['POST'])
    @auth_required_for_llm
    def extract_rich_analysis_streaming(case_id):
        """
        Extract rich analysis with SSE streaming for real-time progress.

        Three analyses with academic framework grounding:
        1. Causal-Normative Links (Berreby et al. 2017)
        2. Question Emergence (McLaren 2003)
        3. Resolution Patterns (Harris et al. 2018)
        """
        import json as json_module

        def sse_msg(data):
            return f"data: {json_module.dumps(data)}\n\n"

        def generate():
            try:
                from app.services.case_synthesizer import CaseSynthesizer

                case = Document.query.get_or_404(case_id)

                yield sse_msg({'stage': 'START', 'progress': 5, 'messages': ['Starting rich analysis...']})

                # Initialize synthesizer
                synthesizer = CaseSynthesizer()

                # Load foundation (entities from Passes 1-3)
                yield sse_msg({'stage': 'LOADING_FOUNDATION', 'progress': 10, 'messages': ['Building entity foundation from Passes 1-3...']})
                foundation = synthesizer._build_entity_foundation(case_id)

                entity_counts = {
                    'roles': len(foundation.roles),
                    'actions': len(foundation.actions),
                    'events': len(foundation.events),
                    'obligations': len(foundation.obligations),
                    'constraints': len(foundation.constraints),
                    'principles': len(foundation.principles)
                }
                total_entities = sum(entity_counts.values())

                yield sse_msg({
                    'stage': 'FOUNDATION_LOADED',
                    'progress': 15,
                    'messages': [
                        f'Entity foundation built: {total_entities} entities',
                        f'Roles: {entity_counts["roles"]}, Actions: {entity_counts["actions"]}, Obligations: {entity_counts["obligations"]}'
                    ]
                })

                # Load questions and conclusions
                yield sse_msg({'stage': 'LOADING_QC', 'progress': 18, 'messages': ['Loading questions and conclusions...']})
                questions, conclusions = synthesizer._load_qc(case_id)

                if not questions and not conclusions:
                    yield sse_msg({
                        'stage': 'ERROR',
                        'progress': 100,
                        'messages': ['No questions or conclusions found. Run Q&C extraction first.'],
                        'error': True
                    })
                    return

                # Show sample Q&C for debugging
                q_sample = questions[0].get('text', '')[:60] + '...' if questions else 'None'
                c_sample = conclusions[0].get('text', '')[:60] + '...' if conclusions else 'None'

                yield sse_msg({
                    'stage': 'QC_LOADED',
                    'progress': 22,
                    'messages': [
                        f'Loaded {len(questions)} questions, {len(conclusions)} conclusions',
                        f'Sample Q: {q_sample}',
                        f'Sample C: {c_sample}'
                    ]
                })

                # Load provisions
                yield sse_msg({'stage': 'LOADING_PROVISIONS', 'progress': 25, 'messages': ['Loading code provisions...']})
                provisions = synthesizer._load_provisions(case_id)
                yield sse_msg({
                    'stage': 'PROVISIONS_LOADED',
                    'progress': 28,
                    'messages': [f'Loaded {len(provisions)} code provisions']
                })

                # Load academic frameworks
                yield sse_msg({'stage': 'LOADING_FRAMEWORKS', 'progress': 30, 'messages': ['Loading academic frameworks...']})

                frameworks_loaded = []
                try:
                    from app.academic_references.frameworks.extensional_principles import CITATION_SHORT as MCLAREN_CITATION
                    frameworks_loaded.append(f'McLaren (2003) - extensional principles')
                except ImportError:
                    pass

                try:
                    from app.academic_references.frameworks.moral_intensity import CITATION_SHORT as JONES_CITATION
                    frameworks_loaded.append(f'Jones (1991) - moral intensity')
                except ImportError:
                    pass

                try:
                    from app.academic_references.frameworks.role_ethics import CITATION_SHORT as OAKLEY_CITATION
                    frameworks_loaded.append(f'Oakley & Cocking (2001) - role ethics')
                except ImportError:
                    pass

                if frameworks_loaded:
                    yield sse_msg({
                        'stage': 'FRAMEWORKS_LOADED',
                        'progress': 35,
                        'messages': ['Academic frameworks loaded:'] + frameworks_loaded
                    })
                else:
                    yield sse_msg({
                        'stage': 'FRAMEWORKS_SKIP',
                        'progress': 35,
                        'messages': ['Using built-in analysis definitions']
                    })

                # Initialize LLM traces collector
                llm_traces = []

                # ========================================
                # Analysis 1: Causal-Normative Links
                # ========================================
                yield sse_msg({
                    'stage': 'ANALYZING_CAUSAL',
                    'progress': 40,
                    'messages': [
                        'Analyzing causal-normative links...',
                        'Mapping actions to obligations they fulfill or violate'
                    ]
                })

                causal_links = synthesizer._analyze_causal_normative_links(foundation, llm_traces)

                yield sse_msg({
                    'stage': 'CAUSAL_COMPLETE',
                    'progress': 55,
                    'messages': [
                        f'Causal-normative analysis complete: {len(causal_links)} links',
                        f'Actions mapped to obligations/principles'
                    ]
                })

                # ========================================
                # Analysis 2: Question Emergence (Toulmin)
                # ========================================
                # Process in batches of 5 with progress updates
                BATCH_SIZE = 5
                total_questions = len(questions)
                num_batches = (total_questions + BATCH_SIZE - 1) // BATCH_SIZE
                question_emergence = []

                for batch_idx in range(num_batches):
                    batch_start = batch_idx * BATCH_SIZE
                    batch_questions = questions[batch_start:batch_start + BATCH_SIZE]
                    batch_num = batch_idx + 1

                    # Progress: 60-75% spread across batches
                    batch_progress = 60 + int((batch_idx / num_batches) * 15)

                    yield sse_msg({
                        'stage': 'ANALYZING_EMERGENCE',
                        'progress': batch_progress,
                        'messages': [
                            f'Analyzing question emergence (Toulmin) - batch {batch_num}/{num_batches}...',
                            f'Processing {len(batch_questions)} questions'
                        ]
                    })

                    batch_results = synthesizer._analyze_question_batch(
                        batch_questions, foundation, llm_traces, batch_start
                    )
                    question_emergence.extend(batch_results)

                emergence_summary = []
                for qe in question_emergence[:2]:
                    trigger = qe.data_events[0] if qe.data_events else 'Unknown trigger'
                    emergence_summary.append(f'Q: "{qe.question_text[:50]}..." triggered by {trigger}')

                yield sse_msg({
                    'stage': 'EMERGENCE_COMPLETE',
                    'progress': 75,
                    'messages': [
                        f'Question emergence analysis complete: {len(question_emergence)} patterns',
                    ] + emergence_summary[:2]
                })

                # ========================================
                # Analysis 3: Resolution Patterns (Harris)
                # ========================================
                yield sse_msg({
                    'stage': 'ANALYZING_RESOLUTION',
                    'progress': 80,
                    'messages': [
                        'Analyzing resolution patterns...',
                        'Identifying HOW the board resolved questions'
                    ]
                })

                resolution_patterns = synthesizer._analyze_resolution_patterns(
                    conclusions, questions, provisions, llm_traces
                )

                resolution_summary = []
                for rp in resolution_patterns[:2]:
                    det_factors = len(rp.determinative_facts) if rp.determinative_facts else 0
                    resolution_summary.append(f'C: "{rp.conclusion_text[:40]}..." ({det_factors} determinative factors)')

                yield sse_msg({
                    'stage': 'RESOLUTION_COMPLETE',
                    'progress': 90,
                    'messages': [
                        f'Resolution pattern analysis complete: {len(resolution_patterns)} patterns',
                    ] + resolution_summary[:2]
                })

                # ========================================
                # Store results
                # ========================================
                yield sse_msg({'stage': 'STORING', 'progress': 92, 'messages': ['Storing rich analysis results...']})

                synthesizer._store_rich_analysis(case_id, causal_links, question_emergence, resolution_patterns)

                # Save prompts/responses to extraction_prompts for UI persistence on refresh
                session_id = str(uuid.uuid4())

                # Combine prompts and responses for storage
                combined_prompt = ""
                combined_response = ""
                for trace in llm_traces:
                    combined_prompt += f"\n--- {trace.stage.upper()} ---\n{trace.prompt}\n"
                    combined_response += f"\n--- {trace.stage.upper()} ---\n{trace.response}\n"

                try:
                    saved_prompt = ExtractionPrompt.save_prompt(
                        case_id=case_id,
                        concept_type='rich_analysis',  # Must match get_saved_step4_prompt mapping
                        prompt_text=combined_prompt,
                        raw_response=combined_response,
                        step_number=4,
                        section_type=STEP4_SECTION_TYPE,
                        llm_model=STEP4_DEFAULT_MODEL,
                        extraction_session_id=session_id
                    )
                    logger.info(f"Saved rich analysis prompt id={saved_prompt.id}")
                except Exception as prompt_err:
                    logger.warning(f"Could not save rich analysis prompt: {prompt_err}")

                yield sse_msg({'stage': 'STORED', 'progress': 95, 'messages': ['Analysis stored to database']})

                # Build final result
                status_messages = [
                    f"Causal-normative links: {len(causal_links)}",
                    f"Question emergence patterns: {len(question_emergence)}",
                    f"Resolution patterns: {len(resolution_patterns)}",
                    f"LLM analyses performed: {len(llm_traces)}"
                ]

                yield sse_msg({
                    'stage': 'COMPLETE',
                    'progress': 100,
                    'messages': ['Rich analysis complete'],
                    'status_messages': status_messages,
                    'prompt': combined_prompt if combined_prompt else 'Rich analysis prompts',
                    'raw_llm_response': combined_response if combined_response else '',
                    'result': {
                        'causal_normative_links': len(causal_links),
                        'question_emergence': len(question_emergence),
                        'resolution_patterns': len(resolution_patterns),
                        'llm_traces': len(llm_traces)
                    },
                    'details': {
                        'causal_links': [
                            {
                                'action': cl.action_label,
                                'fulfills': len(cl.fulfills_obligations),
                                'violates': len(cl.violates_obligations),
                                'confidence': cl.confidence
                            }
                            for cl in causal_links[:5]
                        ],
                        'question_emergence': [
                            {
                                'question': qe.question_text[:60] + '...' if len(qe.question_text) > 60 else qe.question_text,
                                'data_triggers': len(qe.data_events) + len(qe.data_actions),
                                'competing_warrants': len(qe.competing_warrants)
                            }
                            for qe in question_emergence[:5]
                        ],
                        'resolution_patterns': [
                            {
                                'conclusion': rp.conclusion_text[:60] + '...' if len(rp.conclusion_text) > 60 else rp.conclusion_text,
                                'determinative_principles': len(rp.determinative_principles),
                                'determinative_facts': len(rp.determinative_facts)
                            }
                            for rp in resolution_patterns[:5]
                        ]
                    }
                })

            except Exception as e:
                logger.error(f"Streaming rich analysis error: {e}")
                import traceback
                traceback.print_exc()
                yield sse_msg({'stage': 'ERROR', 'progress': 100, 'messages': [f'Error: {str(e)}'], 'error': True})

        return Response(stream_with_context(generate()), mimetype='text/event-stream')

    @bp.route('/case/<int:case_id>/extract_rich_analysis', methods=['POST'])
    @auth_required_for_llm
    def extract_rich_analysis_individual(case_id):
        """
        Extract rich analysis (causal-normative links, question emergence, resolution patterns).
        Returns prompt and response for UI display.
        """
        try:
            from app.services.case_synthesizer import CaseSynthesizer

            case = Document.query.get_or_404(case_id)
            synthesizer = CaseSynthesizer()

            # Build foundation
            foundation = synthesizer._build_entity_foundation(case_id)

            # Load Q&C
            questions, conclusions = synthesizer._load_qc(case_id)

            if not questions and not conclusions:
                return jsonify({
                    'success': False,
                    'error': 'No questions or conclusions found. Run extraction first.'
                }), 400

            # Load provisions
            provisions = synthesizer._load_provisions(case_id)

            # Run rich analysis
            causal_links, question_emergence, resolution_patterns, llm_traces = synthesizer._run_rich_analysis(
                case_id, foundation, provisions, questions, conclusions
            )

            # Store rich analysis
            synthesizer._store_rich_analysis(case_id, causal_links, question_emergence, resolution_patterns)

            return jsonify({
                'success': True,
                'result': {
                    'causal_normative_links': len(causal_links),
                    'question_emergence': len(question_emergence),
                    'resolution_patterns': len(resolution_patterns)
                },
                'llm_traces': [
                    {
                        'stage': t.stage,
                        'prompt': t.prompt,
                        'response': t.response,
                        'model': t.model
                    }
                    for t in llm_traces
                ],
                'metadata': {
                    'timestamp': datetime.utcnow().isoformat()
                }
            })

        except Exception as e:
            logger.error(f"Error extracting rich analysis for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    # Return the functions so they can be used for CSRF exemption
    return {
        'extract_rich_analysis_individual': extract_rich_analysis_individual,
        'extract_rich_analysis_streaming': extract_rich_analysis_streaming
    }
