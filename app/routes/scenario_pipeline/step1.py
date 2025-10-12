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
from app.models import Document
from app.routes.scenario_pipeline.overview import _format_section_for_llm

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

def step1(case_id):
    """
    Step 1: Contextual Framework Pass for Facts and Discussion Sections
    Shows both sections with entities pass buttons for extracting roles, states, and resources.
    """
    case, facts_section, discussion_section, saved_prompts = step1_data(case_id)

    # Template context
    context = {
        'case': case,
        'facts_section': facts_section,
        'discussion_section': discussion_section,
        'current_step': 1,
        'step_title': 'Contextual Framework Pass - Facts & Discussion',
        'next_step_url': url_for('scenario_pipeline.step2', case_id=case_id),
        'prev_step_url': url_for('scenario_pipeline.overview', case_id=case_id),
        'saved_prompts': saved_prompts
    }

    # Use multi-section template with separate extractors
    return render_template('scenarios/step1.html', **context)

def step1b(case_id):
    """
    Step 1b: Contextual Framework Pass for Discussion Section
    Same exact structure as step1 but shows Discussion section content and prompts
    """
    # Load data with section_type='discussion' to get discussion prompts
    case, facts_section, discussion_section, saved_prompts = step1_data(case_id, section_type='discussion')

    # Template context
    context = {
        'case': case,
        'facts_section': facts_section,
        'discussion_section': discussion_section,
        'current_step': 1,
        'step_title': 'Contextual Framework Pass - Discussion',
        'next_step_url': url_for('scenario_pipeline.step2', case_id=case_id),  # Go to Pass 2 (Questions/Conclusions moved to Step 4)
        'prev_step_url': url_for('scenario_pipeline.step1', case_id=case_id),
        'saved_prompts': saved_prompts  # These are now discussion-specific prompts
    }

    # Use step1b.html template
    return render_template('scenarios/step1b.html', **context)

def step1c(case_id):
    """
    Step 1c: Contextual Framework Pass for Questions Section
    Extracts roles, states, and resources from the Questions section
    """
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
    """
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
    Extracts roles and resources using the ProEthica extraction services with PROV-O tracking.
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
        
        # Import the extraction services and provenance service
        from app.services.extraction.dual_role_extractor import DualRoleExtractor
        from app.services.extraction.resources import ResourcesExtractor
        from app.services.extraction.enhanced_prompts_states_capabilities import EnhancedStatesExtractor
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
        
        # Initialize extractors (Pass 1: Contextual Framework - Dual Roles, States, Resources)
        dual_role_extractor = DualRoleExtractor()
        resources_extractor = ResourcesExtractor()
        
        # Initialize LLM client for enhanced States extractor
        from app.utils.llm_utils import get_llm_client
        llm_client = get_llm_client()
        states_extractor = EnhancedStatesExtractor(llm_client=llm_client, provenance_service=prov)
        
        # Track versioned workflow if available
        version_context = nullcontext()
        if USE_VERSIONED_PROVENANCE:
            version_context = prov.track_versioned_workflow(
                workflow_name='step1_extraction',
                description='Enhanced entities pass extraction with Chapter 2 literature',
                version_tag='enhanced_prompts',
                auto_version=True
            )
        
        # Use context manager for versioned workflow
        with version_context:
            # Track the overall entities pass activity
            with prov.track_activity(
                activity_type='extraction',
                activity_name='entities_pass_step1',
                case_id=case_id,
                session_id=session_id,
                agent_type='extraction_service',
                agent_name='proethica_entities_pass',
                execution_plan={
                    'section_length': len(section_text),
                    'extraction_types': ['roles', 'states', 'resources'],
                    'pass_name': 'Contextual Framework (Pass 1)',
                    'version': 'enhanced_prompts_chapter2' if USE_VERSIONED_PROVENANCE else 'standard'
                }
            ) as main_activity:
                
                # Track dual roles extraction as a sub-activity
                with prov.track_activity(
                    activity_type='llm_query',
                    activity_name='dual_roles_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='DualRoleExtractor'
                ) as roles_activity:
                    logger.info("Extracting role classes and individuals with provenance tracking...")
                    candidate_role_classes, role_individuals = dual_role_extractor.extract_dual_roles(
                        case_text=section_text,
                        case_id=case_id,
                        section_type='facts'
                    )

                    # Record the role class extraction results
                    roles_results_entity = prov.record_extraction_results(
                        results=[{
                            'label': c.label,
                            'definition': c.definition,
                            'confidence': c.discovery_confidence,
                            'type': 'role_class'
                        } for c in candidate_role_classes],
                        activity=roles_activity,
                        entity_type='extracted_role_classes',
                        metadata={'count': len(candidate_role_classes)}
                    )

                    # Record the individual extraction results
                    individuals_results_entity = prov.record_extraction_results(
                        results=[{
                            'name': ind.name,
                            'role_class': ind.role_class,
                            'confidence': ind.confidence,
                            'is_new_role_class': ind.is_new_role_class,
                            'attributes': ind.attributes
                        } for ind in role_individuals],
                        activity=roles_activity,
                        entity_type='extracted_role_individuals',
                        metadata={'count': len(role_individuals)}
                    )
                
                # Track resources extraction as a sub-activity
                with prov.track_activity(
                    activity_type='llm_query',
                    activity_name='resources_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='ResourcesExtractor'
                ) as resources_activity:
                    logger.info("Extracting resources with provenance tracking...")
                    resource_candidates = resources_extractor.extract(
                        section_text,
                        guideline_id=case_id,
                        activity=resources_activity
                    )
                    
                    # Record the extraction results
                    resources_results_entity = prov.record_extraction_results(
                        results=[{
                            'label': c.label,
                            'description': c.description,
                            'confidence': c.confidence,
                            'debug': c.debug
                        } for c in resource_candidates],
                        activity=resources_activity,
                        entity_type='extracted_resources',
                        metadata={'count': len(resource_candidates)}
                    )
                
                # Track states extraction as a sub-activity (Part of Pass 1: Contextual Framework)
                with prov.track_activity(
                    activity_type='llm_query',
                    activity_name='states_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='EnhancedStatesExtractor'
                ) as states_activity:
                    logger.info("Extracting states with enhanced extractor...")
                    state_candidates = states_extractor.extract(
                        section_text,
                        context={'case_id': case_id},
                        activity=states_activity
                    )
                    
                    # Record the extraction results
                    states_results_entity = prov.record_extraction_results(
                        results=[{
                            'label': c.label,
                            'description': c.description,
                            'confidence': c.confidence,
                            'debug': c.debug
                        } for c in state_candidates],
                        activity=states_activity,
                        entity_type='extracted_states',
                        metadata={'count': len(state_candidates)}
                    )
                
                # Link the sub-activities to the main activity
                prov.link_activities(roles_activity, main_activity, 'sequence')
                prov.link_activities(states_activity, roles_activity, 'sequence')
                prov.link_activities(resources_activity, states_activity, 'sequence')
        
        # Commit provenance records to database
        db.session.commit()
        
        # Convert dual extraction results to serializable format
        roles_data = []
        for candidate in candidate_role_classes:
            role_entry = {
                'label': candidate.label,
                'definition': candidate.definition,
                'type': 'role_class',
                'confidence': candidate.discovery_confidence,
                # New dual extraction fields
                'distinguishing_features': candidate.distinguishing_features,
                'professional_scope': candidate.professional_scope,
                'typical_qualifications': candidate.typical_qualifications,
                'examples_from_case': candidate.examples_from_case,
                'similarity_to_existing': candidate.similarity_to_existing,
                'existing_similar_classes': candidate.existing_similar_classes or [],
                'status': candidate.status,
                'validation_priority': candidate.validation_priority,
                'is_novel': candidate.is_novel,
                'candidate_id': candidate.id,
                # Legacy compatibility
                'description': candidate.definition,
                'primary_type': 'Role'
            }
            roles_data.append(role_entry)

        # Convert role individuals to serializable format
        individuals_data = []
        for individual in role_individuals:
            individual_entry = {
                'name': individual.name,
                'role_class': individual.role_class,
                'confidence': individual.confidence,
                'is_new_role_class': individual.is_new_role_class,
                'attributes': individual.attributes,
                'relationships': individual.relationships,
                'case_section': individual.case_section,
                'type': 'role_individual'
            }
            individuals_data.append(individual_entry)
        
        resources_data = []
        for candidate in resource_candidates:
            # Extract enhanced fields from debug for easier access
            debug_data = candidate.debug or {}
            resource_entry = {
                'label': candidate.label,
                'description': candidate.description,
                'type': candidate.primary_type,
                'confidence': candidate.confidence,
                # Enhanced fields from new prompts
                'resource_category': debug_data.get('resource_category'),  # professional_code, case_precedent, etc.
                'extensional_function': debug_data.get('extensional_function'),
                'professional_knowledge_type': debug_data.get('professional_knowledge_type'),
                'usage_context': debug_data.get('usage_context', []),
                'text_references': debug_data.get('text_references', []),
                'theoretical_grounding': debug_data.get('theoretical_grounding'),
                'authority_level': debug_data.get('authority_level'),
                'is_existing': debug_data.get('is_existing'),
                'ontology_match_reasoning': debug_data.get('ontology_match_reasoning'),
                # Preserve all debug info for complete data
                'debug': candidate.debug
            }
            resources_data.append(resource_entry)
        
        # Convert states candidates to serializable format with enhanced fields
        states_data = []
        for candidate in state_candidates:
            # Extract enhanced fields from debug for easier access
            debug_data = candidate.debug or {}
            state_entry = {
                'label': candidate.label,
                'description': candidate.description,
                'type': candidate.primary_type,
                'confidence': candidate.confidence,
                # Enhanced fields from States extractor
                'state_category': debug_data.get('state_category'),  # ConflictState, RiskState, etc.
                'ethical_impact': debug_data.get('ethical_impact'),
                'contextual_factors': debug_data.get('contextual_factors', []),
                'text_references': debug_data.get('text_references', []),
                'theoretical_grounding': debug_data.get('theoretical_grounding'),
                'temporal_aspect': debug_data.get('temporal_aspect'),
                'is_existing': debug_data.get('is_existing'),
                'ontology_match_reasoning': debug_data.get('ontology_match_reasoning'),
                # Preserve all debug info for complete data
                'debug': candidate.debug
            }
            states_data.append(state_entry)
        
        logger.info(f"Entities pass completed for case {case_id}: {len(roles_data)} role classes, {len(individuals_data)} individuals, {len(states_data)} states, {len(resources_data)} resources")

        return jsonify({
            'success': True,
            'roles': roles_data,
            'individuals': individuals_data,
            'states': states_data,
            'resources': resources_data,
            'summary': {
                'roles_count': len(roles_data),
                'individuals_count': len(individuals_data),
                'states_count': len(states_data),
                'resources_count': len(resources_data),
                'total_entities': len(roles_data) + len(individuals_data) + len(states_data) + len(resources_data),
                'new_role_classes': len([r for r in roles_data if r.get('is_novel', False)]),
                'new_role_individuals': len([i for i in individuals_data if i.get('is_new_role_class', False)])
            },
            'execution_timestamp': logger.created if hasattr(logger, 'created') else None,
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

        # Import services
        from app.services.extraction.dual_role_extractor import DualRoleExtractor
        from app.services.extraction.resources import ResourcesExtractor
        from app.services.extraction.enhanced_prompts_states_capabilities import EnhancedStatesExtractor
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

        # Initialize extractors - Pass section_type='discussion' to all
        dual_role_extractor = DualRoleExtractor()
        resources_extractor = ResourcesExtractor()

        from app.utils.llm_utils import get_llm_client
        llm_client = get_llm_client()
        states_extractor = EnhancedStatesExtractor(llm_client=llm_client, provenance_service=prov)

        # Track versioned workflow
        version_context = nullcontext()
        if USE_VERSIONED_PROVENANCE:
            version_context = prov.track_versioned_workflow(
                workflow_name='step1b_extraction_discussion',
                description='Discussion section entities pass extraction',
                version_tag='discussion_section',
                auto_version=True
            )

        with version_context:
            # Track main activity
            with prov.track_activity(
                activity_type='extraction',
                activity_name='entities_pass_step1_discussion',
                case_id=case_id,
                session_id=session_id,
                agent_type='extraction_service',
                agent_name='proethica_entities_pass_discussion',
                execution_plan={
                    'section_length': len(section_text),
                    'section_type': 'discussion',
                    'extraction_types': ['roles', 'states', 'resources'],
                    'pass_name': 'Contextual Framework (Pass 1 - Discussion)'
                }
            ) as main_activity:

                # Extract roles with section_type='discussion'
                with prov.track_activity(
                    activity_type='llm_query',
                    activity_name='dual_roles_extraction_discussion',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='DualRoleExtractor'
                ) as roles_activity:
                    logger.info("Extracting roles from Discussion section...")
                    candidate_role_classes, role_individuals = dual_role_extractor.extract_dual_roles(
                        case_text=section_text,
                        case_id=case_id,
                        section_type='discussion'  # Key difference: Discussion section
                    )

                    roles_results_entity = prov.record_extraction_results(
                        results=[{
                            'label': c.label,
                            'definition': c.definition,
                            'confidence': c.discovery_confidence,
                            'type': 'role_class'
                        } for c in candidate_role_classes],
                        activity=roles_activity,
                        entity_type='extracted_role_classes',
                        metadata={'count': len(candidate_role_classes), 'section_type': 'discussion'}
                    )

                    individuals_results_entity = prov.record_extraction_results(
                        results=[{
                            'name': ind.name,
                            'role_class': ind.role_class,
                            'confidence': ind.confidence
                        } for ind in role_individuals],
                        activity=roles_activity,
                        entity_type='extracted_role_individuals',
                        metadata={'count': len(role_individuals), 'section_type': 'discussion'}
                    )

                # Extract resources with section_type='discussion'
                with prov.track_activity(
                    activity_type='llm_query',
                    activity_name='resources_extraction_discussion',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='ResourcesExtractor'
                ) as resources_activity:
                    logger.info("Extracting resources from Discussion section...")
                    resource_candidates = resources_extractor.extract(
                        section_text,
                        guideline_id=case_id,
                        activity=resources_activity
                    )

                    resources_results_entity = prov.record_extraction_results(
                        results=[{
                            'label': c.label,
                            'description': c.description,
                            'confidence': c.confidence
                        } for c in resource_candidates],
                        activity=resources_activity,
                        entity_type='extracted_resources',
                        metadata={'count': len(resource_candidates), 'section_type': 'discussion'}
                    )

                # Extract states with section_type='discussion'
                with prov.track_activity(
                    activity_type='llm_query',
                    activity_name='states_extraction_discussion',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='EnhancedStatesExtractor'
                ) as states_activity:
                    logger.info("Extracting states from Discussion section...")
                    state_candidates = states_extractor.extract(
                        section_text,
                        context={'case_id': case_id},
                        activity=states_activity
                    )

                    states_results_entity = prov.record_extraction_results(
                        results=[{
                            'label': c.label,
                            'description': c.description,
                            'confidence': c.confidence
                        } for c in state_candidates],
                        activity=states_activity,
                        entity_type='extracted_states',
                        metadata={'count': len(state_candidates), 'section_type': 'discussion'}
                    )

                # Link activities
                prov.link_activities(roles_activity, main_activity, 'sequence')
                prov.link_activities(states_activity, roles_activity, 'sequence')
                prov.link_activities(resources_activity, states_activity, 'sequence')

        # Commit provenance
        db.session.commit()

        # Format results (same as entities_pass_execute)
        roles_data = []
        for candidate in candidate_role_classes:
            roles_data.append({
                'label': candidate.label,
                'definition': candidate.definition,
                'type': 'role_class',
                'confidence': candidate.discovery_confidence,
                'section_type': 'discussion'  # Mark section
            })

        individuals_data = []
        for individual in role_individuals:
            individuals_data.append({
                'name': individual.name,
                'role_class': individual.role_class,
                'confidence': individual.confidence,
                'type': 'role_individual',
                'section_type': 'discussion'  # Mark section
            })

        resources_data = []
        for candidate in resource_candidates:
            resources_data.append({
                'label': candidate.label,
                'description': candidate.description,
                'type': candidate.primary_type,
                'confidence': candidate.confidence,
                'section_type': 'discussion'  # Mark section
            })

        states_data = []
        for candidate in state_candidates:
            states_data.append({
                'label': candidate.label,
                'description': candidate.description,
                'type': candidate.primary_type,
                'confidence': candidate.confidence,
                'section_type': 'discussion'  # Mark section
            })

        logger.info(f"Discussion entities pass completed: {len(roles_data)} role classes, {len(individuals_data)} individuals, {len(states_data)} states, {len(resources_data)} resources")

        return jsonify({
            'success': True,
            'section_type': 'discussion',
            'roles': roles_data,
            'individuals': individuals_data,
            'states': states_data,
            'resources': resources_data,
            'summary': {
                'roles_count': len(roles_data),
                'individuals_count': len(individuals_data),
                'states_count': len(states_data),
                'resources_count': len(resources_data),
                'total_entities': len(roles_data) + len(individuals_data) + len(states_data) + len(resources_data)
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
            'is_committed': m.is_committed
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

    try:
        concept_type = request.args.get('concept_type', 'roles')
        section_type = request.args.get('section_type', 'facts')  # Support section_type parameter

        # Get the saved prompt from database with section_type
        saved_prompt = ExtractionPrompt.get_active_prompt(case_id, concept_type, section_type=section_type)

        if saved_prompt:
            return jsonify({
                'success': True,
                'prompt_text': saved_prompt.prompt_text,
                'raw_response': saved_prompt.raw_response,  # Include the raw response
                'created_at': saved_prompt.created_at.strftime('%Y-%m-%d %H:%M'),
                'llm_model': saved_prompt.llm_model,
                'section_type': saved_prompt.section_type
            })
        else:
            return jsonify({
                'success': False,
                'message': f'No saved prompt found for {concept_type} in {section_type} section'
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

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        concept_type = data.get('concept_type')
        section_text = data.get('section_text')
        section_type = data.get('section_type', 'facts')  # Support section_type parameter

        if not concept_type:
            return jsonify({'error': 'concept_type is required'}), 400
        if not section_text:
            return jsonify({'error': 'section_text is required'}), 400

        # Validate concept type
        if concept_type not in ['roles', 'states', 'resources']:
            return jsonify({'error': 'Invalid concept_type. Must be roles, states, or resources'}), 400

        logger.info(f"Executing individual {concept_type} extraction for case {case_id}, section: {section_type}")

        # Import necessary services
        from app.utils.llm_utils import get_llm_client
        from app.services.provenance_service import get_provenance_service
        from models import ModelConfig
        from app.models import db
        import uuid
        import datetime

        # Try to use versioned provenance if available
        try:
            from app.services.provenance_versioning_service import get_versioned_provenance_service
            prov = get_versioned_provenance_service(session=db.session)
            USE_VERSIONED = True
        except ImportError:
            prov = get_provenance_service(session=db.session)
            USE_VERSIONED = False

        # Create a session ID for this extraction
        session_id = str(uuid.uuid4())

        # Get LLM client for enhanced extractors
        llm_client = get_llm_client()

        # Get the case for context
        case = Document.query.get_or_404(case_id)
        context = {
            'case_id': case_id,
            'case_title': case.title,
            'document_type': case.document_type,
            'extraction_mode': 'individual'
        }

        # Initialize the appropriate extractor and perform extraction
        candidates = []
        extraction_prompt = None

        if concept_type == 'roles':
            from app.services.extraction.dual_role_extractor import DualRoleExtractor

            extractor = DualRoleExtractor()

            # Generate the prompt for display (dual extraction)
            extraction_prompt = extractor._create_dual_role_extraction_prompt(section_text, section_type)
            logger.info(f"DEBUG: Generated extraction prompt (first 200 chars): {extraction_prompt[:200] if extraction_prompt else 'None'}")

            # Use dual extraction to get both classes and individuals
            # Skip complex provenance tracking for individual extraction to avoid session issues
            try:
                logger.info(f"DEBUG: About to call extract_dual_roles with case_id={case_id}, section_type={section_type}")
                logger.info(f"DEBUG: section_text length: {len(section_text)}")
                candidate_role_classes, role_individuals = extractor.extract_dual_roles(
                    case_text=section_text,
                    case_id=case_id,
                    section_type=section_type  # Use the section_type parameter
                )
                logger.info(f"DEBUG: extract_dual_roles completed successfully")
            except Exception as e:
                logger.error(f"DEBUG: extract_dual_roles failed with error: {e}")
                import traceback
                logger.error(f"DEBUG: Full traceback: {traceback.format_exc()}")
                raise

            # Get the raw LLM response for debugging
            raw_llm_response = extractor.get_last_raw_response()

            # Save the prompt and raw response to database
            from app.models import ExtractionPrompt, db
            try:
                saved_prompt = ExtractionPrompt.save_prompt(
                    case_id=case_id,
                    concept_type='roles',
                    prompt_text=extraction_prompt,
                    raw_response=raw_llm_response,  # Save the raw LLM response
                    step_number=1,
                    section_type=section_type,  # Include section_type
                    llm_model=ModelConfig.get_claude_model("powerful") if llm_client else "fallback",
                    extraction_session_id=session_id
                )
                logger.info(f"Saved roles extraction prompt and response for case {case_id}")
            except Exception as e:
                logger.warning(f"Could not save extraction prompt: {e}")
            logger.info(f"DEBUG RDF: raw_llm_response available: {raw_llm_response is not None}, length: {len(raw_llm_response) if raw_llm_response else 0}")

            # Convert the raw response to RDF if we have it
            if raw_llm_response:
                try:
                    import json
                    from app.services.rdf_extraction_converter import RDFExtractionConverter
                    from app.models import TemporaryRDFStorage

                    logger.info(f"DEBUG RDF: Starting RDF conversion for case {case_id}")

                    # Parse the raw response - handle mixed text/JSON
                    try:
                        raw_data = json.loads(raw_llm_response)
                    except json.JSONDecodeError:
                        # Try to extract JSON from mixed response
                        import re
                        json_match = re.search(r'\{[\s\S]*\}', raw_llm_response)
                        if json_match:
                            raw_data = json.loads(json_match.group())
                            logger.info(f"DEBUG RDF: Extracted JSON from mixed response")
                        else:
                            logger.error(f"DEBUG RDF: Could not extract JSON from response")
                            raise ValueError("Could not extract JSON from LLM response")

                    logger.info(f"DEBUG RDF: Parsed JSON with keys: {list(raw_data.keys())}")
                    logger.info(f"DEBUG RDF: new_role_classes count: {len(raw_data.get('new_role_classes', []))}")
                    logger.info(f"DEBUG RDF: role_individuals count: {len(raw_data.get('role_individuals', []))}")

                    # Convert to RDF
                    rdf_converter = RDFExtractionConverter()
                    class_graph, individual_graph = rdf_converter.convert_extraction_to_rdf(
                        raw_data, case_id
                    )
                    logger.info(f"DEBUG RDF: Converted to RDF graphs - classes: {len(class_graph)}, individuals: {len(individual_graph)}")

                    # Get temporary triples for storage
                    rdf_data = rdf_converter.get_temporary_triples()
                    logger.info(f"DEBUG RDF: Got temporary triples - new_classes: {len(rdf_data.get('new_classes', []))}, new_individuals: {len(rdf_data.get('new_individuals', []))}")

                    # Prepare provenance metadata for entity storage
                    provenance_data = {
                        'section_type': section_type,
                        'extracted_at': datetime.datetime.utcnow().isoformat(),
                        'model_used': 'claude-opus-4-1-20250805',
                        'extraction_pass': 'contextual_framework',
                        'concept_type': 'roles'
                    }

                    # Store in temporary RDF storage with provenance
                    stored_entities = TemporaryRDFStorage.store_extraction_results(
                        case_id=case_id,
                        extraction_session_id=session_id,
                        extraction_type='roles',
                        rdf_data=rdf_data,
                        extraction_model='claude-opus-4-1-20250805',
                        provenance_data=provenance_data
                    )

                    logger.info(f"✅ DEBUG RDF: Stored {len(stored_entities)} RDF entities in temporary storage for case {case_id}")

                except Exception as e:
                    logger.error(f"❌ DEBUG RDF: Failed to convert and store RDF: {e}")
                    import traceback
                    logger.error(f"DEBUG RDF Traceback: {traceback.format_exc()}")
            else:
                logger.warning(f"DEBUG RDF: No raw_llm_response available for RDF conversion")

            # Convert to format expected by the response
            candidates = []

            # Debug: Check what we actually got
            logger.info(f"DEBUG: candidate_role_classes type: {type(candidate_role_classes)}, length: {len(candidate_role_classes)}")
            if candidate_role_classes:
                logger.info(f"DEBUG: first role_class type: {type(candidate_role_classes[0])}")
                logger.info(f"DEBUG: first role_class content: {candidate_role_classes[0]}")

            logger.info(f"DEBUG: role_individuals type: {type(role_individuals)}, length: {len(role_individuals)}")
            if role_individuals:
                logger.info(f"DEBUG: first individual type: {type(role_individuals[0])}")
                logger.info(f"DEBUG: first individual content: {role_individuals[0]}")

            # Now candidate_role_classes are CandidateRoleClass objects
            # and role_individuals are RoleIndividual objects
            for role_class in candidate_role_classes:
                candidates.append({
                    'label': role_class.label,
                    'description': role_class.definition,
                    'type': 'role_class',
                    'confidence': role_class.confidence,
                    'distinguishing_features': role_class.distinguishing_features,
                    'professional_scope': role_class.professional_scope,
                    'primary_type': 'Role'
                })

            # Add individuals
            for individual in role_individuals:
                candidates.append({
                    'label': individual.name,
                    'description': f"Individual assigned to {individual.role_class}",
                    'type': 'role_individual',
                    'confidence': individual.confidence,
                    'role_class': individual.role_class,
                    'attributes': individual.attributes,
                    'relationships': individual.relationships,
                    'primary_type': 'Role'
                })

        elif concept_type == 'states':
            from app.services.extraction.dual_states_extractor import DualStatesExtractor

            extractor = DualStatesExtractor()

            # Generate the prompt for display (dual extraction)
            extraction_prompt = extractor._create_dual_states_extraction_prompt(section_text, section_type)

            # Perform dual extraction (classes + individuals)
            # Skip provenance tracking for now - focusing on extraction functionality
            candidate_state_classes, state_individuals = extractor.extract_dual_states(section_text, case_id, section_type)

            logger.info(f"Dual states extraction for case {case_id}: {len(candidate_state_classes)} new classes, {len(state_individuals)} individuals")

            # Get the raw LLM response for RDF conversion and display
            raw_llm_response = extractor.get_last_raw_response()

            # Save the prompt and raw response to database
            from app.models import ExtractionPrompt, db
            try:
                saved_prompt = ExtractionPrompt.save_prompt(
                    case_id=case_id,
                    concept_type='states',
                    prompt_text=extraction_prompt,
                    raw_response=raw_llm_response,  # Save the raw LLM response
                    step_number=1,
                    section_type=section_type,  # Include section_type
                    llm_model=ModelConfig.get_claude_model("powerful") if llm_client else "fallback",
                    extraction_session_id=session_id
                )
                logger.info(f"Saved states extraction prompt and response for case {case_id}, section: {section_type}")
            except Exception as e:
                logger.warning(f"Could not save extraction prompt: {e}")
            logger.info(f"DEBUG RDF: raw_llm_response available: {raw_llm_response is not None}, length: {len(raw_llm_response) if raw_llm_response else 0}")

            # Convert the raw response to RDF if we have it
            if raw_llm_response:
                try:
                    import json
                    from app.services.rdf_extraction_converter import RDFExtractionConverter
                    from app.models import TemporaryRDFStorage

                    logger.info(f"DEBUG RDF: Starting RDF conversion for states in case {case_id}")

                    # Parse the raw response - handle mixed text/JSON
                    try:
                        raw_data = json.loads(raw_llm_response)
                    except json.JSONDecodeError:
                        # Try to extract JSON from mixed response
                        import re
                        json_match = re.search(r'\{[\s\S]*\}', raw_llm_response)
                        if json_match:
                            raw_data = json.loads(json_match.group())
                            logger.info(f"DEBUG RDF: Extracted JSON from mixed response")
                        else:
                            logger.error(f"DEBUG RDF: Could not extract JSON from response")
                            raise ValueError("Could not extract JSON from LLM response")

                    logger.info(f"DEBUG RDF: Parsed JSON with keys: {list(raw_data.keys())}")
                    logger.info(f"DEBUG RDF: new_state_classes count: {len(raw_data.get('new_state_classes', []))}")
                    logger.info(f"DEBUG RDF: state_individuals count: {len(raw_data.get('state_individuals', []))}")

                    # Convert to RDF using states-specific conversion
                    rdf_converter = RDFExtractionConverter()
                    class_graph, individual_graph = rdf_converter.convert_states_extraction_to_rdf(
                        raw_data, case_id
                    )
                    logger.info(f"DEBUG RDF: Converted to RDF graphs - classes: {len(class_graph)}, individuals: {len(individual_graph)}")

                    # Get temporary triples for storage
                    rdf_data = rdf_converter.get_temporary_triples()
                    logger.info(f"DEBUG RDF: Got temporary triples - new_classes: {len(rdf_data.get('new_classes', []))}, new_individuals: {len(rdf_data.get('new_individuals', []))}")

                    # Prepare provenance metadata for entity storage
                    provenance_data = {
                        'section_type': section_type,
                        'extracted_at': datetime.datetime.utcnow().isoformat(),
                        'model_used': 'claude-opus-4-1-20250805',
                        'extraction_pass': 'contextual_framework',
                        'concept_type': 'states'
                    }

                    # Store in temporary RDF storage using the same method as Roles
                    stored_entities = TemporaryRDFStorage.store_extraction_results(
                        case_id=case_id,
                        extraction_session_id=session_id,
                        extraction_type='states',  # Mark as states extraction
                        rdf_data=rdf_data,
                        extraction_model='claude-opus-4-1-20250805',
                        provenance_data=provenance_data
                    )

                    logger.info(f"✅ DEBUG RDF: Stored {len(stored_entities)} RDF entities in temporary storage for case {case_id}")

                except Exception as e:
                    logger.error(f"Error converting states to RDF: {e}", exc_info=True)

            # Convert to common format for storage
            candidates = []
            for state_class in candidate_state_classes:
                candidates.append({
                    'label': state_class.label,
                    'description': state_class.definition,
                    'type': 'state_class',
                    'confidence': state_class.confidence,
                    'activation_conditions': state_class.activation_conditions,
                    'persistence_type': state_class.persistence_type,
                    'primary_type': 'State'
                })

            # Add individuals
            for individual in state_individuals:
                candidates.append({
                    'label': individual.identifier,
                    'description': f"State instance of {individual.state_class}",
                    'type': 'state_individual',
                    'confidence': individual.confidence,
                    'state_class': individual.state_class,
                    'active_period': individual.active_period,
                    'triggering_event': individual.triggering_event,
                    'primary_type': 'State'
                })

        elif concept_type == 'resources':
            from app.services.extraction.dual_resources_extractor import DualResourcesExtractor

            extractor = DualResourcesExtractor()

            # Generate the prompt for display (dual extraction)
            extraction_prompt = extractor._create_dual_resources_extraction_prompt(section_text, section_type)

            # Perform dual extraction (classes + individuals)
            # Skip provenance tracking for now - focusing on extraction functionality
            candidate_resource_classes, resource_individuals = extractor.extract_dual_resources(section_text, case_id, section_type)

            logger.info(f"Dual resources extraction for case {case_id}: {len(candidate_resource_classes)} new classes, {len(resource_individuals)} individuals")

            # Get the raw LLM response for RDF conversion and display
            raw_llm_response = extractor.get_last_raw_response()

            # Save the prompt and raw response to database
            from app.models import ExtractionPrompt, db
            try:
                saved_prompt = ExtractionPrompt.save_prompt(
                    case_id=case_id,
                    concept_type='resources',
                    prompt_text=extraction_prompt,
                    raw_response=raw_llm_response,  # Save the raw LLM response
                    step_number=1,
                    section_type=section_type,  # Include section_type
                    llm_model=ModelConfig.get_claude_model("powerful") if llm_client else "fallback",
                    extraction_session_id=session_id
                )
                logger.info(f"Saved resources extraction prompt and response for case {case_id}, section: {section_type}")
            except Exception as e:
                logger.warning(f"Could not save extraction prompt: {e}")
            logger.info(f"DEBUG RDF: raw_llm_response available: {raw_llm_response is not None}, length: {len(raw_llm_response) if raw_llm_response else 0}")

            # Convert the raw response to RDF if we have it
            if raw_llm_response:
                try:
                    import json
                    from app.services.rdf_extraction_converter import RDFExtractionConverter
                    from app.models import TemporaryRDFStorage

                    logger.info(f"DEBUG RDF: Starting RDF conversion for resources in case {case_id}")

                    # Parse the raw response - handle mixed text/JSON
                    try:
                        raw_data = json.loads(raw_llm_response)
                    except json.JSONDecodeError:
                        # Try to extract JSON from mixed response
                        import re
                        json_match = re.search(r'\{[\s\S]*\}', raw_llm_response)
                        if json_match:
                            raw_data = json.loads(json_match.group())
                            logger.info(f"DEBUG RDF: Extracted JSON from mixed response")
                        else:
                            logger.error(f"DEBUG RDF: Could not extract JSON from response")
                            raise ValueError("Could not extract JSON from LLM response")

                    logger.info(f"DEBUG RDF: Parsed JSON with keys: {list(raw_data.keys())}")
                    logger.info(f"DEBUG RDF: new_resource_classes count: {len(raw_data.get('new_resource_classes', []))}")
                    logger.info(f"DEBUG RDF: resource_individuals count: {len(raw_data.get('resource_individuals', []))}")

                    # Convert to RDF using resources-specific conversion
                    rdf_converter = RDFExtractionConverter()
                    class_graph, individual_graph = rdf_converter.convert_resources_extraction_to_rdf(
                        raw_data, case_id
                    )
                    logger.info(f"DEBUG RDF: Converted to RDF graphs - classes: {len(class_graph)}, individuals: {len(individual_graph)}")

                    # Get temporary triples for storage
                    rdf_data = rdf_converter.get_temporary_triples()
                    logger.info(f"DEBUG RDF: Got temporary triples - new_classes: {len(rdf_data.get('new_classes', []))}, new_individuals: {len(rdf_data.get('new_individuals', []))}")

                    # Prepare provenance metadata for entity storage
                    provenance_data = {
                        'section_type': section_type,
                        'extracted_at': datetime.datetime.utcnow().isoformat(),
                        'model_used': 'claude-opus-4-1-20250805',
                        'extraction_pass': 'contextual_framework',
                        'concept_type': 'resources'
                    }

                    # Store in temporary RDF storage using the same method as Roles and States
                    stored_entities = TemporaryRDFStorage.store_extraction_results(
                        case_id=case_id,
                        extraction_session_id=session_id,
                        extraction_type='resources',  # Mark as resources extraction
                        rdf_data=rdf_data,
                        extraction_model='claude-opus-4-1-20250805',
                        provenance_data=provenance_data
                    )

                    logger.info(f"DEBUG RDF: Stored {len(stored_entities)} RDF entities for resources in case {case_id}")

                    # Convert to format for response (for backward compatibility)
                    candidates = []
                    for cls in candidate_resource_classes:
                        candidates.append({
                            'label': cls.label,
                            'description': cls.definition,
                            'type': 'class',
                            'primary_type': 'Resource',
                            'category': 'Resource',
                            'confidence': cls.confidence,
                            'distinguishing_features': [cls.resource_type],
                            'professional_scope': cls.typical_usage,
                            'role_class': ''
                        })
                    for individual in resource_individuals:
                        candidates.append({
                            'label': individual.identifier,
                            'description': individual.document_title or individual.used_in_context,
                            'type': 'individual',
                            'name': individual.identifier,
                            'primary_type': 'Resource',
                            'category': 'Resource',
                            'confidence': individual.confidence,
                            'attributes': {
                                'created_by': individual.created_by,
                                'version': individual.version,
                                'used_by': individual.used_by
                            },
                            'relationships': []
                        })

                    # Skip the old storage method since we're using RDF storage
                    logger.info(f"Skipping old storage - using RDF storage instead")

                except Exception as e:
                    logger.error(f"DEBUG RDF: Failed to convert or store resources as RDF: {e}")
                    import traceback
                    logger.error(f"DEBUG RDF: {traceback.format_exc()}")
                    # Fall back to old format
                    candidates = []

            else:
                logger.warning(f"DEBUG RDF: No raw response available for RDF conversion")
                candidates = []

        # Store extracted entities in temporary storage for review
        # Skip this for concept types that use RDF storage
        skip_old_storage = concept_type in ['roles', 'states', 'resources'] and raw_llm_response

        logger.info(f"About to store {len(candidates) if candidates else 0} candidates in temporary storage (skip_old_storage={skip_old_storage})")

        if candidates and not skip_old_storage:
            try:
                logger.info(f"Importing CaseEntityStorageService...")
                from app.services.case_entity_storage_service import CaseEntityStorageService
                logger.info(f"✅ CaseEntityStorageService imported successfully")

                # Map concept types to NSPE sections
                section_mapping = {
                    'roles': 'facts',
                    'states': 'facts',
                    'resources': 'facts'  # Resources can be in facts or references
                }

                # Convert candidates to storage format
                entities_for_storage = []
                for candidate in candidates:
                    entity_data = {
                        'label': candidate['label'],
                        'description': candidate['description'] or '',
                        'category': candidate.get('primary_type', concept_type.capitalize()),
                        'confidence': candidate['confidence'],
                        'source_text': '',
                        'extraction_metadata': {
                            'type': candidate['type'],
                            'distinguishing_features': candidate.get('distinguishing_features', []),
                            'professional_scope': candidate.get('professional_scope', ''),
                            'role_class': candidate.get('role_class', ''),
                            'attributes': candidate.get('attributes', {}),
                            'relationships': candidate.get('relationships', [])
                        }
                    }
                    entities_for_storage.append(entity_data)
                    logger.info(f"Prepared entity for storage: {entity_data['label']} ({entity_data['category']}) - {candidate['type']}")

                logger.info(f"Attempting to store {len(entities_for_storage)} entities...")

                # Store in temporary storage
                storage_session_id, temp_concepts = CaseEntityStorageService.store_extracted_entities(
                    entities=entities_for_storage,
                    case_id=case_id,
                    section_type=section_mapping.get(concept_type, 'facts'),
                    extraction_metadata={
                        'extraction_type': f'{concept_type}_individual',
                        'extraction_pass': 'contextual_framework',
                        'model_used': 'claude-opus-4-1-20250805',
                        'extractor': f'{concept_type.capitalize()}Extractor',
                        'session_uuid': session_id,
                        'individual_extraction': True
                    },
                    provenance_activity=activity if USE_VERSIONED and 'activity' in locals() else None
                )

                logger.info(f"✅ Successfully stored {len(temp_concepts)} {concept_type} entities in temporary storage (session: {storage_session_id})")

            except Exception as e:
                logger.error(f"❌ Failed to store {concept_type} entities in temporary storage: {e}")
                import traceback
                logger.error(f"Storage error traceback: {traceback.format_exc()}")
        else:
            logger.warning(f"No candidates to store for {concept_type} extraction")

        # Format results
        results = []
        for candidate in candidates:
            result = {
                'label': candidate['label'],
                'description': candidate['description'],
                'type': candidate['primary_type'],
                'confidence': candidate['confidence']
            }

            # Add any debug info
            if 'debug' in candidate and candidate['debug']:
                for key, value in candidate['debug'].items():
                    if key not in result:
                        result[key] = value

            results.append(result)

        # Determine model used
        model_used = ModelConfig.get_claude_model("powerful") if llm_client else "fallback"

        # Log what we're about to send
        logger.info(f"DEBUG: About to send prompt in response (first 200 chars): {extraction_prompt[:200] if extraction_prompt else 'None'}")

        response_data = {
            'success': True,
            'concept_type': concept_type,
            'results': results,
            'count': len(results),
            'prompt': extraction_prompt,
            'extraction_metadata': {
                'extraction_method': 'enhanced_individual',
                'llm_available': llm_client is not None,
                'model_used': model_used,
                'timestamp': datetime.datetime.now().isoformat(),
                'provenance_tracked': USE_VERSIONED
            },
            'session_id': session_id
        }

        # Add special formatting for dual extraction types (roles and states)
        if concept_type == 'roles' and 'candidate_role_classes' in locals():
            # Separate roles into classes and individuals
            response_data['role_classes'] = [c for c in candidates if c.get('type') == 'role_class']
            response_data['individuals'] = [{
                'name': c['label'],
                'role_class': c.get('role_class'),
                'case_involvement': c.get('description'),
                'attributes': c.get('attributes', {})
            } for c in candidates if c.get('type') == 'role_individual']
            if 'raw_llm_response' in locals():
                response_data['raw_llm_response'] = raw_llm_response
                logger.info(f"Adding raw LLM response to response data (length: {len(raw_llm_response) if raw_llm_response else 0})")

        elif concept_type == 'states' and 'candidate_state_classes' in locals():
            # Separate states into classes and individuals
            response_data['state_classes'] = [{
                'label': c['label'],
                'description': c['description'],
                'confidence': c['confidence'],
                'persistence_type': c.get('persistence_type'),
                'activation_conditions': c.get('activation_conditions', [])
            } for c in candidates if c.get('type') == 'state_class']
            response_data['state_individuals'] = [{
                'identifier': c['label'],
                'state_class': c.get('state_class'),
                'active_period': c.get('active_period'),
                'triggering_event': c.get('triggering_event'),
                'confidence': c['confidence']
            } for c in candidates if c.get('type') == 'state_individual']
            if 'raw_llm_response' in locals():
                response_data['raw_llm_response'] = raw_llm_response
                logger.info(f"Adding raw LLM response to response data (length: {len(raw_llm_response) if raw_llm_response else 0})")

        elif concept_type == 'resources' and 'candidate_resource_classes' in locals():
            # Separate resources into classes and individuals
            response_data['resource_classes'] = [{
                'label': c['label'],
                'description': c['description'],
                'confidence': c['confidence'],
                'resource_type': c.get('resource_type'),
                'accessibility': c.get('accessibility', [])
            } for c in candidates if c.get('type') == 'class']
            response_data['resource_individuals'] = [{
                'identifier': c['label'],
                'resource_class': c.get('resource_class'),
                'document_title': c.get('description'),
                'created_by': c.get('attributes', {}).get('created_by'),
                'used_by': c.get('attributes', {}).get('used_by'),
                'confidence': c['confidence']
            } for c in candidates if c.get('type') == 'individual']
            if 'raw_llm_response' in locals():
                response_data['raw_llm_response'] = raw_llm_response
                logger.info(f"Adding raw LLM response to response data for resources (length: {len(raw_llm_response) if raw_llm_response else 0})")

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error extracting individual {concept_type} for case {case_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
