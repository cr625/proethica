"""
Enhanced Events Extractor - Pass 3 Temporal Dynamics Implementation

This implements the Events component of the ProEthica 9-concept formalism with comprehensive
Pass integration showing how Events trigger state changes and activate obligations.

Events (E) - Temporal occurrences that trigger ethical considerations, including both
consequences of actions and external occurrences affecting professional practice.

Based on Chapter 2.2.7: Events as temporal dynamics that drive ethical evaluation
and create causal chains requiring professional response (Berreby et al. 2017, Zhang et al. 2023).
"""

from typing import List, Optional, Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_enhanced_events_prompt(text: str, include_mcp_context: bool = False, 
                                  existing_events: Optional[List] = None,
                                  pass1_context: Optional[Dict] = None,
                                  pass2_context: Optional[Dict] = None) -> str:
    """
    Create enhanced events extraction prompt with MCP ontology context and Pass integration.
    
    Args:
        text: Text to extract events from
        include_mcp_context: Whether to include MCP ontology context
        existing_events: Pre-fetched events (if None, will fetch via MCP)
        pass1_context: Contextual framework from Pass 1 (Roles, States, Resources)
        pass2_context: Normative requirements from Pass 2 (Principles, Obligations, Constraints, Capabilities)
    
    Returns:
        Enhanced prompt string with ontology awareness and Pass integration
    """
    
    # Fetch MCP context if enabled
    ontology_context = ""
    if include_mcp_context:
        try:
            if existing_events is None:
                from app.services.external_mcp_client import get_external_mcp_client
                logger.info("Fetching events context from external MCP server...")
                external_client = get_external_mcp_client()
                existing_events = external_client.get_all_event_entities()
                logger.info(f"Retrieved {len(existing_events) if existing_events else 0} existing events from MCP")
            
            # Also fetch related Pass context for integration
            if pass1_context is None or pass2_context is None:
                from app.services.external_mcp_client import get_external_mcp_client
                external_client = get_external_mcp_client()
                
                if pass1_context is None:
                    try:
                        roles = external_client.get_all_role_entities()
                        states = external_client.get_all_state_entities() 
                        resources = external_client.get_all_resource_entities()
                        pass1_context = {
                            'roles': roles or [],
                            'states': states or [], 
                            'resources': resources or []
                        }
                    except Exception as e:
                        logger.warning(f"Could not fetch Pass 1 context: {e}")
                        pass1_context = {'roles': [], 'states': [], 'resources': []}
                
                if pass2_context is None:
                    try:
                        principles = external_client.get_all_principle_entities()
                        obligations = external_client.get_all_obligation_entities()
                        constraints = external_client.get_all_constraint_entities()
                        capabilities = external_client.get_all_capability_entities()
                        pass2_context = {
                            'principles': principles or [],
                            'obligations': obligations or [],
                            'constraints': constraints or [],
                            'capabilities': capabilities or []
                        }
                    except Exception as e:
                        logger.warning(f"Could not fetch Pass 2 context: {e}")
                        pass2_context = {'principles': [], 'obligations': [], 'constraints': [], 'capabilities': []}
            
        except Exception as e:
            logger.error(f"Failed to get external MCP context for events: {e}")
            existing_events = []
            pass1_context = {'roles': [], 'states': [], 'resources': []}
            pass2_context = {'principles': [], 'obligations': [], 'constraints': [], 'capabilities': []}
    
    # Build ontology context section
    if include_mcp_context and existing_events:
        ontology_context = f"""
EXISTING EVENTS IN ONTOLOGY:
Found {len(existing_events)} existing event concepts organized by type:

EVENT CATEGORIES & DEFINITIONS:
"""
        
        # Group events by type for better organization
        event_types = {}
        for event in existing_events:
            label = event.get('label', 'Unknown Event')
            definition = event.get('definition') or event.get('description') or 'No definition available'
            
            # Determine event type from label
            event_type = "General Event"
            if any(word in label.lower() for word in ['crisis', 'emergency', 'failure', 'accident']):
                event_type = "Crisis Events"
            elif any(word in label.lower() for word in ['compliance', 'violation', 'breach', 'misconduct']):
                event_type = "Compliance Events"
            elif any(word in label.lower() for word in ['conflict', 'dispute', 'disagreement']):
                event_type = "Conflict Events"
            elif any(word in label.lower() for word in ['project', 'deadline', 'milestone']):
                event_type = "Project Events"
            elif any(word in label.lower() for word in ['safety', 'harm', 'injury', 'incident']):
                event_type = "Safety Events"
            elif any(word in label.lower() for word in ['evaluation', 'audit', 'inspection', 'review']):
                event_type = "Evaluation Events"
            elif any(word in label.lower() for word in ['discovery', 'finding', 'detection']):
                event_type = "Discovery Events"
            elif any(word in label.lower() for word in ['change', 'modification', 'update']):
                event_type = "Change Events"
            
            if event_type not in event_types:
                event_types[event_type] = []
            event_types[event_type].append((label, definition))
        
        # Add grouped events to context
        for event_type, events_list in event_types.items():
            ontology_context += f"\n{event_type}:\n"
            for label, definition in events_list:
                ontology_context += f"  - **{label}**: {definition}\n"
    
    elif include_mcp_context:
        ontology_context = "\nEXISTING EVENTS IN ONTOLOGY:\nNo existing event concepts found in ontology.\n"
    
    # Build Pass integration context
    pass_integration = ""
    if include_mcp_context and (pass1_context or pass2_context):
        pass_integration = """
PASS INTEGRATION CONTEXT:

**PASS 3 TEMPORAL DYNAMICS FOCUS:**
Events represent temporal occurrences that trigger ethical considerations and drive state changes.
They include both consequences of actions and external occurrences that affect professional practice.
Your extraction should show how events create temporal flow in professional scenarios.

**Key Integration Points:**
"""
        
        if pass1_context and pass1_context.get('states'):
            states_sample = pass1_context['states'][:5]  # Show first 5
            pass_integration += f"""
• **Events → States**: Events trigger transitions between environmental states
  Sample states that events can trigger: {', '.join([s.get('label', 'Unknown') for s in states_sample])}
"""
        
        if pass2_context and pass2_context.get('obligations'):
            obligations_sample = pass2_context['obligations'][:3]
            pass_integration += f"""
• **Events → Obligations**: Events activate specific professional obligations and requirements
  Sample obligations triggered by events: {', '.join([o.get('label', 'Unknown') for o in obligations_sample])}
"""
        
        if pass1_context and pass1_context.get('roles'):
            roles_sample = pass1_context['roles'][:3]
            pass_integration += f"""
• **Roles → Events**: Professional roles determine how events are interpreted and responded to
  Sample roles affected by events: {', '.join([r.get('label', 'Unknown') for r in roles_sample])}
"""
        
        if pass2_context and pass2_context.get('constraints'):
            constraints_sample = pass2_context['constraints'][:3]
            pass_integration += f"""
• **Events → Constraints**: Events may activate or modify professional constraints
  Sample constraints affected by events: {', '.join([c.get('label', 'Unknown') for c in constraints_sample])}
"""
        
        if pass2_context and pass2_context.get('capabilities'):
            capabilities_sample = pass2_context['capabilities'][:3]
            pass_integration += f"""
• **Events → Capabilities**: Events may require specific capabilities for appropriate response
  Sample capabilities needed for event response: {', '.join([cap.get('label', 'Unknown') for cap in capabilities_sample])}
"""

    # Build the complete enhanced prompt
    enhanced_prompt = f"""You are an expert in professional ethics extracting EVENTS from an ethics guideline.

{ontology_context}

{pass_integration}

**EVENTS DEFINED** (Chapter 2.2.7):
Events are temporal occurrences that trigger ethical considerations. They include both consequences 
of volitional actions and external occurrences that happen without agent intervention but affect 
professional practice (Zhang et al. 2023, Berreby et al. 2017).

**KEY CHARACTERISTICS OF PROFESSIONAL EVENTS:**
• **Temporal Nature**: Occur at specific points in time with before/after states
• **Trigger Ethics**: Create situations requiring ethical evaluation and response
• **Causal Chains**: Form part of action-consequence sequences (Wright's NESS test)
• **State Transitions**: Drive changes in professional environmental conditions
• **Response Requirements**: Activate professional obligations and response protocols

**CRITICAL DISTINCTION FROM ACTIONS:**
Events are occurrences AFFECTING agents (whether caused by them or external).
Actions are volitional choices BY agents.
Example: 'Report is filed' (Event) vs 'Engineer decides to report' (Action)
Events capture what happens; Actions capture the decision to make it happen.

**EVENT TYPES TO IDENTIFY:**

1. **Crisis Events**: failures, accidents, emergencies requiring immediate response (the occurrence, not the response)
2. **Compliance Events**: violations discovered, breaches detected, misconduct revealed (the discovery event)
3. **Conflict Events**: disputes arising, disagreements emerging (the emergence of conflict)
4. **Project Events**: deadlines reached, milestones achieved (the temporal occurrence)
5. **Safety Events**: incidents occurring, harm manifesting, threats emerging (the actual occurrence)
6. **Evaluation Events**: audits conducted, inspections performed, reviews completed (the event of being evaluated)
7. **Discovery Events**: findings revealed, detections made, information uncovered (the moment of discovery)
8. **Change Events**: modifications implemented, updates applied (the occurrence of change)

**RELATIONSHIP TO ACTIONS:**
Every Action becomes an Event in the temporal flow, but not every Event stems from an Action.
- Action-caused Events: Results of volitional decisions (e.g., 'construction halted' after decision to halt)
- External Events: Occurrences without direct agent volition (e.g., 'earthquake damages structure')
Both types trigger professional obligations and ethical considerations.

**EXTRACTION GUIDELINES:**

• Focus on **triggering events** that create ethical considerations
• Distinguish **agent-caused** events (consequences of actions) from **external** events
• Consider **temporal sequence** - what happens when and in what order
• Identify **state changes** - how events alter environmental conditions
• Note **obligation activation** - which duties events trigger
• Consider **response requirements** - what events demand professionally
• Show **Pass integration** - how events connect to roles, obligations, and states

**APPORTIONMENT RULE:**
- If text emphasizes OCCURRENCE/HAPPENING/TRIGGER/DISCOVERY → Extract as Event
- If text emphasizes DECISION/CHOICE/INTENTION/DELIBERATION → Extract as Action
- If both aspects present → Extract the Event (the Action extractor will capture the volition)
- External occurrences without agent volition → Always extract as Event

**TEXT TO ANALYZE:**
{text}

**OUTPUT INSTRUCTIONS:**
Extract professional events as JSON array with this exact structure:
[
  {{
    "label": "Event Name",
    "description": "Clear description of what occurs and its significance for professional practice",
    "event_type": "Crisis/Compliance/Conflict/Project/Safety/Evaluation/Discovery/Change",
    "temporal_nature": "Brief explanation of when/how this event occurs in professional scenarios",
    "triggering_conditions": "What causes or precedes this event",
    "ethical_significance": "Why this event requires professional attention or response",
    "pass_integration": {{
      "triggers_obligations": ["Obligations this event activates"],
      "changes_states": ["Environmental states this event creates or modifies"],
      "affects_roles": ["Professional roles that must respond to this event"], 
      "requires_capabilities": ["Capabilities needed to handle this event appropriately"]
    }},
    "causal_relationships": {{
      "caused_by_actions": ["Actions that might cause this event (e.g., 'Decide to Report' causes 'Report Filed')"],
      "leads_to_events": ["Subsequent events this might trigger"],
      "is_external": "true/false - whether this event occurs without agent volition"
    }},
    "confidence": 0.8
  }}
]

Focus on quality over quantity. Extract clear, professionally significant events with strong temporal and causal reasoning.
"""
    
    return enhanced_prompt


class EnhancedEventsExtractor:
    """
    Enhanced Events Extractor with comprehensive Pass integration and MCP ontology awareness.
    
    This extractor implements Pass 3 temporal dynamics by showing how Events trigger state changes,
    activate obligations, and create the temporal flow of professional ethical scenarios through
    both action consequences and external occurrences.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def extract_events(self, text: str, include_mcp_context: bool = True, 
                      existing_events: Optional[List] = None,
                      pass1_context: Optional[Dict] = None,
                      pass2_context: Optional[Dict] = None) -> List[Dict]:
        """
        Extract events with enhanced ontology context and Pass integration.
        
        Args:
            text: Text to extract events from
            include_mcp_context: Whether to include MCP ontology context
            existing_events: Pre-fetched events (if None, will fetch via MCP)
            pass1_context: Contextual framework from Pass 1
            pass2_context: Normative requirements from Pass 2
        
        Returns:
            List of extracted event dictionaries with Pass integration
        """
        
        try:
            # Create enhanced prompt
            prompt = create_enhanced_events_prompt(
                text=text,
                include_mcp_context=include_mcp_context,
                existing_events=existing_events,
                pass1_context=pass1_context,
                pass2_context=pass2_context
            )
            
            # For now, return the prompt as this is the enhanced prompt generator
            # The actual LLM extraction would be handled by the calling code
            self.logger.info(f"Generated enhanced events prompt with MCP context: {include_mcp_context}")
            
            return {
                'prompt': prompt,
                'ontology_context_included': include_mcp_context,
                'events_count': len(existing_events) if existing_events else 0,
                'pass1_context_included': pass1_context is not None,
                'pass2_context_included': pass2_context is not None
            }
            
        except Exception as e:
            self.logger.error(f"Error in enhanced events extraction: {e}")
            raise
    
    def get_prompt_preview(self, text: str, include_mcp_context: bool = True) -> str:
        """Get the enhanced prompt for preview/debugging purposes."""
        return create_enhanced_events_prompt(
            text=text,
            include_mcp_context=include_mcp_context
        )


def test_enhanced_events_extractor():
    """Test function for the enhanced events extractor."""
    
    # Sample NSPE text for testing
    sample_text = """
    If engineers discover a design flaw that could lead to structural failure,
    they must immediately notify their supervisor and the client. When a 
    construction accident occurs due to inadequate safety protocols, the 
    responsible engineer faces professional review. Deadline pressure often
    creates ethical dilemmas when safety standards might be compromised.
    """
    
    try:
        extractor = EnhancedEventsExtractor()
        result = extractor.extract_events(
            text=sample_text,
            include_mcp_context=True
        )
        
        print("Enhanced Events Extractor Test Results:")
        print(f"Ontology context included: {result.get('ontology_context_included')}")
        print(f"Events in ontology: {result.get('events_count')}")
        print(f"Pass 1 context: {result.get('pass1_context_included')}")
        print(f"Pass 2 context: {result.get('pass2_context_included')}")
        print("\nGenerated prompt preview (first 500 chars):")
        print(result.get('prompt', '')[:500] + "...")
        
    except Exception as e:
        print(f"Test failed: {e}")


if __name__ == "__main__":
    test_enhanced_events_extractor()
