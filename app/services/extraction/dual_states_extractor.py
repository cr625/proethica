"""
Dual States Extractor - Discovers both new state classes and individual state instances

This service extracts:
1. NEW STATE CLASSES: Novel situational states not in existing ontology
2. INDIVIDUAL STATE INSTANCES: Specific state conditions active in cases
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from app.services.external_mcp_client import get_external_mcp_client
from models import ModelConfig

logger = logging.getLogger(__name__)

@dataclass
class CandidateStateClass:
    """Represents a potentially new state class with temporal properties"""
    label: str
    definition: str
    activation_conditions: List[str]
    termination_conditions: List[str] = None
    persistence_type: str = 'inertial'  # 'inertial' (persistent) or 'non-inertial' (momentary)
    affected_obligations: List[str] = None
    temporal_properties: str = ''  # How urgency/intensity changes over time
    domain_context: str = ''  # Medical/Engineering/Legal/etc.
    discovered_in_case: int = 0
    confidence: float = 0.0
    examples_from_case: List[str] = None
    similarity_to_existing: float = 0.0
    existing_similar_classes: List[str] = None

@dataclass
class StateIndividual:
    """Represents a specific state instance active in a case with temporal tracking"""
    identifier: str
    state_class: str  # URI of the state class
    active_period: str  # When this state was active (backwards compatibility)
    triggering_event: str
    affected_parties: List[str]
    case_section: str
    confidence: float
    is_new_state_class: bool = False  # True if this is a newly discovered state class
    # Enhanced temporal and relational properties
    subject: str = ''  # WHO is in this state (person/organization)
    initiated_at: str = ''  # When state began
    terminated_by: str = ''  # What ended this state
    terminated_at: str = ''  # When state ended
    affects_obligations: List[str] = None  # Which obligations affected
    urgency_level: str = ''  # low/medium/high/critical
    case_involvement: str = ''  # How this affected the case

class DualStatesExtractor:
    """Extract both new state classes and individual state instances"""

    def __init__(self):
        self.mcp_client = get_external_mcp_client()
        self.existing_state_classes = self._load_existing_state_classes()
        self.model_name = ModelConfig.get_claude_model("powerful")
        self.last_raw_response = None  # Store the raw LLM response

    def extract_dual_states(self, case_text: str, case_id: int, section_type: str) -> Tuple[List[CandidateStateClass], List[StateIndividual]]:
        """
        Extract both new state classes and individual state instances from case text

        Returns:
            Tuple of (candidate_state_classes, state_individuals)
        """
        try:
            # 1. Generate dual extraction prompt
            prompt = self._create_dual_states_extraction_prompt(case_text, section_type)

            # 2. Call LLM for dual extraction
            extraction_result = self._call_llm_for_dual_extraction(prompt)

            # 3. Parse and validate results
            candidate_classes = self._parse_candidate_state_classes(extraction_result.get('new_state_classes', []), case_id)
            state_individuals = self._parse_state_individuals(extraction_result.get('state_individuals', []), case_id, section_type)

            # 4. Cross-reference: link individuals to new classes if applicable
            self._link_individuals_to_new_classes(state_individuals, candidate_classes)

            logger.info(f"Extracted {len(candidate_classes)} candidate state classes and {len(state_individuals)} state individuals from case {case_id}")

            # Return raw extraction results - let route handler manage storage
            return candidate_classes, state_individuals

        except Exception as e:
            logger.error(f"Error in dual states extraction: {e}")
            return [], []

    def _load_existing_state_classes(self) -> List[Dict[str, Any]]:
        """Load existing state classes from proethica-intermediate via MCP"""
        try:
            # Get all state entities using MCP
            existing_states = self.mcp_client.get_all_state_entities()
            logger.info(f"Retrieved {len(existing_states)} existing states from external MCP for dual extraction context")
            return existing_states

        except Exception as e:
            logger.error(f"Error loading existing state classes: {e}")
            return []

    def _create_dual_states_extraction_prompt(self, case_text: str, section_type: str) -> str:
        """Create prompt for extracting both new state classes and individual state instances"""

        existing_states_text = self._format_existing_states_for_prompt()

        return f"""
{existing_states_text}

You are analyzing a professional ethics case to extract both STATE CLASSES and STATE INSTANCES.

DEFINITIONS:
- STATE CLASS: A type of situational condition (e.g., "Conflict of Interest", "Emergency Situation", "Resource Constraint")
- STATE INDIVIDUAL: A specific instance of a state active in this case attached to specific people/organizations

CRITICAL REQUIREMENT: Every STATE CLASS you identify MUST be based on at least one specific STATE INDIVIDUAL instance in the case.
You cannot propose a state class without providing the concrete instance(s) that demonstrate it.

KEY INSIGHT FROM LITERATURE:
States are not abstract - they are concrete conditions affecting specific actors at specific times.
Each state has a subject (WHO is in the state), temporal boundaries (WHEN), and causal relationships (WHY).

YOUR TASK - Extract two LINKED types of entities:

1. NEW STATE CLASSES (types not in the existing ontology above):
   - Novel types of situational states discovered in this case
   - Must be sufficiently general to apply to other cases
   - Should represent distinct environmental or contextual conditions
   - Consider both inertial (persistent) and non-inertial (momentary) fluents

2. STATE INDIVIDUALS (specific instances in this case):
   - Specific states active in this case narrative
   - MUST be attached to specific individuals or organizations in the case
   - Include temporal properties (when initiated, when terminated)
   - Include causal relationships (triggered by what event, affects which obligations)
   - Map to existing classes where possible, or to new classes you discover

EXTRACTION GUIDELINES:

For NEW STATE CLASSES, identify:
- Label: Clear, professional name for the state type
- Definition: What this state represents
- Activation conditions: What events/conditions trigger this state
- Termination conditions: What events/conditions end this state
- Persistence type: "inertial" (persists until terminated) or "non-inertial" (momentary)
- Affected obligations: Which professional duties does this state affect?
- Temporal properties: How does this state evolve over time?
- Domain context: Medical/Engineering/Legal/etc.
- Examples from case: Specific instances showing this state type

For STATE INDIVIDUALS, identify:
- Identifier: Unique descriptor (e.g., "John_Smith_ConflictOfInterest_ProjectX")
- State class: Which state type it represents (existing or new)
- Subject: WHO is in this state (person/organization name from the case)
- Initiated by: What event triggered this state?
- Initiated at: When did this state begin?
- Terminated by: What event ended this state (if applicable)?
- Terminated at: When did this state end (if applicable)?
- Affects obligations: Which specific obligations were affected?
- Urgency/Intensity: Does this state's urgency change over time?
- Related parties: Who else is affected by this state?
- Case involvement: How this state affected the case outcome

CASE TEXT FROM {section_type} SECTION:
{case_text}

Respond with a JSON structure. Here's a CONCRETE EXAMPLE showing the required linkage:

EXAMPLE (if the case mentions "Engineer A faced a conflict when discovering his brother worked for the contractor"):
{{
  "new_state_classes": [
    {{
      "label": "Family Conflict of Interest",
      "definition": "A state where a professional's family relationships create potential bias in professional decisions",
      "activation_conditions": ["Discovery of family member involvement", "Family member has financial interest"],
      "termination_conditions": ["Recusal from decision", "Family member withdraws"],
      "persistence_type": "inertial",
      "affected_obligations": ["Duty of impartiality", "Disclosure requirements"],
      "temporal_properties": "Persists until formally addressed through recusal or disclosure",
      "domain_context": "Engineering",
      "examples_from_case": ["Engineer A discovered brother worked for ABC Contractors"],
      "confidence": 0.85,
      "rationale": "Specific type of conflict not covered by general COI in existing ontology"
    }}
  ],
  "state_individuals": [
    {{
      "identifier": "EngineerA_FamilyConflict_ABCContractors",
      "state_class": "Family Conflict of Interest",
      "subject": "Engineer A",
      "initiated_by": "Discovery that brother is senior manager at ABC Contractors",
      "initiated_at": "When bidding process began",
      "terminated_by": "Engineer A recused from contractor selection",
      "terminated_at": "Two weeks after discovery",
      "affects_obligations": ["Maintain impartial contractor selection", "Disclose conflicts to client"],
      "urgency_level": "high",
      "related_parties": ["Client B", "ABC Contractors", "Engineer A's brother"],
      "case_involvement": "Led to Engineer A's recusal from contractor selection process",
      "is_existing_class": false,
      "confidence": 0.9
    }}
  ]
}}

YOUR RESPONSE FORMAT (use the same structure with YOUR case's specific details):
{{
  "new_state_classes": [
    // For each new state type you discover
  ],
  "state_individuals": [
    // For each specific instance in the case (MUST have at least one per new class)
  ]
}}

EXTRACTION RULES:
1. For EVERY new state class you identify, you MUST provide at least one corresponding state individual
2. State individuals MUST have a clear subject (specific person/organization from the case)
3. If you cannot identify a specific instance, do not create the state class
4. States without subjects are invalid (e.g., cannot have "general emergency" - must be "City M's water emergency")
5. Each state individual should clearly demonstrate why its state class is needed

Focus on states that:
1. Are attached to specific individuals or organizations mentioned in the case
2. Have clear temporal boundaries (when initiated, when terminated)
3. Affect specific ethical obligations or professional duties
4. Show causal relationships with events in the case
5. Demonstrate the context-dependent nature of professional ethics

EXAMPLE OF CORRECT EXTRACTION:
State Class: "Public Health Risk State"
State Individual: "City_M_PublicHealthRisk_2023" with subject="City M", initiated_by="Decision to change water source", affects_obligations=["Ensure public safety", "Provide clean water"]

EXAMPLE OF INCORRECT EXTRACTION:
State Class: "Emergency Situation" with NO corresponding individual (INVALID - no specific instance)
"""

    def _format_existing_states_for_prompt(self) -> str:
        """Format existing state classes for inclusion in prompt"""
        if not self.existing_state_classes:
            return "EXISTING STATE CLASSES IN ONTOLOGY: None found. All states you identify will be new."

        text = "EXISTING STATE CLASSES IN ONTOLOGY (DO NOT RE-EXTRACT THESE):\n\n"

        # Group by category if available
        categorized = {}
        uncategorized = []

        for state in self.existing_state_classes:
            category = state.get('category', 'Uncategorized')
            if category and category != 'Uncategorized':
                if category not in categorized:
                    categorized[category] = []
                categorized[category].append(state)
            else:
                uncategorized.append(state)

        # Format categorized states
        for category, states in sorted(categorized.items()):
            text += f"\n{category.upper()} STATES:\n"
            for state in sorted(states, key=lambda x: x.get('label', '')):
                label = state.get('label', 'Unknown')
                definition = state.get('description', state.get('definition', 'No definition'))
                text += f"- {label}: {definition}\n"

        # Format uncategorized states
        if uncategorized:
            text += "\nOTHER STATES:\n"
            for state in sorted(uncategorized, key=lambda x: x.get('label', '')):
                label = state.get('label', 'Unknown')
                definition = state.get('description', state.get('definition', 'No definition'))
                text += f"- {label}: {definition}\n"

        text += "\nIMPORTANT: Only extract NEW state types not listed above!\n"
        return text

    def _call_llm_for_dual_extraction(self, prompt: str) -> Dict[str, Any]:
        """Call LLM for dual state extraction"""
        try:
            from app.utils.llm_utils import get_llm_client

            llm_client = get_llm_client()
            if llm_client:
                response = llm_client.messages.create(
                    model=self.model_name,
                    max_tokens=4000,
                    temperature=0.3,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )

                response_text = response.content[0].text if response.content else ""

                # Store raw response for debugging
                self.last_raw_response = response_text

                # Parse JSON response
                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError:
                    # Try to extract JSON from mixed response
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', response_text)
                    if json_match:
                        result = json.loads(json_match.group())
                    else:
                        logger.error("Could not parse JSON from LLM response")
                        return {}

                return result

        except Exception as e:
            logger.error(f"Error calling LLM for dual states extraction: {e}")
            return {}

    def _parse_candidate_state_classes(self, raw_classes: List[Dict], case_id: int) -> List[CandidateStateClass]:
        """Parse raw state class data into CandidateStateClass objects"""
        candidates = []

        for raw in raw_classes:
            try:
                candidate = CandidateStateClass(
                    label=raw.get('label', 'Unknown State'),
                    definition=raw.get('definition', ''),
                    activation_conditions=raw.get('activation_conditions', []),
                    persistence_type=raw.get('persistence_type', 'persistent'),
                    affected_obligations=raw.get('affected_obligations', []),
                    discovered_in_case=case_id,
                    confidence=raw.get('confidence', 0.7),
                    examples_from_case=raw.get('examples_from_case', [])
                )

                # Calculate similarity to existing classes
                similarity, similar = self._calculate_similarity_to_existing(candidate.label, candidate.definition)
                candidate.similarity_to_existing = similarity
                candidate.existing_similar_classes = similar

                candidates.append(candidate)

            except Exception as e:
                logger.error(f"Error parsing candidate state class: {e}")

        return candidates

    def _parse_state_individuals(self, raw_individuals: List[Dict], case_id: int, section_type: str) -> List[StateIndividual]:
        """Parse raw individual data into StateIndividual objects with enhanced temporal properties"""
        individuals = []

        for raw in raw_individuals:
            try:
                # Create enhanced StateIndividual with temporal properties
                individual = StateIndividual(
                    identifier=raw.get('identifier', 'Unknown State Instance'),
                    state_class=raw.get('state_class', 'State'),
                    active_period=raw.get('active_period', ''),  # Backwards compatibility
                    triggering_event=raw.get('initiated_by', raw.get('triggering_event', '')),
                    affected_parties=raw.get('related_parties', raw.get('affected_parties', [])),
                    case_section=section_type,
                    confidence=raw.get('confidence', 0.8),
                    is_new_state_class=not raw.get('is_existing_class', True)
                )

                # Add enhanced temporal and relational properties
                individual.subject = raw.get('subject', '')
                individual.initiated_at = raw.get('initiated_at', '')
                individual.terminated_by = raw.get('terminated_by', '')
                individual.terminated_at = raw.get('terminated_at', '')
                individual.affects_obligations = raw.get('affects_obligations', [])
                individual.urgency_level = raw.get('urgency_level', '')
                individual.case_involvement = raw.get('case_involvement', '')

                individuals.append(individual)

            except Exception as e:
                logger.error(f"Error parsing state individual: {e}")

        return individuals

    def _calculate_similarity_to_existing(self, label: str, definition: str) -> Tuple[float, List[str]]:
        """Calculate semantic similarity to existing state classes"""
        # For now, simple label matching - could be enhanced with embeddings
        similar_classes = []
        max_similarity = 0.0

        label_lower = label.lower()
        for existing in self.existing_state_classes:
            existing_label = existing.get('label', '').lower()
            if label_lower == existing_label:
                return 1.0, [existing.get('label')]
            elif label_lower in existing_label or existing_label in label_lower:
                similar_classes.append(existing.get('label'))
                max_similarity = max(max_similarity, 0.5)

        return max_similarity, similar_classes

    def _link_individuals_to_new_classes(self, individuals: List[StateIndividual], new_classes: List[CandidateStateClass]):
        """Link individuals to newly discovered state classes"""
        new_class_labels = {c.label for c in new_classes}

        for individual in individuals:
            if individual.state_class in new_class_labels:
                individual.is_new_state_class = True

    def get_last_raw_response(self) -> Optional[str]:
        """Return the last raw LLM response for debugging"""
        return self.last_raw_response

    def get_extraction_summary(self, candidates: List[CandidateStateClass], individuals: List[StateIndividual]) -> Dict[str, Any]:
        """Generate summary of extraction results"""
        return {
            'new_state_classes_count': len(candidates),
            'state_individuals_count': len(individuals),
            'individuals_with_new_classes': sum(1 for i in individuals if i.is_new_state_class),
            'confidence_avg': sum(c.confidence for c in candidates) / len(candidates) if candidates else 0
        }