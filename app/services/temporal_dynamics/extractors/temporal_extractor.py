"""
Temporal Extractor - Stage 1: Combined Section Analysis

Uses LLM to analyze Facts and Discussion sections together to understand
the unified temporal narrative.
"""

from typing import Dict
import json
import logging

from app.utils.llm_utils import get_llm_client

logger = logging.getLogger(__name__)


def analyze_combined_sections(facts: str, discussion: str) -> Dict:
    """
    Use LLM to analyze combined Facts and Discussion sections

    Args:
        facts: Facts section text
        discussion: Discussion section text

    Returns:
        {
            'unified_timeline_summary': str,
            'decision_points': List[str],
            'temporal_overlap_notes': str,
            'competing_priorities_mentioned': List[str]
        }
    """
    logger.info("[Extractor] Analyzing combined sections")

    llm_client = get_llm_client()

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
        response = llm_client.invoke(prompt)
        response_text = response.content

        logger.info(f"[Extractor] LLM response length: {len(response_text)} chars")

        # Try to parse JSON directly
        try:
            analysis = json.loads(response_text)
            logger.info("[Extractor] Successfully parsed JSON directly")
            return analysis
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            import re
            json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group(1))
                logger.info("[Extractor] Successfully parsed JSON from code block")
                return analysis
            else:
                # Try to find JSON object anywhere in response
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group(0))
                    logger.info("[Extractor] Successfully parsed JSON from response body")
                    return analysis
                else:
                    logger.error("[Extractor] No valid JSON found in response")
                    raise ValueError("LLM did not return valid JSON")

    except Exception as e:
        logger.error(f"[Extractor] Error analyzing sections: {e}", exc_info=True)
        # Return default structure
        return {
            'unified_timeline_summary': 'Error analyzing timeline',
            'decision_points': [],
            'temporal_overlap_notes': f'Analysis failed: {str(e)}',
            'competing_priorities_mentioned': []
        }
