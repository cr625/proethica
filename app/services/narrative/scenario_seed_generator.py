"""
Scenario Seed Generator (Stage 4.3)

Generates scenario seeds for interactive Step 5 scenario generation.
Links decision points to branch structures for turn-by-turn exploration.

Uses transformation classification to guide branch structure generation.
"""

import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict

from app.utils.llm_utils import get_llm_client
from app.academic_references.frameworks.transformation_classification import (
    TRANSFORMATION_TYPES,
    get_prompt_context as get_transformation_context
)

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ScenarioOption:
    """An option within a scenario branch."""
    option_id: str
    label: str
    description: str
    action_uris: List[str] = field(default_factory=list)
    is_board_choice: bool = False
    leads_to: Optional[str] = None  # Next branch ID


@dataclass
class ScenarioBranch:
    """A branch point in the scenario."""
    branch_id: str
    context: str  # Situation description
    question: str  # What decision must be made
    decision_point_uri: str

    # Entity grounding
    decision_maker_uri: str
    decision_maker_label: str
    involved_obligation_uris: List[str] = field(default_factory=list)

    # Options
    options: List[ScenarioOption] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            **asdict(self),
            'options': [asdict(o) for o in self.options]
        }


@dataclass
class AlternativePath:
    """An alternative path through the scenario."""
    path_id: str
    description: str
    choice_sequence: List[str]  # Branch choices taken
    outcome_description: str
    ethical_assessment: str = ""


@dataclass
class ScenarioSeeds:
    """Complete scenario seeds for Step 5."""
    case_id: int

    # Entry point
    opening_context: str
    initial_state_description: str

    # Characters
    protagonist_uri: str
    protagonist_label: str
    supporting_characters: List[Dict] = field(default_factory=list)

    # Branch structure
    branches: List[ScenarioBranch] = field(default_factory=list)

    # Paths
    canonical_path: List[str] = field(default_factory=list)  # Board's actual path
    alternative_paths: List[AlternativePath] = field(default_factory=list)

    # Transformation classification
    transformation_type: str = ""

    def to_dict(self) -> Dict:
        return {
            'case_id': self.case_id,
            'opening_context': self.opening_context,
            'initial_state_description': self.initial_state_description,
            'protagonist_uri': self.protagonist_uri,
            'protagonist_label': self.protagonist_label,
            'supporting_characters': self.supporting_characters,
            'branches': [b.to_dict() for b in self.branches],
            'canonical_path': self.canonical_path,
            'alternative_paths': [asdict(p) for p in self.alternative_paths],
            'transformation_type': self.transformation_type
        }

    def summary(self) -> Dict:
        return {
            'branches_count': len(self.branches),
            'options_count': sum(len(b.options) for b in self.branches),
            'alternative_paths': len(self.alternative_paths),
            'has_canonical_path': len(self.canonical_path) > 0
        }


# =============================================================================
# SCENARIO SEED GENERATOR SERVICE
# =============================================================================

class ScenarioSeedGenerator:
    """
    Generates scenario seeds from narrative elements and decision points.

    Uses transformation classification to guide branch structure.
    """

    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        self.llm_client = get_llm_client() if use_llm else None

    def generate(
        self,
        case_id: int,
        narrative_elements,  # NarrativeElements from Stage 4.1
        timeline=None,  # EntityGroundedTimeline from Stage 4.2
        transformation_type: str = None
    ) -> ScenarioSeeds:
        """
        Generate scenario seeds from narrative elements.

        Args:
            case_id: Case ID
            narrative_elements: NarrativeElements from Stage 4.1
            timeline: EntityGroundedTimeline from Stage 4.2
            transformation_type: Case transformation classification

        Returns:
            ScenarioSeeds for Step 5 scenario generation
        """
        # Extract protagonist
        protagonist = self._identify_protagonist(narrative_elements.characters)

        # Build opening context
        opening_context = self._build_opening_context(
            narrative_elements.setting,
            protagonist
        )

        # Build branches from decision moments
        branches = self._build_branches(
            narrative_elements.decision_moments,
            narrative_elements.conflicts
        )

        # Build canonical path (board's choices)
        canonical_path = self._extract_canonical_path(
            narrative_elements.decision_moments
        )

        # Generate alternative paths
        alternative_paths = self._generate_alternative_paths(
            branches, canonical_path, transformation_type
        )

        # Enhance with LLM if enabled
        if self.use_llm and self.llm_client:
            opening_context = self._enhance_opening_with_llm(
                opening_context, narrative_elements, case_id
            )

        return ScenarioSeeds(
            case_id=case_id,
            opening_context=opening_context,
            initial_state_description=narrative_elements.setting.description if narrative_elements.setting else "",
            protagonist_uri=protagonist.uri if protagonist else "",
            protagonist_label=protagonist.label if protagonist else "",
            supporting_characters=[
                {'uri': c.uri, 'label': c.label, 'role_type': c.role_type}
                for c in narrative_elements.characters[1:5]
            ],
            branches=branches,
            canonical_path=canonical_path,
            alternative_paths=alternative_paths,
            transformation_type=transformation_type or ""
        )

    def _identify_protagonist(self, characters: List) -> Optional[Any]:
        """Identify the protagonist from characters."""
        # First, look for explicit protagonist
        for char in characters:
            if hasattr(char, 'role_type') and char.role_type == 'protagonist':
                return char

        # Fall back to first character
        return characters[0] if characters else None

    def _build_opening_context(self, setting, protagonist) -> str:
        """Build opening context for scenario."""
        parts = []

        if protagonist:
            parts.append(f"You are {protagonist.label}.")

        if setting:
            parts.append(setting.description)

        if protagonist and hasattr(protagonist, 'professional_position'):
            if protagonist.professional_position:
                parts.append(f"Your role: {protagonist.professional_position}")

        return " ".join(parts)

    def _build_branches(
        self,
        decision_moments: List,
        conflicts: List
    ) -> List[ScenarioBranch]:
        """Build scenario branches from decision moments."""
        branches = []

        for i, decision in enumerate(decision_moments):
            # Build context from decision
            context = decision.description if hasattr(decision, 'description') else ""

            # Build options
            options = []
            if hasattr(decision, 'options') and decision.options:
                for j, opt in enumerate(decision.options):
                    options.append(ScenarioOption(
                        option_id=f"opt_{i}_{j}",
                        label=opt.get('label', f"Option {j+1}"),
                        description=opt.get('description', ''),
                        action_uris=opt.get('action_uris', []),
                        is_board_choice=opt.get('is_board_choice', False),
                        leads_to=f"branch_{i+1}" if i < len(decision_moments) - 1 else None
                    ))

            # Add default options if none exist
            if not options:
                options = [
                    ScenarioOption(
                        option_id=f"opt_{i}_0",
                        label="Follow obligation",
                        description="Prioritize professional duty",
                        leads_to=f"branch_{i+1}" if i < len(decision_moments) - 1 else None
                    ),
                    ScenarioOption(
                        option_id=f"opt_{i}_1",
                        label="Consider alternatives",
                        description="Explore other approaches",
                        leads_to=f"branch_{i+1}" if i < len(decision_moments) - 1 else None
                    )
                ]

            branches.append(ScenarioBranch(
                branch_id=f"branch_{i}",
                context=context,
                question=decision.question if hasattr(decision, 'question') else "",
                decision_point_uri=decision.uri if hasattr(decision, 'uri') else "",
                decision_maker_uri=decision.decision_maker_uri if hasattr(decision, 'decision_maker_uri') else "",
                decision_maker_label=decision.decision_maker_label if hasattr(decision, 'decision_maker_label') else "",
                involved_obligation_uris=decision.competing_obligations if hasattr(decision, 'competing_obligations') else [],
                options=options
            ))

        return branches

    def _extract_canonical_path(self, decision_moments: List) -> List[str]:
        """Extract canonical path (board's choices) from decision moments."""
        path = []

        for decision in decision_moments:
            if hasattr(decision, 'board_choice') and decision.board_choice:
                path.append(decision.board_choice)
            elif hasattr(decision, 'options'):
                # Find board choice option
                for opt in decision.options:
                    if opt.get('is_board_choice'):
                        path.append(opt.get('label', ''))
                        break

        return path

    def _generate_alternative_paths(
        self,
        branches: List[ScenarioBranch],
        canonical_path: List[str],
        transformation_type: str
    ) -> List[AlternativePath]:
        """Generate alternative paths based on transformation type."""
        alternatives = []

        if not branches:
            return alternatives

        # Generate based on transformation type
        if transformation_type == 'transfer':
            # Transfer: Single clear path exists
            alternatives.append(AlternativePath(
                path_id="alt_1",
                description="Alternative where engineer chooses differently",
                choice_sequence=["Alternative choice"],
                outcome_description="Different outcome pathway",
                ethical_assessment="Would have violated professional obligations"
            ))
        elif transformation_type == 'oscillation':
            # Oscillation: Multiple valid approaches
            alternatives.append(AlternativePath(
                path_id="alt_1",
                description="First alternative approach",
                choice_sequence=["Alternative A"],
                outcome_description="Emphasizes one set of obligations"
            ))
            alternatives.append(AlternativePath(
                path_id="alt_2",
                description="Second alternative approach",
                choice_sequence=["Alternative B"],
                outcome_description="Emphasizes competing obligations"
            ))
        elif transformation_type == 'stalemate':
            # Stalemate: No clear resolution
            alternatives.append(AlternativePath(
                path_id="alt_1",
                description="Path emphasizing public safety",
                choice_sequence=["Prioritize safety"],
                outcome_description="Potential career consequences"
            ))
            alternatives.append(AlternativePath(
                path_id="alt_2",
                description="Path emphasizing employer loyalty",
                choice_sequence=["Support employer"],
                outcome_description="Potential safety concerns"
            ))

        return alternatives

    def _enhance_opening_with_llm(
        self,
        opening_context: str,
        narrative_elements,
        case_id: int
    ) -> str:
        """Use LLM to enhance opening context."""
        if not self.llm_client:
            return opening_context

        protagonist = None
        if narrative_elements.characters:
            protagonist = narrative_elements.characters[0]

        prompt = f"""Rewrite this scenario opening to be more engaging while maintaining professional tone.

CURRENT OPENING:
{opening_context}

SETTING DETAILS:
{narrative_elements.setting.description if narrative_elements.setting else 'Professional context'}

Write a 2-3 sentence opening that:
1. Establishes the professional context
2. Hints at the ethical dilemma ahead
3. Uses second person ("You are...")
4. Maintains objective, professional tone

Output ONLY the enhanced opening text."""

        try:
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                temperature=0.4,
                messages=[{"role": "user", "content": prompt}]
            )

            enhanced = response.content[0].text.strip()
            logger.info(f"Enhanced scenario opening with LLM")
            return enhanced

        except Exception as e:
            logger.warning(f"LLM opening enhancement failed: {e}")
            return opening_context


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def generate_scenario_seeds(
    case_id: int,
    narrative_elements,
    timeline=None,
    transformation_type: str = None,
    use_llm: bool = True
) -> ScenarioSeeds:
    """
    Convenience function to generate scenario seeds.

    Args:
        case_id: Case ID
        narrative_elements: NarrativeElements from Stage 4.1
        timeline: EntityGroundedTimeline from Stage 4.2
        transformation_type: Case transformation classification
        use_llm: Whether to use LLM for enhancement

    Returns:
        ScenarioSeeds for Step 5 scenario generation
    """
    generator = ScenarioSeedGenerator(use_llm=use_llm)
    return generator.generate(
        case_id=case_id,
        narrative_elements=narrative_elements,
        timeline=timeline,
        transformation_type=transformation_type
    )
