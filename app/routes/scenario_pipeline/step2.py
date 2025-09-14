"""
Step 2: Normative Requirements Pass for Facts Section
Shows the facts section and provides extraction for Pass 2: Principles, Obligations, Constraints, and Capabilities.
Based on Chapter 2 literature: Capabilities are essential for norm competence (Tolmeijer et al. 2021) - 
agents need capabilities to store, recognize, apply, and resolve normative requirements.
"""

import logging
import json
import uuid
from contextlib import nullcontext
from flask import render_template, request, jsonify, redirect, url_for, flash
from app.models import Document, db
from app.routes.scenario_pipeline.overview import _format_section_for_llm
from app.services.extraction.enhanced_prompts_principles import EnhancedPrinciplesExtractor, create_enhanced_principles_prompt
from app.services.extraction.enhanced_prompts_obligations import EnhancedObligationsExtractor, create_enhanced_obligations_prompt
from app.services.extraction.enhanced_prompts_constraints import EnhancedConstraintsExtractor, create_enhanced_constraints_prompt
from app.services.extraction.enhanced_prompts_states_capabilities import EnhancedCapabilitiesExtractor, create_enhanced_capabilities_prompt
from app.utils.llm_utils import get_llm_client

# Import provenance services
try:
    from app.services.provenance_versioning_service import get_versioned_provenance_service
    USE_VERSIONED_PROVENANCE = True
except ImportError:
    from app.services.provenance_service import get_provenance_service
    USE_VERSIONED_PROVENANCE = False

logger = logging.getLogger(__name__)

# Function to exempt specific routes from CSRF after app initialization
def init_step2_csrf_exemption(app):
    """Exempt Step 2 normative pass routes from CSRF protection"""
    if hasattr(app, 'csrf') and app.csrf:
        # Import the route functions that actually get called
        from app.routes.scenario_pipeline.interactive_builder import normative_pass_prompt, normative_pass_execute, step2_extract
        # Exempt the normative pass routes from CSRF protection
        app.csrf.exempt(normative_pass_prompt)
        app.csrf.exempt(normative_pass_execute)
        app.csrf.exempt(step2_extract)

def step2(case_id):
    """
    Step 2: Normative Pass for Facts Section
    Shows the facts section with a normative pass button for extracting principles, obligations, and constraints.
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
        
        # Find the facts section (same as step1)
        facts_section = None
        facts_section_key = None
        
        # Look for facts section (case insensitive)
        for section_key, section_content in raw_sections.items():
            if 'fact' in section_key.lower():
                facts_section_key = section_key
                facts_section = _format_section_for_llm(section_key, section_content, case_doc=case)
                break
        
        # If no facts section found, use first available section
        if not facts_section and raw_sections:
            first_key = list(raw_sections.keys())[0]
            facts_section_key = first_key
            facts_section = _format_section_for_llm(first_key, raw_sections[first_key], case_doc=case)
        
        # Template context
        context = {
            'case': case,
            'discussion_section': facts_section,  # Keep variable name for template compatibility
            'discussion_section_key': facts_section_key,
            'current_step': 2,
            'step_title': 'Normative Pass - Facts Section',
            'next_step_url': url_for('scenario_pipeline.step3', case_id=case_id),
            'prev_step_url': url_for('scenario_pipeline.step1', case_id=case_id)
        }
        
        return render_template('scenarios/step2.html', **context)
        
    except Exception as e:
        logger.error(f"Error loading step 2 for case {case_id}: {str(e)}")
        flash(f'Error loading step 2: {str(e)}', 'danger')
        return redirect(url_for('cases.view_case', id=case_id))

def normative_pass_prompt(case_id):
    """
    API endpoint to generate and return the LLM prompt for normative pass before execution.
    This will extract principles, obligations, and constraints.
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
        
        logger.info(f"Generating normative pass prompt for case {case_id}")
        
        # Use enhanced principles prompt from Chapter 2 literature with MCP context
        # MCP will be fetched dynamically from the external server
        principles_prompt = create_enhanced_principles_prompt(section_text, include_mcp_context=True)

        # Use enhanced obligations prompt with MCP context
        obligations_prompt = create_enhanced_obligations_prompt(section_text, include_mcp_context=True)

        # Use enhanced constraints prompt with MCP context - retrieves 17 constraints via recursive CTE
        constraints_prompt = create_enhanced_constraints_prompt(section_text, include_mcp_context=True)
        
        # Use enhanced capabilities prompt with MCP context - retrieves capability types via recursive CTE
        capabilities_prompt = create_enhanced_capabilities_prompt(section_text, include_mcp_context=True)
        
        return jsonify({
            'success': True,
            'principles_prompt': principles_prompt,
            'obligations_prompt': obligations_prompt,
            'constraints_prompt': constraints_prompt,
            'capabilities_prompt': capabilities_prompt,
            'section_length': len(section_text)
        })
        
    except Exception as e:
        logger.error(f"Error generating normative pass prompt for case {case_id}: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500

def normative_pass_execute(case_id):
    """
    API endpoint to execute the normative pass extraction.
    This will run the actual LLM extraction for principles, obligations, and constraints.
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405
        
        # Get the case
        case = Document.query.get_or_404(case_id)
        
        # Get the facts section text (same logic as step2 view)
        section_text = None
        raw_sections = {}
        
        if case.doc_metadata:
            # Get sections from metadata
            if 'sections_dual' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections_dual']
            elif 'sections' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections']
            elif 'document_structure' in case.doc_metadata and 'sections' in case.doc_metadata['document_structure']:
                raw_sections = case.doc_metadata['document_structure']['sections']
        
        # Look for facts section
        for section_key, section_content in raw_sections.items():
            if 'fact' in section_key.lower():
                section_text = _format_section_for_llm(section_key, section_content, case)
                break
        
        # If no facts section found, use first available section
        if not section_text and raw_sections:
            first_key = list(raw_sections.keys())[0]
            section_text = _format_section_for_llm(first_key, raw_sections[first_key], case)
        
        if not section_text:
            # Fallback to using available content
            section_text = case.content or case.description or ""
            if not section_text:
                return jsonify({'error': 'No facts section found'}), 400
        
        logger.info(f"Executing normative pass for case {case_id}")
        
        # Initialize enhanced extractors with LLM client
        try:
            llm_client = get_llm_client()
        except Exception as e:
            logger.warning(f"Could not initialize LLM client: {str(e)}")
            llm_client = None
        
        # Initialize provenance service with versioning if available
        if USE_VERSIONED_PROVENANCE:
            prov = get_versioned_provenance_service()
            logger.info("Using versioned provenance service for Step 2")
        else:
            from app.services.provenance_service import get_provenance_service
            prov = get_provenance_service()
            logger.info("Using standard provenance service")
        
        # Create session ID for this normative pass
        session_id = str(uuid.uuid4())
        
        # Create context from the case we already have
        context = {
            'case_id': case_id,
            'case_title': case.title if case else None,
            'document_type': 'ethics_case'
        }
        
        # Track versioned workflow if available
        version_context = nullcontext()
        if USE_VERSIONED_PROVENANCE:
            version_context = prov.track_versioned_workflow(
                workflow_name='step2_normative_pass',
                description='Pass 2: Normative extraction of Principles, Obligations, and Constraints',
                version_tag='enhanced_normative',
                auto_version=True
            )
        
        # Use context manager for versioned workflow
        with version_context:
            # Track the main normative pass activity
            with prov.track_activity(
                activity_type='extraction',
                activity_name='normative_pass_step2',
                case_id=case_id,
                session_id=session_id,
                agent_type='extraction_service',
                agent_name='proethica_normative_pass',
                execution_plan={
                    'pass_number': 2,
                    'concepts': ['principles', 'obligations', 'constraints'],
                    'strategy': 'llm_enhanced',
                    'version': 'enhanced_normative' if USE_VERSIONED_PROVENANCE else 'standard'
                }
            ) as main_activity:
                
                # Extract principles
                with prov.track_activity(
                    activity_type='llm_query',
                    activity_name='principles_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='EnhancedPrinciplesExtractor'
                ) as principles_activity:
                    logger.info("Extracting principles with provenance tracking...")
                    principles_extractor = EnhancedPrinciplesExtractor(
                        llm_client=llm_client,
                        provenance_service=prov
                    )
                    principle_candidates = principles_extractor.extract(
                        section_text, 
                        context=context,
                        activity=principles_activity
                    )
                    
                    # Record extraction results
                    prov.record_extraction_results(
                        results=[{
                            'label': c.label,
                            'description': c.description,
                            'confidence': c.confidence,
                            'debug': c.debug
                        } for c in principle_candidates],
                        activity=principles_activity,
                        entity_type='extracted_principles',
                        metadata={'count': len(principle_candidates)}
                    )
                
                # Extract obligations
                with prov.track_activity(
                    activity_type='llm_query',
                    activity_name='obligations_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='EnhancedObligationsExtractor'
                ) as obligations_activity:
                    logger.info("Extracting obligations with provenance tracking...")
                    obligations_extractor = EnhancedObligationsExtractor(
                        llm_client=llm_client,
                        provenance_service=prov
                    )
                    obligation_candidates = obligations_extractor.extract(
                        section_text,
                        context=context,
                        activity=obligations_activity
                    )
                    
                    # Record extraction results
                    prov.record_extraction_results(
                        results=[{
                            'label': c.label,
                            'description': c.description,
                            'confidence': c.confidence,
                            'debug': c.debug
                        } for c in obligation_candidates],
                        activity=obligations_activity,
                        entity_type='extracted_obligations',
                        metadata={'count': len(obligation_candidates)}
                    )
                
                # Extract constraints
                with prov.track_activity(
                    activity_type='llm_query',
                    activity_name='constraints_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='EnhancedConstraintsExtractor'
                ) as constraints_activity:
                    logger.info("Extracting constraints with provenance tracking...")
                    constraints_extractor = EnhancedConstraintsExtractor(
                        llm_client=llm_client,
                        provenance_service=prov
                    )
                    constraint_candidates = constraints_extractor.extract(
                        section_text,
                        context=context,
                        activity=constraints_activity
                    )
                    
                    # Record extraction results
                    prov.record_extraction_results(
                        results=[{
                            'label': c.label,
                            'description': c.description,
                            'confidence': c.confidence,
                            'debug': c.debug
                        } for c in constraint_candidates],
                        activity=constraints_activity,
                        entity_type='extracted_constraints',
                        metadata={'count': len(constraint_candidates)}
                    )
                
                # Track capabilities extraction as a sub-activity (Part of Pass 2: Normative Requirements)
                with prov.track_activity(
                    activity_type='llm_query',
                    activity_name='capabilities_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='EnhancedCapabilitiesExtractor'
                ) as capabilities_activity:
                    logger.info("Extracting capabilities with enhanced extractor...")
                    capabilities_extractor = EnhancedCapabilitiesExtractor(
                        llm_client=llm_client,
                        provenance_service=prov
                    )
                    capability_candidates = capabilities_extractor.extract(
                        section_text,
                        context=context,
                        activity=capabilities_activity
                    )
                    
                    # Record extraction results
                    prov.record_extraction_results(
                        results=[{
                            'label': c.label,
                            'description': c.description,
                            'confidence': c.confidence,
                            'debug': c.debug
                        } for c in capability_candidates],
                        activity=capabilities_activity,
                        entity_type='extracted_capabilities',
                        metadata={'count': len(capability_candidates)}
                    )
                
                # Link sub-activities to main activity
                prov.link_activities(principles_activity, main_activity, 'sequence')
                prov.link_activities(obligations_activity, principles_activity, 'sequence')
                prov.link_activities(constraints_activity, obligations_activity, 'sequence')
                prov.link_activities(capabilities_activity, constraints_activity, 'sequence')
        
        # Commit provenance records
        db.session.commit()
        
        # Convert candidates to response format
        principles = []
        for candidate in principle_candidates:
            principle_data = {
                "label": candidate.label,
                "description": candidate.description or "",
                "type": "principle",
                "principle_category": candidate.debug.get('principle_category', 'professional'),
                "abstraction_level": candidate.debug.get('abstraction_level', 'high'),
                "requires_interpretation": candidate.debug.get('requires_interpretation', True),
                "potential_conflicts": candidate.debug.get('potential_conflicts', []),
                "extensional_examples": candidate.debug.get('extensional_examples', []),
                "derived_obligations": candidate.debug.get('derived_obligations', []),
                "scholarly_grounding": candidate.debug.get('scholarly_grounding', ''),
                "confidence": candidate.confidence
            }
            principles.append(principle_data)
        
        obligations = []
        for candidate in obligation_candidates:
            obligation_data = {
                "label": candidate.label,
                "description": candidate.description or "",
                "type": "obligation",
                "obligation_type": candidate.debug.get('obligation_type', 'professional_practice'),
                "enforcement_level": candidate.debug.get('enforcement_level', 'mandatory'),
                "derived_from_principle": candidate.debug.get('derived_from_principle', ''),
                "stakeholders_affected": candidate.debug.get('stakeholders_affected', []),
                "potential_conflicts": candidate.debug.get('potential_conflicts', []),
                "monitoring_criteria": candidate.debug.get('monitoring_criteria', ''),
                "nspe_reference": candidate.debug.get('nspe_reference', ''),
                "contextual_factors": candidate.debug.get('contextual_factors', ''),
                "confidence": candidate.confidence
            }
            obligations.append(obligation_data)
        
        constraints = []
        for candidate in constraint_candidates:
            constraint_data = {
                "label": candidate.label,
                "description": candidate.description or "",
                "type": "constraint",
                "constraint_category": candidate.debug.get('constraint_category', 'resource'),
                "flexibility": candidate.debug.get('flexibility', 'non-negotiable'),
                "impact_on_decisions": candidate.debug.get('impact_on_decisions', ''),
                "affected_stakeholders": candidate.debug.get('affected_stakeholders', []),
                "potential_violations": candidate.debug.get('potential_violations', ''),
                "mitigation_strategies": candidate.debug.get('mitigation_strategies', []),
                "temporal_aspect": candidate.debug.get('temporal_aspect', 'permanent'),
                "quantifiable_metrics": candidate.debug.get('quantifiable_metrics', ''),
                "confidence": candidate.confidence
            }
            constraints.append(constraint_data)
        
        capabilities = []
        for candidate in capability_candidates:
            capability_data = {
                "label": candidate.label,
                "description": candidate.description or "",
                "type": "capability",
                "capability_category": candidate.debug.get('capability_category', 'TechnicalCapability'),
                "ethical_relevance": candidate.debug.get('ethical_relevance', ''),
                "required_for_roles": candidate.debug.get('required_for_roles', []),
                "enables_obligations": candidate.debug.get('enables_obligations', []),
                "theoretical_grounding": candidate.debug.get('theoretical_grounding', ''),
                "development_path": candidate.debug.get('development_path', ''),
                "confidence": candidate.confidence
            }
            capabilities.append(capability_data)
        
        # Summary statistics
        summary = {
            'principles_count': len(principles),
            'obligations_count': len(obligations),
            'constraints_count': len(constraints),
            'capabilities_count': len(capabilities),
            'total_entities': len(principles) + len(obligations) + len(constraints) + len(capabilities),
            'session_id': session_id,
            'version': 'enhanced_normative' if USE_VERSIONED_PROVENANCE else 'standard'
        }
        
        # Add provenance URL if available
        if USE_VERSIONED_PROVENANCE:
            summary['provenance_url'] = url_for('provenance.provenance_viewer')
        
        # Add extraction metadata
        from datetime import datetime
        extraction_metadata = {
            'timestamp': datetime.now().isoformat(),
            'extraction_method': 'enhanced_chapter2' if llm_client else 'fallback_heuristic',
            'principles_extractor': 'EnhancedPrinciplesExtractor',
            'obligations_extractor': 'placeholder',  # Will be updated when we implement enhanced obligations
            'constraints_extractor': 'placeholder',  # Will be updated when we implement enhanced constraints
            'llm_available': llm_client is not None,
            'provenance_tracked': True,
            'model_used': getattr(llm_client, 'model', 'fallback') if llm_client else 'heuristic'
        }
        
        return jsonify({
            'success': True,
            'principles': principles,
            'obligations': obligations,
            'constraints': constraints,
            'capabilities': capabilities,
            'summary': summary,
            'extraction_metadata': extraction_metadata
        })
        
    except Exception as e:
        logger.error(f"Error executing normative pass for case {case_id}: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500
