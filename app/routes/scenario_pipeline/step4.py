"""
Step 4: Whole-Case Synthesis

Analyzes analytical sections (Code Provisions, Questions, Conclusions) with
complete entity context after all 3 passes complete.

Three-Part Synthesis:
  Part A: Code Provisions (References section)
  Part B: Questions & Conclusions
  Part C: Cross-Section Synthesis
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from flask import Blueprint, render_template, request, jsonify

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
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

# Import streaming synthesis
from app.routes.scenario_pipeline.step4_streaming import synthesize_case_streaming

logger = logging.getLogger(__name__)

bp = Blueprint('step4', __name__, url_prefix='/scenario_pipeline')


def init_step4_csrf_exemption(app):
    """Exempt Step 4 synthesis route from CSRF protection"""
    if hasattr(app, 'csrf') and app.csrf:
        from app.routes.scenario_pipeline.step4 import synthesize_case
        app.csrf.exempt(synthesize_case)


@bp.route('/case/<int:case_id>/step4')
def step4_synthesis(case_id):
    """
    Display Step 4 synthesis page.

    Shows entity summary from Passes 1-3 and synthesis status.
    """
    try:
        case = Document.query.get_or_404(case_id)

        # Get entity counts from all passes
        entities_summary = get_entities_summary(case_id)

        # Check synthesis status
        synthesis_status = get_synthesis_status(case_id)

        return render_template(
            'scenarios/step4.html',
            case=case,
            entities_summary=entities_summary,
            synthesis_status=synthesis_status,
            current_step=4,
            prev_step_url=f"/scenario_pipeline/case/{case_id}/step3",
            next_step_url="#"
        )

    except Exception as e:
        logger.error(f"Error displaying Step 4 for case {case_id}: {e}")
        return str(e), 500


@bp.route('/case/<int:case_id>/synthesis_results')
def view_synthesis_results(case_id):
    """
    Display detailed synthesis results visualization.

    Shows:
    - Entity graph structure
    - Causal-normative links
    - Question emergence analysis
    - Resolution patterns
    """
    try:
        case = Document.query.get_or_404(case_id)

        # Load synthesis results from database
        synthesis_prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='whole_case_synthesis'
        ).order_by(ExtractionPrompt.created_at.desc()).first()

        if not synthesis_prompt:
            return render_template(
                'scenarios/synthesis_results.html',
                case=case,
                synthesis_data=None,
                error_message="No synthesis results found. Please run synthesis first.",
                current_step=4,
                prev_step_url=f"/scenario_pipeline/case/{case_id}/step4",
                next_step_url="#"
            )

        # Parse synthesis data
        import json
        synthesis_data = json.loads(synthesis_prompt.raw_response)

        # Load entity graph for displaying node details
        entity_graph_data = _load_entity_graph_details(case_id, synthesis_data)

        return render_template(
            'scenarios/synthesis_results.html',
            case=case,
            synthesis_data=synthesis_data,
            entity_graph_data=entity_graph_data,
            synthesis_timestamp=synthesis_prompt.created_at,
            results_summary=synthesis_prompt.results_summary,
            current_step=4,
            prev_step_url=f"/scenario_pipeline/case/{case_id}/step4",
            next_step_url="#"
        )

    except Exception as e:
        logger.error(f"Error viewing synthesis results for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return str(e), 500


def _load_entity_graph_details(case_id: int, synthesis_data: Dict) -> Dict:
    """
    Load detailed entity information for graph visualization

    Returns:
        Dict with entity details indexed by entity_id
    """
    entity_details = {}

    # Load all entities from database
    entities = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        storage_type='individual'
    ).all()

    for entity in entities:
        entity_id = f"{entity.entity_type}_{entity.id}"
        entity_details[entity_id] = {
            'id': entity_id,
            'type': entity.entity_type,
            'label': entity.entity_label,
            'definition': entity.entity_definition,
            'rdf_json_ld': entity.rdf_json_ld
        }

    return entity_details


@bp.route('/case/<int:case_id>/synthesize_streaming')
def synthesize_streaming(case_id):
    """
    Execute whole-case synthesis with Server-Sent Events streaming.

    Real-time progress updates showing:
    - Part A: Code Provisions extraction
    - Part B: Questions & Conclusions extraction
    - Part C: Cross-section synthesis
    - LLM prompts and responses for each stage
    """
    return synthesize_case_streaming(case_id)


@bp.route('/case/<int:case_id>/save_streaming_results', methods=['POST'])
def save_streaming_results(case_id):
    """
    Save Step 4 streaming synthesis results to database.

    Called by frontend after SSE streaming completes to persist
    LLM prompts and responses for page refresh persistence.
    """
    from app.routes.scenario_pipeline.step4_streaming import save_step4_streaming_results
    return save_step4_streaming_results(case_id)


@bp.route('/case/<int:case_id>/synthesize', methods=['POST'])
def synthesize_case(case_id):
    """
    Execute whole-case synthesis (legacy endpoint).

    Three-part process:
    1. Extract and link code provisions
    2. Extract and link questions/conclusions
    3. Perform cross-section synthesis
    """
    try:
        case = Document.query.get_or_404(case_id)

        logger.info(f"Starting Step 4 synthesis for case {case_id}")

        # PART A: Code Provisions
        logger.info("Part A: Extracting code provisions")
        provisions = extract_and_link_provisions(case_id, case)

        # PART B: Questions & Conclusions
        logger.info("Part B: Extracting questions and conclusions")
        questions, conclusions = extract_questions_conclusions(
            case_id,
            case,
            provisions
        )

        # PART C: Cross-Section Synthesis
        logger.info("Part C: Performing cross-section synthesis")
        synthesis_results = perform_cross_section_synthesis(
            case_id,
            provisions,
            questions,
            conclusions
        )

        logger.info(f"Step 4 synthesis complete for case {case_id}")

        return jsonify({
            'success': True,
            'provisions_count': len(provisions),
            'questions_count': len(questions),
            'conclusions_count': len(conclusions),
            'synthesis_results': synthesis_results
        })

    except Exception as e:
        logger.error(f"Error in synthesis for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_entities_summary(case_id: int) -> Dict:
    """
    Get summary of all extracted entities from Passes 1-3.

    Returns:
        Dict with entity counts by type
    """
    from sqlalchemy import func

    # Use case-insensitive queries with func.lower()
    summary = {}

    # Pass 1
    summary['roles'] = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        func.lower(TemporaryRDFStorage.entity_type) == 'roles',
        TemporaryRDFStorage.storage_type == 'individual'
    ).count()

    summary['states'] = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        func.lower(TemporaryRDFStorage.entity_type) == 'states',
        TemporaryRDFStorage.storage_type == 'individual'
    ).count()

    summary['resources'] = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        func.lower(TemporaryRDFStorage.entity_type) == 'resources',
        TemporaryRDFStorage.storage_type == 'individual'
    ).count()

    # Pass 2
    summary['principles'] = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        func.lower(TemporaryRDFStorage.entity_type) == 'principles',
        TemporaryRDFStorage.storage_type == 'individual'
    ).count()

    summary['obligations'] = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        func.lower(TemporaryRDFStorage.entity_type) == 'obligations',
        TemporaryRDFStorage.storage_type == 'individual'
    ).count()

    summary['constraints'] = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        func.lower(TemporaryRDFStorage.entity_type) == 'constraints',
        TemporaryRDFStorage.storage_type == 'individual'
    ).count()

    summary['capabilities'] = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        func.lower(TemporaryRDFStorage.entity_type) == 'capabilities',
        TemporaryRDFStorage.storage_type == 'individual'
    ).count()

    # Pass 3 - Handle combined Actions_events or separate actions/events
    actions_events_count = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        func.lower(TemporaryRDFStorage.entity_type) == 'actions_events',
        TemporaryRDFStorage.storage_type == 'individual'
    ).count()

    actions_only = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        func.lower(TemporaryRDFStorage.entity_type) == 'actions',
        TemporaryRDFStorage.storage_type == 'individual'
    ).count()

    events_only = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        func.lower(TemporaryRDFStorage.entity_type) == 'events',
        TemporaryRDFStorage.storage_type == 'individual'
    ).count()

    # If combined, split evenly for display (or query individually)
    if actions_events_count > 0 and actions_only == 0 and events_only == 0:
        summary['actions'] = actions_events_count  # Show all as actions
        summary['events'] = 0  # Combined format
    else:
        summary['actions'] = actions_only
        summary['events'] = events_only

    # Calculate totals
    summary['pass1_total'] = sum([
        summary['roles'],
        summary['states'],
        summary['resources']
    ])
    summary['pass2_total'] = sum([
        summary['principles'],
        summary['obligations'],
        summary['constraints'],
        summary['capabilities']
    ])
    summary['pass3_total'] = sum([
        summary['actions'],
        summary['events']
    ])
    summary['total'] = summary['pass1_total'] + summary['pass2_total'] + summary['pass3_total']

    return summary


def get_synthesis_status(case_id: int) -> Dict:
    """
    Check if synthesis has been completed for this case.

    Returns:
        Dict with synthesis status and results
    """
    # Check for code provisions
    provisions = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='code_provision_reference'
    ).count()

    # Check for questions
    questions = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='ethical_question'
    ).count()

    # Check for conclusions
    conclusions = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='ethical_conclusion'
    ).count()

    completed = provisions > 0 or questions > 0 or conclusions > 0

    return {
        'completed': completed,
        'provisions_count': provisions,
        'questions_count': questions,
        'conclusions_count': conclusions
    }


def get_all_case_entities(case_id: int) -> Dict[str, List]:
    """
    Query ALL extracted entities from Passes 1-3.

    Returns:
        Dict with entities by type:
        {
            'roles': [...],
            'states': [...],
            ...
        }
    """
    entity_types = [
        'roles', 'states', 'resources',
        'principles', 'obligations', 'constraints', 'capabilities',
        'actions', 'events'
    ]

    entities = {}
    for entity_type in entity_types:
        entities[entity_type] = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            entity_type=entity_type,
            storage_type='individual'
        ).all()

    logger.info(
        f"Loaded entities for case {case_id}: "
        f"{sum(len(entities[t]) for t in entity_types)} total"
    )

    return entities


# ============================================================================
# PART A: CODE PROVISIONS
# ============================================================================

def extract_and_link_provisions(case_id: int, case: Document) -> List[Dict]:
    """
    Part A: Extract code provisions and link to all entity types.

    Returns:
        List of provision dicts with excerpts and entity links
    """
    logger.info(f"Part A: Starting code provision extraction for case {case_id}")

    # Get references section HTML
    references_html = None
    if case.doc_metadata and 'sections_dual' in case.doc_metadata:
        for section_key, section_content in case.doc_metadata['sections_dual'].items():
            if 'reference' in section_key.lower():
                if isinstance(section_content, dict):
                    references_html = section_content.get('html', '')
                break

    if not references_html:
        logger.warning(f"No references section found for case {case_id}")
        return []

    # Parse HTML to extract provisions
    parser = NSPEReferencesParser()
    provisions = parser.parse_references_html(references_html)

    if not provisions:
        logger.warning(f"No provisions parsed for case {case_id}")
        return []

    logger.info(f"Parsed {len(provisions)} provisions")

    # Get ALL entities (9 types)
    all_entities = get_all_case_entities(case_id)

    # Prepare case sections for mention detection
    case_sections = {}
    if case.doc_metadata and 'sections_dual' in case.doc_metadata:
        sections = case.doc_metadata['sections_dual']
        for section_key in ['facts', 'discussion', 'question', 'conclusion']:
            if section_key in sections:
                section_data = sections[section_key]
                if isinstance(section_data, dict):
                    case_sections[section_key] = section_data.get('text', '')
                else:
                    case_sections[section_key] = str(section_data)

    # Stage 1: Universal detection
    detector = UniversalProvisionDetector()
    all_mentions = detector.detect_all_provisions(case_sections)

    logger.info(f"Detected {len(all_mentions)} provision mentions")

    # Stage 2: Group by provision
    grouper = ProvisionGrouper()
    grouped_mentions = grouper.group_mentions_by_provision(
        all_mentions,
        provisions
    )

    # Stage 3: Validate with LLM
    llm_client = get_llm_client()
    validator = ProvisionGroupValidator(llm_client)

    for provision in provisions:
        code = provision['code_provision']
        mentions = grouped_mentions.get(code, [])

        if not mentions:
            provision['relevant_excerpts'] = []
            continue

        validated = validator.validate_group(
            code,
            provision['provision_text'],
            mentions
        )

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

    # Link to entities (ALL 9 types)
    linker = CodeProvisionLinker(llm_client)

    # Format entities for linker
    def format_entities(entity_list):
        return [
            {
                'label': e.entity_label,
                'definition': e.entity_definition
            }
            for e in entity_list
        ]

    linked_provisions = linker.link_provisions_to_entities(
        provisions,
        roles=format_entities(all_entities['roles']),
        states=format_entities(all_entities['states']),
        resources=format_entities(all_entities['resources']),
        principles=format_entities(all_entities['principles']),
        obligations=format_entities(all_entities['obligations']),
        constraints=format_entities(all_entities['constraints']),
        capabilities=format_entities(all_entities['capabilities']),
        actions=format_entities(all_entities['actions']),
        events=format_entities(all_entities['events']),
        case_text_summary=f"Case {case_id}: {case.title}"
    )

    # Store provisions
    session_id = str(uuid.uuid4())

    # Clear old provisions
    TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='code_provision_reference'
    ).delete(synchronize_session=False)

    # Save extraction prompt
    extraction_prompt = ExtractionPrompt(
        case_id=case_id,
        concept_type='code_provision_reference',
        step_number=4,
        section_type='references',
        prompt_text=linker.last_linking_prompt or 'Code provision extraction',
        llm_model='claude-opus-4-20250514',
        extraction_session_id=session_id,
        raw_response=linker.last_linking_response or '',
        results_summary={
            'total_provisions': len(linked_provisions),
            'total_excerpts': sum(len(p.get('relevant_excerpts', [])) for p in linked_provisions)
        },
        is_active=True,
        times_used=1,
        created_at=datetime.utcnow(),
        last_used_at=datetime.utcnow()
    )
    db.session.add(extraction_prompt)

    # Store provisions
    for provision in linked_provisions:
        label = f"NSPE_{provision['code_provision'].replace('.', '_')}"

        rdf_entity = TemporaryRDFStorage(
            case_id=case_id,
            extraction_session_id=session_id,
            extraction_type='code_provision_reference',
            storage_type='individual',
            entity_type='resources',
            entity_label=label,
            entity_definition=provision['provision_text'],
            rdf_json_ld={
                '@type': 'proeth-case:CodeProvisionReference',
                'label': label,
                'codeProvision': provision['code_provision'],
                'provisionText': provision['provision_text'],
                'subjectReferences': provision.get('subject_references', []),
                'appliesTo': provision.get('applies_to', []),
                'relevantExcerpts': provision.get('relevant_excerpts', []),
                'providedBy': 'NSPE Board of Ethical Review',
                'authoritative': True
            },
            is_selected=True
        )
        db.session.add(rdf_entity)

    db.session.commit()

    logger.info(f"Part A complete: Stored {len(linked_provisions)} code provisions")

    return linked_provisions


# ============================================================================
# PART B: QUESTIONS & CONCLUSIONS
# ============================================================================

def extract_questions_conclusions(
    case_id: int,
    case: Document,
    provisions: List[Dict]
) -> Tuple[List, List]:
    """
    Part B: Extract questions and conclusions with entity tagging.

    Returns:
        Tuple of (questions, conclusions)
    """
    logger.info(f"Part B: Starting Q&C extraction for case {case_id}")

    # Get ALL entities
    all_entities = get_all_case_entities(case_id)

    # Get Questions and Conclusions section text
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

    llm_client = get_llm_client()

    # Extract questions
    question_analyzer = QuestionAnalyzer(llm_client)
    questions = question_analyzer.extract_questions(
        questions_text,
        all_entities,
        provisions
    )

    logger.info(f"Extracted {len(questions)} questions")

    # Extract conclusions
    conclusion_analyzer = ConclusionAnalyzer(llm_client)
    conclusions = conclusion_analyzer.extract_conclusions(
        conclusions_text,
        all_entities,
        provisions
    )

    logger.info(f"Extracted {len(conclusions)} conclusions")

    # Link Q→C
    linker = QuestionConclusionLinker(llm_client)
    qc_links = linker.link_questions_to_conclusions(questions, conclusions)

    logger.info(f"Created {len(qc_links)} Q→C links")

    # Apply links to conclusions
    conclusions = linker.apply_links_to_conclusions(conclusions, qc_links)

    # Store questions and conclusions
    session_id = str(uuid.uuid4())

    # Clear old Q&C
    TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='ethical_question'
    ).delete(synchronize_session=False)

    TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='ethical_conclusion'
    ).delete(synchronize_session=False)

    # Store questions
    for question in questions:
        rdf_entity = TemporaryRDFStorage(
            case_id=case_id,
            extraction_session_id=session_id,
            extraction_type='ethical_question',
            storage_type='individual',
            entity_type='questions',
            entity_label=f"Question_{question.question_number}",
            entity_definition=question.question_text,
            rdf_json_ld={
                '@type': 'proeth-case:EthicalQuestion',
                'questionNumber': question.question_number,
                'questionText': question.question_text,
                'mentionedEntities': question.mentioned_entities,
                'relatedProvisions': question.related_provisions,
                'extractionReasoning': question.extraction_reasoning
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
            entity_label=f"Conclusion_{conclusion.conclusion_number}",
            entity_definition=conclusion.conclusion_text,
            rdf_json_ld={
                '@type': 'proeth-case:EthicalConclusion',
                'conclusionNumber': conclusion.conclusion_number,
                'conclusionText': conclusion.conclusion_text,
                'mentionedEntities': conclusion.mentioned_entities,
                'citedProvisions': conclusion.cited_provisions,
                'conclusionType': conclusion.conclusion_type,
                'answersQuestions': getattr(conclusion, 'answers_questions', []),
                'extractionReasoning': conclusion.extraction_reasoning
            },
            is_selected=True
        )
        db.session.add(rdf_entity)

    db.session.commit()

    logger.info(f"Part B complete: Stored {len(questions)} questions, {len(conclusions)} conclusions")

    return questions, conclusions


# ============================================================================
# PART C: CROSS-SECTION SYNTHESIS
# ============================================================================

def perform_cross_section_synthesis(
    case_id: int,
    provisions: List[Dict],
    questions: List,
    conclusions: List
) -> Dict:
    """
    Part C: Cross-section synthesis operations.

    Uses CaseSynthesisService to:
    - Build entity knowledge graph
    - Link causal chains to normative requirements
    - Analyze question emergence
    - Extract resolution patterns

    Returns:
        Dict with synthesis results
    """
    logger.info(f"Part C: Starting cross-section synthesis for case {case_id}")

    # Initialize synthesis service
    llm_client = get_llm_client()
    synthesis_service = CaseSynthesisService(llm_client)

    try:
        # Run comprehensive synthesis
        synthesis = synthesis_service.synthesize_case(case_id)

        # Convert to dict for JSON response
        synthesis_results = {
            'entity_graph': {
                'status': 'complete',
                'total_nodes': synthesis.total_nodes,
                'node_types': len(synthesis.entity_graph.by_type),
                'sections': len(synthesis.entity_graph.by_section)
            },
            'causal_normative_links': {
                'status': 'complete',
                'total_links': len(synthesis.causal_normative_links),
                'actions_linked': len([l for l in synthesis.causal_normative_links if 'actions' in l.action_id]),
                'events_linked': len([l for l in synthesis.causal_normative_links if 'events' in l.action_id])
            },
            'question_emergence': {
                'status': 'complete',
                'total_questions': len(synthesis.question_emergence),
                'questions_with_triggers': len([q for q in synthesis.question_emergence
                                                if q.triggered_by_events or q.triggered_by_actions])
            },
            'resolution_patterns': {
                'status': 'complete',
                'total_patterns': len(synthesis.resolution_patterns),
                'pattern_types': list(set([p.pattern_type for p in synthesis.resolution_patterns]))
            },
            'statistics': {
                'synthesis_timestamp': synthesis.synthesis_timestamp.isoformat(),
                'total_entities': synthesis.total_nodes,
                'total_provisions': len(provisions),
                'total_questions': len(questions),
                'total_conclusions': len(conclusions)
            }
        }

        # Store synthesis for later viewing
        _store_synthesis_results(case_id, synthesis)

        logger.info(f"Part C complete: Full synthesis performed")

        return synthesis_results

    except Exception as e:
        logger.error(f"Error in synthesis: {e}")
        import traceback
        traceback.print_exc()

        # Return error status
        return {
            'entity_graph': {
                'status': 'error',
                'message': str(e)
            },
            'error': str(e)
        }


def _store_synthesis_results(case_id: int, synthesis) -> None:
    """
    Store synthesis results for later viewing

    Creates a special extraction prompt entry with synthesis results.
    """
    import json
    import uuid
    from datetime import datetime

    session_id = str(uuid.uuid4())

    # Serialize synthesis results
    synthesis_data = {
        'entity_graph': {
            'total_nodes': len(synthesis.entity_graph.nodes),
            'by_type': {k: len(v) for k, v in synthesis.entity_graph.by_type.items()},
            'by_section': {k: len(v) for k, v in synthesis.entity_graph.by_section.items()}
        },
        'causal_normative_links': [
            {
                'action_id': link.action_id,
                'action_label': link.action_label,
                'fulfills_obligations': link.fulfills_obligations,
                'violates_obligations': link.violates_obligations,
                'guided_by_principles': link.guided_by_principles,
                'constrained_by': link.constrained_by,
                'enabled_by_capabilities': link.enabled_by_capabilities,
                'agent_role': link.agent_role,
                'agent_state': link.agent_state,
                'used_resources': link.used_resources,
                'reasoning': link.reasoning,
                'confidence': link.confidence
            }
            for link in synthesis.causal_normative_links
        ],
        'question_emergence': [
            {
                'question_id': qe.question_id,
                'question_text': qe.question_text,
                'question_number': qe.question_number,
                'triggered_by_events': qe.triggered_by_events,
                'triggered_by_actions': qe.triggered_by_actions,
                'involves_states': qe.involves_states,
                'involves_roles': qe.involves_roles,
                'competing_obligations': qe.competing_obligations,
                'competing_principles': qe.competing_principles,
                'emergence_narrative': qe.emergence_narrative,
                'confidence': qe.confidence
            }
            for qe in synthesis.question_emergence
        ],
        'resolution_patterns': [
            {
                'conclusion_id': rp.conclusion_id,
                'conclusion_text': rp.conclusion_text,
                'conclusion_number': rp.conclusion_number,
                'answers_questions': rp.answers_questions,
                'determinative_principles': rp.determinative_principles,
                'determinative_facts': rp.determinative_facts,
                'cited_provisions': rp.cited_provisions,
                'pattern_type': rp.pattern_type,
                'resolution_narrative': rp.resolution_narrative,
                'confidence': rp.confidence
            }
            for rp in synthesis.resolution_patterns
        ]
    }

    # Delete old synthesis results
    ExtractionPrompt.query.filter_by(
        case_id=case_id,
        concept_type='whole_case_synthesis'
    ).delete(synchronize_session=False)

    # Store as extraction prompt
    extraction_prompt = ExtractionPrompt(
        case_id=case_id,
        concept_type='whole_case_synthesis',
        step_number=4,
        section_type='synthesis',
        prompt_text='Whole-case synthesis integrating all passes',
        llm_model='case_synthesis_service',
        extraction_session_id=session_id,
        raw_response=json.dumps(synthesis_data, indent=2),
        results_summary={
            'total_nodes': synthesis.total_nodes,
            'total_links': len(synthesis.causal_normative_links),
            'questions_analyzed': len(synthesis.question_emergence),
            'patterns_extracted': len(synthesis.resolution_patterns)
        },
        is_active=True,
        times_used=1,
        created_at=datetime.utcnow(),
        last_used_at=datetime.utcnow()
    )

    db.session.add(extraction_prompt)
    db.session.commit()

    logger.info(f"Stored synthesis results for case {case_id}")
