"""Shared JSON parsing utilities for LLM responses.

Handles common LLM response formats (code blocks, raw JSON) and provides
truncation recovery for responses cut off by max_tokens.
"""

import json
import re
import logging
from typing import Optional, Any, List

logger = logging.getLogger(__name__)


def parse_json_response(response_text: str, context: str = "unknown") -> Optional[List]:
    """Parse JSON array from LLM response, handling various formats.

    Tries multiple strategies in order:
    1. ```json ... ``` code block
    2. ``` ... ``` code block without language marker
    3. Raw JSON array [ ... ]
    4. First [ to last ] bracket search
    5. Truncation repair (close unclosed delimiters)

    Args:
        response_text: Raw LLM response text.
        context: Description for logging (e.g., "resolution patterns").

    Returns:
        Parsed list or None if parsing fails.
    """
    if not response_text or not response_text.strip():
        logger.warning(f"Empty response for {context}")
        return None

    # Strategy 1: code block with json marker
    json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 2: code block without json marker
    json_match = re.search(r'```\s*(.*?)\s*```', response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3: raw JSON array
    json_match = re.search(r'\[\s*\{.*?\}\s*\]', response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    # Strategy 4: first [ to last ]
    start = response_text.find('[')
    end = response_text.rfind(']')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(response_text[start:end + 1])
        except json.JSONDecodeError:
            pass

    # Strategy 5: truncation repair
    repaired = repair_truncated_json(response_text)
    if repaired:
        try:
            result = json.loads(repaired)
            logger.info(f"Recovered {context} JSON via truncation repair")
            return result
        except json.JSONDecodeError:
            pass

    logger.warning(f"Could not parse JSON in {context} response. First 500 chars: {response_text[:500]}")
    return None


def parse_json_object(response_text: str, context: str = "unknown") -> Optional[dict]:
    """Parse JSON object from LLM response (same strategies as parse_json_response but for objects).

    Args:
        response_text: Raw LLM response text.
        context: Description for logging.

    Returns:
        Parsed dict or None if parsing fails.
    """
    if not response_text or not response_text.strip():
        logger.warning(f"Empty response for {context}")
        return None

    # Strategy 1: code block
    json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', response_text, re.DOTALL)
    if json_match:
        parsed = _try_parse_object(json_match.group(1))
        if parsed is not None:
            return parsed

    # Strategy 2: truncated code block
    trunc_match = re.search(r'```(?:json)?\s*\n(.*)', response_text, re.DOTALL)
    if trunc_match and '```' not in trunc_match.group(1):
        parsed = _try_parse_object(trunc_match.group(1).rstrip())
        if parsed is not None:
            logger.info(f"Recovered {context} JSON from truncated code block")
            return parsed

    # Strategy 3: raw JSON object
    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if json_match:
        parsed = _try_parse_object(json_match.group(0))
        if parsed is not None:
            return parsed

    logger.warning(f"Could not parse JSON object in {context} response. First 500 chars: {response_text[:500]}")
    return None


def _try_parse_object(text: str) -> Optional[dict]:
    """Try to parse JSON object text, with repair strategies."""
    # Direct parse
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Trailing comma repair
    try:
        repaired = re.sub(r',\s*([}\]])', r'\1', text)
        result = json.loads(repaired)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Truncation repair
    repaired = _repair_truncated_object(text)
    if repaired:
        try:
            result = json.loads(repaired)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    return None


def _repair_truncated_object(text: str) -> Optional[str]:
    """Repair a truncated JSON object by balancing delimiters."""
    text = text.rstrip()
    # Strip incomplete trailing string value
    text = re.sub(r',?\s*"[^"]*":\s*"[^"]*$', '', text)
    # Strip incomplete trailing key
    text = re.sub(r',?\s*"[^"]*":\s*$', '', text)
    # Strip trailing comma
    text = re.sub(r',\s*$', '', text)

    opens = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')

    if opens <= 0 and open_brackets <= 0:
        return None

    text += ']' * open_brackets + '}' * opens
    return text


def repair_truncated_json(response_text: str) -> Optional[str]:
    """Repair JSON array truncated by max_tokens.

    Finds JSON content, strips the incomplete trailing element,
    and closes unclosed brackets/braces.

    Returns repaired JSON string or None if no JSON found.
    """
    # Find the start of JSON content
    start = response_text.find('[')
    if start == -1:
        # Try object
        start = response_text.find('{')
        if start == -1:
            return None

    text = response_text[start:].rstrip()

    # Strip incomplete trailing string value (e.g., "key": "incomplete val)
    text = re.sub(r',?\s*"[^"]*":\s*"[^"]*$', '', text)
    # Strip incomplete trailing key (e.g., "key":)
    text = re.sub(r',?\s*"[^"]*":\s*$', '', text)
    # Strip trailing comma
    text = re.sub(r',\s*$', '', text)
    # Strip trailing empty object start (e.g., ", {" left after value removal)
    text = re.sub(r',?\s*\{\s*$', '', text)

    # Count unbalanced delimiters
    opens = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')

    if opens <= 0 and open_brackets <= 0:
        return None  # Already balanced or no JSON structure

    # Close inner arrays first, then objects
    text += ']' * open_brackets + '}' * opens
    return text
