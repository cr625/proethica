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
        import httpx
        llm_client = anthropic.Anthropic(
            api_key=api_key,
            timeout=httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)
        )
        model_name = "claude-sonnet-4-5-20250929"
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
            messages=[{"role": "user", "content": prompt}],
            timeout=300.0
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

    prompt = f"""Extract EVENTS (occurrences, NOT volitional decisions) from this engineering ethics case.

CASE NARRATIVE:
{narrative.get('unified_timeline_summary', '')}

ACTIONS ALREADY IDENTIFIED:
{chr(10).join(action_summary)}

Extract all EVENTS (occurrences, outcomes, automatic triggers - NOT volitional decisions).

EMERGENCY_KEYWORDS: safety, urgent, critical, hazard, danger, risk, failure, accident

Return JSON with ALL these fields:

{{
  "events": [
    {{
      "label": "Brief event name",
      "description": "What occurred",
      "temporal_marker": "When",
      "source_section": "facts",
      "classification": {{
        "event_type": "outcome/exogenous/automatic_trigger",
        "emergency_status": "critical/high/medium/low/routine",
        "automatic_trigger": true/false,
        "preconditions_met": ["List if applicable"]
      }},
      "urgency": {{
        "urgency_level": "critical/high/medium/low",
        "overrides_obligations": true/false,
        "activates_constraints": ["List"],
        "emergency_procedures_required": true/false
      }},
      "triggers": {{
        "activates_constraints": ["List"],
        "creates_obligations": ["List"],
        "deactivates_constraints": [],
        "state_change": "What changed"
      }},
      "causal_context": {{
        "caused_by_action": "Action label if applicable",
        "causal_chain": ["Brief sequence"],
        "ness_test_factors": {{
          "necessary_factors": ["What was required"],
          "sufficient_factors": ["What combination was enough"]
        }}
      }},
      "scenario_metadata": {{
        "emotional_impact": "How affects characters",
        "stakeholder_consequences": {{"role": "impact"}},
        "dramatic_tension": "low/medium/high",
        "narrative_pacing": "slow_burn/escalation/crisis/aftermath",
        "crisis_identification": true/false,
        "learning_moment": "Educational takeaway",
        "discussion_prompts": ["Questions for classroom"],
        "ethical_implications": "Deeper tensions revealed"
      }}
    }}
  ]
}}

Only extract occurrences (events), not decisions (actions). Be specific with emergency classification. Return only JSON."""

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
