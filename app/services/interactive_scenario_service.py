"""
Interactive Scenario Service

Manages user interactive scenario explorations where they make choices
at decision points and see LLM-generated consequences constrained by
event calculus rules.

Workflow:
1. Start session: Load case decision points and initial fluents
2. Present decision: Show current decision point with options
3. Process choice: User selects option -> LLM generates consequences
4. Update state: Apply fluent changes from consequences
5. Loop or complete: Move to next decision or generate final analysis
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from app.models import db, Document, TemporaryRDFStorage, ExtractionPrompt
from app.models.scenario_exploration import ScenarioExplorationSession, ScenarioExplorationChoice
from app.utils.llm_utils import get_llm_client

logger = logging.getLogger(__name__)


class InteractiveScenarioService:
    """Service for managing interactive scenario explorations."""

    def __init__(self):
        self.llm_client = None

    def _get_llm_client(self):
        """Lazy load LLM client."""
        if self.llm_client is None:
            self.llm_client = get_llm_client()
        return self.llm_client

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
        # Load initial state from Phase 4 data
        decision_points = self._load_decision_points(case_id)
        initial_fluents = self._load_initial_fluents(case_id)

        if not decision_points:
            raise ValueError(f"No decision points found for case {case_id}. Run Phase 4 first.")

        # Create session
        session = ScenarioExplorationSession(
            case_id=case_id,
            session_uuid=str(uuid.uuid4()),
            status='in_progress',
            current_decision_index=0,
            exploration_mode='interactive',
            active_fluents=initial_fluents,
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

        Returns dict with:
            - decision_point: The decision point data
            - options: Available options
            - context: Current fluent state and narrative context
            - board_choice: What the board actually chose (hidden until after choice)
        """
        decision_points = self._load_decision_points(session.case_id)

        if session.current_decision_index >= len(decision_points):
            return None  # All decisions made

        dp = decision_points[session.current_decision_index]

        # Build context from current fluents
        context = self._build_decision_context(session, dp)

        return {
            'decision_index': session.current_decision_index,
            'total_decisions': len(decision_points),
            'decision_point': {
                'uri': dp.get('uri', ''),
                'label': dp.get('label', f'Decision {session.current_decision_index + 1}'),
                'question': dp.get('question', dp.get('description', '')),
                'description': dp.get('description', ''),
            },
            'options': dp.get('options', []),
            'context': context,
            'active_fluents': session.active_fluents or [],
        }

    def _build_decision_context(self, session: ScenarioExplorationSession, decision_point: Dict) -> str:
        """Build narrative context for the current decision."""
        # Get previous choices narrative
        previous_narrative = ""
        for choice in session.choices:
            if choice.consequences_narrative:
                previous_narrative += f"\n{choice.consequences_narrative}"

        # Get case opening context
        opening_context = self._load_opening_context(session.case_id)

        context = opening_context or "You are facing an ethical decision in a professional engineering context."

        if previous_narrative:
            context += f"\n\nBased on your previous choices:{previous_narrative}"

        # Add current fluent state
        if session.active_fluents:
            fluent_summary = ", ".join(session.active_fluents[:5])
            context += f"\n\nCurrent situation: {fluent_summary}"

        return context

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
        Process a user's choice at the current decision point.

        Args:
            session: The exploration session
            chosen_option_index: Index of the option chosen
            time_spent_seconds: How long user deliberated

        Returns:
            Dict with consequences and updated state
        """
        decision_points = self._load_decision_points(session.case_id)

        if session.current_decision_index >= len(decision_points):
            raise ValueError("No more decisions to make")

        dp = decision_points[session.current_decision_index]
        options = dp.get('options', [])

        if chosen_option_index >= len(options):
            raise ValueError(f"Invalid option index: {chosen_option_index}")

        chosen_option = options[chosen_option_index]

        # Check if choice already exists (e.g., page refresh)
        existing_choice = ScenarioExplorationChoice.query.filter_by(
            session_id=session.id,
            decision_point_index=session.current_decision_index
        ).first()

        if existing_choice:
            # Choice already recorded - return existing data and move to next
            logger.info(f"Choice already exists for session {session.id} decision {session.current_decision_index}")
            is_complete = (session.current_decision_index + 1) >= len(decision_points)
            return {
                'choice_recorded': True,
                'consequences_narrative': existing_choice.consequences_narrative or '',
                'matched_board': existing_choice.matches_board_choice,
                'board_choice': existing_choice.board_choice_label,
                'is_complete': is_complete,
                'next_decision_index': session.current_decision_index + 1 if not is_complete else None,
                'active_fluents': session.active_fluents,
                'already_existed': True
            }

        # Find board's actual choice
        board_choice_index = None
        board_choice_label = None
        for i, opt in enumerate(options):
            if opt.get('is_board_choice'):
                board_choice_index = i
                board_choice_label = opt.get('label', '')
                break

        # Generate consequences using LLM
        consequences = self._generate_consequences(
            session=session,
            decision_point=dp,
            chosen_option=chosen_option,
            all_options=options
        )

        # Record the choice
        choice = ScenarioExplorationChoice(
            session_id=session.id,
            decision_point_index=session.current_decision_index,
            decision_point_uri=dp.get('uri', ''),
            decision_point_label=dp.get('label', ''),
            chosen_option_index=chosen_option_index,
            chosen_option_label=chosen_option.get('label', ''),
            chosen_option_uri=chosen_option.get('uri', ''),
            board_choice_index=board_choice_index,
            board_choice_label=board_choice_label,
            matches_board_choice=(chosen_option_index == board_choice_index),
            consequences_narrative=consequences.get('narrative', ''),
            fluents_initiated=consequences.get('fluents_initiated', []),
            fluents_terminated=consequences.get('fluents_terminated', []),
            context_provided=consequences.get('context_provided', {}),
            time_spent_seconds=time_spent_seconds
        )

        db.session.add(choice)

        # Update session state
        session.current_decision_index += 1
        session.last_activity_at = datetime.utcnow()

        # Update fluents
        active = set(session.active_fluents or [])
        terminated = set(session.terminated_fluents or [])

        for f in consequences.get('fluents_initiated', []):
            active.add(f)
            terminated.discard(f)

        for f in consequences.get('fluents_terminated', []):
            active.discard(f)
            terminated.add(f)

        session.active_fluents = list(active)
        session.terminated_fluents = list(terminated)

        # Check if complete
        is_complete = session.current_decision_index >= len(decision_points)
        if is_complete:
            session.status = 'completed'
            session.completed_at = datetime.utcnow()

        db.session.commit()

        return {
            'choice_recorded': True,
            'consequences_narrative': consequences.get('narrative', ''),
            'matched_board': choice.matches_board_choice,
            'board_choice': board_choice_label,
            'is_complete': is_complete,
            'next_decision_index': session.current_decision_index if not is_complete else None,
            'active_fluents': session.active_fluents,
        }

    def _generate_consequences(
        self,
        session: ScenarioExplorationSession,
        decision_point: Dict,
        chosen_option: Dict,
        all_options: List[Dict]
    ) -> Dict[str, Any]:
        """
        Generate consequences of a choice using LLM with event calculus constraints.
        """
        # Build prompt with event calculus rules
        event_calculus_rules = self._load_event_calculus_rules(session.case_id)

        prompt = f"""You are analyzing the consequences of an ethical decision in a professional engineering case.

## Event Calculus Rules (constraints on what can happen)
{event_calculus_rules}

## Current State
Active fluents (things that are true): {json.dumps(session.active_fluents or [])}

## Decision Point
{decision_point.get('label', 'Decision')}
Question: {decision_point.get('question', decision_point.get('description', ''))}

## User's Choice
The user chose: "{chosen_option.get('label', '')}"
{chosen_option.get('description', '')}

## Task
Generate a brief narrative (2-3 sentences) describing the immediate consequences of this choice.
Also identify which fluents are initiated (become true) and terminated (become false) as a result.

Respond in JSON format:
{{
    "narrative": "Brief description of what happens as a result of this choice...",
    "fluents_initiated": ["list", "of", "new", "fluents"],
    "fluents_terminated": ["list", "of", "ended", "fluents"],
    "ethical_implications": "One sentence on ethical significance"
}}
"""

        try:
            client = self._get_llm_client()
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            # Parse JSON from response
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
                result['context_provided'] = {
                    'decision': decision_point.get('label', ''),
                    'choice': chosen_option.get('label', ''),
                    'active_fluents_before': session.active_fluents or []
                }
                return result

        except Exception as e:
            logger.error(f"Error generating consequences: {e}")

        # Fallback
        return {
            'narrative': f"You chose to {chosen_option.get('label', 'proceed')}. The situation continues to develop.",
            'fluents_initiated': [],
            'fluents_terminated': [],
            'context_provided': {}
        }

    # =========================================================================
    # FINAL ANALYSIS
    # =========================================================================

    def generate_final_analysis(self, session: ScenarioExplorationSession) -> Dict[str, Any]:
        """
        Generate final analysis comparing user's choices to board's choices.
        """
        if session.status != 'completed':
            raise ValueError("Session not complete - cannot generate analysis")

        # Gather choice comparison data
        choices_summary = []
        matches = 0
        total = len(session.choices)

        for choice in session.choices:
            choices_summary.append({
                'decision': choice.decision_point_label,
                'user_choice': choice.chosen_option_label,
                'board_choice': choice.board_choice_label,
                'matched': choice.matches_board_choice,
                'time_spent': choice.time_spent_seconds
            })
            if choice.matches_board_choice:
                matches += 1

        match_percentage = (matches / total * 100) if total > 0 else 0

        # Generate LLM analysis
        analysis_narrative = self._generate_analysis_narrative(session, choices_summary)

        # Build final analysis
        analysis = {
            'session_uuid': session.session_uuid,
            'case_id': session.case_id,
            'total_decisions': total,
            'matches_with_board': matches,
            'match_percentage': match_percentage,
            'choices_summary': choices_summary,
            'analysis_narrative': analysis_narrative,
            'final_fluent_state': session.active_fluents,
            'exploration_duration_seconds': (
                (session.completed_at - session.started_at).total_seconds()
                if session.completed_at and session.started_at else None
            )
        }

        # Save to session
        session.final_analysis = analysis
        db.session.commit()

        return analysis

    def _generate_analysis_narrative(
        self,
        session: ScenarioExplorationSession,
        choices_summary: List[Dict]
    ) -> str:
        """Generate narrative analysis of user's path vs board's path."""

        prompt = f"""Analyze this user's ethical decision-making compared to the Board of Ethical Review.

## User's Choices vs Board's Choices
{json.dumps(choices_summary, indent=2)}

## Task
Write a 3-4 paragraph analysis covering:
1. Overall alignment with board decisions ({sum(1 for c in choices_summary if c['matched'])}/{len(choices_summary)} matched)
2. Key differences in reasoning (where user diverged from board)
3. Ethical principles at play in the divergences
4. What this suggests about different ethical frameworks or priorities

Be constructive and educational. Neither path is inherently "wrong" - explore the ethical considerations.
"""

        try:
            client = self._get_llm_client()
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Error generating analysis narrative: {e}")
            return f"Your choices aligned with the board {sum(1 for c in choices_summary if c['matched'])} out of {len(choices_summary)} times."

    # =========================================================================
    # DATA LOADING HELPERS
    # =========================================================================

    def _load_decision_points(self, case_id: int) -> List[Dict]:
        """Load decision points from Phase 4 data."""
        # First try Phase 4 data
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

                        # Fix empty option labels on-the-fly
                        options = self._ensure_option_labels(options, question, context, i)

                        decision_points.append({
                            'uri': branch.get('decision_point_uri', ''),
                            'label': branch.get('decision_point_label', branch.get('decision_maker_label', '')),
                            'question': question,
                            'description': context,
                            'options': options
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

            # Fix empty option labels on-the-fly
            options = self._ensure_option_labels(options, question, '', i)

            decision_points.append({
                'uri': r.entity_uri or '',
                'label': r.entity_label or '',
                'question': question,
                'description': r.entity_definition or '',
                'options': options
            })

        return decision_points

    def _ensure_option_labels(self, options: List[Dict], question: str, context: str, branch_idx: int) -> List[Dict]:
        """Ensure all options have meaningful labels, generating if needed."""
        if not options:
            # Generate default options
            return self._generate_default_options(question, context, branch_idx)

        fixed_options = []
        for j, opt in enumerate(options):
            label = opt.get('label', '') or ''
            description = opt.get('description', '') or ''

            # If label is empty, generate one
            if not label.strip():
                label, description = self._generate_option_label(
                    question=question,
                    option_index=j,
                    is_board_choice=opt.get('is_board_choice', False),
                    context=context
                )

            fixed_options.append({
                **opt,
                'label': label,
                'description': description
            })

        return fixed_options

    def _generate_option_label(self, question: str, option_index: int, is_board_choice: bool, context: str) -> tuple:
        """Generate a meaningful option label based on context."""
        # Try LLM if available
        client = self._get_llm_client()
        if client:
            try:
                prompt = f"""Generate a concise option label for an ethical decision.

QUESTION: {question}
CONTEXT: {context[:200] if context else 'Professional ethics scenario'}
OPTION: {option_index + 1} of 2
BOARD RECOMMENDED: {is_board_choice}

Generate:
1. Action-oriented label (5-10 words)
2. Brief description (1 sentence)

Format:
LABEL: [label]
DESCRIPTION: [description]"""

                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=100,
                    temperature=0.3,
                    messages=[{"role": "user", "content": prompt}]
                )

                text = response.content[0].text.strip()
                label = desc = ""
                for line in text.split('\n'):
                    if line.startswith('LABEL:'):
                        label = line.replace('LABEL:', '').strip()
                    elif line.startswith('DESCRIPTION:'):
                        desc = line.replace('DESCRIPTION:', '').strip()

                if label:
                    return label, desc

            except Exception as e:
                logger.warning(f"LLM label generation failed: {e}")

        # Fallback labels
        if is_board_choice:
            return "Follow professional obligation", "Prioritize ethical duty as recommended"
        else:
            return "Consider alternative approach", "Explore other options and trade-offs"

    def _generate_default_options(self, question: str, context: str, branch_idx: int) -> List[Dict]:
        """Generate default options when none exist."""
        label1, desc1 = self._generate_option_label(question, 0, True, context)
        label2, desc2 = self._generate_option_label(question, 1, False, context)

        return [
            {
                'option_id': f'opt_{branch_idx}_0',
                'label': label1,
                'description': desc1,
                'is_board_choice': True,
                'action_uris': []
            },
            {
                'option_id': f'opt_{branch_idx}_1',
                'label': label2,
                'description': desc2,
                'is_board_choice': False,
                'action_uris': []
            }
        ]

    def _load_initial_fluents(self, case_id: int) -> List[str]:
        """Load initial fluents from event calculus data."""
        # Try to load from timeline data
        prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='phase4_narrative'
        ).order_by(ExtractionPrompt.created_at.desc()).first()

        if prompt and prompt.raw_response:
            try:
                data = json.loads(prompt.raw_response)
                if 'timeline' in data and 'initial_fluents' in data['timeline']:
                    return [f.get('fluent_expr', f.get('label', ''))
                            for f in data['timeline']['initial_fluents']]
            except (json.JSONDecodeError, TypeError):
                pass

        # Fallback: derive from states
        from sqlalchemy import text
        query = text("""
            SELECT entity_label
            FROM temporary_rdf_storage
            WHERE case_id = :case_id AND entity_type = 'States'
            ORDER BY entity_label
        """)
        results = db.session.execute(query, {"case_id": case_id}).fetchall()

        return [r.entity_label for r in results if r.entity_label]

    def _load_event_calculus_rules(self, case_id: int) -> str:
        """Load event calculus rules for constraint generation."""
        # Try to load from timeline
        prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='phase4_narrative'
        ).order_by(ExtractionPrompt.created_at.desc()).first()

        if prompt and prompt.raw_response:
            try:
                data = json.loads(prompt.raw_response)
                if 'timeline' in data and 'event_trace' in data['timeline']:
                    return data['timeline']['event_trace'][:2000]  # Truncate if too long
            except (json.JSONDecodeError, TypeError):
                pass

        return "No explicit event calculus rules available. Use general causal reasoning."

    def _load_opening_context(self, case_id: int) -> str:
        """Load opening context from scenario seeds."""
        prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='phase4_narrative'
        ).order_by(ExtractionPrompt.created_at.desc()).first()

        if prompt and prompt.raw_response:
            try:
                data = json.loads(prompt.raw_response)
                if 'scenario_seeds' in data:
                    return data['scenario_seeds'].get('opening_context', '')
            except (json.JSONDecodeError, TypeError):
                pass

        return ""


# Singleton instance
interactive_scenario_service = InteractiveScenarioService()
