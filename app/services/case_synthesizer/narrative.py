"""
Case Synthesizer (Step 4) -- narrative construction.

The Phase-4 narrative methods, split out of case_synthesizer.py as a mixin so the
orchestrating class stays focused. Mixed into CaseSynthesizer; `self.` resolution is
preserved by MRO. Import header mirrors synthesizer.py so relocated bodies resolve.
"""

import json
import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime

from sqlalchemy import text
from app import db
from app.models import Document, TemporaryRDFStorage, ExtractionPrompt
from app.utils.llm_utils import get_llm_client
from app.domains import DomainConfig, get_domain_config
from model_config import ModelConfig

# Data models (extracted to separate module for modularity)
from app.services.step4_synthesis.case_synthesis_models import (  # noqa: F401 -- re-exported for backward compatibility
    EntitySummary, EntityFoundation, TimelineEvent, ScenarioSeeds,
    CaseNarrative, LLMTrace, CausalNormativeLink, QuestionEmergenceAnalysis,
    ResolutionPatternAnalysis, TransformationAnalysis, CaseSynthesisModel,
    SynthesisResult
)

# E1-E3 Services
from app.services.entity_analysis import (
    ObligationCoverageAnalyzer,
    ActionOptionMapper,
    DecisionPointComposer,
    get_obligation_coverage,
    get_action_option_map,
    compose_decision_points,
    ComposedDecisionPoints,
    EntityGroundedDecisionPoint
)

# F1-F3 Services
from app.services.entity_analysis import (
    PrincipleProvisionAligner,
    ArgumentGenerator,
    ArgumentValidator,
    get_principle_provision_alignment,
    generate_arguments,
    validate_arguments,
    GeneratedArguments,
    ValidatedArguments
)

# Phase 4 Narrative Pipeline
from app.services.narrative import construct_phase4_narrative

# Phase 3: Decision Point Synthesis
from app.services.decision_point_synthesizer import (
    DecisionPointSynthesizer,
    CanonicalDecisionPoint,
    Phase3SynthesisResult,
    synthesize_decision_points
)
from app.utils.llm_utils import text_from_message

logger = logging.getLogger(__name__)


class NarrativeConstructionMixin:
    """Phase-4 narrative construction. Mixed into CaseSynthesizer."""

    def _construct_narrative(
        self,
        case_id: int,
        foundation: EntityFoundation,
        canonical_points: List[CanonicalDecisionPoint],
        conclusions: List[Dict]
    ) -> CaseNarrative:
        """
        Construct narrative elements for case explanation and scenario.
        """
        # Build timeline from entities
        timeline = []
        sequence = 1

        # Phase 1: Initial states
        if foundation.states:
            timeline.append(TimelineEvent(
                sequence=sequence,
                phase_label="Initial Context",
                description=f"Case begins with {len(foundation.states)} contextual states",
                entity_uris=[s.uri for s in foundation.states[:3]],
                entity_labels=[s.label for s in foundation.states[:3]],
                event_type='state'
            ))
            sequence += 1

        # Phase 2: Actions taken
        if foundation.actions:
            timeline.append(TimelineEvent(
                sequence=sequence,
                phase_label="Actions",
                description=f"{len(foundation.actions)} key actions by participants",
                entity_uris=[a.uri for a in foundation.actions],
                entity_labels=[a.label for a in foundation.actions],
                event_type='action'
            ))
            sequence += 1

        # Phase 3: Events that occurred
        if foundation.events:
            timeline.append(TimelineEvent(
                sequence=sequence,
                phase_label="Events",
                description=f"{len(foundation.events)} significant events",
                entity_uris=[e.uri for e in foundation.events],
                entity_labels=[e.label for e in foundation.events],
                event_type='event'
            ))
            sequence += 1

        # Phase 4: Decision points
        for dp in canonical_points:
            timeline.append(TimelineEvent(
                sequence=sequence,
                phase_label=f"Decision: {dp.focus_id}",
                description=dp.description,
                entity_uris=[dp.role_uri] + (dp.involved_action_uris or []),
                entity_labels=[dp.role_label],
                event_type='decision'
            ))
            sequence += 1

        # Phase 5: Resolution
        if conclusions:
            timeline.append(TimelineEvent(
                sequence=sequence,
                phase_label="Board Resolution",
                description=conclusions[0].get('text', conclusions[0].get('label', 'Board determination'))[:200],
                entity_uris=[c.get('uri', '') for c in conclusions],
                entity_labels=[c.get('label', '') for c in conclusions],
                event_type='outcome'
            ))

        # Build scenario seeds
        protagonist = foundation.roles[0] if foundation.roles else None
        scenario_seeds = None
        if protagonist and canonical_points:
            key_tensions = []
            for dp in canonical_points:
                if dp.obligation_label and dp.constraint_label:
                    key_tensions.append(f"{dp.obligation_label} vs {dp.constraint_label}")
                elif dp.obligation_label:
                    key_tensions.append(dp.obligation_label)

            scenario_seeds = ScenarioSeeds(
                protagonist=protagonist.label,
                protagonist_uri=protagonist.uri,
                setting=f"Professional engineering context with {len(foundation.roles)} key participants",
                inciting_incident=canonical_points[0].decision_question if canonical_points else "Ethical dilemma emerges",
                key_tensions=key_tensions[:3],
                resolution_path=conclusions[0].get('text', '')[:200] if conclusions else ""
            )

        # Generate case summary
        case_summary = self._generate_case_summary(foundation, canonical_points, conclusions)

        return CaseNarrative(
            case_summary=case_summary,
            timeline=timeline,
            scenario_seeds=scenario_seeds
        )

    def _generate_case_summary(
        self,
        foundation: EntityFoundation,
        canonical_points: List[CanonicalDecisionPoint],
        conclusions: List[Dict]
    ) -> str:
        """Generate a 2-3 sentence case summary."""
        # Build summary from entities
        protagonist = foundation.roles[0].label if foundation.roles else "An engineer"
        num_decisions = len(canonical_points)
        key_question = canonical_points[0].decision_question if canonical_points else "a professional ethics question"
        resolution = conclusions[0].get('label', 'The Board provided guidance') if conclusions else "The Board deliberated"

        return (
            f"{protagonist} faced {num_decisions} key decision point{'s' if num_decisions != 1 else ''} "
            f"involving {key_question[:100]}{'...' if len(key_question) > 100 else ''} "
            f"{resolution[:100]}{'...' if len(resolution) > 100 else ''}"
        )

    def _construct_narrative_with_llm(
        self,
        case_id: int,
        case: Document,
        foundation: EntityFoundation,
        canonical_points: List[CanonicalDecisionPoint],
        conclusions: List[Dict]
    ) -> Tuple[CaseNarrative, List[LLMTrace]]:
        """
        Construct narrative elements using LLM for richer descriptions.

        Uses LLM to:
        1. Generate a compelling 2-3 sentence case summary
        2. Create timeline event descriptions that tell a coherent story
        3. Build scenario seeds with meaningful tensions

        Returns:
            Tuple of (CaseNarrative, list of LLMTraces)
        """
        llm_traces = []

        # Build base narrative first (non-LLM)
        base_narrative = self._construct_narrative(case_id, foundation, canonical_points, conclusions)

        # Get case context
        case_title = case.title if case else f"Case {case_id}"
        facts_text = ""
        if case.doc_metadata:
            sections_dual = case.doc_metadata.get('sections_dual', {})
            if 'facts' in sections_dual:
                facts_data = sections_dual['facts']
                facts_text = facts_data.get('text', '')[:1500] if isinstance(facts_data, dict) else str(facts_data)[:1500]

        # =================================================================
        # LLM-Enhanced Case Summary
        # =================================================================
        summary_prompt = f"""Generate a concise 2-3 sentence summary of this NSPE ethics case.

## Case: {case_title}

## Facts (excerpt):
{facts_text}

## Key Participants:
{', '.join([r.label for r in foundation.roles[:5]])}

## Obligations at stake:
{', '.join([o.label for o in foundation.obligations[:5]])}

## Decision Points:
{chr(10).join([f"- {dp.decision_question}" for dp in canonical_points[:3]])}

## Board Conclusions:
{chr(10).join([f"- {c.get('text', c.get('label', ''))[:100]}" for c in conclusions[:2]])}

Write a professional, objective summary that:
1. Identifies the key ethical tension
2. Names the primary decision-maker role (without using "Engineer A" - describe their role)
3. Hints at the resolution

Output ONLY the 2-3 sentence summary, no additional text."""

        try:
            from app.utils.llm_utils import direct_call_params
            response = self.llm_client.messages.create(
                **direct_call_params(ModelConfig.get_claude_model("default"),
                                     max_tokens=300, temperature=0.3),
                messages=[{"role": "user", "content": summary_prompt}]
            )

            enhanced_summary = text_from_message(response).strip()

            llm_traces.append(LLMTrace(
                phase=4,
                phase_name="Narrative Construction",
                stage="Case Summary",
                prompt=summary_prompt,
                response=enhanced_summary,
                model=ModelConfig.get_claude_model("default")
            ))

            logger.info(f"Phase 4: Generated LLM-enhanced case summary")
        except Exception as e:
            logger.warning(f"LLM summary generation failed: {e}")
            enhanced_summary = base_narrative.case_summary

        # =================================================================
        # LLM-Enhanced Timeline
        # =================================================================
        timeline_prompt = f"""Create a timeline of key events for this ethics case. For each phase, write a 1-2 sentence description.

## Case: {case_title}

## Extracted Entities:
- Roles: {', '.join([r.label for r in foundation.roles[:5]])}
- States: {', '.join([s.label for s in foundation.states[:5]])}
- Actions: {', '.join([a.label for a in foundation.actions[:5]])}
- Events: {', '.join([e.label for e in foundation.events[:5]])}

## Decision Points:
{chr(10).join([f"{i+1}. {dp.decision_question}" for i, dp in enumerate(canonical_points[:4])])}

## Conclusions:
{chr(10).join([f"- {c.get('text', c.get('label', ''))[:150]}" for c in conclusions[:2]])}

Generate 4-6 timeline phases. For each, output:
1. Phase label (e.g., "Initial Situation", "Conflict Emerges", "Decision Point", "Resolution")
2. Description (1-2 sentences, objective professional tone)
3. Event type: state/action/event/decision/outcome

Output as JSON array:
```json
[
  {{"phase_label": "...", "description": "...", "event_type": "state"}},
  ...
]
```"""

        try:
            from app.utils.llm_utils import direct_call_params
            response = self.llm_client.messages.create(
                **direct_call_params(ModelConfig.get_claude_model("default"),
                                     max_tokens=800, temperature=0.3),
                messages=[{"role": "user", "content": timeline_prompt}]
            )

            response_text = text_from_message(response)

            llm_traces.append(LLMTrace(
                phase=4,
                phase_name="Narrative Construction",
                stage="Timeline Construction",
                prompt=timeline_prompt,
                response=response_text,
                model=ModelConfig.get_claude_model("default")
            ))

            # Parse timeline JSON
            import re
            json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
            if json_match:
                timeline_data = json.loads(json_match.group(1))

                enhanced_timeline = []
                for i, item in enumerate(timeline_data, 1):
                    enhanced_timeline.append(TimelineEvent(
                        sequence=i,
                        phase_label=item.get('phase_label', f'Phase {i}'),
                        description=item.get('description', ''),
                        entity_uris=[],  # LLM doesn't provide URIs
                        entity_labels=[],
                        event_type=item.get('event_type', 'event')
                    ))

                logger.info(f"Phase 4: Generated {len(enhanced_timeline)} LLM-enhanced timeline events")
            else:
                enhanced_timeline = base_narrative.timeline
        except Exception as e:
            logger.warning(f"LLM timeline generation failed: {e}")
            enhanced_timeline = base_narrative.timeline

        # =================================================================
        # Enhanced Scenario Seeds
        # =================================================================
        scenario_seeds = base_narrative.scenario_seeds

        if foundation.roles and canonical_points:
            # Use first canonical point's question as inciting incident
            scenario_seeds = ScenarioSeeds(
                protagonist=foundation.roles[0].label,
                protagonist_uri=foundation.roles[0].uri,
                setting=f"Professional engineering context involving {case_title}",
                inciting_incident=canonical_points[0].decision_question if canonical_points else "An ethical dilemma emerges",
                key_tensions=[
                    f"{dp.obligation_label} vs {dp.constraint_label}"
                    for dp in canonical_points
                    if dp.obligation_label and dp.constraint_label
                ][:3],
                resolution_path=conclusions[0].get('text', '')[:200] if conclusions else ""
            )

        return CaseNarrative(
            case_summary=enhanced_summary,
            timeline=enhanced_timeline,
            scenario_seeds=scenario_seeds
        ), llm_traces
