"""
Case Pipeline Progress Tracking Service

Tracks progress through the ProEthica extraction pipeline by checking
completed extractions in temporary_rdf_storage table.

The temporary_rdf_storage table persists even after entities are committed
to OntServe (is_committed flag changes from false to true), so we can use
it as a reliable source for tracking what steps have been completed.
"""

import logging
from typing import Dict, List, Optional, Set
from sqlalchemy import func, and_, text
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.models import db

logger = logging.getLogger(__name__)


class CasePipelineProgress:
    """
    Track case pipeline progress by checking completed extractions.
    Maps extraction types to pipeline steps.
    """

    # Step requirements: which extraction types must exist for each step
    STEP_REQUIREMENTS = {
        1: {
            'name': 'Contextual Framework',
            'extractions': ['roles', 'states', 'resources'],
            'requires_both_sections': False  # Currently only extracts from one section
        },
        2: {
            'name': 'Normative Requirements',
            'extractions': ['principles', 'obligations', 'constraints', 'capabilities'],
            'requires_both_sections': False  # Currently only extracts from one section
        },
        3: {
            'name': 'Temporal Dynamics',
            'extractions': ['temporal_dynamics_enhanced'],
            'requires_both_sections': False
        },
        4: {
            'name': 'Whole-Case Synthesis',
            'extractions': ['provision', 'question', 'conclusion', 'precedent_case_reference'],
            'requires_all': False  # At least one should be present
        },
        5: {
            'name': 'Scenario Generation',
            'extractions': ['scenario_metadata', 'scenario_timeline', 'scenario_participant'],
            'requires_all': False  # At least one scenario component
        }
    }

    @staticmethod
    def _is_step4_complete(case_id: int) -> bool:
        """
        Check if Step 4 (Whole-Case Synthesis) is complete.

        Step 4 is complete if at least one of the following exists:
        1. Legacy extractions (provision, question, conclusion, precedent)
        2. New Parts D-F (institutional analysis, action mapping, transformation)

        Args:
            case_id: The case document ID

        Returns:
            True if Step 4 is complete
        """
        try:
            # Check legacy extractions first (from temporary_rdf_storage)
            legacy_types = {'provision', 'question', 'conclusion', 'precedent_case_reference'}
            completed_types = CasePipelineProgress.get_completed_extraction_types(case_id)

            if any(ext_type in completed_types for ext_type in legacy_types):
                return True

            # Check new Step 4 Parts D-F tables
            # Part D: Institutional Rule Analysis
            has_part_d = db.session.execute(
                text("SELECT 1 FROM case_institutional_analysis WHERE case_id = :case_id LIMIT 1"),
                {'case_id': case_id}
            ).fetchone() is not None

            # Part E: Action Rule Mapping
            has_part_e = db.session.execute(
                text("SELECT 1 FROM case_action_mapping WHERE case_id = :case_id LIMIT 1"),
                {'case_id': case_id}
            ).fetchone() is not None

            # Part F: Transformation Classification
            has_part_f = db.session.execute(
                text("SELECT 1 FROM case_transformation WHERE case_id = :case_id LIMIT 1"),
                {'case_id': case_id}
            ).fetchone() is not None

            # Step 4 complete if ALL three parts are done
            # (Updated to require all parts for completeness)
            return has_part_d and has_part_e and has_part_f

        except Exception as e:
            logger.error(f"Error checking Step 4 completion for case {case_id}: {e}")
            return False

    @staticmethod
    def get_completed_extraction_types(case_id: int) -> Set[str]:
        """
        Get all extraction types that have been completed for a case.
        Returns a set of extraction type names that have at least one record
        in temporary_rdf_storage (committed or uncommitted).

        Args:
            case_id: The case document ID

        Returns:
            Set of extraction type strings that exist for this case
        """
        try:
            # Query distinct extraction types for this case
            results = db.session.query(
                TemporaryRDFStorage.extraction_type
            ).filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.extraction_type.isnot(None)
            ).distinct().all()

            return {result[0] for result in results if result[0]}

        except Exception as e:
            logger.error(f"Error getting completed extraction types for case {case_id}: {e}")
            return set()

    @staticmethod
    def get_extraction_count(case_id: int, extraction_type: str) -> int:
        """
        Get count of entities for a specific extraction type.

        Args:
            case_id: The case document ID
            extraction_type: The extraction type to count

        Returns:
            Number of entities of this type
        """
        try:
            count = db.session.query(func.count(TemporaryRDFStorage.id)).filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.extraction_type == extraction_type
            ).scalar()

            return count or 0

        except Exception as e:
            logger.error(f"Error counting extraction type {extraction_type} for case {case_id}: {e}")
            return 0

    @staticmethod
    def is_step_complete(case_id: int, step_number: int) -> bool:
        """
        Check if a pipeline step is complete for a case.

        A step is considered complete if at least one of its required
        extraction types has records in temporary_rdf_storage.

        Special case for Step 4: Also checks dedicated tables for Parts D-F
        (case_institutional_analysis, case_action_mapping, case_transformation).

        Args:
            case_id: The case document ID
            step_number: The step number (1-5)

        Returns:
            True if step is complete, False otherwise
        """
        if step_number not in CasePipelineProgress.STEP_REQUIREMENTS:
            logger.warning(f"Unknown step number: {step_number}")
            return False

        # Special handling for Step 4 - check dedicated tables
        if step_number == 4:
            return CasePipelineProgress._is_step4_complete(case_id)

        step_config = CasePipelineProgress.STEP_REQUIREMENTS[step_number]
        required_extractions = step_config['extractions']
        requires_all = step_config.get('requires_all', True)

        completed_types = CasePipelineProgress.get_completed_extraction_types(case_id)

        if requires_all:
            # All required extractions must be present
            return all(ext_type in completed_types for ext_type in required_extractions)
        else:
            # At least one required extraction must be present
            return any(ext_type in completed_types for ext_type in required_extractions)

    @staticmethod
    def get_case_progress(case_id: int) -> Dict[int, Dict]:
        """
        Get comprehensive progress status for all pipeline steps.

        Args:
            case_id: The case document ID

        Returns:
            Dictionary with step numbers as keys and progress details as values:
            {
                1: {
                    'name': 'Contextual Framework',
                    'complete': True,
                    'extractions': {
                        'roles': 12,
                        'states': 15,
                        'resources': 21
                    },
                    'can_proceed': True
                },
                ...
            }
        """
        completed_types = CasePipelineProgress.get_completed_extraction_types(case_id)
        progress = {}

        for step_num, step_config in CasePipelineProgress.STEP_REQUIREMENTS.items():
            # Get counts for each required extraction type
            extraction_counts = {}
            for ext_type in step_config['extractions']:
                if ext_type in completed_types:
                    count = CasePipelineProgress.get_extraction_count(case_id, ext_type)
                    extraction_counts[ext_type] = count
                else:
                    extraction_counts[ext_type] = 0

            # Determine if step is complete
            requires_all = step_config.get('requires_all', True)
            if requires_all:
                is_complete = all(count > 0 for count in extraction_counts.values())
            else:
                is_complete = any(count > 0 for count in extraction_counts.values())

            # Determine if user can proceed to next step
            # Can proceed if this step is complete OR if previous steps are complete
            can_proceed = is_complete
            if step_num > 1:
                # Check if previous step is complete
                prev_step_complete = CasePipelineProgress.is_step_complete(case_id, step_num - 1)
                can_proceed = prev_step_complete and is_complete

            progress[step_num] = {
                'name': step_config['name'],
                'complete': is_complete,
                'extractions': extraction_counts,
                'total_entities': sum(extraction_counts.values()),
                'can_proceed': can_proceed
            }

        return progress

    @staticmethod
    def get_next_available_step(case_id: int) -> int:
        """
        Get the next step that should be completed.
        Returns the first incomplete step, or the last step + 1 if all complete.

        Args:
            case_id: The case document ID

        Returns:
            Step number (1-6, where 6 means all steps complete)
        """
        for step_num in sorted(CasePipelineProgress.STEP_REQUIREMENTS.keys()):
            if not CasePipelineProgress.is_step_complete(case_id, step_num):
                return step_num

        # All steps complete
        return max(CasePipelineProgress.STEP_REQUIREMENTS.keys()) + 1

    @staticmethod
    def can_access_step(case_id: int, step_number: int) -> bool:
        """
        Check if user can access a given step.
        User can access a step if the previous step is complete.

        Args:
            case_id: The case document ID
            step_number: The step to check access for

        Returns:
            True if user can access this step
        """
        # Can always access step 1
        if step_number == 1:
            return True

        # For other steps, check if previous step is complete
        prev_step = step_number - 1
        return CasePipelineProgress.is_step_complete(case_id, prev_step)

    @staticmethod
    def get_progress_summary(case_id: int) -> Dict:
        """
        Get a summary of overall pipeline progress.

        Args:
            case_id: The case document ID

        Returns:
            Summary dictionary with overall stats
        """
        progress = CasePipelineProgress.get_case_progress(case_id)

        total_steps = len(CasePipelineProgress.STEP_REQUIREMENTS)
        completed_steps = sum(1 for step_data in progress.values() if step_data['complete'])
        total_entities = sum(step_data['total_entities'] for step_data in progress.values())

        return {
            'total_steps': total_steps,
            'completed_steps': completed_steps,
            'progress_percentage': round((completed_steps / total_steps) * 100, 1) if total_steps > 0 else 0,
            'total_entities': total_entities,
            'next_step': CasePipelineProgress.get_next_available_step(case_id),
            'is_complete': completed_steps == total_steps,
            'steps': progress
        }
