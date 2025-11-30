"""
Step 3: Temporal Dynamics Pass for Facts Section
Shows the facts section and provides extraction for Pass 3: Actions and Events.
Based on Chapter 2 literature: Actions are volitional professional decisions (Hooker & Kim 2018) 
and Events are temporal occurrences that trigger ethical considerations (Zhang et al. 2023).
"""

import logging
import json
import uuid
from contextlib import nullcontext
from flask import render_template, request, jsonify, redirect, url_for, flash
from app.models import Document, db
from app.routes.scenario_pipeline.overview import _format_section_for_llm
from app.services.pipeline_status_service import PipelineStatusService
from app.services.extraction.enhanced_prompts_actions import EnhancedActionsExtractor, create_enhanced_actions_prompt
from app.services.extraction.enhanced_prompts_events import EnhancedEventsExtractor, create_enhanced_events_prompt
from app.services.extraction.dual_actions_events_extractor import DualActionsEventsExtractor
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.models.extraction_prompt import ExtractionPrompt
from app.services.rdf_extraction_converter import RDFExtractionConverter
from app.utils.llm_utils import get_llm_client
from models import ModelConfig

# Import provenance services
try:
    from app.services.provenance_versioning_service import get_versioned_provenance_service
    USE_VERSIONED_PROVENANCE = True
except ImportError:
    from app.services.provenance_service import get_provenance_service
    USE_VERSIONED_PROVENANCE = False

logger = logging.getLogger(__name__)

# Function to exempt specific routes from CSRF after app initialization
def init_step3_csrf_exemption(app):
    """Exempt Step 3 temporal dynamics pass routes from CSRF protection"""
    if hasattr(app, 'csrf') and app.csrf:
        # Import the route functions that actually get called
        from app.routes.scenario_pipeline.interactive_builder import behavioral_pass_prompt, behavioral_pass_execute, step3_extract, step3_extract_individual
        # Exempt the temporal pass routes from CSRF protection
        try:
            app.csrf.exempt(behavioral_pass_prompt)
            app.csrf.exempt(behavioral_pass_execute)
            app.csrf.exempt(step3_extract)
            app.csrf.exempt(step3_extract_individual)
        except:
            # Routes may not exist yet, ignore for now
            pass

def step3(case_id):
    """
    Step 3: Temporal Dynamics Pass for Facts Section
    Shows the facts section with a temporal dynamics pass button for extracting actions and events.
    """
    try:
        # Get the case
        case = Document.query.get_or_404(case_id)
        
        # Extract sections using the same logic as step2
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
        
        # Find the facts section (same logic as step2)
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
        
        # Check for saved extraction data
        saved_prompt = ExtractionPrompt.get_active_prompt(case_id, 'actions_events')

        # Get pipeline status for navigation
        pipeline_status = PipelineStatusService.get_step_status(case_id)

        # Template context
        context = {
            'case': case,
            'discussion_section': facts_section,  # Keep variable name for template compatibility
            'discussion_section_key': facts_section_key,
            'current_step': 3,
            'step_title': 'Temporal Dynamics Pass - Facts Section',
            'next_step_url': url_for('step4.step4_synthesis', case_id=case_id),
            'next_step_name': 'Whole-Case Synthesis',
            'prev_step_url': url_for('scenario_pipeline.step2b', case_id=case_id),
            'has_saved_extraction': saved_prompt is not None,
            'saved_prompt': saved_prompt.prompt_text if saved_prompt else None,
            'saved_response': saved_prompt.raw_response if saved_prompt else None,
            'saved_model': saved_prompt.llm_model if saved_prompt else None,
            'pipeline_status': pipeline_status
        }

        return render_template('scenarios/step3_dual_extraction.html', **context)
        
    except Exception as e:
        logger.error(f"Error loading step 3 for case {case_id}: {str(e)}")
        flash(f'Error loading step 3: {str(e)}', 'danger')
        return redirect(url_for('cases.view_case', id=case_id))

def behavioral_pass_prompt(case_id):
    """
    API endpoint to generate and return the LLM prompt for temporal dynamics pass before execution.
    This will extract actions and events with Pass integration context.
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
        
        logger.info(f"Generating temporal dynamics pass prompt for case {case_id}")
        
        # Use enhanced actions prompt with MCP context and Pass integration
        actions_prompt = create_enhanced_actions_prompt(
            section_text, 
            include_mcp_context=True,
            pass1_context=None,  # Will be fetched dynamically from MCP
            pass2_context=None   # Will be fetched dynamically from MCP
        )

        # Use enhanced events prompt with MCP context and Pass integration
        events_prompt = create_enhanced_events_prompt(
            section_text,
            include_mcp_context=True,
            pass1_context=None,  # Will be fetched dynamically from MCP
            pass2_context=None   # Will be fetched dynamically from MCP
        )
        
        return jsonify({
            'success': True,
            'actions_prompt': actions_prompt,
            'events_prompt': events_prompt,
            'section_length': len(section_text),
            'pass_integration': True
        })
        
    except Exception as e:
        logger.error(f"Error generating temporal dynamics pass prompt for case {case_id}: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500

def behavioral_pass_execute(case_id):
    """
    API endpoint to execute the temporal dynamics pass extraction.
    This will run the actual LLM extraction for actions and events with Pass integration.
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405
        
        # Get the case
        case = Document.query.get_or_404(case_id)
        
        # Get the facts section text (same logic as step3 view)
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
        
        logger.info(f"Executing temporal dynamics pass for case {case_id}")
        
        # Initialize LLM client
        try:
            llm_client = get_llm_client()
        except Exception as e:
            logger.warning(f"Could not initialize LLM client: {str(e)}")
            llm_client = None
        
        # Initialize provenance service with versioning if available
        if USE_VERSIONED_PROVENANCE:
            prov = get_versioned_provenance_service()
            logger.info("Using versioned provenance service for Step 3")
        else:
            from app.services.provenance_service import get_provenance_service
            prov = get_provenance_service()
            logger.info("Using standard provenance service")
        
        # Create session ID for this temporal dynamics pass
        session_id = str(uuid.uuid4())
        
        # Create context from the case
        context = {
            'case_id': case_id,
            'case_title': case.title if case else None,
            'document_type': 'ethics_case'
        }
        
        # Track versioned workflow if available
        version_context = nullcontext()
        if USE_VERSIONED_PROVENANCE:
            version_context = prov.track_versioned_workflow(
                workflow_name='step3_temporal_pass',
                description='Pass 3: Temporal dynamics extraction of Actions and Events',
                version_tag='enhanced_temporal',
                auto_version=True
            )
        
        # Use context manager for versioned workflow
        with version_context:
            # Track the main temporal dynamics pass activity
            with prov.track_activity(
                activity_type='extraction',
                activity_name='temporal_pass_step3',
                case_id=case_id,
                session_id=session_id,
                agent_type='extraction_service',
                agent_name='proethica_temporal_pass',
                execution_plan={
                    'pass_number': 3,
                    'concepts': ['actions', 'events'],
                    'strategy': 'llm_enhanced_with_pass_integration',
                    'version': 'enhanced_temporal' if USE_VERSIONED_PROVENANCE else 'standard'
                }
            ) as main_activity:
                
                # Extract actions
                with prov.track_activity(
                    activity_type='llm_query',
                    activity_name='actions_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='EnhancedActionsExtractor'
                ) as actions_activity:
                    logger.info("Extracting actions with Pass integration...")
                    actions_extractor = EnhancedActionsExtractor()
                    
                    # The extractor returns metadata for now (prompt generation)
                    # In actual LLM integration, this would return extracted candidates
                    actions_result = actions_extractor.extract_actions(
                        text=section_text,
                        include_mcp_context=True
                    )

                    # Capture the actions prompt for display
                    actions_prompt = actions_result.get('prompt', '') if isinstance(actions_result, dict) else ''

                    # Call LLM with the actions prompt
                    actions_llm_response = ""
                    action_candidates = []
                    if not actions_prompt:
                        raise Exception("No actions prompt generated")
                    if not llm_client:
                        raise Exception("LLM client not available")

                    response = llm_client.messages.create(
                        model=ModelConfig.get_claude_model("powerful"),
                        max_tokens=6000,
                        temperature=0.7,
                        messages=[{"role": "user", "content": actions_prompt}]
                    )
                    actions_llm_response = response.content[0].text if response.content else ""
                    logger.info(f"Actions LLM response length: {len(actions_llm_response)}")

                    if not actions_llm_response:
                        raise Exception("Empty response from LLM for actions")

                    # TODO: Parse the LLM response to extract action candidates
                    # For now, we'll just capture the response for display
                    # The actual parsing will be implemented separately
                    action_candidates = []

                    # Placeholder for mock actions (to be removed after implementing parser)
                    if False:  # Disabled mock data
                        mock_actions = [
                            {
                                'label': 'Disclose Conflict of Interest',
                                'description': 'Professional action to inform stakeholders about potential conflicts that could influence judgment',
                                'action_type': 'Communication',
                                'confidence': 0.9,
                                'debug': {
                                    'volitional_nature': 'Requires deliberate choice to maintain transparency',
                                    'professional_context': 'Required by NSPE Code for professional integrity',
                                    'pass_integration': {
                                        'fulfills_obligations': ['Disclosure Obligation', 'Transparency Principle'],
                                        'requires_capabilities': ['Professional Competence', 'Ethical Reasoning'],
                                        'constrained_by': ['Confidentiality Constraint', 'Legal Constraint'],
                                        'appropriate_states': ['Conflict of Interest State', 'Client Relationship']
                                    }
                                }
                            },
                            {
                                'label': 'Seek Technical Assistance',
                                'description': 'Professional action to consult with qualified experts when work exceeds competence',
                                'action_type': 'Collaboration',
                                'confidence': 0.8,
                                'debug': {
                                    'volitional_nature': 'Deliberate choice to maintain professional standards',
                                    'professional_context': 'Required when outside area of competence',
                                    'pass_integration': {
                                        'fulfills_obligations': ['Competence Obligation', 'Safety Obligation'],
                                        'requires_capabilities': ['Situational Awareness', 'Professional Competence'],
                                        'constrained_by': ['Competence Constraint', 'Resource Constraint'],
                                        'appropriate_states': ['Outside Competence', 'Public Safety at Risk']
                                    }
                                }
                            }
                        ]
                        # Convert to candidate-like objects for consistency
                        from app.services.extraction.base import ConceptCandidate
                        action_candidates = [
                            ConceptCandidate(
                                label=action['label'],
                                description=action['description'],
                                primary_type='action',
                                category=action['action_type'],
                                confidence=action['confidence'],
                                debug=action['debug']
                            ) for action in mock_actions
                        ]
                    
                    # Record extraction results
                    prov.record_extraction_results(
                        results=[{
                            'label': c.label,
                            'description': c.description,
                            'confidence': c.confidence,
                            'debug': c.debug
                        } for c in action_candidates],
                        activity=actions_activity,
                        entity_type='extracted_actions',
                        metadata={'count': len(action_candidates)}
                    )
                
                # Extract events
                with prov.track_activity(
                    activity_type='llm_query',
                    activity_name='events_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='EnhancedEventsExtractor'
                ) as events_activity:
                    logger.info("Extracting events with Pass integration...")
                    events_extractor = EnhancedEventsExtractor()
                    
                    # The extractor returns metadata for now (prompt generation)
                    events_result = events_extractor.extract_events(
                        text=section_text,
                        include_mcp_context=True
                    )

                    # Capture the events prompt for display
                    events_prompt = events_result.get('prompt', '') if isinstance(events_result, dict) else ''

                    # Call LLM with the events prompt
                    events_llm_response = ""
                    event_candidates = []
                    if not events_prompt:
                        raise Exception("No events prompt generated")
                    if not llm_client:
                        raise Exception("LLM client not available")

                    response = llm_client.messages.create(
                        model=ModelConfig.get_claude_model("powerful"),
                        max_tokens=6000,
                        temperature=0.7,
                        messages=[{"role": "user", "content": events_prompt}]
                    )
                    events_llm_response = response.content[0].text if response.content else ""
                    logger.info(f"Events LLM response length: {len(events_llm_response)}")

                    if not events_llm_response:
                        raise Exception("Empty response from LLM for events")

                    # TODO: Parse the LLM response to extract event candidates
                    # For now, we'll just capture the response for display
                    # The actual parsing will be implemented separately
                    event_candidates = []

                    # Placeholder for mock events (to be removed after implementing parser)
                    if False:  # Disabled mock data
                        mock_events = [
                            {
                                'label': 'Safety Incident Discovery',
                                'description': 'Event where potential safety hazard is identified requiring professional response',
                                'event_type': 'Discovery',
                                'confidence': 0.9,
                                'debug': {
                                    'temporal_nature': 'Occurs when inspection or analysis reveals hazards',
                                    'triggering_conditions': 'Design review, construction inspection, or operation monitoring',
                                    'ethical_significance': 'Triggers public safety obligations and disclosure requirements',
                                    'pass_integration': {
                                        'triggers_obligations': ['Safety Obligation', 'Reporting Obligation'],
                                        'changes_states': ['Public Safety at Risk', 'Crisis Conditions'],
                                        'affects_roles': ['Engineer Role', 'Public Responsibility Role'],
                                        'requires_capabilities': ['Situational Awareness', 'Ethical Reasoning']
                                    }
                                }
                            },
                            {
                                'label': 'Project Deadline Pressure',
                                'description': 'Temporal event where approaching deadlines create potential conflicts with safety',
                                'event_type': 'Project',
                                'confidence': 0.8,
                                'debug': {
                                    'temporal_nature': 'Time-dependent pressure that intensifies as deadline approaches',
                                    'triggering_conditions': 'Project schedule constraints and resource limitations',
                                    'ethical_significance': 'Creates tension between efficiency and professional obligations',
                                    'pass_integration': {
                                        'triggers_obligations': ['Safety Obligation', 'Competence Obligation'],
                                        'changes_states': ['Deadline Approaching', 'Resource Constrained'],
                                        'affects_roles': ['Professional Role', 'Employer Relationship Role'],
                                        'requires_capabilities': ['Temporal Reasoning', 'Conflict Resolution']
                                    }
                                }
                            }
                        ]
                        # Convert to candidate-like objects
                        from app.services.extraction.base import ConceptCandidate
                        event_candidates = [
                            ConceptCandidate(
                                label=event['label'],
                                description=event['description'],
                                primary_type='event',
                                category=event['event_type'],
                                confidence=event['confidence'],
                                debug=event['debug']
                            ) for event in mock_events
                        ]
                    
                    # Record extraction results
                    prov.record_extraction_results(
                        results=[{
                            'label': c.label,
                            'description': c.description,
                            'confidence': c.confidence,
                            'debug': c.debug
                        } for c in event_candidates],
                        activity=events_activity,
                        entity_type='extracted_events',
                        metadata={'count': len(event_candidates)}
                    )

                # Link sub-activities to main activity BEFORE committing
                prov.link_activities(actions_activity, main_activity, 'sequence')
                prov.link_activities(events_activity, actions_activity, 'sequence')

                # Commit provenance records
                db.session.commit()

        # Expunge all objects to prevent detached instance errors (after context managers close)
        db.session.expunge_all()

        # Convert candidates to response format
        actions = []
        for candidate in action_candidates:
            action_data = {
                "label": candidate.label,
                "description": candidate.description or "",
                "type": "action",
                "action_type": candidate.category or "GeneralAction",
                "volitional_nature": candidate.debug.get('volitional_nature', ''),
                "professional_context": candidate.debug.get('professional_context', ''),
                "pass_integration": candidate.debug.get('pass_integration', {}),
                "causal_responsibility": candidate.debug.get('causal_responsibility', ''),
                "intention_based": candidate.debug.get('intention_based', True),
                "confidence": candidate.confidence
            }
            actions.append(action_data)
        
        events = []
        for candidate in event_candidates:
            event_data = {
                "label": candidate.label,
                "description": candidate.description or "",
                "type": "event", 
                "event_type": candidate.category or "GeneralEvent",
                "temporal_nature": candidate.debug.get('temporal_nature', ''),
                "triggering_conditions": candidate.debug.get('triggering_conditions', ''),
                "ethical_significance": candidate.debug.get('ethical_significance', ''),
                "pass_integration": candidate.debug.get('pass_integration', {}),
                "causal_relationships": candidate.debug.get('causal_relationships', {}),
                "state_transitions": candidate.debug.get('state_transitions', []),
                "confidence": candidate.confidence
            }
            events.append(event_data)
        
        # Summary statistics
        summary = {
            'actions_count': len(actions),
            'events_count': len(events),
            'total_entities': len(actions) + len(events),
            'session_id': session_id,
            'version': 'enhanced_temporal' if USE_VERSIONED_PROVENANCE else 'standard',
            'pass_integration': True,
            'temporal_dynamics': True
        }
        
        # Add provenance URL if available
        if USE_VERSIONED_PROVENANCE:
            summary['provenance_url'] = url_for('provenance.provenance_viewer')
        
        # Add extraction metadata
        from datetime import datetime
        extraction_metadata = {
            'timestamp': datetime.now().isoformat(),
            'extraction_method': 'enhanced_temporal_pass3' if llm_client else 'fallback_heuristic',
            'actions_extractor': 'EnhancedActionsExtractor',
            'events_extractor': 'EnhancedEventsExtractor',
            'pass_integration_enabled': True,
            'llm_available': llm_client is not None,
            'provenance_tracked': True,
            'model_used': getattr(llm_client, 'model', 'fallback') if llm_client else 'heuristic'
        }
        
        return jsonify({
            'success': True,
            'actions': actions,
            'events': events,
            'summary': summary,
            'extraction_metadata': extraction_metadata,
            'prompts': {
                'actions_prompt': actions_prompt,
                'events_prompt': events_prompt
            },
            'llm_responses': {
                'actions_response': actions_llm_response,
                'events_response': events_llm_response
            }
        })
        
    except Exception as e:
        logger.error(f"Error executing temporal dynamics pass for case {case_id}: {str(e)}")
        # Rollback any uncommitted changes to avoid session issues
        try:
            db.session.rollback()
        except:
            pass
        return jsonify({'error': str(e), 'success': False}), 500

def step3_extract():
    """
    Direct extraction endpoint for step3 - uses dual extractor that saves to database.
    This maintains consistency with step2 naming patterns.
    """
    case_id = request.view_args.get('case_id')
    if not case_id:
        return jsonify({'error': 'Case ID required'}), 400

    return extract_individual_actions_events(case_id)

def extract_individual_actions_events(case_id):
    """
    API endpoint for individual actions & events extraction using dual extractor.

    Follows the same pattern as Step 2 individual extraction but combines
    both actions and events in a single temporal dynamics extraction.
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405

        # Get the case
        case = Document.query.get_or_404(case_id)

        # Get request data (concept_type should be 'actions_events' for combined extraction)
        data = request.get_json()
        concept_type = data.get('concept_type', 'actions_events')

        if concept_type != 'actions_events':
            return jsonify({'error': 'Only actions_events concept type supported'}), 400

        # Extract facts section using same logic as step3 view
        raw_sections = {}
        if case.doc_metadata:
            if 'sections_dual' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections_dual']
            elif 'sections' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections']
            elif 'document_structure' in case.doc_metadata and 'sections' in case.doc_metadata['document_structure']:
                raw_sections = case.doc_metadata['document_structure']['sections']

        # Find facts section
        section_text = None
        for section_key, section_content in raw_sections.items():
            if 'fact' in section_key.lower():
                section_text = _format_section_for_llm(section_key, section_content, case)
                break

        # If no facts section found, use first available section
        if not section_text and raw_sections:
            first_key = list(raw_sections.keys())[0]
            section_text = _format_section_for_llm(first_key, raw_sections[first_key], case)

        if not section_text:
            section_text = case.content or case.description or ""
            if not section_text:
                return jsonify({'error': 'No facts section found'}), 400

        logger.info(f"Extracting individual actions & events for case {case_id}")

        # Initialize the dual extractor
        extractor = DualActionsEventsExtractor()

        # Perform dual extraction
        candidate_action_classes, action_individuals, candidate_event_classes, event_individuals = extractor.extract_dual_actions_events(
            section_text, case_id, 'facts'
        )

        # Get raw response for display and RDF conversion
        raw_llm_response = extractor.get_last_raw_response()

        # Generate session ID for this extraction
        session_id = str(uuid.uuid4())

        # Save prompt and response for provenance
        extraction_prompt = extractor._create_dual_temporal_extraction_prompt(section_text, 'facts')
        ExtractionPrompt.save_prompt(
            case_id=case_id,
            concept_type='actions_events',
            prompt_text=extraction_prompt,
            raw_response=raw_llm_response,
            step_number=3,
            llm_model=ModelConfig.get_claude_model("powerful")
        )

        # Convert to RDF if we have raw response
        if raw_llm_response:
            # Parse JSON from potentially mixed text/JSON response
            try:
                raw_data = json.loads(raw_llm_response)
            except json.JSONDecodeError:
                import re
                json_match = re.search(r'\{[\s\S]*\}', raw_llm_response)
                if json_match:
                    raw_data = json.loads(json_match.group())
                else:
                    logger.warning("Could not extract JSON from LLM response")
                    raw_data = {
                        'new_action_classes': [],
                        'action_individuals': [],
                        'new_event_classes': [],
                        'event_individuals': []
                    }

            # Convert to RDF
            rdf_converter = RDFExtractionConverter()
            class_graph, individual_graph = rdf_converter.convert_actions_events_extraction_to_rdf(
                raw_data, case_id
            )

            # Store in temporary RDF storage
            rdf_data = rdf_converter.get_temporary_triples()

            # Clear any existing actions_events data for this case
            TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='actions_events',
                is_committed=False
            ).delete()

            TemporaryRDFStorage.store_extraction_results(
                case_id=case_id,
                extraction_session_id=session_id,
                extraction_type='actions_events',
                rdf_data=rdf_data,
                extraction_model='claude-opus-4-1-20250805'
            )

        # Format results for JSON response
        results = []

        # Add action classes
        for action_class in candidate_action_classes:
            results.append({
                'label': action_class.label,
                'description': action_class.definition,
                'type': 'action_class',
                'category': action_class.action_category,
                'confidence': action_class.confidence,
                'debug': {
                    'volitional_requirement': action_class.volitional_requirement,
                    'professional_context': action_class.professional_context,
                    'temporal_constraints': action_class.temporal_constraints,
                    'causal_implications': action_class.causal_implications,
                    'extraction_method': 'dual_temporal'
                }
            })

        # Add action individuals
        for individual in action_individuals:
            results.append({
                'label': individual.identifier,
                'description': f"Action performed by {individual.performed_by}",
                'type': 'action_individual',
                'category': individual.action_class,
                'confidence': individual.confidence,
                'debug': {
                    'performed_by': individual.performed_by,
                    'temporal_interval': individual.temporal_interval,
                    'causal_triggers': individual.causal_triggers,
                    'causal_results': individual.causal_results,
                    'allen_relations': individual.allen_relations,
                    'extraction_method': 'dual_temporal'
                }
            })

        # Add event classes
        for event_class in candidate_event_classes:
            results.append({
                'label': event_class.label,
                'description': event_class.definition,
                'type': 'event_class',
                'category': event_class.event_category,
                'confidence': event_class.confidence,
                'debug': {
                    'temporal_marker': event_class.temporal_marker,
                    'automatic_nature': event_class.automatic_nature,
                    'constraint_activation': event_class.constraint_activation,
                    'obligation_transformation': event_class.obligation_transformation,
                    'extraction_method': 'dual_temporal'
                }
            })

        # Add event individuals
        for individual in event_individuals:
            results.append({
                'label': individual.identifier,
                'description': f"Event that occurred to {individual.occurred_to or 'entity'}",
                'type': 'event_individual',
                'category': individual.event_class,
                'confidence': individual.confidence,
                'debug': {
                    'occurred_to': individual.occurred_to,
                    'discovered_by': individual.discovered_by,
                    'temporal_interval': individual.temporal_interval,
                    'causal_triggers': individual.causal_triggers,
                    'causal_results': individual.causal_results,
                    'allen_relations': individual.allen_relations,
                    'extraction_method': 'dual_temporal'
                }
            })

        # Response data
        response_data = {
            'success': True,
            'concepts': results,
            'prompt': extraction_prompt,
            'raw_response': raw_llm_response,
            'metadata': {
                'extraction_method': 'dual_temporal',
                'model_used': ModelConfig.get_claude_model("powerful"),
                'session_id': session_id,
                'concept_counts': {
                    'action_classes': len(candidate_action_classes),
                    'action_individuals': len(action_individuals),
                    'event_classes': len(candidate_event_classes),
                    'event_individuals': len(event_individuals),
                    'total': len(results)
                },
                'temporal_relationships': True,
                'allen_algebra': True
            }
        }

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error in individual actions/events extraction for case {case_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'concepts': [],
            'prompt': '',
            'raw_response': '',
            'metadata': {'extraction_method': 'dual_temporal_failed'}
        }), 500

def step3_get_saved_prompt(case_id):
    """
    API endpoint to get saved extraction prompt and raw response for Step 3.
    """
    from flask import request, jsonify
    from app.models import ExtractionPrompt
    try:
        concept_type = request.args.get('concept_type', 'actions_events')

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
        logger.error(f"Error getting saved prompt for case {case_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
