"""
Event Extractor for Enhanced Temporal Dynamics Pass

Extracts occurrences (non-volitional events) with:
- Emergency classification and urgency levels
- Automatic triggers and preconditions
- Constraint activation and obligation creation
- Causal context (what action caused this event)
"""

from typing import Dict, List
import json
import logging
from datetime import datetime

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
        llm_client = anthropic.Anthropic(api_key=api_key)
        model_name = "claude-sonnet-4-20250514"
        logger.info("[Stage 4] Initialized Anthropic client")
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
        # Call LLM
        logger.info("[Stage 4] Calling LLM for event extraction")
        response = llm_client.messages.create(
            model=model_name,
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )

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
   - Event label (concise name, 3-5 words)
   - Event description (1-2 sentences)
   - Temporal marker (when it occurred)

2. EVENT CLASSIFICATION:
   - Event type: "outcome" (result of action) | "exogenous" (external) | "automatic_trigger" (preconditions met)
   - Emergency status: "critical" | "high" | "medium" | "low" | "routine"
   - Automatic trigger: true/false
   - Preconditions met (if automatic trigger)

3. URGENCY & PRIORITY:
   - Urgency level: "critical" | "high" | "medium" | "low"
   - Overrides obligations: true/false
   - Activates constraints (which ones?)
   - Emergency procedures required: true/false

4. TRIGGERS & EFFECTS:
   - Activates constraints (list constraint names)
   - Creates obligations (list new obligations)
   - Deactivates constraints (list if any)
   - State change description

5. CAUSAL CONTEXT:
   - Caused by action (reference action label if applicable)
   - Causal chain summary (brief sequence leading to this event)
   - NESS test factors:
     * Necessary factors (what was required for this to occur)
     * Sufficient factors (what combination was enough)

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
        "emergency_status": "critical",
        "automatic_trigger": false,
        "preconditions_met": ["Inadequate supervision", "Insufficient review", "Complex task assigned"]
      }},

      "urgency": {{
        "urgency_level": "critical",
        "overrides_obligations": true,
        "activates_constraints": ["PublicSafety_Paramount_Constraint"],
        "emergency_procedures_required": true
      }},

      "triggers": {{
        "activates_constraints": ["PublicSafety_Paramount", "Immediate_Review_Required"],
        "creates_obligations": ["Immediate_Correction", "Report_To_Authority", "Halt_Construction"],
        "deactivates_constraints": [],
        "state_change": "Project halted; safety review initiated; stakeholders notified"
      }},

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
- Be specific with emergency classification
- Identify which constraints and obligations are triggered
- Use EMERGENCY_KEYWORDS: safety, urgent, critical, hazard, danger, risk, failure, accident

JSON Response:"""

    return prompt


def _parse_event_response(response_text: str) -> List[Dict]:
    """
    Parse LLM response to extract events.

    Handles both direct JSON and markdown code blocks.
    """
    try:
        # Try direct JSON parse first
        result = json.loads(response_text)
        return result.get('events', [])

    except json.JSONDecodeError:
        # Try to extract JSON from markdown code block
        import re

        # Look for ```json ... ``` block
        json_match = re.search(r'```json\s*\n(.*?)\n```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            result = json.loads(json_str)
            return result.get('events', [])

        # Look for { ... } object
        json_match = re.search(r'\{.*"events".*\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            return result.get('events', [])

        logger.error(f"Could not parse event response as JSON: {response_text[:200]}")
        return []


def _apply_emergency_keywords(events: List[Dict]) -> List[Dict]:
    """
    Apply automatic emergency flagging based on keywords.

    This supplements LLM classification per the plan's Q&A decision.
    """
    for event in events:
        # Check description and label for emergency keywords
        text = f"{event.get('label', '')} {event.get('description', '')}".lower()

        # Check if any emergency keyword appears
        has_emergency_keyword = any(keyword in text for keyword in EMERGENCY_KEYWORDS)

        if has_emergency_keyword:
            # Add emergency flag if not already critical
            classification = event.get('classification', {})
            if classification.get('emergency_status', '').lower() not in ['critical', 'high']:
                # Upgrade to high if keyword detected
                classification['emergency_status'] = 'high'
                event['keyword_emergency_detected'] = True

    return events


def _is_emergency(event: Dict) -> bool:
    """Check if event is classified as emergency (critical or high)."""
    classification = event.get('classification', {})
    status = classification.get('emergency_status', '').lower()
    return status in ['critical', 'high']
