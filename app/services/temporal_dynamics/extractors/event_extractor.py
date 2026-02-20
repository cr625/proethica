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

from models import ModelConfig

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
        llm_client = anthropic.Anthropic(api_key=api_key, timeout=180.0)
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

6. SCENARIO METADATA (for interactive teaching scenarios):
   - Emotional impact: How does this event affect characters emotionally?
   - Stakeholder consequences: Who is affected and how?
   - Dramatic tension: Does this event increase tension/stakes? (low/medium/high)
   - Narrative pacing: Does this accelerate or slow the story? ("slow_burn", "escalation", "crisis", "aftermath")
   - Crisis identification: Is this a turning point in the story? (true/false)
   - Learning moment: What should students learn from this event?
   - Discussion prompts: List 2-3 questions for classroom discussion
   - Ethical implications: What ethical issues does this event reveal?

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
      }},

      "scenario_metadata": {{
        "emotional_impact": "Shock and alarm for senior engineer; anxiety for intern; concern for public; fear among project stakeholders",
        "stakeholder_consequences": {{
          "senior_engineer": "Professional reputation at risk, potential disciplinary action",
          "intern": "Loss of confidence, potential end to engineering career before it starts",
          "public": "Safety compromised, trust in engineering profession damaged",
          "company": "Project delays, financial losses, legal liability"
        }},
        "dramatic_tension": "high",
        "narrative_pacing": "crisis",
        "crisis_identification": true,
        "learning_moment": "Demonstrates concrete consequences of inadequate supervision and competence violations; shows how professional shortcuts create cascading risks",
        "discussion_prompts": [
          "At what point could this outcome have been prevented?",
          "What systemic changes would prevent similar failures?",
          "How should professional responsibility be distributed in complex projects?"
        ],
        "ethical_implications": "Reveals tension between efficiency pressures and safety obligations; demonstrates duty to ensure competent practice; shows impact of professional negligence on vulnerable populations"
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
- For scenario metadata: Think about how this event impacts the story and learning
  - Emotional impact should capture multiple perspectives (agent, affected parties, observers)
  - Stakeholder consequences should be specific and concrete
  - Dramatic tension indicates how suspenseful/uncertain the situation becomes
  - Narrative pacing shows whether story accelerates (crisis/escalation) or slows (aftermath/slow_burn)
  - Crisis identification marks turning points where situation fundamentally changes
  - Learning moments should be clear educational takeaways
  - Discussion prompts should probe ethical reasoning, not just facts
  - Ethical implications should reveal deeper tensions and values conflicts

JSON Response:"""

    return prompt


def _parse_event_response(response_text: str) -> List[Dict]:
    """
    Parse LLM response to extract events.

    Handles various JSON formats with robust error handling:
    - Direct JSON
    - Markdown code blocks (```json ... ```)
    - JSON embedded in text
    - Common JSON formatting issues (trailing commas, etc.)
    """
    import re

    if not response_text or not response_text.strip():
        logger.error("[Stage 4] Empty response text received")
        return []

    # Log response length for debugging
    logger.info(f"[Stage 4] Parsing response of {len(response_text)} characters")

    # Strategy 1: Try direct JSON parse
    try:
        result = json.loads(response_text)
        events = result.get('events', [])
        logger.info(f"[Stage 4] Direct JSON parse successful: {len(events)} events")
        return events
    except json.JSONDecodeError as e:
        logger.debug(f"[Stage 4] Direct JSON parse failed: {e}")

    # Strategy 2: Extract from markdown code block (```json ... ```)
    json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1).strip()
        try:
            result = json.loads(json_str)
            events = result.get('events', [])
            logger.info(f"[Stage 4] Markdown block parse successful: {len(events)} events")
            return events
        except json.JSONDecodeError as e:
            logger.debug(f"[Stage 4] Markdown block parse failed: {e}")
            # Try fixing common issues
            events = _try_fix_and_parse_events(json_str, "markdown block")
            if events is not None:
                return events

    # Strategy 3: Find outermost JSON object containing "events"
    json_match = re.search(r'(\{[^{}]*"events"\s*:\s*\[.*?\][^{}]*\})', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
        try:
            result = json.loads(json_str)
            events = result.get('events', [])
            logger.info(f"[Stage 4] Regex extraction successful: {len(events)} events")
            return events
        except json.JSONDecodeError as e:
            logger.debug(f"[Stage 4] Regex extraction failed: {e}")
            events = _try_fix_and_parse_events(json_str, "regex extraction")
            if events is not None:
                return events

    # Strategy 4: Find any JSON object and look for events key
    start_idx = response_text.find('{')
    if start_idx != -1:
        depth = 0
        end_idx = start_idx
        for i, char in enumerate(response_text[start_idx:], start_idx):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break

        if end_idx > start_idx:
            json_str = response_text[start_idx:end_idx]
            try:
                result = json.loads(json_str)
                events = result.get('events', [])
                logger.info(f"[Stage 4] Brace matching parse successful: {len(events)} events")
                return events
            except json.JSONDecodeError as e:
                logger.debug(f"[Stage 4] Brace matching parse failed: {e}")
                events = _try_fix_and_parse_events(json_str, "brace matching")
                if events is not None:
                    return events

    # All strategies failed
    logger.error(f"[Stage 4] All JSON parsing strategies failed")
    logger.error(f"[Stage 4] Response preview (first 500 chars): {response_text[:500]}")
    logger.error(f"[Stage 4] Response preview (last 200 chars): {response_text[-200:]}")
    return []


def _try_fix_and_parse_events(json_str: str, source: str) -> List[Dict]:
    """
    Attempt to fix common JSON issues and parse for events.

    Returns list of events if successful, None if failed.
    """
    import re

    # Fix 1: Remove trailing commas
    fixed = re.sub(r',\s*([}\]])', r'\1', json_str)
    try:
        result = json.loads(fixed)
        events = result.get('events', [])
        logger.info(f"[Stage 4] Fixed trailing commas from {source}: {len(events)} events")
        return events
    except json.JSONDecodeError:
        pass

    # Fix 2: Replace single quotes with double quotes
    fixed = re.sub(r"(?<=[{,:\[])\s*'([^']*?)'\s*(?=[,}\]:])", r'"\1"', json_str)
    try:
        result = json.loads(fixed)
        events = result.get('events', [])
        logger.info(f"[Stage 4] Fixed single quotes from {source}: {len(events)} events")
        return events
    except json.JSONDecodeError:
        pass

    # Fix 3: Handle unescaped newlines
    fixed = json_str.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    try:
        result = json.loads(fixed)
        events = result.get('events', [])
        logger.info(f"[Stage 4] Fixed newlines from {source}: {len(events)} events")
        return events
    except json.JSONDecodeError:
        pass

    return None


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
