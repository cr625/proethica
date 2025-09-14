"""
Enhanced Actions Extractor - Pass 3 Temporal Dynamics Implementation

This implements the Actions component of the ProEthica 9-concept formalism with comprehensive
Pass integration showing how Actions fulfill Obligations from Pass 2 within Roles from Pass 1.

Actions (A) - Volitional professional decisions and interventions that carry ethical significance
and operate within the temporal dynamics of professional practice.

Based on Chapter 2.2.6: Actions as professional decisions requiring deliberation between alternatives
with intention-based evaluation per Doctrine of Double Effect (Govindarajulu & Bringsjord 2017).
"""

from typing import List, Optional, Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_enhanced_actions_prompt(text: str, include_mcp_context: bool = False, 
                                   existing_actions: Optional[List] = None,
                                   pass1_context: Optional[Dict] = None,
                                   pass2_context: Optional[Dict] = None) -> str:
    """
    Create enhanced actions extraction prompt with MCP ontology context and Pass integration.
    
    Args:
        text: Text to extract actions from
        include_mcp_context: Whether to include MCP ontology context
        existing_actions: Pre-fetched actions (if None, will fetch via MCP)
        pass1_context: Contextual framework from Pass 1 (Roles, States, Resources)
        pass2_context: Normative requirements from Pass 2 (Principles, Obligations, Constraints, Capabilities)
    
    Returns:
        Enhanced prompt string with ontology awareness and Pass integration
    """
    
    # Fetch MCP context if enabled
    ontology_context = ""
    if include_mcp_context:
        try:
            if existing_actions is None:
                from app.services.external_mcp_client import get_external_mcp_client
                logger.info("Fetching actions context from external MCP server...")
                external_client = get_external_mcp_client()
                existing_actions = external_client.get_all_action_entities()
                logger.info(f"Retrieved {len(existing_actions) if existing_actions else 0} existing actions from MCP")
            
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
            logger.error(f"Failed to get external MCP context for actions: {e}")
            existing_actions = []
            pass1_context = {'roles': [], 'states': [], 'resources': []}
            pass2_context = {'principles': [], 'obligations': [], 'constraints': [], 'capabilities': []}
    
    # Build ontology context section
    if include_mcp_context and existing_actions:
        ontology_context = f"""
EXISTING ACTIONS IN ONTOLOGY:
Found {len(existing_actions)} existing action concepts organized by type:

ACTION CATEGORIES & DEFINITIONS:
"""
        
        # Group actions by type for better organization
        action_types = {}
        for action in existing_actions:
            label = action.get('label', 'Unknown Action')
            definition = action.get('definition') or action.get('description') or 'No definition available'
            
            # Determine action type from label
            action_type = "General Action"
            if any(word in label.lower() for word in ['communication', 'disclosure', 'inform', 'notify']):
                action_type = "Communication Actions"
            elif any(word in label.lower() for word in ['prevention', 'avoid', 'prevent', 'minimize']):
                action_type = "Prevention Actions"
            elif any(word in label.lower() for word in ['maintenance', 'maintain', 'uphold', 'preserve']):
                action_type = "Maintenance Actions"
            elif any(word in label.lower() for word in ['performance', 'perform', 'execute', 'conduct']):
                action_type = "Performance Actions"
            elif any(word in label.lower() for word in ['evaluation', 'evaluate', 'assess', 'analyze']):
                action_type = "Evaluation Actions"
            elif any(word in label.lower() for word in ['collaboration', 'consult', 'coordinate']):
                action_type = "Collaboration Actions"
            elif any(word in label.lower() for word in ['creation', 'design', 'develop', 'create']):
                action_type = "Creation Actions"
            elif any(word in label.lower() for word in ['monitoring', 'monitor', 'supervise', 'oversee']):
                action_type = "Monitoring Actions"
            
            if action_type not in action_types:
                action_types[action_type] = []
            action_types[action_type].append((label, definition))
        
        # Add grouped actions to context
        for action_type, actions_list in action_types.items():
            ontology_context += f"\n{action_type}:\n"
            for label, definition in actions_list:
                ontology_context += f"  - **{label}**: {definition}\n"
    
    elif include_mcp_context:
        ontology_context = "\nEXISTING ACTIONS IN ONTOLOGY:\nNo existing action concepts found in ontology.\n"
    
    # Build Pass integration context
    pass_integration = ""
    if include_mcp_context and (pass1_context or pass2_context):
        pass_integration = """
PASS INTEGRATION CONTEXT:

**PASS 3 TEMPORAL DYNAMICS FOCUS:**
Actions represent volitional professional decisions that fulfill obligations, operate within states, 
and are constrained by professional limitations. Your extraction should show how actions connect 
to the temporal flow of professional ethical scenarios.

**Key Integration Points:**
"""
        
        if pass2_context and pass2_context.get('obligations'):
            obligations_sample = pass2_context['obligations'][:5]  # Show first 5
            pass_integration += f"""
• **Actions → Obligations**: Actions fulfill specific professional obligations
  Sample obligations to connect: {', '.join([o.get('label', 'Unknown') for o in obligations_sample])}
"""
        
        if pass1_context and pass1_context.get('roles'):
            roles_sample = pass1_context['roles'][:3]
            pass_integration += f"""
• **Roles → Actions**: Professional roles determine which actions are available and appropriate
  Sample roles: {', '.join([r.get('label', 'Unknown') for r in roles_sample])}
"""
        
        if pass1_context and pass1_context.get('states'):
            states_sample = pass1_context['states'][:3] 
            pass_integration += f"""
• **States → Actions**: Environmental conditions determine which actions are needed or appropriate
  Sample states: {', '.join([s.get('label', 'Unknown') for s in states_sample])}
"""
        
        if pass2_context and pass2_context.get('constraints'):
            constraints_sample = pass2_context['constraints'][:3]
            pass_integration += f"""
• **Constraints → Actions**: Professional boundaries limit which actions are permissible
  Sample constraints: {', '.join([c.get('label', 'Unknown') for c in constraints_sample])}
"""
        
        if pass2_context and pass2_context.get('capabilities'):
            capabilities_sample = pass2_context['capabilities'][:3]
            pass_integration += f"""
• **Capabilities → Actions**: Agent competencies determine which actions can be performed
  Sample capabilities: {', '.join([cap.get('label', 'Unknown') for cap in capabilities_sample])}
"""

    # Build the complete enhanced prompt
    enhanced_prompt = f"""You are an expert in professional ethics extracting ACTIONS from an ethics guideline.

{ontology_context}

{pass_integration}

**ACTIONS DEFINED** (Chapter 2.2.6):
Actions are volitional professional decisions and interventions that agents perform through deliberate choice. 
They differ from events through their requirement for agent volition and intentional reasoning 
(Sarmiento et al. 2023, Berreby et al. 2017).

**KEY CHARACTERISTICS OF PROFESSIONAL ACTIONS:**
• **Volitional**: Require deliberate choice and intention (Hooker & Kim 2018)
• **Professional Context**: Carry domain-specific meaning within professional roles (Dawson 1994)
• **Ethically Evaluable**: Subject to ethical assessment through multiple frameworks (Bonnemains et al. 2018)
• **Causal Responsibility**: Create causal chains for responsibility attribution (Sarmiento et al. 2023)

**CRITICAL DISTINCTION FROM EVENTS:**
Actions are volitional choices BY agents. Events are occurrences AFFECTING agents.
Example: 'Engineer decides to report' (Action) vs 'Report is filed' (Event)
The same scenario often contains both the volitional decision and its temporal occurrence.

**ACTION TYPES TO IDENTIFY:**

1. **Communication Actions**: disclosure, informing, notifying, reporting (the decision to communicate)
2. **Prevention Actions**: avoiding, preventing, minimizing harms (the choice to prevent)
3. **Maintenance Actions**: upholding, preserving professional standards (the effort to maintain)
4. **Performance Actions**: executing, conducting professional services (the act of performing)
5. **Evaluation Actions**: assessing, analyzing, reviewing situations (the volitional act of evaluating)
6. **Collaboration Actions**: consulting, coordinating with others (the decision to collaborate)
7. **Creation Actions**: designing, developing solutions (the intentional creation process)
8. **Monitoring Actions**: supervising, overseeing processes (the active monitoring choice)

**RELATIONSHIP TO EVENTS:**
Every Action becomes an Event in the temporal flow. The Action captures the volitional choice;
the Event captures its occurrence and consequences.
Example: 'Decide to halt construction' (Action) → 'Construction halted' (Event)

**EXTRACTION GUIDELINES:**

• Focus on **professional actions** with ethical significance
• Identify **volitional decisions** requiring professional judgment
• Consider **intention and reasoning** behind actions (Doctrine of Double Effect)
• Extract **atomic actions** - split compound descriptions
• Note **causal relationships** between actions and outcomes
• Consider **temporal context** - when actions are appropriate
• Show **Pass integration** - how actions fulfill obligations within roles

**APPORTIONMENT RULE:**
- If text emphasizes DECISION/CHOICE/INTENTION/DELIBERATION → Extract as Action
- If text emphasizes OCCURRENCE/HAPPENING/TRIGGER/CONSEQUENCE → Extract as Event
- If both aspects present → Extract the Action (the Event extractor will capture the occurrence)

**TEXT TO ANALYZE:**
{text}

**OUTPUT INSTRUCTIONS:**
Extract professional actions as JSON array with this exact structure:
[
  {{
    "label": "Action Name",
    "description": "Clear description of what this action involves and its professional significance",
    "action_type": "Communication/Prevention/Maintenance/Performance/Evaluation/Collaboration/Creation/Monitoring",
    "volitional_nature": "Brief explanation of the deliberate choice involved",
    "professional_context": "How this action operates within professional practice",
    "pass_integration": {{
      "fulfills_obligations": ["List of obligation types this action fulfills"],
      "requires_capabilities": ["Capabilities needed to perform this action"],
      "constrained_by": ["Constraints that limit this action"],
      "appropriate_states": ["States where this action is most relevant"]
    }},
    "temporal_relationship": {{
      "becomes_event": "The event this action creates (e.g., 'Report Filed' for 'Decide to Report')",
      "triggered_by_events": ["Events that might trigger this action decision"]
    }},
    "confidence": 0.8
  }}
]

Focus on quality over quantity. Extract clear, professionally significant actions with strong Pass integration.
"""
    
    return enhanced_prompt


class EnhancedActionsExtractor:
    """
    Enhanced Actions Extractor with comprehensive Pass integration and MCP ontology awareness.
    
    This extractor implements Pass 3 temporal dynamics by showing how Actions fulfill Obligations
    from Pass 2, operate within Roles and States from Pass 1, and create the volitional flow
    of professional ethical scenarios.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def extract_actions(self, text: str, include_mcp_context: bool = True, 
                       existing_actions: Optional[List] = None,
                       pass1_context: Optional[Dict] = None,
                       pass2_context: Optional[Dict] = None) -> List[Dict]:
        """
        Extract actions with enhanced ontology context and Pass integration.
        
        Args:
            text: Text to extract actions from
            include_mcp_context: Whether to include MCP ontology context
            existing_actions: Pre-fetched actions (if None, will fetch via MCP)
            pass1_context: Contextual framework from Pass 1
            pass2_context: Normative requirements from Pass 2
        
        Returns:
            List of extracted action dictionaries with Pass integration
        """
        
        try:
            # Create enhanced prompt
            prompt = create_enhanced_actions_prompt(
                text=text,
                include_mcp_context=include_mcp_context,
                existing_actions=existing_actions,
                pass1_context=pass1_context,
                pass2_context=pass2_context
            )
            
            # For now, return the prompt as this is the enhanced prompt generator
            # The actual LLM extraction would be handled by the calling code
            self.logger.info(f"Generated enhanced actions prompt with MCP context: {include_mcp_context}")
            
            return {
                'prompt': prompt,
                'ontology_context_included': include_mcp_context,
                'actions_count': len(existing_actions) if existing_actions else 0,
                'pass1_context_included': pass1_context is not None,
                'pass2_context_included': pass2_context is not None
            }
            
        except Exception as e:
            self.logger.error(f"Error in enhanced actions extraction: {e}")
            raise
    
    def get_prompt_preview(self, text: str, include_mcp_context: bool = True) -> str:
        """Get the enhanced prompt for preview/debugging purposes."""
        return create_enhanced_actions_prompt(
            text=text,
            include_mcp_context=include_mcp_context
        )


def test_enhanced_actions_extractor():
    """Test function for the enhanced actions extractor."""
    
    # Sample NSPE text for testing
    sample_text = """
    Engineers must hold paramount the safety, health, and welfare of the public. 
    Engineers should disclose conflicts of interest to clients and employers.
    Engineers shall perform services only in areas of their competence and should
    seek assistance when technical problems exceed their expertise.
    """
    
    try:
        extractor = EnhancedActionsExtractor()
        result = extractor.extract_actions(
            text=sample_text,
            include_mcp_context=True
        )
        
        print("Enhanced Actions Extractor Test Results:")
        print(f"Ontology context included: {result.get('ontology_context_included')}")
        print(f"Actions in ontology: {result.get('actions_count')}")
        print(f"Pass 1 context: {result.get('pass1_context_included')}")
        print(f"Pass 2 context: {result.get('pass2_context_included')}")
        print("\nGenerated prompt preview (first 500 chars):")
        print(result.get('prompt', '')[:500] + "...")
        
    except Exception as e:
        print(f"Test failed: {e}")


if __name__ == "__main__":
    test_enhanced_actions_extractor()
