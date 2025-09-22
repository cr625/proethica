"""
Enhanced Prompts for States and Capabilities Extraction
Based on Chapter 2 Sections 2.2.4 and 2.2.8 Literature Review

This module provides enhanced prompt templates that incorporate:
- Context-dependent ethical evaluation (States)
- Environmental conditions affecting obligations (States)
- Agent competencies and meta-capabilities (Capabilities)
- Professional domain expertise requirements (Capabilities)
"""

def create_enhanced_states_prompt(text: str, include_ontology_context: bool = False, existing_states: list = None) -> str:
    """
    Create enhanced states extraction prompt based on Chapter 2.2.4 literature.
    
    Based on:
    - Berreby et al. (2017): Event Calculus for persistent vs momentary state representation
    - Rao et al. (2023): Context determines ethical evaluation of identical actions
    - Almpani et al. (2023): Environmental states create dynamic priority ordering
    - Dennis et al. (2016): Context activates different obligation sets from same principles
    - Sarmiento et al. (2023): States emerge from causal chains of professional actions
    """
    
    ontology_context = ""
    if include_ontology_context and existing_states:
        # Organize states hierarchically (though most are direct children of State)
        base_state = None
        specific_states = []
        
        # De-duplicate and organize
        seen_labels = set()
        for state in existing_states:
            label = state.get('label', '')
            if label in seen_labels:
                continue
            seen_labels.add(label)
            
            description = state.get('description', state.get('definition', ''))
            
            if label == 'State':
                if not base_state:  # Take first State as base
                    base_state = {'label': label, 'definition': description}
            else:
                specific_states.append({'label': label, 'definition': description})
        
        # Build hierarchical context - NO TRUNCATION
        ontology_context = f"""
EXISTING STATES IN ONTOLOGY (Hierarchical View):
Found {len(seen_labels)} state concepts organized by hierarchy:

**BASE CLASS:**
- **{base_state['label'] if base_state else 'State'}**: {base_state['definition'] if base_state else 'Environmental context that determines obligation activation and action constraints.'}
  (This is the parent class for all state concepts)

**SPECIFIC STATES (Direct instances):**
"""
        for spec in sorted(specific_states, key=lambda x: x['label']):
            ontology_context += f"- **{spec['label']}**: {spec['definition']}\n"
        
        ontology_context += """
**PASS 1 INTEGRATION (Roles + STATES + Resources):**
States work with Roles to determine WHEN obligations activate:
- Roles define WHO has obligations
- States define WHEN those obligations become active
- Resources define WHAT knowledge guides decisions in those states

Example: "Engineer Role" + "Conflict of Interest State" → Activates disclosure obligations
"""
    else:
        ontology_context = """
ONTOLOGY CONTEXT:
States in ProEthica represent environmental contexts that:
- Determine which ethical principles activate
- Transform principles into concrete obligations
- Define available/prohibited actions
- Persist until altered by events
- Include both objective facts and subjective interpretations

Note: No existing state instances found in ontology. All extracted states will be new.
"""
    
    return f"""
{ontology_context}

You are analyzing professional ethics text to extract ENVIRONMENTAL STATES as part of Pass 1 (Contextual Framework) of the ProEthica extraction.

THEORETICAL FRAMEWORK - Key Insights from Environmental Context Literature:

States are not merely descriptive facts but context conditions that fundamentally alter ethical evaluation:
- **Context-Dependent Ethics**: Identical actions have different ethical status in different states (Rao et al. 2023 analysis of 200+ ethics cases)
- **Obligation Activation**: States transform abstract principles into concrete duties (Dennis et al. 2016 study of context-aware systems)
- **Persistent vs Momentary**: Some states persist until changed (inertial), others are temporary (Berreby et al. 2017 Event Calculus formalization)
- **Dynamic Priorities**: Environmental states create priority orderings on decision policies (Almpani et al. 2023 autonomous vehicle ethics)
- **Causal Emergence**: States emerge from chains of professional actions and events (Sarmiento et al. 2023 causal modeling)

**RELATIONSHIP TO ROLES (Pass 1 Integration):**
States work with Roles to determine obligation activation:
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
{text if isinstance(text, str) else str(text)}

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
    "text_references": ["professional has personal interest"],
    "theoretical_grounding": "Context determines obligation activation (Dennis et al. 2016)",
    "ethical_impact": "Triggers disclosure and management obligations",
    "contextual_factors": ["Personal interest", "Professional judgment"],
    "importance": "high",
    "is_existing": false,
    "ontology_match_reasoning": "New state not in existing ontology",
    "confidence": 0.85
  }}
]

Extract states that represent environmental conditions affecting ethical requirements and evaluation.
"""


def create_enhanced_capabilities_prompt(text: str, include_mcp_context: bool = False, 
                                       existing_capabilities: list = None) -> str:
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
    if include_mcp_context:
        # Fetch capabilities from MCP if not provided
        if existing_capabilities is None:
            try:
                from app.services.external_mcp_client import get_external_mcp_client
                external_client = get_external_mcp_client()
                existing_capabilities = external_client.get_all_capability_entities()
            except Exception as e:
                existing_capabilities = []
        
        # Build context from existing capabilities
        if existing_capabilities:
            ontology_context = f"""
EXISTING CAPABILITIES IN ONTOLOGY:
Found {len(existing_capabilities)} capability concepts in ontology:

"""
            for cap in existing_capabilities[:20]:  # Show first 20
                label = cap.get('label', 'Unknown')
                description = cap.get('description', 'No description')
                ontology_context += f"- **{label}**: {description}\n"
            
            if len(existing_capabilities) > 20:
                ontology_context += f"\n... and {len(existing_capabilities) - 20} more capabilities\n"
            
            ontology_context += """

CAPABILITY CATEGORIES (Based on Tolmeijer et al. 2021):
- **Norm Management**: Norm Competence, Conflict Resolution
- **Awareness & Perception**: Situational Awareness, Ethical Perception  
- **Learning & Adaptation**: Ethical Learning, Principle Refinement
- **Reasoning & Deliberation**: Ethical Reasoning, Causal Reasoning, Temporal Reasoning
- **Communication & Explanation**: Explanation Generation, Justification Capability
- **Domain-Specific**: Domain Expertise, Professional Competence
"""
        else:
            ontology_context = """
ONTOLOGY CONTEXT:
Capabilities in ProEthica represent agent competencies that:
- Enable complex ethical decision-making
- Extend beyond simple rule-following
- Include technical and meta-cognitive abilities
- Require domain-specific expertise
- Support learning and adaptation

Note: No existing capability instances found in ontology. All extracted capabilities will be new.
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
        import os
        
        # Try to get existing states from MCP if enabled
        existing_states = []
        if True:
            try:
                from app.services.external_mcp_client import get_external_mcp_client
                external_client = get_external_mcp_client()
                existing_states = external_client.get_all_state_entities()
            except Exception as e:
                # Log but don't fail if MCP is unavailable
                pass
        
        # Create the enhanced prompt with existing states context
        prompt = create_enhanced_states_prompt(text, include_ontology_context=True, existing_states=existing_states)
        
        # Call LLM if available
        if self.llm_client:
            try:
                # Record the prompt if provenance tracking is active
                prompt_entity = None
                if self.provenance_service and activity:
                    prompt_entity = self.provenance_service.record_prompt(
                        prompt_text=prompt[:500],
                        activity=activity,
                        entity_name="extraction_prompt",
                        metadata={
                            'extraction_type': 'states_or_capabilities',
                            'prompt_length': len(prompt)
                        }
                    )
                
                # Import ModelConfig to get the proper model
                from models import ModelConfig

                # Check which type of client we have and use appropriate API
                if hasattr(self.llm_client, 'messages') and hasattr(self.llm_client.messages, 'create'):
                    # Anthropic client - use Opus model for powerful extraction
                    model_name = ModelConfig.get_claude_model("powerful")  # This gets opus-4.1
                    response = self.llm_client.messages.create(
                        model=model_name,
                        max_tokens=2000,
                        messages=[{
                            "role": "user",
                            "content": prompt
                        }]
                    )
                    response_text = response.content[0].text if response.content else ""
                elif hasattr(self.llm_client, 'chat') and hasattr(self.llm_client.chat, 'completions'):
                    # OpenAI client
                    response = self.llm_client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": "You are an expert in environmental context and state classification in professional ethics."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.2,
                        max_tokens=2000
                    )
                    response_text = response.choices[0].message.content
                else:
                    raise ValueError("Unknown LLM client type")
                
                # Parse response
                import json
                
                # Record response in provenance
                if self.provenance_service and activity:
                    # Calculate token usage based on client type
                    tokens_used = 0
                    if hasattr(response, 'usage'):
                        tokens_used = response.usage.total_tokens if hasattr(response.usage, 'total_tokens') else 0
                    
                    response_entity = self.provenance_service.record_response(
                        response_text=response_text[:500],
                        prompt_entity=prompt_entity,
                        activity=activity,
                        entity_name="extraction_response",
                        metadata={
                            'extraction_type': 'states_or_capabilities',
                            'response_length': len(response_text),
                            'tokens_used': tokens_used
                        }
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
                self.logger.error(f"LLM extraction failed: {e}")
        
        # Fallback to basic extraction
        return self._fallback_extraction(text)
    
    def _fallback_extraction(self, text):
        """Simple fallback extraction based on state keywords."""
        from app.services.extraction.base import ConceptCandidate
        
        # Ensure text is a string
        if not isinstance(text, str):
            text = str(text)
        
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
        import logging
        self.logger = logging.getLogger(__name__)

    def extract(self, text, context=None, activity=None):
        """
        Extract capabilities using enhanced prompts with provenance tracking.
        """
        from app.services.extraction.base import ConceptCandidate
        # Import ModelConfig to get the proper model
        from models import ModelConfig
        
        # Create the enhanced prompt
        prompt = create_enhanced_capabilities_prompt(text, include_mcp_context=True)
        
        # Call LLM if available
        if self.llm_client:
            try:
                # Record the prompt if provenance tracking is active
                prompt_entity = None
                if self.provenance_service and activity:
                    prompt_entity = self.provenance_service.record_prompt(
                        prompt_text=prompt[:500],
                        activity=activity,
                        entity_name="extraction_prompt",
                        metadata={
                            'extraction_type': 'states_or_capabilities',
                            'prompt_length': len(prompt)
                        }
                    )
                
                # Import ModelConfig to get the proper model
                from models import ModelConfig

                # Check which type of client we have and use appropriate API
                if hasattr(self.llm_client, 'messages') and hasattr(self.llm_client.messages, 'create'):
                    # Anthropic client - use Opus model for powerful extraction
                    model_name = ModelConfig.get_claude_model("powerful")  # This gets opus-4.1
                    response = self.llm_client.messages.create(
                        model=model_name,
                        max_tokens=2000,
                        messages=[{
                            "role": "user",
                            "content": prompt
                        }]
                    )
                    response_text = response.content[0].text if response.content else ""
                elif hasattr(self.llm_client, 'chat') and hasattr(self.llm_client.chat, 'completions'):
                    # OpenAI client
                    response = self.llm_client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": "You are an expert in professional competencies and capability assessment."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.2,
                        max_tokens=2000
                    )
                    response_text = response.choices[0].message.content
                else:
                    raise ValueError("Unknown LLM client type")
                
                # Parse response
                import json
                
                # Record response in provenance
                if self.provenance_service and activity:
                    # Calculate token usage based on client type
                    tokens_used = 0
                    if hasattr(response, 'usage'):
                        tokens_used = response.usage.total_tokens if hasattr(response.usage, 'total_tokens') else 0
                    
                    response_entity = self.provenance_service.record_response(
                        response_text=response_text[:500],
                        prompt_entity=prompt_entity,
                        activity=activity,
                        entity_name="extraction_response",
                        metadata={
                            'extraction_type': 'states_or_capabilities',
                            'response_length': len(response_text),
                            'tokens_used': tokens_used
                        }
                    )
                
                # Extract JSON from response with better error handling
                capabilities = []
                try:
                    self.logger.info(f"Raw response length: {len(response_text)}")
                    self.logger.debug(f"Raw response (first 500 chars): {response_text[:500]}")

                    if '```json' in response_text:
                        json_text = response_text.split('```json')[1].split('```')[0]
                    else:
                        json_text = response_text

                    # Try direct JSON parsing
                    result = json.loads(json_text)
                    self.logger.info(f"JSON parse successful, type: {type(result)}")

                    # Handle different response formats
                    if isinstance(result, dict):
                        if 'capabilities' in result:
                            capabilities = result['capabilities']
                            self.logger.info(f"Extracted {len(capabilities)} capabilities from 'capabilities' key")
                        else:
                            # Single capability dict
                            capabilities = [result]
                            self.logger.info("Wrapped single capability dict in list")
                    elif isinstance(result, list):
                        capabilities = result
                        self.logger.info(f"Direct list with {len(capabilities)} capabilities")
                    else:
                        self.logger.warning(f"Unexpected JSON format: {type(result)}")
                        capabilities = []

                except json.JSONDecodeError as e:
                    self.logger.warning(f"Failed to parse JSON directly, attempting extraction: {e}")
                    # Try to extract JSON from mixed text response
                    import re
                    json_match = re.search(r'\{[\s\S]*\}|\[[\s\S]*\]', response_text)
                    if json_match:
                        try:
                            result = json.loads(json_match.group())
                            if isinstance(result, dict) and 'capabilities' in result:
                                capabilities = result['capabilities']
                                self.logger.info(f"Extracted {len(capabilities)} capabilities from regex-extracted JSON")
                            elif isinstance(result, list):
                                capabilities = result
                                self.logger.info(f"Extracted list with {len(capabilities)} capabilities from regex")
                            else:
                                self.logger.warning("Extracted JSON but no capabilities found")
                                capabilities = []
                        except json.JSONDecodeError:
                            self.logger.warning("Failed to parse extracted JSON")
                            capabilities = []
                    else:
                        self.logger.warning("No JSON structure found in response")
                        capabilities = []
                
                # Convert to ConceptCandidates
                candidates = []
                for capability in capabilities:
                    candidate = ConceptCandidate(
                        label=capability.get('label', 'Unknown Capability'),
                        description=capability.get('description', ''),
                        primary_type='capability',
                        category='capability',
                        confidence=capability.get('confidence', 0.85),
                        debug={
                            'capability_type': capability.get('capability_type', capability.get('type', 'general')),
                            'source_quote': capability.get('source_quote', ''),
                            'is_existing': capability.get('is_existing', False),
                            'ontology_match': capability.get('ontology_match'),
                            'required_for': capability.get('required_for', []),
                            'enables': capability.get('enables', []),
                            'developed_through': capability.get('developed_through', ''),
                            'assessment_criteria': capability.get('assessment_criteria', ''),
                            'extraction_method': 'llm_enhanced'
                        }
                    )
                    candidates.append(candidate)
                
                return candidates
                
            except Exception as e:
                self.logger.error(f"LLM extraction failed: {e}")
        
        # Fallback to basic extraction
        return self._fallback_extraction(text)
    
    def _fallback_extraction(self, text):
        """Simple fallback extraction based on capability keywords."""
        from app.services.extraction.base import ConceptCandidate
        
        # Ensure text is a string
        if not isinstance(text, str):
            text = str(text)
        
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
