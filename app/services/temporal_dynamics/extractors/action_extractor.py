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
        llm_client = anthropic.Anthropic(api_key=api_key)
        model_name = "claude-sonnet-4-20250514"
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
        # Call LLM
        logger.info("[Stage 3] Calling LLM for action extraction")
        response = llm_client.messages.create(
            model=model_name,
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
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

    prompt = f"""You are analyzing an engineering ethics case to extract ACTIONS (volitional professional decisions).

CASE NARRATIVE:
{narrative.get('unified_timeline_summary', '')}

DECISION POINTS IDENTIFIED:
{chr(10).join(f"- {dp}" for dp in narrative.get('decision_points', []))}

COMPETING PRIORITIES MENTIONED:
{chr(10).join(f"- {cp}" for cp in narrative.get('competing_priorities_mentioned', []))}

TEMPORAL CONTEXT:
{temporal_context}

---

Extract all ACTIONS (volitional decisions by professionals). For each action, identify:

1. BASIC INFO:
   - Action label (concise name, 3-5 words)
   - Action description (1-2 sentences)
   - Agent performing action (person name and role if available)
   - Temporal marker (when it occurred - use markers from temporal context)

2. INTENTION & MENTAL STATE:
   - Mental state: "deliberate", "negligent", or "accidental"
   - Intended outcome (what agent aimed to achieve)
   - Foreseen unintended effects (if any - Doctrine of Double Effect)
   - Agent's knowledge state at time of action

3. ETHICAL CONTEXT:
   - Obligations fulfilled (list specific obligations)
   - Obligations violated (list specific violations)
   - Guiding principles (e.g., public safety, efficiency, thoroughness)
   - Active constraints (e.g., registration requirements, time limits)
   - Competing obligations (if multiple obligations conflict)

4. COMPETING PRIORITIES:
   - Has tradeoffs: true/false
   - Priority conflict description (if applicable)
   - Conflicting factors (list factors that competed)
   - Resolution reasoning (how agent resolved the conflict)

5. PROFESSIONAL CONTEXT:
   - Within competence: true/false
   - Required capabilities (e.g., engineering judgment, technical analysis)
   - Required resources (e.g., design specifications, test equipment)

6. SCENARIO METADATA (for interactive teaching scenarios):
   - Character motivation: Why did the agent take this action? What drove them?
   - Ethical tension: What competing values or duties created tension?
   - Decision significance: Why does this matter for ethics education? What's the key learning point?
   - Narrative role: Story position - "inciting_incident", "rising_action", "climax", "falling_action", "resolution"
   - Stakes: What's at risk? What could go wrong?
   - Is decision point: true/false - Could the story branch here? Is this a critical choice moment?
   - Alternative actions: List 2-3 other choices the agent could have made
   - Consequences if alternative: For each alternative, what would have happened?

Return your analysis as a JSON array:

```json
{{
  "actions": [
    {{
      "label": "Task Assignment Decision",
      "description": "Senior engineer assigned complex design task to junior intern without adequate supervision plan",
      "agent": "John Smith (Senior Engineer)",
      "temporal_marker": "Month 3",
      "source_section": "facts",

      "intention": {{
        "mental_state": "deliberate",
        "intended_outcome": "Complete design quickly to meet deadline",
        "foreseen_unintended_effects": [
          "Intern may lack experience for task complexity"
        ],
        "agent_knowledge": "Knew intern had limited experience but felt deadline pressure"
      }},

      "ethical_context": {{
        "obligations_fulfilled": [],
        "obligations_violated": ["Competence_Obligation", "Adequate_Supervision"],
        "guiding_principles": ["Efficiency", "Meeting_Deadlines"],
        "active_constraints": ["Registration_Requirements", "Professional_Standards"],
        "competing_obligations": [
          {{
            "obligation_1": "Meet project deadline",
            "obligation_2": "Ensure work quality and competence",
            "resolution": "Prioritized deadline over competence verification"
          }}
        ]
      }},

      "competing_priorities": {{
        "has_tradeoffs": true,
        "priority_conflict": "Urgency vs. Professional Competence",
        "conflicting_factors": ["Time pressure", "Quality assurance", "Supervision burden"],
        "resolution_reasoning": "Deadline took precedence; planned to review intern's work later"
      }},

      "professional_context": {{
        "within_competence": true,
        "required_capabilities": ["Engineering_Judgment", "Task_Delegation", "Supervision"],
        "required_resources": ["Design_Specifications", "Project_Timeline", "Supervision_Time"]
      }},

      "scenario_metadata": {{
        "character_motivation": "Felt pressure to meet deadline; believed intern could handle it with later review",
        "ethical_tension": "Professional duty to ensure competence vs. organizational pressure to deliver on time",
        "decision_significance": "Critical teaching moment about delegation limits and professional responsibility",
        "narrative_role": "inciting_incident",
        "stakes": "Design quality, public safety if structural calculations are incorrect, intern's professional development",
        "is_decision_point": true,
        "alternative_actions": [
          "Decline the assignment and explain competence concerns to management",
          "Accept with explicit supervision plan including daily check-ins",
          "Request deadline extension to properly supervise or do work himself"
        ],
        "consequences_if_alternative": [
          "Might face management pushback but maintains professional standards",
          "Deadline might slip slightly but work quality assured",
          "Project timeline affected but risk eliminated"
        ]
      }}
    }}
  ]
}}
```

IMPORTANT:
- Only extract volitional decisions (actions), not occurrences (events)
- Be specific with obligation names and principles
- Identify competing priorities explicitly
- Use temporal markers from the identified context
- If an action affects multiple timepoints, note the primary one
- For scenario metadata: Think like a teacher creating an interactive case study
  - Character motivations should be psychologically realistic
  - Ethical tensions should be genuine dilemmas, not easy choices
  - Decision significance should explain what students will learn
  - Narrative roles follow story arc structure
  - Stakes should be concrete and serious
  - Decision points are where learners could make different choices
  - Alternatives should be realistic options the agent actually had
  - Consequences should show what would have happened differently

JSON Response:"""

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
