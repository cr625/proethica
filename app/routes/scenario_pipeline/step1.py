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
            'prev_step_url': url_for('scenario_pipeline.overview', case_id=case_id)
        }
        
        # Use extended template with both Facts and Discussion sections
        return render_template('scenarios/step1.html', **context)

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
        from app.services.extraction.roles import RolesExtractor
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
        
        # Initialize extractors (Pass 1: Contextual Framework - Roles, States, Resources)
        roles_extractor = RolesExtractor()
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
                
                # Track roles extraction as a sub-activity
                with prov.track_activity(
                    activity_type='llm_query',
                    activity_name='roles_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='RolesExtractor'
                ) as roles_activity:
                    logger.info("Extracting roles with provenance tracking...")
                    role_candidates = roles_extractor.extract(
                        section_text, 
                        guideline_id=case_id,
                        activity=roles_activity
                    )
                    
                    # Record the extraction results
                    roles_results_entity = prov.record_extraction_results(
                        results=[{
                            'label': c.label,
                            'description': c.description,
                            'confidence': c.confidence,
                            'debug': c.debug
                        } for c in role_candidates],
                        activity=roles_activity,
                        entity_type='extracted_roles',
                        metadata={'count': len(role_candidates)}
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
        
        # Convert candidates to serializable format with ALL enhanced fields
        roles_data = []
        for candidate in role_candidates:
            # Extract enhanced fields from debug for easier access
            debug_data = candidate.debug or {}
            role_entry = {
                'label': candidate.label,
                'description': candidate.description,
                'type': candidate.primary_type,
                'confidence': candidate.confidence,
                # Enhanced fields from new prompts
                'role_category': debug_data.get('role_category'),  # provider_client, professional_peer, etc.
                'obligations_generated': debug_data.get('obligations_generated', []),
                'ethical_filter_function': debug_data.get('ethical_filter_function'),
                'theoretical_grounding': debug_data.get('theoretical_grounding'),
                'text_references': debug_data.get('text_references', []),
                'is_existing': debug_data.get('is_existing'),
                'ontology_match_reasoning': debug_data.get('ontology_match_reasoning'),
                # Preserve all debug info for complete data
                'debug': candidate.debug
            }
            roles_data.append(role_entry)
        
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
        
        logger.info(f"Entities pass completed for case {case_id}: {len(roles_data)} roles, {len(states_data)} states, {len(resources_data)} resources")
        
        return jsonify({
            'success': True,
            'roles': roles_data,
            'states': states_data,
            'resources': resources_data,
            'summary': {
                'roles_count': len(roles_data),
                'states_count': len(states_data),
                'resources_count': len(resources_data),
                'total_entities': len(roles_data) + len(states_data) + len(resources_data)
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
        from app.models import ModelConfig, db
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
            from app.services.extraction.roles import RolesExtractor
            from app.services.extraction.enhanced_prompts_roles import create_enhanced_roles_prompt

            extractor = RolesExtractor(provenance_service=prov)

            # Generate the prompt for display
            extraction_prompt = create_enhanced_roles_prompt(section_text, include_mcp_context=True)

            # Track activity if using versioned provenance
            if USE_VERSIONED:
                with prov.track_activity(
                    activity_type='extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='RolesExtractor'
                ) as activity:
                    candidates = extractor.extract(section_text, context=context, activity=activity)
            else:
                candidates = extractor.extract(section_text, context=context)

        elif concept_type == 'states':
            from app.services.extraction.enhanced_prompts_states_capabilities import EnhancedStatesExtractor, create_enhanced_states_prompt
            from app.services.external_mcp_client import get_external_mcp_client

            # Get existing states from MCP for context
            existing_states = None
            try:
                external_client = get_external_mcp_client()
                existing_states = external_client.get_all_state_entities()
                logger.info(f"Retrieved {len(existing_states)} existing states from MCP")
            except Exception as e:
                logger.warning(f"Could not retrieve existing states from MCP: {e}")

            # Generate prompt with MCP context
            extraction_prompt = create_enhanced_states_prompt(
                section_text,
                include_ontology_context=True,
                existing_states=existing_states
            )

            extractor = EnhancedStatesExtractor(llm_client=llm_client, provenance_service=prov)

            if USE_VERSIONED:
                with prov.track_activity(
                    activity_type='extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='EnhancedStatesExtractor'
                ) as activity:
                    candidates = extractor.extract(section_text, context=context, activity=activity)
            else:
                candidates = extractor.extract(section_text, context=context)

        elif concept_type == 'resources':
            from app.services.extraction.resources import ResourcesExtractor
            from app.services.extraction.enhanced_prompts_resources import create_enhanced_resources_prompt

            extractor = ResourcesExtractor(provenance_service=prov)

            # Generate the prompt for display
            extraction_prompt = create_enhanced_resources_prompt(section_text, include_mcp_context=True)

            if USE_VERSIONED:
                with prov.track_activity(
                    activity_type='extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='ResourcesExtractor'
                ) as activity:
                    candidates = extractor.extract(section_text, context=context, activity=activity)
            else:
                candidates = extractor.extract(section_text, context=context)

        # Format results
        results = []
        for candidate in candidates:
            result = {
                'label': candidate.label,
                'description': candidate.description,
                'type': candidate.primary_type,
                'confidence': candidate.confidence
            }

            # Add any debug info
            if hasattr(candidate, 'debug') and candidate.debug:
                for key, value in candidate.debug.items():
                    if key not in result:
                        result[key] = value

            results.append(result)

        # Determine model used
        model_used = ModelConfig.get_claude_model("powerful") if llm_client else "fallback"

        return jsonify({
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
        })

    except Exception as e:
        logger.error(f"Error extracting individual {concept_type} for case {case_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
