"""
Stage 4: Decision Point Identification

Identifies critical decision moments in the scenario from:
1. Actions with isDecisionPoint=true (from Step 3 enhanced temporal extraction)
2. Ethical questions from Step 4 synthesis

For each decision point, generates:
- Decision question
- Context and stakes
- Decision options (actual choice + alternatives from action metadata)
- Arguments for/against each option
- Links to code provisions and principles
- Ethical tensions and competing values

Documentation: docs/SCENARIO_SYNTHESIS_ARCHITECTURE_REVISED.md (Stage 4)
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from app.utils.llm_utils import get_llm_client

logger = logging.getLogger(__name__)


@dataclass
class DecisionOption:
    """A single decision option (choice the agent could make)."""
    id: str
    label: str  # Short description
    description: str  # Full description of this option
    is_actual_choice: bool  # Whether this was the actual choice made

    # Arguments
    arguments_for: List[str]  # Reasons to choose this option
    arguments_against: List[str]  # Reasons to reject this option

    # Ethical analysis
    principles_supported: List[str]  # Principles this option upholds
    principles_violated: List[str]  # Principles this option violates
    obligations_fulfilled: List[str]  # Obligations this satisfies
    obligations_neglected: List[str]  # Obligations this ignores

    # Consequences
    likely_consequences: List[str]  # What would happen if chosen

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dictionary."""
        return {
            'id': self.id,
            'label': self.label,
            'description': self.description,
            'is_actual_choice': self.is_actual_choice,
            'arguments_for': self.arguments_for,
            'arguments_against': self.arguments_against,
            'principles_supported': self.principles_supported,
            'principles_violated': self.principles_violated,
            'obligations_fulfilled': self.obligations_fulfilled,
            'obligations_neglected': self.obligations_neglected,
            'likely_consequences': self.likely_consequences
        }


@dataclass
class DecisionPoint:
    """
    A critical decision moment in the scenario.

    Built from actions with isDecisionPoint=true and ethical questions.
    """
    # Identity
    id: str  # Unique identifier
    decision_question: str  # The central ethical question

    # Context
    timepoint: str  # When this decision occurs (from timeline)
    decision_maker: str  # Who must decide (participant)
    situation_context: str  # What's happening

    # Stakes and tensions
    ethical_tension: str  # Core ethical conflict
    stakes: str  # What's at risk
    competing_values: List[str]  # Which values/duties conflict

    # Options
    options: List[DecisionOption]  # Available choices
    actual_choice_id: str  # Which option was actually chosen

    # Links
    related_action_uri: Optional[str]  # Source action entity
    related_question_uris: List[str]  # Related ethical questions from Step 4
    code_provisions: List[str]  # Relevant NSPE code sections

    # Metadata
    source_type: str  # 'action' or 'question'
    narrative_significance: str  # Why this matters for learning

    # Source data
    extracted_data: Dict[str, Any]  # Original RDF data

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dictionary."""
        return {
            'id': self.id,
            'decision_question': self.decision_question,
            'timepoint': self.timepoint,
            'decision_maker': self.decision_maker,
            'situation_context': self.situation_context,
            'ethical_tension': self.ethical_tension,
            'stakes': self.stakes,
            'competing_values': self.competing_values,
            'options': [opt.to_dict() for opt in self.options],
            'actual_choice_id': self.actual_choice_id,
            'related_action_uri': self.related_action_uri,
            'related_question_uris': self.related_question_uris,
            'code_provisions': self.code_provisions,
            'source_type': self.source_type,
            'narrative_significance': self.narrative_significance
        }


@dataclass
class DecisionIdentificationResult:
    """Result of Stage 4 decision identification."""
    decision_points: List[DecisionPoint]
    total_decisions: int
    decisions_from_actions: int
    decisions_from_questions: int
    llm_prompt: Optional[str] = None
    llm_response: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dictionary."""
        return {
            'total_decisions': self.total_decisions,
            'decisions_from_actions': self.decisions_from_actions,
            'decisions_from_questions': self.decisions_from_questions,
            'decision_points': [dp.to_dict() for dp in self.decision_points]
        }


class DecisionIdentifier:
    """
    Stage 4: Identify decision points from actions and questions.

    Extracts critical decision moments and enriches them with:
    - Decision options
    - Arguments for/against
    - Ethical analysis
    - Code provision links
    """

    def __init__(self):
        """Initialize decision identifier with LLM client."""
        self.llm_client = get_llm_client()
        logger.info("[Decision Identifier] Initialized")

    def identify_decisions(
        self,
        actions: List[Any],  # RDFEntity objects
        questions: List[Any],  # RDFEntity objects
        timeline_data: Optional[Dict] = None,
        participants: Optional[List] = None,
        synthesis_data: Optional[Any] = None
    ) -> DecisionIdentificationResult:
        """
        Identify decision points from actions and ethical questions.

        Args:
            actions: List of action entities from temporal extraction
            questions: List of ethical question entities from Step 4
            timeline_data: Optional timeline for temporal context
            participants: Optional participant profiles for decision makers
            synthesis_data: Optional synthesis data for code provisions

        Returns:
            DecisionIdentificationResult with decision points
        """
        logger.info(f"[Decision Identifier] Processing {len(actions)} actions, {len(questions)} questions")

        decision_points = []

        # Extract decisions from actions with isDecisionPoint=true
        action_decisions = self._identify_from_actions(
            actions,
            timeline_data,
            participants,
            synthesis_data
        )
        decision_points.extend(action_decisions)

        # Extract decisions from ethical questions
        question_decisions = self._identify_from_questions(
            questions,
            actions,
            participants,
            synthesis_data
        )
        decision_points.extend(question_decisions)

        result = DecisionIdentificationResult(
            decision_points=decision_points,
            total_decisions=len(decision_points),
            decisions_from_actions=len(action_decisions),
            decisions_from_questions=len(question_decisions)
        )

        logger.info(
            f"[Decision Identifier] Identified {len(decision_points)} decision points "
            f"({len(action_decisions)} from actions, {len(question_decisions)} from questions)"
        )

        return result

    def _identify_from_actions(
        self,
        actions: List[Any],
        timeline_data: Optional[Dict],
        participants: Optional[List],
        synthesis_data: Optional[Any]
    ) -> List[DecisionPoint]:
        """Identify decision points from actions with isDecisionPoint=true."""
        decision_points = []

        for action in actions:
            try:
                rdf_data = action.rdf_json_ld if hasattr(action, 'rdf_json_ld') else {}

                # Debug: Log what we're seeing
                logger.debug(f"[Decision Identifier] Checking action: {action.label}")
                logger.debug(f"[Decision Identifier] RDF data keys: {list(rdf_data.keys()) if rdf_data else 'None'}")
                if rdf_data and 'proeth-scenario:isDecisionPoint' in rdf_data:
                    logger.debug(f"[Decision Identifier] isDecisionPoint value: {rdf_data['proeth-scenario:isDecisionPoint']}")

                # Check if this is a decision point
                is_decision = rdf_data.get('proeth-scenario:isDecisionPoint', False)
                if not is_decision:
                    logger.debug(f"[Decision Identifier] Action {action.label} is not a decision point (value: {is_decision})")
                    continue

                logger.info(f"[Decision Identifier] Found decision point: {action.label}")

                # Extract decision point data
                decision = self._create_decision_from_action(
                    action,
                    rdf_data,
                    timeline_data,
                    participants,
                    synthesis_data
                )

                if decision:
                    decision_points.append(decision)
                    logger.debug(f"[Decision Identifier] Created decision from action: {action.label}")

            except Exception as e:
                logger.error(f"[Decision Identifier] Error processing action {action.label}: {e}", exc_info=True)
                continue

        return decision_points

    def _create_decision_from_action(
        self,
        action: Any,
        rdf_data: Dict,
        timeline_data: Optional[Dict],
        participants: Optional[List],
        synthesis_data: Optional[Any]
    ) -> Optional[DecisionPoint]:
        """Create a DecisionPoint from an action entity."""

        # Extract scenario metadata
        ethical_tension = rdf_data.get('proeth-scenario:ethicalTension', 'Ethical tension not specified')
        stakes = rdf_data.get('proeth-scenario:stakes', 'Stakes not specified')
        decision_significance = rdf_data.get('proeth-scenario:decisionSignificance', '')
        alternative_actions = rdf_data.get('proeth-scenario:alternativeActions', [])
        consequences_if_alternative = rdf_data.get('proeth-scenario:consequencesIfAlternative', [])
        character_motivation = rdf_data.get('proeth-scenario:characterMotivation', '')

        # Extract action data
        description = rdf_data.get('proeth:description', action.label)
        agent = rdf_data.get('proeth:hasAgent', 'Unknown')
        timepoint = rdf_data.get('proeth:temporalMarker', 'Time unknown')

        # Generate decision question
        decision_question = f"Should {agent} {action.label.lower()}?"

        # Create decision options
        options = []

        # Generate safe base ID for options
        if action.uri:
            base_id = action.uri
        else:
            base_id = action.label.replace(' ', '_')

        # Option 1: Actual choice made
        actual_option = DecisionOption(
            id=f"{base_id}_actual",
            label=action.label,
            description=description,
            is_actual_choice=True,
            arguments_for=[character_motivation] if character_motivation else [],
            arguments_against=[],  # Will be filled by LLM
            principles_supported=self._extract_principles(rdf_data, 'proeth:guidedByPrinciple'),
            principles_violated=[],
            obligations_fulfilled=self._extract_obligations(rdf_data, 'proeth:fulfillsObligation'),
            obligations_neglected=[],
            likely_consequences=self._extract_consequences(rdf_data)
        )
        options.append(actual_option)

        # Options 2+: Alternatives
        for i, alt_action in enumerate(alternative_actions):
            alt_consequences = consequences_if_alternative[i] if i < len(consequences_if_alternative) else ''

            alt_option = DecisionOption(
                id=f"{base_id}_alt_{i}",
                label=f"Alternative {i+1}",
                description=alt_action,
                is_actual_choice=False,
                arguments_for=[],  # Will be filled by LLM
                arguments_against=[],
                principles_supported=[],
                principles_violated=[],
                obligations_fulfilled=[],
                obligations_neglected=[],
                likely_consequences=[alt_consequences] if alt_consequences else []
            )
            options.append(alt_option)

        # Extract code provisions
        code_provisions = self._extract_code_provisions(rdf_data, synthesis_data)

        # Create decision point
        # Generate safe ID from URI or label
        if action.uri and '#' in action.uri:
            decision_id = f"decision_{action.uri.split('#')[-1]}"
        else:
            # Fallback: use label with underscores
            decision_id = f"decision_{action.label.replace(' ', '_')}"

        decision = DecisionPoint(
            id=decision_id,
            decision_question=decision_question,
            timepoint=timepoint,
            decision_maker=agent,
            situation_context=description,
            ethical_tension=ethical_tension,
            stakes=stakes,
            competing_values=self._extract_competing_values(ethical_tension),
            options=options,
            actual_choice_id=actual_option.id,
            related_action_uri=action.uri if action.uri else '',
            related_question_uris=[],
            code_provisions=code_provisions,
            source_type='action',
            narrative_significance=decision_significance,
            extracted_data=rdf_data
        )

        return decision

    def _identify_from_questions(
        self,
        questions: List[Any],
        actions: List[Any],
        participants: Optional[List],
        synthesis_data: Optional[Any]
    ) -> List[DecisionPoint]:
        """Identify decision points from ethical questions."""
        decision_points = []

        # For now, skip question-based decisions (focus on action-based)
        # Can enhance later to convert questions into decision points

        return decision_points

    def _extract_principles(self, rdf_data: Dict, key: str) -> List[str]:
        """Extract principle URIs and convert to labels."""
        principles = rdf_data.get(key, [])
        if not principles:
            return []
        if isinstance(principles, str):
            principles = [principles]

        # Extract labels from URIs (handle None values)
        result = []
        for p in principles:
            if p and isinstance(p, str):
                result.append(p.split('#')[-1].replace('_', ' '))
        return result

    def _extract_obligations(self, rdf_data: Dict, key: str) -> List[str]:
        """Extract obligation URIs and convert to labels."""
        obligations = rdf_data.get(key, [])
        if not obligations:
            return []
        if isinstance(obligations, str):
            obligations = [obligations]

        # Extract labels from URIs (handle None values)
        result = []
        for o in obligations:
            if o and isinstance(o, str):
                result.append(o.split('#')[-1].replace('_', ' '))
        return result

    def _extract_consequences(self, rdf_data: Dict) -> List[str]:
        """Extract consequence descriptions."""
        intended = rdf_data.get('proeth:intendedOutcome', '')
        foreseen = rdf_data.get('proeth:foreseenUnintendedEffects', [])

        consequences = []
        if intended:
            consequences.append(f"Intended: {intended}")
        if foreseen:
            if isinstance(foreseen, list):
                consequences.extend([f"Foreseen: {f}" for f in foreseen])
            else:
                consequences.append(f"Foreseen: {foreseen}")

        return consequences

    def _extract_competing_values(self, ethical_tension: str) -> List[str]:
        """Extract competing values from ethical tension description."""
        # Simple heuristic: split on "vs.", "versus", "vs", or "conflict between"
        tension_lower = ethical_tension.lower()

        if ' vs. ' in tension_lower:
            parts = ethical_tension.split(' vs. ')
            return [p.strip() for p in parts]
        elif ' vs ' in tension_lower:
            parts = ethical_tension.split(' vs ')
            return [p.strip() for p in parts]
        elif 'versus' in tension_lower:
            parts = ethical_tension.split('versus')
            return [p.strip() for p in parts]
        elif 'conflict between' in tension_lower:
            # Extract text after "conflict between"
            idx = tension_lower.index('conflict between')
            text = ethical_tension[idx + len('conflict between'):].strip()
            if ' and ' in text:
                parts = text.split(' and ')
                return [p.strip() for p in parts]

        # Fallback: return the whole tension as single value
        return [ethical_tension]

    def _extract_code_provisions(
        self,
        rdf_data: Dict,
        synthesis_data: Optional[Any]
    ) -> List[str]:
        """Extract relevant code provisions."""
        # TODO: Link to code provisions from Step 4 synthesis
        # For now, return empty list
        return []
