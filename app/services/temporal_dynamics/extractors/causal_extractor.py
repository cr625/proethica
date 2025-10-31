"""
Causal Chain Extractor for Enhanced Temporal Dynamics Pass

Analyzes causal relationships between actions and events with:
- NESS test analysis (necessary and sufficient factors)
- Responsibility attribution (direct/indirect)
- Causal chain construction (limited to 5 steps per plan)
- Intervention points identification
"""

from typing import Dict, List
import json
import logging
from datetime import datetime

import os

logger = logging.getLogger(__name__)

# Maximum causal chain depth per plan Q&A
MAX_CAUSAL_CHAIN_DEPTH = 5


def analyze_causal_chains(
    actions: List[Dict],
    events: List[Dict],
    case_id: int,
    llm_trace: List[Dict]
) -> List[Dict]:
    """
    Analyze causal relationships between actions and events.

    Args:
        actions: Actions extracted in Stage 3
        events: Events extracted in Stage 4
        case_id: Case ID for logging
        llm_trace: List to append LLM interactions to

    Returns:
        List of causal chain dictionaries
    """
    logger.info(f"[Stage 5] Analyzing causal chains for case {case_id}")

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
        logger.info("[Stage 5] Initialized Anthropic client")
    except Exception as e:
        logger.error(f"[Stage 5] Failed to initialize LLM client: {e}")
        raise RuntimeError(f"No LLM client available: {e}")

    # Build prompt with action/event context
    prompt = _build_causal_analysis_prompt(actions, events)

    # Record prompt in trace
    trace_entry = {
        'stage': 'causal_analysis',
        'timestamp': datetime.utcnow().isoformat(),
        'prompt': prompt,
        'model': model_name,
    }

    try:
        # Call LLM
        logger.info("[Stage 5] Calling LLM for causal chain analysis")
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
        causal_chains = _parse_causal_response(response_text)

        # Enforce maximum chain depth
        causal_chains = _enforce_max_depth(causal_chains)

        trace_entry['parsed_output'] = {
            'causal_chain_count': len(causal_chains),
            'max_chain_length': max((len(c.get('causal_chain', {}).get('sequence', [])) for c in causal_chains), default=0)
        }

        # Add token usage if available
        if hasattr(response, 'usage'):
            trace_entry['tokens'] = {
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens,
                'total_tokens': response.usage.input_tokens + response.usage.output_tokens
            }

        logger.info(f"[Stage 5] Identified {len(causal_chains)} causal chains")

        return causal_chains

    except Exception as e:
        logger.error(f"[Stage 5] Error analyzing causal chains: {e}")
        trace_entry['error'] = str(e)
        return []

    finally:
        # Always append trace entry
        llm_trace.append(trace_entry)


def _build_causal_analysis_prompt(actions: List[Dict], events: List[Dict]) -> str:
    """Build the LLM prompt for causal chain analysis."""

    # Format action summaries
    action_summary = []
    for i, action in enumerate(actions[:15], 1):  # Limit to avoid token overflow
        action_summary.append(
            f"{i}. {action.get('label', 'Unknown')} - "
            f"{action.get('description', 'No description')[:100]}"
        )

    # Format event summaries
    event_summary = []
    for i, event in enumerate(events[:15], 1):
        event_summary.append(
            f"{i}. {event.get('label', 'Unknown')} - "
            f"{event.get('description', 'No description')[:100]}"
        )

    prompt = f"""You are analyzing causal relationships in an engineering ethics case.

ACTIONS (Volitional Decisions):
{chr(10).join(action_summary)}

EVENTS (Occurrences):
{chr(10).join(event_summary)}

---

Analyze the causal relationships between these actions and events.

For each significant causal relationship, identify:

1. DIRECT CAUSATION:
   - Cause (which action or event)
   - Effect (which event or subsequent action)
   - Causal language (quote from text showing causation)

2. NESS TEST ANALYSIS (Necessary Element of Sufficient Set):
   - Necessary factors: What elements were REQUIRED for the outcome?
   - Sufficient factors: What combination was ENOUGH to cause the outcome?
   - Counterfactual: Would outcome have occurred without the cause?

3. RESPONSIBILITY ATTRIBUTION:
   - Responsible agent (who bears responsibility)
   - Within agent control: true/false
   - Agent knowledge (what agent knew at the time)
   - Intervening factors (external factors that contributed)
   - Responsibility type: "direct" | "indirect" | "shared"

4. CAUSAL CHAIN (Maximum {MAX_CAUSAL_CHAIN_DEPTH} steps):
   - Sequence: Ordered list of elements from initial action to final outcome
   - Intervention points: Where intervention could have prevented the outcome

IMPORTANT:
- Limit causal chains to {MAX_CAUSAL_CHAIN_DEPTH} steps maximum
- Focus on the most significant causal relationships
- Use NESS test to distinguish necessary from sufficient factors
- Identify responsibility clearly (direct, indirect, or shared)
- Note intervention points for counterfactual analysis

Return your analysis as a JSON array:

```json
{{
  "causal_relationships": [
    {{
      "cause": "Task Assignment Decision",
      "effect": "Design Structural Failure",
      "causal_language": "The assignment of this complex task to an inexperienced intern without proper supervision led directly to the structural flaw",

      "ness_test": {{
        "necessary_factors": [
          "Assignment to unqualified person",
          "Complex technical requirements beyond skill level",
          "Inadequate supervision during critical design phase"
        ],
        "sufficient_factors": [
          "Combination of inexperience + task complexity + lack of oversight"
        ],
        "counterfactual": "With qualified engineer or adequate supervision, flaw would likely have been prevented"
      }},

      "responsibility": {{
        "responsible_agent": "John Smith (Senior Engineer)",
        "within_control": true,
        "agent_knowledge": "Knew intern lacked experience but proceeded under deadline pressure",
        "intervening_factors": ["Tight project deadline", "Limited staffing"],
        "responsibility_type": "direct"
      }},

      "causal_chain": {{
        "sequence": [
          {{
            "step": 1,
            "element": "Task Assignment Decision",
            "description": "Senior engineer assigns complex structural analysis to junior intern"
          }},
          {{
            "step": 2,
            "element": "Inadequate Supervision Event",
            "description": "Intern works on design without sufficient guidance or review checkpoints"
          }},
          {{
            "step": 3,
            "element": "Design Flaw Introduction",
            "description": "Critical structural flaw incorporated into design due to inexperience"
          }},
          {{
            "step": 4,
            "element": "Initial Review Failure",
            "description": "Cursory review fails to identify the complexity of the flaw"
          }},
          {{
            "step": 5,
            "element": "Design Structural Failure Discovery",
            "description": "Independent expert review discovers critical safety flaw"
          }}
        ],
        "intervention_points": [
          {{
            "after_step": 1,
            "intervention": "Provide comprehensive supervision plan with regular checkpoints",
            "would_prevent": true,
            "likelihood": "high"
          }},
          {{
            "after_step": 3,
            "intervention": "Conduct thorough technical peer review",
            "would_prevent": true,
            "likelihood": "high"
          }}
        ]
      }}
    }}
  ]
}}
```

JSON Response:"""

    return prompt


def _parse_causal_response(response_text: str) -> List[Dict]:
    """
    Parse LLM response to extract causal chains.

    Handles both direct JSON and markdown code blocks.
    """
    try:
        # Try direct JSON parse first
        result = json.loads(response_text)
        return result.get('causal_relationships', [])

    except json.JSONDecodeError:
        # Try to extract JSON from markdown code block
        import re

        # Look for ```json ... ``` block
        json_match = re.search(r'```json\s*\n(.*?)\n```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            result = json.loads(json_str)
            return result.get('causal_relationships', [])

        # Look for { ... } object
        json_match = re.search(r'\{.*"causal_relationships".*\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            return result.get('causal_relationships', [])

        logger.error(f"Could not parse causal response as JSON: {response_text[:200]}")
        return []


def _enforce_max_depth(causal_chains: List[Dict]) -> List[Dict]:
    """
    Enforce maximum causal chain depth limit.

    Per plan Q&A: Limit to 5 steps to avoid excessive complexity.
    """
    for chain in causal_chains:
        causal_data = chain.get('causal_chain', {})
        sequence = causal_data.get('sequence', [])

        if len(sequence) > MAX_CAUSAL_CHAIN_DEPTH:
            # Truncate to max depth
            causal_data['sequence'] = sequence[:MAX_CAUSAL_CHAIN_DEPTH]
            causal_data['truncated'] = True
            causal_data['original_length'] = len(sequence)

            logger.warning(
                f"Causal chain truncated from {len(sequence)} to {MAX_CAUSAL_CHAIN_DEPTH} steps"
            )

    return causal_chains
