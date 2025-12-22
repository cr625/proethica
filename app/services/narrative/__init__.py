"""
Narrative Construction Services for ProEthica (Phase 4).

This module provides services for constructing entity-grounded narratives
from extracted entities and decision points.

Services:
    NarrativeElementExtractor (4.1): Extracts characters, settings, events, conflicts
    TimelineConstructor (4.2): Builds Event Calculus-based timelines
    ScenarioSeedGenerator (4.3): Generates seeds for interactive scenarios
    InsightDeriver (4.4): Derives patterns and generalizable insights

Based on: Berreby, Bourgne & Ganascia (2017) - Declarative Modular Framework

Usage:
    from app.services.narrative import (
        construct_phase4_narrative,
        extract_narrative_elements,
        construct_timeline,
        generate_scenario_seeds,
        derive_insights
    )

    # Run complete Phase 4 pipeline
    result = construct_phase4_narrative(case_id, foundation, canonical_points, conclusions)

    # Or run individual stages
    elements = extract_narrative_elements(case_id, foundation, canonical_points, conclusions)
    timeline = construct_timeline(case_id, elements)
    seeds = generate_scenario_seeds(case_id, elements, timeline)
    insights = derive_insights(case_id, elements, timeline, seeds)
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime

# Stage 4.1: Narrative Element Extraction
from app.services.narrative.narrative_element_extractor import (
    NarrativeElementExtractor,
    NarrativeElements,
    NarrativeCharacter,
    NarrativeSetting,
    NarrativeEvent,
    NarrativeConflict,
    EthicalTension,  # Alias for NarrativeConflict - normalized terminology
    DecisionMoment,
    NarrativeResolution,
    extract_narrative_elements
)

# Stage 4.2: Timeline Construction
from app.services.narrative.timeline_constructor import (
    TimelineConstructor,
    EntityGroundedTimeline,
    TimelineEvent,
    TimelinePhase,
    Fluent,
    CausalLink,
    construct_timeline
)

# Stage 4.3: Scenario Seed Generation
from app.services.narrative.scenario_seed_generator import (
    ScenarioSeedGenerator,
    ScenarioSeeds,
    ScenarioBranch,
    ScenarioOption,
    AlternativePath,
    generate_scenario_seeds
)

# Stage 4.4: Insight Derivation
from app.services.narrative.insight_deriver import (
    InsightDeriver,
    CaseInsights,
    EthicalPrincipleApplied,
    CasePattern,
    NovelAspect,
    LimitationNote,
    derive_insights
)


# =============================================================================
# COMPLETE PHASE 4 RESULT
# =============================================================================

@dataclass
class Phase4NarrativeResult:
    """Complete Phase 4 narrative construction result."""
    case_id: int

    # Stage outputs
    narrative_elements: NarrativeElements
    timeline: EntityGroundedTimeline
    scenario_seeds: ScenarioSeeds
    insights: CaseInsights

    # Metadata
    construction_timestamp: datetime = field(default_factory=datetime.now)
    stages_completed: List[str] = field(default_factory=list)
    llm_enhanced: bool = True

    def to_dict(self) -> Dict:
        return {
            'case_id': self.case_id,
            'narrative_elements': self.narrative_elements.to_dict(),
            'timeline': self.timeline.to_dict(),
            'scenario_seeds': self.scenario_seeds.to_dict(),
            'insights': self.insights.to_dict(),
            'construction_timestamp': self.construction_timestamp.isoformat(),
            'stages_completed': self.stages_completed,
            'llm_enhanced': self.llm_enhanced
        }

    def summary(self) -> Dict:
        return {
            'narrative_elements': self.narrative_elements.summary(),
            'timeline': self.timeline.summary(),
            'scenario_seeds': self.scenario_seeds.summary(),
            'insights': self.insights.summary(),
            'stages_completed': len(self.stages_completed)
        }


# =============================================================================
# UNIFIED PHASE 4 PIPELINE
# =============================================================================

def construct_phase4_narrative(
    case_id: int,
    foundation,  # EntityFoundation from case_synthesizer
    canonical_points: List = None,
    conclusions: List[Dict] = None,
    transformation_type: str = None,
    causal_normative_links: List[Dict] = None,
    use_llm: bool = True
) -> Phase4NarrativeResult:
    """
    Execute complete Phase 4 narrative construction pipeline.

    This function runs all four stages in sequence:
    1. Stage 4.1: Extract narrative elements (characters, settings, events, conflicts)
    2. Stage 4.2: Construct entity-grounded timeline with Event Calculus
    3. Stage 4.3: Generate scenario seeds for Step 5
    4. Stage 4.4: Derive insights and patterns for precedent discovery

    Args:
        case_id: Case ID
        foundation: EntityFoundation with all Pass 1-3 entities
        canonical_points: Decision points from Phase 3
        conclusions: Board conclusions
        transformation_type: Case transformation classification
        causal_normative_links: Causal links from Phase 2B
        use_llm: Whether to use LLM for enhancement

    Returns:
        Phase4NarrativeResult with all stage outputs
    """
    canonical_points = canonical_points or []
    conclusions = conclusions or []
    causal_normative_links = causal_normative_links or []
    stages_completed = []

    # Stage 4.1: Narrative Element Extraction
    narrative_elements = extract_narrative_elements(
        case_id=case_id,
        foundation=foundation,
        canonical_points=canonical_points,
        conclusions=conclusions,
        transformation_type=transformation_type,
        use_llm=use_llm
    )
    stages_completed.append('4.1_narrative_elements')

    # Stage 4.2: Timeline Construction
    timeline = construct_timeline(
        case_id=case_id,
        narrative_elements=narrative_elements,
        foundation=foundation,
        causal_normative_links=causal_normative_links,
        use_llm=use_llm
    )
    stages_completed.append('4.2_timeline')

    # Stage 4.3: Scenario Seed Generation
    scenario_seeds = generate_scenario_seeds(
        case_id=case_id,
        narrative_elements=narrative_elements,
        timeline=timeline,
        transformation_type=transformation_type,
        use_llm=use_llm
    )
    stages_completed.append('4.3_scenario_seeds')

    # Stage 4.4: Insight Derivation
    insights = derive_insights(
        case_id=case_id,
        narrative_elements=narrative_elements,
        timeline=timeline,
        scenario_seeds=scenario_seeds,
        transformation_type=transformation_type,
        use_llm=use_llm
    )
    stages_completed.append('4.4_insights')

    return Phase4NarrativeResult(
        case_id=case_id,
        narrative_elements=narrative_elements,
        timeline=timeline,
        scenario_seeds=scenario_seeds,
        insights=insights,
        stages_completed=stages_completed,
        llm_enhanced=use_llm
    )


__all__ = [
    # Complete pipeline
    'construct_phase4_narrative',
    'Phase4NarrativeResult',

    # Stage 4.1: Narrative Elements
    'NarrativeElementExtractor',
    'NarrativeElements',
    'NarrativeCharacter',
    'NarrativeSetting',
    'NarrativeEvent',
    'NarrativeConflict',
    'EthicalTension',  # Alias for NarrativeConflict
    'DecisionMoment',
    'NarrativeResolution',
    'extract_narrative_elements',

    # Stage 4.2: Timeline
    'TimelineConstructor',
    'EntityGroundedTimeline',
    'TimelineEvent',
    'TimelinePhase',
    'Fluent',
    'CausalLink',
    'construct_timeline',

    # Stage 4.3: Scenario Seeds
    'ScenarioSeedGenerator',
    'ScenarioSeeds',
    'ScenarioBranch',
    'ScenarioOption',
    'AlternativePath',
    'generate_scenario_seeds',

    # Stage 4.4: Insights
    'InsightDeriver',
    'CaseInsights',
    'EthicalPrincipleApplied',
    'CasePattern',
    'NovelAspect',
    'LimitationNote',
    'derive_insights',
]
