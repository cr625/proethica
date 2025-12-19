"""
Timeline Constructor (Stage 4.2)

Constructs entity-grounded timelines using Berreby's Event Calculus framework.

Based on: Berreby, Bourgne & Ganascia (2017) - Event Calculus and Causal Chains

Event Calculus Concepts:
- initially(F): F is true at T=0
- occurs(S, E, T): Event E occurs at time T in simulation S
- holds(S, F, T): Fluent F holds at time T in simulation S
- initiates(S, E, F, T): Event E initiates fluent F at time T
- terminates(S, E, F, T): Event E terminates fluent F at time T
- cons(S, E, T, F): F is a consequence of event E at time T
"""

import logging
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

from app.utils.llm_utils import get_llm_client
from app.academic_references.frameworks.declarative_ethics import (
    get_event_trace_template,
    get_causal_analysis_template,
    EVENT_CALCULUS_PREDICATES
)

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

class TimelinePhase(Enum):
    """Phases of case timeline following narrative arc."""
    INITIAL = "Initial Situation"
    RISING = "Rising Action"
    CONFLICT = "Conflict Emerges"
    DECISION = "Decision Point"
    CLIMAX = "Ethical Determination"
    RESOLUTION = "Resolution"
    AFTERMATH = "Aftermath"


@dataclass
class Fluent:
    """
    A fluent (state that can change) in Event Calculus.

    From Berreby: "Fluents are states that persist until terminated."
    """
    uri: str
    label: str
    fluent_type: str = "state"  # 'state', 'obligation_active', 'constraint_binding'

    # Event Calculus status
    initially_true: bool = False
    current_value: bool = True

    # Grounding
    source_entity_uri: str = ""
    source_entity_type: str = ""

    def to_predicate(self, time_point: int, simulation: str = "case") -> str:
        """Generate Event Calculus predicate."""
        if self.initially_true and time_point == 0:
            return f"initially({self.label.replace(' ', '_')})"
        return f"holds({simulation}, {self.label.replace(' ', '_')}, {time_point})"

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class CausalLink:
    """
    A causal relationship between events/fluents.

    From Berreby's cons(S, E, T, F) predicate.
    """
    source_uri: str  # Event or fluent that causes
    source_label: str
    source_type: str  # 'event', 'fluent', 'action'

    target_uri: str  # What is caused
    target_label: str
    target_type: str  # 'event', 'fluent', 'outcome'

    link_type: str = "consequence"  # 'consequence', 'precondition', 'enables'
    confidence: float = 0.5

    def to_predicate(self, time_point: int, simulation: str = "case") -> str:
        """Generate cons() predicate."""
        return f"cons({simulation}, {self.source_label.replace(' ', '_')}, {time_point}, {self.target_label.replace(' ', '_')})"

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TimelineEvent:
    """
    An event in the entity-grounded timeline.

    Enhanced from case_synthesizer.TimelineEvent with Event Calculus support.
    """
    sequence: int
    phase: TimelinePhase
    phase_label: str

    # Core properties
    event_uri: str
    event_label: str
    description: str
    event_type: str  # 'state', 'action', 'automatic', 'decision', 'outcome'

    # Entity grounding
    entity_uris: List[str] = field(default_factory=list)
    entity_labels: List[str] = field(default_factory=list)

    # Event Calculus attributes
    agent_uri: Optional[str] = None  # Who performed (for actions)
    agent_label: Optional[str] = None
    time_point: int = 0  # T in Event Calculus

    # Fluent effects
    precondition_fluents: List[str] = field(default_factory=list)  # Fluents that must hold
    initiated_fluents: List[str] = field(default_factory=list)  # Fluents initiated
    terminated_fluents: List[str] = field(default_factory=list)  # Fluents terminated

    # Causal links
    causal_links: List[str] = field(default_factory=list)  # URIs of caused events/fluents

    def to_predicate(self, simulation: str = "case") -> str:
        """Generate occurs() predicate."""
        return f"occurs({simulation}, {self.event_label.replace(' ', '_')}, {self.time_point})"

    def to_dict(self) -> Dict:
        result = asdict(self)
        result['phase'] = self.phase.value
        return result


@dataclass
class EntityGroundedTimeline:
    """
    Complete timeline with full entity grounding and Event Calculus representation.
    """
    case_id: int

    # Timeline events
    events: List[TimelineEvent] = field(default_factory=list)

    # Fluent tracking (Berreby's Event Calculus)
    initial_fluents: List[Fluent] = field(default_factory=list)  # States at T=0
    fluent_history: Dict[int, List[str]] = field(default_factory=dict)  # Time -> fluents that hold

    # Causal chains
    causal_links: List[CausalLink] = field(default_factory=list)

    # Decision point markers
    decision_points: List[int] = field(default_factory=list)  # Time points with decisions

    # Metadata
    total_time_points: int = 0
    construction_metadata: Dict = field(default_factory=dict)

    def to_event_trace(self) -> str:
        """
        Generate Berreby-style event trace string.

        Output format:
        EVENT TRACE:
        Initial State (T=0):
        - initially(fluent_1)
        ...
        Time Point 1:
        - occurs(case, event_1, 1)
        ...
        """
        lines = ["EVENT TRACE:", "", "Initial State (T=0):"]

        # Initial fluents
        for fluent in self.initial_fluents:
            lines.append(f"- {fluent.to_predicate(0)}")

        # Events by time point
        events_by_time = {}
        for event in self.events:
            t = event.time_point
            if t not in events_by_time:
                events_by_time[t] = []
            events_by_time[t].append(event)

        for t in sorted(events_by_time.keys()):
            if t == 0:
                continue
            lines.append(f"")
            lines.append(f"Time Point {t}:")
            for event in events_by_time[t]:
                lines.append(f"- {event.to_predicate()}")
                for initiated in event.initiated_fluents:
                    lines.append(f"  initiates(case, {event.event_label.replace(' ', '_')}, {initiated}, {t})")
                for terminated in event.terminated_fluents:
                    lines.append(f"  terminates(case, {event.event_label.replace(' ', '_')}, {terminated}, {t})")

        # Causal links
        if self.causal_links:
            lines.append("")
            lines.append("CAUSAL CHAIN:")
            for link in self.causal_links:
                lines.append(f"- {link.to_predicate(0)}")

        return "\n".join(lines)

    def to_dict(self) -> Dict:
        return {
            'case_id': self.case_id,
            'events': [e.to_dict() for e in self.events],
            'initial_fluents': [f.to_dict() for f in self.initial_fluents],
            'fluent_history': self.fluent_history,
            'causal_links': [c.to_dict() for c in self.causal_links],
            'decision_points': self.decision_points,
            'total_time_points': self.total_time_points,
            'event_trace': self.to_event_trace(),
            'construction_metadata': self.construction_metadata
        }

    def summary(self) -> Dict:
        return {
            'events_count': len(self.events),
            'initial_fluents_count': len(self.initial_fluents),
            'causal_links_count': len(self.causal_links),
            'decision_points_count': len(self.decision_points),
            'time_span': self.total_time_points
        }


# =============================================================================
# TIMELINE CONSTRUCTOR SERVICE
# =============================================================================

class TimelineConstructor:
    """
    Constructs entity-grounded timelines using Event Calculus framework.

    Produces timelines with:
    - Entity-grounded events
    - Fluent tracking (state changes)
    - Causal links between events
    - Decision point markers
    """

    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        self.llm_client = get_llm_client() if use_llm else None

    def construct(
        self,
        case_id: int,
        narrative_elements,  # NarrativeElements from Stage 4.1
        foundation=None,  # EntityFoundation for additional context
        causal_normative_links: List[Dict] = None
    ) -> EntityGroundedTimeline:
        """
        Construct entity-grounded timeline from narrative elements.

        Args:
            case_id: Case ID
            narrative_elements: NarrativeElements from Stage 4.1
            foundation: EntityFoundation for additional context
            causal_normative_links: Causal links from Phase 2B

        Returns:
            EntityGroundedTimeline with Event Calculus representation
        """
        causal_normative_links = causal_normative_links or []

        # Build initial fluents from setting
        initial_fluents = self._build_initial_fluents(narrative_elements.setting)

        # Build timeline events
        events = self._build_timeline_events(narrative_elements)

        # Build causal links
        causal_links = self._build_causal_links(
            events, narrative_elements, causal_normative_links
        )

        # Track decision points
        decision_points = [
            e.time_point for e in events
            if e.event_type == 'decision'
        ]

        # Enhance with LLM if enabled
        if self.use_llm and self.llm_client:
            events = self._enhance_timeline_with_llm(
                events, narrative_elements, case_id
            )

        # Build fluent history
        fluent_history = self._build_fluent_history(initial_fluents, events)

        return EntityGroundedTimeline(
            case_id=case_id,
            events=events,
            initial_fluents=initial_fluents,
            fluent_history=fluent_history,
            causal_links=causal_links,
            decision_points=decision_points,
            total_time_points=max([e.time_point for e in events]) if events else 0,
            construction_metadata={
                'llm_enhanced': self.use_llm,
                'source_elements': narrative_elements.summary() if hasattr(narrative_elements, 'summary') else {},
                'causal_links_source_count': len(causal_normative_links)
            }
        )

    def _build_initial_fluents(self, setting) -> List[Fluent]:
        """Build initial fluents from NarrativeSetting."""
        fluents = []

        if not setting:
            return fluents

        # Convert initial states to fluents
        for state in setting.initial_states:
            fluents.append(Fluent(
                uri=state.get('uri', ''),
                label=state.get('label', ''),
                fluent_type='state',
                initially_true=True,
                current_value=True,
                source_entity_uri=state.get('uri', ''),
                source_entity_type='state'
            ))

        return fluents

    def _build_timeline_events(self, narrative_elements) -> List[TimelineEvent]:
        """Build timeline events from narrative elements."""
        timeline_events = []
        time_point = 1

        # Phase 1: Initial situation from setting
        if narrative_elements.setting:
            timeline_events.append(TimelineEvent(
                sequence=1,
                phase=TimelinePhase.INITIAL,
                phase_label=TimelinePhase.INITIAL.value,
                event_uri="",
                event_label="case_begins",
                description=narrative_elements.setting.description,
                event_type='state',
                entity_uris=[s.get('uri', '') for s in narrative_elements.setting.initial_states[:3]],
                entity_labels=[s.get('label', '') for s in narrative_elements.setting.initial_states[:3]],
                time_point=0,  # T=0 for initial state
                initiated_fluents=[s.get('label', '').replace(' ', '_')
                                  for s in narrative_elements.setting.initial_states[:5]]
            ))

        # Phase 2: Rising action from events
        for event in narrative_elements.events:
            phase = TimelinePhase.RISING
            if event.event_type == 'action':
                phase_label = "Action"
            else:
                phase_label = "Event"

            timeline_events.append(TimelineEvent(
                sequence=len(timeline_events) + 1,
                phase=phase,
                phase_label=phase_label,
                event_uri=event.uri,
                event_label=event.label,
                description=event.description,
                event_type=event.event_type,
                entity_uris=[event.uri],
                entity_labels=[event.label],
                agent_uri=event.agent_uri,
                agent_label=event.agent_label,
                time_point=time_point,
                precondition_fluents=event.preconditions,
                initiated_fluents=event.initiates,
                terminated_fluents=event.terminates
            ))
            time_point += 1

        # Phase 3: Conflicts emerge
        for conflict in narrative_elements.conflicts[:2]:  # Limit to top 2
            timeline_events.append(TimelineEvent(
                sequence=len(timeline_events) + 1,
                phase=TimelinePhase.CONFLICT,
                phase_label=TimelinePhase.CONFLICT.value,
                event_uri=conflict.conflict_id,
                event_label=f"conflict_emerges_{conflict.conflict_id}",
                description=conflict.description,
                event_type='automatic',  # Conflicts emerge automatically from actions
                entity_uris=[conflict.entity1_uri, conflict.entity2_uri],
                entity_labels=[conflict.entity1_label, conflict.entity2_label],
                time_point=time_point
            ))
            time_point += 1

        # Phase 4: Decision points
        for decision in narrative_elements.decision_moments:
            timeline_events.append(TimelineEvent(
                sequence=len(timeline_events) + 1,
                phase=TimelinePhase.DECISION,
                phase_label=f"Decision: {decision.decision_id}",
                event_uri=decision.uri,
                event_label=decision.decision_id,
                description=decision.question,
                event_type='decision',
                entity_uris=[decision.decision_maker_uri],
                entity_labels=[decision.decision_maker_label],
                agent_uri=decision.decision_maker_uri,
                agent_label=decision.decision_maker_label,
                time_point=time_point
            ))
            time_point += 1

        # Phase 5: Resolution
        if narrative_elements.resolution:
            timeline_events.append(TimelineEvent(
                sequence=len(timeline_events) + 1,
                phase=TimelinePhase.RESOLUTION,
                phase_label=TimelinePhase.RESOLUTION.value,
                event_uri="board_resolution",
                event_label="board_resolution",
                description=narrative_elements.resolution.summary,
                event_type='outcome',
                entity_uris=[c.get('uri', '') for c in narrative_elements.resolution.conclusions[:2]],
                entity_labels=[c.get('label', '') for c in narrative_elements.resolution.conclusions[:2]],
                time_point=time_point
            ))

        return timeline_events

    def _build_causal_links(
        self,
        events: List[TimelineEvent],
        narrative_elements,
        causal_normative_links: List[Dict]
    ) -> List[CausalLink]:
        """Build causal links between events."""
        links = []

        # First, add links from causal_normative_links
        for cnl in causal_normative_links:
            links.append(CausalLink(
                source_uri=cnl.get('action_uri', ''),
                source_label=cnl.get('action_label', ''),
                source_type='action',
                target_uri=cnl.get('obligation_uri', ''),
                target_label=cnl.get('obligation_label', ''),
                target_type='obligation',
                link_type='triggers',
                confidence=cnl.get('confidence', 0.5)
            ))

        # Build sequential links between timeline events
        for i, event in enumerate(events[:-1]):
            next_event = events[i + 1]

            # Link actions to following events
            if event.event_type == 'action':
                links.append(CausalLink(
                    source_uri=event.event_uri,
                    source_label=event.event_label,
                    source_type='action',
                    target_uri=next_event.event_uri,
                    target_label=next_event.event_label,
                    target_type=next_event.event_type,
                    link_type='enables',
                    confidence=0.6
                ))

        # Link conflicts to decision points
        conflict_events = [e for e in events if e.phase == TimelinePhase.CONFLICT]
        decision_events = [e for e in events if e.phase == TimelinePhase.DECISION]

        for conflict in conflict_events:
            for decision in decision_events:
                links.append(CausalLink(
                    source_uri=conflict.event_uri,
                    source_label=conflict.event_label,
                    source_type='conflict',
                    target_uri=decision.event_uri,
                    target_label=decision.event_label,
                    target_type='decision',
                    link_type='precipitates',
                    confidence=0.7
                ))

        return links

    def _build_fluent_history(
        self,
        initial_fluents: List[Fluent],
        events: List[TimelineEvent]
    ) -> Dict[int, List[str]]:
        """Build history of which fluents hold at each time point."""
        history = {}

        # Start with initial fluents at T=0
        current_fluents = set([f.label.replace(' ', '_') for f in initial_fluents])
        history[0] = list(current_fluents)

        # Track changes through timeline
        for event in sorted(events, key=lambda e: e.time_point):
            t = event.time_point
            if t == 0:
                continue

            # Apply initiated fluents
            for fluent in event.initiated_fluents:
                current_fluents.add(fluent.replace(' ', '_'))

            # Remove terminated fluents
            for fluent in event.terminated_fluents:
                fluent_key = fluent.replace(' ', '_')
                current_fluents.discard(fluent_key)

            history[t] = list(current_fluents)

        return history

    def _enhance_timeline_with_llm(
        self,
        events: List[TimelineEvent],
        narrative_elements,
        case_id: int
    ) -> List[TimelineEvent]:
        """Use LLM to enhance timeline event descriptions."""
        if not events or not self.llm_client:
            return events

        # Build context for LLM
        event_list = "\n".join([
            f"{i+1}. [{e.phase.value}] {e.event_label}: {e.description[:100]}..."
            for i, e in enumerate(events[:8])
        ])

        prompt = f"""Enhance these timeline events from an NSPE ethics case with clearer, more narrative descriptions.

TIMELINE EVENTS:
{event_list}

For each event, provide a clearer 1-2 sentence description that:
1. Uses professional but accessible language
2. Explains the significance of the event
3. Maintains objective tone

Output as JSON array:
```json
[
  {{"event_number": 1, "enhanced_description": "..."}}
]
```"""

        try:
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=800,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )

            import json
            import re

            response_text = response.content[0].text
            json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)

            if json_match:
                enhancements = json.loads(json_match.group(1))

                for enhancement in enhancements:
                    event_num = enhancement.get('event_number', 0) - 1
                    if 0 <= event_num < len(events):
                        events[event_num].description = enhancement.get(
                            'enhanced_description',
                            events[event_num].description
                        )

            logger.info(f"Enhanced {len(events)} timeline events with LLM")

        except Exception as e:
            logger.warning(f"LLM timeline enhancement failed: {e}")

        return events


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def construct_timeline(
    case_id: int,
    narrative_elements,
    foundation=None,
    causal_normative_links: List[Dict] = None,
    use_llm: bool = True
) -> EntityGroundedTimeline:
    """
    Convenience function to construct entity-grounded timeline.

    Args:
        case_id: Case ID
        narrative_elements: NarrativeElements from Stage 4.1
        foundation: EntityFoundation for additional context
        causal_normative_links: Causal links from Phase 2B
        use_llm: Whether to use LLM for enhancement

    Returns:
        EntityGroundedTimeline with Event Calculus representation
    """
    constructor = TimelineConstructor(use_llm=use_llm)
    return constructor.construct(
        case_id=case_id,
        narrative_elements=narrative_elements,
        foundation=foundation,
        causal_normative_links=causal_normative_links
    )
