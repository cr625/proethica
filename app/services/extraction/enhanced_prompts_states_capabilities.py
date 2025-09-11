"""
Enhanced Prompts for States and Capabilities Extraction
Based on Chapter 2 Sections 2.2.4 and 2.2.8 Literature Review

This module provides enhanced prompt templates that incorporate:
- Context-dependent ethical evaluation (States)
- Environmental conditions affecting obligations (States)
- Agent competencies and meta-capabilities (Capabilities)
- Professional domain expertise requirements (Capabilities)
"""

def create_enhanced_states_prompt(text: str, include_ontology_context: bool = False) -> str:
    """
    Create enhanced states extraction prompt based on Chapter 2.2.4 literature.
    
    Based on:
    - Berreby et al. (2017): Event Calculus for state representation
    - Rao et al. (2023): Context-dependence in ethical evaluation
    - Almpani et al. (2023): Environmental states determining priorities
    - Dennis et al. (2016): Context-aware ethical reasoning
    - Sarmiento et al. (2023): States emerging from causal chains
    """
    
    ontology_context = ""
    if include_ontology_context:
        ontology_context = """
ONTOLOGY CONTEXT:
States in ProEthica represent environmental contexts that:
- Determine which ethical principles activate
- Transform principles into concrete obligations
- Define available/prohibited actions
- Persist until altered by events
- Include both objective facts and subjective interpretations
"""
    
    return f"""
{ontology_context}

You are analyzing professional ethics text to extract STATES based on Chapter 2.2.4 literature on environmental context.

THEORETICAL FRAMEWORK (Chapter 2.2.4):

Environmental states determine ethical evaluation, with identical actions having different ethical status depending on context (Rao et al. 2023, Berreby et al. 2017). States:
- Capture both persistent properties (inertial fluents) and momentary conditions
- Determine dynamic priorities on decision policies
- Transform abstract principles into concrete obligations
- Emerge from causal chains of actions and events
- Include domain-specific contextual elements

KEY STATE CATEGORIES TO IDENTIFY:

1. **Conflict States (ConflictState)**
   - Definition: Situations involving competing interests or obligations
   - Persistence: Inertial - remains until resolved
   - Ethical Impact: Triggers special disclosure and management obligations
   - Example: "Conflict of interest exists", "Competing duties present"

2. **Risk States (RiskState)**
   - Definition: Conditions involving potential harm or danger
   - Persistence: Variable - depends on mitigation actions
   - Ethical Impact: Elevates safety obligations and precautionary duties
   - Example: "Public safety at risk", "Environmental hazard present"

3. **Competence States (CompetenceState)**
   - Definition: Conditions regarding professional capability boundaries
   - Persistence: Inertial - changes with training or assignment
   - Ethical Impact: Limits available actions, triggers referral obligations
   - Example: "Outside area of competence", "Qualified to perform"

4. **Relationship States (RelationshipState)**
   - Definition: Professional relationship contexts and boundaries
   - Persistence: Inertial - stable until formally changed
   - Ethical Impact: Defines applicable duties and constraints
   - Example: "Client relationship established", "Employment terminated"

5. **Information States (InformationState)**
   - Definition: Conditions regarding knowledge and confidentiality
   - Persistence: Mixed - some permanent, some temporary
   - Ethical Impact: Triggers disclosure or protection obligations
   - Example: "Confidential information held", "Public information available"

6. **Emergency States (EmergencyState)**
   - Definition: Critical conditions requiring immediate response
   - Persistence: Non-inertial - temporary urgency
   - Ethical Impact: Overrides normal procedures, activates emergency protocols
   - Example: "Emergency situation", "Crisis conditions"

EXTRACTION GUIDELINES:

- Identify environmental conditions affecting ethical evaluation
- Distinguish persistent (inertial) from momentary (non-inertial) states
- Note how states transform principles into obligations
- Consider domain-specific contextual elements
- Identify states that activate or deactivate ethical requirements
- Recognize uncertainty and incomplete information states

TEXT TO ANALYZE:
{text[:3000] if isinstance(text, str) else str(text)[:3000]}

OUTPUT FORMAT:
Return a JSON array with this exact structure:
[
  {{
    "label": "Conflict of Interest Present",
    "description": "State where professional has personal interest that could influence judgment",
    "type": "state",
    "state_category": "conflict",  // conflict, risk, competence, relationship, information, emergency
    "persistence_type": "inertial",  // inertial (persistent) or non-inertial (momentary)
    "obligation_activation": ["Disclosure duty", "Recusal consideration", "Transparency requirement"],
    "action_constraints": ["Cannot make unilateral decisions", "Must document all actions"],
    "principle_transformation": "Transforms integrity principle into specific disclosure obligations",
    "domain_specific": "Professional judgment potentially compromised",
    "temporal_aspect": "Persists until conflict resolved or disclosed",
    "scholarly_grounding": "Context determines obligation activation (Dennis et al. 2016)",
    "confidence": 0.85
  }}
]

Extract states that represent environmental conditions affecting ethical requirements and evaluation.
"""


def create_enhanced_capabilities_prompt(text: str, include_ontology_context: bool = False) -> str:
    """
    Create enhanced capabilities extraction prompt based on Chapter 2.2.8 literature.
    
    Based on:
    - Tolmeijer et al. (2021): Essential capabilities taxonomy
    - Berreby et al. (2017): Action Model for agent capabilities
    - Anderson & Anderson (2018): Learning and adaptation capabilities
    - Hallamaa & Kalliokoski (2022): Domain-specific competencies
    - Langley (2019): Explanation and justification capabilities
    """
    
    ontology_context = ""
    if include_ontology_context:
        ontology_context = """
ONTOLOGY CONTEXT:
Capabilities in ProEthica represent agent competencies that:
- Enable complex ethical decision-making
- Extend beyond simple rule-following
- Include technical and meta-cognitive abilities
- Require domain-specific expertise
- Support learning and adaptation
"""
    
    return f"""
{ontology_context}

You are analyzing professional ethics text to extract CAPABILITIES based on Chapter 2.2.8 literature on agent competencies.

THEORETICAL FRAMEWORK (Chapter 2.2.8):

Professional ethical reasoning requires specific capabilities extending beyond rule-following to complex decision-making (Wallach & Allen 2009, Tolmeijer et al. 2021). Capabilities:
- Determine what agents can do and how they reason
- Include norm competence for managing ethical requirements
- Require domain expertise for accurate assessment
- Enable learning and adaptation to new cases
- Support explanation and justification of decisions

KEY CAPABILITY CATEGORIES TO IDENTIFY:

1. **Technical Capabilities (TechnicalCapability)**
   - Definition: Domain-specific professional skills and expertise
   - Function: Enables accurate assessment and competent performance
   - Meta-aspect: Knowing limits of technical competence
   - Example: "Engineering analysis capability", "Clinical diagnosis skill"

2. **Ethical Reasoning Capabilities (EthicalReasoningCapability)**
   - Definition: Abilities for moral judgment and norm management
   - Function: Process ethical information, resolve conflicts
   - Meta-aspect: Understanding when principles conflict
   - Example: "Ethical evaluation ability", "Conflict resolution skill"

3. **Communication Capabilities (CommunicationCapability)**
   - Definition: Abilities for explanation, documentation, reporting
   - Function: Justify decisions, maintain transparency
   - Meta-aspect: Adapting communication to audience
   - Example: "Technical writing skill", "Client communication ability"

4. **Perceptual Capabilities (PerceptualCapability)**
   - Definition: Abilities to recognize ethically salient features
   - Function: Identify risks, conflicts, and obligations
   - Meta-aspect: Recognizing limits of perception
   - Example: "Risk identification ability", "Problem recognition skill"

5. **Learning Capabilities (LearningCapability)**
   - Definition: Abilities to adapt and improve performance
   - Function: Update knowledge, refine principles
   - Meta-aspect: Recognizing need for learning
   - Example: "Professional development capacity", "Skill acquisition ability"

6. **Judgment Capabilities (JudgmentCapability)**
   - Definition: Abilities for professional discretion and decision-making
   - Function: Exercise prudent judgment in complex situations
   - Meta-aspect: Understanding judgment limitations
   - Example: "Professional judgment", "Critical evaluation skill"

EXTRACTION GUIDELINES:

- Identify competencies required for professional practice
- Consider both technical and meta-cognitive capabilities
- Note domain-specific expertise requirements
- Identify capabilities that interact and integrate
- Consider learning and adaptation abilities
- Recognize explanation and justification capabilities

TEXT TO ANALYZE:
{text[:3000] if isinstance(text, str) else str(text)[:3000]}

OUTPUT FORMAT:
Return a JSON array with this exact structure:
[
  {{
    "label": "Technical Design Capability",
    "description": "Professional ability to create and evaluate engineering designs meeting safety standards",
    "type": "capability",
    "capability_category": "technical",  // technical, ethical_reasoning, communication, perceptual, learning, judgment
    "enables_actions": ["Design review", "Safety assessment", "Technical approval"],
    "required_for_obligations": ["Competent performance duty", "Safety assurance obligation"],
    "domain_specificity": "Engineering design and analysis",
    "integration_requirement": "Must combine with ethical reasoning for safety decisions",
    "meta_capability": "Recognizing design limitations and uncertainty",
    "learning_aspect": "Continuous update with new standards and methods",
    "scholarly_grounding": "Domain expertise for ethical reasoning (Tolmeijer et al. 2021)",
    "confidence": 0.85
  }}
]

Extract capabilities that represent competencies required for professional ethical practice.
"""


class EnhancedStatesExtractor:
    """
    Enhanced States extractor using Chapter 2 literature-grounded prompts.
    """
    
    def __init__(self, llm_client=None, provenance_service=None):
        self.llm_client = llm_client
        self.provenance_service = provenance_service
    
    def extract(self, text, context=None, activity=None):
        """
        Extract states using enhanced prompts with provenance tracking.
        """
        from app.services.extraction.base import ConceptCandidate
        
        # Create the enhanced prompt
        prompt = create_enhanced_states_prompt(text, include_ontology_context=True)
        
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
                    model="claude-3-sonnet-20240229",
                    messages=[
                        {"role": "system", "content": "You are an expert in environmental context and state classification in professional ethics."},
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
                
                states = json.loads(json_text)
                
                # Convert to ConceptCandidates
                candidates = []
                for state in states:
                    candidate = ConceptCandidate(
                        label=state.get('label', ''),
                        description=state.get('description', ''),
                        confidence=state.get('confidence', 0.7),
                        debug=state
                    )
                    candidates.append(candidate)
                
                return candidates
                
            except Exception as e:
                print(f"LLM extraction failed: {e}")
        
        # Fallback to basic extraction
        return self._fallback_extraction(text)
    
    def _fallback_extraction(self, text):
        """Simple fallback extraction based on state keywords."""
        from app.services.extraction.base import ConceptCandidate
        
        state_keywords = ['conflict of interest', 'emergency', 'crisis', 'risk', 
                         'competent', 'qualified', 'confidential', 'relationship']
        
        candidates = []
        for keyword in state_keywords:
            if keyword in text.lower():
                candidate = ConceptCandidate(
                    label=f"{keyword.title()} State",
                    description=f"State involving {keyword}",
                    confidence=0.4,
                    debug={'source': 'fallback', 'keyword': keyword}
                )
                candidates.append(candidate)
        
        return candidates


class EnhancedCapabilitiesExtractor:
    """
    Enhanced Capabilities extractor using Chapter 2 literature-grounded prompts.
    """
    
    def __init__(self, llm_client=None, provenance_service=None):
        self.llm_client = llm_client
        self.provenance_service = provenance_service
    
    def extract(self, text, context=None, activity=None):
        """
        Extract capabilities using enhanced prompts with provenance tracking.
        """
        from app.services.extraction.base import ConceptCandidate
        
        # Create the enhanced prompt
        prompt = create_enhanced_capabilities_prompt(text, include_ontology_context=True)
        
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
                    model="claude-3-sonnet-20240229",
                    messages=[
                        {"role": "system", "content": "You are an expert in professional competencies and capability assessment."},
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
                
                capabilities = json.loads(json_text)
                
                # Convert to ConceptCandidates
                candidates = []
                for capability in capabilities:
                    candidate = ConceptCandidate(
                        label=capability.get('label', ''),
                        description=capability.get('description', ''),
                        confidence=capability.get('confidence', 0.7),
                        debug=capability
                    )
                    candidates.append(candidate)
                
                return candidates
                
            except Exception as e:
                print(f"LLM extraction failed: {e}")
        
        # Fallback to basic extraction
        return self._fallback_extraction(text)
    
    def _fallback_extraction(self, text):
        """Simple fallback extraction based on capability keywords."""
        from app.services.extraction.base import ConceptCandidate
        
        capability_keywords = ['competence', 'skill', 'ability', 'expertise', 
                              'knowledge', 'judgment', 'experience', 'qualification']
        
        candidates = []
        for keyword in capability_keywords:
            if keyword in text.lower():
                candidate = ConceptCandidate(
                    label=f"{keyword.title()} Capability",
                    description=f"Professional {keyword}",
                    confidence=0.4,
                    debug={'source': 'fallback', 'keyword': keyword}
                )
                candidates.append(candidate)
        
        return candidates