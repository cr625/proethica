"""
Step 4 Streaming Synthesis

Server-Sent Events (SSE) streaming for whole-case synthesis with real-time
LLM prompt/response display.

Similar to Step 3 Enhanced Temporal Dynamics.
"""

from flask import Response, jsonify, current_app, request
import json
import logging
import uuid
from datetime import datetime

from app import db
from app.models import Document, TemporaryRDFStorage, ExtractionPrompt
from app.utils.llm_utils import get_llm_client

# Import synthesis services
from app.services.nspe_references_parser import NSPEReferencesParser
from app.services.universal_provision_detector import UniversalProvisionDetector
from app.services.provision_grouper import ProvisionGrouper
from app.services.provision_group_validator import ProvisionGroupValidator
from app.services.code_provision_linker import CodeProvisionLinker
from app.services.question_analyzer import QuestionAnalyzer
from app.services.conclusion_analyzer import ConclusionAnalyzer
from app.services.question_conclusion_linker import QuestionConclusionLinker
from app.services.case_synthesis_service import CaseSynthesisService

# Import Part D: Institutional Rule Analysis
from app.services.case_analysis.institutional_rule_analyzer import InstitutionalRuleAnalyzer

logger = logging.getLogger(__name__)


def synthesize_case_streaming(case_id):
    """
    Execute Step 4 synthesis with SSE streaming for progress tracking.
    
    Key design: Pre-load ALL database data before generator starts,
    then generator only yields SSE events (no database access).
    """
    try:
        logger.info(f"[Step 4 Streaming] Starting synthesis for case {case_id}")

        # ==========================================
        # PRE-LOAD ALL DATA (has Flask context here)
        # ==========================================
        case = Document.query.get_or_404(case_id)
        llm_client = get_llm_client()
        
        # Get case sections
        sections_dual = case.doc_metadata.get('sections_dual', {}) if case.doc_metadata else {}
        
        # Extract section texts
        references_html = None
        for section_key, section_content in sections_dual.items():
            if 'reference' in section_key.lower():
                references_html = section_content.get('html', '') if isinstance(section_content, dict) else ''
                break
        
        questions_text = ""
        if 'question' in sections_dual:
            q_data = sections_dual['question']
            questions_text = q_data.get('text', '') if isinstance(q_data, dict) else str(q_data)
        
        conclusions_text = ""
        if 'conclusion' in sections_dual:
            c_data = sections_dual['conclusion']
            conclusions_text = c_data.get('text', '') if isinstance(c_data, dict) else str(c_data)
        
        # Extract case sections for provision detection
        case_sections = {}
        for section_key in ['facts', 'discussion', 'question', 'conclusion']:
            if section_key in sections_dual:
                section_data = sections_dual[section_key]
                case_sections[section_key] = section_data.get('text', '') if isinstance(section_data, dict) else str(section_data)
        
        # Pre-load all entities (BEFORE generator)
        all_entities = _get_all_case_entities(case_id)
        
        # ==========================================
        # GENERATOR FUNCTION (no database access)
        # ==========================================
        def generate():
            """Generator for Server-Sent Events - uses pre-loaded data only"""
            try:
                llm_traces = []
                session_id = str(uuid.uuid4())
                
                # Storage for results (will be saved AFTER generator completes)
                synthesis_results = {
                    'provisions': [],
                    'questions': [],
                    'conclusions': [],
                    'synthesis': None
                }
                
                # =============================================================
                # PART A: CODE PROVISIONS
                # =============================================================
                yield sse_message({
                    'stage': 'PART_A_START',
                    'progress': 10,
                    'messages': ['Part A: Extracting code provisions...']
                })
                
                if not references_html:
                    yield sse_message({
                        'stage': 'PART_A_WARNING',
                        'progress': 15,
                        'messages': ['Warning: No references section found'],
                        'errors': ['No references section available']
                    })
                    provisions = []
                else:
                    # Parse provisions
                    parser = NSPEReferencesParser()
                    provisions = parser.parse_references_html(references_html)
                    
                    yield sse_message({
                        'stage': 'PART_A_PARSED',
                        'progress': 20,
                        'messages': [f'Parsed {len(provisions)} NSPE code provisions']
                    })
                    
                    # Detect mentions
                    detector = UniversalProvisionDetector()
                    all_mentions = detector.detect_all_provisions(case_sections)
                    
                    yield sse_message({
                        'stage': 'PART_A_MENTIONS',
                        'progress': 30,
                        'messages': [f'Detected {len(all_mentions)} provision mentions']
                    })
                    
                    # Group and validate
                    grouper = ProvisionGrouper()
                    grouped_mentions = grouper.group_mentions_by_provision(all_mentions, provisions)
                    
                    validator = ProvisionGroupValidator(llm_client)
                    
                    for i, provision in enumerate(provisions):
                        code = provision['code_provision']
                        mentions = grouped_mentions.get(code, [])
                        
                        if mentions:
                            validated = validator.validate_group(code, provision['provision_text'], mentions)
                            provision['relevant_excerpts'] = [
                                {
                                    'section': v.section,
                                    'text': v.excerpt,
                                    'matched_citation': v.citation_text,
                                    'mention_type': v.content_type,
                                    'confidence': v.confidence,
                                    'validation_reasoning': v.reasoning
                                }
                                for v in validated
                            ]
                            
                            # Capture LLM trace
                            if hasattr(validator, 'last_prompt') and hasattr(validator, 'last_response'):
                                llm_traces.append({
                                    'stage': f'Code Provision {code} Validation',
                                    'prompt': validator.last_prompt,
                                    'response': validator.last_response,
                                    'model': 'claude-sonnet-4-5-20250929',
                                    'timestamp': datetime.utcnow().isoformat()
                                })
                        else:
                            provision['relevant_excerpts'] = []
                        
                        progress = 30 + int((i + 1) / len(provisions) * 15)
                        yield sse_message({
                            'stage': 'PART_A_VALIDATING',
                            'progress': progress,
                            'messages': [f'Validated {i+1}/{len(provisions)} provisions']
                        })
                    
                    # Link to entities
                    yield sse_message({
                        'stage': 'PART_A_LINKING',
                        'progress': 45,
                        'messages': ['Linking provisions to extracted entities...']
                    })
                    
                    linker = CodeProvisionLinker(llm_client)
                    provisions = linker.link_provisions_to_entities(
                        provisions,
                        roles=_format_entities(all_entities['roles']),
                        states=_format_entities(all_entities['states']),
                        resources=_format_entities(all_entities['resources']),
                        principles=_format_entities(all_entities['principles']),
                        obligations=_format_entities(all_entities['obligations']),
                        constraints=_format_entities(all_entities['constraints']),
                        capabilities=_format_entities(all_entities['capabilities']),
                        actions=_format_entities(all_entities['actions']),
                        events=_format_entities(all_entities['events']),
                        case_text_summary=f"Case {case_id}: {case.title}"
                    )
                    
                    # Capture LLM trace
                    if hasattr(linker, 'last_linking_prompt') and hasattr(linker, 'last_linking_response'):
                        llm_traces.append({
                            'stage': 'Code Provision Linking',
                            'prompt': linker.last_linking_prompt,
                            'response': linker.last_linking_response,
                            'model': 'claude-sonnet-4-5-20250929',
                            'timestamp': datetime.utcnow().isoformat()
                        })
                
                synthesis_results['provisions'] = provisions
                
                yield sse_message({
                    'stage': 'PART_A_COMPLETE',
                    'progress': 50,
                    'messages': [f'Part A complete: {len(provisions)} provisions'],
                    'llm_trace': llm_traces[-2:] if len(llm_traces) >= 2 else llm_traces
                })
                
                # =============================================================
                # PART B: QUESTIONS & CONCLUSIONS
                # =============================================================
                yield sse_message({
                    'stage': 'PART_B_START',
                    'progress': 55,
                    'messages': ['Part B: Extracting questions and conclusions...']
                })
                
                # Extract questions
                question_analyzer = QuestionAnalyzer(llm_client)
                questions = question_analyzer.extract_questions(
                    questions_text,
                    all_entities,
                    provisions
                )
                
                if hasattr(question_analyzer, 'last_prompt') and hasattr(question_analyzer, 'last_response'):
                    llm_traces.append({
                        'stage': 'Question Extraction',
                        'prompt': question_analyzer.last_prompt,
                        'response': question_analyzer.last_response,
                        'model': 'claude-sonnet-4-5-20250929',
                        'timestamp': datetime.utcnow().isoformat()
                    })
                
                yield sse_message({
                    'stage': 'PART_B_QUESTIONS',
                    'progress': 65,
                    'messages': [f'Extracted {len(questions)} questions'],
                    'llm_trace': [llm_traces[-1]] if llm_traces else []
                })
                
                # Extract conclusions
                conclusion_analyzer = ConclusionAnalyzer(llm_client)
                conclusions = conclusion_analyzer.extract_conclusions(
                    conclusions_text,
                    all_entities,
                    provisions
                )
                
                if hasattr(conclusion_analyzer, 'last_prompt') and hasattr(conclusion_analyzer, 'last_response'):
                    llm_traces.append({
                        'stage': 'Conclusion Extraction',
                        'prompt': conclusion_analyzer.last_prompt,
                        'response': conclusion_analyzer.last_response,
                        'model': 'claude-sonnet-4-5-20250929',
                        'timestamp': datetime.utcnow().isoformat()
                    })
                
                yield sse_message({
                    'stage': 'PART_B_CONCLUSIONS',
                    'progress': 75,
                    'messages': [f'Extracted {len(conclusions)} conclusions'],
                    'llm_trace': [llm_traces[-1]] if llm_traces else []
                })
                
                # Link Q->C
                linker_qc = QuestionConclusionLinker(llm_client)
                qc_links = linker_qc.link_questions_to_conclusions(questions, conclusions)
                conclusions = linker_qc.apply_links_to_conclusions(conclusions, qc_links)
                
                if hasattr(linker_qc, 'last_prompt') and hasattr(linker_qc, 'last_response'):
                    llm_traces.append({
                        'stage': 'Question-Conclusion Linking',
                        'prompt': linker_qc.last_prompt,
                        'response': linker_qc.last_response,
                        'model': 'claude-sonnet-4-5-20250929',
                        'timestamp': datetime.utcnow().isoformat()
                    })
                
                synthesis_results['questions'] = questions
                synthesis_results['conclusions'] = conclusions
                
                yield sse_message({
                    'stage': 'PART_B_COMPLETE',
                    'progress': 80,
                    'messages': [f'Part B complete: {len(questions)} Q, {len(conclusions)} C'],
                    'llm_trace': [llm_traces[-1]] if llm_traces else []
                })
                
                # =============================================================
                # PART C: CROSS-SECTION SYNTHESIS
                # =============================================================
                yield sse_message({
                    'stage': 'PART_C_START',
                    'progress': 85,
                    'messages': ['Part C: Performing whole-case synthesis...']
                })
                
                # NOTE: CaseSynthesisService uses pre-loaded entities from closure
                # It doesn't make new database queries
                synthesis_service = CaseSynthesisService(llm_client)
                
                # Build entity graph (uses pre-loaded all_entities)
                from app.services.case_synthesis_service import EntityGraph, EntityNode
                entity_graph = EntityGraph(nodes={})
                
                # Pre-loaded entities are already in memory, just structure them
                for entity_type, entity_list in all_entities.items():
                    for entity in entity_list:
                        entity_id = f"{entity_type}_{entity.id}"
                        node = EntityNode(
                            entity_id=entity_id,
                            entity_type=entity_type.lower(),
                            label=entity.entity_label,
                            definition=entity.entity_definition or "",
                            section_type='unknown',  # Would need extraction_session lookup
                            extraction_session_id=entity.extraction_session_id,
                            rdf_json_ld=entity.rdf_json_ld or {}
                        )
                        entity_graph.add_node(node)
                
                synthesis_results['synthesis'] = {
                    'entity_graph': entity_graph,
                    'total_nodes': len(entity_graph.nodes),
                    'node_types': len(entity_graph.by_type)
                }
                
                yield sse_message({
                    'stage': 'PART_C_GRAPH',
                    'progress': 90,
                    'messages': [
                        f'Built entity graph: {len(entity_graph.nodes)} nodes',
                        f'Entity types: {len(entity_graph.by_type)}'
                    ]
                })
                
                yield sse_message({
                    'stage': 'PART_C_COMPLETE',
                    'progress': 88,
                    'messages': ['Part C complete: Entity graph built']
                })

                # =============================================================
                # PART D: INSTITUTIONAL RULE ANALYSIS
                # =============================================================
                yield sse_message({
                    'stage': 'PART_D_START',
                    'progress': 90,
                    'messages': ['Part D: Analyzing institutional rules and normative tensions...']
                })

                # Get P, O, Cs entities for institutional analysis
                principles_entities = all_entities.get('principles', [])
                obligations_entities = all_entities.get('obligations', [])
                constraints_entities = all_entities.get('constraints', [])

                institutional_analysis = None
                if principles_entities or obligations_entities or constraints_entities:
                    # Initialize analyzer with pre-loaded LLM client (from closure, has Flask context)
                    institutional_analyzer = InstitutionalRuleAnalyzer(llm_client)

                    # Build case context from questions and conclusions
                    case_context = {
                        'questions': [getattr(q, 'question_text', '') for q in synthesis_results['questions']],
                        'conclusions': [getattr(c, 'conclusion_text', '') for c in synthesis_results['conclusions']],
                        'provisions': [f"{p.get('code_provision', '')}: {p.get('provision_text', '')}" for p in synthesis_results['provisions']]
                    }

                    # Run institutional analysis
                    institutional_analysis = institutional_analyzer.analyze_case(
                        case_id=case_id,
                        principles=principles_entities,
                        obligations=obligations_entities,
                        constraints=constraints_entities,
                        case_context=case_context
                    )

                    # Capture LLM trace
                    if hasattr(institutional_analyzer, 'last_prompt') and hasattr(institutional_analyzer, 'last_response'):
                        llm_traces.append({
                            'stage': 'Institutional Rule Analysis',
                            'prompt': institutional_analyzer.last_prompt,
                            'response': institutional_analyzer.last_response,
                            'model': 'claude-sonnet-4-5-20250929',
                            'timestamp': datetime.utcnow().isoformat()
                        })

                    # Convert to dict for JSON serialization
                    synthesis_results['institutional_analysis'] = institutional_analysis.to_dict()

                    yield sse_message({
                        'stage': 'PART_D_COMPLETE',
                        'progress': 95,
                        'messages': [
                            f'Part D complete: Analyzed {len(institutional_analysis.principle_tensions)} principle tensions',
                            f'{len(institutional_analysis.obligation_conflicts)} obligation conflicts identified',
                            f'{len(institutional_analysis.constraining_factors)} constraining factors mapped'
                        ],
                        'llm_trace': [llm_traces[-1]] if llm_traces else []
                    })
                else:
                    yield sse_message({
                        'stage': 'PART_D_SKIPPED',
                        'progress': 95,
                        'messages': ['Part D skipped: No P/O/Cs entities available for analysis']
                    })

                # =============================================================
                # COMPLETION - Return data for frontend to save
                # =============================================================
                completion_data = {
                    'complete': True,
                    'progress': 100,
                    'messages': ['Synthesis complete! Saving to database...'],
                    'summary': {
                        'provisions_count': len(synthesis_results['provisions']),
                        'questions_count': len(synthesis_results['questions']),
                        'conclusions_count': len(synthesis_results['conclusions']),
                        'total_nodes': synthesis_results['synthesis']['total_nodes'],
                        'llm_interactions': len(llm_traces)
                    },
                    # Include session_id and llm_traces for database saving
                    'session_id': session_id,
                    'llm_traces': llm_traces,
                    'synthesis_results': {
                        'provisions': synthesis_results['provisions'],
                        'questions': [
                            {
                                'id': getattr(q, 'question_number', ''),
                                'text': getattr(q, 'question_text', ''),
                                'mentioned_entities': getattr(q, 'mentioned_entities', []),
                                'related_provisions': getattr(q, 'related_provisions', [])
                            }
                            for q in synthesis_results['questions']
                        ],
                        'conclusions': [
                            {
                                'id': getattr(c, 'conclusion_number', ''),
                                'text': getattr(c, 'conclusion_text', ''),
                                'mentioned_entities': getattr(c, 'mentioned_entities', []),
                                'cited_provisions': getattr(c, 'cited_provisions', []),
                                'answers_questions': getattr(c, 'answers_questions', [])
                            }
                            for c in synthesis_results['conclusions']
                        ],
                        'entity_graph': {
                            'total_nodes': synthesis_results['synthesis']['total_nodes'],
                            'node_types': synthesis_results['synthesis']['node_types']
                        },
                        'institutional_analysis': synthesis_results.get('institutional_analysis')  # Part D results (dict)
                    }
                }
                yield sse_message(completion_data)

                # Database saving happens via the /save_streaming_results endpoint
                # called by the frontend JavaScript after streaming completes.
                # Cannot save here due to Flask app context issues in generator.

            except Exception as e:
                logger.error(f"[Step 4 Streaming] Error: {e}", exc_info=True)
                yield sse_message({
                    'error': str(e),
                    'progress': 0,
                    'messages': [f'Error: {str(e)}']
                })
        
        # Return SSE response
        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive'
            }
        )
        
    except Exception as e:
        logger.error(f"[Step 4 Streaming] Setup error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def sse_message(data):
    """Format data as Server-Sent Event"""
    return f"data: {json.dumps(data)}\n\n"


def _get_all_case_entities(case_id):
    """Query ALL extracted entities from Passes 1-3"""
    from sqlalchemy import func

    entity_types = [
        'roles', 'states', 'resources',
        'principles', 'obligations', 'constraints', 'capabilities',
        'actions', 'events'
    ]

    entities = {}
    for entity_type in entity_types:
        # Case-insensitive query using func.lower()
        entities[entity_type] = TemporaryRDFStorage.query.filter(
            TemporaryRDFStorage.case_id == case_id,
            func.lower(TemporaryRDFStorage.entity_type) == entity_type.lower(),
            TemporaryRDFStorage.storage_type == 'individual'
        ).all()

    return entities


def _format_entities(entity_list):
    """Format entities for service consumption"""
    return [
        {
            'label': e.entity_label,
            'definition': e.entity_definition
        }
        for e in entity_list
    ]


def save_step4_streaming_results(case_id):
    """
    Save Step 4 streaming synthesis results to database.

    Called by frontend after SSE streaming completes with all LLM traces and synthesis data.
    This allows persistence across page refreshes (similar to Step 3).
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        logger.info(f"Saving Step 4 streaming results for case {case_id}")
        logger.info(f"[Save Endpoint Debug] Received data keys: {list(data.keys())}")
        logger.info(f"[Save Endpoint Debug] synthesis_results keys: {list(data.get('synthesis_results', {}).keys())}")

        session_id = data.get('session_id')
        llm_traces = data.get('llm_traces', [])
        synthesis_results = data.get('synthesis_results', {})

        logger.info(f"[Save Endpoint Debug] session_id: {session_id}")
        logger.info(f"[Save Endpoint Debug] llm_traces length: {len(llm_traces)}")
        logger.info(f"[Save Endpoint Debug] questions in synthesis_results: {len(synthesis_results.get('questions', []))}")
        logger.info(f"[Save Endpoint Debug] conclusions in synthesis_results: {len(synthesis_results.get('conclusions', []))}")

        if not session_id:
            return jsonify({'error': 'session_id is required'}), 400

        # Combine all LLM prompts and responses into a single consolidated record
        combined_prompts = []
        combined_responses = []

        for trace in llm_traces:
            stage = trace.get('stage', 'unknown')
            combined_prompts.append(f"=== {stage} ===\n{trace.get('prompt', '')}\n")
            combined_responses.append(f"=== {stage} ===\n{trace.get('response', '')}\n")

        combined_prompt_text = "\n".join(combined_prompts)
        combined_response_text = "\n".join(combined_responses)

        # Store Code Provisions to TemporaryRDFStorage
        provisions_list = synthesis_results.get('provisions', [])
        logger.info(f"[Save Endpoint] Saving {len(provisions_list)} provisions to TemporaryRDFStorage")

        # Clear old provisions
        TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='code_provision_reference'
        ).delete(synchronize_session=False)

        for p in provisions_list:
            code = p.get('code_provision', '')
            label = f"NSPE_{code.replace('.', '_')}"

            rdf_entity = TemporaryRDFStorage(
                case_id=case_id,
                extraction_session_id=session_id,
                extraction_type='code_provision_reference',
                storage_type='individual',
                entity_type='resources',
                entity_label=label,
                entity_definition=p.get('provision_text', ''),
                rdf_json_ld={
                    '@type': 'proeth-case:CodeProvisionReference',
                    'label': label,
                    'codeProvision': code,
                    'provisionText': p.get('provision_text', ''),
                    'subjectReferences': p.get('subject_references', []),
                    'appliesTo': p.get('applies_to', []),
                    'relevantExcerpts': p.get('relevant_excerpts', []),
                    'providedBy': 'NSPE Board of Ethical Review',
                    'authoritative': True
                },
                is_selected=True,
                extraction_model='claude-opus-4-20250514',
                ontology_target=f'proethica-case-{case_id}'
            )
            db.session.add(rdf_entity)

        # Store Questions to TemporaryRDFStorage
        questions_list = synthesis_results.get('questions', [])
        logger.info(f"[Save Endpoint] Saving {len(questions_list)} questions to TemporaryRDFStorage")

        for q in questions_list:
            question_num = q.get('id', 0)
            question_text = q.get('text', '')

            rdf_entity = TemporaryRDFStorage(
                case_id=case_id,
                extraction_session_id=session_id,
                extraction_type='ethical_question',
                storage_type='individual',
                entity_type='questions',
                entity_label=f"Question_{question_num}",
                entity_definition=question_text,
                rdf_json_ld={
                    '@type': 'proeth-case:EthicalQuestion',
                    'questionNumber': question_num,
                    'questionText': question_text,
                    'mentionedEntities': q.get('mentioned_entities', []),
                    'relatedProvisions': q.get('related_provisions', [])
                },
                is_selected=True,
                extraction_model='claude-opus-4-20250514',
                ontology_target=f'proethica-case-{case_id}'
            )
            db.session.add(rdf_entity)

        # Store Conclusions to TemporaryRDFStorage
        conclusions_list = synthesis_results.get('conclusions', [])
        logger.info(f"[Save Endpoint] Saving {len(conclusions_list)} conclusions to TemporaryRDFStorage")

        for c in conclusions_list:
            conclusion_num = c.get('id', 0)
            conclusion_text = c.get('text', '')

            rdf_entity = TemporaryRDFStorage(
                case_id=case_id,
                extraction_session_id=session_id,
                extraction_type='ethical_conclusion',
                storage_type='individual',
                entity_type='conclusions',
                entity_label=f"Conclusion_{conclusion_num}",
                entity_definition=conclusion_text,
                rdf_json_ld={
                    '@type': 'proeth-case:EthicalConclusion',
                    'conclusionNumber': conclusion_num,
                    'conclusionText': conclusion_text,
                    'mentionedEntities': c.get('mentioned_entities', []),
                    'citedProvisions': c.get('cited_provisions', []),
                    'answersQuestions': c.get('answers_questions', [])
                },
                is_selected=True,
                extraction_model='claude-opus-4-20250514',
                ontology_target=f'proethica-case-{case_id}'
            )
            db.session.add(rdf_entity)

        # Store Institutional Analysis (Part D) to database
        institutional_analysis_dict = synthesis_results.get('institutional_analysis')
        if institutional_analysis_dict:
            logger.info(f"[Save Endpoint] Saving institutional analysis for case {case_id}")

            # Import the analyzer and dataclass
            from app.services.case_analysis.institutional_rule_analyzer import (
                InstitutionalRuleAnalyzer,
                InstitutionalAnalysis
            )

            # Reconstruct InstitutionalAnalysis dataclass from dict
            institutional_analysis = InstitutionalAnalysis.from_dict(institutional_analysis_dict)

            # Save to database
            analyzer = InstitutionalRuleAnalyzer()  # Gets its own LLM client (though not needed for saving)
            saved = analyzer.save_to_database(
                case_id=case_id,
                analysis=institutional_analysis,
                llm_model='claude-sonnet-4-5-20250929'
            )

            if saved:
                logger.info(f"[Save Endpoint] Successfully saved institutional analysis")
            else:
                logger.warning(f"[Save Endpoint] Failed to save institutional analysis")

        # Delete old Step 4 synthesis prompts
        ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='whole_case_synthesis'
        ).delete(synchronize_session=False)

        # Save as single ExtractionPrompt entry
        extraction_prompt = ExtractionPrompt(
            case_id=case_id,
            concept_type='whole_case_synthesis',
            step_number=4,
            section_type='synthesis',
            prompt_text=combined_prompt_text,
            llm_model='claude-opus-4-20250514',
            extraction_session_id=session_id,
            raw_response=combined_response_text,
            results_summary={
                'provisions_count': len(synthesis_results.get('provisions', [])),
                'questions_count': len(synthesis_results.get('questions', [])),
                'conclusions_count': len(synthesis_results.get('conclusions', [])),
                'total_nodes': synthesis_results.get('entity_graph', {}).get('total_nodes', 0),
                'llm_interactions': len(llm_traces),
                'stages': [t.get('stage') for t in llm_traces]
            },
            is_active=True,
            times_used=1,
            created_at=datetime.utcnow(),
            last_used_at=datetime.utcnow()
        )
        db.session.add(extraction_prompt)
        db.session.commit()

        logger.info(f"Successfully saved Step 4 streaming results for case {case_id}")
        logger.info(f"[Save Endpoint] Saved {len(provisions_list)} provisions, {len(questions_list)} questions, and {len(conclusions_list)} conclusions")

        return jsonify({
            'success': True,
            'message': 'Step 4 synthesis results saved successfully',
            'session_id': session_id,
            'traces_saved': len(llm_traces),
            'provisions_saved': len(provisions_list),
            'questions_saved': len(questions_list),
            'conclusions_saved': len(conclusions_list)
        })

    except Exception as e:
        logger.error(f"Error saving Step 4 streaming results: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
