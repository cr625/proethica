"""
Step 4 Synthesis Service

Provides unified synthesis logic that can be called from:
- Flask routes (step4_run_all.py)
- Celery tasks (pipeline_tasks.py)

This ensures the same code path is used regardless of invocation method.

Usage:
    from app.services.step4_synthesis_service import run_step4_synthesis

    # Synchronous call
    result = run_step4_synthesis(case_id)

    # With progress callback (for async status updates)
    def on_progress(stage, message):
        print(f"{stage}: {message}")
    result = run_step4_synthesis(case_id, progress_callback=on_progress)
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Callable, Optional
from dataclasses import dataclass, field

from models import ModelConfig
from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.utils.llm_utils import get_llm_client

logger = logging.getLogger(__name__)


@dataclass
class Step4SynthesisResult:
    """Result of Step 4 synthesis."""
    success: bool
    case_id: int
    stages_completed: list = field(default_factory=list)
    provisions_count: int = 0
    questions_count: int = 0
    conclusions_count: int = 0
    transformation_type: str = ''
    causal_links_count: int = 0
    decision_points_count: int = 0
    narrative_complete: bool = False
    error: str = None
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'case_id': self.case_id,
            'stages_completed': self.stages_completed,
            'provisions_count': self.provisions_count,
            'questions_count': self.questions_count,
            'conclusions_count': self.conclusions_count,
            'transformation_type': self.transformation_type,
            'causal_links_count': self.causal_links_count,
            'decision_points_count': self.decision_points_count,
            'narrative_complete': self.narrative_complete,
            'error': self.error,
            'duration_seconds': self.duration_seconds
        }


def run_step4_synthesis(
    case_id: int,
    progress_callback: Optional[Callable[[str, str], None]] = None,
    skip_clear: bool = False
) -> Step4SynthesisResult:
    """
    Run complete Step 4 synthesis for a case.

    This is the unified entry point for Step 4 synthesis, used by both
    Flask routes and Celery tasks.

    Args:
        case_id: Case ID to synthesize
        progress_callback: Optional callback for progress updates
            Signature: callback(stage: str, message: str)
        skip_clear: If True, don't clear existing Step 4 data first

    Returns:
        Step4SynthesisResult with synthesis results
    """
    start_time = datetime.now()
    result = Step4SynthesisResult(success=False, case_id=case_id)

    def notify(stage: str, message: str):
        logger.info(f"[Step4Synthesis] {stage}: {message}")
        if progress_callback:
            try:
                progress_callback(stage, message)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

    try:
        # Verify case exists
        case = Document.query.get(case_id)
        if not case:
            result.error = f"Case {case_id} not found"
            return result

        llm_client = get_llm_client()
        if not llm_client:
            result.error = "LLM client not available"
            return result

        # Helper to get entities - must return dict keyed by entity type
        def get_all_case_entities(cid):
            entity_type_map = {
                'roles': 'Roles',
                'states': 'States',
                'resources': 'Resources',
                'principles': 'Principles',
                'obligations': 'Obligations',
                'constraints': 'Constraints',
                'capabilities': 'Capabilities',
                'actions': 'actions',
                'events': 'events'
            }
            entities = {}
            for key, db_type in entity_type_map.items():
                entities[key] = TemporaryRDFStorage.query.filter_by(
                    case_id=cid,
                    entity_type=db_type,
                    storage_type='individual'
                ).all()
            return entities

        # =====================================================================
        # STEP 1: Clear existing Step 4 data (unless skipped)
        # =====================================================================
        if not skip_clear:
            notify('CLEAR', f"Clearing Step 4 data for case {case_id}")
            _clear_step4_data(case_id)
            result.stages_completed.append('CLEAR')

        # =====================================================================
        # STEP 2A: Provisions
        # =====================================================================
        notify('PROVISIONS', 'Extracting code provisions')
        provisions_result = _run_provisions(case_id, llm_client, get_all_case_entities)
        if provisions_result.get('error'):
            result.error = f"Provisions failed: {provisions_result.get('error')}"
            return result
        if provisions_result.get('skipped'):
            notify('PROVISIONS', f"Skipped: {provisions_result.get('reason', 'no references')}")
        result.provisions_count = provisions_result.get('provisions_count', len(provisions_result.get('provisions', [])))
        result.stages_completed.append('PROVISIONS')

        # =====================================================================
        # STEP 2C: Q&C Unified
        # =====================================================================
        notify('QC', 'Extracting questions and conclusions')
        qc_result = _run_qc_unified(case_id, llm_client, get_all_case_entities)
        if qc_result.get('error'):
            result.error = f"Q&C failed: {qc_result.get('error')}"
            return result
        result.questions_count = qc_result.get('questions_count', 0)
        result.conclusions_count = qc_result.get('conclusions_count', 0)
        result.stages_completed.append('QC')

        # =====================================================================
        # STEP 2D: Transformation
        # =====================================================================
        notify('TRANSFORMATION', 'Classifying transformation type')
        transformation_result = _run_transformation(case_id, llm_client, get_all_case_entities)
        result.transformation_type = transformation_result.get('transformation_type', 'unknown')
        result.stages_completed.append('TRANSFORMATION')

        # =====================================================================
        # STEP 2E: Rich Analysis
        # =====================================================================
        notify('RICH_ANALYSIS', 'Running rich analysis')
        rich_result = _run_rich_analysis(case_id, llm_client)
        if rich_result.get('error'):
            result.error = f"Rich analysis failed: {rich_result.get('error')}"
            return result
        result.causal_links_count = rich_result.get('causal_links_count', 0)
        result.stages_completed.append('RICH_ANALYSIS')

        # =====================================================================
        # PHASE 3: Decision Point Synthesis
        # =====================================================================
        notify('PHASE3', 'Synthesizing decision points')
        phase3_result = _run_phase3(case_id, llm_client)
        if phase3_result.get('error'):
            result.error = f"Phase 3 failed: {phase3_result.get('error')}"
            return result
        result.decision_points_count = phase3_result.get('canonical_count', 0)
        result.stages_completed.append('PHASE3')

        # =====================================================================
        # PHASE 4: Narrative Construction
        # =====================================================================
        notify('PHASE4', 'Constructing narrative')
        phase4_result = _run_phase4(case_id, llm_client)
        if phase4_result.get('error'):
            result.error = f"Phase 4 failed: {phase4_result.get('error')}"
            return result
        result.narrative_complete = True
        result.stages_completed.append('PHASE4')

        # =====================================================================
        # SUCCESS
        # =====================================================================
        result.success = True
        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        notify('COMPLETE', f"Synthesis complete in {result.duration_seconds:.1f}s")

        return result

    except Exception as e:
        logger.error(f"[Step4Synthesis] Failed for case {case_id}: {e}", exc_info=True)
        result.error = str(e)
        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        return result


# =============================================================================
# Helper functions (same logic as step4_run_all.py)
# =============================================================================

def _clear_step4_data(case_id: int) -> dict:
    """Clear existing Step 4 data for a case."""
    step4_types = [
        'code_provision_reference',
        'ethical_question',
        'ethical_conclusion',
        'causal_normative_link',
        'question_emergence',
        'resolution_pattern',
        'canonical_decision_point',
        'decision_point',
        'decision_option',
        'scenario_character',
        'scenario_timeline_event',
        'narrative_element'
    ]

    deleted_count = 0
    for entity_type in step4_types:
        count = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type=entity_type
        ).delete(synchronize_session=False)
        deleted_count += count

    # Also clear extraction prompts for step 4
    ExtractionPrompt.query.filter_by(
        case_id=case_id,
        step_number=4
    ).delete(synchronize_session=False)

    db.session.commit()
    return {'deleted_entities': deleted_count}


def _run_provisions(case_id: int, llm_client, get_all_case_entities) -> dict:
    """
    Run provisions extraction - SAME code as step4_run_all.py.
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
            # No references section or empty - skip provisions extraction but don't fail
            logger.info(f"[Step4Synthesis] No references content found for case {case_id} - skipping provisions")
            return {
                'provisions': [],
                'all_mentions': [],
                'validation_results': [],
                'skipped': True,
                'reason': 'No references section content'
            }

        # Parse provisions
        parser = NSPEReferencesParser()
        provisions = parser.parse_references_html(references_html)
        logger.info(f"[Step4Synthesis] Parsed {len(provisions)} NSPE code provisions")

        # Get case sections for detection
        case_sections = {}
        for section_key in ['facts', 'discussion', 'question', 'conclusion']:
            if section_key in sections_dual:
                section_data = sections_dual[section_key]
                case_sections[section_key] = section_data.get('text', '') if isinstance(section_data, dict) else str(section_data)

        # Detect mentions
        detector = UniversalProvisionDetector()
        all_mentions = detector.detect_all_provisions(case_sections)
        logger.info(f"[Step4Synthesis] Detected {len(all_mentions)} provision mentions")

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
        logger.info(f"[Step4Synthesis] Linked provisions to {total_links} entities")

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
        logger.info(f"[Step4Synthesis] Stored {len(provisions)} provisions")

        return {
            'provisions_count': len(provisions),
            'entity_links': total_links
        }

    except Exception as e:
        logger.error(f"[Step4Synthesis] Provisions error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


def _run_qc_unified(case_id: int, llm_client, get_all_case_entities) -> dict:
    """
    Run Q&C unified extraction - SAME code as step4_run_all.py.
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
        logger.info(f"[Step4Synthesis] Loaded {len(provisions)} provisions")

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
        logger.info(f"[Step4Synthesis] Extracted {board_q_count} Board + {len(questions) - board_q_count} analytical = {len(questions)} questions")

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
        logger.info(f"[Step4Synthesis] Extracted {board_c_count} Board + {len(conclusions) - board_c_count} analytical = {len(conclusions)} conclusions")

        # Link Q to C
        linker = QuestionConclusionLinker(llm_client)
        qc_links = linker.link_questions_to_conclusions(questions, conclusions)
        conclusions = linker.apply_links_to_conclusions(conclusions, qc_links)
        logger.info(f"[Step4Synthesis] Created {len(qc_links)} Q-C links")

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
        logger.info(f"[Step4Synthesis] Stored {len(questions)} questions and {len(conclusions)} conclusions")

        # Save ExtractionPrompts for UI display
        try:
            q_prompt_text = getattr(question_analyzer, 'last_prompt', None) or f'LLM extraction of {len(questions)} questions'
            q_response_text = getattr(question_analyzer, 'last_response', None) or ''

            questions_prompt = ExtractionPrompt(
                case_id=case_id,
                concept_type='ethical_question',
                step_number=4,
                section_type='synthesis',
                prompt_text=q_prompt_text[:10000] if q_prompt_text else 'Question extraction',
                llm_model=ModelConfig.get_claude_model("default"),
                extraction_session_id=session_id,
                raw_response=q_response_text[:10000] if q_response_text else '',
                results_summary=json.dumps({
                    'total': len(questions),
                    'board_explicit': board_q_count,
                    'analytical': len(questions) - board_q_count
                })
            )
            db.session.add(questions_prompt)

            c_prompt_text = getattr(conclusion_analyzer, 'last_prompt', None) or f'LLM extraction of {len(conclusions)} conclusions'
            c_response_text = getattr(conclusion_analyzer, 'last_response', None) or ''

            conclusions_prompt = ExtractionPrompt(
                case_id=case_id,
                concept_type='ethical_conclusion',
                step_number=4,
                section_type='synthesis',
                prompt_text=c_prompt_text[:10000] if c_prompt_text else 'Conclusion extraction',
                llm_model=ModelConfig.get_claude_model("default"),
                extraction_session_id=session_id,
                raw_response=c_response_text[:10000] if c_response_text else '',
                results_summary=json.dumps({
                    'total': len(conclusions),
                    'board_explicit': board_c_count,
                    'analytical': len(conclusions) - board_c_count,
                    'qc_links': len(qc_links)
                })
            )
            db.session.add(conclusions_prompt)
            db.session.commit()
            logger.info(f"[Step4Synthesis] Saved Q&C ExtractionPrompts with LLM prompts")
        except Exception as e:
            logger.warning(f"[Step4Synthesis] Could not save Q&C prompts: {e}")

        return {
            'questions_count': len(questions),
            'conclusions_count': len(conclusions),
            'links_count': len(qc_links)
        }

    except Exception as e:
        logger.error(f"[Step4Synthesis] Q&C error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


def _run_transformation(case_id: int, llm_client, get_all_case_entities) -> dict:
    """
    Run transformation classification - SAME code as step4_run_all.py.
    """
    from app.services.case_analysis.transformation_classifier import TransformationClassifier

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

        # Get all entities for context
        all_entities = get_all_case_entities(case_id)

        # Classify transformation
        classifier = TransformationClassifier(llm_client)
        result = classifier.classify(
            case_id=case_id,
            questions=q_list,
            conclusions=c_list,
            case_title=case.title,
            case_facts=facts_text,
            all_entities=all_entities
        )

        logger.info(f"[Step4Synthesis] Transformation type: {result.transformation_type} (confidence: {result.confidence})")

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
                    llm_model=ModelConfig.get_claude_model("default"),
                    extraction_session_id=session_id,
                    raw_response=getattr(classifier, 'last_response', ''),
                    results_summary=json.dumps({'transformation_type': result.transformation_type, 'confidence': result.confidence})
                )
                db.session.add(transformation_prompt)
                db.session.commit()
            except Exception as e:
                logger.warning(f"[Step4Synthesis] Could not save transformation prompt: {e}")

        return {
            'transformation_type': result.transformation_type,
            'confidence': result.confidence
        }

    except Exception as e:
        logger.error(f"[Step4Synthesis] Transformation error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


def _run_rich_analysis(case_id: int, llm_client) -> dict:
    """
    Run rich analysis - SAME code as step4_run_all.py.
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

        # Run rich analysis via RichAnalyzer (label-based prompts)
        from app.services.rich_analysis import RichAnalyzer
        analyzer = RichAnalyzer()
        llm_traces = []

        causal_links = analyzer.analyze_causal_normative_links(foundation, llm_traces)
        logger.info(f"[Step4Synthesis] Causal links: {len(causal_links)}")

        question_emergence = []
        for i, q in enumerate(questions):
            batch_results = analyzer.analyze_question_batch([q], foundation, llm_traces, i)
            question_emergence.extend(batch_results)
        logger.info(f"[Step4Synthesis] Question emergence: {len(question_emergence)}")

        resolution_patterns = analyzer.analyze_resolution_patterns(
            conclusions, questions, provisions, foundation, llm_traces
        )
        logger.info(f"[Step4Synthesis] Resolution patterns: {len(resolution_patterns)}")

        analyzer.store_rich_analysis(case_id, causal_links, question_emergence, resolution_patterns)

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
                llm_model=ModelConfig.get_claude_model("default"),
                extraction_session_id=session_id
            )
            logger.info(f"[Step4Synthesis] Saved rich analysis prompt id={saved_prompt.id}")
        except Exception as e:
            logger.warning(f"[Step4Synthesis] Could not save rich analysis prompt: {e}")

        return {
            'causal_links_count': len(causal_links),
            'question_emergence_count': len(question_emergence),
            'resolution_patterns_count': len(resolution_patterns)
        }

    except Exception as e:
        logger.error(f"[Step4Synthesis] Rich analysis error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


def _run_phase3(case_id: int, llm_client) -> dict:
    """Run Phase 3 decision point synthesis."""
    try:
        from app.services.decision_point_synthesizer import synthesize_decision_points

        # Load Phase 2 data
        questions = [e.rdf_json_ld for e in TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type='ethical_question').all()]
        conclusions = [e.rdf_json_ld for e in TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type='ethical_conclusion').all()]
        question_emergence = [e.rdf_json_ld for e in TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type='question_emergence').all()]
        resolution_patterns = [e.rdf_json_ld for e in TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type='resolution_pattern').all()]

        # Run synthesis (this has the unified LLM fallback)
        result = synthesize_decision_points(
            case_id=case_id,
            questions=questions,
            conclusions=conclusions,
            question_emergence=question_emergence,
            resolution_patterns=resolution_patterns,
            domain='engineering',
            skip_llm=False
        )

        # Save prompt
        session_id = result.extraction_session_id or str(uuid.uuid4())
        if result.llm_prompt:
            prompt_text = result.llm_prompt[:10000]
            raw_response = result.llm_response[:10000] if result.llm_response else ''
        else:
            prompt_text = 'Phase 3 Decision Point Synthesis (E1-E3 Algorithmic)'
            raw_response = f'Candidates: {result.candidates_count}, Canonical: {result.canonical_count}'

        prompt = ExtractionPrompt(
            case_id=case_id,
            concept_type='phase3_decision_synthesis',
            step_number=4,
            section_type='synthesis',
            prompt_text=prompt_text,
            llm_model=ModelConfig.get_claude_model("default") if result.llm_prompt else 'algorithmic',
            extraction_session_id=session_id,
            raw_response=raw_response,
            results_summary=json.dumps({
                'canonical_count': result.canonical_count,
                'candidates_count': result.candidates_count
            })
        )
        db.session.add(prompt)
        db.session.commit()

        return {
            'canonical_count': result.canonical_count,
            'candidates_count': result.candidates_count
        }

    except Exception as e:
        logger.error(f"Phase 3 failed: {e}", exc_info=True)
        return {'error': str(e)}


def _run_phase4(case_id: int, llm_client) -> dict:
    """
    Run Phase 4 narrative construction - SAME code as step4_run_all.py.
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

        # Load causal links (from database, as dicts)
        links_raw = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='causal_normative_link'
        ).all()
        causal_links = [
            link.rdf_json_ld if link.rdf_json_ld else {
                'action_uri': link.entity_uri or '',
                'action_label': link.entity_label,
                'obligation_uri': '',
                'obligation_label': ''
            }
            for link in links_raw
        ]

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

        logger.info(f"[Step4Synthesis] Phase 4: {len(result.narrative_elements.characters)} characters, {len(result.timeline.events)} events")

        # Save extraction prompt for provenance
        session_id = str(uuid.uuid4())
        extraction_prompt = ExtractionPrompt(
            case_id=case_id,
            concept_type='phase4_narrative',
            step_number=4,
            section_type='synthesis',
            prompt_text=f"Phase 4 Narrative Construction - {len(result.stages_completed)} stages",
            llm_model=ModelConfig.get_claude_model("default"),
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
            llm_model=ModelConfig.get_claude_model("default"),
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
            logger.info(f"[Step4Synthesis] Updated precedent features from Phase 4")
        except Exception as e:
            logger.warning(f"[Step4Synthesis] Failed to update precedent features: {e}")

        return {
            'characters_count': len(result.narrative_elements.characters),
            'timeline_events_count': len(result.timeline.events),
            'branches_count': len(result.scenario_seeds.branches)
        }

    except Exception as e:
        logger.error(f"[Step4Synthesis] Phase 4 error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}
