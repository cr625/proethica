"""
PipelineStateManager: derives per-case pipeline completion state from the
actual data artifacts in the database (artifact counts, extraction-prompt
existence, reconciliation records, published-entity flags).
"""

import logging
from typing import Dict, List, Optional, Any

from .definitions import WORKFLOW_DEFINITION, CheckType, TaskStatus

logger = logging.getLogger(__name__)


class PipelineStateManager:
    """
    Unified state manager that derives state from actual data artifacts.

    Usage:
        manager = PipelineStateManager()
        state = manager.get_pipeline_state(case_id)

        # Check prerequisites
        if state.can_start('step4_qc'):
            # Enable Q&C extraction button

        # Get blockers for tooltip
        blockers = state.get_blockers('step4_transformation')
        # -> ['Questions & Conclusions not complete']
    """

    def __init__(self, db_session=None):
        self._db_session = db_session
        self._artifact_cache: Dict[int, Dict[str, int]] = {}
        self._section_cache: Dict[int, Dict[str, set]] = {}

    @property
    def db(self):
        """Get database session."""
        if self._db_session:
            return self._db_session
        from app import db
        return db.session

    def get_pipeline_state(self, case_id: int) -> 'PipelineState':
        """Get complete pipeline state for a case."""
        from .read_model import PipelineState
        return PipelineState(case_id, self)

    def get_artifact_counts(self, case_id: int) -> Dict[str, int]:
        """
        Get counts of all artifact types for a case. Cached per instance.

        Returns:
            Dict mapping extraction_type to count
        """
        if case_id in self._artifact_cache:
            return self._artifact_cache[case_id]

        from app.models import TemporaryRDFStorage
        from sqlalchemy import func

        try:
            results = self.db.query(
                TemporaryRDFStorage.extraction_type,
                func.count(TemporaryRDFStorage.id)
            ).filter(
                TemporaryRDFStorage.case_id == case_id
            ).group_by(
                TemporaryRDFStorage.extraction_type
            ).all()

            counts = {row[0]: row[1] for row in results}
            self._artifact_cache[case_id] = counts
            return counts

        except Exception as e:
            logger.warning(f"Error getting artifact counts for case {case_id}: {e}")
            return {}

    def get_entity_type_counts(self, case_id: int) -> Dict[str, Dict[str, int]]:
        """
        Get counts grouped by (extraction_type, entity_type). Cached per instance.

        Returns:
            Nested dict: {extraction_type: {entity_type: count}}
        """
        cache_key = f"entity_type_{case_id}"
        if hasattr(self, '_entity_type_cache') and cache_key in self._entity_type_cache:
            return self._entity_type_cache[cache_key]

        from app.models import TemporaryRDFStorage
        from sqlalchemy import func

        if not hasattr(self, '_entity_type_cache'):
            self._entity_type_cache = {}

        try:
            results = self.db.query(
                TemporaryRDFStorage.extraction_type,
                TemporaryRDFStorage.entity_type,
                func.count(TemporaryRDFStorage.id)
            ).filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.entity_type.isnot(None)
            ).group_by(
                TemporaryRDFStorage.extraction_type,
                TemporaryRDFStorage.entity_type
            ).all()

            counts: Dict[str, Dict[str, int]] = {}
            for ext_type, ent_type, count in results:
                counts.setdefault(ext_type, {})[ent_type] = count

            self._entity_type_cache[cache_key] = counts
            return counts

        except Exception as e:
            logger.warning(f"Error getting entity type counts for case {case_id}: {e}")
            return {}

    def _get_section_types(self, case_id: int) -> Dict[str, set]:
        """
        Get which section_types have extraction_prompts for each concept_type.
        Used to distinguish facts vs discussion for Steps 1-2.

        Returns:
            Dict mapping concept_type to set of section_types (e.g. {'role': {'facts', 'discussion'}})
        """
        if case_id in self._section_cache:
            return self._section_cache[case_id]

        from sqlalchemy import text

        try:
            results = self.db.execute(text("""
                SELECT concept_type, section_type
                FROM extraction_prompts
                WHERE case_id = :case_id
                AND section_type IN ('facts', 'discussion')
                GROUP BY concept_type, section_type
            """), {'case_id': case_id}).fetchall()

            sections: Dict[str, set] = {}
            for row in results:
                sections.setdefault(row[0], set()).add(row[1])

            self._section_cache[case_id] = sections
            return sections

        except Exception as e:
            logger.warning(f"Error getting section types for case {case_id}: {e}")
            return {}

    def _check_reconciliation(self, case_id: int) -> bool:
        """Check if reconciliation has been completed for a case.

        Mirrors PipelineStatusService._check_reconcile() backward-compat logic:
        True if ReconciliationRun exists OR entities have been published (for
        cases committed before the reconciliation feature).
        """
        try:
            from app.models.reconciliation_run import ReconciliationRun
            run_exists = ReconciliationRun.query.filter_by(
                case_id=case_id
            ).first() is not None

            if run_exists:
                return True

            # Backward compat: committed entities imply reconciliation was done
            return self._check_published(case_id, published_types=None)

        except Exception as e:
            logger.warning(f"Error checking reconciliation for case {case_id}: {e}")
            return False

    def _check_published(self, case_id: int, published_types: Optional[List[str]] = None) -> bool:
        """Check if entities have been published (is_published=true).

        Args:
            case_id: Case ID
            published_types: If set, only count these extraction_types. None = all types.
        """
        from sqlalchemy import text

        try:
            if published_types:
                result = self.db.execute(text("""
                    SELECT COUNT(*) as count
                    FROM temporary_rdf_storage
                    WHERE case_id = :case_id
                    AND is_published = true
                    AND extraction_type = ANY(:types)
                """), {'case_id': case_id, 'types': published_types}).fetchone()
            else:
                result = self.db.execute(text("""
                    SELECT COUNT(*) as count
                    FROM temporary_rdf_storage
                    WHERE case_id = :case_id
                    AND is_published = true
                """), {'case_id': case_id}).fetchone()

            return (result.count if result else 0) > 0

        except Exception as e:
            logger.warning(f"Error checking published entities for case {case_id}: {e}")
            return False

    def _check_extraction_prompts(self, case_id: int, concept_type_pattern: str) -> bool:
        """Check if extraction prompts exist for a concept_type pattern.

        Args:
            case_id: Case ID
            concept_type_pattern: Exact match or LIKE pattern (if contains %)
        """
        from sqlalchemy import text

        try:
            if '%' in concept_type_pattern:
                result = self.db.execute(text("""
                    SELECT COUNT(*) as count
                    FROM extraction_prompts
                    WHERE case_id = :case_id
                    AND concept_type LIKE :pattern
                """), {'case_id': case_id, 'pattern': concept_type_pattern}).fetchone()
            else:
                result = self.db.execute(text("""
                    SELECT COUNT(*) as count
                    FROM extraction_prompts
                    WHERE case_id = :case_id
                    AND concept_type = :concept_type
                """), {'case_id': case_id, 'concept_type': concept_type_pattern}).fetchone()

            return (result.count if result else 0) > 0

        except Exception as e:
            logger.warning(f"Error checking extraction prompts for case {case_id}: {e}")
            return False

    def invalidate_cache(self, case_id: int = None):
        """Invalidate artifact and section caches. Call after extraction completes."""
        if case_id is None:
            self._artifact_cache.clear()
            self._section_cache.clear()
        else:
            self._artifact_cache.pop(case_id, None)
            self._section_cache.pop(case_id, None)

    def check_task_complete(self, case_id: int, step: str, task: str) -> bool:
        """
        Check if a task has produced required artifacts.

        Dispatches to the appropriate check based on the task's check_type,
        with section-awareness when the parent step has a section_type.
        """
        step_def = WORKFLOW_DEFINITION.get(step)
        if not step_def:
            return False

        task_def = next((t for t in step_def.tasks if t.name == task), None)
        if not task_def:
            return False

        effective_check = task_def.check_type

        if effective_check == CheckType.RECONCILIATION_RUN:
            return self._check_reconciliation(case_id)

        if effective_check == CheckType.PUBLISHED_ENTITIES:
            return self._check_published(case_id, step_def.published_types)

        if effective_check == CheckType.EXTRACTION_PROMPTS:
            # Narrative uses phase4% pattern
            pattern = task_def.prompt_concept_type
            if pattern == 'phase4_narrative':
                pattern = 'phase4%'
            return self._check_extraction_prompts(case_id, pattern)

        # Default: ARTIFACTS check
        counts = self.get_artifact_counts(case_id)
        total_artifacts = sum(counts.get(atype, 0) for atype in task_def.artifact_types)

        if total_artifacts < task_def.min_artifacts:
            return False

        # Section-aware: if step has a section_type, verify extraction_prompts
        # exist for that section. This distinguishes pass1_facts from pass1_discussion
        # since both produce the same extraction_types in temporary_rdf_storage.
        # Uses the CURRENT TASK's artifact_types (plural: 'roles') which match
        # extraction_prompts.concept_type, NOT prompt_concept_type (singular: 'role').
        if step_def.section_type:
            sections = self._get_section_types(case_id)
            has_section = any(
                step_def.section_type in sections.get(ct, set())
                for ct in task_def.artifact_types
            )
            if not has_section:
                return False

        return True

    def check_step_complete(self, case_id: int, step: str) -> bool:
        """Check if all tasks in a step are complete."""
        step_def = WORKFLOW_DEFINITION.get(step)
        if not step_def:
            return False

        return all(
            self.check_task_complete(case_id, step, task.name)
            for task in step_def.tasks
        )

    def check_prerequisites_met(
        self,
        case_id: int,
        step: str,
        task: str = None
    ) -> tuple[bool, List[str]]:
        """
        Check if prerequisites are met to start a step/task.

        Returns:
            Tuple of (can_start, list_of_missing_prerequisites)
        """
        missing = []
        step_def = WORKFLOW_DEFINITION.get(step)

        if not step_def:
            return False, [f"Unknown step: {step}"]

        # Check step-level prerequisites
        for prereq_step in step_def.prerequisites:
            if not self.check_step_complete(case_id, prereq_step):
                prereq_def = WORKFLOW_DEFINITION.get(prereq_step)
                prereq_name = prereq_def.display_name if prereq_def else prereq_step
                missing.append(f"{prereq_name} not complete")

        # Check task-level prerequisites (within the same step)
        if task:
            task_def = next((t for t in step_def.tasks if t.name == task), None)
            if task_def and task_def.prerequisites:
                for prereq_task in task_def.prerequisites:
                    if not self.check_task_complete(case_id, step, prereq_task):
                        prereq_task_def = next(
                            (t for t in step_def.tasks if t.name == prereq_task), None
                        )
                        prereq_name = prereq_task_def.display_name if prereq_task_def else prereq_task
                        missing.append(f"{prereq_name} not complete")

        return (len(missing) == 0, missing)

    def get_step_status(self, case_id: int, step: str) -> TaskStatus:
        """Get overall status of a step."""
        step_def = WORKFLOW_DEFINITION.get(step)
        if not step_def:
            return TaskStatus.NOT_STARTED

        complete_count = sum(
            1 for task in step_def.tasks
            if self.check_task_complete(case_id, step, task.name)
        )

        if complete_count == 0:
            return TaskStatus.NOT_STARTED
        elif complete_count == len(step_def.tasks):
            return TaskStatus.COMPLETE
        else:
            return TaskStatus.IN_PROGRESS

    def get_step_progress(self, case_id: int, step: str) -> Dict[str, Any]:
        """Get detailed progress for a step."""
        step_def = WORKFLOW_DEFINITION.get(step)
        if not step_def:
            return {'error': f'Unknown step: {step}'}

        tasks_complete = sum(
            1 for task in step_def.tasks
            if self.check_task_complete(case_id, step, task.name)
        )
        total_tasks = len(step_def.tasks)

        return {
            'step': step,
            'display_name': step_def.display_name,
            'tasks_complete': tasks_complete,
            'tasks_total': total_tasks,
            'percentage': int((tasks_complete / total_tasks) * 100) if total_tasks > 0 else 0,
            'status': self.get_step_status(case_id, step).value,
        }

    def check_step4_complete(self, case_id: int) -> bool:
        """Check if all Step 4 substeps are complete.

        Convenience method for callers that need to know if the entire
        Case Analysis phase is done (replaces the old single 'step4' entry).
        """
        step4_substeps = [
            name for name, defn in WORKFLOW_DEFINITION.items()
            if defn.step_group == 'Case Analysis'
        ]
        return all(self.check_step_complete(case_id, s) for s in step4_substeps)
