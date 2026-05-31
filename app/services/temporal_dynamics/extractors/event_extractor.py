"""
Event Extractor for Enhanced Temporal Dynamics Pass

Extracts occurrences (non-volitional events) with:
- Emergency classification and urgency levels
- Automatic triggers and preconditions
- Constraint activation and obligation creation
- Causal context (what action caused this event)
"""

from typing import Dict, List
import logging
from datetime import datetime

from model_config import ModelConfig
from app.services.prompt_style import STYLE_FORMATTING_LINE

import os

logger = logging.getLogger(__name__)

# Keywords for automatic emergency detection
EMERGENCY_KEYWORDS = [
    'safety', 'urgent', 'critical', 'emergency', 'hazard', 'danger', 'risk',
    'failure', 'collapse', 'accident', 'injury', 'death', 'catastrophic'
]


def extract_events_with_classification(
    narrative: Dict,
    temporal_markers: Dict,
    actions: List[Dict],
    case_id: int,
    llm_trace: List[Dict]
) -> List[Dict]:
    """
    Extract events (occurrences, automatic triggers, outcomes) with classification.

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
        model_name = ModelConfig.get_claude_model('default')
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
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            response = stream.get_final_message()

        # Extract response content
        response_text = response.content[0].text

        # Record response in trace
        trace_entry['response'] = response_text

        # Parse JSON response
        events = _parse_event_response(response_text)

        # Apply automatic emergency flagging
        events = _apply_emergency_keywords(events)

        trace_entry['parsed_output'] = {
            'event_count': len(events),
            'emergency_events': sum(1 for e in events if _is_emergency(e))
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

    prompt = f"""You are analyzing an engineering ethics case to extract EVENTS (occurrences, not volitional decisions).

CASE NARRATIVE:
{narrative.get('unified_timeline_summary', '')}

ACTIONS ALREADY IDENTIFIED:
{chr(10).join(action_summary)}

---

Extract all EVENTS (occurrences, outcomes, automatic triggers - NOT volitional decisions).

For each event, identify:

1. BASIC INFO:
   - Event label: a SHORT, GENERAL name of AT MOST 4 words naming the KIND of event,
     NOT the case scenario: write "Structural Failure", NOT "Single-Client Conflict
     Mitigation Recognized"; write "Permit Denial", NOT "City Council Permit Denial
     After Accelerated Review". The label becomes the event's entity URI, so keep it
     terse and reusable; put all case-specific detail in the description.
   - Event description (1-2 sentences; put the case-specific detail HERE)
   - Temporal marker (when it occurred)

2. EVENT CLASSIFICATION:
   - Event type: "outcome" (result of an agent's action) | "exogenous" (external, not
     caused by a case agent) | "automatic_trigger" (fires automatically when preconditions
     hold). This is the Event Calculus distinction between agent-caused and exogenous /
     automatic occurrences (Berreby et al. 2017); it carries weight for responsibility
     attribution (an exogenous event is no agent's doing; an outcome traces to an action).
   - Severity: "critical" | "high" | "medium" | "low" | "routine". A heuristic triage
     indicator of how serious the occurrence is for the case, NOT a formal ontology
     category. (The former separate "urgency_level" field is removed; it always duplicated
     this value.)
   - Automatic trigger: true/false
   - Preconditions met (if automatic trigger)

3. STATE CHANGE:
   - State change: a brief prose summary of what changed in the world.
     Do NOT list the obligations or constraints that "become active" here. An event
     does not create an obligation or activate a constraint directly; it initiates a
     STATE (a fluent) that then makes those obligations/constraints apply. Capture the
     states in 3b (initiates / terminates), not free-text obligation/constraint names.
     The State -> Obligation and State -> Constraint links are recovered downstream
     from the already-extracted obligation and constraint individuals.

3b. FLUENT TRANSITIONS (Event Calculus; Kowalski & Sergot 1986, Berreby et al. 2017):
   - initiates: list of STATES (fluents) this event brings into holding. An event does not
     create an obligation directly; it initiates a STATE (fluent) that then makes
     obligations or constraints apply. Name the conditions/states that become true (for
     example "Public Safety Risk", "Project Suspended"), using the same state names used
     elsewhere in the case. The constraints/obligations above are the consequences of these
     initiated states. Empty list if the event changes no state.
   - terminates: list of STATES (fluents) this event ends (conditions that stop holding).
   - temporal_extent: "instant" if the event is a point occurrence, "interval" if it
     extends over a period (anchors the event in OWL-Time; temporal_marker stays the textual when).

4. CAUSAL CONTEXT:
   - Caused by action (reference action label if applicable)
   - Causal chain summary (brief sequence leading to this event)
   - NESS test factors:
     * Necessary factors (what was required for this to occur)
     * Sufficient factors (what combination was enough)

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
        "event_type": "outcome",
        "severity": "critical",
        "automatic_trigger": false,
        "preconditions_met": ["Inadequate supervision", "Insufficient review", "Complex task assigned"]
      }},

      "triggers": {{
        "state_change": "Project halted; safety review initiated; stakeholders notified"
      }},

      "initiates": ["Public Safety Risk", "Project Halted State"],
      "terminates": [],
      "temporal_extent": "instant",

      "causal_context": {{
        "caused_by_action": "Task Assignment Decision",
        "causal_chain": [
          "Senior engineer assigned complex task to unqualified intern",
          "Inadequate supervision provided during design phase",
          "Initial review insufficient to catch complexity issues",
          "Critical structural flaw discovered in detailed review"
        ],
        "ness_test_factors": {{
          "necessary_factors": [
            "Assignment to person lacking expertise",
            "Complex technical requirements beyond skill level"
          ],
          "sufficient_factors": [
            "Combination of inexperience, complexity, and inadequate supervision"
          ]
        }}
      }}
    }}
  ]
}}
```

IMPORTANT:
- Only extract occurrences (events), not volitional decisions (those are actions)
- Use the identified actions to infer causal relationships
- Be specific with the severity assessment
- Capture what changes as the STATES the event initiates / terminates (3b), not as
  free-text obligation or constraint names
- Severity keywords (safety, urgent, critical, hazard, danger, risk, failure, accident)
  raise the severity to at least "high"

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


def _apply_emergency_keywords(events: List[Dict]) -> List[Dict]:
    """
    Raise an event's heuristic `severity` to at least "high" when its label or
    description contains an emergency-indicating keyword.

    This is a deliberately ad-hoc triage heuristic supplementing the LLM's severity
    assessment, not a literature-grounded classifier; severity is a triage indicator,
    not a formal ontology category.
    """
    for event in events:
        # Check description and label for emergency keywords
        text = f"{event.get('label', '')} {event.get('description', '')}".lower()

        # Check if any emergency keyword appears
        has_emergency_keyword = any(keyword in text for keyword in EMERGENCY_KEYWORDS)

        if has_emergency_keyword:
            # Raise severity to high if not already critical/high
            classification = event.get('classification', {})
            if classification.get('severity', '').lower() not in ['critical', 'high']:
                classification['severity'] = 'high'
                event['keyword_severity_detected'] = True

    return events


def _is_emergency(event: Dict) -> bool:
    """Check if event is high-severity (severity critical or high)."""
    classification = event.get('classification', {})
    status = classification.get('severity', '').lower()
    return status in ['critical', 'high']
