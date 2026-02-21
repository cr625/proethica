"""
Enhanced Prompts for Actions and Events Extraction
Based on Chapter 2 Sections 2.2.6-2.2.7 Literature Review

This module provides enhanced prompt templates that incorporate:
- Scholarly citations on professional actions and temporal dynamics
- Volitional vs automatic distinction
- Causal chains and responsibility attribution
- Professional decision points and temporal triggers
"""

from models import ModelConfig


def create_enhanced_actions_prompt(text: str, include_ontology_context: bool = False) -> str:
    """
    Create enhanced actions extraction prompt based on Chapter 2.2.6 literature.
    
    Based on:
    - Abbott (2020): Professional actions as deliberate interventions
    - Sarmiento et al. (2023): Actions as volitional events with causal chains
    - Berreby et al. (2017): Action Model for ethical agents
    - Dawson (1994): Professional actions with special moral properties
    - Govindarajulu & Bringsjord (2017): Intention-based action evaluation
    """
    
    ontology_context = ""
    if include_ontology_context:
        ontology_context = """
ONTOLOGY CONTEXT:
Professional actions in ProEthica are volitional interventions requiring:
- Agent volition and deliberate choice
- Professional capacity and authorization
- Ethical evaluation before execution
- Causal responsibility attribution
"""
    
    return f"""
{ontology_context}

You are analyzing professional ethics text to extract ACTIONS based on Chapter 2.2.6 literature establishing actions as deliberate professional interventions.

THEORETICAL FRAMEWORK (Chapter 2.2.6):

Professional actions are deliberate interventions performed through volitional choice within professional capacity (Abbott 2020, Sarmiento et al. 2023). They differ from events through:
- Requirement for agent volition and deliberate intervention
- Operational manifestation of obligations transformed from principles
- Decision points requiring ethical evaluation before execution
- Professional context determining availability and interpretation

KEY ACTION CATEGORIES TO IDENTIFY:

1. **Decision Actions (DecisionAction)**
   - Definition: Choices between alternatives requiring professional judgment
   - Volitional Aspect: Deliberate selection among options
   - Professional Context: Exercises professional discretion and expertise
   - Example: "Approve design", "Reject proposal", "Select contractor"

2. **Intervention Actions (InterventionAction)**
   - Definition: Direct modifications to situations or systems
   - Volitional Aspect: Intentional change to environment or state
   - Professional Context: Uses professional skills to alter conditions
   - Example: "Modify design", "Implement safeguards", "Correct deficiencies"

3. **Communication Actions (CommunicationAction)**
   - Definition: Information transmission with professional implications
   - Volitional Aspect: Deliberate disclosure or withholding
   - Professional Context: Professional reporting and documentation duties
   - Example: "Report violation", "Disclose risks", "Document findings"

4. **Review Actions (ReviewAction)**
   - Definition: Professional evaluation and verification activities
   - Volitional Aspect: Systematic assessment using professional standards
   - Professional Context: Quality assurance and peer review responsibilities
   - Example: "Review calculations", "Verify compliance", "Audit procedures"

5. **Authorization Actions (AuthorizationAction)**
   - Definition: Exercise of professional authority to permit or certify
   - Volitional Aspect: Formal approval based on professional judgment
   - Professional Context: Legal/professional standing to authorize
   - Example: "Certify design", "Approve payment", "Authorize construction"

EXTRACTION GUIDELINES:

- Focus on volitional interventions requiring deliberate choice
- Identify decision points where ethical evaluation occurs
- Link actions to professional obligations they fulfill
- Consider temporal sequencing and causal chains
- Note intention and professional judgment requirements
- Distinguish actions from automatic events or states

TEXT TO ANALYZE:
{text[:3000] if isinstance(text, str) else str(text)[:3000]}

OUTPUT FORMAT:
Return a JSON array with this exact structure:
[
  {{
    "label": "Report Safety Violation",
    "description": "Professional action to formally report observed safety violations to appropriate authorities",
    "type": "action",
    "action_category": "communication",  // decision, intervention, communication, review, authorization
    "volitional_requirement": "Deliberate choice to report despite potential consequences",
    "professional_context": "Engineering duty to protect public safety",
    "obligations_fulfilled": ["Public safety duty", "Professional reporting requirement"],
    "temporal_aspect": "Must occur promptly upon discovery",
    "causal_implications": "Initiates regulatory review process",
    "intention_requirement": "Intent to protect public welfare",
    "scholarly_grounding": "Professional intervention requiring volition (Sarmiento et al. 2023)",
    "confidence": 0.85
  }}
]

Extract only clear professional actions showing volitional intervention, not states or passive conditions.
"""


def create_enhanced_events_prompt(text: str, include_ontology_context: bool = False) -> str:
    """
    Create enhanced events extraction prompt based on Chapter 2.2.7 literature.
    
    Based on:
    - Berreby et al. (2017): Event Calculus and automatic events
    - Sarmiento et al. (2023): Events as nodes in causal chains
    - Zhang et al. (2023): Moral events classification
    - Anderson & Anderson (2018): Temporal dynamics in ethics
    """
    
    ontology_context = ""
    if include_ontology_context:
        ontology_context = """
ONTOLOGY CONTEXT:
Events in ProEthica represent occurrences that:
- Trigger ethical consideration and constraint activation
- Include both volitional outcomes and exogenous occurrences
- Serve as temporal markers for obligation transformation
- Enable responsibility attribution through causal chains
"""
    
    return f"""
{ontology_context}

You are analyzing professional ethics text to extract EVENTS based on Chapter 2.2.7 literature on temporal dynamics and ethical triggers.

THEORETICAL FRAMEWORK (Chapter 2.2.7):

Events are occurrences triggering ethical consideration, distinct from but interconnected with actions (Berreby et al. 2017). They:
- Represent what happens in temporal flow
- Include both agent-caused outcomes and exogenous occurrences
- Trigger constraint activation and obligation transformation
- Serve as nodes in causal chains for responsibility attribution

KEY EVENT CATEGORIES TO IDENTIFY:

1. **Triggering Events (TriggeringEvent)**
   - Definition: Occurrences that initiate ethical obligations or constraints
   - Temporal Role: Marks transition points in ethical requirements
   - Causal Function: Begins causal chains requiring response
   - Example: "Conflict discovered", "Safety risk identified", "Deadline reached"

2. **Outcome Events (OutcomeEvent)**
   - Definition: Results or consequences of actions or processes
   - Temporal Role: Endpoints of causal chains
   - Causal Function: Effects requiring evaluation or further action
   - Example: "Project completed", "Failure occurred", "Harm resulted"

3. **Milestone Events (MilestoneEvent)**
   - Definition: Significant points in professional processes
   - Temporal Role: Marks phases requiring different obligations
   - Causal Function: Transitions between ethical contexts
   - Example: "Contract signed", "Approval granted", "Certification achieved"

4. **Emergency Events (EmergencyEvent)**
   - Definition: Critical occurrences requiring immediate response
   - Temporal Role: Suspends normal obligations, activates emergency constraints
   - Causal Function: Overrides standard procedures
   - Example: "Structural failure", "Safety breach", "System compromise"

5. **Discovery Events (DiscoveryEvent)**
   - Definition: Revelations of previously unknown information
   - Temporal Role: Changes knowledge state affecting obligations
   - Causal Function: Triggers reassessment and potential action
   - Example: "Defect discovered", "Conflict revealed", "Error detected"

EXTRACTION GUIDELINES:

- Identify occurrences that trigger ethical considerations
- Distinguish automatic events from volitional actions
- Note temporal sequencing and causal relationships
- Consider constraint activation and obligation transformation
- Identify both exogenous and consequence events
- Mark emergency events that override normal procedures

TEXT TO ANALYZE:
{text[:3000] if isinstance(text, str) else str(text)[:3000]}

OUTPUT FORMAT:
Return a JSON array with this exact structure:
[
  {{
    "label": "Safety Risk Identified",
    "description": "Discovery event when potential safety hazard becomes known to professional",
    "type": "event",
    "event_category": "discovery",  // triggering, outcome, milestone, emergency, discovery
    "temporal_marker": "Initiates obligation to respond",
    "automatic_nature": "Occurs when conditions met, not through volition",
    "constraint_activation": ["Immediate reporting requirement", "Work suspension if severe"],
    "obligation_transformation": "Transforms general safety duty into specific response obligation",
    "causal_position": "Beginning of response chain",
    "ethical_salience": "High - triggers multiple professional duties",
    "scholarly_grounding": "Automatic event triggering obligations (Berreby et al. 2017)",
    "confidence": 0.85
  }}
]

Extract events that mark temporal points triggering ethical consideration or obligation changes.
"""


class EnhancedActionsExtractor:
    """
    Enhanced Actions extractor using Chapter 2 literature-grounded prompts.
    """
    
    def __init__(self, llm_client=None, provenance_service=None):
        self.llm_client = llm_client
        self.provenance_service = provenance_service
    
    def extract(self, text, context=None, activity=None):
        """
        Extract actions using enhanced prompts with provenance tracking.
        """
        from app.services.extraction.base import ConceptCandidate
        
        # Create the enhanced prompt
        prompt = create_enhanced_actions_prompt(text, include_ontology_context=True)
        
        # Call LLM if available
        if self.llm_client:
            try:
                # Track LLM call in provenance if activity provided
                if self.provenance_service and activity:
                    self.provenance_service.track_llm_call(
                        prompt=prompt[:500],  # First 500 chars for provenance
                        provider='claude',
                        model='claude-3',
                        activity=activity
                    )
                
                response = self.llm_client.chat.completions.create(
                    model=ModelConfig.get_claude_model("default"),
                    messages=[
                        {"role": "system", "content": "You are an expert in professional ethics and action classification."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=2000
                )
                
                # Parse response
                import json
                response_text = response.choices[0].message.content
                
                # Track response in provenance
                if self.provenance_service and activity:
                    self.provenance_service.track_llm_response(
                        response=response_text[:500],
                        tokens_used=response.usage.total_tokens if hasattr(response, 'usage') else 0,
                        activity=activity
                    )
                
                # Extract JSON from response
                if '```json' in response_text:
                    json_text = response_text.split('```json')[1].split('```')[0]
                else:
                    json_text = response_text
                
                actions = json.loads(json_text)
                
                # Convert to ConceptCandidates
                candidates = []
                for action in actions:
                    candidate = ConceptCandidate(
                        label=action.get('label', ''),
                        description=action.get('description', ''),
                        confidence=action.get('confidence', 0.7),
                        debug=action
                    )
                    candidates.append(candidate)
                
                return candidates
                
            except Exception as e:
                print(f"LLM extraction failed: {e}")
        
        # Fallback to basic extraction
        return self._fallback_extraction(text)
    
    def _fallback_extraction(self, text):
        """Simple fallback extraction based on action keywords."""
        from app.services.extraction.base import ConceptCandidate
        
        action_keywords = ['approve', 'reject', 'report', 'review', 'implement', 
                          'modify', 'certify', 'authorize', 'disclose', 'document']
        
        candidates = []
        for keyword in action_keywords:
            if keyword in text.lower():
                candidate = ConceptCandidate(
                    label=f"{keyword.capitalize()} Action",
                    description=f"Professional action involving {keyword}",
                    confidence=0.4,
                    debug={'source': 'fallback', 'keyword': keyword}
                )
                candidates.append(candidate)
        
        return candidates


class EnhancedEventsExtractor:
    """
    Enhanced Events extractor using Chapter 2 literature-grounded prompts.
    """
    
    def __init__(self, llm_client=None, provenance_service=None):
        self.llm_client = llm_client
        self.provenance_service = provenance_service
    
    def extract(self, text, context=None, activity=None):
        """
        Extract events using enhanced prompts with provenance tracking.
        """
        from app.services.extraction.base import ConceptCandidate
        
        # Create the enhanced prompt
        prompt = create_enhanced_events_prompt(text, include_ontology_context=True)
        
        # Call LLM if available
        if self.llm_client:
            try:
                # Track LLM call in provenance if activity provided
                if self.provenance_service and activity:
                    self.provenance_service.track_llm_call(
                        prompt=prompt[:500],
                        provider='claude',
                        model='claude-3',
                        activity=activity
                    )
                
                response = self.llm_client.chat.completions.create(
                    model=ModelConfig.get_claude_model("default"),
                    messages=[
                        {"role": "system", "content": "You are an expert in temporal dynamics and event classification in professional ethics."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=2000
                )
                
                # Parse response
                import json
                response_text = response.choices[0].message.content
                
                # Track response in provenance
                if self.provenance_service and activity:
                    self.provenance_service.track_llm_response(
                        response=response_text[:500],
                        tokens_used=response.usage.total_tokens if hasattr(response, 'usage') else 0,
                        activity=activity
                    )
                
                # Extract JSON from response
                if '```json' in response_text:
                    json_text = response_text.split('```json')[1].split('```')[0]
                else:
                    json_text = response_text
                
                events = json.loads(json_text)
                
                # Convert to ConceptCandidates
                candidates = []
                for event in events:
                    candidate = ConceptCandidate(
                        label=event.get('label', ''),
                        description=event.get('description', ''),
                        confidence=event.get('confidence', 0.7),
                        debug=event
                    )
                    candidates.append(candidate)
                
                return candidates
                
            except Exception as e:
                print(f"LLM extraction failed: {e}")
        
        # Fallback to basic extraction
        return self._fallback_extraction(text)
    
    def _fallback_extraction(self, text):
        """Simple fallback extraction based on event keywords."""
        from app.services.extraction.base import ConceptCandidate
        
        event_keywords = ['discovered', 'occurred', 'identified', 'detected', 
                         'failed', 'completed', 'triggered', 'emerged', 'revealed']
        
        candidates = []
        for keyword in event_keywords:
            if keyword in text.lower():
                candidate = ConceptCandidate(
                    label=f"{keyword.capitalize()} Event",
                    description=f"Event involving {keyword}",
                    confidence=0.4,
                    debug={'source': 'fallback', 'keyword': keyword}
                )
                candidates.append(candidate)
        
        return candidates