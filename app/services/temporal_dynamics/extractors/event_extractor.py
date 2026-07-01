"""
Event Extractor for Enhanced Temporal Dynamics Pass

Extracts occurrences (non-volitional events) aligned to the ratified Event (E)
field set (extraction-architecture spec, E section):
- Origin classification (event_type: outcome / exogenous / automatic, the
  Berreby et al. 2017 agent-caused vs external vs automatic origin axis)
- Fluent transitions (initiates / terminates State labels) plus the OWL-Time extent
- Causal context (the action that caused the event)
"""

from typing import Dict, List
import logging
from datetime import datetime

from model_config import ModelConfig
from app.services.prompt_style import STYLE_FORMATTING_LINE

import os
from app.utils.llm_utils import text_from_message

logger = logging.getLogger(__name__)


def extract_events_with_classification(
    narrative: Dict,
    temporal_markers: Dict,
    actions: List[Dict],
    case_id: int,
    llm_trace: List[Dict]
) -> List[Dict]:
    """
    Extract events (occurrences, outcomes) with origin classification.

    Args:
        narrative: Unified narrative from Stage 1
        temporal_markers: Temporal markers from Stage 2
        actions: Actions extracted in Stage 3
        case_id: Case ID for logging
        llm_trace: List to append LLM interactions to

    Returns:
        List of event dictionaries with classification
    """
    logger.info(f"[Stage 4] Extracting events for case {case_id}")

    # Initialize Anthropic client directly using environment variables
    # (avoids Flask context issues in LangGraph execution)
    try:
        import anthropic
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not found in environment")
        llm_client = anthropic.Anthropic(api_key=api_key, timeout=180.0, max_retries=2)
        model_name = ModelConfig.get_claude_model('powerful')
        logger.info(f"[Stage 4] Initialized Anthropic client with model {model_name}")
    except Exception as e:
        logger.error(f"[Stage 4] Failed to initialize LLM client: {e}")
        raise RuntimeError(f"No LLM client available: {e}")

    # Build prompt with action context
    prompt = _build_event_extraction_prompt(narrative, temporal_markers, actions)

    # Record prompt in trace
    trace_entry = {
        'stage': 'event_extraction',
        'timestamp': datetime.utcnow().isoformat(),
        'prompt': prompt,
        'model': model_name,
    }

    try:
        # Call LLM with streaming to prevent WSL2 TCP idle timeout (60s)
        logger.info("[Stage 4] Calling LLM for event extraction (streaming)")
        with llm_client.messages.stream(
            model=model_name,
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            response = stream.get_final_message()

        # Extract response content
        response_text = text_from_message(response)

        # Record response in trace
        trace_entry['response'] = response_text

        # Parse JSON response
        events = _parse_event_response(response_text)

        trace_entry['parsed_output'] = {
            'event_count': len(events),
        }

        # Add token usage if available
        if hasattr(response, 'usage'):
            trace_entry['tokens'] = {
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens,
                'total_tokens': response.usage.input_tokens + response.usage.output_tokens
            }

        logger.info(f"[Stage 4] Extracted {len(events)} events")

        return events

    except Exception as e:
        logger.error(f"[Stage 4] Error extracting events: {e}")
        trace_entry['error'] = str(e)
        return []

    finally:
        # Always append trace entry
        trace_entry['end_timestamp'] = datetime.utcnow().isoformat()
        llm_trace.append(trace_entry)


def _build_event_extraction_prompt(
    narrative: Dict,
    temporal_markers: Dict,
    actions: List[Dict]
) -> str:
    """Build the LLM prompt for event extraction."""

    # Format action context
    action_summary = []
    for action in actions[:10]:  # Limit to first 10 actions to avoid token overflow
        action_summary.append(f"- {action.get('label', 'Unknown')} (by {action.get('agent', 'Unknown')})")

    # Ontology-sourced typing boundary (disjointness + scope-note individuation), single-sourced from
    # the ontology via concept_ontology_slots so the live Step-4 typing matches the other components.
    # concept_ontology_slots reads the ontology TTL/SHACL files, so it works without a Flask app context
    # (this extractor runs inside the context-free LangGraph pipeline).
    from app.services.prompt_variable_resolver import concept_ontology_slots
    _slots = concept_ontology_slots('events', 'all')
    typing_block = "\n".join(s for s in (_slots.get('event_boundary'), _slots.get('event_individuation')) if s).strip()

    prompt = f"""You are analyzing an engineering ethics case to extract EVENTS (occurrences, not volitional decisions).

CASE NARRATIVE:
{narrative.get('unified_timeline_summary', '')}

ACTIONS ALREADY IDENTIFIED:
{chr(10).join(action_summary)}

---

Extract all EVENTS (occurrences, outcomes, automatic occurrences - NOT volitional decisions).

TYPING (rules the ontology enforces):
{typing_block}

For each event, identify:

1. BASIC INFO:
   - Event label: a SHORT, GENERAL name of AT MOST 4 words naming the KIND of event,
     NOT the case scenario: write "Structural Failure", NOT "Single-Client Conflict
     Mitigation Recognized"; write "Permit Denial", NOT "City Council Permit Denial
     After Accelerated Review". The label becomes the event's entity URI, so keep it
     terse and reusable; put all case-specific detail in the description.
   - Event description (1-2 sentences; put the case-specific detail HERE)
   - Temporal marker (when it occurred)

2. ORIGIN CLASSIFICATION:
   - Event type: "outcome" (result of a case agent's action) | "exogenous" (external,
     not caused by a case agent) | "automatic" (fires automatically once its triggering
     conditions hold). This is the Event Calculus origin distinction between agent-caused
     and exogenous / automatic occurrences (Berreby et al. 2017); it carries weight for
     responsibility attribution (an exogenous event is no agent's doing; an outcome traces
     to an action).

3. FLUENT TRANSITIONS (Event Calculus; Kowalski & Sergot 1986, Berreby et al. 2017):
   - initiates: list of STATES (fluents) this event brings into holding. An event does not
     create an obligation directly; it initiates a STATE (fluent) that then makes
     obligations or constraints apply. Name the conditions/states that become true (for
     example "Public Safety Risk", "Project Suspended"), using the same state names used
     elsewhere in the case. The downstream obligation and constraint links are recovered
     from these initiated states, not from free-text names. Empty list if the event changes
     no state.
   - terminates: list of STATES (fluents) this event ends (conditions that stop holding).
   - temporal_extent: "instant" if the event is a point occurrence, "interval" if it
     extends over a period (anchors the event in OWL-Time; temporal_marker stays the textual when).

4. CAUSAL CONTEXT:
   - Caused by action (reference action label if applicable)

{STYLE_FORMATTING_LINE}

Return your analysis as a JSON array:

```json
{{
  "events": [
    {{
      "label": "Design Structural Failure",
      "description": "Critical structural flaw discovered during independent review of intern's design work",
      "temporal_marker": "Month 5",
      "source_section": "facts",

      "classification": {{
        "event_type": "outcome"
      }},

      "initiates": ["Public Safety Risk", "Project Halted State"],
      "terminates": [],
      "temporal_extent": "instant",

      "causal_context": {{
        "caused_by_action": "Task Assignment Decision"
      }}
    }}
  ]
}}
```

IMPORTANT:
- Only extract occurrences (events), not volitional decisions (those are actions)
- Use the identified actions to infer causal relationships
- Capture what changes as the STATES the event initiates / terminates (section 3), not as
  free-text obligation or constraint names

JSON Response:"""

    return prompt


def _parse_event_response(response_text: str) -> List[Dict]:
    """Parse LLM response to extract events using shared JSON parser."""
    from app.utils.llm_json_utils import parse_json_object

    if not response_text or not response_text.strip():
        logger.error("[Stage 4] Empty response text received")
        return []

    logger.info(f"[Stage 4] Parsing response of {len(response_text)} characters")

    result = parse_json_object(response_text, context="event_extraction")
    if result is None:
        logger.error(f"[Stage 4] All JSON parsing strategies failed")
        logger.error(f"[Stage 4] Response preview (first 500 chars): {response_text[:500]}")
        return []

    events = result.get('events', [])
    logger.info(f"[Stage 4] Parsed {len(events)} events")
    return events
