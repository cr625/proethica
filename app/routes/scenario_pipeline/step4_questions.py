"""
Step 4 Question Extraction Routes

Handles ethical question extraction with entity grounding:
- Individual question extraction (non-streaming)
- Streaming question extraction with real-time progress
- Analytical question generation (implicit, principle tensions, etc.)
"""

import logging
import uuid
from datetime import datetime
from flask import jsonify, Response, stream_with_context

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.utils.llm_utils import get_llm_client
from app.utils.environment_auth import auth_required_for_llm

from app.services.question_analyzer import QuestionAnalyzer
from app.services.entity_grounding_service import EntityGroundingService

logger = logging.getLogger(__name__)


def register_question_routes(bp, get_all_case_entities):
    """Register question extraction routes on the blueprint.

    Args:
        bp: The Flask Blueprint to register routes on
        get_all_case_entities: Function to get all entities for a case
    """

    @bp.route('/case/<int:case_id>/extract_questions', methods=['POST'])
    @auth_required_for_llm
    def extract_questions_individual(case_id):
        """
        Extract ethical questions individually (Part B - questions only).
        Returns prompt and response for UI display.
        """
        try:
            case = Document.query.get_or_404(case_id)

            # Get question section text
            questions_text = ""
            if case.doc_metadata and 'sections_dual' in case.doc_metadata:
                q_data = case.doc_metadata['sections_dual'].get('question', {})
                questions_text = q_data.get('text', '') if isinstance(q_data, dict) else str(q_data)

            if not questions_text:
                return jsonify({
                    'success': False,
                    'error': 'No question section found in case'
                }), 400

            # Clear existing questions
            TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='ethical_question'
            ).delete(synchronize_session=False)
            db.session.commit()

            # Get all entities for context
            all_entities = get_all_case_entities(case_id)

            # Load provisions for linking
            provisions_objs = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='code_provision_reference'
            ).all()

            provisions = [
                {
                    'code_provision': p.rdf_json_ld.get('codeProvision', p.entity_label) if p.rdf_json_ld else p.entity_label,
                    'provision_text': p.entity_definition
                }
                for p in provisions_objs
            ]

            # Extract questions
            llm_client = get_llm_client()
            analyzer = QuestionAnalyzer(llm_client)
            questions = analyzer.extract_questions(
                questions_text=questions_text,
                all_entities=all_entities,
                code_provisions=provisions
            )

            # Store questions
            session_id = str(uuid.uuid4())

            # Save extraction prompt
            extraction_prompt = ExtractionPrompt(
                case_id=case_id,
                concept_type='ethical_question',
                step_number=4,
                section_type='questions',
                prompt_text=analyzer.last_prompt or 'Question extraction',
                llm_model='claude-sonnet-4-20250514',
                extraction_session_id=session_id,
                raw_response=analyzer.last_response or '',
                results_summary={'total_questions': len(questions)},
                is_active=True,
                times_used=1,
                created_at=datetime.utcnow(),
                last_used_at=datetime.utcnow()
            )
            db.session.add(extraction_prompt)

            # Store question entities
            for q in questions:
                rdf_entity = TemporaryRDFStorage(
                    case_id=case_id,
                    extraction_session_id=session_id,
                    extraction_type='ethical_question',
                    storage_type='individual',
                    entity_type='questions',
                    entity_label=q.get('label', f"Question_{q.get('question_number', 0)}"),
                    entity_definition=q.get('question_text', ''),
                    rdf_json_ld={
                        '@type': 'proeth-case:EthicalQuestion',
                        'label': q.get('label', ''),
                        'questionNumber': q.get('question_number', 0),
                        'questionText': q.get('question_text', ''),
                        'relatedProvisions': q.get('related_provisions', []),
                        'mentionedEntities': q.get('mentioned_entities', [])
                    },
                    is_selected=True
                )
                db.session.add(rdf_entity)

            db.session.commit()

            # Build status messages for UI display
            status_messages = []
            for q in questions:
                q_num = q.get('question_number', 0)
                provisions = q.get('related_provisions', [])
                entities = q.get('mentioned_entities', [])
                status_messages.append(f"Question {q_num}: {len(provisions)} provisions, {len(entities)} entities mentioned")

            return jsonify({
                'success': True,
                'prompt': analyzer.last_prompt or 'Question extraction',
                'raw_llm_response': analyzer.last_response or '',
                'status_messages': status_messages,
                'result': {
                    'count': len(questions),
                    'questions': [
                        {
                            'number': q.get('question_number', 0),
                            'text': q.get('question_text', '')[:200] + '...' if len(q.get('question_text', '')) > 200 else q.get('question_text', ''),
                            'provisions': q.get('related_provisions', [])
                        }
                        for q in questions
                    ]
                },
                'metadata': {
                    'model': 'claude-sonnet-4-20250514',
                    'timestamp': datetime.utcnow().isoformat()
                }
            })

        except Exception as e:
            logger.error(f"Error extracting questions for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/extract_questions_stream', methods=['POST'])
    @auth_required_for_llm
    def extract_questions_streaming(case_id):
        """
        Extract ethical questions with SSE streaming for real-time progress.
        Now includes analytical question generation (implicit, principle tensions, etc.)
        """
        import json

        def sse_msg(data):
            return f"data: {json.dumps(data)}\n\n"

        def generate():
            try:
                case = Document.query.get_or_404(case_id)

                yield sse_msg({'stage': 'START', 'progress': 5, 'messages': ['Starting question analysis...']})

                # Get question section text
                questions_text = ""
                facts_text = ""
                conclusion_text = ""
                if case.doc_metadata and 'sections_dual' in case.doc_metadata:
                    sections = case.doc_metadata['sections_dual']
                    q_data = sections.get('question', {})
                    questions_text = q_data.get('text', '') if isinstance(q_data, dict) else str(q_data)
                    f_data = sections.get('facts', {})
                    facts_text = f_data.get('text', '') if isinstance(f_data, dict) else str(f_data)
                    c_data = sections.get('conclusion', {})
                    conclusion_text = c_data.get('text', '') if isinstance(c_data, dict) else str(c_data)

                if not questions_text:
                    yield sse_msg({'stage': 'ERROR', 'progress': 100, 'messages': ['No question section found in case'], 'error': True})
                    return

                yield sse_msg({'stage': 'FOUND_SECTION', 'progress': 8, 'messages': ['Found question section in case']})

                # Clear existing questions
                TemporaryRDFStorage.query.filter_by(
                    case_id=case_id,
                    extraction_type='ethical_question'
                ).delete(synchronize_session=False)
                db.session.commit()

                yield sse_msg({'stage': 'CLEARED', 'progress': 10, 'messages': ['Cleared previous question extractions']})

                # Get all entities for context
                yield sse_msg({'stage': 'LOADING_ENTITIES', 'progress': 15, 'messages': ['Loading extracted entities for context...']})
                all_entities = get_all_case_entities(case_id)

                entity_count = sum(len(v) for v in all_entities.values() if isinstance(v, list))
                yield sse_msg({'stage': 'ENTITIES_LOADED', 'progress': 20, 'messages': [f'Loaded {entity_count} entities for context']})

                # Load provisions for linking
                yield sse_msg({'stage': 'LOADING_PROVISIONS', 'progress': 22, 'messages': ['Loading code provisions...']})
                provisions_objs = TemporaryRDFStorage.query.filter_by(
                    case_id=case_id,
                    extraction_type='code_provision_reference'
                ).all()

                provisions = [
                    {
                        'code_provision': p.rdf_json_ld.get('codeProvision', p.entity_label) if p.rdf_json_ld else p.entity_label,
                        'provision_text': p.entity_definition
                    }
                    for p in provisions_objs
                ]
                yield sse_msg({'stage': 'PROVISIONS_LOADED', 'progress': 25, 'messages': [f'Loaded {len(provisions)} code provisions']})

                # STAGE 1: Extract Board's explicit questions
                yield sse_msg({'stage': 'EXTRACTING_BOARD', 'progress': 30, 'messages': ["Stage 1: Extracting Board's explicit questions..."]})

                llm_client = get_llm_client()
                analyzer = QuestionAnalyzer(llm_client)

                # Use the enhanced analysis method
                all_questions = analyzer.extract_questions_with_analysis(
                    questions_text=questions_text,
                    all_entities=all_entities,
                    code_provisions=provisions,
                    case_facts=facts_text,
                    case_conclusion=conclusion_text
                )

                board_questions = all_questions.get('board_explicit', [])
                stage1_source = all_questions.get('stage1_source', 'unknown')
                stage1_used_llm = all_questions.get('stage1_used_llm', False)

                # Report how Stage 1 was performed
                if stage1_used_llm:
                    stage1_msg = f"Extracted {len(board_questions)} Board questions via LLM (parsing failed)"
                else:
                    stage1_msg = f"Parsed {len(board_questions)} Board questions from imported text (no LLM needed)"
                yield sse_msg({'stage': 'BOARD_EXTRACTED', 'progress': 50, 'messages': [stage1_msg]})

                # STAGE 2: Generate analytical questions
                yield sse_msg({'stage': 'GENERATING_ANALYTICAL', 'progress': 55, 'messages': ['Stage 2: Generating analytical questions...']})

                implicit = all_questions.get('implicit', [])
                principle_tension = all_questions.get('principle_tension', [])
                theoretical = all_questions.get('theoretical', [])
                counterfactual = all_questions.get('counterfactual', [])

                analytical_count = len(implicit) + len(principle_tension) + len(theoretical) + len(counterfactual)
                yield sse_msg({'stage': 'ANALYTICAL_GENERATED', 'progress': 70, 'messages': [
                    f'Generated {analytical_count} analytical questions:',
                    f'  - {len(implicit)} implicit questions',
                    f'  - {len(principle_tension)} principle tensions',
                    f'  - {len(theoretical)} theoretical framings',
                    f'  - {len(counterfactual)} counterfactual questions'
                ]})

                # Ground entity references in all questions
                yield sse_msg({'stage': 'GROUNDING', 'progress': 72, 'messages': ['Grounding entity references in questions...']})

                grounding_service = EntityGroundingService()

                def ground_question(q):
                    """Apply entity grounding to a question."""
                    result = grounding_service.ground_text(q.question_text, all_entities)
                    # Update question with grounding data
                    q.grounded_text = result.grounded_text
                    q.entity_mentions = [
                        {
                            'label': m.label,
                            'uri': m.uri,
                            'entity_type': m.entity_type,
                            'start': m.start,
                            'end': m.end,
                            'match_type': m.match_type,
                            'confidence': m.confidence,
                            'matched_text': m.matched_text
                        }
                        for m in result.entity_mentions
                    ]
                    q.involved_entities = result.involved_entities
                    q.grounding_stats = result.grounding_stats
                    return q

                # Ground all questions
                all_questions_to_ground = board_questions + implicit + principle_tension + theoretical + counterfactual
                total_grounded = 0
                grounding_stats_total = {'exact': 0, 'partial': 0, 'semantic': 0}

                for q in all_questions_to_ground:
                    ground_question(q)
                    total_grounded += 1
                    if hasattr(q, 'grounding_stats'):
                        grounding_stats_total['exact'] += q.grounding_stats.get('exact', 0)
                        grounding_stats_total['partial'] += q.grounding_stats.get('partial', 0)
                        grounding_stats_total['semantic'] += q.grounding_stats.get('semantic', 0)

                total_mentions = grounding_stats_total['exact'] + grounding_stats_total['partial'] + grounding_stats_total['semantic']
                yield sse_msg({
                    'stage': 'GROUNDING_COMPLETE',
                    'progress': 75,
                    'messages': [
                        f'Grounded {total_mentions} entity mentions in {total_grounded} questions',
                        f'  - {grounding_stats_total["exact"]} exact matches',
                        f'  - {grounding_stats_total["partial"]} partial matches'
                    ]
                })

                # Store all questions
                yield sse_msg({'stage': 'STORING', 'progress': 76, 'messages': ['Storing all questions in database...']})
                session_id = str(uuid.uuid4())

                # Save extraction prompt
                extraction_prompt = ExtractionPrompt(
                    case_id=case_id,
                    concept_type='ethical_question',
                    step_number=4,
                    section_type='questions',
                    prompt_text=analyzer.last_prompt or 'Question analysis',
                    llm_model='claude-sonnet-4-20250514',
                    extraction_session_id=session_id,
                    raw_response=analyzer.last_response or '',
                    results_summary={
                        'board_explicit': len(board_questions),
                        'implicit': len(implicit),
                        'principle_tension': len(principle_tension),
                        'theoretical': len(theoretical),
                        'counterfactual': len(counterfactual)
                    },
                    is_active=True,
                    times_used=1,
                    created_at=datetime.utcnow(),
                    last_used_at=datetime.utcnow()
                )
                db.session.add(extraction_prompt)

                # Helper to store questions
                def store_question(q, q_type_label):
                    rdf_entity = TemporaryRDFStorage(
                        case_id=case_id,
                        extraction_session_id=session_id,
                        extraction_type='ethical_question',
                        storage_type='individual',
                        entity_type='questions',
                        entity_label=f"Q{q.question_number}_{q.question_type}",
                        entity_definition=q.question_text,
                        rdf_json_ld={
                            '@type': 'proeth-case:EthicalQuestion',
                            'questionNumber': q.question_number,
                            'questionText': q.question_text,
                            'questionType': q.question_type,
                            'relatedProvisions': q.related_provisions,
                            'mentionedEntities': q.mentioned_entities,
                            'mentionedEntityUris': q.mentioned_entity_uris,
                            'extractionReasoning': q.extraction_reasoning,
                            'source': q.source,
                            'sourceQuestion': q.source_question,
                            'ethicalFramework': q.ethical_framework,
                            # Entity grounding data
                            'groundedText': getattr(q, 'grounded_text', q.question_text),
                            'entityMentions': getattr(q, 'entity_mentions', []),
                            'involvedEntities': getattr(q, 'involved_entities', {}),
                            'groundingStats': getattr(q, 'grounding_stats', {})
                        },
                        is_selected=True
                    )
                    db.session.add(rdf_entity)

                # Store all question types
                all_to_store = [
                    (board_questions, 'board_explicit'),
                    (implicit, 'implicit'),
                    (principle_tension, 'principle_tension'),
                    (theoretical, 'theoretical'),
                    (counterfactual, 'counterfactual')
                ]

                total_stored = 0
                total_questions = len(board_questions) + analytical_count
                for questions, q_type in all_to_store:
                    for q in questions:
                        store_question(q, q_type)
                        total_stored += 1
                        progress = 75 + int((total_stored / max(total_questions, 1)) * 20)
                        yield sse_msg({'stage': 'STORING_QUESTION', 'progress': progress,
                                       'messages': [f'Stored {total_stored}/{total_questions} questions']})

                db.session.commit()

                yield sse_msg({'stage': 'STORED', 'progress': 98, 'messages': ['All questions stored successfully']})

                # Build status messages
                source_note = "(from import)" if stage1_source == 'imported' else "(LLM extracted)"
                status_messages = [
                    # Input context
                    f"Input: {len(provisions)} code provisions, {entity_count} entities",
                    # Stage 1 results
                    f"Stage 1 - Board Questions: {len(board_questions)} {source_note}",
                    # Stage 2 results
                    f"Stage 2 - Implicit Questions: {len(implicit)}",
                    f"Stage 2 - Principle Tensions: {len(principle_tension)}",
                    f"Stage 2 - Theoretical Framings: {len(theoretical)}",
                    f"Stage 2 - Counterfactual Questions: {len(counterfactual)}",
                    # Grounding summary
                    f"Entity Grounding: {total_mentions} mentions ({grounding_stats_total['exact']} exact, {grounding_stats_total['partial']} partial)"
                ]

                yield sse_msg({
                    'stage': 'COMPLETE',
                    'progress': 100,
                    'messages': [f'Analysis complete: {total_questions} questions total'],
                    'status_messages': status_messages,
                    'prompt': analyzer.last_prompt or 'Question analysis',
                    'raw_llm_response': analyzer.last_response or '',
                    'result': {
                        'count': total_questions,
                        'board_explicit': len(board_questions),
                        'analytical': analytical_count,
                        'stage1_source': stage1_source,
                        'stage1_used_llm': stage1_used_llm,
                        'by_type': {
                            'board_explicit': len(board_questions),
                            'implicit': len(implicit),
                            'principle_tension': len(principle_tension),
                            'theoretical': len(theoretical),
                            'counterfactual': len(counterfactual)
                        },
                        'grounding': {
                            'total_mentions': total_mentions,
                            'exact': grounding_stats_total['exact'],
                            'partial': grounding_stats_total['partial']
                        }
                    },
                    'input_context': {
                        'provisions': len(provisions),
                        'entities': entity_count
                    }
                })

            except Exception as e:
                logger.error(f"Streaming questions error: {e}")
                import traceback
                traceback.print_exc()
                yield sse_msg({'stage': 'ERROR', 'progress': 100, 'messages': [f'Error: {str(e)}'], 'error': True})

        return Response(stream_with_context(generate()), mimetype='text/event-stream')
