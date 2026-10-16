"""
Temporal Extractor - Stage 1: Combined Section Analysis

Uses LLM to analyze Facts and Discussion sections together to understand
the unified temporal narrative.
"""

from typing import Dict, Tuple
import logging
from datetime import datetime

from model_config import ModelConfig

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

    # Provider from the powerful tier (context-free, for LangGraph use).
    try:
        from app.services.llm.factory import get_tier_provider

        provider = get_tier_provider('powerful')
        logger.info(f"[Extractor] Initialized {provider.name} provider")
    except Exception as e:
        logger.error(f"[Extractor] Failed to initialize LLM provider: {e}")
        raise RuntimeError(f"No LLM provider available: {e}")

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
        model_name = provider.model

        # Streaming through the provider protocol (WSL2 idle-timeout
        # avoidance stays in the adapters); 4000 stays the requested
        # budget for non-thinking models.
        response = provider.stream_complete(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000, temperature=None, model=model_name,
        )
        response_text = response.text

        logger.info(f"[Extractor] LLM response length: {len(response_text)} chars")

        # Extract token usage
        token_info = {
            'input_tokens': response.usage.input_tokens if hasattr(response, 'usage') else 0,
            'output_tokens': response.usage.output_tokens if hasattr(response, 'usage') else 0,
            'total_tokens': (response.usage.input_tokens + response.usage.output_tokens) if hasattr(response, 'usage') else 0
        }

        # Parse JSON using shared utility
        from app.utils.llm_json_utils import parse_json_object
        analysis = parse_json_object(response_text, context="section_analysis")
        if analysis is None:
            raise ValueError("LLM did not return valid JSON for section analysis")

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
            'model': provider.model if 'provider' in locals() else ModelConfig.get_tier_model('powerful'),
            'parsed_output': error_analysis,
            'tokens': {}
        }
        return error_analysis, error_trace
