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

        return {
            'decision_index': session.current_decision_index,
            'total_decisions': len(decision_points),
            'decision_point': {
                'uri': dp.get('uri', ''),
                'label': dp.get('label', dp.get('decision_maker_label', '')),
                'question': dp.get('question', dp.get('description', '')),
                'decision_maker_label': dp.get('decision_maker_label', ''),
            },
            'options': [
                {'label': opt.get('label', ''), 'option_id': opt.get('option_id', '')}
                for opt in dp.get('options', [])
            ],
            'competing_obligation_labels': dp.get('competing_obligation_labels', []),
            'context': context,
        }

    # =========================================================================
    # CHOICE PROCESSING
    # =========================================================================

    def process_choice(
        self,
        session: ScenarioExplorationSession,
        chosen_option_index: int,
        time_spent_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Record a user's choice at the current decision point.

        No LLM call -- just records the choice index and board comparison
        fields from Phase 4 data, then advances the session.
        """
        decision_points = self._load_decision_points(session.case_id)

        if session.current_decision_index >= len(decision_points):
            raise ValueError("No more decisions to make")

        dp = decision_points[session.current_decision_index]
        options = dp.get('options', [])

        if chosen_option_index >= len(options):
            raise ValueError(f"Invalid option index: {chosen_option_index}")

        chosen_option = options[chosen_option_index]

        # Idempotency: check for existing choice (page refresh)
        existing = ScenarioExplorationChoice.query.filter_by(
            session_id=session.id,
            decision_point_index=session.current_decision_index
        ).first()
        if existing:
            is_complete = (session.current_decision_index + 1) >= len(decision_points)
            return {'choice_recorded': True, 'is_complete': is_complete, 'already_existed': True}

        # Find board choice from Phase 4 data
        board_choice_index, board_choice_label = None, None
        for i, opt in enumerate(options):
            if opt.get('is_board_choice'):
                board_choice_index = i
                board_choice_label = opt.get('label', '')
                break

        choice = ScenarioExplorationChoice(
            session_id=session.id,
            decision_point_index=session.current_decision_index,
            decision_point_uri=dp.get('uri', ''),
            decision_point_label=dp.get('decision_maker_label', dp.get('label', '')),
            chosen_option_index=chosen_option_index,
            chosen_option_label=chosen_option.get('label', ''),
            chosen_option_uri=chosen_option.get('uri', ''),
            board_choice_index=board_choice_index,
            board_choice_label=board_choice_label,
            matches_board_choice=(chosen_option_index == board_choice_index),
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

        decisions = []
        matches = 0
        for choice in session.choices:
            idx = choice.decision_point_index
            if idx >= len(branches):
                continue
            branch = branches[idx]
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
                'decision_index': idx,
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
        return [
            {'index': i, 'decision_maker_label': dp.get('decision_maker_label', f'Decision {i+1}')}
            for i, dp in enumerate(self._load_decision_points(case_id))
        ]

    # =========================================================================
    # DATA LOADING HELPERS
    # =========================================================================

    def _load_phase4_data(self, case_id: int) -> Dict:
        """Load the full phase4_narrative JSON for a case."""
        prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='phase4_narrative'
        ).order_by(ExtractionPrompt.created_at.desc()).first()

        if prompt and prompt.raw_response:
            try:
                return json.loads(prompt.raw_response)
            except (json.JSONDecodeError, TypeError):
                pass
        return {}

    def _load_decision_points(self, case_id: int) -> List[Dict]:
        """Load decision points from Phase 4 data."""
        prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='phase4_narrative'
        ).order_by(ExtractionPrompt.created_at.desc()).first()

        if prompt and prompt.raw_response:
            try:
                data = json.loads(prompt.raw_response)
                if 'scenario_seeds' in data and 'branches' in data['scenario_seeds']:
                    branches = data['scenario_seeds']['branches']
                    decision_points = []
                    for i, branch in enumerate(branches):
                        question = branch.get('question', branch.get('decision_question', ''))
                        context = branch.get('context', branch.get('description', ''))
                        options = branch.get('options', [])

                        decision_points.append({
                            'uri': branch.get('decision_point_uri', ''),
                            'label': branch.get('decision_point_label', branch.get('decision_maker_label', '')),
                            'decision_maker_label': branch.get('decision_maker_label', ''),
                            'question': question,
                            'context': context,
                            'description': context,
                            'options': options,
                            'competing_obligation_labels': branch.get('competing_obligation_labels', []),
                        })
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
