"""
Action Extractor for Enhanced Temporal Dynamics Pass

Extracts volitional professional decisions with:
- Intentions and mental states (deliberate/negligent/accidental)
- Competing priorities and ethical context
- Professional competence and required capabilities
- Links to obligations, principles, constraints, resources
"""

from typing import Dict, List
import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


def extract_actions_with_metadata(
    narrative: Dict,
    temporal_markers: Dict,
    case_id: int,
    llm_trace: List[Dict]
) -> List[Dict]:
    """
    Extract actions (volitional professional decisions) with rich metadata.

    Args:
        narrative: Unified narrative from Stage 1
        temporal_markers: Temporal markers from Stage 2
        case_id: Case ID for logging
        llm_trace: List to append LLM interactions to

    Returns:
        List of action dictionaries with full metadata
    """
    logger.info(f"[Stage 3] Extracting actions for case {case_id}")

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
        logger.info("[Stage 3] Initialized Anthropic client")
    except Exception as e:
        logger.error(f"[Stage 3] Failed to initialize LLM client: {e}")
        raise RuntimeError(f"No LLM client available: {e}")

    # Build prompt with temporal context
    prompt = _build_action_extraction_prompt(narrative, temporal_markers)

    # Record prompt in trace
    trace_entry = {
        'stage': 'action_extraction',
        'timestamp': datetime.utcnow().isoformat(),
        'prompt': prompt,
        'model': model_name,
    }

    try:
        # Call LLM with extended timeout for complex prompts
        logger.info("[Stage 3] Calling LLM for action extraction")
        response = llm_client.messages.create(
            model=model_name,
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
            timeout=300.0
        )
        response_text = response.content[0].text

        # Record response in trace
        trace_entry['response'] = response_text

        # Parse JSON response
        actions = _parse_action_response(response_text)
        trace_entry['parsed_output'] = {'action_count': len(actions)}

        # Add token usage if available
        if hasattr(response, 'usage'):
            trace_entry['tokens'] = {
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens,
                'total_tokens': response.usage.input_tokens + response.usage.output_tokens
            }

        logger.info(f"[Stage 3] Extracted {len(actions)} actions")

        return actions

    except Exception as e:
        logger.error(f"[Stage 3] Error extracting actions: {e}")
        trace_entry['error'] = str(e)
        return []

    finally:
        # Always append trace entry
        llm_trace.append(trace_entry)


def _build_action_extraction_prompt(narrative: Dict, temporal_markers: Dict) -> str:
    """Build the LLM prompt for action extraction."""

    # Format temporal context
    temporal_context = ""
    if temporal_markers.get('absolute'):
        temporal_context += f"\nAbsolute time markers: {len(temporal_markers['absolute'])} identified"
    if temporal_markers.get('relative'):
        temporal_context += f"\nRelative markers: {len(temporal_markers['relative'])} identified"

    prompt = f"""Extract ACTIONS (volitional professional decisions) from this engineering ethics case.

CASE NARRATIVE:
{narrative.get('unified_timeline_summary', '')}

DECISION POINTS:
{chr(10).join(f"- {dp}" for dp in narrative.get('decision_points', []))}

Return JSON with this structure:
{{
  "actions": [
    {{
      "label": "Brief action name",
      "description": "What happened",
      "agent": "Who did it",
      "temporal_marker": "When",
      "source_section": "facts",
      "intention": {{
        "mental_state": "deliberate/negligent/accidental",
        "intended_outcome": "Goal",
        "agent_knowledge": "What they knew"
      }},
      "ethical_context": {{
        "obligations_violated": ["List any"],
        "guiding_principles": ["List relevant"],
        "competing_obligations": [{{"obligation_1": "X", "obligation_2": "Y", "resolution": "How resolved"}}]
      }},
      "competing_priorities": {{
        "has_tradeoffs": true,
        "conflicting_factors": ["List factors"]
      }},
      "professional_context": {{
        "within_competence": true,
        "required_capabilities": ["List"]
      }},
      "scenario_metadata": {{
        "character_motivation": "Why",
        "ethical_tension": "Dilemma",
        "narrative_role": "inciting_incident/rising_action/climax",
        "stakes": "What's at risk",
        "is_decision_point": true
      }}
    }}
  ]
}}

Return only JSON, no explanations."""

    return prompt


def _parse_action_response(response_text: str) -> List[Dict]:
    """
    Parse LLM response to extract actions.

    Handles both direct JSON and markdown code blocks.
    """
    try:
        # Try direct JSON parse first
        result = json.loads(response_text)
        return result.get('actions', [])

    except json.JSONDecodeError:
        # Try to extract JSON from markdown code block
        import re

        # Look for ```json ... ``` block
        json_match = re.search(r'```json\s*\n(.*?)\n```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            result = json.loads(json_str)
            return result.get('actions', [])

        # Look for { ... } object
        json_match = re.search(r'\{.*"actions".*\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            return result.get('actions', [])

        logger.error(f"Could not parse action response as JSON: {response_text[:200]}")
        return []
