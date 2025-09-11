"""
Step 1a: Entities Pass for Facts Section
Shows the facts section and provides an entities pass button that extracts roles and resources.
"""

import logging
from flask import render_template, request, jsonify, redirect, url_for, flash
from app.models import Document
from app.routes.scenario_pipeline.step1 import _format_section_for_llm

logger = logging.getLogger(__name__)

# Function to exempt specific routes from CSRF after app initialization
def init_step1a_csrf_exemption(app):
    """Exempt Step 1a entities pass routes from CSRF protection"""
    if hasattr(app, 'csrf') and app.csrf:
        # Import the route functions that actually get called
        from app.routes.scenario_pipeline.interactive_builder import entities_pass_prompt, entities_pass_execute
        # Exempt the entities pass routes from CSRF protection
        app.csrf.exempt(entities_pass_prompt)
        app.csrf.exempt(entities_pass_execute)

def step1a(case_id):
    """
    Step 1a: Entities Pass for Facts Section
    Shows the facts section with an entities pass button for extracting roles and resources.
    """
    try:
        # Get the case
        case = Document.query.get_or_404(case_id)
        
        # Extract sections using the same logic as step1
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
        
        # Template context
        context = {
            'case': case,
            'facts_section': facts_section,
            'facts_section_key': facts_section_key,
            'current_step': 1.5,  # Use numeric value that can be compared with integers (1 < 1.5 < 2)
            'step_title': 'Entities Pass - Facts Section',
            'next_step_url': url_for('scenario_pipeline.step2', case_id=case_id),  # Go to Step 2
            'prev_step_url': url_for('scenario_pipeline.step1', case_id=case_id)
        }
        
        return render_template('scenarios/step1a.html', **context)
        
    except Exception as e:
        logger.error(f"Error loading step 1a for case {case_id}: {str(e)}")
        flash(f'Error loading step 1a: {str(e)}', 'danger')
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
        
        # Create extractors to generate the actual prompts that will be used
        roles_extractor = RolesExtractor()
        resources_extractor = ResourcesExtractor()
        
        # Get the actual prompts that will be sent to the LLM (with MCP context if enabled)
        roles_prompt = roles_extractor._get_prompt_for_preview(section_text)
        resources_prompt = resources_extractor._get_prompt_for_preview(section_text)
        
        return jsonify({
            'success': True,
            'roles_prompt': roles_prompt,
            'resources_prompt': resources_prompt,
            'combined_prompt': f"ROLES EXTRACTION:\n{roles_prompt}\n\n---\n\nRESOURCES EXTRACTION:\n{resources_prompt}",
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
        from app.services.provenance_service import get_provenance_service
        from app.models import db
        import uuid
        
        # Initialize provenance service
        prov = get_provenance_service()
        
        # Create a session ID for this extraction workflow
        session_id = str(uuid.uuid4())
        
        # Initialize extractors
        roles_extractor = RolesExtractor()
        resources_extractor = ResourcesExtractor()
        
        # Track the overall entities pass activity
        with prov.track_activity(
            activity_type='extraction',
            activity_name='entities_pass_step1a',
            case_id=case_id,
            session_id=session_id,
            agent_type='extraction_service',
            agent_name='proethica_entities_pass',
            execution_plan={
                'section_length': len(section_text),
                'extraction_types': ['roles', 'resources']
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
            
            # Link the sub-activities to the main activity
            prov.link_activities(roles_activity, main_activity, 'sequence')
            prov.link_activities(resources_activity, roles_activity, 'sequence')
        
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
        
        logger.info(f"Entities pass completed for case {case_id}: {len(roles_data)} roles, {len(resources_data)} resources")
        
        return jsonify({
            'success': True,
            'roles': roles_data,
            'resources': resources_data,
            'summary': {
                'roles_count': len(roles_data),
                'resources_count': len(resources_data),
                'total_entities': len(roles_data) + len(resources_data)
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

