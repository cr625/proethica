"""
Interactive Scenario Service

Manages user interactive scenario explorations where they make choices
at decision points and view pre-computed consequences from Phase 4 data.

All consequence narratives, obligation labels, and board rationale are
pre-generated during Phase 4 extraction (Stage 4.3b). This service is
a pure data reader at runtime -- no LLM calls.

Workflow:
1. Start session: Load case decision points from Phase 4 data
2. Present decision: Show current decision point with options
3. Process choice: User selects option -> record choice, advance index
4. Summary: Show all choices made (no board comparison yet)
5. Analysis: Build comparison from Phase 4 data (board reveal)
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from app.models import db, Document, TemporaryRDFStorage, ExtractionPrompt
from app.models.scenario_exploration import ScenarioExplorationSession, ScenarioExplorationChoice

logger = logging.getLogger(__name__)


def get_phase4_prompt(case_id: int):
    """Get the latest phase4_narrative ExtractionPrompt record for a case.

    Shared accessor used by both InteractiveScenarioService and step5 route
    module to avoid duplicating the query.
    """
    return ExtractionPrompt.query.filter_by(
        case_id=case_id,
        concept_type='phase4_narrative'
    ).order_by(ExtractionPrompt.created_at.desc()).first()


class InteractiveScenarioService:
    """Service for managing interactive scenario explorations (pure data reader)."""

    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================

    def start_session(self, case_id: int, user_id: Optional[int] = None) -> ScenarioExplorationSession:
        """
        Start a new interactive exploration session for a case.

        Args:
            case_id: The case to explore
            user_id: Optional user ID for tracking

        Returns:
            New ScenarioExplorationSession
        """
        decision_points = self._load_decision_points(case_id)

        if not decision_points:
            raise ValueError(f"No decision points found for case {case_id}. Run Phase 4 first.")

        session = ScenarioExplorationSession(
            case_id=case_id,
            session_uuid=str(uuid.uuid4()),
            status='in_progress',
            current_decision_index=0,
            exploration_mode='interactive',
            active_fluents=[],
            terminated_fluents=[],
            user_id=user_id
        )

        db.session.add(session)
        db.session.commit()

        logger.info(f"Started exploration session {session.session_uuid} for case {case_id}")
        return session

    def get_session(self, session_uuid: str) -> Optional[ScenarioExplorationSession]:
        """Get an exploration session by UUID."""
        return ScenarioExplorationSession.query.filter_by(session_uuid=session_uuid).first()

    def get_active_sessions(self, case_id: int) -> List[ScenarioExplorationSession]:
        """Get all in-progress sessions for a case."""
        return ScenarioExplorationSession.query.filter_by(
            case_id=case_id,
            status='in_progress'
        ).order_by(ScenarioExplorationSession.last_activity_at.desc()).all()

    # =========================================================================
    # DECISION POINT HANDLING
    # =========================================================================

    def get_current_decision(self, session: ScenarioExplorationSession) -> Optional[Dict]:
        """
        Get the current decision point for a session.

        Returns dict with decision point data, options (labels only, no
        consequence data), and competing obligation labels.
        """
        decision_points = self._load_decision_points(session.case_id)

        if session.current_decision_index >= len(decision_points):
            return None

        dp = decision_points[session.current_decision_index]
        context = ""
        if session.current_decision_index == 0:
            phase4_data = self._load_phase4_data(session.case_id)
            context = phase4_data.get('scenario_seeds', {}).get('opening_context', '')
        else:
            context = dp.get('context', '')

        # Use neutral framing if available
        has_neutral = bool(dp.get('neutral_question'))
        if has_neutral:
            question = dp['neutral_question']
            neutral_opts = dp.get('neutral_options', [])
            option_order = dp.get('option_order', list(range(len(dp.get('options', [])))))
            options_for_display = [
                {'label': nopt.get('label', ''), 'option_id': f'opt_{nopt["original_index"]}',
                 'original_index': nopt['original_index']}
                for nopt in neutral_opts
            ]
        else:
            question = dp.get('question', dp.get('description', ''))
            options_for_display = [
                {'label': opt.get('label', ''), 'option_id': opt.get('option_id', ''),
                 'original_index': i}
                for i, opt in enumerate(dp.get('options', []))
            ]
            option_order = list(range(len(dp.get('options', []))))

        return {
            'decision_index': session.current_decision_index,
            'total_decisions': len(decision_points),
            'decision_point': {
                'uri': dp.get('uri', ''),
                'label': dp.get('label', dp.get('decision_maker_label', '')),
                'question': question,
                'decision_maker_label': dp.get('decision_maker_label', ''),
            },
            'options': options_for_display,
            'option_order': option_order,
            'competing_obligation_labels': dp.get('competing_obligation_labels', []),
            'context': context,
        }

    # =========================================================================
    # CHOICE PROCESSING
    # =========================================================================

    def process_choice(
        self,
        session: ScenarioExplorationSession,
        chosen_display_index: int,
        time_spent_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Record a user's choice at the current decision point.

        No LLM call -- just records the choice and board comparison
        fields from Phase 4 data, then advances the session.

        chosen_display_index is the position in the displayed option list,
        which may differ from the original option index if options were
        reordered by neutralization.
        """
        decision_points = self._load_decision_points(session.case_id)

        if session.current_decision_index >= len(decision_points):
            raise ValueError("No more decisions to make")

        dp = decision_points[session.current_decision_index]
        original_options = dp.get('options', [])

        # Map display index -> original index via option_order or neutral_options
        neutral_opts = dp.get('neutral_options', [])
        option_order = dp.get('option_order')
        if neutral_opts and chosen_display_index < len(neutral_opts):
            original_option_index = neutral_opts[chosen_display_index].get('original_index', chosen_display_index)
            chosen_label = neutral_opts[chosen_display_index].get('label', '')
        elif option_order and chosen_display_index < len(option_order):
            original_option_index = option_order[chosen_display_index]
            chosen_option = original_options[original_option_index] if original_option_index < len(original_options) else {}
            chosen_label = chosen_option.get('label', '')
        else:
            original_option_index = chosen_display_index
            chosen_option = original_options[original_option_index] if original_option_index < len(original_options) else {}
            chosen_label = chosen_option.get('label', '')

        # Idempotency: check for existing choice (page refresh)
        existing = ScenarioExplorationChoice.query.filter_by(
            session_id=session.id,
            decision_point_index=session.current_decision_index
        ).first()
        if existing:
            is_complete = (session.current_decision_index + 1) >= len(decision_points)
            return {'choice_recorded': True, 'is_complete': is_complete, 'already_existed': True}

        # Find board choice from original options
        board_choice_index, board_choice_label = None, None
        for i, opt in enumerate(original_options):
            if opt.get('is_board_choice'):
                board_choice_index = i
                board_choice_label = opt.get('label', '')
                break

        # Use neutral question for label if available
        question_for_label = dp.get('neutral_question', dp.get('question', ''))

        choice = ScenarioExplorationChoice(
            session_id=session.id,
            decision_point_index=session.current_decision_index,
            decision_point_uri=dp.get('uri', ''),
            decision_point_label=self._shorten_question(question_for_label, max_len=120) or dp.get('label', ''),
            chosen_option_index=original_option_index,
            chosen_option_label=chosen_label,
            chosen_option_uri='',
            board_choice_index=board_choice_index,
            board_choice_label=board_choice_label,
            matches_board_choice=(original_option_index == board_choice_index),
            time_spent_seconds=time_spent_seconds,
        )
        db.session.add(choice)

        session.current_decision_index += 1
        session.last_activity_at = datetime.utcnow()
        is_complete = session.current_decision_index >= len(decision_points)
        if is_complete:
            session.status = 'completed'
            session.completed_at = datetime.utcnow()
        db.session.commit()

        return {'choice_recorded': True, 'is_complete': is_complete}

    # =========================================================================
    # ANALYSIS
    # =========================================================================

    def get_analysis_data(self, session: ScenarioExplorationSession) -> Dict[str, Any]:
        """Build analysis comparison from Phase 4 data + session choices."""
        phase4_data = self._load_phase4_data(session.case_id)
        branches = phase4_data.get('scenario_seeds', {}).get('branches', [])
        resolution = phase4_data.get('narrative_elements', {}).get('resolution', {})

        # Build mapping from curated index -> original branch index
        curated_dps = self._load_decision_points(session.case_id)
        index_map = {i: dp['original_branch_index'] for i, dp in enumerate(curated_dps)
                     if 'original_branch_index' in dp}

        decisions = []
        matches = 0
        for choice in session.choices:
            curated_idx = choice.decision_point_index
            original_idx = index_map.get(curated_idx, curated_idx)
            if original_idx >= len(branches):
                continue
            branch = branches[original_idx]
            options = branch.get('options', [])

            user_opt = options[choice.chosen_option_index] if choice.chosen_option_index < len(options) else {}
            board_opt, board_idx = {}, None
            for i, opt in enumerate(options):
                if opt.get('is_board_choice'):
                    board_opt, board_idx = opt, i
                    break

            matched = choice.matches_board_choice
            if matched:
                matches += 1

            alternatives = [
                {'label': opt.get('label', ''), 'consequence_narrative': opt.get('consequence_narrative', ''),
                 'consequence_obligations': opt.get('consequence_obligations', [])}
                for i, opt in enumerate(options)
                if i != choice.chosen_option_index and i != board_idx
            ]

            decisions.append({
                'decision_index': curated_idx,
                'decision_maker_label': branch.get('decision_maker_label', ''),
                'question': branch.get('question', ''),
                'matched': matched,
                'board_rationale': branch.get('board_rationale', ''),
                'competing_obligation_labels': branch.get('competing_obligation_labels', []),
                'user_choice': {
                    'label': user_opt.get('label', ''),
                    'consequence_narrative': user_opt.get('consequence_narrative', ''),
                    'consequence_obligations': user_opt.get('consequence_obligations', []),
                },
                'board_choice': {
                    'label': board_opt.get('label', ''),
                    'consequence_narrative': board_opt.get('consequence_narrative', ''),
                    'consequence_obligations': board_opt.get('consequence_obligations', []),
                },
                'alternatives': alternatives,
            })

        return {
            'session_uuid': session.session_uuid,
            'case_id': session.case_id,
            'total_decisions': len(decisions),
            'matches_with_board': matches,
            'decisions': decisions,
            'resolution': resolution,
        }

    def get_all_decision_points_for_stepper(self, case_id: int) -> List[Dict]:
        """Minimal info for each decision point (for stepper display)."""
        result = []
        for i, dp in enumerate(self._load_decision_points(case_id)):
            question = dp.get('question', '')
            short_label = self._shorten_question(question, max_len=50) if question else f'Decision {i+1}'
            result.append({
                'index': i,
                'decision_maker_label': dp.get('decision_maker_label', f'Decision {i+1}'),
                'short_label': short_label,
            })
        return result

    @staticmethod
    def _shorten_question(question: str, max_len: int = 50) -> str:
        """Extract a short label from a decision question for stepper display."""
        # Strip common question prefixes
        for prefix in ['Should Engineer A ', 'Should Engineer B ', 'Did Engineer A ',
                        'Did Engineer B ', 'Should ', 'Did ']:
            if question.startswith(prefix):
                question = question[len(prefix):]
                break
        # Capitalize first letter
        if question:
            question = question[0].upper() + question[1:]
        # Truncate at word boundary
        if len(question) <= max_len:
            return question
        truncated = question[:max_len].rsplit(' ', 1)[0]
        return truncated + '...'

    # =========================================================================
    # ENRICHED CONTEXT
    # =========================================================================

    def get_enriched_decision_context(
        self, case_id: int, decision_index: int, phase4_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Build rich context for the current decision point: decision maker profile,
        competing obligations with definitions, ethical tensions, code provisions,
        and setting summary.

        All sections gracefully return empty dicts/lists when data is missing.
        """
        if phase4_data is None:
            phase4_data = self._load_phase4_data(case_id)

        narrative = phase4_data.get('narrative_elements', {})
        decision_points = self._load_decision_points(case_id)

        if decision_index >= len(decision_points):
            return {}

        dp = decision_points[decision_index]
        original_idx = dp.get('original_branch_index', decision_index)
        branches = phase4_data.get('scenario_seeds', {}).get('branches', [])
        branch = branches[original_idx] if original_idx < len(branches) else {}

        # --- Decision Maker ---
        decision_maker = {}
        dm_uri = branch.get('decision_maker_uri', '')
        dm_label = branch.get('decision_maker_label', dp.get('decision_maker_label', ''))
        characters = narrative.get('characters', [])
        for char in characters:
            # Match by URI or by label substring (URIs are shortform like "case-7#Engineer")
            char_uri = char.get('uri', '')
            char_label = char.get('label', '')
            if (dm_uri and (char_uri == dm_uri or dm_uri in char_uri or char_uri.endswith(dm_uri))) or \
               (dm_label and dm_label.lower() in char_label.lower()):
                decision_maker = {
                    'label': char_label,
                    'role_type': char.get('role_type', ''),
                    'professional_position': char.get('professional_position', ''),
                    'ethical_stance': char.get('ethical_stance', ''),
                }
                break
        if not decision_maker and dm_label:
            decision_maker = {'label': dm_label, 'role_type': '', 'professional_position': '', 'ethical_stance': ''}

        # --- Enriched Obligations ---
        obligation_labels = dp.get('competing_obligation_labels', [])
        enriched_obligations = self._resolve_obligation_labels(case_id, obligation_labels)

        # --- Matched Conflicts ---
        matched_conflicts = []
        conflicts = narrative.get('conflicts', [])
        obl_labels_lower = {lbl.lower() for lbl in obligation_labels}
        for conflict in conflicts:
            # Match if entity labels overlap with obligation labels or affected_role_uris contains dm
            e1_label = conflict.get('entity1_label', '').lower()
            e2_label = conflict.get('entity2_label', '').lower()
            affected = conflict.get('affected_role_uris', [])

            label_match = any(
                ol in e1_label or ol in e2_label or e1_label in ol or e2_label in ol
                for ol in obl_labels_lower
            )
            role_match = dm_uri and any(dm_uri in r or r in dm_uri for r in affected)

            if label_match or role_match:
                matched_conflicts.append({
                    'description': conflict.get('description', ''),
                    'conflict_type': conflict.get('conflict_type', ''),
                    'entity1_label': conflict.get('entity1_label', ''),
                    'entity2_label': conflict.get('entity2_label', ''),
                    'entity1_type': conflict.get('entity1_type', ''),
                    'entity2_type': conflict.get('entity2_type', ''),
                })

        # --- Provisions ---
        provisions = self._load_provisions(case_id)

        # --- Setting ---
        setting_summary = ''
        if decision_index == 0:
            setting = narrative.get('setting', {})
            setting_summary = setting.get('description', '') if isinstance(setting, dict) else ''

        return {
            'decision_maker': decision_maker,
            'enriched_obligations': enriched_obligations,
            'matched_conflicts': matched_conflicts,
            'provisions': provisions,
            'setting_summary': setting_summary,
        }

    def _resolve_obligation_labels(self, case_id: int, labels: List[str]) -> List[Dict]:
        """Resolve obligation labels to entities with definitions from the DB."""
        if not labels:
            return []

        from sqlalchemy import text
        query = text("""
            SELECT entity_uri, entity_label, entity_definition, entity_type, extraction_type
            FROM temporary_rdf_storage
            WHERE case_id = :case_id
              AND extraction_type IN ('obligations', 'constraints')
            ORDER BY entity_label
        """)
        rows = db.session.execute(query, {"case_id": case_id}).fetchall()

        # Build lookup by lowercase label
        db_lookup = {}
        for r in rows:
            db_lookup[r.entity_label.lower()] = {
                'label': r.entity_label,
                'uri': r.entity_uri or '',
                'definition': r.entity_definition or '',
                'entity_type': r.extraction_type or r.entity_type or '',
            }

        results = []
        for lbl in labels:
            lbl_lower = lbl.lower()
            if lbl_lower in db_lookup:
                entry = dict(db_lookup[lbl_lower])
            else:
                # Fuzzy match: check if the label is a substring of a DB label
                entry = None
                for db_lbl, data in db_lookup.items():
                    if lbl_lower in db_lbl or db_lbl in lbl_lower:
                        entry = dict(data)
                        break
                if entry is None:
                    entry = {'label': lbl, 'uri': '', 'definition': '', 'entity_type': 'obligations'}
            # Add shortened label for compact chip display
            entry['shortened_label'] = entry['label']
            results.append(entry)
        return results

    def _load_provisions(self, case_id: int) -> List[Dict]:
        """Load code provision references for a case."""
        from sqlalchemy import text
        query = text("""
            SELECT entity_uri, entity_label, entity_definition
            FROM temporary_rdf_storage
            WHERE case_id = :case_id AND entity_type = 'provisions'
            ORDER BY entity_label
        """)
        rows = db.session.execute(query, {"case_id": case_id}).fetchall()
        return [
            {'label': r.entity_label or '', 'uri': r.entity_uri or '', 'definition': r.entity_definition or ''}
            for r in rows
        ]

    # =========================================================================
    # TIMELINE
    # =========================================================================

    def get_timeline_events(self, case_id: int) -> List[Dict]:
        """
        Load timeline events for inline display.  Returns a list of dicts
        with keys: label, event_type ('action'|'event'), description.
        Sourced from Phase 4 narrative timeline, falling back to entity DB.
        """
        phase4 = self._load_phase4_data(case_id)
        timeline = phase4.get('timeline', {})
        raw_events = timeline.get('events', [])

        if raw_events:
            return [
                {
                    'label': ev.get('event_label', ev.get('label', '')),
                    'event_type': 'action' if ev.get('event_type') == 'action'
                                  or ev.get('phase_label') == 'Action' else 'event',
                    'description': ev.get('description', ''),
                }
                for ev in raw_events
            ]

        # Fallback: build from entity records
        from sqlalchemy import text
        query = text("""
            SELECT entity_label, entity_type, entity_definition
            FROM temporary_rdf_storage
            WHERE case_id = :case_id AND entity_type IN ('actions', 'events')
            ORDER BY entity_type, entity_label
        """)
        rows = db.session.execute(query, {"case_id": case_id}).fetchall()
        return [
            {
                'label': r.entity_label or '',
                'event_type': 'action' if r.entity_type == 'actions' else 'event',
                'description': r.entity_definition or '',
            }
            for r in rows
        ]

    # =========================================================================
    # COMBINED TIMELINE (events + decision markers)
    # =========================================================================

    def build_combined_timeline(
        self, case_id: int, decision_points: List[Dict], current_decision_index: int
    ) -> List[Dict]:
        """
        Build a unified timeline interleaving Phase 4 events with decision
        point markers.  Each item has:
            item_type:  'event' | 'decision'
            state:      'completed' | 'active' | 'future'  (decisions only)
            dp_index:   int  (decisions only, 0-based)
            label, event_type, description  (events)
            short_label, decision_maker_label  (decisions)

        Decision-type timeline events are matched to decision points by label
        similarity.  Unmatched decision points are placed proportionally.
        """
        raw_events = self.get_timeline_events(case_id)
        # Filter out structural markers (DP#, case_begins, board_resolution, conflict_emerges_*)
        import re
        timeline_events = [
            ev for ev in raw_events
            if not re.match(r'^DP\d+$', ev.get('label', ''))
            and ev.get('label', '') not in ('case_begins', 'board_resolution')
            and not ev.get('label', '').startswith('conflict_emerges_')
        ]

        if not timeline_events:
            # No timeline data -- return decision points only as a flat list
            return self._decisions_only_timeline(decision_points, current_decision_index)

        # Build combined list
        combined = []
        dp_placed = set()

        # Try to match timeline decision-events to our decision points
        dp_anchors = {}  # timeline_index -> dp_index
        for ti, ev in enumerate(timeline_events):
            if ev.get('event_type') == 'decision' or 'decision' in ev.get('label', '').lower():
                best_match = self._match_event_to_decision(ev, decision_points, dp_placed)
                if best_match is not None:
                    dp_anchors[ti] = best_match
                    dp_placed.add(best_match)

        # Place unmatched decision points proportionally
        unmatched_dps = [i for i in range(len(decision_points)) if i not in dp_placed]
        if unmatched_dps and timeline_events:
            n_events = len(timeline_events)
            for ui, dp_idx in enumerate(unmatched_dps):
                # Distribute evenly across timeline positions
                pos = int((dp_idx + 1) / (len(decision_points) + 1) * n_events)
                pos = min(pos, n_events - 1)
                # Find nearest unused slot
                while pos in dp_anchors and pos < n_events - 1:
                    pos += 1
                dp_anchors[pos] = dp_idx
                dp_placed.add(dp_idx)

        # Build the interleaved list
        for ti, ev in enumerate(timeline_events):
            # Insert decision marker BEFORE matched event
            if ti in dp_anchors:
                dp_idx = dp_anchors[ti]
                dp = decision_points[dp_idx]
                state = self._decision_state(dp_idx, current_decision_index)
                combined.append({
                    'item_type': 'decision',
                    'state': state,
                    'dp_index': dp_idx,
                    'short_label': dp.get('short_label', f'Decision {dp_idx + 1}'),
                    'decision_maker_label': dp.get('decision_maker_label', ''),
                })

            # Determine event state relative to the current decision point
            # Events before the first unplaced anchor are 'past', after are 'future'
            event_state = self._event_state_from_anchors(ti, dp_anchors, current_decision_index)
            combined.append({
                'item_type': 'event',
                'state': event_state,
                'label': ev.get('label', ''),
                'event_type': ev.get('event_type', 'event'),
                'description': ev.get('description', ''),
            })

        # Append any decision points that still didn't get placed
        for dp_idx in range(len(decision_points)):
            if dp_idx not in dp_placed:
                state = self._decision_state(dp_idx, current_decision_index)
                dp = decision_points[dp_idx]
                combined.append({
                    'item_type': 'decision',
                    'state': state,
                    'dp_index': dp_idx,
                    'short_label': dp.get('short_label', f'Decision {dp_idx + 1}'),
                    'decision_maker_label': dp.get('decision_maker_label', ''),
                })

        return combined

    def _decisions_only_timeline(
        self, decision_points: List[Dict], current_decision_index: int
    ) -> List[Dict]:
        """Fallback when no timeline events exist: just list decision markers."""
        return [
            {
                'item_type': 'decision',
                'state': self._decision_state(i, current_decision_index),
                'dp_index': i,
                'short_label': dp.get('short_label', f'Decision {i + 1}'),
                'decision_maker_label': dp.get('decision_maker_label', ''),
            }
            for i, dp in enumerate(decision_points)
        ]

    @staticmethod
    def _decision_state(dp_index: int, current_index: int) -> str:
        if dp_index < current_index:
            return 'completed'
        elif dp_index == current_index:
            return 'active'
        return 'future'

    @staticmethod
    def _match_event_to_decision(
        event: Dict, decision_points: List[Dict], already_placed: set
    ) -> Optional[int]:
        """Find the best-matching decision point for a timeline event by label overlap."""
        ev_label = event.get('label', '').lower()
        if not ev_label:
            return None

        ev_words = set(ev_label.split())
        best_score, best_idx = 0, None

        for i, dp in enumerate(decision_points):
            if i in already_placed:
                continue
            dp_label = dp.get('decision_maker_label', '').lower()
            dp_words = set(dp_label.split())
            # Word overlap score
            overlap = len(ev_words & dp_words)
            if overlap > best_score:
                best_score = overlap
                best_idx = i

        return best_idx if best_score >= 1 else None

    @staticmethod
    def _event_state_from_anchors(
        event_index: int, dp_anchors: Dict[int, int], current_decision_index: int
    ) -> str:
        """Determine whether a timeline event is past/current/future relative to progress."""
        # Find the nearest decision anchor at or after this event
        nearest_dp_idx = None
        for anchor_pos in sorted(dp_anchors.keys()):
            if anchor_pos >= event_index:
                nearest_dp_idx = dp_anchors[anchor_pos]
                break

        if nearest_dp_idx is None:
            # Event is after all decision anchors
            return 'future'

        if nearest_dp_idx < current_decision_index:
            return 'past'
        elif nearest_dp_idx == current_decision_index:
            return 'current'
        return 'future'

    # =========================================================================
    # DATA LOADING HELPERS
    # =========================================================================

    def _load_phase4_data(self, case_id: int) -> Dict:
        """Load the full phase4_narrative JSON for a case."""
        prompt = get_phase4_prompt(case_id)
        if prompt and prompt.raw_response:
            try:
                return json.loads(prompt.raw_response)
            except (json.JSONDecodeError, TypeError):
                pass
        return {}

    def _load_decision_points(self, case_id: int) -> List[Dict]:
        """Load decision points from Phase 4 data, filtered by interactive selection."""
        prompt = get_phase4_prompt(case_id)

        if prompt and prompt.raw_response:
            try:
                data = json.loads(prompt.raw_response)
                if 'scenario_seeds' in data and 'branches' in data['scenario_seeds']:
                    seeds = data['scenario_seeds']
                    branches = seeds['branches']

                    # Get interactive selection (curated subset)
                    selection = seeds.get('interactive_selection')
                    if selection and selection.get('branch_indices'):
                        selected_indices = set(selection['branch_indices'])
                    else:
                        # No stored selection -- compute and persist so the
                        # selection is stable even if scoring heuristics change
                        from app.services.scenario_consolidation_service import consolidate_branches
                        result = consolidate_branches(branches)
                        selected_indices = set(result['branch_indices'])
                        seeds['interactive_selection'] = result
                        prompt.raw_response = json.dumps(data)
                        db.session.commit()
                        logger.info(
                            f"Persisted interactive_selection for case {case_id}: "
                            f"{len(selected_indices)} of {len(branches)} branches"
                        )

                    decision_points = []
                    for i, branch in enumerate(branches):
                        if i not in selected_indices:
                            continue
                        question = branch.get('question', branch.get('decision_question', ''))
                        context = branch.get('context', branch.get('description', ''))
                        options = branch.get('options', [])

                        dp = {
                            'uri': branch.get('decision_point_uri', ''),
                            'label': branch.get('decision_point_label', branch.get('decision_maker_label', '')),
                            'decision_maker_label': branch.get('decision_maker_label', ''),
                            'question': question,
                            'context': context,
                            'description': context,
                            'options': options,
                            'competing_obligation_labels': branch.get('competing_obligation_labels', []),
                            'original_branch_index': i,
                        }
                        # Carry through neutral framing if present
                        if branch.get('neutral_question'):
                            dp['neutral_question'] = branch['neutral_question']
                            dp['neutral_options'] = branch.get('neutral_options', [])
                            dp['option_order'] = branch.get('option_order', [])
                        decision_points.append(dp)
                    if decision_points:
                        return decision_points
            except (json.JSONDecodeError, TypeError):
                pass

        # Fallback to decision_point entities
        from sqlalchemy import text
        query = text("""
            SELECT entity_uri, entity_label, entity_definition, rdf_json_ld
            FROM temporary_rdf_storage
            WHERE case_id = :case_id AND entity_type = 'decision_point'
            ORDER BY entity_label
        """)
        results = db.session.execute(query, {"case_id": case_id}).fetchall()

        decision_points = []
        for i, r in enumerate(results):
            rdf_data = r.rdf_json_ld if r.rdf_json_ld else {}
            question = rdf_data.get('decision_question', r.entity_definition or '')
            options = rdf_data.get('options', [])

            decision_points.append({
                'uri': r.entity_uri or '',
                'label': r.entity_label or '',
                'decision_maker_label': r.entity_label or '',
                'question': question,
                'description': r.entity_definition or '',
                'options': options,
                'competing_obligation_labels': [],
            })

        return decision_points


# Singleton instance
interactive_scenario_service = InteractiveScenarioService()
