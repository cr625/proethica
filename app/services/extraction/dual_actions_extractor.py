"""
Dual Actions Extractor - Discovers both new action classes and individual action instances

This service extracts:
1. NEW ACTION CLASSES: Novel volitional action types not in existing ontology
2. ACTION INDIVIDUALS: Specific actions performed in cases with temporal properties

Based on Chapter 2 Section 2.2.6 literature:
- Actions are volitional professional interventions (Abbott 2020, Sarmiento et al. 2023)
- Actions fulfill obligations while requiring deliberate choice
- Actions have temporal constraints and causal implications
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from app.services.external_mcp_client import get_external_mcp_client
from app.utils.llm_utils import extract_json_from_response
from models import ModelConfig

logger = logging.getLogger(__name__)

@dataclass
class CandidateActionClass:
    """Represents a potentially new action class for temporal dynamics"""
    label: str
    definition: str
    action_category: str  # decision, intervention, communication, review, authorization
    volitional_requirement: str  # What deliberate choice is required
    professional_context: str  # Professional scope and authority needed
    obligations_fulfilled: List[str]  # What obligations this action fulfills
    temporal_constraints: List[str]  # When this action must/can be performed
    causal_implications: List[str]  # What this action typically causes
    intention_requirement: str  # Required intention for ethical validity
    examples_from_case: List[str]  # How this action appears in the case
    discovered_in_case: int
    confidence: float
    similarity_to_existing: float = 0.0
    existing_similar_classes: List[str] = None
    source_text: Optional[str] = None  # Text snippet where this action is identified

@dataclass
class ActionIndividual:
    """Represents a specific action performed in a case with temporal properties"""
    identifier: str  # e.g., "EngineerL_ReportViolation_Month3"
    action_class: str  # URI of the action class it instantiates
    performed_by: str  # Who performed this action
    performed_on: Optional[str]  # What/who the action was performed on
    temporal_interval: str  # When the action occurred (Allen interval)
    duration: Optional[str]  # How long the action took
    sequence_order: Optional[int]  # Order in sequence of actions
    causal_triggers: List[str]  # What events caused this action
    causal_results: List[str]  # What events resulted from this action
    allen_relations: List[Dict[str, str]]  # Temporal relations to other actions/events
    obligations_fulfilled: List[str]  # Specific obligations this action fulfills
    constraints_respected: List[str]  # Constraints that limit this action
    capabilities_required: List[str]  # Capabilities needed to perform this action
    case_context: str  # Context within the case
    confidence: float
    is_new_action_class: bool = False
    source_text: Optional[str] = None  # Text snippet where this action is mentioned


class DualActionsExtractor:
    """Extract both new action classes and individual action instances"""

    def __init__(self, llm_client=None):
        """
        Initialize the dual actions extractor.

        Args:
            llm_client: Optional LLM client for dependency injection (used in testing).
                       If None and MOCK_LLM_ENABLED=true, uses mock client.
                       Otherwise uses the default LLM client from llm_utils.
        """
        # Use mock provider to get appropriate client (mock if enabled, None otherwise)
        from app.services.extraction.mock_llm_provider import (
            get_llm_client_for_extraction,
            get_current_data_source,
            DataSource
        )
        self.llm_client = get_llm_client_for_extraction(llm_client)
        self.data_source = get_current_data_source()
        self.mcp_client = get_external_mcp_client()
        self.existing_action_classes = self._load_existing_action_classes()
        # Use Sonnet (default) instead of Opus (powerful) - Opus times out on long extractions
        self.model_name = ModelConfig.get_claude_model("default")
        self.last_raw_response = None  # CRITICAL for RDF conversion
        self.last_prompt = None  # Store the prompt sent to LLM

    def extract_dual_actions(self, case_text: str, case_id: int, section_type: str) -> Tuple[
        List[CandidateActionClass], List[ActionIndividual]
    ]:
        """
        Extract both new action classes and individual action instances from case text

        Returns:
            Tuple of (candidate_action_classes, action_individuals)

        Raises:
            ExtractionError: If LLM call fails (NOT silently caught)
        """
        # Store section_type for mock client lookup
        self._current_section_type = section_type

        # 1. Generate dual extraction prompt
        prompt = self._create_dual_actions_extraction_prompt(case_text, section_type)

        # 2. Call LLM for dual extraction - errors will propagate, NOT be swallowed
        extraction_result = self._call_llm_for_dual_extraction(prompt)

        # 3. Parse and validate results
        candidate_action_classes = self._parse_candidate_action_classes(
            extraction_result.get('new_action_classes', []), case_id
        )
        action_individuals = self._parse_action_individuals(
            extraction_result.get('action_individuals', []), case_id, section_type
        )

        # 4. Cross-reference: link individuals to new classes if applicable
        self._link_individuals_to_new_classes(action_individuals, candidate_action_classes)

        logger.info(f"Extracted {len(candidate_action_classes)} candidate action classes, "
                   f"{len(action_individuals)} action individuals from case {case_id} (source: {self.data_source.value})")

        return candidate_action_classes, action_individuals

    def get_last_raw_response(self) -> Optional[str]:
        """Return the raw LLM response for RDF conversion"""
        return self.last_raw_response

    def _load_existing_action_classes(self) -> List[Dict[str, Any]]:
        """Load existing action classes from proethica-intermediate via MCP"""
        try:
            existing_actions = self.mcp_client.get_all_action_entities()
            logger.info(f"Retrieved {len(existing_actions)} existing actions from MCP for dual extraction context")
            return existing_actions
        except Exception as e:
            logger.error(f"Error loading existing action classes: {e}")
            return []

    def _create_dual_actions_extraction_prompt(self, case_text: str, section_type: str) -> str:
        """Create prompt for extracting both new action classes and individual action instances"""

        existing_actions_text = self._format_existing_actions_for_prompt()

        return f"""
ACTIONS EXTRACTION - Pass 3 Temporal Dynamics (Volitional Interventions)

THEORETICAL CONTEXT (Chapter 2.2.6):
- Actions are VOLITIONAL professional interventions requiring deliberate choice (Abbott 2020, Sarmiento et al. 2023)
- Actions fulfill obligations while requiring intentional reasoning
- Actions differ from Events: Actions are choices BY agents; Events are occurrences AFFECTING agents
- Actions have temporal constraints and create causal consequences

EXISTING ACTION CLASSES IN ONTOLOGY:
{existing_actions_text}

=== TASK ===
From the following case text ({section_type} section), extract ACTIONS at TWO levels:

LEVEL 1 - NEW ACTION CLASSES: Identify volitional action types that appear to be NEW, not covered by existing classes above.
Look for:
- Professional interventions requiring deliberate choice
- Volitional decisions with ethical implications
- Actions that fulfill professional obligations
- Interventions that create causal consequences

For each NEW action class, provide:
- label: Clear action name (e.g., "Emergency Work Suspension", "Stakeholder Notification")
- definition: What professional intervention this action represents
- action_category: decision/intervention/communication/review/authorization
- volitional_requirement: What deliberate choice is required
- professional_context: What professional authority/scope is needed
- obligations_fulfilled: What professional obligations this action fulfills
- temporal_constraints: When this action must/can be performed
- causal_implications: What this action typically causes
- intention_requirement: Required intention for ethical validity
- examples_from_case: How this action appears in the case text

LEVEL 2 - ACTION INDIVIDUALS: Identify specific instances where actions are performed. For each instance:
- identifier: Unique identifier (e.g., "EngineerL_SuspendWork_Month3")
- action_class: Which action class it instantiates (use existing classes when possible)
- performed_by: Who performed this action
- performed_on: What/who the action was performed on
- temporal_interval: When the action occurred
- duration: How long the action took
- sequence_order: Order in sequence of actions (1, 2, 3...)
- causal_triggers: What events caused this action
- causal_results: What events resulted from this action
- allen_relations: Temporal relations to other actions/events
- obligations_fulfilled: Specific obligations this action fulfills
- constraints_respected: Constraints that limit this action
- capabilities_required: Capabilities needed to perform this action

CRITICAL DISTINCTION FROM EVENTS:
- If text emphasizes DECISION/CHOICE/INTENTION/DELIBERATION -> Extract as Action
- If text emphasizes OCCURRENCE/HAPPENING/TRIGGER/CONSEQUENCE -> That's an Event (extracted separately)
- Example: 'Engineer decides to report' (Action) vs 'Report is filed' (Event)

CASE TEXT:
{case_text}

Respond with valid JSON in this format:
{{
    "new_action_classes": [
        {{
            "label": "Emergency Work Suspension",
            "definition": "Professional action to immediately halt work when safety risks are identified",
            "action_category": "intervention",
            "volitional_requirement": "Deliberate choice to prioritize safety over schedule",
            "professional_context": "Engineering authority to stop work for safety reasons",
            "obligations_fulfilled": ["Public Safety Obligation", "Professional Competence Obligation"],
            "temporal_constraints": ["Must occur immediately upon risk identification", "Cannot be delayed"],
            "causal_implications": ["Project delays", "Additional safety measures required"],
            "intention_requirement": "Intent to protect public safety and professional integrity",
            "examples_from_case": ["Engineer suspended work when foundation issues discovered"],
            "source_text": "EXACT text snippet from case where this action is identified (max 200 characters)",
            "confidence": 0.85
        }}
    ],
    "action_individuals": [
        {{
            "identifier": "EngineerL_SuspendWork_Month3",
            "action_class": "Emergency Work Suspension",
            "performed_by": "Engineer L",
            "performed_on": "Construction Project X",
            "temporal_interval": "Month 3, Week 2",
            "duration": "Immediate (ongoing until resolved)",
            "sequence_order": 2,
            "causal_triggers": ["SafetyRisk_Identified_Month3"],
            "causal_results": ["ProjectDelay_Month3", "SafetyReview_Initiated"],
            "allen_relations": [
                {{"relation": "after", "target": "SafetyRisk_Identified_Month3"}},
                {{"relation": "before", "target": "SafetyReview_Initiated"}}
            ],
            "obligations_fulfilled": ["Public Safety Obligation"],
            "constraints_respected": ["Safety Constraint", "Professional Authority Constraint"],
            "capabilities_required": ["Safety Assessment", "Professional Judgment"],
            "source_text": "EXACT text snippet from case where this action is mentioned (max 200 characters)",
            "confidence": 0.85
        }}
    ]
}}
"""

    def _format_existing_actions_for_prompt(self) -> str:
        """Format existing action classes for inclusion in prompt"""
        # Defensive check - ensure we have a list
        if self.existing_action_classes is None:
            self.existing_action_classes = []
        if not self.existing_action_classes:
            return "No existing action classes loaded."

        formatted_actions = []
        for action in self.existing_action_classes[:10]:  # Limit to avoid prompt length issues
            label = action.get('label', 'Unknown')
            # Handle None values from OntServe entities
            description = action.get('description') or action.get('comment') or ''
            description = description[:150] if description else ''
            formatted_actions.append(f"- {label}: {description}")

        return "\n".join(formatted_actions)

    def _call_llm_for_dual_extraction(self, prompt: str) -> Dict[str, Any]:
        """Call LLM with dual extraction prompt"""
        from app.services.extraction.mock_llm_provider import (
            LLMConnectionError, LLMResponseError
        )

        # Store prompt for later retrieval
        self.last_prompt = prompt

        try:
            # Use injected client if available (for testing), otherwise get default
            if self.llm_client is not None:
                # Mock client - call with extraction type for fixture lookup
                response = self.llm_client.call(
                    prompt=prompt,
                    extraction_type='actions',
                    section_type=getattr(self, '_current_section_type', 'temporal')
                )
                response_text = response.content if hasattr(response, 'content') else str(response)
                self.last_raw_response = response_text
                try:
                    return extract_json_from_response(response_text)
                except ValueError as e:
                    raise LLMResponseError(f"Could not parse JSON from LLM response: {str(e)}")

            # Import the LLM client getter
            try:
                from app.utils.llm_utils import get_llm_client
            except ImportError as e:
                raise LLMConnectionError(f"Could not import get_llm_client: {e}")

            client = get_llm_client()
            if not client:
                raise LLMConnectionError("No LLM client available for actions extraction")

            # Call the LLM
            response = client.messages.create(
                model=self.model_name,
                max_tokens=4000,
                temperature=0.7,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Store the raw response for RDF conversion
            response_text = response.content[0].text if response.content else ""
            self.last_raw_response = response_text

            # Parse JSON from response
            try:
                return extract_json_from_response(response_text)
            except ValueError as e:
                raise LLMResponseError(f"Could not parse JSON from LLM response: {str(e)}")

        except (LLMConnectionError, LLMResponseError):
            raise
        except Exception as e:
            error_msg = str(e).lower()
            # Re-raise connection errors so pipeline can handle them properly
            if 'connection' in error_msg or 'timeout' in error_msg or 'api' in error_msg:
                logger.error(f"API connection error for actions extraction: {e}")
                raise LLMConnectionError(f"LLM API connection failed: {e}") from e
            raise LLMResponseError(f"Actions extraction failed: {e}") from e

    def _parse_candidate_action_classes(self, raw_classes: List[Dict], case_id: int) -> List[CandidateActionClass]:
        """Parse raw action class data into CandidateActionClass objects"""
        candidates = []

        for raw_class in raw_classes:
            try:
                # Get source_text from LLM response, or fall back to first example
                source_text = raw_class.get('source_text')
                if not source_text and raw_class.get('examples_from_case'):
                    source_text = raw_class.get('examples_from_case', [''])[0]

                candidate = CandidateActionClass(
                    label=raw_class.get('label', 'Unknown Action'),
                    definition=raw_class.get('definition', ''),
                    action_category=raw_class.get('action_category', 'intervention'),
                    volitional_requirement=raw_class.get('volitional_requirement', ''),
                    professional_context=raw_class.get('professional_context', ''),
                    obligations_fulfilled=raw_class.get('obligations_fulfilled', []),
                    temporal_constraints=raw_class.get('temporal_constraints', []),
                    causal_implications=raw_class.get('causal_implications', []),
                    intention_requirement=raw_class.get('intention_requirement', ''),
                    examples_from_case=raw_class.get('examples_from_case', []),
                    discovered_in_case=case_id,
                    confidence=raw_class.get('confidence', 0.85),
                    similarity_to_existing=0.0,
                    existing_similar_classes=[],
                    source_text=source_text
                )

                # Calculate similarity to existing actions
                self._calculate_action_similarity(candidate)

                candidates.append(candidate)

            except Exception as e:
                logger.error(f"Error parsing action class: {e}")
                continue

        return candidates

    def _parse_action_individuals(self, raw_individuals: List[Dict], case_id: int, section_type: str) -> List[ActionIndividual]:
        """Parse raw action individual data into ActionIndividual objects"""
        individuals = []

        for raw_ind in raw_individuals:
            try:
                individual = ActionIndividual(
                    identifier=raw_ind.get('identifier', f'Action_{case_id}_{len(individuals)}'),
                    action_class=raw_ind.get('action_class', 'Unknown'),
                    performed_by=raw_ind.get('performed_by', ''),
                    performed_on=raw_ind.get('performed_on', None),
                    temporal_interval=raw_ind.get('temporal_interval', ''),
                    duration=raw_ind.get('duration', None),
                    sequence_order=raw_ind.get('sequence_order', None),
                    causal_triggers=raw_ind.get('causal_triggers', []),
                    causal_results=raw_ind.get('causal_results', []),
                    allen_relations=raw_ind.get('allen_relations', []),
                    obligations_fulfilled=raw_ind.get('obligations_fulfilled', []),
                    constraints_respected=raw_ind.get('constraints_respected', []),
                    capabilities_required=raw_ind.get('capabilities_required', []),
                    case_context=section_type,
                    confidence=raw_ind.get('confidence', 0.85),
                    is_new_action_class=False,
                    source_text=raw_ind.get('source_text')
                )
                individuals.append(individual)

            except Exception as e:
                logger.error(f"Error parsing action individual: {e}")
                continue

        return individuals

    def _calculate_action_similarity(self, candidate: CandidateActionClass):
        """Calculate similarity between candidate and existing action classes"""
        if not self.existing_action_classes:
            return

        # Simple label-based similarity for now
        candidate_label_lower = candidate.label.lower()
        similar_classes = []

        for existing in self.existing_action_classes:
            existing_label = existing.get('label', '').lower()
            if (candidate_label_lower in existing_label or
                existing_label in candidate_label_lower or
                any(word in existing_label for word in candidate_label_lower.split())):
                similar_classes.append(existing.get('label', 'Unknown'))

        if similar_classes:
            candidate.similarity_to_existing = 0.8  # High similarity if label matches
            candidate.existing_similar_classes = similar_classes[:3]
        else:
            candidate.similarity_to_existing = 0.0

    def _link_individuals_to_new_classes(self, action_individuals: List[ActionIndividual],
                                        candidate_action_classes: List[CandidateActionClass]):
        """Link individuals to newly discovered classes"""
        action_candidate_labels = {c.label for c in candidate_action_classes}

        for individual in action_individuals:
            if individual.action_class in action_candidate_labels:
                individual.is_new_action_class = True
