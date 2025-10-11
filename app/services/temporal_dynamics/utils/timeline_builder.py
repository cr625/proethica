"""
Timeline Builder for Enhanced Temporal Dynamics Pass

Constructs chronological timeline from actions, events, and temporal markers.
Resolves relative temporal references and validates consistency.
"""

from typing import Dict, List
import logging
import re

logger = logging.getLogger(__name__)


def build_timeline(
    actions: List[Dict],
    events: List[Dict],
    temporal_markers: Dict
) -> Dict:
    """
    Build chronological timeline from actions and events.

    Args:
        actions: Actions from Stage 3
        events: Events from Stage 4
        temporal_markers: Temporal markers from Stage 2

    Returns:
        Timeline dictionary with ordered timepoints
    """
    logger.info(f"[Stage 6] Building timeline from {len(actions)} actions and {len(events)} events")

    # Collect all temporal elements
    timeline_elements = []

    # Add actions
    for action in actions:
        timeline_elements.append({
            'type': 'action',
            'id': action.get('label', 'Unknown Action'),
            'label': action.get('label', 'Unknown'),
            'description': action.get('description', ''),
            'agent': action.get('agent', 'Unknown'),
            'temporal_marker': action.get('temporal_marker', 'Unknown time'),
            'urgency': None  # Actions don't have urgency
        })

    # Add events
    for event in events:
        urgency = event.get('urgency', {}).get('urgency_level', None)
        timeline_elements.append({
            'type': 'event',
            'id': event.get('label', 'Unknown Event'),
            'label': event.get('label', 'Unknown'),
            'description': event.get('description', ''),
            'temporal_marker': event.get('temporal_marker', 'Unknown time'),
            'urgency': urgency
        })

    # Group by temporal marker
    timeline_groups = _group_by_temporal_marker(timeline_elements)

    # Sort groups chronologically
    sorted_timeline = _sort_timeline_groups(timeline_groups)

    # Validate temporal consistency
    consistency_check = _validate_consistency(sorted_timeline)

    logger.info(f"[Stage 6] Timeline constructed with {len(sorted_timeline)} timepoints")

    return {
        'timeline': sorted_timeline,
        'temporal_consistency_check': consistency_check,
        'total_elements': len(timeline_elements),
        'actions': len(actions),
        'events': len(events)
    }


def _group_by_temporal_marker(elements: List[Dict]) -> Dict[str, List[Dict]]:
    """Group timeline elements by their temporal marker."""
    groups = {}

    for element in elements:
        marker = element['temporal_marker']

        if marker not in groups:
            groups[marker] = []

        groups[marker].append(element)

    return groups


def _sort_timeline_groups(groups: Dict[str, List[Dict]]) -> List[Dict]:
    """
    Sort timeline groups chronologically.

    Handles common time markers like "Month 1", "Week 3", "Day 5", etc.
    """
    timeline = []

    # Extract sortable keys
    sortable_groups = []
    for marker, elements in groups.items():
        sort_key = _extract_sort_key(marker)
        sortable_groups.append((sort_key, marker, elements))

    # Sort by extracted key
    sortable_groups.sort(key=lambda x: x[0])

    # Build timeline
    for sort_key, marker, elements in sortable_groups:
        # Determine if this is a single timepoint or interval
        is_interval = '-' in marker or 'to' in marker.lower()

        timeline_entry = {
            'timepoint': marker,
            'iso_duration': _convert_to_iso(marker),
            'is_interval': is_interval,
            'elements': elements
        }

        timeline.append(timeline_entry)

    return timeline


def _extract_sort_key(marker: str) -> tuple:
    """
    Extract a sortable key from a temporal marker.

    Examples:
      - "Month 3" -> (1, 3)  # (unit_rank, value)
      - "Week 15" -> (2, 15)
      - "Day 100" -> (3, 100)
      - "Before Project Start" -> (0, 0)
      - "Unknown time" -> (999, 0)
    """
    marker_lower = marker.lower()

    # Try to extract number
    match = re.search(r'(\d+)', marker)
    if not match:
        # No number found - put at beginning or end
        if 'before' in marker_lower or 'start' in marker_lower:
            return (0, 0)
        else:
            return (999, 0)  # Unknown time at end

    value = int(match.group(1))

    # Determine unit
    if 'month' in marker_lower:
        return (1, value)
    elif 'week' in marker_lower:
        return (2, value)
    elif 'day' in marker_lower:
        return (3, value)
    elif 'hour' in marker_lower:
        return (4, value)
    else:
        return (5, value)  # Generic number


def _convert_to_iso(marker: str) -> str:
    """
    Convert temporal marker to ISO 8601 duration if possible.

    Examples:
      - "Month 3" -> "P3M"
      - "Week 15" -> "P15W"
      - "Day 100" -> "P100D"
    """
    marker_lower = marker.lower()

    # Extract number
    match = re.search(r'(\d+)', marker)
    if not match:
        return ""

    value = match.group(1)

    # Determine unit
    if 'month' in marker_lower:
        return f"P{value}M"
    elif 'week' in marker_lower:
        return f"P{value}W"
    elif 'day' in marker_lower:
        return f"P{value}D"
    elif 'hour' in marker_lower:
        return f"PT{value}H"
    else:
        return ""


def _validate_consistency(timeline: List[Dict]) -> Dict:
    """
    Validate temporal consistency of the timeline.

    Checks for:
    - Contradictions (e.g., A before B, but B appears first)
    - Warnings (e.g., very long gaps between events)
    """
    warnings = []
    contradictions = []

    # Check for large gaps (more than 10 timepoints apart)
    for i in range(len(timeline) - 1):
        current_iso = timeline[i].get('iso_duration', '')
        next_iso = timeline[i+1].get('iso_duration', '')

        # Extract numeric values if possible
        current_val = _extract_iso_value(current_iso)
        next_val = _extract_iso_value(next_iso)

        if current_val is not None and next_val is not None:
            gap = next_val - current_val
            if gap > 10:
                warnings.append(f"Large temporal gap ({gap} units) between {timeline[i]['timepoint']} and {timeline[i+1]['timepoint']}")

    # TODO: Add more sophisticated consistency checks
    # - Check for explicit "before/after" contradictions
    # - Validate Allen interval relations

    return {
        'valid': len(contradictions) == 0,
        'warnings': warnings,
        'contradictions': contradictions
    }


def _extract_iso_value(iso_duration: str) -> int:
    """Extract numeric value from ISO 8601 duration."""
    if not iso_duration:
        return None

    match = re.search(r'(\d+)', iso_duration)
    if match:
        return int(match.group(1))

    return None
