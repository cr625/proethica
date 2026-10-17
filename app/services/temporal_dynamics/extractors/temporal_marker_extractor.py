"""
Temporal Marker Extractor - Stage 2

Extracts dates, times, temporal phrases, and Allen interval relations from text.
Uses LLM for extraction with optional dateutil validation.
"""

from typing import Dict, List
import logging
import os
import re


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

    # Provider from the powerful tier (context-free, for LangGraph use).
    try:
        from app.services.llm.factory import get_tier_provider

        provider = get_tier_provider('powerful')
        logger.info(f"[Temporal Extractor] Initialized {provider.name} provider")
    except Exception as e:
        logger.error(f"[Temporal Extractor] Failed to initialize LLM provider: {e}")
        raise RuntimeError(f"No LLM provider available: {e}")

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
   - DO NOT treat a citation to a prior NSPE Board of Ethical Review case as a date. Forms
     like "Case 18-10", "BER Case 96-8", "Case 93-3", or "BER 07-6" are precedent references,
     NOT dates or times, even when introduced by "in" (e.g. "In BER Case 18-10, ..."). The
     "NN-NN" in a case number is a docket identifier, not a month-day or year. Exclude all
     such case citations from explicit_dates.

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
    model_name = provider.model
    trace_entry = {
        'stage': 'temporal_markers',
        'timestamp': datetime.utcnow().isoformat(),
        'prompt': prompt,
        'model': model_name,
    }

    try:
        # Call LLM
        # Streaming to prevent WSL2 TCP idle timeout.
        # direct_call_params floors max_tokens at 16000 for thinking-by-default models
        # (thinking spends from the same budget) and gates temperature; 4000 stays the
        # requested floor input for non-thinking models.
        response = provider.stream_complete(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000, temperature=None, model=model_name,
        )
        response_text = response.text

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

        # Deterministic backstop: drop any "explicit date" that is actually a BER/board case
        # citation ("Case 18-10", "BER Case 96-8"). The "NN-NN" docket shape reads like a date
        # to the model despite the prompt guard, and dateutil then chokes on it. Reuses the
        # same precedent pattern the rest of the pipeline uses to drop phantom precedents.
        markers = _drop_precedent_dates(markers)

        # Allen evidence must be a verbatim span of the case (lesson L5): the evidence field of a
        # committed relation carried a parenthetical hedge inside the quote. A hedge is stripped
        # and the span snapped to the case's characters; a relation whose evidence cannot be
        # located in the case at all is dropped (logged).
        markers = _ground_allen_evidence(markers, f"{facts}\n\n{discussion}")

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


def _drop_precedent_dates(markers: Dict) -> Dict:
    """Remove explicit_dates whose value is a BER/board case citation (e.g. "Case 18-10",
    "BER Case 96-8"). These are precedent docket numbers, not dates. Logs each drop (no
    silent removal). Returns the same markers dict with explicit_dates filtered."""
    from app.services.extraction.precedent_filter import is_precedent_reference

    dates = markers.get('explicit_dates') or []
    kept, dropped = [], []
    for item in dates:
        date_val = (item or {}).get('date', '') if isinstance(item, dict) else ''
        if is_precedent_reference(date_val):
            dropped.append(date_val)
        else:
            kept.append(item)
    if dropped:
        markers['explicit_dates'] = kept
        logger.info("[Temporal Extractor] Dropped %d case-citation 'date(s)' (precedent refs, "
                    "not dates): %s", len(dropped), ", ".join(dropped))
    return markers


_PARENTHETICAL_RE = re.compile(r"\s*\([^()]*\)")


def _ground_allen_evidence(markers: Dict, case_text: str) -> Dict:
    """Require each allen_relations[].evidence to be a verbatim span of the case text.

    The evidence is snapped to the case's own characters when its tokens match (the token test
    ignores punctuation and whitespace). When it does not match as written, a parenthetical the
    model inserted into the quote (a hedge such as "(apparently)") is removed and the test
    repeated. A relation whose evidence still matches nothing is dropped, since the evidence is
    the relation's only grounding. Logs every repair and drop; returns the same markers dict."""
    from app.services.extraction.quote_grounding import verbatim_span

    rels = markers.get('allen_relations') or []
    if not isinstance(rels, list) or not rels:
        return markers
    kept, dropped, repaired = [], [], 0
    for rel in rels:
        if not isinstance(rel, dict):
            continue
        evidence = str(rel.get('evidence') or '').strip()
        span = verbatim_span(evidence, case_text) if evidence else None
        if span is None and evidence:
            stripped = _PARENTHETICAL_RE.sub('', evidence).strip()
            if stripped and stripped != evidence:
                span = verbatim_span(stripped, case_text)
        if span is None:
            dropped.append(rel)
            continue
        if span != evidence:
            repaired += 1
        rel['evidence'] = span
        kept.append(rel)
    if dropped or repaired:
        markers['allen_relations'] = kept
        logger.info("[Temporal Extractor] Allen evidence grounding: %d relation(s) snapped to the "
                    "case text, %d dropped for evidence absent from the case: %s",
                    repaired, len(dropped),
                    "; ".join(f"{r.get('entity1')} {r.get('relation')} {r.get('entity2')}"
                              for r in dropped) or "none")
    return markers


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
