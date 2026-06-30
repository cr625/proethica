"""
Action Extractor for Enhanced Temporal Dynamics Pass

Single-pass extraction of core action data: intentions (DCEC double-effect), ethical
context (obligations fulfilled/violated, principles, constraints), competing priorities,
professional context, and the Event-Calculus fluent transitions (initiates/terminates).

The former Phase 2 scenario-metadata enrichment (character motivation, dramatic tension,
stakes, alternatives, learning moments) was removed 2026-05-31: that content is narrative
gloss derivable on demand from the committed entities at scenario/lesson-generation time
(competing obligations -> ethical tension, intention + role -> motivation, decision points
+ options -> alternatives), so pre-extracting it was redundant. See
docs-internal/reextraction/pass3-fluents-owltime-revision.md.
"""

from typing import Dict, List, Optional
import logging
import os

from model_config import ModelConfig
from app.services.prompt_style import STYLE_FORMATTING_LINE
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
    Extract actions (volitional professional decisions) with their core metadata
    (intentions, ethics, competing priorities, professional context, fluent transitions).

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
        model_name = ModelConfig.get_claude_model('powerful')
        logger.info(f"[Stage 3] Initialized Anthropic client with model {model_name}")
    except Exception as e:
        logger.error(f"[Stage 3] Failed to initialize LLM client: {e}")
        raise RuntimeError(f"No LLM client available: {e}")

    actions = _extract_core_actions(
        narrative, temporal_markers, case_id, llm_client, model_name, llm_trace,
        facts_text=facts_text, discussion_text=discussion_text
    )
    logger.info(f"[Stage 3] Extracted {len(actions)} actions")
    return actions


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

    # Ontology-sourced typing boundary (disjointness + scope-note individuation), single-sourced from
    # the ontology via concept_ontology_slots so the live Step-3 typing matches the other components.
    # concept_ontology_slots reads the ontology TTL/SHACL files, so it works without a Flask app context
    # (this extractor runs inside the context-free LangGraph pipeline).
    from app.services.prompt_variable_resolver import concept_ontology_slots
    _slots = concept_ontology_slots('actions', 'all')
    typing_block = "\n".join(s for s in (_slots.get('action_boundary'), _slots.get('action_individuation')) if s).strip()

    return f"""Extract ACTIONS (volitional professional decisions) from this ethics case.
{source_text_section}{narrative_section}{temporal_context}

TYPING (rules the ontology enforces):
{typing_block}

For each ACTION, extract:
1. label: A SHORT, GENERAL action name of AT MOST 4 words. Name the KIND of action,
   not the case scenario: write "Advisory Recommendation", NOT "Advising City on
   Projects Generating Personal Commissions"; write "Task Assignment", NOT "Assigning
   Complex Bridge Analysis to Inexperienced Intern". All case-specific detail (who,
   what, where, conditions) goes in description / agent / temporal_marker below, never
   in the label. The label becomes the action's entity URI, so keep it terse and reusable.
2. description: 1-2 sentences (put the case-specific detail HERE)
3. agent: Person and role
4. temporal_marker: When it occurred
5. source_section: "facts" or "discussion"
6. intention: {{mental_state, intended_outcome, foreseen_unintended_effects, agent_knowledge}}
7. ethical_context: {{obligations_fulfilled, obligations_violated, guiding_principles}}. Name
   the obligations and principles using the SAME names they carry elsewhere in the case
   (the obligation/principle individuals already extracted), not fresh paraphrases: these
   are resolved downstream to those actual individuals (Action fulfillsObligation /
   violatesObligation / guidedByPrinciple edges). Do NOT list constraints or competing
   obligation pairs here; constraint activation is carried by the State an action
   initiates, and obligation competition by the case's defeasibility edges.
8. professional_context: {{within_competence, required_capabilities}}
9. initiates: list of STATES (fluents) this action brings into holding. In the Event
   Calculus (Kowalski & Sergot 1986; Berreby et al. 2017) a happening initiates a fluent
   that then holds until terminated. Name the conditions/states that become true because
   of this action (for example "Conflict of Interest", "Public Safety Risk Disclosed"),
   using the same state names used elsewhere in the case. Empty list if it changes no state.
10. terminates: list of STATES (fluents) this action ends (conditions that stop holding).
    Empty list if none.
11. temporal_extent: "instant" if the action is a point occurrence, "interval" if it
    extends over a period. This anchors the action in OWL-Time; temporal_marker stays the
    textual when.

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
      "guiding_principles": ["Efficiency"]
    }},
    "professional_context": {{
      "within_competence": true,
      "required_capabilities": ["Engineering judgment"]
    }},
    "initiates": ["Quality Risk State"],
    "terminates": [],
    "temporal_extent": "instant"
  }}
]}}
```

Only extract volitional decisions, not occurrences/events. Be specific with obligations and principles.

{STYLE_FORMATTING_LINE}

JSON:"""


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
