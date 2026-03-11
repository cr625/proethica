"""
Step 4 Question & Conclusion Extraction Routes

Thin route handlers that delegate to entity_graph_service.
Keeps only:
- Route registration and Flask HTTP concerns (jsonify, request, Response)
- SSE streaming wrapper (extract_qc_unified_streaming)
- Non-streaming route (extract_qc_unified) that delegates to service
"""

import json as json_mod
import logging
import uuid

from flask import jsonify, request, Response, stream_with_context

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.utils.llm_utils import get_llm_client
from app.utils.environment_auth import auth_required_for_llm

from app.services.question_analyzer import QuestionAnalyzer
from app.services.conclusion_analyzer import ConclusionAnalyzer
from app.services.question_conclusion_linker import QuestionConclusionLinker

from app.services.entity_graph_service import (
    build_entity_graph,
    build_qc_flow,
    extract_questions_conclusions,
    count_question_types,
)

logger = logging.getLogger(__name__)


# ============================================================================
# ROUTE REGISTRATION
# ============================================================================

def register_qc_routes(bp):
    """Register Q&C extraction and visualization routes on the blueprint."""

    @bp.route('/case/<int:case_id>/entity_graph')
    def get_entity_graph_api(case_id):
        """API endpoint returning entity graph data for D3.js visualization."""
        try:
            show_type_hubs = request.args.get('type_hubs', 'false').lower() == 'true'
            result = build_entity_graph(case_id, show_type_hubs=show_type_hubs)
            return jsonify(result)
        except Exception as e:
            logger.error(f"Error getting entity graph for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/qc_flow')
    def get_qc_flow_api(case_id):
        """API endpoint returning Question-Conclusion flow data for Sankey visualization."""
        try:
            result = build_qc_flow(case_id)
            return jsonify(result)
        except Exception as e:
            logger.error(f"Error building Q-C flow for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e),
                'questions': [],
                'conclusions': [],
                'links': []
            }), 500

    @bp.route('/case/<int:case_id>/extract_qc_unified', methods=['POST'])
    @auth_required_for_llm
    def extract_qc_unified(case_id):
        """Part B UNIFIED: Extract Questions, Conclusions, and Link them atomically."""
        try:
            case = Document.query.get_or_404(case_id)

            # Get provisions for context
            provisions_records = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='code_provision_reference'
            ).all()
            provisions = [r.rdf_json_ld for r in provisions_records if r.rdf_json_ld]

            questions, conclusions = extract_questions_conclusions(case_id, case, provisions)

            # Get prompts for display
            q_prompt = ExtractionPrompt.query.filter_by(
                case_id=case_id,
                concept_type='ethical_question'
            ).order_by(ExtractionPrompt.created_at.desc()).first()

            c_prompt = ExtractionPrompt.query.filter_by(
                case_id=case_id,
                concept_type='ethical_conclusion'
            ).order_by(ExtractionPrompt.created_at.desc()).first()

            linked_conclusions = [c for c in conclusions if c.get('answers_questions', [])]

            from app.routes.scenario_pipeline.step4.helpers import _count_conclusion_types_from_list

            return jsonify({
                'success': True,
                'prompt': f"Questions extraction:\n{q_prompt.prompt_text[:500] if q_prompt else 'N/A'}...\n\nConclusions extraction:\n{c_prompt.prompt_text[:500] if c_prompt else 'N/A'}...",
                'raw_llm_response': f"Questions: {len(questions)} extracted\nConclusions: {len(conclusions)} extracted\nLinks: {len(linked_conclusions)} conclusions linked to questions",
                'status_messages': [
                    f"Extracted {len(questions)} questions (board_explicit + analytical)",
                    f"Extracted {len(conclusions)} conclusions (board_explicit + analytical)",
                    f"Linked {len(linked_conclusions)} conclusions to questions"
                ],
                'result': {
                    'questions': len(questions),
                    'conclusions': len(conclusions),
                    'links': len(linked_conclusions),
                    'question_types': count_question_types(questions),
                    'conclusion_types': _count_conclusion_types_from_list(conclusions)
                },
                'metadata': {
                    'q_model': q_prompt.llm_model if q_prompt else 'unknown',
                    'c_model': c_prompt.llm_model if c_prompt else 'unknown',
                    'timestamp': q_prompt.created_at.isoformat() if q_prompt else None
                }
            })

        except Exception as e:
            logger.error(f"Error in unified Q+C extraction for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/extract_qc_unified_stream', methods=['POST'])
    @auth_required_for_llm
    def extract_qc_unified_streaming(case_id):
        """Part B UNIFIED with SSE streaming: Extract Questions, Conclusions, and Link them."""
        from app.routes.scenario_pipeline.step4.helpers import get_all_case_entities

        def sse_msg(data):
            return f"data: {json_mod.dumps(data)}\n\n"

        def generate():
            try:
                case = Document.query.get_or_404(case_id)

                yield sse_msg({'stage': 'START', 'progress': 0, 'messages': ['Starting Q&C extraction...']})

                # Load provisions
                yield sse_msg({'stage': 'LOADING_PROVISIONS', 'progress': 5, 'messages': ['Loading code provisions...']})
                provisions_records = TemporaryRDFStorage.query.filter_by(
                    case_id=case_id,
                    extraction_type='code_provision_reference'
                ).all()
                provisions = [r.rdf_json_ld for r in provisions_records if r.rdf_json_ld]
                yield sse_msg({'stage': 'PROVISIONS_LOADED', 'progress': 8, 'messages': [f'Loaded {len(provisions)} provisions']})

                # Get all entities for context
                yield sse_msg({'stage': 'LOADING_ENTITIES', 'progress': 10, 'messages': ['Loading extracted entities...']})
                all_entities = get_all_case_entities(case_id)
                entity_count = sum(len(v) for v in all_entities.values() if isinstance(v, list))
                yield sse_msg({'stage': 'ENTITIES_LOADED', 'progress': 15, 'messages': [f'Loaded {entity_count} entities']})

                # Get section text
                questions_text = ""
                conclusions_text = ""
                if case.doc_metadata and 'sections_dual' in case.doc_metadata:
                    sections = case.doc_metadata['sections_dual']
                    if 'question' in sections:
                        q_data = sections['question']
                        questions_text = q_data.get('text', '') if isinstance(q_data, dict) else str(q_data)
                    if 'conclusion' in sections:
                        c_data = sections['conclusion']
                        conclusions_text = c_data.get('text', '') if isinstance(c_data, dict) else str(c_data)

                # Clear old Q&C
                yield sse_msg({'stage': 'CLEARING', 'progress': 18, 'messages': ['Clearing previous Q&C extractions...']})
                TemporaryRDFStorage.query.filter_by(
                    case_id=case_id,
                    extraction_type='ethical_question'
                ).delete(synchronize_session=False)
                TemporaryRDFStorage.query.filter_by(
                    case_id=case_id,
                    extraction_type='ethical_conclusion'
                ).delete(synchronize_session=False)
                db.session.commit()

                llm_client = get_llm_client()

                # Get facts section for context
                facts_text = ""
                if case.doc_metadata and 'sections_dual' in case.doc_metadata:
                    sections = case.doc_metadata['sections_dual']
                    if 'facts' in sections:
                        f_data = sections['facts']
                        facts_text = f_data.get('text', '') if isinstance(f_data, dict) else str(f_data)

                # Extract questions (with analytical generation)
                yield sse_msg({'stage': 'EXTRACTING_QUESTIONS', 'progress': 25, 'messages': ['Stage 1: Extracting Board questions...']})
                question_analyzer = QuestionAnalyzer(llm_client)

                logger.info(f"Calling extract_questions_with_analysis with {len(all_entities)} entity types")

                questions_result = question_analyzer.extract_questions_with_analysis(
                    questions_text=questions_text,
                    all_entities=all_entities,
                    code_provisions=provisions,
                    case_facts=facts_text,
                    case_conclusion=conclusions_text
                )

                for q_type in ['board_explicit', 'implicit', 'principle_tension', 'theoretical', 'counterfactual']:
                    count = len(questions_result.get(q_type, []))
                    logger.info(f"  {q_type}: {count} questions")

                yield sse_msg({'stage': 'QUESTIONS_STAGE1', 'progress': 35, 'messages': [f'Stage 1 complete: {len(questions_result.get("board_explicit", []))} Board questions']})
                yield sse_msg({'stage': 'QUESTIONS_STAGE2', 'progress': 40, 'messages': [f'Stage 2: Generated {len(questions_result.get("implicit", []))} implicit, {len(questions_result.get("principle_tension", []))} principle_tension, {len(questions_result.get("theoretical", []))} theoretical, {len(questions_result.get("counterfactual", []))} counterfactual']})

                # Flatten all question types into single list
                questions = []
                for q_type in ['board_explicit', 'implicit', 'principle_tension', 'theoretical', 'counterfactual']:
                    for q in questions_result.get(q_type, []):
                        q_dict = question_analyzer._question_to_dict(q) if hasattr(q, 'question_number') else q
                        questions.append(q_dict)

                board_count = len(questions_result.get('board_explicit', []))
                analytical_count = len(questions) - board_count
                q_messages = [f'Total: {board_count} Board + {analytical_count} analytical = {len(questions)} questions']
                if getattr(question_analyzer, 'analytical_failed', False):
                    q_messages.append('WARNING: Analytical question generation failed after retries')
                elif analytical_count == 0 and board_count > 0:
                    q_messages.append('WARNING: No analytical questions were generated')
                yield sse_msg({'stage': 'QUESTIONS_DONE', 'progress': 45, 'messages': q_messages})

                # Get board questions for conclusion context
                board_questions = [question_analyzer._question_to_dict(q) if hasattr(q, 'question_number') else q
                                  for q in questions_result.get('board_explicit', [])]
                analytical_questions = [q for q in questions if q.get('question_type') != 'board_explicit']

                # Extract conclusions (with analytical generation)
                yield sse_msg({'stage': 'EXTRACTING_CONCLUSIONS', 'progress': 50, 'messages': ['Extracting Board conclusions + generating analytical conclusions...']})
                conclusion_analyzer = ConclusionAnalyzer(llm_client)
                conclusions_result = conclusion_analyzer.extract_conclusions_with_analysis(
                    conclusions_text=conclusions_text,
                    all_entities=all_entities,
                    code_provisions=provisions,
                    board_questions=board_questions,
                    analytical_questions=analytical_questions,
                    case_facts=facts_text
                )

                # Flatten all conclusion types into single list
                conclusions = []
                for c_type in ['board_explicit', 'analytical_extension', 'question_response', 'principle_synthesis']:
                    for c in conclusions_result.get(c_type, []):
                        c_dict = conclusion_analyzer._conclusion_to_dict(c) if hasattr(c, 'conclusion_number') else c
                        conclusions.append(c_dict)

                board_c_count = len(conclusions_result.get('board_explicit', []))
                analytical_c_count = len(conclusions) - board_c_count
                c_messages = [f'Extracted {board_c_count} Board + {analytical_c_count} analytical = {len(conclusions)} total conclusions']
                if getattr(conclusion_analyzer, 'analytical_failed', False):
                    c_messages.append('WARNING: Analytical conclusion generation failed after retries')
                elif analytical_c_count == 0 and board_c_count > 0:
                    c_messages.append('WARNING: No analytical conclusions were generated')
                yield sse_msg({'stage': 'CONCLUSIONS_DONE', 'progress': 70, 'messages': c_messages})

                # Link Q to C
                yield sse_msg({'stage': 'LINKING', 'progress': 75, 'messages': ['Linking questions to conclusions...']})
                linker = QuestionConclusionLinker(llm_client)
                qc_links = linker.link_questions_to_conclusions(questions, conclusions)
                conclusions = linker.apply_links_to_conclusions(conclusions, qc_links)
                yield sse_msg({'stage': 'LINKING_DONE', 'progress': 85, 'messages': [f'Created {len(qc_links)} Q-C links']})

                # Store everything
                yield sse_msg({'stage': 'STORING', 'progress': 88, 'messages': ['Storing extractions...']})
                session_id = str(uuid.uuid4())

                # Store questions
                for question in questions:
                    rdf_entity = TemporaryRDFStorage(
                        case_id=case_id,
                        extraction_session_id=session_id,
                        extraction_type='ethical_question',
                        storage_type='individual',
                        entity_type='questions',
                        entity_label=f"Question_{question['question_number']}",
                        entity_definition=question['question_text'],
                        rdf_json_ld={
                            '@type': 'proeth-case:EthicalQuestion',
                            'questionNumber': question['question_number'],
                            'questionText': question['question_text'],
                            'questionType': question.get('question_type', 'unknown'),
                            'mentionedEntities': question.get('mentioned_entities', {}),
                            'relatedProvisions': question.get('related_provisions', []),
                            'extractionReasoning': question.get('extraction_reasoning', '')
                        },
                        is_selected=True
                    )
                    db.session.add(rdf_entity)

                # Store conclusions
                for conclusion in conclusions:
                    rdf_entity = TemporaryRDFStorage(
                        case_id=case_id,
                        extraction_session_id=session_id,
                        extraction_type='ethical_conclusion',
                        storage_type='individual',
                        entity_type='conclusions',
                        entity_label=f"Conclusion_{conclusion['conclusion_number']}",
                        entity_definition=conclusion['conclusion_text'],
                        rdf_json_ld={
                            '@type': 'proeth-case:EthicalConclusion',
                            'conclusionNumber': conclusion['conclusion_number'],
                            'conclusionText': conclusion['conclusion_text'],
                            'conclusionType': conclusion.get('conclusion_type', 'unknown'),
                            'mentionedEntities': conclusion.get('mentioned_entities', {}),
                            'citedProvisions': conclusion.get('cited_provisions', []),
                            'answersQuestions': conclusion.get('answers_questions', []),
                            'extractionReasoning': conclusion.get('extraction_reasoning', '')
                        },
                        is_selected=True
                    )
                    db.session.add(rdf_entity)

                db.session.commit()

                # Build formatted results for display
                results_text = f"Questions & Conclusions Extraction\n"
                results_text += "=" * 40 + "\n\n"
                results_text += f"QUESTIONS ({len(questions)}):\n"
                for q in questions:
                    q_num = q.get('question_number', '?')
                    q_type = q.get('question_type', 'unknown')
                    q_text = q.get('question_text', '')[:80]
                    results_text += f"  Q{q_num} [{q_type}]: {q_text}...\n" if len(q.get('question_text', '')) > 80 else f"  Q{q_num} [{q_type}]: {q_text}\n"
                results_text += f"\nCONCLUSIONS ({len(conclusions)}):\n"
                for c in conclusions:
                    c_num = c.get('conclusion_number', '?')
                    c_type = c.get('conclusion_type', 'unknown')
                    c_text = c.get('conclusion_text', '')[:80]
                    answers = c.get('answers_questions', [])
                    answers_str = f" -> answers Q{answers}" if answers else ""
                    results_text += f"  C{c_num} [{c_type}]{answers_str}: {c_text}...\n" if len(c.get('conclusion_text', '')) > 80 else f"  C{c_num} [{c_type}]{answers_str}: {c_text}\n"

                status_messages = [
                    f"Extracted {len(questions)} questions (board_explicit + analytical)",
                    f"Extracted {len(conclusions)} conclusions (board_explicit + analytical)",
                    f"Linked {len(qc_links)} Q-C pairs"
                ]

                # Capture actual LLM prompts from analyzers
                actual_prompts = []
                if question_analyzer.last_prompt:
                    actual_prompts.append("=== QUESTIONS EXTRACTION PROMPT ===\n" + question_analyzer.last_prompt)
                if conclusion_analyzer.last_prompt:
                    actual_prompts.append("=== CONCLUSIONS EXTRACTION PROMPT ===\n" + conclusion_analyzer.last_prompt)
                combined_prompt = "\n\n".join(actual_prompts) if actual_prompts else "No prompts captured"

                yield sse_msg({
                    'stage': 'COMPLETE',
                    'progress': 100,
                    'messages': [
                        f'Extraction complete!',
                        f'Questions: {len(questions)}',
                        f'Conclusions: {len(conclusions)}',
                        f'Links: {len(qc_links)}'
                    ],
                    'status_messages': status_messages,
                    'prompt': combined_prompt,
                    'raw_llm_response': results_text,
                    'result': {
                        'questions': len(questions),
                        'conclusions': len(conclusions),
                        'links': len(qc_links)
                    }
                })

            except Exception as e:
                logger.error(f"Error in streaming Q+C extraction for case {case_id}: {e}")
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
