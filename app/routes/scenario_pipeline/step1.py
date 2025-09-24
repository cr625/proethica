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

def step1(case_id):
    """
    Step 1: Contextual Framework Pass for Facts and Discussion Sections
    Shows both sections with entities pass buttons for extracting roles, states, and resources.
    Discussion uses dual analysis: independent and contextual with Facts awareness.
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
        
        # Load any saved prompts for this case
        from app.models import ExtractionPrompt
        saved_prompts = {
            'roles': ExtractionPrompt.get_active_prompt(case_id, 'roles'),
            'states': ExtractionPrompt.get_active_prompt(case_id, 'states'),
            'resources': ExtractionPrompt.get_active_prompt(case_id, 'resources')
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

        # Use multi-section template with separate extractors
        return render_template('scenarios/step1_multi_section.html', **context)

    except Exception as e:
        logger.error(f"Error loading step 1 for case {case_id}: {str(e)}")
        flash(f'Error loading step 1: {str(e)}', 'danger')
        return redirect(url_for('cases.view_case', id=case_id))

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
    API endpoint to get saved extraction prompt for a specific concept type.
    """
    from flask import request, jsonify
    from app.models import ExtractionPrompt

    try:
        concept_type = request.args.get('concept_type', 'roles')

        # Get the saved prompt from database
        saved_prompt = ExtractionPrompt.get_active_prompt(case_id, concept_type)

        if saved_prompt:
            return jsonify({
                'success': True,
                'prompt_text': saved_prompt.prompt_text,
                'raw_response': saved_prompt.raw_response,  # Include the raw response
                'created_at': saved_prompt.created_at.strftime('%Y-%m-%d %H:%M'),
                'llm_model': saved_prompt.llm_model
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No saved prompt found'
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

        if not concept_type:
            return jsonify({'error': 'concept_type is required'}), 400
        if not section_text:
            return jsonify({'error': 'section_text is required'}), 400

        # Validate concept type
        if concept_type not in ['roles', 'states', 'resources']:
            return jsonify({'error': 'Invalid concept_type. Must be roles, states, or resources'}), 400

        logger.info(f"Executing individual {concept_type} extraction for case {case_id}")

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
            extraction_prompt = extractor._create_dual_role_extraction_prompt(section_text, 'facts')
            logger.info(f"DEBUG: Generated extraction prompt (first 200 chars): {extraction_prompt[:200] if extraction_prompt else 'None'}")

            # Use dual extraction to get both classes and individuals
            # Skip complex provenance tracking for individual extraction to avoid session issues
            try:
                logger.info(f"DEBUG: About to call extract_dual_roles with case_id={case_id}, section_type='facts'")
                logger.info(f"DEBUG: section_text length: {len(section_text)}")
                candidate_role_classes, role_individuals = extractor.extract_dual_roles(
                    case_text=section_text,
                    case_id=case_id,
                    section_type='facts'
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

                    # Store in temporary RDF storage
                    stored_entities = TemporaryRDFStorage.store_extraction_results(
                        case_id=case_id,
                        extraction_session_id=session_id,
                        extraction_type='roles',
                        rdf_data=rdf_data,
                        extraction_model='claude-opus-4-1-20250805'
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
            extraction_prompt = extractor._create_dual_states_extraction_prompt(section_text, 'facts')

            # Perform dual extraction (classes + individuals)
            if USE_VERSIONED:
                with prov.track_activity(
                    activity_type='extraction',
                    activity_name='states_dual_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='DualStatesExtractor'
                ) as activity:
                    candidate_state_classes, state_individuals = extractor.extract_dual_states(section_text, case_id, 'facts')
                    activity.used_entity(f"case_{case_id}_facts", attributes={'section': 'facts', 'text_length': len(section_text)})
                    activity.generated_entity(
                        f"states_extraction_{session_id}",
                        attributes={
                            'new_classes_count': len(candidate_state_classes),
                            'individuals_count': len(state_individuals)
                        }
                    )
            else:
                candidate_state_classes, state_individuals = extractor.extract_dual_states(section_text, case_id, 'facts')

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
                    llm_model=ModelConfig.get_claude_model("powerful") if llm_client else "fallback",
                    extraction_session_id=session_id
                )
                logger.info(f"Saved states extraction prompt and response for case {case_id}")
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

                    # Store in temporary RDF storage
                    for class_data in rdf_data.get('new_classes', []):
                        storage_entry = TemporaryRDFStorage(
                            case_id=case_id,
                            entity_type='state_class',
                            entity_label=class_data['label'],
                            rdf_triples=json.dumps(class_data['triples']),
                            metadata={
                                'extraction_session': session_id,
                                'section': 'facts'
                            }
                        )
                        db.session.add(storage_entry)

                    for ind_data in rdf_data.get('new_individuals', []):
                        storage_entry = TemporaryRDFStorage(
                            case_id=case_id,
                            entity_type='state_individual',
                            entity_label=ind_data['label'],
                            rdf_triples=json.dumps(ind_data['triples']),
                            metadata={
                                'extraction_session': session_id,
                                'section': 'facts'
                            }
                        )
                        db.session.add(storage_entry)

                    db.session.commit()
                    logger.info(f"Stored {len(rdf_data.get('new_classes', [])) + len(rdf_data.get('new_individuals', []))} RDF entities in temporary storage")

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
            from app.services.extraction.resources import ResourcesExtractor

            extractor = ResourcesExtractor()

            # Generate the prompt for display
            extraction_prompt = extractor._get_prompt_for_preview(section_text)

            # Save the prompt to database
            from app.models import ExtractionPrompt, db
            try:
                saved_prompt = ExtractionPrompt.save_prompt(
                    case_id=case_id,
                    concept_type='resources',
                    prompt_text=extraction_prompt,
                    step_number=1,
                    llm_model=ModelConfig.get_claude_model("powerful") if llm_client else "fallback",
                    extraction_session_id=session_id
                )
                logger.info(f"Saved resources extraction prompt for case {case_id}")
            except Exception as e:
                logger.warning(f"Could not save extraction prompt: {e}")

            if USE_VERSIONED:
                with prov.track_activity(
                    activity_type='extraction',
                    activity_name='resources_individual_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='ResourcesExtractor'
                ) as activity:
                    candidates = extractor.extract(section_text, activity=activity)
            else:
                candidates = extractor.extract(section_text)

        # Store extracted entities in temporary storage for review
        logger.info(f"About to store {len(candidates) if candidates else 0} candidates in temporary storage")

        if candidates:
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

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error extracting individual {concept_type} for case {case_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
