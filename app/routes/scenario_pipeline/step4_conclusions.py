"""
Step 4 Conclusion Extraction Routes

Handles board conclusion extraction with entity grounding:
- Board explicit conclusions
- Analytical extensions
- Question responses
- Principle syntheses
"""

import logging
import uuid
from datetime import datetime
from flask import jsonify, Response, stream_with_context

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.utils.llm_utils import get_llm_client
from app.utils.environment_auth import auth_required_for_llm

from app.services.conclusion_analyzer import ConclusionAnalyzer
from app.services.entity_grounding_service import EntityGroundingService

logger = logging.getLogger(__name__)


def register_conclusion_routes(bp, get_all_case_entities):
    """Register conclusion extraction routes on the blueprint.

    Args:
        bp: The Flask Blueprint to register routes on
        get_all_case_entities: Function to get all entities for a case
    """

    @bp.route('/case/<int:case_id>/extract_conclusions', methods=['POST'])
    @auth_required_for_llm
    def extract_conclusions_individual(case_id):
        """
        Extract board conclusions individually (Part B - conclusions only).
        Now includes analytical conclusion generation.
        Returns prompt and response for UI display.
        """
        try:
            case = Document.query.get_or_404(case_id)

            # Get conclusion and facts section text
            conclusions_text = ""
            facts_text = ""
            if case.doc_metadata and 'sections_dual' in case.doc_metadata:
                c_data = case.doc_metadata['sections_dual'].get('conclusion', {})
                conclusions_text = c_data.get('text', '') if isinstance(c_data, dict) else str(c_data)
                f_data = case.doc_metadata['sections_dual'].get('facts', {})
                facts_text = f_data.get('text', '') if isinstance(f_data, dict) else str(f_data)

            if not conclusions_text:
                return jsonify({
                    'success': False,
                    'error': 'No conclusion section found in case'
                }), 400

            # Clear existing conclusions
            TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='ethical_conclusion'
            ).delete(synchronize_session=False)
            db.session.commit()

            # Load all entities for context
            all_entities = get_all_case_entities(case_id)

            # Load questions (both board and analytical)
            questions_objs = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='ethical_question'
            ).all()

            board_questions = []
            analytical_questions = []
            for q in questions_objs:
                q_data = {
                    'question_number': q.rdf_json_ld.get('questionNumber', 0) if q.rdf_json_ld else 0,
                    'question_text': q.entity_definition,
                    'question_type': q.rdf_json_ld.get('questionType', 'unknown') if q.rdf_json_ld else 'unknown'
                }
                if q.rdf_json_ld and q.rdf_json_ld.get('questionType') == 'board_explicit':
                    board_questions.append(q_data)
                else:
                    analytical_questions.append(q_data)

            # Load provisions
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

            # Extract conclusions with analysis
            llm_client = get_llm_client()
            analyzer = ConclusionAnalyzer(llm_client)
            all_conclusions = analyzer.extract_conclusions_with_analysis(
                conclusions_text=conclusions_text,
                all_entities=all_entities,
                code_provisions=provisions,
                board_questions=board_questions,
                analytical_questions=analytical_questions,
                case_facts=facts_text
            )

            board_conclusions = all_conclusions.get('board_explicit', [])
            analytical_extension = all_conclusions.get('analytical_extension', [])
            question_response = all_conclusions.get('question_response', [])
            principle_synthesis = all_conclusions.get('principle_synthesis', [])
            stage1_source = all_conclusions.get('stage1_source', 'unknown')
            stage1_used_llm = all_conclusions.get('stage1_used_llm', False)

            # Ground entity references in all conclusions
            grounding_service = EntityGroundingService()

            def ground_conclusion(c):
                """Apply entity grounding to a conclusion."""
                result = grounding_service.ground_text(c.conclusion_text, all_entities)
                c.grounded_text = result.grounded_text
                c.entity_mentions = [
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
                c.involved_entities = result.involved_entities
                c.grounding_stats = result.grounding_stats
                return c

            # Ground all conclusions
            all_conclusions_to_ground = board_conclusions + analytical_extension + question_response + principle_synthesis
            for c in all_conclusions_to_ground:
                ground_conclusion(c)

            # Store conclusions
            session_id = str(uuid.uuid4())

            # Save extraction prompt
            extraction_prompt = ExtractionPrompt(
                case_id=case_id,
                concept_type='ethical_conclusion',
                step_number=4,
                section_type='conclusions',  # plural to match DB constraint
                prompt_text=analyzer.last_prompt or 'Conclusion extraction',
                llm_model='claude-sonnet-4-20250514',
                extraction_session_id=session_id,
                raw_response=analyzer.last_response or '',
                results_summary={
                    'board_explicit': len(board_conclusions),
                    'analytical_extension': len(analytical_extension),
                    'question_response': len(question_response),
                    'principle_synthesis': len(principle_synthesis),
                    'stage1_source': stage1_source
                },
                is_active=True,
                times_used=1,
                created_at=datetime.utcnow(),
                last_used_at=datetime.utcnow()
            )
            db.session.add(extraction_prompt)

            # Helper to store conclusions
            def store_conclusion(c):
                rdf_entity = TemporaryRDFStorage(
                    case_id=case_id,
                    extraction_session_id=session_id,
                    extraction_type='ethical_conclusion',
                    storage_type='individual',
                    entity_type='conclusions',
                    entity_label=f"C{c.conclusion_number}_{c.conclusion_type}",
                    entity_definition=c.conclusion_text,
                    rdf_json_ld={
                        '@type': 'proeth-case:EthicalConclusion',
                        'conclusionNumber': c.conclusion_number,
                        'conclusionText': c.conclusion_text,
                        'conclusionType': c.conclusion_type,
                        'boardConclusionType': c.board_conclusion_type,
                        'mentionedEntities': c.mentioned_entities,
                        'mentionedEntityUris': c.mentioned_entity_uris,
                        'citedProvisions': c.cited_provisions,
                        'extractionReasoning': c.extraction_reasoning,
                        'source': c.source,
                        'answersQuestions': c.answers_questions,
                        'sourceConclusion': c.source_conclusion,
                        'relatedAnalyticalQuestions': c.related_analytical_questions,
                        # Entity grounding data
                        'groundedText': getattr(c, 'grounded_text', c.conclusion_text),
                        'entityMentions': getattr(c, 'entity_mentions', []),
                        'involvedEntities': getattr(c, 'involved_entities', {}),
                        'groundingStats': getattr(c, 'grounding_stats', {})
                    },
                    is_selected=True
                )
                db.session.add(rdf_entity)

            # Store all conclusion types
            all_to_store = [
                board_conclusions,
                analytical_extension,
                question_response,
                principle_synthesis
            ]
            for conclusions in all_to_store:
                for c in conclusions:
                    store_conclusion(c)

            db.session.commit()

            total_conclusions = len(board_conclusions) + len(analytical_extension) + len(question_response) + len(principle_synthesis)

            # Compute grounding stats across all conclusions
            total_grounded = 0
            grounding_totals = {'exact': 0, 'partial': 0, 'semantic': 0}
            for c in all_conclusions_to_ground:
                if hasattr(c, 'grounding_stats'):
                    total_grounded += c.grounding_stats.get('total', 0)
                    grounding_totals['exact'] += c.grounding_stats.get('exact', 0)
                    grounding_totals['partial'] += c.grounding_stats.get('partial', 0)

            # Build status messages with context from 2B
            source_note = "(from import)" if stage1_source == 'imported' else "(LLM extracted)"
            status_messages = [
                # Input context from 2B
                f"Input: {len(board_questions)} Board questions, {len(analytical_questions)} analytical questions",
                f"Input: {len(provisions)} code provisions, {sum(len(e) for e in all_entities.values())} entities",
                # Stage 1 results
                f"Stage 1 - Board Conclusions: {len(board_conclusions)} {source_note}",
                # Stage 2 results
                f"Stage 2 - Analytical Extensions: {len(analytical_extension)}",
                f"Stage 2 - Question Responses: {len(question_response)}",
                f"Stage 2 - Principle Syntheses: {len(principle_synthesis)}",
                # Grounding summary
                f"Entity Grounding: {total_grounded} mentions ({grounding_totals['exact']} exact, {grounding_totals['partial']} partial)"
            ]

            # Add warning if no questions from 2B
            warnings = []
            if not board_questions and not analytical_questions:
                warnings.append("No questions found from Step 2B - run question extraction first for better analytical conclusions")

            return jsonify({
                'success': True,
                'prompt': analyzer.last_prompt or 'Conclusion extraction',
                'raw_llm_response': analyzer.last_response or '',
                'status_messages': status_messages,
                'warnings': warnings,
                'result': {
                    'count': total_conclusions,
                    'board_explicit': len(board_conclusions),
                    'analytical': len(analytical_extension) + len(question_response) + len(principle_synthesis),
                    'stage1_source': stage1_source,
                    'stage1_used_llm': stage1_used_llm,
                    'by_type': {
                        'board_explicit': len(board_conclusions),
                        'analytical_extension': len(analytical_extension),
                        'question_response': len(question_response),
                        'principle_synthesis': len(principle_synthesis)
                    },
                    'grounding': {
                        'total_mentions': total_grounded,
                        'exact': grounding_totals['exact'],
                        'partial': grounding_totals['partial']
                    }
                },
                'input_context': {
                    'board_questions': len(board_questions),
                    'analytical_questions': len(analytical_questions),
                    'provisions': len(provisions),
                    'entities': sum(len(e) for e in all_entities.values())
                },
                'metadata': {
                    'model': 'claude-sonnet-4-20250514',
                    'timestamp': datetime.utcnow().isoformat()
                }
            })

        except Exception as e:
            logger.error(f"Error extracting conclusions for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/extract_conclusions_stream', methods=['POST'])
    @auth_required_for_llm
    def extract_conclusions_streaming(case_id):
        """
        Extract board conclusions with SSE streaming for real-time progress.
        Now includes analytical conclusion generation (extensions, question responses, etc.)
        """
        import json

        def sse_msg(data):
            return f"data: {json.dumps(data)}\n\n"

        def generate():
            try:
                case = Document.query.get_or_404(case_id)

                yield sse_msg({'stage': 'START', 'progress': 5, 'messages': ['Starting conclusion analysis...']})

                # Get conclusion and facts section text
                conclusions_text = ""
                facts_text = ""
                if case.doc_metadata and 'sections_dual' in case.doc_metadata:
                    c_data = case.doc_metadata['sections_dual'].get('conclusion', {})
                    conclusions_text = c_data.get('text', '') if isinstance(c_data, dict) else str(c_data)
                    f_data = case.doc_metadata['sections_dual'].get('facts', {})
                    facts_text = f_data.get('text', '') if isinstance(f_data, dict) else str(f_data)

                if not conclusions_text:
                    yield sse_msg({'stage': 'ERROR', 'progress': 100, 'messages': ['No conclusion section found in case'], 'error': True})
                    return

                yield sse_msg({'stage': 'FOUND_SECTION', 'progress': 8, 'messages': ['Found conclusion section in case']})

                # Clear existing conclusions
                TemporaryRDFStorage.query.filter_by(
                    case_id=case_id,
                    extraction_type='ethical_conclusion'
                ).delete(synchronize_session=False)
                db.session.commit()

                yield sse_msg({'stage': 'CLEARED', 'progress': 10, 'messages': ['Cleared previous conclusion extractions']})

                # Get all entities for context
                yield sse_msg({'stage': 'LOADING_ENTITIES', 'progress': 15, 'messages': ['Loading extracted entities for context...']})
                all_entities = get_all_case_entities(case_id)

                entity_count = sum(len(v) for v in all_entities.values() if isinstance(v, list))
                yield sse_msg({'stage': 'ENTITIES_LOADED', 'progress': 20, 'messages': [f'Loaded {entity_count} entities for context']})

                # Load questions (both board and analytical)
                yield sse_msg({'stage': 'LOADING_QUESTIONS', 'progress': 22, 'messages': ['Loading questions from 2B...']})
                questions_objs = TemporaryRDFStorage.query.filter_by(
                    case_id=case_id,
                    extraction_type='ethical_question'
                ).all()

                board_questions = []
                analytical_questions = []
                for q in questions_objs:
                    q_data = {
                        'question_number': q.rdf_json_ld.get('questionNumber', 0) if q.rdf_json_ld else 0,
                        'question_text': q.entity_definition,
                        'question_type': q.rdf_json_ld.get('questionType', 'unknown') if q.rdf_json_ld else 'unknown'
                    }
                    if q.rdf_json_ld and q.rdf_json_ld.get('questionType') == 'board_explicit':
                        board_questions.append(q_data)
                    else:
                        analytical_questions.append(q_data)

                yield sse_msg({
                    'stage': 'QUESTIONS_LOADED',
                    'progress': 25,
                    'messages': [f'Loaded {len(board_questions)} board questions, {len(analytical_questions)} analytical questions']
                })

                # Load provisions
                yield sse_msg({'stage': 'LOADING_PROVISIONS', 'progress': 27, 'messages': ['Loading code provisions...']})
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
                yield sse_msg({'stage': 'PROVISIONS_LOADED', 'progress': 30, 'messages': [f'Loaded {len(provisions)} code provisions']})

                # STAGE 1: Extract Board's explicit conclusions
                yield sse_msg({'stage': 'EXTRACTING_BOARD', 'progress': 35, 'messages': ["Stage 1: Extracting Board's explicit conclusions..."]})

                llm_client = get_llm_client()
                analyzer = ConclusionAnalyzer(llm_client)

                # Use the enhanced analysis method
                all_conclusions = analyzer.extract_conclusions_with_analysis(
                    conclusions_text=conclusions_text,
                    all_entities=all_entities,
                    code_provisions=provisions,
                    board_questions=board_questions,
                    analytical_questions=analytical_questions,
                    case_facts=facts_text
                )

                board_conclusions = all_conclusions.get('board_explicit', [])
                analytical_extension = all_conclusions.get('analytical_extension', [])
                question_response = all_conclusions.get('question_response', [])
                principle_synthesis = all_conclusions.get('principle_synthesis', [])
                stage1_source = all_conclusions.get('stage1_source', 'unknown')
                stage1_used_llm = all_conclusions.get('stage1_used_llm', False)

                # Report how Stage 1 was performed
                if stage1_used_llm:
                    stage1_msg = f"Extracted {len(board_conclusions)} Board conclusions via LLM (parsing failed)"
                else:
                    stage1_msg = f"Parsed {len(board_conclusions)} Board conclusions from imported text (no LLM needed)"
                yield sse_msg({'stage': 'BOARD_EXTRACTED', 'progress': 50, 'messages': [stage1_msg]})

                # STAGE 2: Report analytical conclusions
                yield sse_msg({'stage': 'ANALYTICAL_GENERATED', 'progress': 55, 'messages': [
                    f'Stage 2: Generated analytical conclusions:',
                    f'  - {len(analytical_extension)} analytical extensions',
                    f'  - {len(question_response)} question responses',
                    f'  - {len(principle_synthesis)} principle syntheses'
                ]})

                # Ground entity references in all conclusions
                yield sse_msg({'stage': 'GROUNDING', 'progress': 60, 'messages': ['Grounding entity references in conclusions...']})

                grounding_service = EntityGroundingService()

                def ground_conclusion(c):
                    """Apply entity grounding to a conclusion."""
                    result = grounding_service.ground_text(c.conclusion_text, all_entities)
                    c.grounded_text = result.grounded_text
                    c.entity_mentions = [
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
                    c.involved_entities = result.involved_entities
                    c.grounding_stats = result.grounding_stats
                    return c

                # Ground all conclusions
                all_conclusions_to_ground = board_conclusions + analytical_extension + question_response + principle_synthesis
                total_grounded = 0
                grounding_stats_total = {'exact': 0, 'partial': 0, 'semantic': 0}

                for c in all_conclusions_to_ground:
                    ground_conclusion(c)
                    total_grounded += 1
                    if hasattr(c, 'grounding_stats'):
                        grounding_stats_total['exact'] += c.grounding_stats.get('exact', 0)
                        grounding_stats_total['partial'] += c.grounding_stats.get('partial', 0)
                        grounding_stats_total['semantic'] += c.grounding_stats.get('semantic', 0)

                total_mentions = grounding_stats_total['exact'] + grounding_stats_total['partial'] + grounding_stats_total['semantic']
                yield sse_msg({
                    'stage': 'GROUNDING_COMPLETE',
                    'progress': 70,
                    'messages': [
                        f'Grounded {total_mentions} entity mentions in {total_grounded} conclusions',
                        f'  - {grounding_stats_total["exact"]} exact matches',
                        f'  - {grounding_stats_total["partial"]} partial matches'
                    ]
                })

                # Store all conclusions
                yield sse_msg({'stage': 'STORING', 'progress': 72, 'messages': ['Storing all conclusions in database...']})
                session_id = str(uuid.uuid4())

                # Save extraction prompt
                extraction_prompt = ExtractionPrompt(
                    case_id=case_id,
                    concept_type='ethical_conclusion',
                    step_number=4,
                    section_type='conclusions',
                    prompt_text=analyzer.last_prompt or 'Conclusion analysis',
                    llm_model='claude-sonnet-4-20250514',
                    extraction_session_id=session_id,
                    raw_response=analyzer.last_response or '',
                    results_summary={
                        'board_explicit': len(board_conclusions),
                        'analytical_extension': len(analytical_extension),
                        'question_response': len(question_response),
                        'principle_synthesis': len(principle_synthesis),
                        'stage1_source': stage1_source
                    },
                    is_active=True,
                    times_used=1,
                    created_at=datetime.utcnow(),
                    last_used_at=datetime.utcnow()
                )
                db.session.add(extraction_prompt)

                # Helper to store conclusions
                def store_conclusion(c):
                    rdf_entity = TemporaryRDFStorage(
                        case_id=case_id,
                        extraction_session_id=session_id,
                        extraction_type='ethical_conclusion',
                        storage_type='individual',
                        entity_type='conclusions',
                        entity_label=f"C{c.conclusion_number}_{c.conclusion_type}",
                        entity_definition=c.conclusion_text,
                        rdf_json_ld={
                            '@type': 'proeth-case:EthicalConclusion',
                            'conclusionNumber': c.conclusion_number,
                            'conclusionText': c.conclusion_text,
                            'conclusionType': c.conclusion_type,
                            'boardConclusionType': c.board_conclusion_type,
                            'mentionedEntities': c.mentioned_entities,
                            'mentionedEntityUris': c.mentioned_entity_uris,
                            'citedProvisions': c.cited_provisions,
                            'extractionReasoning': c.extraction_reasoning,
                            'source': c.source,
                            'answersQuestions': c.answers_questions,
                            'sourceConclusion': c.source_conclusion,
                            'relatedAnalyticalQuestions': c.related_analytical_questions,
                            # Entity grounding data
                            'groundedText': getattr(c, 'grounded_text', c.conclusion_text),
                            'entityMentions': getattr(c, 'entity_mentions', []),
                            'involvedEntities': getattr(c, 'involved_entities', {}),
                            'groundingStats': getattr(c, 'grounding_stats', {})
                        },
                        is_selected=True
                    )
                    db.session.add(rdf_entity)

                # Store all conclusion types
                all_to_store = [
                    board_conclusions,
                    analytical_extension,
                    question_response,
                    principle_synthesis
                ]

                total_stored = 0
                total_conclusions = len(all_conclusions_to_ground)
                for conclusions in all_to_store:
                    for c in conclusions:
                        store_conclusion(c)
                        total_stored += 1
                        progress = 72 + int((total_stored / max(total_conclusions, 1)) * 23)
                        yield sse_msg({'stage': 'STORING_CONCLUSION', 'progress': progress,
                                       'messages': [f'Stored {total_stored}/{total_conclusions} conclusions']})

                db.session.commit()

                yield sse_msg({'stage': 'STORED', 'progress': 98, 'messages': ['All conclusions stored successfully']})

                # Build status messages with context from 2B
                source_note = "(from import)" if stage1_source == 'imported' else "(LLM extracted)"
                warnings = []
                if not board_questions and not analytical_questions:
                    warnings.append("No questions found from Step 2B - run question extraction first for better analytical conclusions")

                status_messages = [
                    # Input context from 2B
                    f"Input: {len(board_questions)} Board questions, {len(analytical_questions)} analytical questions",
                    f"Input: {len(provisions)} code provisions, {entity_count} entities",
                    # Stage 1 results
                    f"Stage 1 - Board Conclusions: {len(board_conclusions)} {source_note}",
                    # Stage 2 results
                    f"Stage 2 - Analytical Extensions: {len(analytical_extension)}",
                    f"Stage 2 - Question Responses: {len(question_response)}",
                    f"Stage 2 - Principle Syntheses: {len(principle_synthesis)}",
                    # Grounding summary
                    f"Entity Grounding: {total_mentions} mentions ({grounding_stats_total['exact']} exact, {grounding_stats_total['partial']} partial)"
                ]

                yield sse_msg({
                    'stage': 'COMPLETE',
                    'progress': 100,
                    'messages': [f'Analysis complete: {total_conclusions} conclusions total'],
                    'status_messages': status_messages,
                    'warnings': warnings,
                    'prompt': analyzer.last_prompt or 'Conclusion analysis',
                    'raw_llm_response': analyzer.last_response or '',
                    'result': {
                        'count': total_conclusions,
                        'board_explicit': len(board_conclusions),
                        'analytical': len(analytical_extension) + len(question_response) + len(principle_synthesis),
                        'stage1_source': stage1_source,
                        'stage1_used_llm': stage1_used_llm,
                        'by_type': {
                            'board_explicit': len(board_conclusions),
                            'analytical_extension': len(analytical_extension),
                            'question_response': len(question_response),
                            'principle_synthesis': len(principle_synthesis)
                        },
                        'grounding': {
                            'total_mentions': total_mentions,
                            'exact': grounding_stats_total['exact'],
                            'partial': grounding_stats_total['partial']
                        }
                    },
                    'input_context': {
                        'board_questions': len(board_questions),
                        'analytical_questions': len(analytical_questions),
                        'provisions': len(provisions),
                        'entities': entity_count
                    }
                })

            except Exception as e:
                logger.error(f"Streaming conclusions error: {e}")
                import traceback
                traceback.print_exc()
                yield sse_msg({'stage': 'ERROR', 'progress': 100, 'messages': [f'Error: {str(e)}'], 'error': True})

        return Response(stream_with_context(generate()), mimetype='text/event-stream')
