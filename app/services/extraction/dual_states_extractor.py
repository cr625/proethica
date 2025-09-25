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
    """Represents a potentially new state class"""
    label: str
    definition: str
    activation_conditions: List[str]
    persistence_type: str  # 'persistent' or 'momentary'
    affected_obligations: List[str]
    discovered_in_case: int
    confidence: float
    examples_from_case: List[str]
    similarity_to_existing: float = 0.0
    existing_similar_classes: List[str] = None

@dataclass
class StateIndividual:
    """Represents a specific state instance active in a case"""
    identifier: str
    state_class: str  # URI of the state class
    active_period: str  # When this state was active in the case
    triggering_event: str
    affected_parties: List[str]
    case_section: str
    confidence: float
    is_new_state_class: bool = False  # True if this is a newly discovered state class

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
- STATE INDIVIDUAL: A specific instance of a state active in this case (e.g., "Engineer A's conflict regarding Project X", "Budget crisis in Q3 2023")

YOUR TASK - Extract two types of entities:

1. NEW STATE CLASSES (types not in the existing ontology above):
   - Novel types of situational states discovered in this case
   - Must be sufficiently general to apply to other cases
   - Should represent distinct environmental or contextual conditions

2. STATE INDIVIDUALS (specific instances in this case):
   - Specific states active in this case narrative
   - Include when they were active and what triggered them
   - Map to existing classes where possible, or to new classes you discover

EXTRACTION GUIDELINES:

For NEW STATE CLASSES, identify:
- Label: Clear, professional name for the state type
- Definition: What this state represents
- Activation conditions: What triggers this state
- Persistence type: Does it persist until changed (persistent) or is it momentary?
- Affected obligations: What duties or actions does this state affect?
- Examples from case: Specific instances showing this state type

For STATE INDIVIDUALS, identify:
- Identifier: Unique descriptor for this specific state instance
- State class: Which state type it represents (existing or new)
- Active period: When was this state active in the case?
- Triggering event: What caused this state to become active?
- Affected parties: Who was affected by this state?

CASE TEXT FROM {section_type} SECTION:
{case_text}

Respond with a JSON structure:
{{
  "new_state_classes": [
    {{
      "label": "State Type Name",
      "definition": "What this state represents",
      "activation_conditions": ["condition 1", "condition 2"],
      "persistence_type": "persistent|momentary",
      "affected_obligations": ["obligation 1", "obligation 2"],
      "examples_from_case": ["example 1", "example 2"],
      "confidence": 0.85,
      "rationale": "Why this is a distinct state type"
    }}
  ],
  "state_individuals": [
    {{
      "identifier": "Specific state instance descriptor",
      "state_class": "State Type Name",
      "active_period": "When active in the case",
      "triggering_event": "What triggered this state",
      "affected_parties": ["Party A", "Party B"],
      "case_involvement": "How this state affected the case",
      "is_existing_class": false,
      "confidence": 0.9
    }}
  ]
}}

Focus on states that:
1. Affect ethical obligations or decision-making
2. Create constraints or enable actions
3. Change the evaluation of professional conduct
4. Represent significant contextual conditions
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
        """Parse raw individual data into StateIndividual objects"""
        individuals = []

        for raw in raw_individuals:
            try:
                individual = StateIndividual(
                    identifier=raw.get('identifier', 'Unknown State Instance'),
                    state_class=raw.get('state_class', 'State'),
                    active_period=raw.get('active_period', ''),
                    triggering_event=raw.get('triggering_event', ''),
                    affected_parties=raw.get('affected_parties', []),
                    case_section=section_type,
                    confidence=raw.get('confidence', 0.8),
                    is_new_state_class=not raw.get('is_existing_class', True)
                )
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