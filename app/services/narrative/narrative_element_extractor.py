"""
Narrative Element Extractor (Stage 4.1)

Extracts narrative elements from extracted entities for case storytelling.
Uses entity URIs to maintain full traceability.

Based on: Berreby et al. (2017) - Action Model and Character Analysis

Components extracted:
- Characters (from Roles)
- Setting (from States, Resources)
- Events (from Actions, Events)
- Ethical Tensions (from Obligation/Constraint tensions) - Jones (1991) Moral Intensity
- Decision Moments (from Phase 3 decision points)
- Resolution (from Conclusions)
"""

import logging
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict

from app import db
from app.models import TemporaryRDFStorage
from app.utils.llm_utils import get_llm_client

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class NarrativeCharacter:
    """A character in the case narrative (derived from Roles)."""
    uri: str
    label: str
    role_type: str = ""  # 'protagonist', 'decision-maker', 'stakeholder', 'authority'
    professional_position: str = ""
    motivations: List[str] = field(default_factory=list)  # From bound obligations
    ethical_stance: str = ""  # From associated principles
    relationships: List[Tuple[str, str]] = field(default_factory=list)  # (relation, target_uri)

    # Entity grounding
    obligation_uris: List[str] = field(default_factory=list)
    principle_uris: List[str] = field(default_factory=list)

    # LLM enhancement flag
    llm_enhanced: bool = False

    def to_dict(self) -> Dict:
        return {
            **asdict(self),
            'relationships': [list(r) for r in self.relationships]
        }


@dataclass
class NarrativeSetting:
    """The setting/context of the narrative (from States, Resources)."""
    description: str
    professional_context: str = ""  # Engineering domain context
    temporal_context: str = ""  # When events occur

    # State fluents (from Berreby's Event Calculus)
    initial_states: List[Dict] = field(default_factory=list)  # {uri, label, fluent_expr}
    resources_involved: List[Dict] = field(default_factory=list)  # {uri, label}

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class NarrativeEvent:
    """An event in the narrative (from Actions, Events)."""
    uri: str
    label: str
    event_type: str  # 'action', 'automatic', 'decision', 'outcome'

    # Berreby Event Calculus attributes
    agent_uri: Optional[str] = None  # Who performed (for actions)
    agent_label: Optional[str] = None
    time_point: int = 0  # Relative temporal ordering

    # Fluent effects (from Berreby)
    preconditions: List[str] = field(default_factory=list)  # Fluents that must hold
    initiates: List[str] = field(default_factory=list)  # Fluents initiated
    terminates: List[str] = field(default_factory=list)  # Fluents terminated

    description: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class NarrativeConflict:
    """
    An ethical tension in the narrative.

    Based on Jones (1991) Moral Intensity model, ethical tensions are characterized by:
    - Magnitude of consequences: How serious are the potential harms/benefits?
    - Probability of effect: How likely are negative outcomes?
    - Temporal immediacy: How soon will consequences occur?
    - Proximity: How close is the decision-maker to those affected?
    - Concentration of effect: Are harms concentrated or diffuse?
    - Social consensus: Is there agreement that the action is wrong?
    """
    conflict_id: str
    description: str
    conflict_type: str  # 'obligation_vs_obligation', 'obligation_vs_constraint', 'role_conflict'

    # Entities in tension
    entity1_uri: str
    entity1_label: str
    entity1_type: str  # 'obligation', 'constraint', 'role'

    entity2_uri: str
    entity2_label: str
    entity2_type: str

    # Affected parties
    affected_role_uris: List[str] = field(default_factory=list)
    affected_role_labels: List[str] = field(default_factory=list)

    # Jones (1991) Moral Intensity Factors (optional, LLM-enhanced)
    magnitude_of_consequences: Optional[str] = None  # 'high', 'medium', 'low'
    probability_of_effect: Optional[str] = None  # 'high', 'medium', 'low'
    temporal_immediacy: Optional[str] = None  # 'immediate', 'near-term', 'long-term'
    proximity: Optional[str] = None  # 'direct', 'indirect', 'remote'
    concentration_of_effect: Optional[str] = None  # 'concentrated', 'diffuse'

    # Resolution (if known)
    resolution_type: Optional[str] = None  # 'prioritized', 'balanced', 'unresolved'
    resolution_rationale: str = ""

    # LLM enhancement flag
    llm_enhanced: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)


# Alias for consistency with UI terminology
EthicalTension = NarrativeConflict


@dataclass
class DecisionMoment:
    """A decision point as a narrative moment."""
    uri: str
    decision_id: str
    question: str
    description: str

    # The decision-maker
    decision_maker_uri: str
    decision_maker_label: str

    # Available options
    options: List[Dict] = field(default_factory=list)  # {label, action_uris, consequences}

    # What's at stake
    competing_obligations: List[str] = field(default_factory=list)
    board_choice: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class NarrativeResolution:
    """How the case was resolved."""
    resolution_type: str  # 'transfer', 'stalemate', 'oscillation', 'phase_lag'
    summary: str

    # Board conclusions
    conclusions: List[Dict] = field(default_factory=list)  # {uri, label, text}

    # Key determinations
    key_findings: List[str] = field(default_factory=list)
    ethical_principles_applied: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class NarrativeElements:
    """Complete set of narrative elements extracted from a case."""
    case_id: int

    # Core narrative components
    characters: List[NarrativeCharacter] = field(default_factory=list)
    setting: Optional[NarrativeSetting] = None
    events: List[NarrativeEvent] = field(default_factory=list)
    conflicts: List[NarrativeConflict] = field(default_factory=list)
    decision_moments: List[DecisionMoment] = field(default_factory=list)
    resolution: Optional[NarrativeResolution] = None

    # Summary statistics
    extraction_metadata: Dict = field(default_factory=dict)

    # LLM interaction traces for display
    llm_traces: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'case_id': self.case_id,
            'characters': [c.to_dict() for c in self.characters],
            'setting': self.setting.to_dict() if self.setting else None,
            'events': [e.to_dict() for e in self.events],
            'conflicts': [c.to_dict() for c in self.conflicts],
            'decision_moments': [d.to_dict() for d in self.decision_moments],
            'resolution': self.resolution.to_dict() if self.resolution else None,
            'extraction_metadata': self.extraction_metadata,
            'llm_traces': self.llm_traces
        }

    def summary(self) -> Dict:
        """Summary counts for display."""
        return {
            'characters': len(self.characters),
            'events': len(self.events),
            'conflicts': len(self.conflicts),
            'decision_moments': len(self.decision_moments),
            'has_setting': self.setting is not None,
            'has_resolution': self.resolution is not None
        }


# =============================================================================
# NARRATIVE ELEMENT EXTRACTOR SERVICE
# =============================================================================

class NarrativeElementExtractor:
    """
    Extracts narrative elements from Pass 1-3 entities and Phase 3 decision points.

    Produces entity-grounded narrative components that maintain full traceability
    to source entities via URIs.
    """

    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        self.llm_client = get_llm_client() if use_llm else None

    def extract(
        self,
        case_id: int,
        foundation: Any,  # EntityFoundation from case_synthesizer
        canonical_points: List[Any] = None,  # CanonicalDecisionPoint list
        conclusions: List[Dict] = None,
        transformation_type: str = None
    ) -> NarrativeElements:
        """
        Extract narrative elements from case entities.

        Args:
            case_id: Case ID
            foundation: EntityFoundation with all Pass 1-3 entities
            canonical_points: Decision points from Phase 3
            conclusions: Board conclusions
            transformation_type: Case transformation type

        Returns:
            NarrativeElements with full entity grounding
        """
        canonical_points = canonical_points or []
        conclusions = conclusions or []

        # Extract each component
        characters = self._extract_characters(foundation)
        setting = self._extract_setting(foundation)
        events = self._extract_events(foundation)
        conflicts = self._extract_conflicts(foundation, canonical_points)
        decision_moments = self._extract_decision_moments(canonical_points)
        resolution = self._extract_resolution(conclusions, transformation_type)

        # Collect LLM traces
        llm_traces = []

        # Enhance with LLM if enabled
        if self.use_llm and self.llm_client:
            characters, char_trace = self._enhance_characters_with_llm(
                characters, foundation, case_id
            )
            if char_trace:
                llm_traces.append(char_trace)

            # Enhance ethical tensions with moral intensity factors (Jones 1991)
            conflicts, tension_trace = self._enhance_tensions_with_llm(
                conflicts, foundation, case_id
            )
            if tension_trace:
                llm_traces.append(tension_trace)

        return NarrativeElements(
            case_id=case_id,
            characters=characters,
            setting=setting,
            events=events,
            conflicts=conflicts,  # Now includes LLM-enhanced ethical tensions
            decision_moments=decision_moments,
            resolution=resolution,
            extraction_metadata={
                'source_entities': foundation.summary() if hasattr(foundation, 'summary') else {},
                'decision_points_count': len(canonical_points),
                'conclusions_count': len(conclusions),
                'transformation_type': transformation_type,
                'llm_enhanced': self.use_llm
            },
            llm_traces=llm_traces
        )

    def _extract_characters(self, foundation) -> List[NarrativeCharacter]:
        """
        Extract characters from Roles with their bound obligations and principles.

        Filters out:
        - Ontology classes (from intermediate/core ontology) - these are role types, not individuals
        - Meta-authority (Board of Ethical Review) - this reviews all cases, not a case character
        """
        characters = []

        # Build role -> obligation bindings
        obligation_map = self._build_obligation_map(foundation)
        principle_map = self._build_principle_map(foundation)

        for role in foundation.roles:
            # Filter out ontology classes (not case-specific individuals)
            if self._is_ontology_class(role.uri):
                logger.debug(f"Skipping ontology class: {role.label} ({role.uri})")
                continue

            # Filter out meta-authority (Board of Ethical Review)
            if self._is_meta_authority(role.label):
                logger.debug(f"Skipping meta-authority: {role.label}")
                continue

            # Determine role type based on position in case
            role_type = self._classify_role_type(role.label)

            # Get bound obligations as motivations
            motivations = []
            obligation_uris = obligation_map.get(role.uri, [])
            for obl in foundation.obligations:
                if obl.uri in obligation_uris:
                    motivations.append(obl.label)

            # Get associated principles
            principle_uris = principle_map.get(role.uri, [])
            ethical_stance = ""
            if principle_uris and foundation.principles:
                relevant_principles = [p.label for p in foundation.principles
                                      if p.uri in principle_uris]
                if relevant_principles:
                    ethical_stance = f"Guided by: {', '.join(relevant_principles[:3])}"

            characters.append(NarrativeCharacter(
                uri=role.uri,
                label=role.label,
                role_type=role_type,
                professional_position=role.definition or "",
                motivations=motivations[:5],
                ethical_stance=ethical_stance,
                relationships=[],  # To be enriched
                obligation_uris=obligation_uris[:5],
                principle_uris=principle_uris[:3]
            ))

        return characters

    def _is_ontology_class(self, uri: str) -> bool:
        """
        Check if a URI represents an ontology class rather than a case-specific individual.

        Classes are defined in the intermediate or core ontology (role types),
        while case-specific individuals have case-numbered URIs.
        """
        if not uri:
            return False
        class_markers = ['intermediate#', 'core#', '/ontology#']
        return any(marker in uri for marker in class_markers)

    def _is_meta_authority(self, label: str) -> bool:
        """
        Check if a role label represents the meta-authority (Board of Ethical Review).

        The NSPE Board of Ethical Review reviews all cases and should not be shown
        as a character in the case narrative. Case-specific authorities (like local
        compliance boards, state licensing boards, etc.) should still be shown.
        """
        if not label:
            return False
        label_lower = label.lower()
        meta_authority_terms = [
            'board of ethical review',
            'nspe board',
        ]
        return any(term in label_lower for term in meta_authority_terms)

    def _classify_role_type(self, role_label: str) -> str:
        """Classify a role into narrative role type."""
        label_lower = role_label.lower()

        # Check for protagonist markers
        if any(term in label_lower for term in ['engineer a', 'primary', 'main']):
            return 'protagonist'

        # Check for decision-maker markers
        if any(term in label_lower for term in ['manager', 'director', 'supervisor', 'boss']):
            return 'decision-maker'

        # Check for authority markers
        if any(term in label_lower for term in ['board', 'commission', 'committee', 'authority']):
            return 'authority'

        # Default to stakeholder
        return 'stakeholder'

    def _build_obligation_map(self, foundation) -> Dict[str, List[str]]:
        """Build mapping of role URIs to their bound obligation URIs."""
        obligation_map = {}

        # Use role_obligation_bindings if available
        if hasattr(foundation, 'role_obligation_bindings') and foundation.role_obligation_bindings:
            for binding in foundation.role_obligation_bindings:
                role_uri = binding.get('role_uri', '')
                obl_uri = binding.get('obligation_uri', '')
                if role_uri and obl_uri:
                    if role_uri not in obligation_map:
                        obligation_map[role_uri] = []
                    obligation_map[role_uri].append(obl_uri)

        return obligation_map

    def _build_principle_map(self, foundation) -> Dict[str, List[str]]:
        """Build mapping of role URIs to associated principle URIs."""
        # For now, associate all principles with protagonist role
        principle_map = {}
        if foundation.roles and foundation.principles:
            protagonist_uri = foundation.roles[0].uri
            principle_map[protagonist_uri] = [p.uri for p in foundation.principles[:5]]
        return principle_map

    def _extract_setting(self, foundation) -> NarrativeSetting:
        """Extract setting from States and Resources."""
        # Build initial states as fluents
        initial_states = []
        for state in foundation.states[:10]:
            fluent_expr = f"holds(case, {state.label.replace(' ', '_')}, 0)"
            initial_states.append({
                'uri': state.uri,
                'label': state.label,
                'fluent_expr': fluent_expr,
                'definition': state.definition or ''
            })

        # Extract resources
        resources = [
            {'uri': r.uri, 'label': r.label}
            for r in foundation.resources[:5]
        ]

        # Build setting description
        state_summary = ', '.join([s.label for s in foundation.states[:3]]) if foundation.states else 'professional context'
        description = f"Case unfolds in a setting characterized by: {state_summary}"

        return NarrativeSetting(
            description=description,
            professional_context="Professional engineering practice",
            temporal_context="During professional engagement",
            initial_states=initial_states,
            resources_involved=resources
        )

    def _extract_events(self, foundation) -> List[NarrativeEvent]:
        """Extract events from Actions and Events with Event Calculus attributes."""
        narrative_events = []
        time_point = 1

        # First, add actions
        for action in foundation.actions:
            # Parse agent from action if available
            agent_uri = None
            agent_label = None

            # Try to extract agent from RDF or definition
            if hasattr(action, 'entity_type') and action.entity_type:
                # Check if we have agent info
                pass

            narrative_events.append(NarrativeEvent(
                uri=action.uri,
                label=action.label,
                event_type='action',
                agent_uri=agent_uri,
                agent_label=agent_label,
                time_point=time_point,
                preconditions=[],  # To be enriched from causal analysis
                initiates=[],
                terminates=[],
                description=action.definition or action.label
            ))
            time_point += 1

        # Then add events (automatic occurrences)
        for event in foundation.events:
            narrative_events.append(NarrativeEvent(
                uri=event.uri,
                label=event.label,
                event_type='automatic',
                time_point=time_point,
                description=event.definition or event.label
            ))
            time_point += 1

        return narrative_events

    def _extract_conflicts(
        self,
        foundation,
        canonical_points: List
    ) -> List[NarrativeConflict]:
        """Extract ethical conflicts from obligation tensions."""
        conflicts = []
        conflict_id = 1

        # Extract conflicts from canonical decision points
        for dp in canonical_points:
            if hasattr(dp, 'obligation_label') and hasattr(dp, 'constraint_label'):
                if dp.obligation_label and dp.constraint_label:
                    conflicts.append(NarrativeConflict(
                        conflict_id=f"conflict_{conflict_id}",
                        description=f"Tension between {dp.obligation_label} and {dp.constraint_label}",
                        conflict_type='obligation_vs_constraint',
                        entity1_uri=getattr(dp, 'obligation_uri', '') or '',
                        entity1_label=dp.obligation_label,
                        entity1_type='obligation',
                        entity2_uri=getattr(dp, 'constraint_uri', '') or '',
                        entity2_label=dp.constraint_label,
                        entity2_type='constraint',
                        affected_role_uris=[getattr(dp, 'role_uri', '')] if hasattr(dp, 'role_uri') else []
                    ))
                    conflict_id += 1

        # Look for obligation-obligation conflicts in the foundation
        obligations = foundation.obligations
        if len(obligations) >= 2:
            # Check for potentially conflicting obligations
            for i, obl1 in enumerate(obligations[:-1]):
                for obl2 in obligations[i+1:]:
                    # Simple heuristic: obligations with opposite-sounding terms
                    if self._potentially_conflicting(obl1.label, obl2.label):
                        conflicts.append(NarrativeConflict(
                            conflict_id=f"conflict_{conflict_id}",
                            description=f"Potential tension between {obl1.label} and {obl2.label}",
                            conflict_type='obligation_vs_obligation',
                            entity1_uri=obl1.uri,
                            entity1_label=obl1.label,
                            entity1_type='obligation',
                            entity2_uri=obl2.uri,
                            entity2_label=obl2.label,
                            entity2_type='obligation'
                        ))
                        conflict_id += 1
                        if conflict_id > 5:  # Limit conflicts
                            break
                if conflict_id > 5:
                    break

        return conflicts

    def _potentially_conflicting(self, label1: str, label2: str) -> bool:
        """Heuristic check for potentially conflicting obligations."""
        # Simple keyword-based conflict detection
        conflict_pairs = [
            ('confidential', 'disclose'),
            ('loyalty', 'public'),
            ('employer', 'client'),
            ('protect', 'inform'),
            ('private', 'safety')
        ]

        l1_lower = label1.lower()
        l2_lower = label2.lower()

        for term1, term2 in conflict_pairs:
            if (term1 in l1_lower and term2 in l2_lower) or \
               (term2 in l1_lower and term1 in l2_lower):
                return True

        return False

    def _extract_decision_moments(
        self,
        canonical_points: List
    ) -> List[DecisionMoment]:
        """Convert canonical decision points to narrative decision moments."""
        moments = []

        for i, dp in enumerate(canonical_points, 1):
            # Extract options
            options = []
            if hasattr(dp, 'options') and dp.options:
                for opt in dp.options:
                    options.append({
                        'label': opt.get('label', ''),
                        'action_uris': opt.get('action_uris', []),
                        'is_board_choice': opt.get('is_board_choice', False)
                    })

            # Find board's choice
            board_choice = None
            for opt in options:
                if opt.get('is_board_choice'):
                    board_choice = opt['label']
                    break

            moments.append(DecisionMoment(
                uri=getattr(dp, 'uri', f"decision_{i}"),
                decision_id=getattr(dp, 'focus_id', f"DP{i}"),
                question=getattr(dp, 'decision_question', ''),
                description=getattr(dp, 'description', ''),
                decision_maker_uri=getattr(dp, 'role_uri', ''),
                decision_maker_label=getattr(dp, 'role_label', ''),
                options=options,
                competing_obligations=[
                    getattr(dp, 'obligation_label', ''),
                    getattr(dp, 'constraint_label', '')
                ],
                board_choice=board_choice
            ))

        return moments

    def _extract_resolution(
        self,
        conclusions: List[Dict],
        transformation_type: str = None
    ) -> NarrativeResolution:
        """Extract resolution from conclusions and transformation type."""
        # Build conclusions list
        conclusion_data = []
        key_findings = []
        principles_mentioned = set()

        for c in conclusions:
            conclusion_data.append({
                'uri': c.get('uri', ''),
                'label': c.get('label', ''),
                'text': c.get('text', c.get('definition', ''))[:300]
            })
            key_findings.append(c.get('label', '')[:100])

            # Extract principles from mentioned_entities
            mentioned = c.get('mentioned_entities', {})
            if isinstance(mentioned, dict):
                for principle in mentioned.get('principles', []):
                    if principle:
                        principles_mentioned.add(principle)

        # Generate summary
        if conclusions:
            summary = conclusions[0].get('text', conclusions[0].get('label', 'Board provided guidance'))[:200]
        else:
            summary = "Case resolution pending analysis"

        return NarrativeResolution(
            resolution_type=transformation_type or 'unknown',
            summary=summary,
            conclusions=conclusion_data,
            key_findings=key_findings[:5],
            ethical_principles_applied=list(principles_mentioned)
        )

    def _enhance_characters_with_llm(
        self,
        characters: List[NarrativeCharacter],
        foundation,
        case_id: int
    ) -> Tuple[List[NarrativeCharacter], Optional[Dict]]:
        """Use LLM to enhance character descriptions. Returns (characters, llm_trace)."""
        if not characters or not self.llm_client:
            return characters, None

        # Build context for LLM
        character_list = "\n".join([
            f"- {c.label}: {c.professional_position or 'Role'}"
            for c in characters[:5]
        ])

        obligations_list = "\n".join([
            f"- {o.label}"
            for o in foundation.obligations[:5]
        ])

        prompt = f"""Analyze these roles from an NSPE ethics case and provide brief character insights.

ROLES:
{character_list}

OBLIGATIONS IN THE CASE:
{obligations_list}

For each role, provide a 1-sentence professional description and likely motivation.
Output as JSON array:
```json
[
  {{"role": "Role label", "description": "...", "motivation": "..."}}
]
```"""

        llm_trace = None
        try:
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )

            import json
            import re

            response_text = response.content[0].text

            # Capture LLM trace
            llm_trace = {
                'stage': 'CHARACTER_ENHANCEMENT',
                'description': 'Enhance character descriptions with professional context',
                'prompt': prompt,
                'response': response_text,
                'model': 'claude-sonnet-4-20250514'
            }

            json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)

            if json_match:
                enhancements = json.loads(json_match.group(1))

                # Apply enhancements
                enhanced_count = 0
                for enhancement in enhancements:
                    role_label = enhancement.get('role', '')
                    for char in characters:
                        if char.label.lower() == role_label.lower() or \
                           role_label.lower() in char.label.lower():
                            if enhancement.get('description'):
                                char.professional_position = enhancement['description']
                            if enhancement.get('motivation'):
                                char.motivations.insert(0, enhancement['motivation'])
                            char.llm_enhanced = True
                            enhanced_count += 1
                            break

            logger.info(f"Enhanced {enhanced_count} characters with LLM")

        except Exception as e:
            logger.warning(f"LLM character enhancement failed: {e}")

        return characters, llm_trace

    def _enhance_tensions_with_llm(
        self,
        tensions: List[NarrativeConflict],
        foundation,
        case_id: int
    ) -> Tuple[List[NarrativeConflict], Optional[Dict]]:
        """
        Use LLM to identify and enhance ethical tensions. Returns (tensions, llm_trace).

        Based on Jones (1991) Moral Intensity model:
        - Magnitude of consequences
        - Probability of effect
        - Temporal immediacy
        - Proximity
        - Concentration of effect

        This method:
        1. Identifies additional tensions from obligations/constraints not caught by heuristics
        2. Enhances existing tensions with moral intensity factors
        3. Provides richer descriptions of the ethical dilemma
        """
        if not self.llm_client:
            return tensions, None

        # Build context from extracted entities
        obligations_list = "\n".join([
            f"- [{o.uri.split('#')[-1] if '#' in o.uri else o.uri.split('/')[-1]}] {o.label}"
            for o in foundation.obligations[:15]
        ])

        constraints_list = "\n".join([
            f"- [{c.uri.split('#')[-1] if '#' in c.uri else c.uri.split('/')[-1]}] {c.label}"
            for c in foundation.constraints[:15]
        ])

        roles_list = "\n".join([
            f"- {r.label}"
            for r in foundation.roles[:10]
        ])

        # Existing tensions found algorithmically
        existing_tensions = "\n".join([
            f"- {t.entity1_label} vs {t.entity2_label}: {t.description}"
            for t in tensions[:5]
        ]) if tensions else "None identified yet"

        prompt = f"""Analyze these extracted entities from an NSPE engineering ethics case and identify ethical tensions.

OBLIGATIONS (duties the engineer must fulfill):
{obligations_list}

CONSTRAINTS (limitations on what the engineer can do):
{constraints_list}

ROLES INVOLVED:
{roles_list}

TENSIONS ALREADY IDENTIFIED:
{existing_tensions}

Identify ethical tensions between obligations and/or constraints. For each tension, assess its moral intensity using Jones (1991) factors.

Focus on tensions that create genuine ethical dilemmas - where fulfilling one duty may compromise another.

Output as JSON array (identify 2-5 key tensions):
```json
[
  {{
    "entity1_id": "URI fragment of first entity",
    "entity1_label": "Label of first entity",
    "entity1_type": "obligation or constraint",
    "entity2_id": "URI fragment of second entity",
    "entity2_label": "Label of second entity",
    "entity2_type": "obligation or constraint",
    "description": "Clear description of why these are in tension",
    "conflict_type": "obligation_vs_obligation or obligation_vs_constraint",
    "affected_roles": ["Role labels affected by this tension"],
    "magnitude_of_consequences": "high/medium/low - how serious are potential harms?",
    "probability_of_effect": "high/medium/low - how likely are negative outcomes?",
    "temporal_immediacy": "immediate/near-term/long-term - when will consequences occur?",
    "proximity": "direct/indirect/remote - how close is decision-maker to affected parties?",
    "concentration_of_effect": "concentrated/diffuse - are harms focused or spread out?"
  }}
]
```"""

        llm_trace = None
        try:
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )

            import json
            import re

            response_text = response.content[0].text

            # Capture LLM trace
            llm_trace = {
                'stage': 'ETHICAL_TENSION_DETECTION',
                'description': 'Identify ethical tensions with Jones (1991) moral intensity factors',
                'prompt': prompt,
                'response': response_text,
                'model': 'claude-sonnet-4-20250514'
            }

            json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)

            if json_match:
                llm_tensions = json.loads(json_match.group(1))

                # Build lookup for existing tensions to avoid duplicates
                existing_pairs = set()
                for t in tensions:
                    pair = tuple(sorted([t.entity1_label.lower(), t.entity2_label.lower()]))
                    existing_pairs.add(pair)

                # Add new tensions from LLM
                tension_id = len(tensions) + 1
                for lt in llm_tensions:
                    pair = tuple(sorted([
                        lt.get('entity1_label', '').lower(),
                        lt.get('entity2_label', '').lower()
                    ]))

                    if pair not in existing_pairs and lt.get('entity1_label') and lt.get('entity2_label'):
                        # Find URIs for entities
                        entity1_uri = self._find_entity_uri(
                            lt.get('entity1_id', ''),
                            lt.get('entity1_label', ''),
                            foundation
                        )
                        entity2_uri = self._find_entity_uri(
                            lt.get('entity2_id', ''),
                            lt.get('entity2_label', ''),
                            foundation
                        )

                        tensions.append(NarrativeConflict(
                            conflict_id=f"tension_{tension_id}",
                            description=lt.get('description', ''),
                            conflict_type=lt.get('conflict_type', 'obligation_vs_obligation'),
                            entity1_uri=entity1_uri,
                            entity1_label=lt.get('entity1_label', ''),
                            entity1_type=lt.get('entity1_type', 'obligation'),
                            entity2_uri=entity2_uri,
                            entity2_label=lt.get('entity2_label', ''),
                            entity2_type=lt.get('entity2_type', 'obligation'),
                            affected_role_labels=lt.get('affected_roles', []),
                            magnitude_of_consequences=lt.get('magnitude_of_consequences'),
                            probability_of_effect=lt.get('probability_of_effect'),
                            temporal_immediacy=lt.get('temporal_immediacy'),
                            proximity=lt.get('proximity'),
                            concentration_of_effect=lt.get('concentration_of_effect'),
                            llm_enhanced=True
                        ))
                        tension_id += 1
                        existing_pairs.add(pair)

                # Also enhance existing tensions with moral intensity if not already present
                for existing_tension in tensions:
                    if not existing_tension.llm_enhanced:
                        for lt in llm_tensions:
                            if (existing_tension.entity1_label.lower() in lt.get('entity1_label', '').lower() or
                                existing_tension.entity2_label.lower() in lt.get('entity2_label', '').lower()):
                                existing_tension.magnitude_of_consequences = lt.get('magnitude_of_consequences')
                                existing_tension.probability_of_effect = lt.get('probability_of_effect')
                                existing_tension.temporal_immediacy = lt.get('temporal_immediacy')
                                existing_tension.proximity = lt.get('proximity')
                                existing_tension.concentration_of_effect = lt.get('concentration_of_effect')
                                existing_tension.llm_enhanced = True
                                break

                logger.info(f"Enhanced tensions with LLM: {len(tensions)} total tensions for case {case_id}")

        except Exception as e:
            logger.warning(f"LLM tension enhancement failed: {e}")

        return tensions, llm_trace

    def _find_entity_uri(self, entity_id: str, entity_label: str, foundation) -> str:
        """Find the full URI for an entity given its ID fragment or label."""
        # Check obligations
        for obl in foundation.obligations:
            if entity_id and entity_id in obl.uri:
                return obl.uri
            if entity_label.lower() == obl.label.lower():
                return obl.uri

        # Check constraints
        for con in foundation.constraints:
            if entity_id and entity_id in con.uri:
                return con.uri
            if entity_label.lower() == con.label.lower():
                return con.uri

        return f"proeth:{entity_id or entity_label.replace(' ', '_')}"


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def extract_narrative_elements(
    case_id: int,
    foundation,
    canonical_points: List = None,
    conclusions: List[Dict] = None,
    transformation_type: str = None,
    use_llm: bool = True
) -> NarrativeElements:
    """
    Convenience function to extract narrative elements.

    Args:
        case_id: Case ID
        foundation: EntityFoundation from case_synthesizer
        canonical_points: Decision points from Phase 3
        conclusions: Board conclusions
        transformation_type: Case transformation type
        use_llm: Whether to use LLM for enhancement

    Returns:
        NarrativeElements with full entity grounding
    """
    extractor = NarrativeElementExtractor(use_llm=use_llm)
    return extractor.extract(
        case_id=case_id,
        foundation=foundation,
        canonical_points=canonical_points,
        conclusions=conclusions,
        transformation_type=transformation_type
    )
