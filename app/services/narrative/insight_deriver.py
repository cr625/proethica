"""
Insight Deriver (Stage 4.4)

Derives insights and generalizable patterns from case analysis.
Identifies ethical principles applied, novel aspects, and patterns
for precedent discovery.
"""

import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict

from app.utils.llm_utils import get_llm_client

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class EthicalPrincipleApplied:
    """An ethical principle applied in the case."""
    principle_uri: str
    principle_label: str
    how_applied: str
    provision_references: List[str] = field(default_factory=list)
    weight_in_resolution: str = ""  # 'primary', 'secondary', 'background'


@dataclass
class CasePattern:
    """A pattern identified in the case."""
    pattern_id: str
    pattern_type: str  # 'conflict_type', 'resolution_strategy', 'stakeholder_dynamics'
    description: str
    entity_uris: List[str] = field(default_factory=list)
    generalizability: str = ""  # 'high', 'medium', 'low'
    similar_cases_hint: str = ""  # For precedent discovery


@dataclass
class NovelAspect:
    """A novel aspect of the case."""
    aspect_id: str
    description: str
    why_novel: str
    implications: str = ""


@dataclass
class LimitationNote:
    """A limitation or gap in the board's reasoning."""
    limitation_id: str
    description: str
    affected_area: str  # 'reasoning', 'scope', 'applicability'


@dataclass
class CaseInsights:
    """Complete insights derived from a case."""
    case_id: int

    # Principles applied
    principles_applied: List[EthicalPrincipleApplied] = field(default_factory=list)

    # Patterns
    patterns: List[CasePattern] = field(default_factory=list)

    # Novel aspects
    novel_aspects: List[NovelAspect] = field(default_factory=list)

    # Limitations
    limitations: List[LimitationNote] = field(default_factory=list)

    # Summary insights
    key_takeaways: List[str] = field(default_factory=list)
    precedent_features: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'case_id': self.case_id,
            'principles_applied': [asdict(p) for p in self.principles_applied],
            'patterns': [asdict(p) for p in self.patterns],
            'novel_aspects': [asdict(n) for n in self.novel_aspects],
            'limitations': [asdict(l) for l in self.limitations],
            'key_takeaways': self.key_takeaways,
            'precedent_features': self.precedent_features
        }

    def summary(self) -> Dict:
        return {
            'principles_count': len(self.principles_applied),
            'patterns_count': len(self.patterns),
            'novel_aspects_count': len(self.novel_aspects),
            'key_takeaways_count': len(self.key_takeaways)
        }


# =============================================================================
# INSIGHT DERIVER SERVICE
# =============================================================================

class InsightDeriver:
    """
    Derives insights from case narrative elements.

    Identifies:
    - Ethical principles applied
    - Patterns for precedent matching
    - Novel aspects of the case
    - Limitations in reasoning
    """

    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        self.llm_client = get_llm_client() if use_llm else None

    def derive(
        self,
        case_id: int,
        narrative_elements,  # NarrativeElements from Stage 4.1
        timeline=None,  # EntityGroundedTimeline from Stage 4.2
        scenario_seeds=None,  # ScenarioSeeds from Stage 4.3
        transformation_type: str = None
    ) -> CaseInsights:
        """
        Derive insights from case analysis.

        Args:
            case_id: Case ID
            narrative_elements: NarrativeElements from Stage 4.1
            timeline: EntityGroundedTimeline from Stage 4.2
            scenario_seeds: ScenarioSeeds from Stage 4.3
            transformation_type: Case transformation classification

        Returns:
            CaseInsights with patterns and generalizable principles
        """
        # Extract principles applied
        principles = self._extract_principles(narrative_elements)

        # Identify patterns
        patterns = self._identify_patterns(
            narrative_elements, transformation_type
        )

        # Build precedent features
        precedent_features = self._build_precedent_features(
            narrative_elements, patterns, transformation_type
        )

        # Generate key takeaways (with LLM if enabled)
        key_takeaways = []
        if self.use_llm and self.llm_client:
            insights_result = self._generate_insights_with_llm(
                narrative_elements, principles, patterns, transformation_type
            )
            key_takeaways = insights_result.get('takeaways', [])
            novel_aspects = insights_result.get('novel_aspects', [])
            limitations = insights_result.get('limitations', [])
        else:
            key_takeaways = self._generate_basic_takeaways(
                narrative_elements, principles
            )
            novel_aspects = []
            limitations = []

        return CaseInsights(
            case_id=case_id,
            principles_applied=principles,
            patterns=patterns,
            novel_aspects=novel_aspects,
            limitations=limitations,
            key_takeaways=key_takeaways,
            precedent_features=precedent_features
        )

    def _extract_principles(self, narrative_elements) -> List[EthicalPrincipleApplied]:
        """Extract ethical principles from resolution and conflicts."""
        principles = []

        # From resolution
        if narrative_elements.resolution:
            for principle_label in narrative_elements.resolution.ethical_principles_applied:
                principles.append(EthicalPrincipleApplied(
                    principle_uri="",  # Would need to look up
                    principle_label=principle_label,
                    how_applied="Referenced in board resolution",
                    weight_in_resolution='primary'
                ))

        # Infer from conflicts
        for conflict in narrative_elements.conflicts[:3]:
            if conflict.resolution_rationale:
                principles.append(EthicalPrincipleApplied(
                    principle_uri="",
                    principle_label=f"Principle governing {conflict.entity1_label}",
                    how_applied=conflict.resolution_rationale,
                    weight_in_resolution='secondary'
                ))

        return principles

    def _identify_patterns(
        self,
        narrative_elements,
        transformation_type: str
    ) -> List[CasePattern]:
        """Identify patterns in the case."""
        patterns = []

        # Conflict type pattern
        if narrative_elements.conflicts:
            conflict_types = [c.conflict_type for c in narrative_elements.conflicts]
            primary_conflict = conflict_types[0] if conflict_types else 'unknown'

            patterns.append(CasePattern(
                pattern_id="conflict_pattern",
                pattern_type="conflict_type",
                description=f"Primary conflict: {primary_conflict}",
                entity_uris=[c.entity1_uri for c in narrative_elements.conflicts[:2]],
                generalizability='high',
                similar_cases_hint=f"Cases with {primary_conflict} conflicts"
            ))

        # Transformation pattern
        if transformation_type:
            patterns.append(CasePattern(
                pattern_id="transformation_pattern",
                pattern_type="resolution_strategy",
                description=f"Resolution follows {transformation_type} pattern",
                generalizability='high',
                similar_cases_hint=f"Cases resolved via {transformation_type}"
            ))

        # Decision maker pattern
        if narrative_elements.characters:
            protagonist = narrative_elements.characters[0]
            patterns.append(CasePattern(
                pattern_id="stakeholder_pattern",
                pattern_type="stakeholder_dynamics",
                description=f"Decision maker: {protagonist.role_type}",
                entity_uris=[protagonist.uri],
                generalizability='medium'
            ))

        return patterns

    def _build_precedent_features(
        self,
        narrative_elements,
        patterns: List[CasePattern],
        transformation_type: str
    ) -> Dict[str, Any]:
        """Build features for precedent discovery."""
        features = {
            'transformation_type': transformation_type or 'unknown',
            'conflict_types': [],
            'stakeholder_roles': [],
            'obligation_categories': [],
            'pattern_ids': [p.pattern_id for p in patterns]
        }

        # Extract conflict types
        for conflict in narrative_elements.conflicts:
            features['conflict_types'].append(conflict.conflict_type)

        # Extract stakeholder roles
        for char in narrative_elements.characters[:5]:
            if hasattr(char, 'role_type'):
                features['stakeholder_roles'].append(char.role_type)

        # Extract obligation categories (from characters' motivations)
        for char in narrative_elements.characters[:3]:
            if hasattr(char, 'motivations'):
                features['obligation_categories'].extend(char.motivations[:2])

        return features

    def _generate_basic_takeaways(
        self,
        narrative_elements,
        principles: List[EthicalPrincipleApplied]
    ) -> List[str]:
        """Generate basic takeaways without LLM."""
        takeaways = []

        # From principles
        for principle in principles[:2]:
            takeaways.append(
                f"Applied principle: {principle.principle_label}"
            )

        # From resolution
        if narrative_elements.resolution:
            takeaways.append(
                f"Resolution type: {narrative_elements.resolution.resolution_type}"
            )

        # From conflicts
        if narrative_elements.conflicts:
            primary_conflict = narrative_elements.conflicts[0]
            takeaways.append(
                f"Key tension: {primary_conflict.description}"
            )

        return takeaways

    def _generate_insights_with_llm(
        self,
        narrative_elements,
        principles: List[EthicalPrincipleApplied],
        patterns: List[CasePattern],
        transformation_type: str
    ) -> Dict:
        """Use LLM to generate detailed insights."""
        if not self.llm_client:
            return {'takeaways': [], 'novel_aspects': [], 'limitations': []}

        # Build context
        conflicts_desc = "\n".join([
            f"- {c.description}"
            for c in narrative_elements.conflicts[:3]
        ])

        resolution_desc = ""
        if narrative_elements.resolution:
            resolution_desc = narrative_elements.resolution.summary

        principles_desc = "\n".join([
            f"- {p.principle_label}: {p.how_applied}"
            for p in principles[:3]
        ])

        prompt = f"""Analyze this NSPE ethics case and derive insights.

CONFLICTS:
{conflicts_desc}

RESOLUTION:
{resolution_desc}

TRANSFORMATION TYPE: {transformation_type or 'unknown'}

PRINCIPLES IDENTIFIED:
{principles_desc}

Provide:
1. 3 key takeaways (1 sentence each)
2. 1-2 novel aspects of this case (if any)
3. 1-2 limitations in the board's reasoning (if any)

Output as JSON:
```json
{{
  "takeaways": ["...", "...", "..."],
  "novel_aspects": [{{"description": "...", "why_novel": "..."}}],
  "limitations": [{{"description": "...", "affected_area": "reasoning|scope|applicability"}}]
}}
```"""

        try:
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=600,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )

            import json
            import re

            response_text = response.content[0].text
            json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)

            if json_match:
                data = json.loads(json_match.group(1))

                novel_aspects = [
                    NovelAspect(
                        aspect_id=f"novel_{i}",
                        description=n.get('description', ''),
                        why_novel=n.get('why_novel', '')
                    )
                    for i, n in enumerate(data.get('novel_aspects', []))
                ]

                limitations = [
                    LimitationNote(
                        limitation_id=f"limit_{i}",
                        description=l.get('description', ''),
                        affected_area=l.get('affected_area', 'reasoning')
                    )
                    for i, l in enumerate(data.get('limitations', []))
                ]

                logger.info("Generated insights with LLM")
                return {
                    'takeaways': data.get('takeaways', []),
                    'novel_aspects': novel_aspects,
                    'limitations': limitations
                }

        except Exception as e:
            logger.warning(f"LLM insight generation failed: {e}")

        return {'takeaways': [], 'novel_aspects': [], 'limitations': []}


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def derive_insights(
    case_id: int,
    narrative_elements,
    timeline=None,
    scenario_seeds=None,
    transformation_type: str = None,
    use_llm: bool = True
) -> CaseInsights:
    """
    Convenience function to derive case insights.

    Args:
        case_id: Case ID
        narrative_elements: NarrativeElements from Stage 4.1
        timeline: EntityGroundedTimeline from Stage 4.2
        scenario_seeds: ScenarioSeeds from Stage 4.3
        transformation_type: Case transformation classification
        use_llm: Whether to use LLM for enhancement

    Returns:
        CaseInsights with patterns and generalizable principles
    """
    deriver = InsightDeriver(use_llm=use_llm)
    return deriver.derive(
        case_id=case_id,
        narrative_elements=narrative_elements,
        timeline=timeline,
        scenario_seeds=scenario_seeds,
        transformation_type=transformation_type
    )
