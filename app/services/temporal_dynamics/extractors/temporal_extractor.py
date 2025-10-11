"""
Temporal Extractor - Stage 1: Combined Section Analysis

Uses LLM to analyze Facts and Discussion sections together to understand
the unified temporal narrative.
"""

from typing import Dict, Tuple
import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


def analyze_combined_sections(facts: str, discussion: str) -> Tuple[Dict, Dict]:
    """
    Use LLM to analyze combined Facts and Discussion sections

    Args:
        facts: Facts section text
        discussion: Discussion section text

    Returns:
        Tuple of (analysis_dict, trace_dict):
        - analysis_dict: {
            'unified_timeline_summary': str,
            'decision_points': List[str],
            'temporal_overlap_notes': str,
            'competing_priorities_mentioned': List[str]
          }
        - trace_dict: {
            'stage': 'section_analysis',
            'timestamp': str,
            'prompt': str,
            'response': str,
            'model': str,
            'parsed_output': Dict,
            'tokens': Dict
          }
    """
    logger.info("[Extractor] Analyzing combined sections")

    # Initialize Anthropic client directly using environment variables
    # (avoids Flask context issues in LangGraph execution)
    try:
        import anthropic
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not found in environment")
        llm_client = anthropic.Anthropic(api_key=api_key)
        logger.info("[Extractor] Initialized Anthropic client")
    except Exception as e:
        logger.error(f"[Extractor] Failed to initialize LLM client: {e}")
        raise RuntimeError(f"No LLM client available: {e}")

    prompt = f"""You are analyzing an engineering ethics case to understand its temporal dynamics.

Given these two sections from a professional ethics case:

FACTS SECTION:
{facts}

DISCUSSION SECTION:
{discussion}

Analyze the complete temporal narrative and identify:

1. **Primary Timeline**: What is the overall sequence of events described across both sections? Provide a concise summary.

2. **Key Decision Points**: What are the critical moments where professionals made choices? List them chronologically.

3. **Temporal Overlap**: How do the two sections relate temporally? Does Discussion analyze events from Facts? Does it add new temporal information? Are there conflicts or clarifications?

4. **Competing Priorities**: Are there any mentions of conflicting obligations, time pressures, resource tradeoffs, or competing ethical considerations? List them.

Return your analysis as valid JSON with this exact structure:
{{
  "unified_timeline_summary": "Brief summary of the overall temporal sequence of events",
  "decision_points": [
    "Decision point 1 with approximate timing",
    "Decision point 2 with approximate timing"
  ],
  "temporal_overlap_notes": "How Facts and Discussion sections relate temporally and what the relationship reveals",
  "competing_priorities_mentioned": [
    "Priority conflict or tradeoff 1",
    "Priority conflict or tradeoff 2"
  ]
}}

Respond ONLY with the JSON, no other text.

JSON Response:"""

    try:
        # Capture timestamp before LLM call
        call_timestamp = datetime.utcnow().isoformat()
        model_name = "claude-sonnet-4-20250514"

        # Use Anthropic messages API
        response = llm_client.messages.create(
            model=model_name,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = response.content[0].text

        logger.info(f"[Extractor] LLM response length: {len(response_text)} chars")

        # Extract token usage
        token_info = {
            'input_tokens': response.usage.input_tokens if hasattr(response, 'usage') else 0,
            'output_tokens': response.usage.output_tokens if hasattr(response, 'usage') else 0,
            'total_tokens': (response.usage.input_tokens + response.usage.output_tokens) if hasattr(response, 'usage') else 0
        }

        # Try to parse JSON directly
        analysis = None
        try:
            analysis = json.loads(response_text)
            logger.info("[Extractor] Successfully parsed JSON directly")
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            import re
            json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group(1))
                logger.info("[Extractor] Successfully parsed JSON from code block")
            else:
                # Try to find JSON object anywhere in response
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group(0))
                    logger.info("[Extractor] Successfully parsed JSON from response body")
                else:
                    logger.error("[Extractor] No valid JSON found in response")
                    raise ValueError("LLM did not return valid JSON")

        # Build trace record
        trace = {
            'stage': 'section_analysis',
            'timestamp': call_timestamp,
            'prompt': prompt,
            'response': response_text,
            'model': model_name,
            'parsed_output': analysis,
            'tokens': token_info
        }

        return analysis, trace

    except Exception as e:
        logger.error(f"[Extractor] Error analyzing sections: {e}", exc_info=True)
        # Return default structure with error trace
        error_analysis = {
            'unified_timeline_summary': 'Error analyzing timeline',
            'decision_points': [],
            'temporal_overlap_notes': f'Analysis failed: {str(e)}',
            'competing_priorities_mentioned': []
        }
        error_trace = {
            'stage': 'section_analysis',
            'timestamp': datetime.utcnow().isoformat(),
            'prompt': prompt if 'prompt' in locals() else '',
            'response': f'ERROR: {str(e)}',
            'model': 'claude-sonnet-4-20250514',
            'parsed_output': error_analysis,
            'tokens': {}
        }
        return error_analysis, error_trace
