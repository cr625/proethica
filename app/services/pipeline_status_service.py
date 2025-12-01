"""
Pipeline Status Service

Provides step completion status for the scenario pipeline.
Used by the UI to show which steps are complete and which are available.

Hybrid approach:
- Checks for RDF entities (confirms extraction succeeded, not just attempted)
- Joins to ExtractionPrompt via extraction_session_id to get section_type
"""

from typing import Dict, Any
from sqlalchemy import text
from app import db
import logging

logger = logging.getLogger(__name__)


class PipelineStatusService:
    """Service to check pipeline step completion status for a case.

    Checks for actual RDF entities (not just prompts) to confirm extraction succeeded.
    Uses extraction_session_id linkage to prompts to determine section_type.
    """

    # Step 1 entity types (Contextual Framework)
    STEP1_TYPES = ('roles', 'states', 'resources')

    # Step 2 entity types (Normative Requirements)
    STEP2_TYPES = ('principles', 'obligations', 'constraints', 'capabilities')

    # Step 3 entity types (Temporal Dynamics)
    STEP3_TYPES = ('actions', 'events', 'actions_events', 'temporal_dynamics_enhanced')

    @classmethod
    def get_step_status(cls, case_id: int) -> Dict[str, Any]:
        """
        Get completion status for all pipeline steps.

        Returns:
            Dictionary with step completion info:
            {
                'step1': {'complete': bool, 'facts_complete': bool, 'discussion_complete': bool},
                'step2': {'complete': bool, 'facts_complete': bool, 'discussion_complete': bool},
                'step3': {'complete': bool},
                'step4': {'complete': bool, 'has_provisions': bool, 'has_qa': bool},
                'step5': {'complete': bool, 'has_scenario': bool}
            }
        """
        try:
            status = {
                'step1': cls._check_extraction_step(case_id, cls.STEP1_TYPES),
                'step2': cls._check_extraction_step(case_id, cls.STEP2_TYPES),
                'step3': cls._check_extraction_step(case_id, cls.STEP3_TYPES),
                'step4': cls._check_step4(case_id),
                'step5': cls._check_step5(case_id),
            }
            return status
        except Exception as e:
            logger.error(f"Error getting pipeline status for case {case_id}: {e}")
            return {
                'step1': {'complete': False, 'facts_complete': False, 'discussion_complete': False},
                'step2': {'complete': False, 'facts_complete': False, 'discussion_complete': False},
                'step3': {'complete': False},
                'step4': {'complete': False, 'has_provisions': False, 'has_qa': False},
                'step5': {'complete': False, 'has_scenario': False},
            }

    @classmethod
    def _check_extraction_step(cls, case_id: int, extraction_types: tuple) -> Dict[str, Any]:
        """Check if an extraction step has completed by looking for RDF entities.

        Uses entity existence (not just prompts) to confirm extraction succeeded.
        Joins to prompts via extraction_session_id to get reliable section_type.
        """
        # Overall count - do we have any entities for this step?
        total_query = text("""
            SELECT COUNT(*) as count
            FROM temporary_rdf_storage
            WHERE case_id = :case_id
            AND extraction_type IN :types
        """)
        total_result = db.session.execute(
            total_query,
            {'case_id': case_id, 'types': extraction_types}
        ).fetchone()
        total_count = total_result.count if total_result else 0

        # Facts section - join to prompts to get section_type
        facts_query = text("""
            SELECT COUNT(DISTINCT r.id) as count
            FROM temporary_rdf_storage r
            JOIN extraction_prompts p ON r.extraction_session_id = p.extraction_session_id
            WHERE r.case_id = :case_id
            AND r.extraction_type IN :types
            AND p.section_type = 'facts'
        """)
        facts_result = db.session.execute(
            facts_query,
            {'case_id': case_id, 'types': extraction_types}
        ).fetchone()
        facts_count = facts_result.count if facts_result else 0

        # Discussion section - join to prompts to get section_type
        discussion_query = text("""
            SELECT COUNT(DISTINCT r.id) as count
            FROM temporary_rdf_storage r
            JOIN extraction_prompts p ON r.extraction_session_id = p.extraction_session_id
            WHERE r.case_id = :case_id
            AND r.extraction_type IN :types
            AND p.section_type = 'discussion'
        """)
        discussion_result = db.session.execute(
            discussion_query,
            {'case_id': case_id, 'types': extraction_types}
        ).fetchone()
        discussion_count = discussion_result.count if discussion_result else 0

        return {
            'complete': total_count > 0,
            'facts_complete': facts_count > 0,
            'discussion_complete': discussion_count > 0
        }

    @classmethod
    def _check_step4(cls, case_id: int) -> Dict[str, Any]:
        """Check if Step 4 (Whole-Case Synthesis) has been run."""
        has_provisions = False
        has_qa = False

        # Check for provisions (table may not exist yet)
        try:
            provisions_query = text("""
                SELECT COUNT(*) as count
                FROM case_provisions
                WHERE case_id = :case_id
            """)
            provisions_result = db.session.execute(
                provisions_query,
                {'case_id': case_id}
            ).fetchone()
            has_provisions = (provisions_result.count if provisions_result else 0) > 0
        except Exception:
            db.session.rollback()  # Clear invalid session state

        # Check for Q&A analysis (table may not exist yet)
        try:
            qa_query = text("""
                SELECT COUNT(*) as count
                FROM case_question_answer
                WHERE case_id = :case_id
            """)
            qa_result = db.session.execute(
                qa_query,
                {'case_id': case_id}
            ).fetchone()
            has_qa = (qa_result.count if qa_result else 0) > 0
        except Exception:
            db.session.rollback()  # Clear invalid session state

        return {
            'complete': has_provisions or has_qa,
            'has_provisions': has_provisions,
            'has_qa': has_qa
        }

    @classmethod
    def _check_step5(cls, case_id: int) -> Dict[str, Any]:
        """Check if Step 5 (Scenario Generation) has been run."""
        # Check for generated scenario
        scenario_query = text("""
            SELECT COUNT(*) as count
            FROM scenario_participants
            WHERE case_id = :case_id
        """)
        try:
            scenario_result = db.session.execute(
                scenario_query,
                {'case_id': case_id}
            ).fetchone()
            has_scenario = (scenario_result.count if scenario_result else 0) > 0
        except Exception:
            # Table might not exist yet
            has_scenario = False

        return {
            'complete': has_scenario,
            'has_scenario': has_scenario
        }

    @classmethod
    def is_step_available(cls, case_id: int, step_number: int) -> bool:
        """
        Check if a step is available (previous step complete or first step).

        Args:
            case_id: The case ID
            step_number: Step number (1-5)

        Returns:
            True if the step is available to run
        """
        if step_number <= 1:
            return True

        status = cls.get_step_status(case_id)
        prev_step_key = f'step{step_number - 1}'
        return status.get(prev_step_key, {}).get('complete', False)
