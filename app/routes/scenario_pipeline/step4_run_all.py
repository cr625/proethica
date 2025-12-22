"""
Step 4 Run All - Simple Non-Streaming Complete Synthesis

Calls the same services as the individual UI buttons in sequence.
This ensures we use the EXACT same code paths without SSE overhead.

Order matches UI (http://localhost:5000/scenario_pipeline/case/<id>/step4):
1. Provisions (2A)
2. Q&C Unified (2B)
3. Transformation (2C)
4. Rich Analysis (2D)
5. Phase 3 Decision Synthesis
6. Phase 4 Narrative Construction

Usage: Called by "Run Complete Synthesis" button.
"""

import json
import logging
import uuid
from datetime import datetime
from flask import jsonify

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.utils.environment_auth import auth_required_for_llm
from app.utils.llm_utils import get_llm_client

logger = logging.getLogger(__name__)


def register_run_all_routes(bp, get_all_case_entities):
    """
    Register the run-all-synthesis route on the blueprint.

    Args:
        bp: The Flask Blueprint to register routes on
        get_all_case_entities: Helper function to load entities for a case
    """

    @bp.route('/case/<int:case_id>/run_complete_synthesis', methods=['POST'])
    @auth_required_for_llm
    def run_complete_synthesis(case_id):
        """
        Run complete Step 4 synthesis by calling the same services as UI buttons.

        Non-streaming - runs to completion, returns JSON result.
        """
        try:
            case = Document.query.get_or_404(case_id)
            results = {'stages': [], 'success': False}
            llm_client = get_llm_client()

            # =====================================================================
            # STEP 1: Clear existing Step 4 data
            # =====================================================================
            logger.info(f"[RunAll] Clearing Step 4 data for case {case_id}")
            clear_result = _clear_step4_data(case_id)
            results['clear'] = clear_result
            results['stages'].append('CLEAR')

            # =====================================================================
            # STEP 2A: Provisions
            # =====================================================================
            logger.info(f"[RunAll] Running provisions extraction for case {case_id}")
            provisions_result = _run_provisions(case_id, llm_client, get_all_case_entities)
            results['provisions'] = provisions_result
            results['stages'].append('PROVISIONS')

            if provisions_result.get('error'):
                logger.error(f"[RunAll] Provisions failed: {provisions_result}")
                return jsonify({
                    'success': False,
                    'error': f"Provisions failed: {provisions_result.get('error')}",
                    'results': results
                }), 500

            # =====================================================================
            # STEP 2B: Q&C Unified
            # =====================================================================
            logger.info(f"[RunAll] Running Q&C extraction for case {case_id}")
            qc_result = _run_qc_unified(case_id, llm_client, get_all_case_entities)
            results['qc'] = qc_result
            results['stages'].append('QC')

            if qc_result.get('error'):
                logger.error(f"[RunAll] Q&C failed: {qc_result}")
                return jsonify({
                    'success': False,
                    'error': f"Q&C failed: {qc_result.get('error')}",
                    'results': results
                }), 500

            # =====================================================================
            # STEP 2C: Transformation
            # =====================================================================
            logger.info(f"[RunAll] Running transformation classification for case {case_id}")
            transformation_result = _run_transformation(case_id, llm_client)
            results['transformation'] = transformation_result
            results['stages'].append('TRANSFORMATION')

            # Non-blocking - continue even on error

            # =====================================================================
            # STEP 2D: Rich Analysis
            # =====================================================================
            logger.info(f"[RunAll] Running rich analysis for case {case_id}")
            rich_result = _run_rich_analysis(case_id)
            results['rich_analysis'] = rich_result
            results['stages'].append('RICH_ANALYSIS')

            # Non-blocking - continue even on error

            # =====================================================================
            # PHASE 3: Decision Synthesis
            # =====================================================================
            logger.info(f"[RunAll] Running Phase 3 decision synthesis for case {case_id}")
            phase3_result = _run_phase3(case_id)
            results['phase3'] = phase3_result
            results['stages'].append('PHASE3')

            # Non-blocking - continue even on error

            # =====================================================================
            # PHASE 4: Narrative Construction
            # =====================================================================
            logger.info(f"[RunAll] Running Phase 4 narrative construction for case {case_id}")
            phase4_result = _run_phase4(case_id)
            results['phase4'] = phase4_result
            results['stages'].append('PHASE4')

            # Non-blocking - continue even on error

            # =====================================================================
            # COMPLETE
            # =====================================================================
            logger.info(f"[RunAll] Complete synthesis finished for case {case_id}")
            results['success'] = True

            return jsonify(results)

        except Exception as e:
            logger.error(f"[RunAll] Error in run_complete_synthesis for case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    return {
        'run_complete_synthesis': run_complete_synthesis
    }


def _clear_step4_data(case_id: int) -> dict:
    """Clear all Step 4 data (Phase 2-4) while preserving Phase 1 entities."""
    try:
        extraction_types_to_clear = [
            'code_provision_reference',
            'ethical_question',
            'ethical_conclusion',
            'question_emergence',
            'resolution_pattern',
            'causal_normative_link',
            'canonical_decision_point',
            'decision_point',
            'decision_option',
            'transformation_analysis',
            'case_summary',
            'timeline_event'
        ]

        deleted_counts = {}
        total_deleted = 0

        for extraction_type in extraction_types_to_clear:
            count = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type=extraction_type
            ).delete(synchronize_session=False)
            if count > 0:
                deleted_counts[extraction_type] = count
                total_deleted += count

        # Clear related extraction prompts
        prompt_types = [
            'code_provision',
            'ethical_question',
            'ethical_conclusion',
            'question_emergence',
            'resolution_pattern',
            'causal_normative_link',
            'transformation',
            'transformation_classification',
            'rich_analysis',
            'phase3_decision_synthesis',
            'phase4_narrative',
            'unified_synthesis',
            'whole_case_synthesis'
        ]

        prompts_deleted = 0
        for prompt_type in prompt_types:
            count = ExtractionPrompt.query.filter_by(
                case_id=case_id,
                concept_type=prompt_type
            ).delete(synchronize_session=False)
            prompts_deleted += count

        db.session.commit()

        logger.info(f"[RunAll] Cleared: {total_deleted} entities, {prompts_deleted} prompts")

        return {
            'entities_deleted': total_deleted,
            'prompts_deleted': prompts_deleted
        }

    except Exception as e:
        logger.error(f"[RunAll] Error clearing data: {e}")
        db.session.rollback()
        return {'error': str(e)}


def _run_provisions(case_id: int, llm_client, get_all_case_entities) -> dict:
    """
    Run provisions extraction - SAME code as extract_provisions_streaming.
    """
    from app.services.nspe_references_parser import NSPEReferencesParser
    from app.services.universal_provision_detector import UniversalProvisionDetector
    from app.services.provision_grouper import ProvisionGrouper
    from app.services.provision_group_validator import ProvisionGroupValidator
    from app.services.code_provision_linker import CodeProvisionLinker

    try:
        case = Document.query.get_or_404(case_id)

        # Get references HTML
        sections_dual = case.doc_metadata.get('sections_dual', {}) if case.doc_metadata else {}
        references_html = None
        for section_key, section_content in sections_dual.items():
            if 'reference' in section_key.lower():
                references_html = section_content.get('html', '') if isinstance(section_content, dict) else ''
                break

        if not references_html:
            return {'error': 'No references section found'}

        # Parse provisions
        parser = NSPEReferencesParser()
        provisions = parser.parse_references_html(references_html)
        logger.info(f"[RunAll] Parsed {len(provisions)} NSPE code provisions")

        # Get case sections for detection
        case_sections = {}
        for section_key in ['facts', 'discussion', 'question', 'conclusion']:
            if section_key in sections_dual:
                section_data = sections_dual[section_key]
                case_sections[section_key] = section_data.get('text', '') if isinstance(section_data, dict) else str(section_data)

        # Detect mentions
        detector = UniversalProvisionDetector()
        all_mentions = detector.detect_all_provisions(case_sections)
        logger.info(f"[RunAll] Detected {len(all_mentions)} provision mentions")

        # Group mentions
        grouper = ProvisionGrouper()
        grouped_mentions = grouper.group_mentions_by_provision(all_mentions, provisions)

        # Validate each provision
        validator = ProvisionGroupValidator(llm_client)
        for provision in provisions:
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
            else:
                provision['relevant_excerpts'] = []

        # Link to entities
        all_entities = get_all_case_entities(case_id)
        linker = CodeProvisionLinker(llm_client)

        def format_entities(entities):
            return [
                {
                    'label': e.entity_label,
                    'definition': e.entity_definition or '',
                    'uri': e.rdf_json_ld.get('@id', '') if e.rdf_json_ld else ''
                }
                for e in entities
            ]

        provisions = linker.link_provisions_to_entities(
            provisions,
            roles=format_entities(all_entities.get('roles', [])),
            states=format_entities(all_entities.get('states', [])),
            resources=format_entities(all_entities.get('resources', [])),
            principles=format_entities(all_entities.get('principles', [])),
            obligations=format_entities(all_entities.get('obligations', [])),
            constraints=format_entities(all_entities.get('constraints', [])),
            capabilities=format_entities(all_entities.get('capabilities', [])),
            actions=format_entities(all_entities.get('actions', [])),
            events=format_entities(all_entities.get('events', [])),
            case_text_summary=f"Case {case_id}: {case.title}"
        )

        total_links = sum(len(p.get('applies_to', [])) for p in provisions)
        logger.info(f"[RunAll] Linked provisions to {total_links} entities")

        # Store provisions
        session_id = str(uuid.uuid4())
        for provision in provisions:
            rdf_entity = TemporaryRDFStorage(
                case_id=case_id,
                extraction_session_id=session_id,
                extraction_type='code_provision_reference',
                storage_type='individual',
                entity_type='provisions',
                entity_label=provision.get('code_provision', 'Unknown'),
                entity_definition=provision.get('provision_text', ''),
                rdf_json_ld={
                    '@type': 'proeth-case:CodeProvisionReference',
                    'codeProvision': provision.get('code_provision', ''),
                    'provisionText': provision.get('provision_text', ''),
                    'relevantExcerpts': provision.get('relevant_excerpts', []),
                    'appliesTo': provision.get('applies_to', [])
                },
                is_selected=True
            )
            db.session.add(rdf_entity)

        db.session.commit()
        logger.info(f"[RunAll] Stored {len(provisions)} provisions")

        return {
            'provisions_count': len(provisions),
            'entity_links': total_links
        }

    except Exception as e:
        logger.error(f"[RunAll] Provisions error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


def _run_qc_unified(case_id: int, llm_client, get_all_case_entities) -> dict:
    """
    Run Q&C unified extraction - SAME code as extract_qc_unified_streaming.
    """
    from app.services.question_analyzer import QuestionAnalyzer
    from app.services.conclusion_analyzer import ConclusionAnalyzer
    from app.services.question_conclusion_linker import QuestionConclusionLinker

    try:
        case = Document.query.get_or_404(case_id)

        # Load provisions
        provisions_records = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='code_provision_reference'
        ).all()
        provisions = [r.rdf_json_ld for r in provisions_records if r.rdf_json_ld]
        logger.info(f"[RunAll] Loaded {len(provisions)} provisions")

        # Get all entities
        all_entities = get_all_case_entities(case_id)

        # Get section text
        questions_text = ""
        conclusions_text = ""
        facts_text = ""
        if case.doc_metadata and 'sections_dual' in case.doc_metadata:
            sections = case.doc_metadata['sections_dual']
            if 'question' in sections:
                q_data = sections['question']
                questions_text = q_data.get('text', '') if isinstance(q_data, dict) else str(q_data)
            if 'conclusion' in sections:
                c_data = sections['conclusion']
                conclusions_text = c_data.get('text', '') if isinstance(c_data, dict) else str(c_data)
            if 'facts' in sections:
                f_data = sections['facts']
                facts_text = f_data.get('text', '') if isinstance(f_data, dict) else str(f_data)

        # Clear old Q&C
        TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_question'
        ).delete(synchronize_session=False)
        TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_conclusion'
        ).delete(synchronize_session=False)
        db.session.commit()

        # Extract questions
        question_analyzer = QuestionAnalyzer(llm_client)
        questions_result = question_analyzer.extract_questions_with_analysis(
            questions_text=questions_text,
            all_entities=all_entities,
            code_provisions=provisions,
            case_facts=facts_text,
            case_conclusion=conclusions_text
        )

        # Flatten all question types
        questions = []
        for q_type in ['board_explicit', 'implicit', 'principle_tension', 'theoretical', 'counterfactual']:
            for q in questions_result.get(q_type, []):
                q_dict = question_analyzer._question_to_dict(q) if hasattr(q, 'question_number') else q
                questions.append(q_dict)

        board_q_count = len(questions_result.get('board_explicit', []))
        logger.info(f"[RunAll] Extracted {board_q_count} Board + {len(questions) - board_q_count} analytical = {len(questions)} questions")

        # Get questions for conclusion context
        board_questions = [question_analyzer._question_to_dict(q) if hasattr(q, 'question_number') else q
                          for q in questions_result.get('board_explicit', [])]
        analytical_questions = [q for q in questions if q.get('question_type') != 'board_explicit']

        # Extract conclusions
        conclusion_analyzer = ConclusionAnalyzer(llm_client)
        conclusions_result = conclusion_analyzer.extract_conclusions_with_analysis(
            conclusions_text=conclusions_text,
            all_entities=all_entities,
            code_provisions=provisions,
            board_questions=board_questions,
            analytical_questions=analytical_questions,
            case_facts=facts_text
        )

        # Flatten all conclusion types
        conclusions = []
        for c_type in ['board_explicit', 'analytical_extension', 'question_response', 'principle_synthesis']:
            for c in conclusions_result.get(c_type, []):
                c_dict = conclusion_analyzer._conclusion_to_dict(c) if hasattr(c, 'conclusion_number') else c
                conclusions.append(c_dict)

        board_c_count = len(conclusions_result.get('board_explicit', []))
        logger.info(f"[RunAll] Extracted {board_c_count} Board + {len(conclusions) - board_c_count} analytical = {len(conclusions)} conclusions")

        # Link Q to C
        linker = QuestionConclusionLinker(llm_client)
        qc_links = linker.link_questions_to_conclusions(questions, conclusions)
        conclusions = linker.apply_links_to_conclusions(conclusions, qc_links)
        logger.info(f"[RunAll] Created {len(qc_links)} Q-C links")

        # Store everything
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
        logger.info(f"[RunAll] Stored {len(questions)} questions and {len(conclusions)} conclusions")

        return {
            'questions_count': len(questions),
            'conclusions_count': len(conclusions),
            'links_count': len(qc_links)
        }

    except Exception as e:
        logger.error(f"[RunAll] Q&C error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


def _run_transformation(case_id: int, llm_client) -> dict:
    """
    Run transformation classification - SAME code as extract_transformation_streaming.
    """
    from app.services.transformation_classifier import TransformationClassifier

    try:
        case = Document.query.get_or_404(case_id)

        # Load Q&C
        questions = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_question'
        ).all()
        conclusions = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_conclusion'
        ).all()

        if not questions or not conclusions:
            return {'error': 'No Q&C found - run Q&C extraction first'}

        # Convert to format expected by classifier
        q_list = [
            {
                'question_number': r.rdf_json_ld.get('questionNumber', 0),
                'question_text': r.rdf_json_ld.get('questionText', r.entity_definition),
                'question_type': r.rdf_json_ld.get('questionType', 'unknown')
            }
            for r in questions if r.rdf_json_ld
        ]
        c_list = [
            {
                'conclusion_number': r.rdf_json_ld.get('conclusionNumber', 0),
                'conclusion_text': r.rdf_json_ld.get('conclusionText', r.entity_definition),
                'conclusion_type': r.rdf_json_ld.get('conclusionType', 'unknown')
            }
            for r in conclusions if r.rdf_json_ld
        ]

        # Get facts section
        facts_text = ""
        if case.doc_metadata and 'sections_dual' in case.doc_metadata:
            sections = case.doc_metadata['sections_dual']
            if 'facts' in sections:
                f_data = sections['facts']
                facts_text = f_data.get('text', '') if isinstance(f_data, dict) else str(f_data)

        # Classify transformation
        classifier = TransformationClassifier(llm_client)
        result = classifier.classify_transformation(
            case_facts=facts_text,
            questions=q_list,
            conclusions=c_list,
            provisions=[]  # Already loaded in Q&C
        )

        logger.info(f"[RunAll] Transformation type: {result.transformation_type} (confidence: {result.confidence})")

        # Save ExtractionPrompt
        session_id = str(uuid.uuid4())
        if hasattr(classifier, 'last_prompt') and classifier.last_prompt:
            try:
                transformation_prompt = ExtractionPrompt(
                    case_id=case_id,
                    concept_type='transformation_classification',
                    step_number=4,
                    section_type='synthesis',
                    prompt_text=classifier.last_prompt,
                    llm_model='claude-sonnet-4-20250514',
                    extraction_session_id=session_id,
                    raw_response=getattr(classifier, 'last_response', ''),
                    results_summary=json.dumps({'transformation_type': result.transformation_type, 'confidence': result.confidence})
                )
                db.session.add(transformation_prompt)
                db.session.commit()
            except Exception as e:
                logger.warning(f"[RunAll] Could not save transformation prompt: {e}")

        return {
            'transformation_type': result.transformation_type,
            'confidence': result.confidence
        }

    except Exception as e:
        logger.error(f"[RunAll] Transformation error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


def _run_rich_analysis(case_id: int) -> dict:
    """
    Run rich analysis - SAME code as extract_rich_analysis_streaming.
    """
    from app.services.case_synthesizer import CaseSynthesizer

    try:
        case = Document.query.get_or_404(case_id)
        synthesizer = CaseSynthesizer()

        # Build foundation
        foundation = synthesizer._build_entity_foundation(case_id)
        if not foundation or foundation.summary()['total'] == 0:
            return {'error': 'No entities found - run Passes 1-3 first'}

        # Load Q&C
        questions, conclusions = synthesizer._load_qc(case_id)
        if not questions and not conclusions:
            return {'error': 'No Q&C found - run Q&C extraction first'}

        # Load provisions
        provisions = synthesizer._load_provisions(case_id)

        # Run rich analysis (same as streaming endpoint)
        llm_traces = []

        # Causal-normative links
        causal_links = synthesizer._analyze_causal_normative_links(foundation, llm_traces)
        logger.info(f"[RunAll] Causal links: {len(causal_links)}")

        # Question emergence
        question_emergence = []
        for i, q in enumerate(questions):
            batch_results = synthesizer._analyze_question_batch([q], foundation, llm_traces, i)
            question_emergence.extend(batch_results)
        logger.info(f"[RunAll] Question emergence: {len(question_emergence)}")

        # Resolution patterns
        resolution_patterns = synthesizer._analyze_resolution_patterns(
            conclusions, questions, provisions, llm_traces
        )
        logger.info(f"[RunAll] Resolution patterns: {len(resolution_patterns)}")

        # Store rich analysis
        synthesizer._store_rich_analysis(case_id, causal_links, question_emergence, resolution_patterns)

        # Save prompts for UI display
        session_id = str(uuid.uuid4())
        combined_prompt = ""
        combined_response = ""
        for trace in llm_traces:
            combined_prompt += f"\n--- {trace.stage.upper()} ---\n{trace.prompt}\n"
            combined_response += f"\n--- {trace.stage.upper()} ---\n{trace.response}\n"

        try:
            saved_prompt = ExtractionPrompt.save_prompt(
                case_id=case_id,
                concept_type='rich_analysis',
                prompt_text=combined_prompt,
                raw_response=combined_response,
                step_number=4,
                section_type='synthesis',
                llm_model='claude-sonnet-4-20250514',
                extraction_session_id=session_id
            )
            logger.info(f"[RunAll] Saved rich analysis prompt id={saved_prompt.id}")
        except Exception as e:
            logger.warning(f"[RunAll] Could not save rich analysis prompt: {e}")

        return {
            'causal_links': len(causal_links),
            'question_emergence': len(question_emergence),
            'resolution_patterns': len(resolution_patterns)
        }

    except Exception as e:
        logger.error(f"[RunAll] Rich analysis error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


def _run_phase3(case_id: int) -> dict:
    """
    Run Phase 3 decision synthesis - SAME code as synthesize_phase3_streaming.
    """
    from app.services.decision_point_synthesizer import synthesize_decision_points
    from app.services.case_synthesizer import CaseSynthesizer

    try:
        case = Document.query.get_or_404(case_id)
        synthesizer = CaseSynthesizer()

        # Load Q&C
        questions, conclusions = synthesizer._load_qc(case_id)
        if not questions:
            return {'error': 'No questions found - run Phase 2 extraction first'}

        # Load rich analysis data
        causal_links, question_emergence, resolution_patterns = synthesizer._load_rich_analysis(case_id)

        # Convert to dict format expected by synthesize_decision_points
        qe_dicts = [qe.to_dict() if hasattr(qe, 'to_dict') else vars(qe) for qe in question_emergence]
        rp_dicts = [rp.to_dict() if hasattr(rp, 'to_dict') else vars(rp) for rp in resolution_patterns]

        # Run Phase 3 synthesis
        result = synthesize_decision_points(
            case_id=case_id,
            questions=questions,
            conclusions=conclusions,
            question_emergence=qe_dicts,
            resolution_patterns=rp_dicts,
            domain='engineering',
            skip_llm=False
        )

        logger.info(f"[RunAll] Phase 3: {result.canonical_count} canonical decision points")

        # Save extraction prompt for provenance
        session_id = result.extraction_session_id or str(uuid.uuid4())
        if result.llm_prompt:
            try:
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
            except Exception as e:
                logger.warning(f"[RunAll] Could not save Phase 3 prompt: {e}")

        return {
            'canonical_count': result.canonical_count,
            'candidates_count': result.candidates_count,
            'high_alignment_count': result.high_alignment_count
        }

    except Exception as e:
        logger.error(f"[RunAll] Phase 3 error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


def _run_phase4(case_id: int) -> dict:
    """
    Run Phase 4 narrative construction - SAME code as construct_phase4_streaming.
    """
    from app.services.narrative import construct_phase4_narrative
    from app.services.precedent import update_precedent_features_from_phase4
    from app.services.case_synthesizer import CaseSynthesizer

    try:
        case = Document.query.get_or_404(case_id)
        synthesizer = CaseSynthesizer()

        # Build foundation
        foundation = synthesizer._build_entity_foundation(case_id)
        if not foundation or foundation.summary()['total'] == 0:
            return {'error': 'No entities found - run Passes 1-3 first'}

        # Load Phase 2-3 data
        canonical_points = synthesizer.load_canonical_points(case_id)
        _, conclusions = synthesizer._load_qc(case_id)

        # Get transformation type
        transformation_record = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='transformation_classification'
        ).order_by(ExtractionPrompt.created_at.desc()).first()
        transformation_type = None
        if transformation_record and transformation_record.results_summary:
            try:
                summary = json.loads(transformation_record.results_summary) if isinstance(transformation_record.results_summary, str) else transformation_record.results_summary
                transformation_type = summary.get('transformation_type')
            except:
                pass

        # Load causal links
        causal_links, _, _ = synthesizer._load_rich_analysis(case_id)

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

        logger.info(f"[RunAll] Phase 4: {len(result.narrative_elements.characters)} characters, {len(result.timeline.events)} events")

        # Save extraction prompt for provenance
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

        # Save whole_case_synthesis to mark as complete
        synthesis_summary = {
            'characters_count': len(result.narrative_elements.characters),
            'timeline_events_count': len(result.timeline.events),
            'scenario_branches_count': len(result.scenario_seeds.branches)
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
                narrative_result=result,
                transformation_type=transformation_type
            )
            logger.info(f"[RunAll] Updated precedent features from Phase 4")
        except Exception as e:
            logger.warning(f"[RunAll] Failed to update precedent features: {e}")

        return {
            'characters_count': len(result.narrative_elements.characters),
            'timeline_events': len(result.timeline.events),
            'branches_count': len(result.scenario_seeds.branches)
        }

    except Exception as e:
        logger.error(f"[RunAll] Phase 4 error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}
