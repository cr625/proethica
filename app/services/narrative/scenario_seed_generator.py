"""
Scenario Seed Generator (Stage 4.3)

Generates scenario seeds for interactive Step 5 scenario generation.
Links decision points to branch structures for turn-by-turn exploration.

Uses transformation classification to guide branch structure generation.
"""

import logging
from typing import List, Dict, Optional, Any, Tuple
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

    # LLM interaction traces for display
    llm_traces: List[Dict] = field(default_factory=list)

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

        # Collect LLM traces
        llm_traces = []

        # Enhance with LLM if enabled
        if self.use_llm and self.llm_client:
            opening_context, opening_trace = self._enhance_opening_with_llm(
                opening_context, narrative_elements, case_id
            )
            if opening_trace:
                llm_traces.append(opening_trace)

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
            transformation_type=transformation_type or "",
            llm_traces=llm_traces
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
            question = decision.question if hasattr(decision, 'question') else ""
            competing_obls = decision.competing_obligations if hasattr(decision, 'competing_obligations') else []

            # Build options
            options = []
            if hasattr(decision, 'options') and decision.options:
                for j, opt in enumerate(decision.options):
                    # Get label, using empty string check (not just None)
                    label = opt.get('label') or ''
                    description = opt.get('description') or ''

                    # If label is empty, generate a meaningful one
                    if not label.strip():
                        label, description = self._generate_option_label(
                            question=question,
                            option_index=j,
                            is_board_choice=opt.get('is_board_choice', False),
                            competing_obligations=competing_obls
                        )

                    options.append(ScenarioOption(
                        option_id=f"opt_{i}_{j}",
                        label=label,
                        description=description,
                        action_uris=opt.get('action_uris', []),
                        is_board_choice=opt.get('is_board_choice', False),
                        leads_to=f"branch_{i+1}" if i < len(decision_moments) - 1 else None
                    ))

            # Add default options if none exist
            if not options:
                # Generate options based on the question and obligations
                options = self._generate_default_options(
                    question=question,
                    competing_obligations=competing_obls,
                    branch_index=i,
                    total_branches=len(decision_moments)
                )

            branches.append(ScenarioBranch(
                branch_id=f"branch_{i}",
                context=context,
                question=question,
                decision_point_uri=decision.uri if hasattr(decision, 'uri') else "",
                decision_maker_uri=decision.decision_maker_uri if hasattr(decision, 'decision_maker_uri') else "",
                decision_maker_label=decision.decision_maker_label if hasattr(decision, 'decision_maker_label') else "",
                involved_obligation_uris=competing_obls,
                options=options
            ))

        return branches

    def _generate_option_label(
        self,
        question: str,
        option_index: int,
        is_board_choice: bool,
        competing_obligations: List[str]
    ) -> tuple:
        """Generate a meaningful option label based on context."""
        # If LLM available, use it for richer labels
        if self.use_llm and self.llm_client:
            return self._generate_option_label_llm(
                question, option_index, is_board_choice, competing_obligations
            )

        # Fallback: Generate based on pattern
        if option_index == 0:
            if is_board_choice:
                label = "Fulfill the professional obligation"
                desc = "Follow the established ethical duty as the board would recommend"
            else:
                label = "Prioritize professional obligation"
                desc = "Focus on meeting the primary ethical duty"
        else:
            if is_board_choice:
                label = "Consider alternative approach"
                desc = "The board determined this was the appropriate path"
            else:
                label = "Explore alternative approach"
                desc = "Consider other factors that may apply"

        # Enhance with obligation context if available
        if competing_obligations:
            obl = competing_obligations[min(option_index, len(competing_obligations) - 1)]
            if obl:
                label = f"Address {obl[:50]}..." if len(obl) > 50 else f"Address {obl}"

        return label, desc

    def _generate_option_label_llm(
        self,
        question: str,
        option_index: int,
        is_board_choice: bool,
        competing_obligations: List[str]
    ) -> tuple:
        """Use LLM to generate meaningful option labels."""
        obligations_text = ", ".join([o for o in competing_obligations if o][:3])

        prompt = f"""Generate a concise option label for an ethical decision scenario.

DECISION QUESTION: {question}

RELEVANT OBLIGATIONS: {obligations_text or 'Professional engineering ethics'}

OPTION NUMBER: {option_index + 1} of 2
IS BOARD'S RECOMMENDED CHOICE: {is_board_choice}

Generate:
1. A short action-oriented label (5-10 words)
2. A brief description (1 sentence)

The label should describe what the person would DO, not just "Option 1".
For example: "Report concerns to regulatory authority" or "Maintain confidentiality with employer"

Output format (exactly two lines):
LABEL: [your label]
DESCRIPTION: [your description]"""

        try:
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=100,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )

            text = response.content[0].text.strip()
            lines = text.split('\n')

            label = "Choose this option"
            desc = ""

            for line in lines:
                if line.startswith('LABEL:'):
                    label = line.replace('LABEL:', '').strip()
                elif line.startswith('DESCRIPTION:'):
                    desc = line.replace('DESCRIPTION:', '').strip()

            logger.debug(f"Generated option label: {label}")
            return label, desc

        except Exception as e:
            logger.warning(f"LLM option label generation failed: {e}")
            # Fallback to simple labels
            if is_board_choice:
                return "Follow board recommendation", "The ethically recommended approach"
            else:
                return "Consider alternative", "An alternative course of action"

    def _generate_default_options(
        self,
        question: str,
        competing_obligations: List[str],
        branch_index: int,
        total_branches: int
    ) -> List[ScenarioOption]:
        """Generate default options when none exist."""
        leads_to = f"branch_{branch_index+1}" if branch_index < total_branches - 1 else None

        # Try LLM generation
        if self.use_llm and self.llm_client:
            options = self._generate_options_llm(question, competing_obligations, branch_index, leads_to)
            if options:
                return options

        # Fallback defaults based on common ethical patterns
        return [
            ScenarioOption(
                option_id=f"opt_{branch_index}_0",
                label="Fulfill the primary obligation",
                description="Prioritize the main professional duty at stake",
                is_board_choice=True,
                leads_to=leads_to
            ),
            ScenarioOption(
                option_id=f"opt_{branch_index}_1",
                label="Seek alternative resolution",
                description="Look for ways to balance competing concerns",
                is_board_choice=False,
                leads_to=leads_to
            )
        ]

    def _generate_options_llm(
        self,
        question: str,
        competing_obligations: List[str],
        branch_index: int,
        leads_to: str
    ) -> List[ScenarioOption]:
        """Use LLM to generate complete option set."""
        obligations_text = ", ".join([o for o in competing_obligations if o][:3])

        prompt = f"""Generate two ethical decision options for this scenario.

DECISION QUESTION: {question}

RELEVANT OBLIGATIONS: {obligations_text or 'Professional engineering ethics'}

Generate exactly 2 options that represent meaningful choices.
Option 1 should typically align with professional duty (mark as board choice).
Option 2 should represent an alternative approach.

Output format:
OPTION1_LABEL: [action-oriented label, 5-10 words]
OPTION1_DESC: [1 sentence description]
OPTION2_LABEL: [action-oriented label, 5-10 words]
OPTION2_DESC: [1 sentence description]"""

        try:
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )

            text = response.content[0].text.strip()
            lines = text.split('\n')

            opt1_label = opt1_desc = opt2_label = opt2_desc = ""

            for line in lines:
                if line.startswith('OPTION1_LABEL:'):
                    opt1_label = line.replace('OPTION1_LABEL:', '').strip()
                elif line.startswith('OPTION1_DESC:'):
                    opt1_desc = line.replace('OPTION1_DESC:', '').strip()
                elif line.startswith('OPTION2_LABEL:'):
                    opt2_label = line.replace('OPTION2_LABEL:', '').strip()
                elif line.startswith('OPTION2_DESC:'):
                    opt2_desc = line.replace('OPTION2_DESC:', '').strip()

            if opt1_label and opt2_label:
                logger.info(f"Generated options via LLM: {opt1_label} / {opt2_label}")
                return [
                    ScenarioOption(
                        option_id=f"opt_{branch_index}_0",
                        label=opt1_label,
                        description=opt1_desc,
                        is_board_choice=True,
                        leads_to=leads_to
                    ),
                    ScenarioOption(
                        option_id=f"opt_{branch_index}_1",
                        label=opt2_label,
                        description=opt2_desc,
                        is_board_choice=False,
                        leads_to=leads_to
                    )
                ]

        except Exception as e:
            logger.warning(f"LLM options generation failed: {e}")

        return None  # Signal to use fallback

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
    ) -> Tuple[str, Optional[Dict]]:
        """Use LLM to enhance opening context. Returns (opening_context, llm_trace)."""
        if not self.llm_client:
            return opening_context, None

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

        llm_trace = None
        try:
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                temperature=0.4,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text.strip()

            # Capture LLM trace
            llm_trace = {
                'stage': 'SCENARIO_OPENING_ENHANCEMENT',
                'description': 'Enhance scenario opening context for engagement',
                'prompt': prompt,
                'response': response_text,
                'model': 'claude-sonnet-4-20250514'
            }

            logger.info(f"Enhanced scenario opening with LLM")
            return response_text, llm_trace

        except Exception as e:
            logger.warning(f"LLM opening enhancement failed: {e}")
            return opening_context, llm_trace


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
