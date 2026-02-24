"""
Temporal Marker Extractor - Stage 2

Extracts dates, times, temporal phrases, and Allen interval relations from text.
Uses LLM for extraction with optional dateutil validation.
"""

from typing import Dict, List
import logging
import os

from models import ModelConfig

logger = logging.getLogger(__name__)


def extract_temporal_markers_llm(facts: str, discussion: str, timeline_summary: str, llm_trace: List[Dict]) -> Dict:
    """
    Use LLM to extract temporal markers from case text

    Args:
        facts: Facts section text
        discussion: Discussion section text
        timeline_summary: Timeline summary from Stage 1
        llm_trace: List to append LLM trace to

    Returns:
        {
            'explicit_dates': List[{'date': str, 'context': str, 'type': str}],
            'temporal_phrases': List[{'phrase': str, 'context': str, 'interpretation': str}],
            'durations': List[{'duration': str, 'context': str, 'interpretation': str}],
            'allen_relations': List[{'entity1': str, 'relation': str, 'entity2': str, 'evidence': str}]
        }
    """
    logger.info("[Temporal Extractor] Extracting temporal markers with LLM")

    from datetime import datetime

    # Initialize Anthropic client directly
    try:
        import anthropic
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not found in environment")
        llm_client = anthropic.Anthropic(api_key=api_key, timeout=180.0, max_retries=2)
        logger.info("[Temporal Extractor] Initialized Anthropic client")
    except Exception as e:
        logger.error(f"[Temporal Extractor] Failed to initialize LLM client: {e}")
        raise RuntimeError(f"No LLM client available: {e}")

    prompt = f"""You are analyzing an engineering ethics case to extract temporal information.

TIMELINE SUMMARY FROM PREVIOUS ANALYSIS:
{timeline_summary}

FACTS SECTION:
{facts}

DISCUSSION SECTION:
{discussion}

Extract all temporal information:

1. **Explicit Dates/Times**: Specific dates, times, or timestamps mentioned
   - Example: "March 15, 2023", "9:00 AM", "Q3 2022"
   - Include context (surrounding sentence)
   - Type: absolute, relative, or approximate

2. **Temporal Phrases**: Relative time expressions
   - Example: "three weeks later", "before the meeting", "during construction"
   - Include interpretation in absolute terms if possible

3. **Durations**: Time periods or lengths
   - Example: "for six months", "over the course of a year", "15 minutes"
   - Include what activity the duration applies to

4. **Allen Interval Relations**: Temporal relationships between events/actions
   - Relations: before, after, meets, overlaps, during, starts, finishes, equals
   - Example: "The inspection [before] the construction began"
   - Example: "Testing [during] the final phase"
   - Provide evidence (quote from text)

Return ONLY valid JSON with this structure:
{{
  "explicit_dates": [
    {{"date": "March 2023", "context": "The project started in March 2023", "type": "absolute"}}
  ],
  "temporal_phrases": [
    {{"phrase": "three weeks later", "context": "Three weeks later, the issue was discovered", "interpretation": "Approximately April 2023"}}
  ],
  "durations": [
    {{"duration": "six months", "context": "The contract was for six months", "interpretation": "March 2023 - September 2023"}}
  ],
  "allen_relations": [
    {{"entity1": "safety inspection", "relation": "before", "entity2": "construction start", "evidence": "The safety inspection was completed before construction began"}}
  ]
}}

Focus on precision. If unsure about a temporal marker, note it as "approximate" or "unclear".

JSON Response:"""

    # Record prompt in trace
    model_name = ModelConfig.get_claude_model('default')
    trace_entry = {
        'stage': 'temporal_markers',
        'timestamp': datetime.utcnow().isoformat(),
        'prompt': prompt,
        'model': model_name,
    }

    try:
        # Call LLM
        # Streaming to prevent WSL2 TCP idle timeout
        with llm_client.messages.stream(
            model=model_name,
            max_tokens=4000,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            response = stream.get_final_message()
        response_text = response.content[0].text

        # Record response in trace
        trace_entry['response'] = response_text

        # Add token usage if available
        if hasattr(response, 'usage'):
            trace_entry['tokens'] = {
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens,
                'total_tokens': response.usage.input_tokens + response.usage.output_tokens
            }

        logger.info(f"[Temporal Extractor] LLM response length: {len(response_text)} chars")

        # Parse JSON using shared utility
        from app.utils.llm_json_utils import parse_json_object
        markers = parse_json_object(response_text, context="temporal_markers")
        if markers is None:
            trace_entry['error'] = "No valid JSON found in response"
            trace_entry['end_timestamp'] = datetime.utcnow().isoformat()
            llm_trace.append(trace_entry)
            raise ValueError("LLM did not return valid JSON for temporal markers")

        trace_entry['parsed_output'] = {
            'explicit_dates': len(markers.get('explicit_dates', [])),
            'temporal_phrases': len(markers.get('temporal_phrases', [])),
            'durations': len(markers.get('durations', [])),
            'allen_relations': len(markers.get('allen_relations', []))
        }
        trace_entry['end_timestamp'] = datetime.utcnow().isoformat()
        llm_trace.append(trace_entry)
        return markers

    except Exception as e:
        logger.error(f"[Temporal Extractor] Error: {e}", exc_info=True)
        trace_entry['error'] = str(e)
        trace_entry['end_timestamp'] = datetime.utcnow().isoformat()
        llm_trace.append(trace_entry)
        # Return empty structure
        return {
            'explicit_dates': [],
            'temporal_phrases': [],
            'durations': [],
            'allen_relations': []
        }


def validate_dates(temporal_markers: Dict) -> List[str]:
    """
    Validate temporal markers using dateutil date parsing.

    Args:
        temporal_markers: Temporal markers from LLM extraction

    Returns:
        List of warning messages (empty if all valid)
    """
    warnings = []

    try:
        from dateutil import parser as date_parser

        logger.info("[Date Validator] Validating dates with dateutil")

        # Validate explicit dates
        for date_item in temporal_markers.get('explicit_dates', []):
            date_str = date_item.get('date', '')
            try:
                # Try to parse the date
                parsed_date = date_parser.parse(date_str, fuzzy=True)
                logger.debug(f"[Date Validator] Parsed '{date_str}' as {parsed_date}")
            except Exception as e:
                warning = f"Could not parse date '{date_str}': {str(e)}"
                warnings.append(warning)
                logger.warning(f"[Date Validator] {warning}")

    except ImportError:
        logger.info("[Date Validator] dateutil not available, skipping validation")
        # Not an error - validation is optional
    except Exception as e:
        logger.warning(f"[Date Validator] Validation error: {e}")
        warnings.append(f"Date validation error: {str(e)}")

    return warnings
