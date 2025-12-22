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

    # Step 4 Phase 2 concept types (Analytical Extraction)
    # These match the actual concept_type values saved in extraction_prompts
    STEP4_PHASE2_TYPES = (
        'code_provision_reference',  # 2A provisions
        'ethical_question',          # 2B questions
        'ethical_conclusion',        # 2B conclusions
        'transformation_classification',  # 2C transformation
        'rich_analysis'              # 2D rich analysis
    )

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
                'step1': {'complete': False, 'facts_complete': False, 'discussion_complete': False, 'questions_complete': False, 'conclusions_complete': False},
                'step2': {'complete': False, 'facts_complete': False, 'discussion_complete': False, 'questions_complete': False, 'conclusions_complete': False},
                'step3': {'complete': False},
                'step4': {'complete': False, 'phase2_complete': False, 'phase2_tasks_done': 0, 'phase3_complete': False, 'phase4_complete': False},
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

        # Questions section - join to prompts to get section_type
        questions_query = text("""
            SELECT COUNT(DISTINCT r.id) as count
            FROM temporary_rdf_storage r
            JOIN extraction_prompts p ON r.extraction_session_id = p.extraction_session_id
            WHERE r.case_id = :case_id
            AND r.extraction_type IN :types
            AND p.section_type = 'questions'
        """)
        questions_result = db.session.execute(
            questions_query,
            {'case_id': case_id, 'types': extraction_types}
        ).fetchone()
        questions_count = questions_result.count if questions_result else 0

        # Conclusions section - join to prompts to get section_type
        conclusions_query = text("""
            SELECT COUNT(DISTINCT r.id) as count
            FROM temporary_rdf_storage r
            JOIN extraction_prompts p ON r.extraction_session_id = p.extraction_session_id
            WHERE r.case_id = :case_id
            AND r.extraction_type IN :types
            AND p.section_type = 'conclusions'
        """)
        conclusions_result = db.session.execute(
            conclusions_query,
            {'case_id': case_id, 'types': extraction_types}
        ).fetchone()
        conclusions_count = conclusions_result.count if conclusions_result else 0

        return {
            'complete': total_count > 0,
            'facts_complete': facts_count > 0,
            'discussion_complete': discussion_count > 0,
            'questions_complete': questions_count > 0,
            'conclusions_complete': conclusions_count > 0
        }

    @classmethod
    def _check_step4(cls, case_id: int) -> Dict[str, Any]:
        """Check if Step 4 (Whole-Case Synthesis) phases have been run.

        Checks:
        - Phase 2: Analytical Extraction (provisions, questions, conclusions, transformation, rich_analysis)
        - Phase 3: Decision Point Synthesis (canonical_decision_point entities)
        - Phase 4: Narrative Construction (phase4 prompts)
        """
        phase2_complete = False
        phase3_complete = False
        phase4_complete = False
        phase2_tasks_done = 0

        # Check Phase 2: extraction_prompts for each concept_type
        # Core tasks that indicate Phase 2 completion: transformation_classification and rich_analysis
        try:
            phase2_query = text("""
                SELECT COUNT(DISTINCT concept_type) as count
                FROM extraction_prompts
                WHERE case_id = :case_id
                AND concept_type IN :types
                AND prompt_text IS NOT NULL
            """)
            phase2_result = db.session.execute(
                phase2_query,
                {'case_id': case_id, 'types': cls.STEP4_PHASE2_TYPES}
            ).fetchone()
            phase2_tasks_done = phase2_result.count if phase2_result else 0

            # Check core tasks (2C transformation + 2D rich_analysis = Phase 2 done)
            core_types = ('transformation_classification', 'rich_analysis')
            core_query = text("""
                SELECT COUNT(DISTINCT concept_type) as count
                FROM extraction_prompts
                WHERE case_id = :case_id
                AND concept_type IN :types
                AND prompt_text IS NOT NULL
            """)
            core_result = db.session.execute(
                core_query,
                {'case_id': case_id, 'types': core_types}
            ).fetchone()
            core_tasks_done = core_result.count if core_result else 0
            phase2_complete = core_tasks_done == len(core_types)
        except Exception:
            db.session.rollback()

        # Check Phase 3: canonical_decision_point entities
        try:
            phase3_query = text("""
                SELECT COUNT(*) as count
                FROM temporary_rdf_storage
                WHERE case_id = :case_id
                AND extraction_type = 'canonical_decision_point'
            """)
            phase3_result = db.session.execute(
                phase3_query,
                {'case_id': case_id}
            ).fetchone()
            phase3_complete = (phase3_result.count if phase3_result else 0) > 0
        except Exception:
            db.session.rollback()

        # Check Phase 4: narrative elements (check extraction_prompts for phase4 types)
        try:
            phase4_query = text("""
                SELECT COUNT(*) as count
                FROM extraction_prompts
                WHERE case_id = :case_id
                AND concept_type LIKE 'phase4%%'
            """)
            phase4_result = db.session.execute(
                phase4_query,
                {'case_id': case_id}
            ).fetchone()
            phase4_complete = (phase4_result.count if phase4_result else 0) > 0
        except Exception:
            db.session.rollback()

        return {
            # Step 4 complete when Phase 4 done (narrative construction ready for Step 5)
            # OR when Phase 2+3 both done (legacy completeness check)
            'complete': phase4_complete or (phase2_complete and phase3_complete),
            'phase2_complete': phase2_complete,
            'phase2_tasks_done': phase2_tasks_done,
            'phase3_complete': phase3_complete,
            'phase4_complete': phase4_complete
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

    @classmethod
    def get_simple_status(cls, case_id: int) -> str:
        """
        Get a simple status string for display in case listings.

        Returns:
            'synthesized' - Step 4 complete
            'extracted' - Passes 1-3 have some entities
            'not_started' - No extraction done
        """
        status = cls.get_step_status(case_id)

        # Check Step 4 completion (synthesis)
        if status.get('step4', {}).get('complete', False):
            return 'synthesized'

        # Check if any extraction has been done (Steps 1-3)
        if (status.get('step1', {}).get('complete', False) or
            status.get('step2', {}).get('complete', False) or
            status.get('step3', {}).get('complete', False)):
            return 'extracted'

        return 'not_started'

    @classmethod
    def get_bulk_simple_status(cls, case_ids: list) -> dict:
        """
        Get simple status for multiple cases efficiently.

        Uses bulk queries to avoid N+1 problem.

        Returns:
            Dict mapping case_id to status string
        """
        if not case_ids:
            return {}

        result = {cid: 'not_started' for cid in case_ids}

        try:
            # Check for Step 4 synthesis completion
            # Check for either whole_case_synthesis OR phase4_narrative (Phase 4 complete)
            synthesis_query = text("""
                SELECT DISTINCT case_id
                FROM extraction_prompts
                WHERE case_id = ANY(:case_ids)
                AND (concept_type = 'whole_case_synthesis' OR concept_type LIKE 'phase4%%')
            """)
            synthesis_result = db.session.execute(
                synthesis_query,
                {'case_ids': case_ids}
            )
            for row in synthesis_result:
                result[row[0]] = 'synthesized'

            # Check for extraction (has RDF entities)
            extraction_query = text("""
                SELECT DISTINCT case_id
                FROM temporary_rdf_storage
                WHERE case_id = ANY(:case_ids)
            """)
            extraction_result = db.session.execute(
                extraction_query,
                {'case_ids': case_ids}
            )
            for row in extraction_result:
                # Only upgrade to 'extracted' if not already 'synthesized'
                if result.get(row[0]) == 'not_started':
                    result[row[0]] = 'extracted'

        except Exception as e:
            logger.error(f"Error getting bulk status: {e}")

        return result
