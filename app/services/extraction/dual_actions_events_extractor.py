"""
Dual Actions & Events Extractor - Discovers both new temporal classes and individual temporal instances

This service extracts:
1. NEW ACTION CLASSES: Novel volitional action types not in existing ontology
2. ACTION INDIVIDUALS: Specific actions performed in cases with temporal properties
3. NEW EVENT CLASSES: Novel temporal occurrence types not in existing ontology
4. EVENT INDIVIDUALS: Specific events that occurred in cases with temporal properties

Based on Chapter 2 Sections 2.2.6-2.2.7 literature:
- Actions are volitional professional interventions (Abbott 2020, Sarmiento et al. 2023)
- Events are temporal occurrences triggering ethical considerations (Berreby et al. 2017)
- Temporal dynamics require Allen's interval algebra for sequence understanding
- Causal chains connect actions and events in ethical narratives
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from app.services.external_mcp_client import get_external_mcp_client
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

class DualActionsEventsExtractor:
    """Extract both new temporal classes and individual temporal instances"""

    def __init__(self):
        self.mcp_client = get_external_mcp_client()
        self.existing_action_classes = self._load_existing_action_classes()
        self.existing_event_classes = self._load_existing_event_classes()
        self.model_name = ModelConfig.get_claude_model("powerful")
        self.last_raw_response = None  # CRITICAL for RDF conversion

    def extract_dual_actions_events(self, case_text: str, case_id: int, section_type: str) -> Tuple[
        List[CandidateActionClass], List[ActionIndividual],
        List[CandidateEventClass], List[EventIndividual]
    ]:
        """
        Extract both new temporal classes and individual temporal instances from case text

        Returns:
            Tuple of (candidate_action_classes, action_individuals, candidate_event_classes, event_individuals)
        """
        try:
            # 1. Generate dual extraction prompt
            prompt = self._create_dual_temporal_extraction_prompt(case_text, section_type)

            # 2. Call LLM for dual extraction
            extraction_result = self._call_llm_for_dual_extraction(prompt)

            # 3. Parse and validate results
            candidate_action_classes = self._parse_candidate_action_classes(
                extraction_result.get('new_action_classes', []), case_id
            )
            action_individuals = self._parse_action_individuals(
                extraction_result.get('action_individuals', []), case_id, section_type
            )
            candidate_event_classes = self._parse_candidate_event_classes(
                extraction_result.get('new_event_classes', []), case_id
            )
            event_individuals = self._parse_event_individuals(
                extraction_result.get('event_individuals', []), case_id, section_type
            )

            # 4. Cross-reference: link individuals to new classes if applicable
            self._link_individuals_to_new_classes(
                action_individuals, candidate_action_classes,
                event_individuals, candidate_event_classes
            )

            # 5. Extract temporal relationships using Allen's interval algebra
            self._extract_temporal_relationships(action_individuals, event_individuals)

            logger.info(f"Extracted {len(candidate_action_classes)} candidate action classes, "
                       f"{len(action_individuals)} action individuals, "
                       f"{len(candidate_event_classes)} candidate event classes, "
                       f"{len(event_individuals)} event individuals from case {case_id}")

            return candidate_action_classes, action_individuals, candidate_event_classes, event_individuals

        except Exception as e:
            logger.error(f"Error in dual actions/events extraction: {e}")
            return [], [], [], []

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

    def _load_existing_event_classes(self) -> List[Dict[str, Any]]:
        """Load existing event classes from proethica-intermediate via MCP"""
        try:
            existing_events = self.mcp_client.get_all_event_entities()
            logger.info(f"Retrieved {len(existing_events)} existing events from MCP for dual extraction context")
            return existing_events
        except Exception as e:
            logger.error(f"Error loading existing event classes: {e}")
            return []

    def _create_dual_temporal_extraction_prompt(self, case_text: str, section_type: str) -> str:
        """Create prompt for extracting both new temporal classes and individual temporal instances"""

        existing_actions_text = self._format_existing_actions_for_prompt()
        existing_events_text = self._format_existing_events_for_prompt()

        return f"""
DUAL TEMPORAL EXTRACTION - Actions & Events Analysis with Allen's Interval Algebra

THEORETICAL CONTEXT (Chapter 2.2.6-2.2.7):
- Actions are VOLITIONAL professional interventions requiring deliberate choice (Abbott 2020, Sarmiento et al. 2023)
- Events are TEMPORAL occurrences that trigger ethical considerations (Berreby et al. 2017)
- Temporal dynamics use Allen's 13 interval relations: before, after, meets, overlaps, during, starts, finishes, equals
- Causal chains connect actions and events in ethical narratives
- Actions fulfill obligations while events trigger obligations

EXISTING ACTION CLASSES IN ONTOLOGY:
{existing_actions_text}

EXISTING EVENT CLASSES IN ONTOLOGY:
{existing_events_text}

=== TASK ===
From the following case text ({section_type} section), extract information at FOUR levels:

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
- temporal_interval: When the action occurred (use Allen interval notation)
- duration: How long the action took
- sequence_order: Order in sequence of actions (1, 2, 3...)
- causal_triggers: What events caused this action
- causal_results: What events resulted from this action
- allen_relations: Temporal relations to other actions/events
- obligations_fulfilled: Specific obligations this action fulfills
- constraints_respected: Constraints that limit this action
- capabilities_required: Capabilities needed to perform this action

LEVEL 3 - NEW EVENT CLASSES: Identify temporal occurrence types that appear to be NEW, not covered by existing classes above.
Look for:
- Occurrences that trigger ethical considerations
- Temporal markers that change professional obligations
- Automatic events that activate constraints
- State transitions requiring professional response

For each NEW event class, provide:
- label: Clear event name (e.g., "Regulatory Deadline Approach", "Client Financial Crisis")
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

LEVEL 4 - EVENT INDIVIDUALS: Identify specific instances where events occurred. For each instance:
- identifier: Unique identifier (e.g., "FinancialCrisis_ClientX_Month2")
- event_class: Which event class it instantiates (use existing classes when possible)
- occurred_to: What/who the event happened to
- discovered_by: Who discovered/observed this event
- temporal_interval: When the event occurred (use Allen interval notation)
- duration: How long the event lasted
- sequence_order: Order in sequence of events (1, 2, 3...)
- causal_triggers: What actions/events caused this event
- causal_results: What actions/events resulted from this event
- allen_relations: Temporal relations to other actions/events
- constraints_activated: Constraints this event activated
- obligations_triggered: Obligations this event triggered
- states_changed: States that changed due to this event

ALLEN'S INTERVAL RELATIONS:
Use these 13 relations to describe temporal relationships:
- before: A finishes before B starts
- after: A starts after B finishes
- meets: A finishes exactly when B starts
- overlaps: A and B partially overlap
- during: A occurs completely within B
- starts: A and B start together but A finishes first
- finishes: A and B finish together but A starts later
- equals: A and B have same start and end times

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
            "examples_from_case": ["Engineer suspended work when foundation issues discovered"]
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
            "capabilities_required": ["Safety Assessment", "Professional Judgment"]
        }}
    ],
    "new_event_classes": [
        {{
            "label": "Client Financial Crisis",
            "definition": "Sudden financial difficulties that affect project funding and decision-making",
            "event_category": "triggering",
            "temporal_marker": "Marks shift from normal operations to crisis management mode",
            "automatic_nature": "Occurs due to external economic factors beyond project control",
            "constraint_activation": ["Budget Constraint", "Timeline Constraint"],
            "obligation_transformation": "Activates obligations to renegotiate scope while maintaining safety",
            "causal_position": "trigger",
            "ethical_salience": "Creates pressure to compromise professional standards",
            "state_transitions": ["Normal Operations → Crisis Management"],
            "examples_from_case": ["Client X faced funding shortfall affecting project scope"]
        }}
    ],
    "event_individuals": [
        {{
            "identifier": "FinancialCrisis_ClientX_Month2",
            "event_class": "Client Financial Crisis",
            "occurred_to": "Client X",
            "discovered_by": "Project Manager",
            "temporal_interval": "Month 2, Week 4",
            "duration": "Ongoing (3+ months)",
            "sequence_order": 1,
            "causal_triggers": ["Market downturn", "Investment withdrawal"],
            "causal_results": ["BudgetReduction_Requested", "ScopeRenegotiation_Initiated"],
            "allen_relations": [
                {{"relation": "before", "target": "EngineerL_SuspendWork_Month3"}},
                {{"relation": "overlaps", "target": "SafetyRisk_Identified_Month3"}}
            ],
            "constraints_activated": ["Budget Constraint", "Timeline Constraint"],
            "obligations_triggered": ["Renegotiation Obligation", "Transparency Obligation"],
            "states_changed": ["Client Relationship State", "Project Financial State"]
        }}
    ]
}}
"""

    def _format_existing_actions_for_prompt(self) -> str:
        """Format existing action classes for inclusion in prompt"""
        if not self.existing_action_classes:
            return "No existing action classes loaded."

        formatted_actions = []
        for action in self.existing_action_classes[:10]:  # Limit to avoid prompt length issues
            label = action.get('label', 'Unknown')
            description = action.get('description', action.get('comment', ''))[:150]
            formatted_actions.append(f"- {label}: {description}")

        return "\n".join(formatted_actions)

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
        try:
            # Import the LLM client getter
            try:
                from app.utils.llm_utils import get_llm_client
            except ImportError:
                logger.error("Could not import get_llm_client")
                return {"new_action_classes": [], "action_individuals": [], "new_event_classes": [], "event_individuals": []}

            client = get_llm_client()
            if not client:
                logger.error("No LLM client available for dual actions/events extraction")
                return {"new_action_classes": [], "action_individuals": [], "new_event_classes": [], "event_individuals": []}

            # Call the LLM
            response = client.messages.create(
                model=self.model_name,
                max_tokens=6000,  # Increased for combined extraction
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
                    logger.error("Could not extract JSON from LLM response")
                    return {"new_action_classes": [], "action_individuals": [], "new_event_classes": [], "event_individuals": []}

            return result

        except Exception as e:
            logger.error(f"Error calling LLM for dual actions/events extraction: {e}")
            return {"new_action_classes": [], "action_individuals": [], "new_event_classes": [], "event_individuals": []}

    def _parse_candidate_action_classes(self, raw_classes: List[Dict], case_id: int) -> List[CandidateActionClass]:
        """Parse raw action class data into CandidateActionClass objects"""
        candidates = []

        for raw_class in raw_classes:
            try:
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
                    existing_similar_classes=[]
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
                    is_new_action_class=False
                )
                individuals.append(individual)

            except Exception as e:
                logger.error(f"Error parsing action individual: {e}")
                continue

        return individuals

    def _parse_candidate_event_classes(self, raw_classes: List[Dict], case_id: int) -> List[CandidateEventClass]:
        """Parse raw event class data into CandidateEventClass objects"""
        candidates = []

        for raw_class in raw_classes:
            try:
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
                    existing_similar_classes=[]
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
                    is_new_event_class=False
                )
                individuals.append(individual)

            except Exception as e:
                logger.error(f"Error parsing event individual: {e}")
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

    def _link_individuals_to_new_classes(self, action_individuals: List[ActionIndividual],
                                        candidate_action_classes: List[CandidateActionClass],
                                        event_individuals: List[EventIndividual],
                                        candidate_event_classes: List[CandidateEventClass]):
        """Link individuals to newly discovered classes"""
        action_candidate_labels = {c.label for c in candidate_action_classes}
        event_candidate_labels = {c.label for c in candidate_event_classes}

        for individual in action_individuals:
            if individual.action_class in action_candidate_labels:
                individual.is_new_action_class = True

        for individual in event_individuals:
            if individual.event_class in event_candidate_labels:
                individual.is_new_event_class = True

    def _extract_temporal_relationships(self, action_individuals: List[ActionIndividual],
                                      event_individuals: List[EventIndividual]):
        """Extract and validate Allen's interval algebra relationships"""
        # This is a placeholder for more sophisticated temporal relationship extraction
        # In a full implementation, this would analyze the temporal intervals and
        # automatically detect Allen relations between actions and events

        all_temporal_entities = []
        for action in action_individuals:
            all_temporal_entities.append(('action', action))
        for event in event_individuals:
            all_temporal_entities.append(('event', event))

        # Sort by sequence order if available
        all_temporal_entities.sort(key=lambda x: x[1].sequence_order or 0)

        # For now, just log the temporal sequence
        logger.info(f"Extracted temporal sequence of {len(all_temporal_entities)} temporal entities")
        for entity_type, entity in all_temporal_entities:
            logger.debug(f"{entity_type}: {entity.identifier} at {entity.temporal_interval}")