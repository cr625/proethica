"""
Step 1: Contextual Framework Pass for Facts and Discussion Sections
Shows both Facts and Discussion sections and provides extraction for Pass 1: Roles, States, and Resources.
Based on Chapter 2 literature: States and Roles work together through context-dependent 
policy activation (Dennis et al. 2016), while Resources provide extensional definitions 
(McLaren 2003).
Discussion analysis uses dual approach: independent and contextual with Facts awareness.
"""

import logging
from contextlib import nullcontext
from flask import render_template, request, jsonify, redirect, url_for, flash, session
from app.models import db, Document
from app.routes.scenario_pipeline.overview import _format_section_for_llm
from app.services.pipeline_status_service import PipelineStatusService

logger = logging.getLogger(__name__)

# Function to exempt specific routes from CSRF after app initialization
def init_step1_csrf_exemption(app):
    """Exempt Step 1a entities pass routes from CSRF protection"""
    if hasattr(app, 'csrf') and app.csrf:
        # Import the route functions that actually get called
        from app.routes.scenario_pipeline.interactive_builder import entities_pass_prompt, entities_pass_execute
        # Exempt the entities pass routes from CSRF protection
        app.csrf.exempt(entities_pass_prompt)
        app.csrf.exempt(entities_pass_execute)

def step1_data(case_id, section_type='facts'):
    """
    Helper function to get Step 1 data without rendering template.
    Returns tuple of (case_doc, facts_section, discussion_section, saved_prompts).

    Args:
        case_id: The case ID
        section_type: Which section's prompts to load ('facts' or 'discussion')
    """
    try:
        # Get the case
        case = Document.query.get_or_404(case_id)

        # Extract sections using the same logic as before
        raw_sections = {}
        if case.doc_metadata:
            # Priority 1: sections_dual (contains formatted HTML with enumerated lists)
            if 'sections_dual' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections_dual']
            # Priority 2: sections (basic sections)
            elif 'sections' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections']
            # Priority 3: document_structure sections
            elif 'document_structure' in case.doc_metadata and 'sections' in case.doc_metadata['document_structure']:
                raw_sections = case.doc_metadata['document_structure']['sections']

        # If no sections found, create basic structure
        if not raw_sections:
            raw_sections = {
                'full_content': case.content or 'No content available'
            }

        # Find the facts section
        facts_section = None
        facts_section_key = None

        # Look for facts/factual section (case insensitive)
        for section_key, section_content in raw_sections.items():
            if 'fact' in section_key.lower():
                facts_section_key = section_key
                facts_section = _format_section_for_llm(section_key, section_content, case_doc=case)
                break

        # If no facts section found, use first available section as fallback
        if not facts_section and raw_sections:
            first_key = list(raw_sections.keys())[0]
            facts_section_key = first_key
            facts_section = _format_section_for_llm(first_key, raw_sections[first_key], case_doc=case)

        # Find the discussion section
        discussion_section = None
        discussion_section_key = None

        # Look for discussion section (case insensitive)
        for section_key, section_content in raw_sections.items():
            if 'discussion' in section_key.lower():
                discussion_section_key = section_key
                discussion_section = _format_section_for_llm(section_key, section_content, case_doc=case)
                break

        # Load any saved prompts for this case - use section_type parameter
        from app.models import ExtractionPrompt

        # For questions and conclusions sections, load both matching and extraction prompts
        if section_type in ['questions', 'conclusions']:
            saved_prompts = {
                'roles': {
                    'matching': ExtractionPrompt.get_active_prompt(case_id, 'roles_matching', section_type=section_type),
                    'extraction': ExtractionPrompt.get_active_prompt(case_id, 'roles_new_extraction', section_type=section_type)
                },
                'states': {
                    'matching': ExtractionPrompt.get_active_prompt(case_id, 'states_matching', section_type=section_type),
                    'extraction': ExtractionPrompt.get_active_prompt(case_id, 'states_new_extraction', section_type=section_type)
                },
                'resources': {
                    'matching': ExtractionPrompt.get_active_prompt(case_id, 'resources_matching', section_type=section_type),
                    'extraction': ExtractionPrompt.get_active_prompt(case_id, 'resources_new_extraction', section_type=section_type)
                }
            }
        else:
            # For facts/discussion, load single prompt per concept type
            saved_prompts = {
                'roles': ExtractionPrompt.get_active_prompt(case_id, 'roles', section_type=section_type),
                'states': ExtractionPrompt.get_active_prompt(case_id, 'states', section_type=section_type),
                'resources': ExtractionPrompt.get_active_prompt(case_id, 'resources', section_type=section_type)
            }

        # Template context
        context = {
            'case': case,
            'facts_section': facts_section,
            'facts_section_key': facts_section_key,
            'discussion_section': discussion_section,
            'discussion_section_key': discussion_section_key,
            'current_step': 1,
            'step_title': 'Contextual Framework Pass - Facts & Discussion',
            'next_step_url': url_for('scenario_pipeline.step2', case_id=case_id),  # Go to Step 2
            'prev_step_url': url_for('scenario_pipeline.overview', case_id=case_id),
            'saved_prompts': saved_prompts  # Add saved prompts to context
        }

        # Return data tuple for use by other functions
        return case, facts_section, discussion_section, saved_prompts

    except Exception as e:
        logger.error(f"Error loading step 1 for case {case_id}: {str(e)}")
        flash(f'Error loading step 1: {str(e)}', 'danger')
        return redirect(url_for('cases.view_case', id=case_id))

def _load_existing_extractions(case_id, concept_types, step_number=1, section_type=None):
    """Load extraction results from temporary_rdf_storage for page-load display.

    When section_type is provided, only returns entities whose section_sources
    include that section. This ensures the facts page shows only facts entities
    and the discussion page shows only discussion entities (including merged ones).

    When section_type is None, loads all entities (used by step 3 and review pages).
    """
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    results = {}
    for concept_type in concept_types:
        entities = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type=concept_type,
        ).all()

        classes = []
        individuals = []
        for e in entities:
            # Section filtering: skip entities not sourced from this section
            if section_type:
                section_sources = (e.rdf_json_ld or {}).get('section_sources', [])
                if section_type not in section_sources:
                    continue

            entry = {
                'label': e.entity_label or '',
                'definition': e.entity_definition or '',
                'confidence': float(e.match_confidence) if e.match_confidence else 0.0,
                'matched_ontology_label': e.matched_ontology_label or '',
                'section_sources': (e.rdf_json_ld or {}).get('section_sources', []),
            }
            if e.storage_type == 'individual':
                entry['type'] = f'{concept_type.rstrip("s")}_individual'
                individuals.append(entry)
            else:
                entry['type'] = f'{concept_type.rstrip("s")}_class'
                classes.append(entry)

        if classes or individuals:
            results[concept_type] = {
                'classes': classes,
                'individuals': individuals,
            }

    return results


def step1(case_id):
    """
    Step 1: Contextual Framework Pass for Facts and Discussion Sections
    Shows both sections with entities pass buttons for extracting roles, states, and resources.
    """
    from app.services.extraction.mock_llm_provider import get_data_source_display

    case, facts_section, discussion_section, saved_prompts = step1_data(case_id)

    # Get pipeline status for navigation
    pipeline_status = PipelineStatusService.get_step_status(case_id)

    # Redirect to review if facts already extracted (unless ?force=1 for re-extraction)
    if (pipeline_status.get('step1', {}).get('facts_complete', False)
            and not request.args.get('force')):
        return redirect(url_for('entity_review.review_case_entities',
                                case_id=case_id, section_type='facts'))

    # Get data source info for UI display (mock mode indicator)
    data_source_info = get_data_source_display()

    # Load existing extraction results for page-load display (facts section only)
    existing_extractions = _load_existing_extractions(
        case_id, ['roles', 'states', 'resources'], step_number=1, section_type='facts'
    )

    # Template context
    context = {
        'case': case,
        'facts_section': facts_section,
        'discussion_section': discussion_section,
        'section_type': 'facts',
        'current_step': 1,
        'step_title': 'Contextual Framework Pass - Facts',
        'next_step_url': url_for('scenario_pipeline.step1b', case_id=case_id),
        'next_step_name': 'Discussion Section',
        'prev_step_url': url_for('scenario_pipeline.overview', case_id=case_id),
        'saved_prompts': saved_prompts,
        'pipeline_status': pipeline_status,
        'data_source': data_source_info['source'],
        'data_source_label': data_source_info['label'],
        'is_mock_mode': data_source_info['is_mock'],
        'data_source_warning': data_source_info.get('warning'),
        'existing_extractions': existing_extractions,
    }

    return render_template('scenarios/step1_streaming.html', **context)

def step1b(case_id):
    """
    Step 1b: Contextual Framework Pass for Discussion Section
    Same streaming template as step1, parameterized for discussion section.

    Requires: Step 1 Facts extraction must be completed first
    """
    from app.services.extraction.mock_llm_provider import get_data_source_display

    # Get pipeline status first to check prerequisites
    pipeline_status = PipelineStatusService.get_step_status(case_id)

    # Enforce prerequisite: Step 1 Facts must be completed
    if not pipeline_status.get('step1', {}).get('facts_complete', False):
        flash('Please complete Step 1 (Facts extraction) before proceeding to Discussion.', 'warning')
        return redirect(url_for('scenario_pipeline.step1', case_id=case_id))

    # Redirect to review if discussion already extracted (unless ?force=1 for re-extraction)
    if (pipeline_status.get('step1', {}).get('discussion_complete', False)
            and not request.args.get('force')):
        return redirect(url_for('entity_review.review_case_entities',
                                case_id=case_id, section_type='discussion'))

    # Load data with section_type='discussion' to get discussion prompts
    case, facts_section, discussion_section, saved_prompts = step1_data(case_id, section_type='discussion')

    # Get data source info for UI display (mock mode indicator)
    data_source_info = get_data_source_display()

    # Load existing extraction results for page-load display (discussion section only)
    existing_extractions = _load_existing_extractions(
        case_id, ['roles', 'states', 'resources'], step_number=1, section_type='discussion'
    )

    # Template context -- same streaming template, parameterized for discussion
    context = {
        'case': case,
        'facts_section': facts_section,
        'discussion_section': discussion_section,
        'section_type': 'discussion',
        'current_step': 1,
        'step_title': 'Contextual Framework Pass - Discussion',
        'next_step_url': url_for('scenario_pipeline.step2', case_id=case_id),
        'next_step_name': 'Normative Requirements',
        'prev_step_url': url_for('scenario_pipeline.step1', case_id=case_id),
        'saved_prompts': saved_prompts,
        'pipeline_status': pipeline_status,
        'data_source': data_source_info['source'],
        'data_source_label': data_source_info['label'],
        'is_mock_mode': data_source_info['is_mock'],
        'data_source_warning': data_source_info.get('warning'),
        'existing_extractions': existing_extractions,
    }

    return render_template('scenarios/step1_streaming.html', **context)

def step1c(case_id):
    """
    Step 1c: Contextual Framework Pass for Questions Section
    Extracts roles, states, and resources from the Questions section

    Requires: Step 1b Discussion extraction must be completed first
    """
    # Get pipeline status first to check prerequisites
    pipeline_status = PipelineStatusService.get_step_status(case_id)

    # Enforce prerequisite: Step 1b Discussion must be completed
    if not pipeline_status.get('step1', {}).get('discussion_complete', False):
        flash('Please complete Step 1b (Discussion extraction) before proceeding to Questions.', 'warning')
        return redirect(url_for('scenario_pipeline.step1b', case_id=case_id))

    # Load data with section_type='questions' to get questions prompts
    case, facts_section, discussion_section, saved_prompts = step1_data(case_id, section_type='questions')

    # Get the questions section
    questions_section = None
    if case.doc_metadata and 'sections_dual' in case.doc_metadata:
        for section_key, section_content in case.doc_metadata['sections_dual'].items():
            if 'question' in section_key.lower():
                questions_section = _format_section_for_llm(section_key, section_content, case_doc=case)
                break

    # Template context
    context = {
        'case': case,
        'questions_section': questions_section,
        'current_step': 1,
        'step_title': 'Contextual Framework Pass - Questions',
        'next_step_url': url_for('scenario_pipeline.step1d', case_id=case_id),
        'prev_step_url': url_for('scenario_pipeline.step1b', case_id=case_id),
        'saved_prompts': saved_prompts  # These are questions-specific prompts
    }

    # Debug: Log what we're passing to template
    logger.info(f"Step1c saved_prompts structure: {type(saved_prompts)}")
    for key in saved_prompts:
        logger.info(f"  {key}: {type(saved_prompts[key])}, value: {saved_prompts[key] if not isinstance(saved_prompts[key], dict) else {k: type(v) for k, v in saved_prompts[key].items()}}")

    # Use step1c.html template
    return render_template('scenarios/step1c.html', **context)

def step1d(case_id):
    """
    Step 1d: Contextual Framework Pass for Conclusions Section
    Extracts roles, states, and resources from the Conclusions section

    Requires: Step 1c Questions extraction must be completed first
    """
    # Get pipeline status first to check prerequisites
    pipeline_status = PipelineStatusService.get_step_status(case_id)

    # Enforce prerequisite: Step 1c Questions must be completed
    if not pipeline_status.get('step1', {}).get('questions_complete', False):
        flash('Please complete Step 1c (Questions extraction) before proceeding to Conclusions.', 'warning')
        return redirect(url_for('scenario_pipeline.step1c', case_id=case_id))

    # Load data with section_type='conclusions' to get conclusions prompts
    case, facts_section, discussion_section, saved_prompts = step1_data(case_id, section_type='conclusions')

    # Get the conclusions section
    conclusions_section = None
    if case.doc_metadata and 'sections_dual' in case.doc_metadata:
        for section_key, section_content in case.doc_metadata['sections_dual'].items():
            if 'conclusion' in section_key.lower():
                conclusions_section = _format_section_for_llm(section_key, section_content, case_doc=case)
                break

    # Get existing Question→Conclusion links if any
    from app.models import TemporaryRDFStorage, ExtractionPrompt
    question_conclusion_links = []

    # Get extraction sessions for conclusions section
    section_prompts = ExtractionPrompt.query.filter_by(
        case_id=case_id,
        section_type='conclusions'
    ).all()
    section_session_ids = {p.extraction_session_id for p in section_prompts if p.extraction_session_id}

    if section_session_ids:
        qc_links = TemporaryRDFStorage.query.filter(
            TemporaryRDFStorage.case_id == case_id,
            TemporaryRDFStorage.extraction_type == 'question_conclusion_link',
            TemporaryRDFStorage.extraction_session_id.in_(section_session_ids)
        ).all()

        for link in qc_links:
            if link.rdf_json_ld:
                question_conclusion_links.append({
                    'question_number': link.rdf_json_ld.get('questionNumber'),
                    'question_text': link.rdf_json_ld.get('questionText', ''),
                    'conclusion_text': link.rdf_json_ld.get('conclusionText', ''),
                    'confidence': link.rdf_json_ld.get('confidence', 0),
                    'reasoning': link.rdf_json_ld.get('reasoning', '')
                })

        logger.info(f"Found {len(question_conclusion_links)} existing Question→Conclusion links")

    # Template context
    context = {
        'case': case,
        'conclusions_section': conclusions_section,
        'current_step': 1,
        'step_title': 'Contextual Framework Pass - Conclusions',
        'next_step_url': url_for('scenario_pipeline.step2', case_id=case_id),
        'prev_step_url': url_for('scenario_pipeline.step1c', case_id=case_id),
        'saved_prompts': saved_prompts,  # These are conclusions-specific prompts
        'question_conclusion_links': question_conclusion_links  # Existing Q→C links
    }

    # Debug: Log what we're passing to template
    logger.info(f"Step1d saved_prompts structure: {type(saved_prompts)}")
    for key in saved_prompts:
        logger.info(f"  {key}: {type(saved_prompts[key])}, value: {saved_prompts[key] if not isinstance(saved_prompts[key], dict) else {k: type(v) for k, v in saved_prompts[key].items()}}")

    # Use step1d.html template
    return render_template('scenarios/step1d.html', **context)


def step1e(case_id):
    """
    Step 1e: NSPE Code of Ethics References
    Extracts and links NSPE Board-selected code provisions to case entities
    """
    # Load data
    case, facts_section, discussion_section, saved_prompts = step1_data(case_id, section_type='facts')

    # Get the references section
    references_section = None
    references_html = None
    if case.doc_metadata and 'sections_dual' in case.doc_metadata:
        for section_key, section_content in case.doc_metadata['sections_dual'].items():
            if 'reference' in section_key.lower():
                references_section = _format_section_for_llm(section_key, section_content, case_doc=case)
                # Also get the HTML for parsing links
                if isinstance(section_content, dict):
                    references_html = section_content.get('html', '')
                break

    # Get existing CodeProvisionReference entities if any
    from app.models import TemporaryRDFStorage, ExtractionPrompt
    code_provisions = []

    # Look for existing code provision references
    existing_provisions = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='code_provision_reference',
        storage_type='individual'
    ).all()

    for provision in existing_provisions:
        if provision.rdf_json_ld:
            code_provisions.append({
                'id': provision.id,
                'code_provision': provision.rdf_json_ld.get('codeProvision', ''),
                'provision_text': provision.rdf_json_ld.get('provisionText', ''),
                'subject_references': provision.rdf_json_ld.get('subjectReferences', []),
                'applies_to': provision.rdf_json_ld.get('appliesTo', []),
                'relevant_excerpts': provision.rdf_json_ld.get('relevantExcerpts', [])
            })

    logger.info(f"Found {len(code_provisions)} existing code provision references")

    # Template context
    context = {
        'case': case,
        'references_section': references_section,
        'references_html': references_html,
        'code_provisions': code_provisions,
        'current_step': 1,
        'step_title': 'NSPE Code of Ethics References',
        'next_step_url': url_for('scenario_pipeline.step2', case_id=case_id),
        'prev_step_url': url_for('scenario_pipeline.step1d', case_id=case_id)
    }

    return render_template('scenarios/step1e.html', **context)


def entities_pass_prompt(case_id):
    """
    API endpoint to generate and return the LLM prompt for entities pass before execution.
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        section_text = data.get('section_text')
        if not section_text:
            return jsonify({'error': 'section_text is required'}), 400
        
        logger.info(f"Generating entities pass prompt for case {case_id}")
        
        # Import the extraction services to get the actual prompts that will be used
        from app.services.extraction.roles import RolesExtractor
        from app.services.extraction.resources import ResourcesExtractor
        from app.services.extraction.enhanced_prompts_states_capabilities import create_enhanced_states_prompt
        
        # Create extractors to generate the actual prompts that will be used
        roles_extractor = RolesExtractor()
        resources_extractor = ResourcesExtractor()
        
        # Get the actual prompts that will be sent to the LLM (with MCP context if enabled)
        roles_prompt = roles_extractor._get_prompt_for_preview(section_text)
        resources_prompt = resources_extractor._get_prompt_for_preview(section_text)
        
        # Get existing states from MCP (always enabled)
        existing_states = []
        try:
            from app.services.external_mcp_client import get_external_mcp_client
            external_client = get_external_mcp_client()
            existing_states = external_client.get_all_state_entities()
            logger.info(f"Retrieved {len(existing_states)} existing states from MCP for prompt preview")
        except Exception as e:
            logger.warning(f"Could not fetch existing states for prompt preview: {e}")
        
        # Get the enhanced states prompt with ontology context and existing states
        states_prompt = create_enhanced_states_prompt(section_text, include_ontology_context=True, existing_states=existing_states)
        
        return jsonify({
            'success': True,
            'roles_prompt': roles_prompt,
            'states_prompt': states_prompt,
            'resources_prompt': resources_prompt,
            'combined_prompt': f"ROLES EXTRACTION:\n{roles_prompt}\n\n---\n\nSTATES EXTRACTION:\n{states_prompt}\n\n---\n\nRESOURCES EXTRACTION:\n{resources_prompt}",
            'section_length': len(section_text)
        })
        
    except Exception as e:
        logger.error(f"Error generating entities pass prompt for case {case_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def entities_pass_execute(case_id):
    """
    API endpoint to execute the entities pass on the facts section.
    Extracts roles, states, and resources using UnifiedDualExtractor with PROV-O tracking.
    Results are stored to ExtractionPrompt + TemporaryRDFStorage via store_extraction_result().
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        section_text = data.get('section_text')
        if not section_text:
            return jsonify({'error': 'section_text is required'}), 400

        logger.info(f"Starting entities pass execution for case {case_id} with provenance tracking")

        from app.services.extraction.unified_dual_extractor import UnifiedDualExtractor
        from app.services.extraction.extraction_graph import store_extraction_result
        from app.services.provenance_service import get_provenance_service
        try:
            from app.services.provenance_versioning_service import get_versioned_provenance_service
            USE_VERSIONED_PROVENANCE = True
        except ImportError:
            USE_VERSIONED_PROVENANCE = False
        from app.models import db
        import uuid

        # Initialize provenance service with versioning if available
        if USE_VERSIONED_PROVENANCE:
            prov = get_versioned_provenance_service(session=db.session)
            logger.info("Using versioned provenance service for tracking")
        else:
            prov = get_provenance_service(session=db.session)
            logger.info("Using standard provenance service")

        # Create a session ID for this extraction workflow
        session_id = str(uuid.uuid4())
        section_type = 'facts'

        # Extraction results collected across all concepts
        all_classes = {}  # concept_type -> list of Pydantic class objects
        all_individuals = {}  # concept_type -> list of Pydantic individual objects
        model_used = None

        # Dependency order for Pass 1: roles -> states -> resources
        concept_order = ['roles', 'states', 'resources']

        # Track versioned workflow if available
        version_context = nullcontext()
        if USE_VERSIONED_PROVENANCE:
            version_context = prov.track_versioned_workflow(
                workflow_name='step1_extraction',
                description='Contextual Framework extraction (Pass 1)',
                version_tag='unified_dual',
                auto_version=True
            )

        with version_context:
            with prov.track_activity(
                activity_type='extraction',
                activity_name='entities_pass_step1',
                case_id=case_id,
                session_id=session_id,
                agent_type='extraction_service',
                agent_name='proethica_entities_pass',
                execution_plan={
                    'section_length': len(section_text),
                    'extraction_types': concept_order,
                    'pass_name': 'Contextual Framework (Pass 1)',
                    'strategy': 'unified_dual_extractor',
                    'version': 'unified_dual' if USE_VERSIONED_PROVENANCE else 'standard'
                }
            ) as main_activity:

                prev_activity = main_activity

                for concept_type in concept_order:
                    with prov.track_activity(
                        activity_type='llm_query',
                        activity_name=f'{concept_type}_extraction',
                        case_id=case_id,
                        session_id=session_id,
                        agent_type='extraction_service',
                        agent_name='UnifiedDualExtractor'
                    ) as concept_activity:
                        logger.info(f"Extracting {concept_type} with UnifiedDualExtractor...")

                        extractor = UnifiedDualExtractor(concept_type)
                        classes, individuals = extractor.extract(
                            case_text=section_text,
                            case_id=case_id,
                            section_type=section_type
                        )

                        if model_used is None:
                            model_used = extractor.model_name

                        all_classes[concept_type] = classes
                        all_individuals[concept_type] = individuals

                        # Store prompt + entities to database
                        store_extraction_result(
                            case_id=case_id,
                            concept_type=concept_type,
                            step_number=1,
                            section_type=section_type,
                            session_id=session_id,
                            extractor=extractor,
                            classes=classes,
                            individuals=individuals,
                            pass_number=1,
                            extraction_pass='contextual_framework',
                        )

                        # Record provenance
                        prov.record_extraction_results(
                            results=[{
                                'label': c.label,
                                'definition': c.definition,
                                'confidence': c.confidence,
                            } for c in classes],
                            activity=concept_activity,
                            entity_type=f'extracted_{concept_type}',
                            metadata={
                                'classes_count': len(classes),
                                'individuals_count': len(individuals),
                            }
                        )

                        prov.link_activities(concept_activity, prev_activity, 'sequence')
                        prev_activity = concept_activity

        # Commit provenance records
        db.session.commit()

        # Serialize Pydantic models to JSON response
        def _serialize_class(cls):
            d = cls.model_dump(mode='json')
            d['type'] = 'class'
            d['description'] = d.get('definition', '')
            return d

        def _serialize_individual(ind):
            d = ind.model_dump(mode='json')
            d['type'] = 'individual'
            return d

        roles_data = [_serialize_class(c) for c in all_classes.get('roles', [])]
        individuals_data = [_serialize_individual(i) for i in all_individuals.get('roles', [])]
        states_data = [_serialize_class(c) for c in all_classes.get('states', [])]
        states_individuals = [_serialize_individual(i) for i in all_individuals.get('states', [])]
        resources_data = [_serialize_class(c) for c in all_classes.get('resources', [])]
        resources_individuals = [_serialize_individual(i) for i in all_individuals.get('resources', [])]

        logger.info(
            f"Entities pass completed for case {case_id}: "
            f"{len(roles_data)} role classes, {len(individuals_data)} role individuals, "
            f"{len(states_data)} state classes, {len(resources_data)} resource classes"
        )

        return jsonify({
            'success': True,
            'roles': roles_data,
            'individuals': individuals_data,
            'states': states_data + states_individuals,
            'resources': resources_data + resources_individuals,
            'summary': {
                'roles_count': len(roles_data),
                'individuals_count': len(individuals_data),
                'states_count': len(states_data) + len(states_individuals),
                'resources_count': len(resources_data) + len(resources_individuals),
                'total_entities': (len(roles_data) + len(individuals_data)
                                   + len(states_data) + len(states_individuals)
                                   + len(resources_data) + len(resources_individuals)),
            },
            'provenance': {
                'session_id': session_id,
                'viewer_url': f'/tools/provenance?case_id={case_id}&session_id={session_id}'
            }
        })

    except Exception as e:
        logger.error(f"Error in entities pass execution for case {case_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'fallback_available': False
        }), 500


def entities_pass_prompt_discussion(case_id):
    """
    API endpoint to generate entities pass prompt for Discussion section.
    Same structure as entities_pass_prompt but for discussion section_type.
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        section_text = data.get('section_text')
        if not section_text:
            return jsonify({'error': 'section_text is required'}), 400

        logger.info(f"Generating entities pass prompt for Discussion section, case {case_id}")

        # Import the extraction services
        from app.services.extraction.roles import RolesExtractor
        from app.services.extraction.resources import ResourcesExtractor
        from app.services.extraction.enhanced_prompts_states_capabilities import create_enhanced_states_prompt

        # Create extractors
        roles_extractor = RolesExtractor()
        resources_extractor = ResourcesExtractor()

        # Get prompts (same extractors, different section context)
        roles_prompt = roles_extractor._get_prompt_for_preview(section_text)
        resources_prompt = resources_extractor._get_prompt_for_preview(section_text)

        # Get existing states from MCP
        existing_states = []
        try:
            from app.services.external_mcp_client import get_external_mcp_client
            external_client = get_external_mcp_client()
            existing_states = external_client.get_all_state_entities()
            logger.info(f"Retrieved {len(existing_states)} existing states from MCP for Discussion prompt preview")
        except Exception as e:
            logger.warning(f"Could not fetch existing states for prompt preview: {e}")

        # Get the enhanced states prompt
        states_prompt = create_enhanced_states_prompt(section_text, include_ontology_context=True, existing_states=existing_states)

        return jsonify({
            'success': True,
            'roles_prompt': roles_prompt,
            'states_prompt': states_prompt,
            'resources_prompt': resources_prompt,
            'combined_prompt': f"ROLES EXTRACTION (Discussion):\n{roles_prompt}\n\n---\n\nSTATES EXTRACTION (Discussion):\n{states_prompt}\n\n---\n\nRESOURCES EXTRACTION (Discussion):\n{resources_prompt}",
            'section_length': len(section_text),
            'section_type': 'discussion'
        })

    except Exception as e:
        logger.error(f"Error generating Discussion entities pass prompt for case {case_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def entities_pass_execute_discussion(case_id):
    """
    API endpoint to execute the entities pass on the Discussion section.
    Same structure as entities_pass_execute but stores with section_type='discussion'.
    Uses UnifiedDualExtractor with storage via store_extraction_result().
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        section_text = data.get('section_text')
        if not section_text:
            return jsonify({'error': 'section_text is required'}), 400

        logger.info(f"Starting entities pass execution for Discussion section, case {case_id}")

        from app.services.extraction.unified_dual_extractor import UnifiedDualExtractor
        from app.services.extraction.extraction_graph import store_extraction_result
        from app.services.provenance_service import get_provenance_service
        try:
            from app.services.provenance_versioning_service import get_versioned_provenance_service
            USE_VERSIONED_PROVENANCE = True
        except ImportError:
            USE_VERSIONED_PROVENANCE = False
        from app.models import db
        import uuid

        # Initialize provenance service
        if USE_VERSIONED_PROVENANCE:
            prov = get_versioned_provenance_service(session=db.session)
            logger.info("Using versioned provenance service for Discussion section tracking")
        else:
            prov = get_provenance_service(session=db.session)

        # Create a session ID
        session_id = str(uuid.uuid4())
        section_type = 'discussion'

        # Extraction results collected across all concepts
        all_classes = {}
        all_individuals = {}
        model_used = None

        concept_order = ['roles', 'states', 'resources']

        # Track versioned workflow
        version_context = nullcontext()
        if USE_VERSIONED_PROVENANCE:
            version_context = prov.track_versioned_workflow(
                workflow_name='step1b_extraction_discussion',
                description='Discussion section entities pass extraction',
                version_tag='unified_dual_discussion',
                auto_version=True
            )

        with version_context:
            with prov.track_activity(
                activity_type='extraction',
                activity_name='entities_pass_step1_discussion',
                case_id=case_id,
                session_id=session_id,
                agent_type='extraction_service',
                agent_name='proethica_entities_pass_discussion',
                execution_plan={
                    'section_length': len(section_text),
                    'section_type': section_type,
                    'extraction_types': concept_order,
                    'pass_name': 'Contextual Framework (Pass 1 - Discussion)',
                    'strategy': 'unified_dual_extractor',
                }
            ) as main_activity:

                prev_activity = main_activity

                for concept_type in concept_order:
                    with prov.track_activity(
                        activity_type='llm_query',
                        activity_name=f'{concept_type}_extraction_discussion',
                        case_id=case_id,
                        session_id=session_id,
                        agent_type='extraction_service',
                        agent_name='UnifiedDualExtractor'
                    ) as concept_activity:
                        logger.info(f"Extracting {concept_type} from Discussion section...")

                        extractor = UnifiedDualExtractor(concept_type)
                        classes, individuals = extractor.extract(
                            case_text=section_text,
                            case_id=case_id,
                            section_type=section_type
                        )

                        if model_used is None:
                            model_used = extractor.model_name

                        all_classes[concept_type] = classes
                        all_individuals[concept_type] = individuals

                        # Store prompt + entities to database
                        store_extraction_result(
                            case_id=case_id,
                            concept_type=concept_type,
                            step_number=1,
                            section_type=section_type,
                            session_id=session_id,
                            extractor=extractor,
                            classes=classes,
                            individuals=individuals,
                            pass_number=1,
                            extraction_pass='contextual_framework',
                        )

                        # Record provenance
                        prov.record_extraction_results(
                            results=[{
                                'label': c.label,
                                'definition': c.definition,
                                'confidence': c.confidence,
                            } for c in classes],
                            activity=concept_activity,
                            entity_type=f'extracted_{concept_type}',
                            metadata={
                                'classes_count': len(classes),
                                'individuals_count': len(individuals),
                                'section_type': section_type,
                            }
                        )

                        prov.link_activities(concept_activity, prev_activity, 'sequence')
                        prev_activity = concept_activity

        # Commit provenance
        db.session.commit()

        # Serialize Pydantic models to JSON response
        def _serialize_class(cls):
            d = cls.model_dump(mode='json')
            d['type'] = 'class'
            d['description'] = d.get('definition', '')
            d['section_type'] = section_type
            return d

        def _serialize_individual(ind):
            d = ind.model_dump(mode='json')
            d['type'] = 'individual'
            d['section_type'] = section_type
            return d

        roles_data = [_serialize_class(c) for c in all_classes.get('roles', [])]
        individuals_data = [_serialize_individual(i) for i in all_individuals.get('roles', [])]
        states_data = [_serialize_class(c) for c in all_classes.get('states', [])]
        states_individuals = [_serialize_individual(i) for i in all_individuals.get('states', [])]
        resources_data = [_serialize_class(c) for c in all_classes.get('resources', [])]
        resources_individuals = [_serialize_individual(i) for i in all_individuals.get('resources', [])]

        logger.info(
            f"Discussion entities pass completed for case {case_id}: "
            f"{len(roles_data)} role classes, {len(individuals_data)} role individuals, "
            f"{len(states_data)} state classes, {len(resources_data)} resource classes"
        )

        return jsonify({
            'success': True,
            'section_type': section_type,
            'roles': roles_data,
            'individuals': individuals_data,
            'states': states_data + states_individuals,
            'resources': resources_data + resources_individuals,
            'summary': {
                'roles_count': len(roles_data),
                'individuals_count': len(individuals_data),
                'states_count': len(states_data) + len(states_individuals),
                'resources_count': len(resources_data) + len(resources_individuals),
                'total_entities': (len(roles_data) + len(individuals_data)
                                   + len(states_data) + len(states_individuals)
                                   + len(resources_data) + len(resources_individuals)),
            },
            'provenance': {
                'session_id': session_id,
                'viewer_url': f'/tools/provenance?case_id={case_id}&session_id={session_id}'
            }
        })

    except Exception as e:
        logger.error(f"Error in Discussion entities pass execution for case {case_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def extract_questions(case_id):
    """
    Extract ethical questions from Questions section using McLaren framework.
    Implements principle instantiation and conflict resolution techniques.
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        question_text = data.get('question_text')
        if not question_text:
            return jsonify({'error': 'question_text is required'}), 400

        logger.info(f"Extracting questions for case {case_id} using McLaren framework")

        # Get previously extracted entities for context
        from app.models import TemporaryRDFStorage, ExtractionPrompt

        # Get Facts entities
        facts_prompts = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            section_type='facts'
        ).all()
        facts_session_ids = {p.extraction_session_id for p in facts_prompts if p.extraction_session_id}

        facts_entities = {}
        if facts_session_ids:
            facts_rdf = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.extraction_session_id.in_(facts_session_ids)
            ).all()
            for entity in facts_rdf:
                et = entity.extraction_type
                if et not in facts_entities:
                    facts_entities[et] = []
                facts_entities[et].append(entity.to_dict())

        # Get Discussion entities
        discussion_prompts = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            section_type='discussion'
        ).all()
        discussion_session_ids = {p.extraction_session_id for p in discussion_prompts if p.extraction_session_id}

        discussion_entities = {}
        if discussion_session_ids:
            discussion_rdf = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.extraction_session_id.in_(discussion_session_ids)
            ).all()
            for entity in discussion_rdf:
                et = entity.extraction_type
                if et not in discussion_entities:
                    discussion_entities[et] = []
                discussion_entities[et].append(entity.to_dict())

        # Initialize question extraction service
        from app.services.question_extraction_service import QuestionExtractionService
        from app.utils.llm_utils import get_llm_client

        llm_client = get_llm_client()
        question_service = QuestionExtractionService(llm_client=llm_client)

        # Extract questions with McLaren framework
        questions = question_service.extract_questions(
            question_section_text=question_text,
            case_id=case_id,
            facts_entities=facts_entities,
            discussion_entities=discussion_entities
        )

        # Create session ID for this extraction
        import uuid
        session_id = str(uuid.uuid4())

        # Store in temporary RDF storage
        storage_entries = question_service.to_rdf_storage(
            questions=questions,
            case_id=case_id,
            extraction_session_id=session_id
        )

        from app.models import db
        for entry in storage_entries:
            rdf_entity = TemporaryRDFStorage(
                case_id=entry['case_id'],
                extraction_session_id=entry['extraction_session_id'],
                extraction_type=entry['extraction_type'],
                storage_type=entry['storage_type'],
                ontology_target=entry['ontology_target'],
                entity_label=entry['entity_label'],
                entity_type=entry['entity_type'],
                entity_definition=entry['entity_definition'],
                rdf_json_ld=entry['rdf_json_ld'],
                is_selected=True  # Auto-select for review
            )
            db.session.add(rdf_entity)

        db.session.commit()

        # Format response
        questions_data = []
        for q in questions:
            questions_data.append({
                'question_number': q.question_number,
                'question_text': q.question_text,
                'invoked_principles': [
                    {
                        'label': p.principle_label,
                        'code': p.principle_code,
                        'facts': p.instantiated_facts,
                        'rationale': p.rationale
                    }
                    for p in q.invoked_principles
                ],
                'principle_conflicts': [
                    {
                        'principle1': c.principle1,
                        'principle2': c.principle2,
                        'description': c.conflict_description,
                        'critical_facts': c.critical_facts
                    }
                    for c in q.principle_conflicts
                ],
                'critical_facts': q.critical_facts,
                'referenced_entities': q.referenced_entities,
                'precedent_pattern': q.precedent_pattern,
                'professional_context': q.professional_context,
                'confidence': q.confidence
            })

        logger.info(f"Successfully extracted {len(questions)} questions for case {case_id}")

        return jsonify({
            'success': True,
            'questions': questions_data,
            'summary': {
                'total_questions': len(questions),
                'with_conflicts': sum(1 for q in questions if q.principle_conflicts),
                'avg_principles_per_question': sum(len(q.invoked_principles) for q in questions) / len(questions) if questions else 0
            },
            'session_id': session_id
        })

    except Exception as e:
        logger.error(f"Error extracting questions for case {case_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def tag_entities_in_questions(case_id):
    """
    Tag/match entities from Facts/Discussion that are referenced in Questions section.
    This creates cross-section links instead of extracting new entities.
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        questions_text = data.get('questions_text')
        entity_type = data.get('entity_type')  # 'roles', 'states', or 'resources'

        if not questions_text or not entity_type:
            return jsonify({'error': 'questions_text and entity_type required'}), 400

        logger.info(f"Tagging {entity_type} entities in Questions section for case {case_id}")

        # Initialize entity matching service
        from app.services.entity_matching_service import EntityMatchingService
        from app.utils.llm_utils import get_llm_client

        llm_client = get_llm_client()
        matching_service = EntityMatchingService(llm_client=llm_client)

        # Match entities from Facts/Discussion AND extract new ones
        matches, new_entities = matching_service.match_entities_in_text(
            section_text=questions_text,
            entity_type=entity_type,
            case_id=case_id,
            previous_sections=['facts', 'discussion'],
            extract_new=True  # Also extract entities not found in previous sections
        )

        # Create session ID
        import uuid
        session_id = str(uuid.uuid4())

        # Save the prompts and responses to extraction_prompts table
        from app.models import ExtractionPrompt, TemporaryRDFStorage, db
        from datetime import datetime

        # Save matching prompt (first LLM call)
        matching_prompt = ExtractionPrompt(
            case_id=case_id,
            concept_type=f'{entity_type}_matching',  # Distinguish matching from extraction
            step_number=1,  # Step 1c - Questions section
            section_type='questions',
            prompt_text=matching_service.last_matching_prompt or '',
            llm_model='claude-opus-4-1-20250805',
            extraction_session_id=session_id,
            raw_response=matching_service.last_matching_response or '',
            results_summary={
                'matches': len(matches),
                'from_facts': sum(1 for m in matches if m.source_section == 'facts'),
                'from_discussion': sum(1 for m in matches if m.source_section == 'discussion')
            },
            is_active=True,
            times_used=1,
            created_at=datetime.utcnow(),
            last_used_at=datetime.utcnow()
        )
        db.session.add(matching_prompt)

        # Save new entity extraction prompt (second LLM call) if extraction was attempted
        if matching_service.last_extraction_prompt:
            extraction_prompt = ExtractionPrompt(
                case_id=case_id,
                concept_type=f'{entity_type}_new_extraction',  # Distinguish extraction from matching
                step_number=1,  # Step 1c - Questions section
                section_type='questions',
                prompt_text=matching_service.last_extraction_prompt,
                llm_model='claude-opus-4-1-20250805',
                extraction_session_id=session_id,
                raw_response=matching_service.last_extraction_response or '',
                results_summary={
                    'new_entities': len(new_entities)
                },
                is_active=True,
                times_used=1,
                created_at=datetime.utcnow(),
                last_used_at=datetime.utcnow()
            )
            db.session.add(extraction_prompt)

        # Store matches as relationships
        storage_entries = matching_service.store_entity_matches(
            matches=matches,
            case_id=case_id,
            target_section='questions',
            extraction_session_id=session_id
        )

        # Save matched entities to database
        for entry in storage_entries:
            rdf_entity = TemporaryRDFStorage(
                case_id=entry['case_id'],
                extraction_session_id=entry['extraction_session_id'],
                extraction_type=entry['extraction_type'],
                storage_type=entry['storage_type'],
                ontology_target=entry['ontology_target'],
                entity_label=entry['entity_label'],
                entity_type=entry['entity_type'],
                entity_definition=entry['entity_definition'],
                rdf_json_ld=entry['rdf_json_ld'],
                is_selected=True  # Auto-select for review
            )
            db.session.add(rdf_entity)

        # Also store NEW entities extracted from Questions
        for new_entity in new_entities:
            rdf_entity = TemporaryRDFStorage(
                case_id=case_id,
                extraction_session_id=session_id,
                extraction_type=f'{entity_type}_new_from_questions',
                storage_type=new_entity['storage_type'],
                ontology_target=f'proethica-case-{case_id}',
                entity_label=new_entity['label'],
                entity_type=new_entity['entity_type'],
                entity_definition=new_entity['definition'],
                rdf_json_ld={
                    '@type': f'proeth-case:{new_entity["label"].replace(" ", "")}',
                    'label': new_entity['label'],
                    'definition': new_entity['definition'],
                    'extractedFrom': 'questions',
                    'isNewEntity': True,
                    'reasoning': new_entity['reasoning'],
                    'confidence': new_entity['confidence']  # Store confidence in JSON
                },
                is_selected=True  # Auto-select for review
            )
            db.session.add(rdf_entity)

        db.session.commit()

        # Format response
        matches_data = [{
            'entity_label': m.entity_label,
            'entity_type': m.entity_type,
            'source_section': m.source_section,
            'mention_text': m.mention_text,
            'confidence': m.confidence,
            'reasoning': m.reasoning,
            'is_published': m.is_published
        } for m in matches]

        logger.info(f"Tagged {len(matches)} {entity_type} entities and found {len(new_entities)} NEW entities in Questions section")

        return jsonify({
            'success': True,
            'entity_type': entity_type,
            'matches': matches_data,
            'new_entities': new_entities,  # Include newly extracted entities
            'summary': {
                'total_matches': len(matches),
                'total_new': len(new_entities),
                'from_facts': sum(1 for m in matches if m.source_section == 'facts'),
                'from_discussion': sum(1 for m in matches if m.source_section == 'discussion'),
                'avg_confidence': sum(m.confidence for m in matches) / len(matches) if matches else 0
            },
            'session_id': session_id,
            'matching_prompt': matching_service.last_matching_prompt,  # Matching prompt for UI display
            'matching_response': matching_service.last_matching_response,  # Matching response for UI display
            'extraction_prompt': matching_service.last_extraction_prompt,  # New entity extraction prompt
            'extraction_response': matching_service.last_extraction_response  # New entity extraction response
        })

    except Exception as e:
        logger.error(f"Error tagging entities in Questions for case {case_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def tag_entities_in_conclusions(case_id):
    """
    Tag/match entities from Facts/Discussion/Questions that are referenced in Conclusions section.
    This creates cross-section links instead of extracting new entities.
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        conclusions_text = data.get('conclusions_text')
        entity_type = data.get('entity_type')  # 'roles', 'states', or 'resources'

        if not conclusions_text or not entity_type:
            return jsonify({'error': 'conclusions_text and entity_type required'}), 400

        logger.info(f"Tagging {entity_type} entities in Conclusions section for case {case_id}")

        # Initialize entity matching service
        from app.services.entity_matching_service import EntityMatchingService
        from app.utils.llm_utils import get_llm_client

        llm_client = get_llm_client()
        matching_service = EntityMatchingService(llm_client=llm_client)

        # Match entities from Facts/Discussion/Questions AND extract new ones
        matches, new_entities = matching_service.match_entities_in_text(
            section_text=conclusions_text,
            entity_type=entity_type,
            case_id=case_id,
            previous_sections=['facts', 'discussion', 'questions'],  # Include questions
            extract_new=True  # Also extract entities not found in previous sections
        )

        # Create session ID
        import uuid
        session_id = str(uuid.uuid4())

        # Save the prompts and responses to extraction_prompts table
        from app.models import ExtractionPrompt, TemporaryRDFStorage, db
        from datetime import datetime

        # Save matching prompt (first LLM call)
        matching_prompt = ExtractionPrompt(
            case_id=case_id,
            concept_type=f'{entity_type}_matching',  # Distinguish matching from extraction
            step_number=1,  # Step 1d - Conclusions section
            section_type='conclusions',
            prompt_text=matching_service.last_matching_prompt or '',
            llm_model='claude-opus-4-1-20250805',
            extraction_session_id=session_id,
            raw_response=matching_service.last_matching_response or '',
            results_summary={
                'matches': len(matches),
                'from_facts': sum(1 for m in matches if m.source_section == 'facts'),
                'from_discussion': sum(1 for m in matches if m.source_section == 'discussion'),
                'from_questions': sum(1 for m in matches if m.source_section == 'questions')
            },
            is_active=True,
            times_used=1,
            created_at=datetime.utcnow(),
            last_used_at=datetime.utcnow()
        )
        db.session.add(matching_prompt)

        # Save new entity extraction prompt (second LLM call) if extraction was attempted
        if matching_service.last_extraction_prompt:
            extraction_prompt = ExtractionPrompt(
                case_id=case_id,
                concept_type=f'{entity_type}_new_extraction',  # Distinguish extraction from matching
                step_number=1,  # Step 1d - Conclusions section
                section_type='conclusions',
                prompt_text=matching_service.last_extraction_prompt,
                llm_model='claude-opus-4-1-20250805',
                extraction_session_id=session_id,
                raw_response=matching_service.last_extraction_response or '',
                results_summary={
                    'new_entities': len(new_entities)
                },
                is_active=True,
                times_used=1,
                created_at=datetime.utcnow(),
                last_used_at=datetime.utcnow()
            )
            db.session.add(extraction_prompt)

        # Store matches as relationships
        storage_entries = matching_service.store_entity_matches(
            matches=matches,
            case_id=case_id,
            target_section='conclusions',
            extraction_session_id=session_id
        )

        # Save matched entities to database
        for entry in storage_entries:
            rdf_entity = TemporaryRDFStorage(
                case_id=entry['case_id'],
                extraction_session_id=entry['extraction_session_id'],
                extraction_type=entry['extraction_type'],  # 'conclusions_entity_refs'
                storage_type=entry['storage_type'],  # 'relationship'
                entity_type=entry['entity_type'],
                entity_label=entry['entity_label'],
                entity_definition=entry.get('entity_definition'),
                rdf_json_ld=entry.get('rdf_json_ld'),
                is_selected=True
            )
            db.session.add(rdf_entity)

        # Store new entities extracted from Conclusions
        for new_entity in new_entities:
            rdf_entity = TemporaryRDFStorage(
                case_id=case_id,
                extraction_session_id=session_id,
                extraction_type=f'{entity_type}_new_from_conclusions',
                storage_type=new_entity['storage_type'],
                ontology_target=f'proethica-case-{case_id}',
                entity_label=new_entity['label'],
                entity_type=new_entity['entity_type'],
                entity_definition=new_entity['definition'],
                rdf_json_ld={
                    '@type': f'proeth-case:{new_entity["label"].replace(" ", "")}',
                    'label': new_entity['label'],
                    'definition': new_entity['definition'],
                    'extractedFrom': 'conclusions',
                    'isNewEntity': True,
                    'reasoning': new_entity['reasoning'],
                    'confidence': new_entity['confidence']
                },
                is_selected=True
            )
            db.session.add(rdf_entity)

        db.session.commit()

        logger.info(f"Successfully tagged {len(matches)} matches and extracted {len(new_entities)} new entities for {entity_type}")

        return jsonify({
            'success': True,
            'matches': [
                {
                    'label': m.entity_label,
                    'source_section': m.source_section,
                    'confidence': m.confidence,
                    'mention': m.mention_text[:100] if m.mention_text else ''
                }
                for m in matches
            ],
            'new_entities': [
                {
                    'label': e.get('label', 'Unknown'),
                    'storage_type': e.get('storage_type', 'individual')
                }
                for e in new_entities
            ],
            'stats': {
                'total_matches': len(matches),
                'total_new_entities': len(new_entities),
                'from_facts': sum(1 for m in matches if m.source_section == 'facts'),
                'from_discussion': sum(1 for m in matches if m.source_section == 'discussion'),
                'from_questions': sum(1 for m in matches if m.source_section == 'questions'),
                'avg_confidence': sum(m.confidence for m in matches) / len(matches) if matches else 0
            },
            'session_id': session_id,
            'matching_prompt': matching_service.last_matching_prompt,  # Matching prompt for UI display
            'matching_response': matching_service.last_matching_response,  # Matching response for UI display
            'extraction_prompt': matching_service.last_extraction_prompt,  # New entity extraction prompt
            'extraction_response': matching_service.last_extraction_response  # New entity extraction response
        })

    except Exception as e:
        logger.error(f"Error tagging entities in Conclusions for case {case_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def link_questions_to_conclusions(case_id):
    """
    Create Question→Conclusion relationship mappings.
    This should be called AFTER entity extraction to link questions to their answers.
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405

        logger.info(f"Linking questions to conclusions for case {case_id}")

        # Get the case document
        from app.models import Document
        case = Document.query.get_or_404(case_id)

        # Extract questions and conclusions sections
        questions_text = None
        conclusions_text = None

        if case.doc_metadata and 'sections_dual' in case.doc_metadata:
            sections = case.doc_metadata['sections_dual']

            # Get questions section (check both 'question' and 'questions')
            for key in ['question', 'questions']:
                if key in sections:
                    question_data = sections[key]
                    if isinstance(question_data, dict):
                        questions_text = question_data.get('text', '')
                    else:
                        questions_text = str(question_data)
                    break

            # Get conclusions section (check both 'conclusion' and 'conclusions')
            for key in ['conclusion', 'conclusions']:
                if key in sections:
                    conclusion_data = sections[key]
                    if isinstance(conclusion_data, dict):
                        conclusions_text = conclusion_data.get('text', '')
                    else:
                        conclusions_text = str(conclusion_data)
                    break

        if not questions_text or not conclusions_text:
            return jsonify({
                'success': False,
                'error': 'Questions or Conclusions section not found in case metadata'
            }), 400

        logger.info(f"Questions text length: {len(questions_text)}")
        logger.info(f"Conclusions text length: {len(conclusions_text)}")

        # Initialize linking service
        from app.services.question_conclusion_linking_service import QuestionConclusionLinkingService
        from app.utils.llm_utils import get_llm_client

        llm_client = get_llm_client()
        linking_service = QuestionConclusionLinkingService(llm_client=llm_client)

        # Create question→conclusion mappings
        pairs = linking_service.link_questions_to_conclusions(
            questions_text=questions_text,
            conclusions_text=conclusions_text,
            use_llm_verification=True
        )

        logger.info(f"Created {len(pairs)} question→conclusion pairs")

        # IMPORTANT: Delete old Q→C links to avoid stacking/duplication
        from app.models import ExtractionPrompt, TemporaryRDFStorage, db
        from datetime import datetime

        # Find existing Q→C link session IDs for this case
        old_linking_prompts = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='question_conclusion_linking',
            section_type='conclusions'
        ).all()

        old_session_ids = [p.extraction_session_id for p in old_linking_prompts if p.extraction_session_id]

        if old_session_ids:
            # Delete old Q→C links
            old_links_count = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.extraction_type == 'question_conclusion_link',
                TemporaryRDFStorage.extraction_session_id.in_(old_session_ids)
            ).delete(synchronize_session=False)

            # Delete old prompts
            ExtractionPrompt.query.filter(
                ExtractionPrompt.case_id == case_id,
                ExtractionPrompt.concept_type == 'question_conclusion_linking',
                ExtractionPrompt.section_type == 'conclusions'
            ).delete(synchronize_session=False)

            logger.info(f"Deleted {old_links_count} old Q→C links and {len(old_linking_prompts)} old prompts")

        # Create session ID for this linking operation
        import uuid
        session_id = str(uuid.uuid4())

        linking_prompt_record = ExtractionPrompt(
            case_id=case_id,
            concept_type='question_conclusion_linking',
            step_number=1,  # Step 1d - Conclusions section
            section_type='conclusions',
            prompt_text=linking_service.last_linking_prompt or '',
            llm_model='claude-opus-4-20250514',
            extraction_session_id=session_id,
            raw_response=linking_service.last_linking_response or '',
            results_summary={
                'total_pairs': len(pairs),
                'avg_confidence': sum(p.confidence for p in pairs) / len(pairs) if pairs else 0
            },
            is_active=True,
            times_used=1,
            created_at=datetime.utcnow(),
            last_used_at=datetime.utcnow()
        )
        db.session.add(linking_prompt_record)

        # Store the question→conclusion links
        storage_entries = linking_service.store_question_conclusion_links(
            pairs=pairs,
            case_id=case_id,
            extraction_session_id=session_id
        )

        # Save to database
        for entry in storage_entries:
            rdf_entity = TemporaryRDFStorage(
                case_id=entry['case_id'],
                extraction_session_id=entry['extraction_session_id'],
                extraction_type=entry['extraction_type'],  # 'question_conclusion_link'
                storage_type=entry['storage_type'],  # 'relationship'
                entity_type=entry['entity_type'],
                entity_label=entry['entity_label'],
                entity_definition=entry['entity_definition'],
                rdf_json_ld=entry['rdf_json_ld'],
                is_selected=True
            )
            db.session.add(rdf_entity)

        db.session.commit()

        logger.info(f"Successfully stored {len(pairs)} question→conclusion links")

        # Format response
        pairs_data = [{
            'question_number': p.question_number,
            'question_text': p.question_text[:200] + '...' if len(p.question_text) > 200 else p.question_text,
            'conclusion_text': p.conclusion_text[:200] + '...' if len(p.conclusion_text) > 200 else p.conclusion_text,
            'confidence': p.confidence,
            'reasoning': p.reasoning
        } for p in pairs]

        return jsonify({
            'success': True,
            'pairs': pairs_data,
            'session_id': session_id,
            'linking_prompt': linking_service.last_linking_prompt,
            'linking_response': linking_service.last_linking_response,
            'stats': {
                'total_pairs': len(pairs),
                'avg_confidence': sum(p.confidence for p in pairs) / len(pairs) if pairs else 0
            }
        })

    except Exception as e:
        logger.error(f"Error linking questions to conclusions for case {case_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def extract_code_provisions(case_id):
    """
    Extract NSPE code provisions and link them to case entities.
    This creates CodeProvisionReference individuals with applies_to relationships.
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405

        logger.info(f"Extracting code provisions for case {case_id}")

        # Get the case document
        from app.models import Document
        case = Document.query.get_or_404(case_id)

        # Get references section HTML
        references_html = None
        if case.doc_metadata and 'sections_dual' in case.doc_metadata:
            for section_key, section_content in case.doc_metadata['sections_dual'].items():
                if 'reference' in section_key.lower():
                    if isinstance(section_content, dict):
                        references_html = section_content.get('html', '')
                    break

        if not references_html:
            return jsonify({
                'success': False,
                'error': 'No references section HTML found in case metadata'
            }), 400

        # Parse HTML to extract code provisions
        from app.services.nspe_references_parser import NSPEReferencesParser
        parser = NSPEReferencesParser()
        provisions = parser.parse_references_html(references_html)

        if not provisions:
            return jsonify({
                'success': False,
                'error': 'No code provisions could be parsed from references section'
            }), 400

        logger.info(f"Parsed {len(provisions)} code provisions")

        # Get existing case entities for linking
        from app.models import TemporaryRDFStorage
        roles = TemporaryRDFStorage.query.filter(
            TemporaryRDFStorage.case_id == case_id,
            TemporaryRDFStorage.entity_type.in_(['Roles', 'roles', 'role']),
            TemporaryRDFStorage.storage_type == 'individual'
        ).all()

        states = TemporaryRDFStorage.query.filter(
            TemporaryRDFStorage.case_id == case_id,
            TemporaryRDFStorage.entity_type.in_(['States', 'states', 'state']),
            TemporaryRDFStorage.storage_type == 'individual'
        ).all()

        resources = TemporaryRDFStorage.query.filter(
            TemporaryRDFStorage.case_id == case_id,
            TemporaryRDFStorage.entity_type.in_(['Resources', 'resources', 'resource']),
            TemporaryRDFStorage.storage_type == 'individual'
        ).all()

        logger.info(f"Found {len(roles)} roles, {len(states)} states, {len(resources)} resources for linking")

        # Format entities for linker
        roles_data = [{'label': r.entity_label, 'definition': r.entity_definition} for r in roles]
        states_data = [{'label': s.entity_label, 'definition': s.entity_definition} for s in states]
        resources_data = [{'label': res.entity_label, 'definition': res.entity_definition} for res in resources]

        # Link provisions to entities using LLM
        from app.services.code_provision_linker import CodeProvisionLinker
        from app.utils.llm_utils import get_llm_client

        llm_client = get_llm_client()
        linker = CodeProvisionLinker(llm_client=llm_client)

        # Get case summary for context
        case_summary = f"Case {case_id}: {case.title}"

        linked_provisions = linker.link_provisions_to_entities(
            provisions=provisions,
            roles=roles_data,
            states=states_data,
            resources=resources_data,
            case_text_summary=case_summary
        )

        logger.info(f"Linked provisions to entities")

        # MENTION-FIRST EXCERPT EXTRACTION - 3-STAGE PIPELINE
        # Stage 1: Detect ALL provision mentions in case (universal detection)
        # Stage 2: Group mentions by which Board provision they reference
        # Stage 3: Validate that grouped mentions discuss the provision content

        # Prepare case sections
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

        logger.info(f"Extracted {len(case_sections)} case sections for excerpt matching")

        # STAGE 1: Universal provision detection - Find ALL mentions
        from app.services.universal_provision_detector import UniversalProvisionDetector

        detector = UniversalProvisionDetector()
        all_mentions = detector.detect_all_provisions(case_sections=case_sections)

        logger.info(
            f"Universal detection found {len(all_mentions)} total provision mentions"
        )

        # STAGE 2: Group mentions by Board provision
        from app.services.provision_grouper import ProvisionGrouper

        grouper = ProvisionGrouper()
        grouped_mentions = grouper.group_mentions_by_provision(
            all_mentions=all_mentions,
            board_provisions=linked_provisions
        )

        # Log grouping summary
        summary = grouper.get_grouping_summary(grouped_mentions)
        logger.info(
            f"Grouped mentions: {summary['provisions_with_mentions']} provisions have mentions, "
            f"{summary['provisions_without_mentions']} have none"
        )

        # STAGE 3: Validate grouped mentions with LLM
        from app.services.provision_group_validator import ProvisionGroupValidator

        validator = ProvisionGroupValidator(llm_client=llm_client)

        for provision in linked_provisions:
            code = provision['code_provision']
            mentions = grouped_mentions.get(code, [])

            if not mentions:
                provision['relevant_excerpts'] = []
                logger.info(f"Provision {code}: no mentions found in case")
                continue

            # Validate that mentions discuss this provision's content
            validated = validator.validate_group(
                provision_code=code,
                provision_text=provision['provision_text'],
                mentions=mentions
            )

            # Convert ValidatedMention objects to dict format for storage
            provision['relevant_excerpts'] = [
                {
                    'section': v.section,
                    'text': v.excerpt,
                    'matched_citation': v.citation_text,
                    'mention_type': v.content_type,  # 'compliance', 'violation', etc.
                    'confidence': v.confidence,
                    'validation_reasoning': v.reasoning,
                    'is_relevant': v.is_relevant
                }
                for v in validated
            ]

            logger.info(
                f"Provision {code}: {len(provision['relevant_excerpts'])} relevant excerpts "
                f"(from {len(mentions)} total mentions)"
            )

        # Clear old code provision references
        from app.models import ExtractionPrompt, db
        from datetime import datetime
        import uuid

        old_provisions = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='code_provision_reference'
        ).delete(synchronize_session=False)

        logger.info(f"Cleared {old_provisions} old code provision references")

        # Create session ID
        session_id = str(uuid.uuid4())

        # Save extraction prompt
        extraction_prompt = ExtractionPrompt(
            case_id=case_id,
            concept_type='code_provision_reference',
            step_number=1,  # Step 1e
            section_type='references',
            prompt_text=linker.last_linking_prompt or 'HTML parsing + LLM entity linking',
            llm_model='claude-opus-4-20250514',
            extraction_session_id=session_id,
            raw_response=linker.last_linking_response or '',
            results_summary={
                'total_provisions': len(linked_provisions),
                'total_entity_links': sum(len(p.get('applies_to', [])) for p in linked_provisions)
            },
            is_active=True,
            times_used=1,
            created_at=datetime.utcnow(),
            last_used_at=datetime.utcnow()
        )
        db.session.add(extraction_prompt)

        # Store code provisions as Resource individuals
        for provision in linked_provisions:
            # Create label
            label = f"NSPE_{provision['code_provision'].replace('.', '_')}"

            rdf_entity = TemporaryRDFStorage(
                case_id=case_id,
                extraction_session_id=session_id,
                extraction_type='code_provision_reference',
                storage_type='individual',
                entity_type='resources',  # Code provisions are Resources
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

        logger.info(f"Successfully stored {len(linked_provisions)} code provision references")

        return jsonify({
            'success': True,
            'total_provisions': len(linked_provisions),
            'provisions': [{
                'code_provision': p['code_provision'],
                'provision_text': p['provision_text'],
                'subject_references_count': len(p.get('subject_references', [])),
                'applies_to_count': len(p.get('applies_to', []))
            } for p in linked_provisions],
            'session_id': session_id,
            'linking_prompt': linker.last_linking_prompt,
            'linking_response': linker.last_linking_response
        })

    except Exception as e:
        logger.error(f"Error extracting code provisions for case {case_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def discussion_contextual_prompt(case_id):
    """
    API endpoint to generate dual prompts for Discussion section analysis.
    Returns both independent and contextual (with Facts awareness) prompts.
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        discussion_text = data.get('discussion_text')
        if not discussion_text:
            return jsonify({'error': 'discussion_text is required'}), 400
        
        # Facts context is optional (for contextual analysis)
        facts_context = data.get('facts_context', None)
        
        logger.info(f"Generating discussion contextual prompts for case {case_id}")
        
        # Import the discussion contextual extractor
        from app.services.extraction.discussion_contextual import create_discussion_contextual_prompt
        
        # Generate both independent and contextual prompts
        prompts = create_discussion_contextual_prompt(
            discussion_text, 
            facts_context=facts_context,
            include_mcp_context=True  # Enable MCP for existing entities
        )
        
        response = {
            'success': True,
            'independent_prompt': prompts['independent'],
            'contextual_prompt': prompts.get('contextual', None),
            'has_facts_context': facts_context is not None,
            'discussion_length': len(discussion_text)
        }
        
        if facts_context:
            response['facts_summary'] = {
                'roles_count': len(facts_context.get('roles', [])),
                'states_count': len(facts_context.get('states', [])),
                'resources_count': len(facts_context.get('resources', []))
            }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error generating discussion prompts for case {case_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def discussion_contextual_execute(case_id):
    """
    API endpoint to execute dual analysis on Discussion section.
    Performs both independent and contextual extraction, then consolidates results.
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        discussion_text = data.get('discussion_text')
        if not discussion_text:
            return jsonify({'error': 'discussion_text is required'}), 400
        
        # Facts context for contextual analysis
        facts_context = data.get('facts_context', None)
        
        logger.info(f"Starting discussion dual analysis for case {case_id}")
        
        # Import necessary services
        from app.services.extraction.discussion_contextual import DiscussionContextualExtractor
        from app.utils.llm_utils import get_llm_client
        import json
        
        # Initialize extractor and LLM client
        extractor = DiscussionContextualExtractor()
        llm_client = get_llm_client()
        
        # Phase 1: Independent Analysis
        logger.info("Phase 1: Independent analysis of discussion")
        independent_prompt = extractor.create_independent_prompt(
            discussion_text, 
            include_mcp_context=True
        )
        
        # Query LLM for independent analysis
        independent_response = llm_client.query(independent_prompt)
        
        # Parse independent results
        try:
            independent_results = json.loads(independent_response)
        except json.JSONDecodeError:
            logger.warning("Failed to parse independent results as JSON, using fallback")
            independent_results = {
                'roles': [],
                'states': [],
                'resources': [],
                'error': 'JSON parsing failed'
            }
        
        # Phase 2: Contextual Analysis (if Facts context provided)
        contextual_results = None
        if facts_context:
            logger.info("Phase 2: Contextual analysis with Facts awareness")
            contextual_prompt = extractor.create_contextual_prompt(
                discussion_text,
                facts_context,
                include_mcp_context=True
            )
            
            # Query LLM for contextual analysis
            contextual_response = llm_client.query(contextual_prompt)
            
            # Parse contextual results
            try:
                contextual_results = json.loads(contextual_response)
            except json.JSONDecodeError:
                logger.warning("Failed to parse contextual results as JSON")
                contextual_results = None
        
        # Phase 3: Consolidation
        logger.info("Phase 3: Consolidating dual analysis results")
        consolidated_results = extractor.consolidate_results(
            independent_results,
            contextual_results or {}
        )
        
        # Build response
        response = {
            'success': True,
            'independent_results': independent_results,
            'contextual_results': contextual_results,
            'consolidated_results': consolidated_results,
            'analysis_metadata': {
                'had_facts_context': facts_context is not None,
                'independent_entities': {
                    'roles': len(independent_results.get('roles', [])),
                    'states': len(independent_results.get('states', [])),
                    'resources': len(independent_results.get('resources', []))
                },
                'consolidated_entities': {
                    'roles': len(consolidated_results.get('roles', [])),
                    'states': len(consolidated_results.get('states', [])),
                    'resources': len(consolidated_results.get('resources', []))
                }
            }
        }
        
        if contextual_results:
            response['analysis_metadata']['contextual_insights'] = {
                'tensions_identified': len(contextual_results.get('identified_tensions', [])),
                'relationships_mapped': len(contextual_results.get('facts_discussion_relationships', []))
            }
        
        logger.info(f"Discussion dual analysis completed for case {case_id}")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in discussion dual analysis for case {case_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def get_saved_prompt(case_id):
    """
    API endpoint to get saved extraction prompt for a specific concept type and section.
    """
    from flask import request, jsonify
    from app.models import ExtractionPrompt
    from app.services.extraction.mock_llm_provider import get_data_source_display

    try:
        concept_type = request.args.get('concept_type', 'roles')
        section_type = request.args.get('section_type', 'facts')  # Support section_type parameter

        # Get current data source info for UI display
        data_source_info = get_data_source_display()

        # Get the saved prompt from database with section_type
        saved_prompt = ExtractionPrompt.get_active_prompt(case_id, concept_type, section_type=section_type)

        if saved_prompt:
            return jsonify({
                'success': True,
                'prompt_text': saved_prompt.prompt_text,
                'raw_response': saved_prompt.raw_response,  # Include the raw response
                'created_at': saved_prompt.created_at.strftime('%Y-%m-%d %H:%M'),
                'llm_model': saved_prompt.llm_model,
                'section_type': saved_prompt.section_type,
                'data_source': 'cached',  # This is saved data
                'data_source_label': 'Cached Response'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'No saved prompt found for {concept_type} in {section_type} section',
                'data_source': data_source_info['source'],
                'data_source_label': data_source_info['label'],
                'is_mock_mode': data_source_info['is_mock']
            })

    except Exception as e:
        logger.error(f"Error getting saved prompt for case {case_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def extract_individual_concept(case_id):
    """
    API endpoint for individual concept extraction in Step 1.
    Extracts a single concept type (roles, states, or resources) independently.
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        concept_type = data.get('concept_type')
        section_text = data.get('section_text')
        section_type = data.get('section_type', 'facts')

        if not concept_type:
            return jsonify({'error': 'concept_type is required'}), 400
        if not section_text:
            return jsonify({'error': 'section_text is required'}), 400
        if concept_type not in ['roles', 'states', 'resources']:
            return jsonify({'error': 'Invalid concept_type. Must be roles, states, or resources'}), 400

        logger.info(f"Executing individual {concept_type} extraction for case {case_id}, section: {section_type}")

        import uuid
        from app.services.extraction.concept_extraction_service import extract_concept

        session_id = str(uuid.uuid4())

        extraction = extract_concept(
            case_text=section_text,
            case_id=case_id,
            concept_type=concept_type,
            section_type=section_type,
            step_number=1,
            session_id=session_id,
        )

        # Build results list from Pydantic models
        import datetime
        type_labels = {'roles': 'Role', 'states': 'State', 'resources': 'Resource'}
        results = []
        for cls in extraction.classes:
            results.append({
                'label': cls.label,
                'description': cls.definition,
                'type': type_labels[concept_type],
                'confidence': cls.confidence,
            })
        for ind in extraction.individuals:
            name = getattr(ind, 'name', None) or getattr(ind, 'identifier', '')
            results.append({
                'label': name,
                'description': getattr(ind, 'definition', '') or '',
                'type': type_labels[concept_type],
                'confidence': ind.confidence,
            })

        from app.services.extraction.mock_llm_provider import get_data_source_display
        data_source_info = get_data_source_display()

        response_data = {
            'success': True,
            'concept_type': concept_type,
            'results': results,
            'count': len(results),
            'prompt': extraction.prompt_text,
            'raw_llm_response': extraction.raw_response,
            'extraction_metadata': {
                'extraction_method': 'enhanced_individual',
                'llm_available': True,
                'model_used': extraction.model_name,
                'timestamp': datetime.datetime.now().isoformat(),
                'provenance_tracked': False,
            },
            'session_id': session_id,
            'data_source': data_source_info['source'],
            'data_source_label': data_source_info['label'],
            'is_mock_mode': data_source_info['is_mock'],
        }

        # Add concept-specific keys for legacy JS compatibility
        if concept_type == 'roles':
            response_data['role_classes'] = [{
                'label': c.label,
                'description': c.definition,
                'type': 'role_class',
                'confidence': c.confidence,
                'distinguishing_features': c.distinguishing_features,
                'professional_scope': c.professional_scope,
            } for c in extraction.classes]
            response_data['individuals'] = [{
                'name': i.name,
                'role_class': i.role_class,
                'case_involvement': getattr(i, 'case_involvement', ''),
                'attributes': i.attributes,
            } for i in extraction.individuals]

        elif concept_type == 'states':
            response_data['state_classes'] = [{
                'label': c.label,
                'description': c.definition,
                'confidence': c.confidence,
                'persistence_type': c.persistence_type.value if c.persistence_type else 'inertial',
                'activation_conditions': c.activation_conditions,
            } for c in extraction.classes]
            response_data['state_individuals'] = [{
                'identifier': i.identifier,
                'state_class': i.state_class,
                'active_period': i.active_period,
                'triggering_event': i.triggering_event,
                'confidence': i.confidence,
            } for i in extraction.individuals]

        elif concept_type == 'resources':
            response_data['resource_classes'] = [{
                'label': c.label,
                'description': c.definition,
                'confidence': c.confidence,
                'resource_category': c.resource_category.value if c.resource_category else None,
                'authority_source': c.authority_source,
            } for c in extraction.classes]
            response_data['resource_individuals'] = [{
                'identifier': i.identifier or i.name,
                'resource_class': i.resource_class,
                'document_title': i.document_title,
                'created_by': i.created_by,
                'used_by': i.used_by,
                'confidence': i.confidence,
            } for i in extraction.individuals]

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error extracting individual {concept_type} for case {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500
