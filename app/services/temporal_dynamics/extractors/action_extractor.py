"""
Action Extractor for Enhanced Temporal Dynamics Pass

Two-phase extraction for reliability:
- Phase 1: Core action data (intentions, ethics, priorities, professional context)
- Phase 2: Scenario metadata enrichment (motivations, tensions, stakes, alternatives)

This split reduces timeout risk by making each LLM call smaller and faster.
"""

from typing import Dict, List, Optional
import logging
import os

from models import ModelConfig
from datetime import datetime

logger = logging.getLogger(__name__)


def extract_actions_with_metadata(
    narrative: Dict,
    temporal_markers: Dict,
    case_id: int,
    llm_trace: List[Dict],
    facts_text: str = '',
    discussion_text: str = ''
) -> List[Dict]:
    """
    Extract actions (volitional professional decisions) with rich metadata.

    Uses two-phase extraction:
    1. Phase 1: Core action data (faster, critical)
    2. Phase 2: Scenario metadata enrichment (optional enhancement)

    Args:
        narrative: Unified narrative from Stage 1
        temporal_markers: Temporal markers from Stage 2
        case_id: Case ID for logging
        llm_trace: List to append LLM interactions to
        facts_text: Raw facts section text (grounding context)
        discussion_text: Raw discussion section text (grounding context)

    Returns:
        List of action dictionaries with full metadata
    """
    logger.info(f"[Stage 3] Extracting actions for case {case_id}")

    # Initialize Anthropic client
    try:
        import anthropic
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not found in environment")
        llm_client = anthropic.Anthropic(api_key=api_key, timeout=180.0, max_retries=2)
        model_name = ModelConfig.get_claude_model('default')
        logger.info(f"[Stage 3] Initialized Anthropic client with model {model_name}")
    except Exception as e:
        logger.error(f"[Stage 3] Failed to initialize LLM client: {e}")
        raise RuntimeError(f"No LLM client available: {e}")

    # Phase 1: Extract core actions
    actions = _extract_core_actions(
        narrative, temporal_markers, case_id, llm_client, model_name, llm_trace,
        facts_text=facts_text, discussion_text=discussion_text
    )

    if not actions:
        logger.warning(f"[Stage 3] Phase 1 returned 0 actions, skipping Phase 2")
        return []

    logger.info(f"[Stage 3] Phase 1 complete: {len(actions)} core actions")

    # Phase 2: Enrich with scenario metadata
    enriched_actions = _enrich_with_scenario_metadata(
        actions, narrative, case_id, llm_client, model_name, llm_trace
    )

    logger.info(f"[Stage 3] Phase 2 complete: {len(enriched_actions)} enriched actions")

    return enriched_actions


def _call_llm_with_streaming(
    llm_client,
    model_name: str,
    prompt: str,
    phase: str,
    case_id: int
) -> Optional[str]:
    """
    Call LLM with streaming to prevent WSL2 TCP idle timeout (60s).

    Streaming keeps the connection alive with continuous data flow,
    preventing the network layer from killing idle connections.

    Returns (response_text, response_message) tuple.
    """
    logger.info(f"[Stage 3] {phase} - LLM streaming call")

    with llm_client.messages.stream(
        model=model_name,
        max_tokens=8000,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        response = stream.get_final_message()

    return response.content[0].text, response


def _extract_core_actions(
    narrative: Dict,
    temporal_markers: Dict,
    case_id: int,
    llm_client,
    model_name: str,
    llm_trace: List[Dict],
    facts_text: str = '',
    discussion_text: str = ''
) -> List[Dict]:
    """
    Phase 1: Extract core action data (no scenario metadata).

    Includes raw case text for grounding when narrative summary is available,
    and as primary source when narrative summary is missing or degraded.
    """
    prompt = _build_phase1_prompt(narrative, temporal_markers, facts_text, discussion_text)
    logger.info(f"[Stage 3] Phase 1 prompt length: {len(prompt)} chars")

    trace_entry = {
        'stage': 'action_extraction',
        'phase': 'phase1_core',
        'timestamp': datetime.utcnow().isoformat(),
        'prompt': prompt,
        'model': model_name,
    }

    try:
        response_text, response = _call_llm_with_streaming(
            llm_client, model_name, prompt, "Phase 1", case_id
        )

        trace_entry['response'] = response_text

        # Parse response
        actions = _parse_action_response(response_text)
        trace_entry['parsed_output'] = {'action_count': len(actions)}

        # Token usage
        if hasattr(response, 'usage'):
            trace_entry['tokens'] = {
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens,
                'total_tokens': response.usage.input_tokens + response.usage.output_tokens
            }

        if len(actions) == 0:
            logger.warning(f"[Stage 3] Phase 1: 0 actions extracted for case {case_id}")
            logger.warning(f"[Stage 3] Response preview: {response_text[:500]}...")
            trace_entry['warning'] = 'Zero actions extracted'

        return actions

    except Exception as e:
        logger.error(f"[Stage 3] Phase 1 error: {e}")
        trace_entry['error'] = str(e)
        return []

    finally:
        trace_entry['end_timestamp'] = datetime.utcnow().isoformat()
        llm_trace.append(trace_entry)


def _enrich_with_scenario_metadata(
    actions: List[Dict],
    narrative: Dict,
    case_id: int,
    llm_client,
    model_name: str,
    llm_trace: List[Dict]
) -> List[Dict]:
    """
    Phase 2: Enrich actions with scenario metadata.

    This is optional enhancement - if it fails, we still have core actions.
    """
    prompt = _build_phase2_prompt(actions, narrative)

    trace_entry = {
        'stage': 'action_extraction',
        'phase': 'phase2_scenario',
        'timestamp': datetime.utcnow().isoformat(),
        'prompt': prompt,
        'model': model_name,
    }

    try:
        response_text, response = _call_llm_with_streaming(
            llm_client, model_name, prompt, "Phase 2", case_id
        )

        trace_entry['response'] = response_text

        # Parse enrichment
        enrichments = _parse_enrichment_response(response_text)
        trace_entry['parsed_output'] = {'enrichment_count': len(enrichments)}

        # Token usage
        if hasattr(response, 'usage'):
            trace_entry['tokens'] = {
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens,
                'total_tokens': response.usage.input_tokens + response.usage.output_tokens
            }

        # Merge enrichments into actions
        enriched = _merge_enrichments(actions, enrichments)
        logger.info(f"[Stage 3] Phase 2: Enriched {len(enriched)} actions with scenario metadata")

        return enriched

    except Exception as e:
        logger.warning(f"[Stage 3] Phase 2 failed: {e} - returning core actions without enrichment")
        trace_entry['error'] = str(e)
        trace_entry['warning'] = 'Enrichment failed - using core actions only'

        # Add empty scenario_metadata to each action
        for action in actions:
            if 'scenario_metadata' not in action:
                action['scenario_metadata'] = {}

        return actions

    finally:
        trace_entry['end_timestamp'] = datetime.utcnow().isoformat()
        llm_trace.append(trace_entry)


def _build_phase1_prompt(narrative: Dict, temporal_markers: Dict,
                         facts_text: str = '', discussion_text: str = '') -> str:
    """Build Phase 1 prompt - core action extraction with source text grounding."""

    temporal_context = ""
    if temporal_markers.get('absolute'):
        temporal_context += f"\nAbsolute markers: {len(temporal_markers['absolute'])}"
    if temporal_markers.get('relative'):
        temporal_context += f"\nRelative markers: {len(temporal_markers['relative'])}"

    # Include raw case text for grounding
    source_text_section = ""
    if facts_text or discussion_text:
        source_text_section = f"""
CASE FACTS:
{facts_text}

CASE DISCUSSION:
{discussion_text}
"""

    # Narrative summary (may be empty/degraded if Stage 1 failed)
    narrative_summary = narrative.get('unified_timeline_summary', '')
    decision_points = narrative.get('decision_points', [])
    competing = narrative.get('competing_priorities_mentioned', [])

    narrative_section = ""
    if narrative_summary and narrative_summary != 'Error analyzing timeline':
        narrative_section = f"""
NARRATIVE SUMMARY:
{narrative_summary}

DECISION POINTS:
{chr(10).join(f"- {dp}" for dp in decision_points)}

COMPETING PRIORITIES:
{chr(10).join(f"- {cp}" for cp in competing)}
"""

    return f"""Extract ACTIONS (volitional professional decisions) from this ethics case.
{source_text_section}{narrative_section}{temporal_context}

For each ACTION, extract:
1. label: Concise name (3-5 words)
2. description: 1-2 sentences
3. agent: Person and role
4. temporal_marker: When it occurred
5. source_section: "facts" or "discussion"
6. intention: {{mental_state, intended_outcome, foreseen_unintended_effects, agent_knowledge}}
7. ethical_context: {{obligations_fulfilled, obligations_violated, guiding_principles, active_constraints, competing_obligations}}
8. competing_priorities: {{has_tradeoffs, priority_conflict, conflicting_factors, resolution_reasoning}}
9. professional_context: {{within_competence, required_capabilities, required_resources}}

Return JSON:
```json
{{"actions": [
  {{
    "label": "Task Assignment Decision",
    "description": "Engineer assigned complex task to intern",
    "agent": "John Smith (Senior Engineer)",
    "temporal_marker": "Month 3",
    "source_section": "facts",
    "intention": {{
      "mental_state": "deliberate",
      "intended_outcome": "Meet deadline",
      "foreseen_unintended_effects": ["Quality risk"],
      "agent_knowledge": "Knew intern lacked experience"
    }},
    "ethical_context": {{
      "obligations_fulfilled": [],
      "obligations_violated": ["Competence", "Supervision"],
      "guiding_principles": ["Efficiency"],
      "active_constraints": ["Registration"],
      "competing_obligations": [{{"obligation_1": "Deadline", "obligation_2": "Quality", "resolution": "Chose deadline"}}]
    }},
    "competing_priorities": {{
      "has_tradeoffs": true,
      "priority_conflict": "Urgency vs Competence",
      "conflicting_factors": ["Time", "Quality"],
      "resolution_reasoning": "Deadline prioritized"
    }},
    "professional_context": {{
      "within_competence": true,
      "required_capabilities": ["Engineering judgment"],
      "required_resources": ["Specifications"]
    }}
  }}
]}}
```

Only extract volitional decisions, not occurrences/events. Be specific with obligations and principles.

JSON:"""


def _build_phase2_prompt(actions: List[Dict], narrative: Dict) -> str:
    """Build Phase 2 prompt - scenario metadata enrichment."""

    # Summarize actions for context
    action_summaries = []
    for i, action in enumerate(actions):
        action_summaries.append(f"{i+1}. {action.get('label', 'Unknown')}: {action.get('description', '')}")

    return f"""Enrich these extracted actions with scenario metadata for teaching scenarios.

CASE NARRATIVE:
{narrative.get('unified_timeline_summary', '')}

EXTRACTED ACTIONS:
{chr(10).join(action_summaries)}

For each action (by number), provide scenario_metadata:
- character_motivation: Why did the agent take this action?
- ethical_tension: What competing values created tension?
- decision_significance: Key learning point for ethics education
- narrative_role: "inciting_incident", "rising_action", "climax", "falling_action", or "resolution"
- stakes: What's at risk? What could go wrong?
- is_decision_point: true/false - Could the story branch here?
- alternative_actions: 2-3 other realistic choices
- consequences_if_alternative: What would have happened for each alternative

Return JSON:
```json
{{"enrichments": [
  {{
    "action_index": 1,
    "scenario_metadata": {{
      "character_motivation": "Felt deadline pressure",
      "ethical_tension": "Professional duty vs organizational pressure",
      "decision_significance": "Teaching moment about delegation limits",
      "narrative_role": "inciting_incident",
      "stakes": "Design quality, public safety",
      "is_decision_point": true,
      "alternative_actions": ["Decline assignment", "Request extension"],
      "consequences_if_alternative": ["Management pushback", "Timeline impact"]
    }}
  }}
]}}
```

JSON:"""


def _merge_enrichments(actions: List[Dict], enrichments: List[Dict]) -> List[Dict]:
    """Merge scenario metadata enrichments into actions."""

    # Build index map
    enrichment_map = {}
    for e in enrichments:
        idx = e.get('action_index', 0)
        if idx > 0:
            enrichment_map[idx - 1] = e.get('scenario_metadata', {})

    # Merge
    for i, action in enumerate(actions):
        if i in enrichment_map:
            action['scenario_metadata'] = enrichment_map[i]
        else:
            action['scenario_metadata'] = {}

    return actions


def _parse_action_response(response_text: str) -> List[Dict]:
    """Parse LLM response to extract actions using shared JSON parser."""
    from app.utils.llm_json_utils import parse_json_object

    if not response_text or not response_text.strip():
        logger.error("[Stage 3] Empty response text")
        return []

    result = parse_json_object(response_text, context="action_extraction")
    if result is None:
        logger.error(f"[Stage 3] All parsing failed. Preview: {response_text[:500]}")
        return []

    actions = result.get('actions', [])
    logger.info(f"[Stage 3] Parsed {len(actions)} actions")
    return actions


def _parse_enrichment_response(response_text: str) -> List[Dict]:
    """Parse Phase 2 enrichment response using shared JSON parser."""
    from app.utils.llm_json_utils import parse_json_object

    if not response_text or not response_text.strip():
        return []

    result = parse_json_object(response_text, context="action_enrichment")
    if result is None:
        logger.warning("[Stage 3] Enrichment parsing failed")
        return []

    return result.get('enrichments', [])
