"""
Dual Events Extractor - Discovers both new event classes and individual event instances

This service extracts:
1. NEW EVENT CLASSES: Novel temporal occurrence types not in existing ontology
2. EVENT INDIVIDUALS: Specific events that occurred in cases with temporal properties

Based on Chapter 2 Section 2.2.7 literature:
- Events are temporal occurrences triggering ethical considerations (Berreby et al. 2017)
- Events trigger state changes and activate obligations
- Events differ from Actions: Events are occurrences AFFECTING agents; Actions are choices BY agents
- Events form causal chains with actions in ethical narratives
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from app.services.external_mcp_client import get_external_mcp_client
from models import ModelConfig

logger = logging.getLogger(__name__)

@dataclass
class CandidateEventClass:
    """Represents a potentially new event class for temporal dynamics"""
    label: str
    definition: str
    event_category: str  # triggering, outcome, milestone, emergency, discovery
    temporal_marker: str  # What temporal transition this event marks
    automatic_nature: str  # How this event occurs without volition
    constraint_activation: List[str]  # What constraints this event activates
    obligation_transformation: str  # How this event changes obligations
    causal_position: str  # Position in causal chains (trigger, intermediate, outcome)
    ethical_salience: str  # Why this event is ethically significant
    state_transitions: List[str]  # What state changes this event causes
    examples_from_case: List[str]  # How this event appears in the case
    discovered_in_case: int
    confidence: float
    similarity_to_existing: float = 0.0
    existing_similar_classes: List[str] = None
    source_text: Optional[str] = None  # Text snippet where this event is identified

@dataclass
class EventIndividual:
    """Represents a specific event that occurred in a case with temporal properties"""
    identifier: str  # e.g., "SafetyRisk_Identified_Month2"
    event_class: str  # URI of the event class it instantiates
    occurred_to: Optional[str]  # What/who the event happened to
    discovered_by: Optional[str]  # Who discovered/observed this event
    temporal_interval: str  # When the event occurred (Allen interval)
    duration: Optional[str]  # How long the event lasted
    sequence_order: Optional[int]  # Order in sequence of events
    causal_triggers: List[str]  # What actions/events caused this event
    causal_results: List[str]  # What actions/events resulted from this event
    allen_relations: List[Dict[str, str]]  # Temporal relations to other actions/events
    constraints_activated: List[str]  # Constraints this event activated
    obligations_triggered: List[str]  # Obligations this event triggered
    states_changed: List[str]  # States that changed due to this event
    case_context: str  # Context within the case
    confidence: float
    is_new_event_class: bool = False
    source_text: Optional[str] = None  # Text snippet where this event is mentioned


class DualEventsExtractor:
    """Extract both new event classes and individual event instances"""

    def __init__(self, llm_client=None):
        """
        Initialize the dual events extractor.

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
        self.existing_event_classes = self._load_existing_event_classes()
        # Use Sonnet (default) instead of Opus (powerful) - Opus times out on long extractions
        self.model_name = ModelConfig.get_claude_model("default")
        self.last_raw_response = None  # CRITICAL for RDF conversion
        self.last_prompt = None  # Store the prompt sent to LLM

    def extract_dual_events(self, case_text: str, case_id: int, section_type: str) -> Tuple[
        List[CandidateEventClass], List[EventIndividual]
    ]:
        """
        Extract both new event classes and individual event instances from case text

        Returns:
            Tuple of (candidate_event_classes, event_individuals)

        Raises:
            ExtractionError: If LLM call fails (NOT silently caught)
        """
        # Store section_type for mock client lookup
        self._current_section_type = section_type

        # 1. Generate dual extraction prompt
        prompt = self._create_dual_events_extraction_prompt(case_text, section_type)

        # 2. Call LLM for dual extraction - errors will propagate, NOT be swallowed
        extraction_result = self._call_llm_for_dual_extraction(prompt)

        # 3. Parse and validate results
        candidate_event_classes = self._parse_candidate_event_classes(
            extraction_result.get('new_event_classes', []), case_id
        )
        event_individuals = self._parse_event_individuals(
            extraction_result.get('event_individuals', []), case_id, section_type
        )

        # 4. Cross-reference: link individuals to new classes if applicable
        self._link_individuals_to_new_classes(event_individuals, candidate_event_classes)

        logger.info(f"Extracted {len(candidate_event_classes)} candidate event classes, "
                   f"{len(event_individuals)} event individuals from case {case_id} (source: {self.data_source.value})")

        return candidate_event_classes, event_individuals

    def get_last_raw_response(self) -> Optional[str]:
        """Return the raw LLM response for RDF conversion"""
        return self.last_raw_response

    def _load_existing_event_classes(self) -> List[Dict[str, Any]]:
        """Load existing event classes from proethica-intermediate via MCP"""
        try:
            existing_events = self.mcp_client.get_all_event_entities()
            logger.info(f"Retrieved {len(existing_events)} existing events from MCP for dual extraction context")
            return existing_events
        except Exception as e:
            logger.error(f"Error loading existing event classes: {e}")
            return []

    def _create_dual_events_extraction_prompt(self, case_text: str, section_type: str) -> str:
        """Create prompt for extracting both new event classes and individual event instances"""

        existing_events_text = self._format_existing_events_for_prompt()

        return f"""
EVENTS EXTRACTION - Pass 3 Temporal Dynamics (Temporal Occurrences)

THEORETICAL CONTEXT (Chapter 2.2.7):
- Events are TEMPORAL OCCURRENCES that trigger ethical considerations (Berreby et al. 2017, Zhang et al. 2023)
- Events include both consequences of actions and external occurrences
- Events differ from Actions: Events are occurrences AFFECTING agents; Actions are choices BY agents
- Events trigger state changes and activate professional obligations
- Events form causal chains in ethical narratives

EXISTING EVENT CLASSES IN ONTOLOGY:
{existing_events_text}

=== TASK ===
From the following case text ({section_type} section), extract EVENTS at TWO levels:

LEVEL 1 - NEW EVENT CLASSES: Identify temporal occurrence types that appear to be NEW, not covered by existing classes above.
Look for:
- Occurrences that trigger ethical considerations
- Temporal markers that change professional obligations
- Automatic events that activate constraints
- State transitions requiring professional response

For each NEW event class, provide:
- label: Clear event name (e.g., "Safety Risk Discovery", "Client Financial Crisis")
- definition: What temporal occurrence this event represents
- event_category: triggering/outcome/milestone/emergency/discovery
- temporal_marker: What temporal transition this event marks
- automatic_nature: How this event occurs without volition
- constraint_activation: What constraints this event activates
- obligation_transformation: How this event changes obligations
- causal_position: Position in causal chains (trigger/intermediate/outcome)
- ethical_salience: Why this event is ethically significant
- state_transitions: What state changes this event causes
- examples_from_case: How this event appears in the case text

LEVEL 2 - EVENT INDIVIDUALS: Identify specific instances where events occurred. For each instance:
- identifier: Unique identifier (e.g., "SafetyRisk_Identified_Month2")
- event_class: Which event class it instantiates (use existing classes when possible)
- occurred_to: What/who the event happened to
- discovered_by: Who discovered/observed this event
- temporal_interval: When the event occurred
- duration: How long the event lasted
- sequence_order: Order in sequence of events (1, 2, 3...)
- causal_triggers: What actions/events caused this event
- causal_results: What actions/events resulted from this event
- allen_relations: Temporal relations to other actions/events
- constraints_activated: Constraints this event activated
- obligations_triggered: Obligations this event triggered
- states_changed: States that changed due to this event

CRITICAL DISTINCTION FROM ACTIONS:
- If text emphasizes OCCURRENCE/HAPPENING/TRIGGER/DISCOVERY -> Extract as Event
- If text emphasizes DECISION/CHOICE/INTENTION/DELIBERATION -> That's an Action (extracted separately)
- Example: 'Report is filed' (Event) vs 'Engineer decides to report' (Action)
- External occurrences without agent volition -> Always extract as Event

EVENT TYPES TO IDENTIFY:
1. Crisis Events: failures, accidents, emergencies (the occurrence, not the response)
2. Compliance Events: violations discovered, breaches detected (the discovery event)
3. Conflict Events: disputes arising, disagreements emerging (the emergence)
4. Project Events: deadlines reached, milestones achieved (the temporal occurrence)
5. Safety Events: incidents occurring, harm manifesting (the actual occurrence)
6. Evaluation Events: audits conducted, inspections performed (the event of being evaluated)
7. Discovery Events: findings revealed, detections made (the moment of discovery)
8. Change Events: modifications implemented, updates applied (the occurrence of change)

CASE TEXT:
{case_text}

Respond with valid JSON in this format:
{{
    "new_event_classes": [
        {{
            "label": "Safety Risk Discovery",
            "definition": "Event where a previously unknown safety hazard becomes known",
            "event_category": "discovery",
            "temporal_marker": "Marks transition from unknown risk to known risk requiring response",
            "automatic_nature": "Occurs through inspection, observation, or testing activities",
            "constraint_activation": ["Immediate Response Required", "Documentation Required"],
            "obligation_transformation": "Activates duty to report and duty to mitigate",
            "causal_position": "trigger",
            "ethical_salience": "Creates professional duty to protect public safety",
            "state_transitions": ["Normal Operations -> Risk Response Mode"],
            "examples_from_case": ["Foundation issues were discovered during inspection"],
            "source_text": "EXACT text snippet from case where this event is identified (max 200 characters)",
            "confidence": 0.85
        }}
    ],
    "event_individuals": [
        {{
            "identifier": "FoundationRisk_Discovered_Month3",
            "event_class": "Safety Risk Discovery",
            "occurred_to": "Project X Foundation",
            "discovered_by": "Engineer L during inspection",
            "temporal_interval": "Month 3, Week 1",
            "duration": "Instantaneous discovery, ongoing situation",
            "sequence_order": 1,
            "causal_triggers": ["Routine inspection conducted"],
            "causal_results": ["EngineerL_SuspendWork_Month3", "SafetyReview_Initiated"],
            "allen_relations": [
                {{"relation": "before", "target": "EngineerL_SuspendWork_Month3"}},
                {{"relation": "meets", "target": "SafetyReview_Initiated"}}
            ],
            "constraints_activated": ["Safety Stop Work Authority", "Immediate Reporting"],
            "obligations_triggered": ["Duty to Report", "Duty to Protect Public"],
            "states_changed": ["Project Safety State", "Engineer's Professional State"],
            "source_text": "EXACT text snippet from case where this event is mentioned (max 200 characters)",
            "confidence": 0.85
        }}
    ]
}}
"""

    def _format_existing_events_for_prompt(self) -> str:
        """Format existing event classes for inclusion in prompt"""
        if not self.existing_event_classes:
            return "No existing event classes loaded."

        formatted_events = []
        for event in self.existing_event_classes[:10]:  # Limit to avoid prompt length issues
            label = event.get('label', 'Unknown')
            description = event.get('description', event.get('comment', ''))[:150]
            formatted_events.append(f"- {label}: {description}")

        return "\n".join(formatted_events)

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
                    extraction_type='events',
                    section_type=getattr(self, '_current_section_type', 'temporal')
                )
                response_text = response.content if hasattr(response, 'content') else str(response)
                self.last_raw_response = response_text
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', response_text)
                    if json_match:
                        return json.loads(json_match.group())
                    raise LLMResponseError(f"Could not parse JSON from response: {response_text[:200]}")

            # Import the LLM client getter
            try:
                from app.utils.llm_utils import get_llm_client
            except ImportError as e:
                raise LLMConnectionError(f"Could not import get_llm_client: {e}")

            client = get_llm_client()
            if not client:
                raise LLMConnectionError("No LLM client available for events extraction")

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
            self.last_raw_response = response.content[0].text if response.content else ""

            # Parse JSON from response
            response_text = response.content[0].text if response.content else ""

            # Try to extract JSON from the response
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # Try to find JSON in the response
                import re
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    raise LLMResponseError(f"Could not extract JSON from LLM response: {response_text[:200]}")

            return result

        except (LLMConnectionError, LLMResponseError):
            raise
        except Exception as e:
            error_msg = str(e).lower()
            # Re-raise connection errors so pipeline can handle them properly
            if 'connection' in error_msg or 'timeout' in error_msg or 'api' in error_msg:
                logger.error(f"API connection error for events extraction: {e}")
                raise LLMConnectionError(f"LLM API connection failed: {e}") from e
            raise LLMResponseError(f"Events extraction failed: {e}") from e

    def _parse_candidate_event_classes(self, raw_classes: List[Dict], case_id: int) -> List[CandidateEventClass]:
        """Parse raw event class data into CandidateEventClass objects"""
        candidates = []

        for raw_class in raw_classes:
            try:
                # Get source_text from LLM response, or fall back to first example
                source_text = raw_class.get('source_text')
                if not source_text and raw_class.get('examples_from_case'):
                    source_text = raw_class.get('examples_from_case', [''])[0]

                candidate = CandidateEventClass(
                    label=raw_class.get('label', 'Unknown Event'),
                    definition=raw_class.get('definition', ''),
                    event_category=raw_class.get('event_category', 'discovery'),
                    temporal_marker=raw_class.get('temporal_marker', ''),
                    automatic_nature=raw_class.get('automatic_nature', ''),
                    constraint_activation=raw_class.get('constraint_activation', []),
                    obligation_transformation=raw_class.get('obligation_transformation', ''),
                    causal_position=raw_class.get('causal_position', 'intermediate'),
                    ethical_salience=raw_class.get('ethical_salience', ''),
                    state_transitions=raw_class.get('state_transitions', []),
                    examples_from_case=raw_class.get('examples_from_case', []),
                    discovered_in_case=case_id,
                    confidence=raw_class.get('confidence', 0.85),
                    similarity_to_existing=0.0,
                    existing_similar_classes=[],
                    source_text=source_text
                )

                # Calculate similarity to existing events
                self._calculate_event_similarity(candidate)

                candidates.append(candidate)

            except Exception as e:
                logger.error(f"Error parsing event class: {e}")
                continue

        return candidates

    def _parse_event_individuals(self, raw_individuals: List[Dict], case_id: int, section_type: str) -> List[EventIndividual]:
        """Parse raw event individual data into EventIndividual objects"""
        individuals = []

        for raw_ind in raw_individuals:
            try:
                individual = EventIndividual(
                    identifier=raw_ind.get('identifier', f'Event_{case_id}_{len(individuals)}'),
                    event_class=raw_ind.get('event_class', 'Unknown'),
                    occurred_to=raw_ind.get('occurred_to', None),
                    discovered_by=raw_ind.get('discovered_by', None),
                    temporal_interval=raw_ind.get('temporal_interval', ''),
                    duration=raw_ind.get('duration', None),
                    sequence_order=raw_ind.get('sequence_order', None),
                    causal_triggers=raw_ind.get('causal_triggers', []),
                    causal_results=raw_ind.get('causal_results', []),
                    allen_relations=raw_ind.get('allen_relations', []),
                    constraints_activated=raw_ind.get('constraints_activated', []),
                    obligations_triggered=raw_ind.get('obligations_triggered', []),
                    states_changed=raw_ind.get('states_changed', []),
                    case_context=section_type,
                    confidence=raw_ind.get('confidence', 0.85),
                    is_new_event_class=False,
                    source_text=raw_ind.get('source_text')
                )
                individuals.append(individual)

            except Exception as e:
                logger.error(f"Error parsing event individual: {e}")
                continue

        return individuals

    def _calculate_event_similarity(self, candidate: CandidateEventClass):
        """Calculate similarity between candidate and existing event classes"""
        if not self.existing_event_classes:
            return

        # Simple label-based similarity for now
        candidate_label_lower = candidate.label.lower()
        similar_classes = []

        for existing in self.existing_event_classes:
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

    def _link_individuals_to_new_classes(self, event_individuals: List[EventIndividual],
                                        candidate_event_classes: List[CandidateEventClass]):
        """Link individuals to newly discovered classes"""
        event_candidate_labels = {c.label for c in candidate_event_classes}

        for individual in event_individuals:
            if individual.event_class in event_candidate_labels:
                individual.is_new_event_class = True
