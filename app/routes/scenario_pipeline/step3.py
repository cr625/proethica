"""
Step 3: Behavioral Pass for Facts Section
Shows the facts section and provides a behavioral pass button that extracts states, actions, events, and capabilities.
"""

import logging
import json
import uuid
from contextlib import nullcontext
from flask import render_template, request, jsonify, redirect, url_for, flash
from app.models import Document, db
from app.routes.scenario_pipeline.overview import _format_section_for_llm
from app.utils.llm_utils import get_llm_client

# Import enhanced behavioral extractors
from app.services.extraction.enhanced_prompts_states_capabilities import (
    EnhancedStatesExtractor,
    EnhancedCapabilitiesExtractor
)
from app.services.extraction.enhanced_prompts_actions_events import (
    EnhancedActionsExtractor,
    EnhancedEventsExtractor
)

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
    """Exempt Step 3 behavioral pass routes from CSRF protection"""
    if hasattr(app, 'csrf') and app.csrf:
        # Import the route functions that actually get called
        from app.routes.scenario_pipeline.interactive_builder import behavioral_pass_prompt, behavioral_pass_execute, step3_extract
        # Exempt the behavioral pass routes from CSRF protection
        app.csrf.exempt(behavioral_pass_prompt)
        app.csrf.exempt(behavioral_pass_execute)
        app.csrf.exempt(step3_extract)

def step3(case_id):
    """
    Step 3: Behavioral Pass for Facts Section
    Shows the facts section with a behavioral pass button for extracting states, actions, events, and capabilities.
    """
    try:
        # Get the case
        case = Document.query.get_or_404(case_id)
        
        # Extract sections using the same logic as step1 and step2
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
        
        # Find the facts section (same as step1 and step2)
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
            'facts_section': facts_section,
            'facts_section_key': facts_section_key,
            'current_step': 3,
            'step_title': 'Behavioral Pass - Facts Section',
            'next_step_url': '#',  # Future: step4 (Discussion section)
            'prev_step_url': url_for('scenario_pipeline.step2', case_id=case_id)
        }
        
        return render_template('scenarios/step3.html', **context)
        
    except Exception as e:
        logger.error(f"Error loading step 3 for case {case_id}: {str(e)}")
        flash(f'Error loading step 3: {str(e)}', 'danger')
        return redirect(url_for('cases.view_case', id=case_id))

def behavioral_pass_prompt(case_id):
    """
    API endpoint to generate and return the LLM prompt for behavioral pass before execution.
    This will extract states, actions, events, and capabilities.
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
        
        logger.info(f"Generating behavioral pass prompt for case {case_id}")
        
        # Create prompts for behavioral concepts
        states_prompt = f"""Extract states and conditions from the following facts text.

Focus on:
- Current states of the system or agents
- Conditions that must be met
- States that trigger obligations or constraints
- Environmental or contextual states

Text:
{section_text[:500]}...

Return as JSON array of state objects."""

        actions_prompt = f"""Extract actions and behaviors from the following facts text.

Focus on:
- Actions taken or to be taken
- Decisions made or to be made
- Professional practices and procedures
- Interventions or responses

Text:
{section_text[:500]}...

Return as JSON array of action objects."""

        events_prompt = f"""Extract events and occurrences from the following facts text.

Focus on:
- Significant events that occurred
- Triggering events for obligations
- Milestone events
- Incidents or accidents

Text:
{section_text[:500]}...

Return as JSON array of event objects."""

        capabilities_prompt = f"""Extract capabilities and competencies from the following facts text.

Focus on:
- Technical skills and expertise
- Professional qualifications
- System capabilities
- Organizational capacities

Text:
{section_text[:500]}...

Return as JSON array of capability objects."""
        
        return jsonify({
            'success': True,
            'states_prompt': states_prompt,
            'actions_prompt': actions_prompt,
            'events_prompt': events_prompt,
            'capabilities_prompt': capabilities_prompt,
            'section_length': len(section_text)
        })
        
    except Exception as e:
        logger.error(f"Error generating behavioral pass prompt for case {case_id}: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500

def behavioral_pass_execute(case_id):
    """
    API endpoint to execute the behavioral pass extraction.
    This will run the actual LLM extraction for states, actions, events, and capabilities.
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
        
        # Ensure section_text is a dict with 'llm_text' key
        if isinstance(section_text, dict) and 'llm_text' in section_text:
            text_for_extraction = section_text['llm_text']
        else:
            text_for_extraction = str(section_text)
        
        logger.info(f"Executing behavioral pass for case {case_id}")
        
        # Initialize extractors
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
        
        # Create session ID for this behavioral pass
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
                workflow_name='step3_behavioral_pass',
                description='Pass 3: Behavioral extraction of States, Actions, Events, and Capabilities',
                version_tag='behavioral_v1',
                auto_version=True
            )
        
        # Use context manager for versioned workflow
        with version_context:
            # Track the main behavioral pass activity
            with prov.track_activity(
                activity_type='extraction',
                activity_name='behavioral_pass_step3',
                case_id=case_id,
                session_id=session_id,
                agent_type='extraction_service',
                agent_name='proethica_behavioral_pass',
                execution_plan={
                    'pass_number': 3,
                    'concepts': ['states', 'actions', 'events', 'capabilities'],
                    'strategy': 'standard',
                    'version': 'behavioral_v1' if USE_VERSIONED_PROVENANCE else 'standard'
                }
            ) as main_activity:
                
                # Extract states
                with prov.track_activity(
                    activity_type='llm_query',
                    activity_name='states_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='StatesExtractor'
                ) as states_activity:
                    logger.info("Extracting states with provenance tracking...")
                    states_extractor = EnhancedStatesExtractor(llm_client=llm_client, provenance_service=prov)
                    state_candidates = states_extractor.extract(text_for_extraction, context=context, activity=states_activity)
                    
                    # Record extraction results
                    prov.record_extraction_results(
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
                
                # Extract actions
                with prov.track_activity(
                    activity_type='llm_query',
                    activity_name='actions_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='ActionsExtractor'
                ) as actions_activity:
                    logger.info("Extracting actions with provenance tracking...")
                    actions_extractor = EnhancedActionsExtractor(llm_client=llm_client, provenance_service=prov)
                    action_candidates = actions_extractor.extract(text_for_extraction, context=context, activity=actions_activity)
                    
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
                    agent_name='EventsExtractor'
                ) as events_activity:
                    logger.info("Extracting events with provenance tracking...")
                    events_extractor = EnhancedEventsExtractor(llm_client=llm_client, provenance_service=prov)
                    event_candidates = events_extractor.extract(text_for_extraction, context=context, activity=events_activity)
                    
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
                
                # Extract capabilities
                with prov.track_activity(
                    activity_type='llm_query',
                    activity_name='capabilities_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='CapabilitiesExtractor'
                ) as capabilities_activity:
                    logger.info("Extracting capabilities with provenance tracking...")
                    capabilities_extractor = EnhancedCapabilitiesExtractor(llm_client=llm_client, provenance_service=prov)
                    capability_candidates = capabilities_extractor.extract(text_for_extraction, context=context, activity=capabilities_activity)
                    
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
                prov.link_activities(states_activity, main_activity, 'sequence')
                prov.link_activities(actions_activity, states_activity, 'sequence')
                prov.link_activities(events_activity, actions_activity, 'sequence')
                prov.link_activities(capabilities_activity, events_activity, 'sequence')
        
        # Commit provenance records
        db.session.commit()
        
        # Convert candidates to response format
        states = []
        for candidate in state_candidates:
            state_data = {
                "label": candidate.label,
                "description": candidate.description or "",
                "type": "state",
                "state_type": candidate.debug.get('state_type', 'condition'),
                "triggers": candidate.debug.get('triggers', []),
                "duration": candidate.debug.get('duration', 'persistent'),
                "affected_entities": candidate.debug.get('affected_entities', []),
                "confidence": candidate.confidence
            }
            states.append(state_data)
        
        actions = []
        for candidate in action_candidates:
            action_data = {
                "label": candidate.label,
                "description": candidate.description or "",
                "type": "action",
                "action_type": candidate.debug.get('action_type', 'professional_practice'),
                "actor": candidate.debug.get('actor', ''),
                "target": candidate.debug.get('target', ''),
                "preconditions": candidate.debug.get('preconditions', []),
                "effects": candidate.debug.get('effects', []),
                "confidence": candidate.confidence
            }
            actions.append(action_data)
        
        events = []
        for candidate in event_candidates:
            event_data = {
                "label": candidate.label,
                "description": candidate.description or "",
                "type": "event",
                "event_type": candidate.debug.get('event_type', 'occurrence'),
                "temporal_marker": candidate.debug.get('temporal_marker', ''),
                "participants": candidate.debug.get('participants', []),
                "consequences": candidate.debug.get('consequences', []),
                "confidence": candidate.confidence
            }
            events.append(event_data)
        
        capabilities = []
        for candidate in capability_candidates:
            capability_data = {
                "label": candidate.label,
                "description": candidate.description or "",
                "type": "capability",
                "capability_type": candidate.debug.get('capability_type', 'technical'),
                "required_for": candidate.debug.get('required_for', []),
                "possessed_by": candidate.debug.get('possessed_by', ''),
                "level": candidate.debug.get('level', 'professional'),
                "confidence": candidate.confidence
            }
            capabilities.append(capability_data)
        
        # Summary statistics
        summary = {
            'states_count': len(states),
            'actions_count': len(actions),
            'events_count': len(events),
            'capabilities_count': len(capabilities),
            'total_entities': len(states) + len(actions) + len(events) + len(capabilities),
            'session_id': session_id,
            'version': 'behavioral_v1' if USE_VERSIONED_PROVENANCE else 'standard'
        }
        
        # Add provenance URL if available
        if USE_VERSIONED_PROVENANCE:
            summary['provenance_url'] = url_for('provenance.provenance_viewer')
        
        # Add extraction metadata
        from datetime import datetime
        extraction_metadata = {
            'timestamp': datetime.now().isoformat(),
            'extraction_method': 'standard',
            'states_extractor': 'StatesExtractor',
            'actions_extractor': 'ActionsExtractor',
            'events_extractor': 'EventsExtractor',
            'capabilities_extractor': 'CapabilitiesExtractor',
            'llm_available': llm_client is not None,
            'provenance_tracked': True,
            'model_used': getattr(llm_client, 'model', 'fallback') if llm_client else 'heuristic'
        }
        
        return jsonify({
            'success': True,
            'states': states,
            'actions': actions,
            'events': events,
            'capabilities': capabilities,
            'summary': summary,
            'extraction_metadata': extraction_metadata
        })
        
    except Exception as e:
        logger.error(f"Error executing behavioral pass for case {case_id}: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500