"""
Pipeline Status Service

Provides step completion status for the scenario pipeline.
Used by the UI to show which steps are complete and which are available.
"""

from typing import Dict, Any
from sqlalchemy import text
from app import db
import logging

logger = logging.getLogger(__name__)


class PipelineStatusService:
    """Service to check pipeline step completion status for a case."""

    # Pass 1 entity types (Contextual Framework)
    PASS1_TYPES = ['roles', 'states', 'resources']

    # Pass 2 entity types (Normative Requirements)
    PASS2_TYPES = ['principles', 'obligations', 'constraints', 'capabilities']

    # Pass 3 entity types (Temporal Dynamics)
    # Note: 'temporal_dynamics_enhanced' is the extraction_type used by the enhanced step3 extraction
    PASS3_TYPES = ['actions', 'events', 'actions_events', 'temporal_dynamics_enhanced']

    @classmethod
    def get_step_status(cls, case_id: int) -> Dict[str, Any]:
        """
        Get completion status for all pipeline steps.

        Returns:
            Dictionary with step completion info:
            {
                'step1': {'complete': bool, 'entity_count': int},
                'step2': {'complete': bool, 'entity_count': int},
                'step3': {'complete': bool, 'entity_count': int},
                'step4': {'complete': bool, 'has_provisions': bool, 'has_qa': bool},
                'step5': {'complete': bool, 'has_scenario': bool}
            }
        """
        try:
            status = {
                'step1': cls._check_step1(case_id),
                'step2': cls._check_step2(case_id),
                'step3': cls._check_step3(case_id),
                'step4': cls._check_step4(case_id),
                'step5': cls._check_step5(case_id),
            }
            return status
        except Exception as e:
            logger.error(f"Error getting pipeline status for case {case_id}: {e}")
            return {
                'step1': {'complete': False, 'entity_count': 0},
                'step2': {'complete': False, 'entity_count': 0},
                'step3': {'complete': False, 'entity_count': 0},
                'step4': {'complete': False, 'has_provisions': False, 'has_qa': False},
                'step5': {'complete': False, 'has_scenario': False},
            }

    @classmethod
    def _check_step1(cls, case_id: int) -> Dict[str, Any]:
        """Check if Step 1 (Contextual Framework) has been run.

        Also tracks section-level completion (facts vs discussion).
        """
        # Overall count
        query = text("""
            SELECT COUNT(*) as count
            FROM temporary_rdf_storage
            WHERE case_id = :case_id
            AND extraction_type IN :types
        """)
        result = db.session.execute(
            query,
            {'case_id': case_id, 'types': tuple(cls.PASS1_TYPES)}
        ).fetchone()
        count = result.count if result else 0

        # Facts section count (section_type is stored in provenance_metadata JSONB)
        facts_query = text("""
            SELECT COUNT(*) as count
            FROM temporary_rdf_storage
            WHERE case_id = :case_id
            AND extraction_type IN :types
            AND provenance_metadata->>'section_type' = 'facts'
        """)
        facts_result = db.session.execute(
            facts_query,
            {'case_id': case_id, 'types': tuple(cls.PASS1_TYPES)}
        ).fetchone()
        facts_count = facts_result.count if facts_result else 0

        # Discussion section count
        discussion_query = text("""
            SELECT COUNT(*) as count
            FROM temporary_rdf_storage
            WHERE case_id = :case_id
            AND extraction_type IN :types
            AND provenance_metadata->>'section_type' = 'discussion'
        """)
        discussion_result = db.session.execute(
            discussion_query,
            {'case_id': case_id, 'types': tuple(cls.PASS1_TYPES)}
        ).fetchone()
        discussion_count = discussion_result.count if discussion_result else 0

        return {
            'complete': count > 0,
            'entity_count': count,
            'facts_complete': facts_count > 0,
            'facts_count': facts_count,
            'discussion_complete': discussion_count > 0,
            'discussion_count': discussion_count
        }

    @classmethod
    def _check_step2(cls, case_id: int) -> Dict[str, Any]:
        """Check if Step 2 (Normative Requirements) has been run.

        Also tracks section-level completion (facts vs discussion).
        Note: For backwards compatibility, NULL section_type is treated as 'facts'
        since older extractions didn't track section_type.
        """
        # Overall count
        query = text("""
            SELECT COUNT(*) as count
            FROM temporary_rdf_storage
            WHERE case_id = :case_id
            AND extraction_type IN :types
        """)
        result = db.session.execute(
            query,
            {'case_id': case_id, 'types': tuple(cls.PASS2_TYPES)}
        ).fetchone()
        count = result.count if result else 0

        # Facts section count (section_type is stored in provenance_metadata JSONB)
        # Treat NULL section_type as 'facts' for backwards compatibility
        facts_query = text("""
            SELECT COUNT(*) as count
            FROM temporary_rdf_storage
            WHERE case_id = :case_id
            AND extraction_type IN :types
            AND (provenance_metadata->>'section_type' = 'facts'
                 OR provenance_metadata->>'section_type' IS NULL)
        """)
        facts_result = db.session.execute(
            facts_query,
            {'case_id': case_id, 'types': tuple(cls.PASS2_TYPES)}
        ).fetchone()
        facts_count = facts_result.count if facts_result else 0

        # Discussion section count
        discussion_query = text("""
            SELECT COUNT(*) as count
            FROM temporary_rdf_storage
            WHERE case_id = :case_id
            AND extraction_type IN :types
            AND provenance_metadata->>'section_type' = 'discussion'
        """)
        discussion_result = db.session.execute(
            discussion_query,
            {'case_id': case_id, 'types': tuple(cls.PASS2_TYPES)}
        ).fetchone()
        discussion_count = discussion_result.count if discussion_result else 0

        return {
            'complete': count > 0,
            'entity_count': count,
            'facts_complete': facts_count > 0,
            'facts_count': facts_count,
            'discussion_complete': discussion_count > 0,
            'discussion_count': discussion_count
        }

    @classmethod
    def _check_step3(cls, case_id: int) -> Dict[str, Any]:
        """Check if Step 3 (Temporal Dynamics) has been run."""
        query = text("""
            SELECT COUNT(*) as count
            FROM temporary_rdf_storage
            WHERE case_id = :case_id
            AND extraction_type IN :types
        """)
        result = db.session.execute(
            query,
            {'case_id': case_id, 'types': tuple(cls.PASS3_TYPES)}
        ).fetchone()

        count = result.count if result else 0
        return {
            'complete': count > 0,
            'entity_count': count
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
