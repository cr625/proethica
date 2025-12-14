"""
Decision Point Composer (Step E3)

Composes entity-grounded decision points from the outputs of E1 and E2.
Each decision point is a (Role, Obligation, ActionSet) triple representing
a point where an ethical choice must be made.

Based on Harris et al. (2018): Line-drawing methodology for determining
where ethical boundaries lie by comparing to paradigm cases.
"""

import logging
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict

from app import db
from app.models import TemporaryRDFStorage
from app.domains import DomainConfig, get_domain_config
from app.services.entity_analysis.obligation_coverage_analyzer import (
    CoverageMatrix,
    ObligationAnalysis,
    ConstraintAnalysis,
    get_obligation_coverage
)
from app.services.entity_analysis.action_option_mapper import (
    ActionOptionMap,
    ActionSet,
    ActionOption,
    get_action_option_map
)

logger = logging.getLogger(__name__)


@dataclass
class DecisionPointGrounding:
    """Entity URIs that ground a decision point."""
    role_uri: str
    role_label: str
    obligation_uri: Optional[str] = None
    obligation_label: Optional[str] = None
    constraint_uri: Optional[str] = None
    constraint_label: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionPointOption:
    """An option within a decision point, grounded in extracted entities."""
    option_id: str
    action_uri: str
    action_label: str
    description: str
    is_board_choice: bool = False
    is_extracted_action: bool = True
    intensity_score: float = 0.0
    downstream_event_uris: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PrecedentParadigm:
    """Precedent case paradigm for line-drawing comparison."""
    case_id: str
    case_title: str
    paradigm_type: str  # 'positive' or 'negative'
    similarity_score: float = 0.0
    shared_features: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EntityGroundedDecisionPoint:
    """
    A decision point fully grounded in extracted entities.

    This is the key output structure combining E1 and E2 analysis.
    """
    focus_id: str
    focus_number: int
    description: str
    decision_question: str

    # Entity grounding
    grounding: DecisionPointGrounding

    # Options (from ActionSet)
    options: List[DecisionPointOption] = field(default_factory=list)

    # Related entities
    provision_uris: List[str] = field(default_factory=list)
    provision_labels: List[str] = field(default_factory=list)
    related_event_uris: List[str] = field(default_factory=list)

    # Board resolution (from Step 4)
    board_question_uri: Optional[str] = None
    board_conclusion_uri: Optional[str] = None
    board_conclusion_text: Optional[str] = None

    # Line-drawing paradigms
    precedent_paradigms: List[PrecedentParadigm] = field(default_factory=list)
    paradigmatic_features: List[str] = field(default_factory=list)

    # Scores
    intensity_score: float = 0.0
    decision_relevance_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'focus_id': self.focus_id,
            'focus_number': self.focus_number,
            'description': self.description,
            'decision_question': self.decision_question,
            'grounding': self.grounding.to_dict(),
            'options': [o.to_dict() for o in self.options],
            'provision_uris': self.provision_uris,
            'provision_labels': self.provision_labels,
            'related_event_uris': self.related_event_uris,
            'board_question_uri': self.board_question_uri,
            'board_conclusion_uri': self.board_conclusion_uri,
            'board_conclusion_text': self.board_conclusion_text,
            'precedent_paradigms': [p.to_dict() for p in self.precedent_paradigms],
            'paradigmatic_features': self.paradigmatic_features,
            'intensity_score': self.intensity_score,
            'decision_relevance_score': self.decision_relevance_score
        }


@dataclass
class ComposedDecisionPoints:
    """Complete set of composed decision points for a case."""
    case_id: int
    decision_points: List[EntityGroundedDecisionPoint] = field(default_factory=list)
    unmatched_obligations: List[str] = field(default_factory=list)  # Obligations without matching actions
    unmatched_actions: List[str] = field(default_factory=list)  # Actions without matching obligations

    def to_dict(self) -> Dict[str, Any]:
        return {
            'case_id': self.case_id,
            'decision_points': [dp.to_dict() for dp in self.decision_points],
            'unmatched_obligations': self.unmatched_obligations,
            'unmatched_actions': self.unmatched_actions
        }


# Keywords for matching obligations to actions
OBLIGATION_ACTION_KEYWORDS = {
    'disclosure': ['disclosure', 'disclose', 'non-disclosure'],
    'verification': ['review', 'verify', 'verification', 'audit'],
    'competence': ['adoption', 'use', 'competence', 'software'],
    'confidentiality': ['upload', 'data', 'privacy', 'confidential'],
    'attribution': ['attribution', 'credit', 'seal', 'application'],
    'safety': ['safety', 'design', 'review', 'error'],
}


class DecisionPointComposer:
    """
    Composes entity-grounded decision points from E1 and E2 outputs.

    Step E3 in the entity-grounded argument pipeline.
    """

    def __init__(self, domain_config: Optional[DomainConfig] = None):
        """
        Initialize with optional domain configuration.

        Args:
            domain_config: Domain-specific config. Defaults to engineering.
        """
        self.domain = domain_config or get_domain_config('engineering')
        self.methodology = self.domain.ethical_framework.methodology

    def compose_decision_points(
        self,
        case_id: int,
        coverage_matrix: Optional[CoverageMatrix] = None,
        action_map: Optional[ActionOptionMap] = None
    ) -> ComposedDecisionPoints:
        """
        Compose decision points from coverage matrix and action map.

        Args:
            case_id: The case to analyze
            coverage_matrix: Output from E1 (optional, will compute if not provided)
            action_map: Output from E2 (optional, will compute if not provided)

        Returns:
            ComposedDecisionPoints with entity-grounded decision points
        """
        logger.info(f"Composing decision points for case {case_id}")

        # Get E1 and E2 outputs if not provided
        if coverage_matrix is None:
            coverage_matrix = get_obligation_coverage(case_id, self.domain.name)
        if action_map is None:
            action_map = get_action_option_map(case_id, self.domain.name)

        # Load Board Q&C from Step 4
        questions, conclusions = self._load_board_qc(case_id)

        # Load provisions from Step 4
        provisions = self._load_provisions(case_id)

        # Match obligations/constraints to action sets
        decision_points = []
        matched_obligation_uris = set()
        matched_action_uris = set()

        focus_number = 1

        # Process decision-relevant obligations
        for obligation in coverage_matrix.obligations:
            if not obligation.decision_relevant:
                continue

            # Find matching action set
            action_set = self._find_matching_action_set(obligation, action_map)

            if action_set:
                matched_action_uris.add(action_set.primary_action_uri)

                # Compose decision point
                dp = self._compose_from_obligation(
                    obligation=obligation,
                    action_set=action_set,
                    questions=questions,
                    conclusions=conclusions,
                    provisions=provisions,
                    focus_number=focus_number,
                    case_id=case_id
                )
                decision_points.append(dp)
                matched_obligation_uris.add(obligation.entity_uri)
                focus_number += 1

        # Process decision-relevant constraints (may create additional DPs)
        for constraint in coverage_matrix.constraints:
            if not constraint.decision_relevant:
                continue

            # Check if already covered by an obligation
            if constraint.constrained_role:
                role_covered = any(
                    dp.grounding.role_label == constraint.constrained_role
                    for dp in decision_points
                )
                if role_covered:
                    continue

            # Find matching action set for constraint
            action_set = self._find_matching_action_set_for_constraint(constraint, action_map)

            if action_set and action_set.primary_action_uri not in matched_action_uris:
                matched_action_uris.add(action_set.primary_action_uri)

                dp = self._compose_from_constraint(
                    constraint=constraint,
                    action_set=action_set,
                    questions=questions,
                    conclusions=conclusions,
                    provisions=provisions,
                    focus_number=focus_number,
                    case_id=case_id
                )
                decision_points.append(dp)
                focus_number += 1

        # Sort by intensity score
        decision_points.sort(key=lambda dp: dp.intensity_score, reverse=True)

        # Re-number after sorting
        for i, dp in enumerate(decision_points, 1):
            dp.focus_number = i
            dp.focus_id = f"DP{i}"

        # Find unmatched items
        unmatched_obligations = [
            o.entity_label for o in coverage_matrix.obligations
            if o.decision_relevant and o.entity_uri not in matched_obligation_uris
        ]
        unmatched_actions = [
            s.primary_action_uri for s in action_map.action_sets
            if s.primary_action_uri not in matched_action_uris
        ]

        result = ComposedDecisionPoints(
            case_id=case_id,
            decision_points=decision_points,
            unmatched_obligations=unmatched_obligations,
            unmatched_actions=unmatched_actions
        )

        logger.info(
            f"Composed {len(decision_points)} decision points, "
            f"{len(unmatched_obligations)} unmatched obligations, "
            f"{len(unmatched_actions)} unmatched actions"
        )

        return result

    def _load_board_qc(self, case_id: int) -> Tuple[List[Dict], List[Dict]]:
        """Load Board questions and conclusions from Step 4."""
        questions_raw = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_question'
        ).all()

        conclusions_raw = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_conclusion'
        ).all()

        questions = [
            {
                'uri': q.entity_uri or f"case-{case_id}#Q{i+1}",
                'label': q.entity_label,
                'text': q.entity_definition or q.entity_label
            }
            for i, q in enumerate(questions_raw)
        ]

        conclusions = [
            {
                'uri': c.entity_uri or f"case-{case_id}#C{i+1}",
                'label': c.entity_label,
                'text': c.entity_definition or c.entity_label
            }
            for i, c in enumerate(conclusions_raw)
        ]

        return questions, conclusions

    def _load_provisions(self, case_id: int) -> List[Dict]:
        """Load code provisions from Step 4."""
        provisions_raw = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='code_provision_reference'
        ).all()

        return [
            {
                'uri': p.entity_uri or f"case-{case_id}#{p.entity_label.replace(' ', '_')}",
                'label': p.entity_label,
                'text': p.entity_definition or ""
            }
            for p in provisions_raw
        ]

    def _find_matching_action_set(
        self,
        obligation: ObligationAnalysis,
        action_map: ActionOptionMap
    ) -> Optional[ActionSet]:
        """Find an action set that matches an obligation."""
        obl_text = f"{obligation.entity_label} {obligation.entity_definition}".lower()
        obl_type = obligation.decision_type

        best_match = None
        best_score = 0

        for action_set in action_map.action_sets:
            action_text = action_set.decision_context.lower()
            primary_label = action_set.actions[0].label.lower() if action_set.actions else ""

            score = self._calculate_match_score(obl_text, obl_type, action_text, primary_label)

            if score > best_score:
                best_score = score
                best_match = action_set

        # Require minimum match score
        if best_score >= 0.3:
            return best_match

        return None

    def _find_matching_action_set_for_constraint(
        self,
        constraint: ConstraintAnalysis,
        action_map: ActionOptionMap
    ) -> Optional[ActionSet]:
        """Find an action set that matches a constraint."""
        con_text = f"{constraint.entity_label} {constraint.entity_definition}".lower()

        best_match = None
        best_score = 0

        for action_set in action_map.action_sets:
            action_text = action_set.decision_context.lower()
            primary_label = action_set.actions[0].label.lower() if action_set.actions else ""

            # Simple keyword overlap
            con_words = set(con_text.split())
            action_words = set(f"{action_text} {primary_label}".split())
            overlap = len(con_words & action_words)
            score = overlap / max(len(con_words), 1)

            if score > best_score:
                best_score = score
                best_match = action_set

        if best_score >= 0.2:
            return best_match

        return None

    def _calculate_match_score(
        self,
        obl_text: str,
        obl_type: str,
        action_text: str,
        action_label: str
    ) -> float:
        """Calculate how well an obligation matches an action."""
        score = 0.0

        # Check keyword overlap based on obligation type
        if obl_type in OBLIGATION_ACTION_KEYWORDS:
            keywords = OBLIGATION_ACTION_KEYWORDS[obl_type]
            for kw in keywords:
                if kw in action_text or kw in action_label:
                    score += 0.3

        # Check direct word overlap
        obl_words = set(obl_text.split())
        action_words = set(f"{action_text} {action_label}".split())
        overlap = len(obl_words & action_words)
        score += overlap * 0.05

        return min(score, 1.0)

    def _compose_from_obligation(
        self,
        obligation: ObligationAnalysis,
        action_set: ActionSet,
        questions: List[Dict],
        conclusions: List[Dict],
        provisions: List[Dict],
        focus_number: int,
        case_id: int
    ) -> EntityGroundedDecisionPoint:
        """Compose a decision point from an obligation and action set."""

        # Build grounding
        grounding = DecisionPointGrounding(
            role_uri=obligation.bound_role_uri or f"case-{case_id}#Unknown_Role",
            role_label=obligation.bound_role or "Unknown Role",
            obligation_uri=obligation.entity_uri,
            obligation_label=obligation.entity_label
        )

        # Build options from action set
        options = []
        for i, action in enumerate(action_set.actions):
            opt = DecisionPointOption(
                option_id=f"O{i+1}",
                action_uri=action.uri,
                action_label=action.label,
                description=action.description or action.label,
                is_board_choice=action.is_board_choice,
                is_extracted_action=action.is_extracted,
                intensity_score=action.intensity_score.overall if action.intensity_score else 0.0,
                downstream_event_uris=action.downstream_events
            )
            options.append(opt)

        # Find matching Board Q&C
        board_q, board_c = self._match_board_qc(
            obligation.entity_label, questions, conclusions
        )

        # Find related provisions
        related_provisions = self._find_related_provisions(
            obligation, provisions
        )

        # Collect related events
        related_events = []
        for action in action_set.actions:
            related_events.extend(action.downstream_events)

        # Generate decision question
        decision_question = self._generate_decision_question(
            grounding.role_label, obligation.entity_label, action_set.decision_context
        )

        # Extract paradigmatic features for line-drawing
        features = self._extract_paradigmatic_features(obligation, action_set)

        return EntityGroundedDecisionPoint(
            focus_id=f"DP{focus_number}",
            focus_number=focus_number,
            description=f"{grounding.role_label}: {obligation.entity_label}",
            decision_question=decision_question,
            grounding=grounding,
            options=options,
            provision_uris=[p['uri'] for p in related_provisions],
            provision_labels=[p['label'] for p in related_provisions],
            related_event_uris=list(set(related_events)),
            board_question_uri=board_q.get('uri') if board_q else None,
            board_conclusion_uri=board_c.get('uri') if board_c else None,
            board_conclusion_text=board_c.get('text') if board_c else None,
            paradigmatic_features=features,
            intensity_score=action_set.max_intensity_score,
            decision_relevance_score=1.0 if obligation.conflicts_with else 0.7
        )

    def _compose_from_constraint(
        self,
        constraint: ConstraintAnalysis,
        action_set: ActionSet,
        questions: List[Dict],
        conclusions: List[Dict],
        provisions: List[Dict],
        focus_number: int,
        case_id: int
    ) -> EntityGroundedDecisionPoint:
        """Compose a decision point from a constraint and action set."""

        grounding = DecisionPointGrounding(
            role_uri=constraint.constrained_role_uri or f"case-{case_id}#Unknown_Role",
            role_label=constraint.constrained_role or "Unknown Role",
            constraint_uri=constraint.entity_uri,
            constraint_label=constraint.entity_label
        )

        options = []
        for i, action in enumerate(action_set.actions):
            opt = DecisionPointOption(
                option_id=f"O{i+1}",
                action_uri=action.uri,
                action_label=action.label,
                description=action.description or action.label,
                is_board_choice=action.is_board_choice,
                is_extracted_action=action.is_extracted,
                intensity_score=action.intensity_score.overall if action.intensity_score else 0.0,
                downstream_event_uris=action.downstream_events
            )
            options.append(opt)

        board_q, board_c = self._match_board_qc(
            constraint.entity_label, questions, conclusions
        )

        decision_question = self._generate_decision_question(
            grounding.role_label, constraint.entity_label, action_set.decision_context
        )

        return EntityGroundedDecisionPoint(
            focus_id=f"DP{focus_number}",
            focus_number=focus_number,
            description=f"{grounding.role_label}: {constraint.entity_label}",
            decision_question=decision_question,
            grounding=grounding,
            options=options,
            provision_uris=[],
            provision_labels=[],
            related_event_uris=[],
            board_question_uri=board_q.get('uri') if board_q else None,
            board_conclusion_uri=board_c.get('uri') if board_c else None,
            board_conclusion_text=board_c.get('text') if board_c else None,
            paradigmatic_features=[],
            intensity_score=action_set.max_intensity_score,
            decision_relevance_score=0.8 if constraint.founding_value_limit else 0.5
        )

    def _match_board_qc(
        self,
        entity_label: str,
        questions: List[Dict],
        conclusions: List[Dict]
    ) -> Tuple[Optional[Dict], Optional[Dict]]:
        """Find Board question and conclusion that match this entity."""
        entity_lower = entity_label.lower()

        # Simple keyword matching
        best_q = None
        best_c = None

        for q in questions:
            q_text = q.get('text', '').lower()
            if any(word in q_text for word in entity_lower.split('_')):
                best_q = q
                break

        for c in conclusions:
            c_text = c.get('text', '').lower()
            if any(word in c_text for word in entity_lower.split('_')):
                best_c = c
                break

        return best_q, best_c

    def _find_related_provisions(
        self,
        obligation: ObligationAnalysis,
        provisions: List[Dict]
    ) -> List[Dict]:
        """Find provisions related to this obligation."""
        # Use provisions from obligation's extraction if available
        if obligation.related_provisions:
            return [
                p for p in provisions
                if any(rp in p['label'] for rp in obligation.related_provisions)
            ]

        # Otherwise, try keyword matching
        obl_lower = obligation.entity_label.lower()
        related = []

        for p in provisions:
            p_label = p['label'].lower()
            # Check for common terms
            if any(term in p_label for term in ['disclosure', 'competence', 'safety']):
                if any(term in obl_lower for term in ['disclosure', 'competence', 'safety']):
                    related.append(p)

        return related[:3]  # Limit to 3

    def _generate_decision_question(
        self,
        role: str,
        entity_label: str,
        action_context: str
    ) -> str:
        """Generate a human-readable decision question."""
        # Clean up the entity label
        clean_label = entity_label.replace('_', ' ')

        # Remove role prefix if present
        for prefix in [role.replace(' ', ''), role]:
            if clean_label.startswith(prefix):
                clean_label = clean_label[len(prefix):].strip()

        return f"Should {role} fulfill the {clean_label} given the circumstances?"

    def _extract_paradigmatic_features(
        self,
        obligation: ObligationAnalysis,
        action_set: ActionSet
    ) -> List[str]:
        """
        Extract paradigmatic features for line-drawing comparison.

        Harris et al. (2018) line-drawing uses features to compare
        test cases to paradigm cases.
        """
        features = []

        # From obligation
        if obligation.decision_type:
            features.append(f"decision_type:{obligation.decision_type}")
        if obligation.is_instantiated:
            features.append("role_bound:yes")
        if obligation.conflicts_with:
            features.append("has_conflicts:yes")

        # From action set
        if action_set.max_intensity_score > 0.7:
            features.append("intensity:high")
        elif action_set.max_intensity_score > 0.4:
            features.append("intensity:medium")
        else:
            features.append("intensity:low")

        # Check for causal consequences
        has_consequences = any(
            a.downstream_events for a in action_set.actions
        )
        if has_consequences:
            features.append("has_consequences:yes")

        return features


def compose_decision_points(
    case_id: int,
    domain: str = 'engineering'
) -> ComposedDecisionPoints:
    """
    Convenience function to compose decision points.

    Args:
        case_id: Case to analyze
        domain: Domain code (default: engineering)

    Returns:
        ComposedDecisionPoints with entity-grounded decision points
    """
    domain_config = get_domain_config(domain)
    composer = DecisionPointComposer(domain_config)
    return composer.compose_decision_points(case_id)
