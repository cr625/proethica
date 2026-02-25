"""
Action-Option Mapper (Step E2)

Maps extracted Actions to decision options and scores them using Jones's (1991)
Moral Intensity framework. This prioritizes which decisions are most salient.

Based on Jones (1991): "Moral intensity captures the extent of issue-related
moral imperative in a situation."
"""

import re
import logging
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict

from app import db
from app.models import TemporaryRDFStorage
from app.domains import DomainConfig, get_domain_config

logger = logging.getLogger(__name__)


@dataclass
class MoralIntensityScore:
    """
    Jones's (1991) Moral Intensity components.

    Each component scored 0.0-1.0, combined into overall intensity.
    """
    magnitude: float = 0.5  # Severity of consequences
    social_consensus: float = 0.5  # Agreement that action is right/wrong
    probability: float = 0.5  # Likelihood of harm/benefit
    temporal_immediacy: float = 0.5  # How soon consequences occur
    proximity: float = 0.5  # Closeness to affected parties
    concentration: float = 0.5  # How focused the effect is

    @property
    def overall(self) -> float:
        """Weighted average of all components."""
        weights = {
            'magnitude': 0.25,
            'social_consensus': 0.20,
            'probability': 0.15,
            'temporal_immediacy': 0.15,
            'proximity': 0.15,
            'concentration': 0.10
        }
        return (
            self.magnitude * weights['magnitude'] +
            self.social_consensus * weights['social_consensus'] +
            self.probability * weights['probability'] +
            self.temporal_immediacy * weights['temporal_immediacy'] +
            self.proximity * weights['proximity'] +
            self.concentration * weights['concentration']
        )

    def to_dict(self) -> Dict[str, float]:
        return {
            'magnitude': self.magnitude,
            'social_consensus': self.social_consensus,
            'probability': self.probability,
            'temporal_immediacy': self.temporal_immediacy,
            'proximity': self.proximity,
            'concentration': self.concentration,
            'overall': self.overall
        }


@dataclass
class ActionOption:
    """A single action option (extracted or generated alternative)."""
    uri: str
    label: str
    description: str = ""
    was_chosen: bool = False  # Was this the action taken in the case?
    is_board_choice: bool = False  # Is this what the Board recommended?
    is_extracted: bool = True  # From extraction vs generated alternative
    downstream_events: List[str] = field(default_factory=list)  # Event URIs
    intensity_score: Optional[MoralIntensityScore] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'uri': self.uri,
            'label': self.label,
            'description': self.description,
            'was_chosen': self.was_chosen,
            'is_board_choice': self.is_board_choice,
            'is_extracted': self.is_extracted,
            'downstream_events': self.downstream_events,
            'intensity_score': self.intensity_score.to_dict() if self.intensity_score else None
        }


@dataclass
class ActionSet:
    """A set of related actions representing alternatives at a decision point."""
    decision_context: str  # What decision this set represents
    primary_action_uri: str  # The main extracted action
    actions: List[ActionOption] = field(default_factory=list)
    max_intensity_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'decision_context': self.decision_context,
            'primary_action_uri': self.primary_action_uri,
            'actions': [a.to_dict() for a in self.actions],
            'max_intensity_score': self.max_intensity_score
        }


@dataclass
class ActionOptionMap:
    """Complete action-option mapping for a case."""
    case_id: int
    action_sets: List[ActionSet] = field(default_factory=list)
    events: List[Dict[str, str]] = field(default_factory=list)  # All events
    causal_chains: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'case_id': self.case_id,
            'action_sets': [s.to_dict() for s in self.action_sets],
            'events': self.events,
            'causal_chains': self.causal_chains
        }


# Keywords for classifying action types
ACTION_TYPE_KEYWORDS = {
    'disclosure': ['disclosure', 'disclose', 'inform', 'tell', 'reveal', 'notify'],
    'adoption': ['adoption', 'adopt', 'use', 'implement', 'deploy'],
    'review': ['review', 'verify', 'check', 'audit', 'inspect', 'examine'],
    'delegation': ['delegate', 'assign', 'transfer', 'hand off'],
    'compliance': ['comply', 'seal', 'certify', 'sign', 'approve', 'stamp'],
}

# Severity keywords for magnitude scoring
SEVERITY_KEYWORDS = {
    'high': ['death', 'injury', 'harm', 'danger', 'safety', 'failure', 'collapse', 'error'],
    'medium': ['damage', 'loss', 'problem', 'issue', 'concern', 'risk'],
    'low': ['inconvenience', 'delay', 'minor', 'slight']
}


class ActionOptionMapper:
    """
    Maps actions to decision options with moral intensity scoring.

    Step E2 in the entity-grounded argument pipeline.
    """

    def __init__(self, domain_config: Optional[DomainConfig] = None):
        """
        Initialize with optional domain configuration.

        Args:
            domain_config: Domain-specific config. Defaults to engineering.
        """
        self.domain = domain_config or get_domain_config('engineering')

    def map_action_options(self, case_id: int) -> ActionOptionMap:
        """
        Map actions to decision options with intensity scores.

        For each action:
        1. Determine if it represents a CHOICE MADE or POSSIBLE OPTION
        2. Link to downstream events via causal chains
        3. Calculate moral intensity score
        4. Group related actions into ActionSets

        Args:
            case_id: The case to analyze

        Returns:
            ActionOptionMap with action sets and intensity scores
        """
        logger.info(f"Mapping action options for case {case_id}")

        # Load entities
        actions_raw = self._load_entities(case_id, 'actions')
        events_raw = self._load_entities(case_id, 'events')
        causal_chains_raw = self._load_entities(case_id, 'causal_chains')

        # Build causal chain lookup
        causal_map = self._build_causal_map(causal_chains_raw)

        # Process events
        events = []
        for entity in events_raw:
            events.append({
                'uri': entity.entity_uri or f"case-{case_id}#{entity.entity_label.replace(' ', '_')}",
                'label': entity.entity_label,
                'definition': entity.entity_definition or ""
            })

        # Process causal chains
        causal_chains = []
        for entity in causal_chains_raw:
            causal_chains.append({
                'uri': entity.entity_uri or f"case-{case_id}#{entity.entity_label.replace(' ', '_')}",
                'label': entity.entity_label,
                'definition': entity.entity_definition or ""
            })

        # Create action sets
        action_sets = []
        for entity in actions_raw:
            action_set = self._create_action_set(entity, causal_map, events, case_id)
            action_sets.append(action_set)

        # Sort by max intensity score (highest first)
        action_sets.sort(key=lambda x: x.max_intensity_score, reverse=True)

        result = ActionOptionMap(
            case_id=case_id,
            action_sets=action_sets,
            events=events,
            causal_chains=causal_chains
        )

        logger.info(
            f"Action mapping complete: {len(action_sets)} action sets, "
            f"{len(events)} events, {len(causal_chains)} causal chains"
        )

        return result

    def _load_entities(self, case_id: int, entity_type: str) -> List[TemporaryRDFStorage]:
        """Load entities of a specific type from the database."""
        return TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            entity_type=entity_type
        ).all()

    def _build_causal_map(
        self,
        causal_chains: List[TemporaryRDFStorage]
    ) -> Dict[str, List[str]]:
        """
        Build a map from action labels to downstream event labels.

        Parses causal chain labels like "Action → Event".
        """
        causal_map = {}

        for chain in causal_chains:
            label = chain.entity_label
            # Parse "Action → Event" format
            if '→' in label:
                parts = label.split('→')
                if len(parts) == 2:
                    action_label = parts[0].strip()
                    event_label = parts[1].strip()

                    if action_label not in causal_map:
                        causal_map[action_label] = []
                    causal_map[action_label].append(event_label)

        return causal_map

    def _create_action_set(
        self,
        action_entity: TemporaryRDFStorage,
        causal_map: Dict[str, List[str]],
        events: List[Dict[str, str]],
        case_id: int
    ) -> ActionSet:
        """Create an ActionSet for a single extracted action."""
        label = action_entity.entity_label
        uri = action_entity.entity_uri or f"case-{case_id}#{label.replace(' ', '_')}"
        definition = action_entity.entity_definition or ""

        # Get downstream events from causal map
        downstream_event_labels = causal_map.get(label, [])
        downstream_event_uris = [
            e['uri'] for e in events
            if e['label'] in downstream_event_labels
        ]

        # Calculate intensity score
        intensity = self._calculate_intensity(
            label, definition, downstream_event_labels, events
        )

        # Create the primary action option (what was actually done)
        primary_action = ActionOption(
            uri=uri,
            label=label,
            description=definition,
            was_chosen=True,  # Extracted actions represent what happened
            is_extracted=True,
            downstream_events=downstream_event_uris,
            intensity_score=intensity
        )

        # Generate alternative action (the opposite choice)
        alternative = self._generate_alternative(label, case_id, events)
        if alternative:
            # Alternative has slightly different intensity (hypothetical)
            alt_intensity = self._calculate_intensity(
                alternative.label, alternative.description, [], events
            )
            alternative.intensity_score = alt_intensity

        actions = [primary_action]
        if alternative:
            actions.append(alternative)

        # Determine decision context from action label
        decision_context = self._extract_decision_context(label)

        return ActionSet(
            decision_context=decision_context,
            primary_action_uri=uri,
            actions=actions,
            max_intensity_score=max(a.intensity_score.overall for a in actions if a.intensity_score)
        )

    def _calculate_intensity(
        self,
        action_label: str,
        action_definition: str,
        downstream_event_labels: List[str],
        all_events: List[Dict[str, str]]
    ) -> MoralIntensityScore:
        """
        Calculate Jones's moral intensity score for an action.

        Components:
        - Magnitude: Severity of consequences (from events)
        - Social Consensus: Based on ethical principle alignment
        - Probability: Confidence/certainty of outcomes
        - Temporal Immediacy: How soon consequences occur
        - Proximity: Closeness to affected parties
        - Concentration: How focused the effect is
        """
        text = f"{action_label} {action_definition}".lower()
        event_text = " ".join(downstream_event_labels).lower()

        # Magnitude: Based on severity of downstream events
        magnitude = self._score_magnitude(event_text)

        # Social Consensus: Higher if action involves clear ethical principles
        consensus = self._score_social_consensus(text)

        # Probability: Default moderate, higher if causal chain exists
        probability = 0.7 if downstream_event_labels else 0.4

        # Temporal Immediacy: Default moderate
        temporal = 0.6

        # Proximity: Higher if involves direct professional relationships
        proximity = self._score_proximity(text)

        # Concentration: Higher if specific parties affected
        concentration = 0.6

        return MoralIntensityScore(
            magnitude=magnitude,
            social_consensus=consensus,
            probability=probability,
            temporal_immediacy=temporal,
            proximity=proximity,
            concentration=concentration
        )

    def _score_magnitude(self, event_text: str) -> float:
        """Score magnitude based on severity keywords in events."""
        for kw in SEVERITY_KEYWORDS['high']:
            if kw in event_text:
                return 0.9

        for kw in SEVERITY_KEYWORDS['medium']:
            if kw in event_text:
                return 0.6

        for kw in SEVERITY_KEYWORDS['low']:
            if kw in event_text:
                return 0.3

        return 0.5  # Default moderate

    def _score_social_consensus(self, text: str) -> float:
        """Score social consensus based on ethical principle keywords."""
        # High consensus topics
        high_consensus = ['safety', 'disclosure', 'honesty', 'competence', 'public']
        for kw in high_consensus:
            if kw in text:
                return 0.8

        return 0.5

    def _score_proximity(self, text: str) -> float:
        """Score proximity based on relationship keywords."""
        # Direct professional relationships
        direct = ['client', 'employer', 'colleague', 'employee']
        for kw in direct:
            if kw in text:
                return 0.8

        # Public/indirect relationships
        indirect = ['public', 'society', 'community']
        for kw in indirect:
            if kw in text:
                return 0.6

        return 0.5

    def _generate_alternative(
        self,
        action_label: str,
        case_id: int,
        events: List[Dict[str, str]]
    ) -> Optional[ActionOption]:
        """
        Generate an alternative action (the opposite of what was done).

        Uses simple negation patterns for common action types.
        """
        label_lower = action_label.lower()

        # Patterns for generating alternatives
        alternatives = {
            'non-disclosure': ('Disclosure Alternative', 'Disclose the information to relevant parties'),
            'disclosure': ('Non-Disclosure Alternative', 'Withhold the information'),
            'adoption': ('Non-Adoption Alternative', 'Decline to adopt or use'),
            'upload': ('Non-Upload Alternative', 'Retain data locally, do not upload'),
        }

        for pattern, (alt_label, alt_desc) in alternatives.items():
            if pattern in label_lower:
                # Extract context from original label
                context = action_label.replace('Decision', '').replace('_', ' ').strip()
                full_label = f"{context} {alt_label}"

                return ActionOption(
                    uri=f"case-{case_id}#{full_label.replace(' ', '_')}",
                    label=full_label,
                    description=alt_desc,
                    was_chosen=False,
                    is_board_choice=True if 'disclosure' in label_lower.lower() else False,
                    is_extracted=False,
                    downstream_events=[]
                )

        # Generic alternative: negate the action as an actionable phrase
        action_def = action_label.replace('_', ' ')
        return ActionOption(
            uri=f"case-{case_id}#{action_label.replace(' ', '_')}_Alternative",
            label=f"Do not {action_def[:1].lower()}{action_def[1:]}",
            description=f"Decline or refrain from taking the action: {action_def}",
            was_chosen=False,
            is_extracted=False,
            downstream_events=[]
        )

    def _extract_decision_context(self, action_label: str) -> str:
        """Extract a human-readable decision context from action label."""
        # Remove common suffixes
        context = action_label.replace('Decision', '').replace('_', ' ').strip()

        # Capitalize properly
        context = ' '.join(word.capitalize() for word in context.split())

        return f"Whether to proceed with {context}"


def get_action_option_map(case_id: int, domain: str = 'engineering') -> ActionOptionMap:
    """
    Convenience function to get action-option mapping.

    Args:
        case_id: Case to analyze
        domain: Domain code (default: engineering)

    Returns:
        ActionOptionMap with action sets and intensity scores
    """
    domain_config = get_domain_config(domain)
    mapper = ActionOptionMapper(domain_config)
    return mapper.map_action_options(case_id)
