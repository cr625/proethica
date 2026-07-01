"""
Causal Chain Extractor for Enhanced Temporal Dynamics Pass

Analyzes causal relationships between actions and events with:
- NESS test analysis (necessary and sufficient factors)
- Responsibility attribution (direct/indirect)
- Causal chain construction (limited to 5 steps per plan)
- Intervention points identification
"""

from typing import Dict, List
import logging
import re
from datetime import datetime

import os

from model_config import ModelConfig
from app.utils.llm_utils import text_from_message

logger = logging.getLogger(__name__)

# Maximum causal chain depth per plan Q&A
MAX_CAUSAL_CHAIN_DEPTH = 5


def analyze_causal_chains(
    actions: List[Dict],
    events: List[Dict],
    case_id: int,
    llm_trace: List[Dict],
    facts_text: str = "",
    discussion_text: str = "",
) -> List[Dict]:
    """
    Analyze causal relationships between actions and events.

    Args:
        actions: Actions extracted in Stage 3
        events: Events extracted in Stage 4
        case_id: Case ID for logging
        llm_trace: List to append LLM interactions to
        facts_text: Full Facts-section text (for grounded causal reasoning + verbatim quotes)
        discussion_text: Full Discussion-section text

    Returns:
        List of causal chain dictionaries

    Causal analysis is the one Step-3 stage that is genuine logical reasoning (NESS test,
    counterfactual, responsibility) rather than span enumeration, and it runs once per case,
    so it uses the most capable model ('powerful' = Opus) over the FULL case text. The
    deterministic precedence/type guards in causal_edges.py remain the safety net regardless.
    """
    logger.info(f"[Stage 5] Analyzing causal chains for case {case_id}")

    # Initialize Anthropic client directly using environment variables
    # (avoids Flask context issues in LangGraph execution)
    try:
        import anthropic
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not found in environment")
        llm_client = anthropic.Anthropic(api_key=api_key, timeout=300.0, max_retries=2)
        # Strongest model for the logic step (low volume, high value); see docstring.
        model_name = ModelConfig.get_claude_model('powerful')
        logger.info(f"[Stage 5] Initialized Anthropic client with model {model_name}")
    except Exception as e:
        logger.error(f"[Stage 5] Failed to initialize LLM client: {e}")
        raise RuntimeError(f"No LLM client available: {e}")

    # Build prompt with action/event context + the full case text
    prompt = _build_causal_analysis_prompt(actions, events, facts_text, discussion_text)

    # Record prompt in trace
    trace_entry = {
        'stage': 'causal_analysis',
        'timestamp': datetime.utcnow().isoformat(),
        'prompt': prompt,
        'model': model_name,
    }

    try:
        # Call LLM with streaming to prevent WSL2 TCP idle timeout (60s)
        logger.info("[Stage 5] Calling LLM for causal chain analysis (streaming)")
        stream_kwargs = dict(
            model=model_name,
            max_tokens=12000,
            messages=[{"role": "user", "content": prompt}],
        )
        # Opus 4.8 rejects `temperature`; pass it only for models that accept it.
        if ModelConfig.supports_temperature(model_name):
            stream_kwargs["temperature"] = 0.2
        with llm_client.messages.stream(**stream_kwargs) as stream:
            response = stream.get_final_message()

        # Extract response content
        response_text = text_from_message(response)

        # Record response in trace
        trace_entry['response'] = response_text

        # Parse JSON response
        causal_chains = _parse_causal_response(response_text)

        # Enforce maximum chain depth
        causal_chains = _enforce_max_depth(causal_chains)

        # Grounded-quote check: now that the full case text is in context, causal_language
        # should be a VERBATIM span of it. Flag each chain (causal_language_grounded) and log
        # the rate, so a paraphrase masquerading as a quote is visible rather than silent.
        grounded = _check_quote_grounding(causal_chains, f"{facts_text}\n{discussion_text}")
        trace_entry['grounded_quotes'] = f"{grounded}/{len(causal_chains)}"
        logger.info(f"[Stage 5] causal_language grounded in case text: {grounded}/{len(causal_chains)}")

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
        trace_entry['end_timestamp'] = datetime.utcnow().isoformat()
        llm_trace.append(trace_entry)


def _build_causal_analysis_prompt(actions: List[Dict], events: List[Dict],
                                  facts_text: str = "", discussion_text: str = "") -> str:
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

    # Full case text -- the causal/NESS reasoning must be grounded in the source narrative,
    # not the 100-char summaries above. (When the temporal stages share a cached prefix this
    # block becomes a prompt-cache hit; for now it is sent in full.)
    case_text_block = ""
    if facts_text or discussion_text:
        case_text_block = (
            "CASE TEXT (ground every causal claim and quote in this):\n"
            f"--- FACTS ---\n{facts_text}\n\n"
            f"--- DISCUSSION ---\n{discussion_text}\n\n---\n\n"
        )

    prompt = f"""You are analyzing causal relationships in an engineering ethics case.

{case_text_block}ACTIONS (Volitional Decisions):
{chr(10).join(action_summary)}

EVENTS (Occurrences):
{chr(10).join(event_summary)}

---

Analyze the causal relationships between these actions and events.

A cause must temporally PRECEDE its effect; never list an effect that occurs before its
cause. Keep each cause and each effect a SINGLE action or event (do not conjoin two with
"+"); emit separate causal relationships instead.

For each significant causal relationship, identify:

1. DIRECT CAUSATION:
   - Cause (which action or event)
   - Effect (which event or subsequent action)
   - Causal language: a VERBATIM quote copied word-for-word from the CASE TEXT above that
     shows the causation. Do NOT paraphrase or invent; if no explicit causal sentence
     exists, quote the closest supporting sentence verbatim.
   - Source section: "facts" or "discussion" -- which case section grounds this causal
     claim, so the NESS analysis can be audited against the original text

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
      "source_section": "facts",

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


def _check_quote_grounding(causal_chains: List[Dict], case_text: str,
                           min_run_words: int = 8) -> int:
    """Flag each chain's causal_language as grounded iff a contiguous run of >= min_run_words
    of it appears verbatim (whitespace/case-normalized) in the case text. Sets
    chain['causal_language_grounded'] and returns the grounded count. Tolerant of leading/
    trailing framing the model adds around the real quote, but requires a genuine span."""
    norm = lambda s: re.sub(r"\s+", " ", (s or "").lower()).strip()
    ct = norm(case_text)
    grounded = 0
    for c in causal_chains:
        q = norm(c.get("causal_language", ""))
        words = q.split()
        is_g = False
        if q and ct:
            if len(words) < min_run_words:
                is_g = q in ct
            else:
                is_g = any(
                    " ".join(words[i:i + min_run_words]) in ct
                    for i in range(len(words) - min_run_words + 1)
                )
        c["causal_language_grounded"] = is_g
        if is_g:
            grounded += 1
    return grounded


def _parse_causal_response(response_text: str) -> List[Dict]:
    """Parse LLM response to extract causal chains using shared JSON parser."""
    from app.utils.llm_json_utils import parse_json_object

    if not response_text or not response_text.strip():
        logger.error("[Stage 5] Empty response text received")
        return []

    logger.info(f"[Stage 5] Parsing response of {len(response_text)} characters")

    result = parse_json_object(response_text, context="causal_analysis")
    if result is None:
        logger.error(f"[Stage 5] All JSON parsing strategies failed")
        logger.error(f"[Stage 5] Response preview (first 500 chars): {response_text[:500]}")
        return []

    chains = result.get('causal_relationships', [])
    logger.info(f"[Stage 5] Parsed {len(chains)} causal chains")
    return chains


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
