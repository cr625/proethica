"""
Stage 2: Timeline Construction for Scenario Generation

Loads timeline data from Step 3 temporal dynamics extraction and
structures it into scenario phases (introduction, development, resolution).
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from sqlalchemy import text

from app import db
from .models import (
    TimelineEntry, ScenarioTimeline, TemporalMarker, AllenRelation,
    Action, Event
)

logger = logging.getLogger(__name__)


@dataclass
class TimelinePhase:
    """A phase in the scenario timeline."""
    name: str  # 'introduction', 'development', or 'resolution'
    timepoints: List[Dict]
    start_index: int
    end_index: int
    description: str


class TimelineConstructor:
    """
    Constructs scenario timeline from Step 3 temporal dynamics data.

    Loads timeline, actions, and events from temporary_rdf_storage
    and structures them into pedagogically-relevant phases.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def build_timeline(self, case_id: int) -> ScenarioTimeline:
        """
        Build complete scenario timeline from Step 3 data.

        Args:
            case_id: Case ID

        Returns:
            ScenarioTimeline with phases and ordered events
        """
        self.logger.info(f"[Timeline Constructor] Building timeline for case {case_id}")

        try:
            # Load timeline structure from temporary_rdf_storage
            timeline_data = self._load_timeline_structure(case_id)

            # Load actions and events
            actions = self._load_actions(case_id)
            events = self._load_events(case_id)

            # Build timeline entries
            timeline_entries = self._build_timeline_entries(
                timeline_data,
                actions,
                events
            )

            # Create phases
            phases = self._create_phases(timeline_entries)

            # Calculate duration if possible
            duration = self._calculate_duration(timeline_data)

            self.logger.info(
                f"[Timeline Constructor] Built timeline with {len(timeline_entries)} entries "
                f"across {len(phases)} phases"
            )

            return ScenarioTimeline(
                entries=timeline_entries,
                phases=phases,
                total_actions=len(actions),
                total_events=len(events),
                duration_description=duration,
                temporal_consistency=timeline_data.get('temporal_consistency', {})
            )

        except Exception as e:
            self.logger.error(f"[Timeline Constructor] Error: {e}", exc_info=True)
            raise

    def _load_timeline_structure(self, case_id: int) -> Dict:
        """Load timeline structure from temporary_rdf_storage."""
        query = text("""
            SELECT rdf_json_ld
            FROM temporary_rdf_storage
            WHERE case_id = :case_id
              AND entity_type = 'timeline'
            LIMIT 1
        """)

        result = db.session.execute(query, {"case_id": case_id}).fetchone()

        if not result or not result.rdf_json_ld:
            self.logger.warning(f"No timeline found for case {case_id}")
            return {}

        timeline_json = result.rdf_json_ld

        # Extract relevant fields
        return {
            'timepoints': timeline_json.get('proeth:hasTimepoints', []),
            'total_elements': timeline_json.get('proeth:totalElements', 0),
            'action_count': timeline_json.get('proeth:actionCount', 0),
            'event_count': timeline_json.get('proeth:eventCount', 0),
            'temporal_consistency': timeline_json.get('proeth:temporalConsistency', {})
        }

    def _load_actions(self, case_id: int) -> List[Dict]:
        """Load action entities from temporary_rdf_storage."""
        query = text("""
            SELECT entity_uri, entity_label, entity_definition, rdf_json_ld
            FROM temporary_rdf_storage
            WHERE case_id = :case_id
              AND entity_type = 'actions'
            ORDER BY entity_label
        """)

        results = db.session.execute(query, {"case_id": case_id}).fetchall()

        actions = []
        for row in results:
            json_ld = row.rdf_json_ld or {}
            actions.append({
                'uri': row.entity_uri,
                'label': row.entity_label,
                'description': row.entity_definition or '',
                'temporal_marker': json_ld.get('proeth:temporalMarker', 'Unknown time'),
                'agent': json_ld.get('proeth:agent', 'Unknown'),
                'volitional': json_ld.get('proeth:volitional', True),
                'type': 'action'
            })

        return actions

    def _load_events(self, case_id: int) -> List[Dict]:
        """Load event entities from temporary_rdf_storage."""
        query = text("""
            SELECT entity_uri, entity_label, entity_definition, rdf_json_ld
            FROM temporary_rdf_storage
            WHERE case_id = :case_id
              AND entity_type = 'events'
            ORDER BY entity_label
        """)

        results = db.session.execute(query, {"case_id": case_id}).fetchall()

        events = []
        for row in results:
            json_ld = row.rdf_json_ld or {}
            classification = json_ld.get('proeth:classification', {})

            events.append({
                'uri': row.entity_uri,
                'label': row.entity_label,
                'description': row.entity_definition or '',
                'temporal_marker': json_ld.get('proeth:temporalMarker', 'Unknown time'),
                'urgency': json_ld.get('proeth:urgency', {}).get('proeth:urgencyLevel'),
                'emergency': classification.get('proeth:isEmergency', False),
                'type': 'event'
            })

        return events

    def _build_timeline_entries(
        self,
        timeline_data: Dict,
        actions: List[Dict],
        events: List[Dict]
    ) -> List[TimelineEntry]:
        """
        Build ordered timeline entries from timepoints, actions, and events.

        Matches actions and events to their timepoints and creates
        TimelineEntry objects in chronological order.
        """
        timepoints = timeline_data.get('timepoints', [])
        entries = []

        # Create a map of temporal markers to actions/events
        element_map = {}
        for action in actions:
            marker = action['temporal_marker']
            if marker not in element_map:
                element_map[marker] = []
            element_map[marker].append(action)

        for event in events:
            marker = event['temporal_marker']
            if marker not in element_map:
                element_map[marker] = []
            element_map[marker].append(event)

        # Build timeline entries for each timepoint
        for idx, timepoint in enumerate(timepoints):
            marker = timepoint.get('proeth:timepoint', 'Unknown')
            is_interval = timepoint.get('proeth:isInterval', False)

            # Get elements at this timepoint
            elements = element_map.get(marker, [])

            # Create entry for this timepoint
            entry = TimelineEntry(
                sequence_number=idx + 1,
                timepoint=marker,
                iso_duration=timepoint.get('time:hasTime', ''),
                is_interval=is_interval,
                elements=elements,
                element_count=len(elements)
            )

            entries.append(entry)

        return entries

    def _create_phases(self, entries: List[TimelineEntry]) -> Dict[str, TimelinePhase]:
        """
        Divide timeline into pedagogical phases.

        - Introduction (first 20%): Context setting, initial conditions
        - Development (middle 60%): Main events, decisions, complications
        - Resolution (final 20%): Outcomes, consequences, conclusions
        """
        total = len(entries)

        if total == 0:
            return {}

        # Calculate phase boundaries
        intro_end = max(1, int(total * 0.2))
        dev_end = max(intro_end + 1, int(total * 0.8))

        # Assign phase to each entry
        for idx, entry in enumerate(entries):
            if idx < intro_end:
                entry.phase = 'introduction'
            elif idx < dev_end:
                entry.phase = 'development'
            else:
                entry.phase = 'resolution'

        phases = {
            'introduction': TimelinePhase(
                name='introduction',
                timepoints=entries[:intro_end],
                start_index=0,
                end_index=intro_end - 1,
                description='Initial context and conditions'
            ),
            'development': TimelinePhase(
                name='development',
                timepoints=entries[intro_end:dev_end],
                start_index=intro_end,
                end_index=dev_end - 1,
                description='Main events, decisions, and complications'
            ),
            'resolution': TimelinePhase(
                name='resolution',
                timepoints=entries[dev_end:],
                start_index=dev_end,
                end_index=total - 1,
                description='Outcomes and consequences'
            )
        }

        return phases

    def _calculate_duration(self, timeline_data: Dict) -> str:
        """
        Calculate or estimate scenario duration from timepoints.

        Returns human-readable duration description.
        """
        timepoints = timeline_data.get('timepoints', [])

        if not timepoints:
            return "Duration unknown"

        # Look for temporal markers that indicate duration
        markers = [tp.get('proeth:timepoint', '') for tp in timepoints]

        # Simple heuristic: count distinct time references
        if any('month' in m.lower() for m in markers):
            return "Multiple months"
        elif any('week' in m.lower() for m in markers):
            return "Several weeks"
        elif any('day' in m.lower() for m in markers):
            return "Multiple days"
        else:
            return f"Timeline spans {len(timepoints)} events"
