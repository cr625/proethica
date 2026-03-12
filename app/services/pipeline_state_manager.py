"""
Pipeline State Manager - Data-Driven State for Extraction Pipeline

Derives pipeline completion state from actual data artifacts in the database.
Each of the 15 pipeline substeps has a defined completion check (artifact counts,
extraction prompt existence, reconciliation records, or published entity flags).

Usage:
    from app.services.pipeline_state_manager import PipelineStateManager, get_pipeline_state

    # Quick access
    state = get_pipeline_state(case_id)
    if state.can_start('step4_qc'):
        enable_button()

    # Full API
    manager = PipelineStateManager()
    state = manager.get_pipeline_state(case_id)
    full_state = state.to_dict()  # For API/template
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of a pipeline substep."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"  # Some artifacts exist
    COMPLETE = "complete"        # All required artifacts exist
    ERROR = "error"              # Task failed (future use)
    SKIPPED = "skipped"          # Task intentionally skipped (future use)


class CheckType(Enum):
    """How to determine if a substep is complete."""
    ARTIFACTS = "artifacts"
    EXTRACTION_PROMPTS = "extraction_prompts"
    RECONCILIATION_RUN = "reconciliation_run"
    PUBLISHED_ENTITIES = "published_entities"


@dataclass
class TaskDefinition:
    """
    A single extractable unit within a workflow step.

    Attributes:
        name: Unique task identifier within the step
        display_name: Human-readable name for UI
        artifact_types: Entity types to check in temporary_rdf_storage
        prompt_concept_type: concept_type in extraction_prompts (for provenance link)
        prerequisites: Other tasks that must complete first (within same step)
        min_artifacts: Minimum number of artifacts required for completion (default: 1)
        check_type: How to verify completion (default: count artifacts)
    """
    name: str
    display_name: str
    artifact_types: List[str]
    prompt_concept_type: str
    prerequisites: List[str] = field(default_factory=list)
    min_artifacts: int = 1
    check_type: CheckType = CheckType.ARTIFACTS


@dataclass
class WorkflowStepDefinition:
    """
    A substep in the pipeline workflow. Each substep contains one or more tasks
    (individual concept types) that are extracted together.

    Attributes:
        name: Unique step identifier (used as dict key in WORKFLOW_DEFINITION)
        display_name: Human-readable name for UI
        tasks: List of tasks in this step (concept-level breakdown for badges)
        prerequisites: Other steps that must complete first (step-level deps)
        step_group: Visual grouping for UI layout
        section_type: 'facts', 'discussion', or None (for section-aware checks)
        check_type: Step-level completion check type (overrides task-level for
                     steps that use non-artifact checks like reconciliation)
        published_types: For PUBLISHED_ENTITIES check_type, which extraction_types
                         to filter on. None means all types.
    """
    name: str
    display_name: str
    tasks: List[TaskDefinition]
    prerequisites: List[str] = field(default_factory=list)
    step_group: str = ""
    section_type: Optional[str] = None
    check_type: CheckType = CheckType.ARTIFACTS
    published_types: Optional[List[str]] = None


# Complete 15-substep pipeline definition.
#
# IMPORTANT: artifact_types must match EXACTLY the extraction_type values
# stored in temporary_rdf_storage. Check with:
#   SELECT DISTINCT extraction_type FROM temporary_rdf_storage;
#
WORKFLOW_DEFINITION: Dict[str, WorkflowStepDefinition] = {
    # --- Pass 1: Contextual Framework (R, S, Rs) ---
    'pass1_facts': WorkflowStepDefinition(
        name='pass1_facts',
        display_name='Pass 1 - Facts',
        step_group='Pass 1',
        section_type='facts',
        tasks=[
            TaskDefinition('roles', 'Roles', ['roles'], 'role'),
            TaskDefinition('states', 'States', ['states'], 'state'),
            TaskDefinition('resources', 'Resources', ['resources'], 'resource'),
        ],
        prerequisites=[],
    ),
    'pass1_discussion': WorkflowStepDefinition(
        name='pass1_discussion',
        display_name='Pass 1 - Discussion',
        step_group='Pass 1',
        section_type='discussion',
        tasks=[
            TaskDefinition('roles', 'Roles', ['roles'], 'role'),
            TaskDefinition('states', 'States', ['states'], 'state'),
            TaskDefinition('resources', 'Resources', ['resources'], 'resource'),
        ],
        prerequisites=['pass1_facts'],
    ),

    # --- Pass 2: Normative Requirements (P, O, Cs, Ca) ---
    'pass2_facts': WorkflowStepDefinition(
        name='pass2_facts',
        display_name='Pass 2 - Facts',
        step_group='Pass 2',
        section_type='facts',
        tasks=[
            TaskDefinition('principles', 'Principles', ['principles'], 'principle'),
            TaskDefinition('obligations', 'Obligations', ['obligations'], 'obligation'),
            TaskDefinition('constraints', 'Constraints', ['constraints'], 'constraint'),
            TaskDefinition('capabilities', 'Capabilities', ['capabilities'], 'capability'),
        ],
        prerequisites=['pass1_facts'],
    ),
    'pass2_discussion': WorkflowStepDefinition(
        name='pass2_discussion',
        display_name='Pass 2 - Discussion',
        step_group='Pass 2',
        section_type='discussion',
        tasks=[
            TaskDefinition('principles', 'Principles', ['principles'], 'principle'),
            TaskDefinition('obligations', 'Obligations', ['obligations'], 'obligation'),
            TaskDefinition('constraints', 'Constraints', ['constraints'], 'constraint'),
            TaskDefinition('capabilities', 'Capabilities', ['capabilities'], 'capability'),
        ],
        prerequisites=['pass1_discussion', 'pass2_facts'],
    ),

    # --- Pass 3: Temporal Dynamics (A, E) ---
    'pass3': WorkflowStepDefinition(
        name='pass3',
        display_name='Pass 3 - Temporal',
        step_group='Pass 3',
        tasks=[
            TaskDefinition('temporal', 'Actions & Events', ['temporal_dynamics_enhanced'], 'temporal'),
        ],
        prerequisites=['pass2_facts', 'pass2_discussion'],
    ),

    # --- Reconcile & Commit ---
    'reconcile': WorkflowStepDefinition(
        name='reconcile',
        display_name='Reconcile',
        step_group='Reconcile & Commit',
        check_type=CheckType.RECONCILIATION_RUN,
        tasks=[
            TaskDefinition('reconcile', 'Entity Reconciliation', [], 'reconciliation',
                           check_type=CheckType.RECONCILIATION_RUN),
        ],
        prerequisites=['pass3'],
    ),
    'commit_extraction': WorkflowStepDefinition(
        name='commit_extraction',
        display_name='Commit Entities',
        step_group='Reconcile & Commit',
        check_type=CheckType.PUBLISHED_ENTITIES,
        tasks=[
            TaskDefinition('commit', 'Publish to OntServe', [], 'commit',
                           check_type=CheckType.PUBLISHED_ENTITIES),
        ],
        prerequisites=['reconcile'],
    ),

    # --- Step 4: Case Analysis (7 substeps) ---
    'step4_provisions': WorkflowStepDefinition(
        name='step4_provisions',
        display_name='Provisions',
        step_group='Case Analysis',
        tasks=[
            TaskDefinition('provisions', 'Code Provisions', ['code_provision_reference'], 'code_provision'),
        ],
        prerequisites=['commit_extraction'],
    ),
    'step4_precedents': WorkflowStepDefinition(
        name='step4_precedents',
        display_name='Precedents',
        step_group='Case Analysis',
        tasks=[
            TaskDefinition('precedents', 'Precedent Cases', ['precedent_case_reference'], 'precedent_case'),
        ],
        prerequisites=['step4_provisions'],
    ),
    'step4_qc': WorkflowStepDefinition(
        name='step4_qc',
        display_name='Questions & Conclusions',
        step_group='Case Analysis',
        tasks=[
            TaskDefinition('questions', 'Ethical Questions', ['ethical_question'], 'ethical_question'),
            TaskDefinition('conclusions', 'Board Conclusions', ['ethical_conclusion'], 'ethical_conclusion'),
        ],
        prerequisites=['step4_provisions'],
    ),
    'step4_transformation': WorkflowStepDefinition(
        name='step4_transformation',
        display_name='Transformation',
        step_group='Case Analysis',
        check_type=CheckType.EXTRACTION_PROMPTS,
        tasks=[
            TaskDefinition('transformation', 'Transformation Classification',
                           [], 'transformation_classification',
                           check_type=CheckType.EXTRACTION_PROMPTS, min_artifacts=0),
        ],
        prerequisites=['step4_qc'],
    ),
    'step4_rich_analysis': WorkflowStepDefinition(
        name='step4_rich_analysis',
        display_name='Rich Analysis',
        step_group='Case Analysis',
        tasks=[
            TaskDefinition('causal_links', 'Causal-Normative Links',
                           ['causal_normative_link'], 'rich_analysis'),
            TaskDefinition('question_emergence', 'Question Emergence',
                           ['question_emergence'], 'rich_analysis'),
            TaskDefinition('resolution_patterns', 'Resolution Patterns',
                           ['resolution_pattern'], 'rich_analysis'),
        ],
        prerequisites=['step4_transformation'],
    ),
    'step4_phase3': WorkflowStepDefinition(
        name='step4_phase3',
        display_name='Decision Points',
        step_group='Case Analysis',
        tasks=[
            TaskDefinition('decision_points', 'Canonical Decision Points',
                           ['canonical_decision_point'], 'phase3_decision_synthesis'),
        ],
        prerequisites=['step4_rich_analysis'],
    ),
    'step4_phase4': WorkflowStepDefinition(
        name='step4_phase4',
        display_name='Narrative',
        step_group='Case Analysis',
        check_type=CheckType.EXTRACTION_PROMPTS,
        tasks=[
            TaskDefinition('narrative', 'Narrative Construction', [], 'phase4_narrative',
                           check_type=CheckType.EXTRACTION_PROMPTS, min_artifacts=0),
        ],
        prerequisites=['step4_phase3'],
    ),

    # --- Publish ---
    'commit_synthesis': WorkflowStepDefinition(
        name='commit_synthesis',
        display_name='Commit Synthesis',
        step_group='Publish',
        check_type=CheckType.PUBLISHED_ENTITIES,
        published_types=[
            'code_provision_reference', 'precedent_case_reference',
            'ethical_question', 'ethical_conclusion',
            'transformation_result', 'causal_normative_link',
            'question_emergence', 'resolution_pattern',
            'canonical_decision_point',
        ],
        tasks=[
            TaskDefinition('commit_synthesis', 'Publish Analysis to OntServe', [], 'commit_synthesis',
                           check_type=CheckType.PUBLISHED_ENTITIES),
        ],
        prerequisites=['step4_phase4'],
    ),
}

# Step group ordering for UI layout
STEP_GROUPS = [
    'Pass 1', 'Pass 2', 'Pass 3', 'Reconcile & Commit',
    'Case Analysis', 'Publish',
]

# Display groups: merge facts+discussion substeps into single dashboard rows.
# Backend pipeline still treats them as separate substeps.
DISPLAY_GROUPS = [
    {
        'key': 'pass1',
        'display_name': 'Pass 1 - Contextual Framework',
        'step_group': 'Pass 1',
        'substeps': ['pass1_facts', 'pass1_discussion'],
    },
    {
        'key': 'pass2',
        'display_name': 'Pass 2 - Normative Requirements',
        'step_group': 'Pass 2',
        'substeps': ['pass2_facts', 'pass2_discussion'],
    },
]

# Reverse mapping: PSM substep name -> display row key
SUBSTEP_TO_DISPLAY_ROW = {}
_MERGED_SUBSTEPS = set()
for _dg in DISPLAY_GROUPS:
    for _sub in _dg['substeps']:
        SUBSTEP_TO_DISPLAY_ROW[_sub] = _dg['key']
        _MERGED_SUBSTEPS.add(_sub)
# Non-merged substeps map to themselves
for _step_name in WORKFLOW_DEFINITION:
    if _step_name not in SUBSTEP_TO_DISPLAY_ROW:
        SUBSTEP_TO_DISPLAY_ROW[_step_name] = _step_name


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


@dataclass
class PipelineState:
    """
    Immutable snapshot of pipeline state for a case.
    Provides convenient API for UI/templates to query state.
    """
    case_id: int
    _manager: PipelineStateManager = field(repr=False)

    def is_complete(self, step: str, task: str = None) -> bool:
        """Check if step/task is complete."""
        if task:
            return self._manager.check_task_complete(self.case_id, step, task)
        return self._manager.check_step_complete(self.case_id, step)

    def can_start(self, step: str, task: str = None) -> bool:
        """Check if prerequisites are met to start step/task."""
        can_start, _ = self._manager.check_prerequisites_met(self.case_id, step, task)
        return can_start

    def get_blockers(self, step: str, task: str = None) -> List[str]:
        """Get list of missing prerequisites."""
        _, blockers = self._manager.check_prerequisites_met(self.case_id, step, task)
        return blockers

    def get_status(self, step: str) -> TaskStatus:
        """Get step status."""
        return self._manager.get_step_status(self.case_id, step)

    def get_progress(self, step: str) -> Dict[str, Any]:
        """Get step progress details."""
        return self._manager.get_step_progress(self.case_id, step)

    def get_artifact_count(self, artifact_type: str) -> int:
        """Get count of specific artifact type."""
        counts = self._manager.get_artifact_counts(self.case_id)
        return counts.get(artifact_type, 0)

    def to_dict(self) -> Dict[str, Any]:
        """
        Export full state for API/template use.

        Returns:
            Dict with complete pipeline state, grouped by step_group.
        """
        artifact_counts = self._manager.get_artifact_counts(self.case_id)

        result = {
            'case_id': self.case_id,
            'steps': {},
            'step_groups': STEP_GROUPS,
        }

        for step_name, step_def in WORKFLOW_DEFINITION.items():
            can_start, blockers = self._manager.check_prerequisites_met(self.case_id, step_name)

            step_state = {
                'name': step_name,
                'display_name': step_def.display_name,
                'step_group': step_def.step_group,
                'status': self.get_status(step_name).value,
                'can_start': can_start,
                'blockers': blockers,
                'progress': self.get_progress(step_name),
                'tasks': {},
            }

            for task in step_def.tasks:
                task_can_start, task_blockers = self._manager.check_prerequisites_met(
                    self.case_id, step_name, task.name
                )
                task_artifact_counts = {
                    atype: artifact_counts.get(atype, 0)
                    for atype in task.artifact_types
                }
                step_state['tasks'][task.name] = {
                    'name': task.name,
                    'display_name': task.display_name,
                    'complete': self.is_complete(step_name, task.name),
                    'can_start': task_can_start,
                    'blockers': task_blockers,
                    'artifact_types': task.artifact_types,
                    'artifact_counts': task_artifact_counts,
                }

            result['steps'][step_name] = step_state

        return result

    def to_display_dict(self) -> Dict[str, Any]:
        """
        Export pipeline state with consolidated display rows.

        Merges facts/discussion substeps into single rows for Pass 1 and Pass 2.
        All other substeps pass through unchanged. Backend substep model stays intact.
        """
        raw = self.to_dict()
        steps = raw['steps']

        display_rows = []
        emitted_substeps = set()

        # Ordered iteration: follow WORKFLOW_DEFINITION order, emit merged rows
        # on first encounter of a display group member
        for step_name in WORKFLOW_DEFINITION:
            if step_name in emitted_substeps:
                continue

            if step_name in _MERGED_SUBSTEPS:
                # Find this substep's display group
                group_key = SUBSTEP_TO_DISPLAY_ROW[step_name]
                group = next(dg for dg in DISPLAY_GROUPS if dg['key'] == group_key)

                # Build merged row from component substeps
                component_states = [steps[s] for s in group['substeps']]
                display_rows.append(
                    _build_merged_row(group, component_states)
                )
                for s in group['substeps']:
                    emitted_substeps.add(s)
            else:
                # Passthrough: wrap existing step state
                step = steps[step_name]
                display_rows.append({
                    'type': 'single',
                    'name': step_name,
                    'display_name': step['display_name'],
                    'step_group': step['step_group'],
                    'status': step['status'],
                    'can_start': step['can_start'],
                    'blockers': step['blockers'],
                    'tasks': step['tasks'],
                    'component_substeps': [step_name],
                    'run_target': step_name,
                    'rerun_target': step_name,
                })
                emitted_substeps.add(step_name)

        raw['display_rows'] = display_rows
        raw['substep_to_display_row'] = SUBSTEP_TO_DISPLAY_ROW
        return raw


def _build_merged_row(group: dict, component_states: list) -> dict:
    """Build a single display row from multiple component substep states."""
    statuses = [s['status'] for s in component_states]

    # Derive combined status
    if all(s == 'complete' for s in statuses):
        combined_status = 'complete'
    elif any(s == 'error' for s in statuses):
        combined_status = 'error'
    elif all(s == 'not_started' for s in statuses):
        combined_status = 'not_started'
    else:
        combined_status = 'in_progress'

    # Combined can_start: true if any component can start
    combined_can_start = any(s['can_start'] for s in component_states)

    # Blockers: from the first non-startable component that blocks progress
    combined_blockers = []
    for s in component_states:
        if not s['can_start'] and s['status'] != 'complete':
            combined_blockers = s['blockers']
            break

    # Merge tasks: deduplicate by task name, sum artifact counts
    merged_tasks = {}
    for comp in component_states:
        for task_name, task_info in comp['tasks'].items():
            if task_name not in merged_tasks:
                merged_tasks[task_name] = dict(task_info)
            # Counts are already totals (not section-filtered), so no summing needed

    # Run target: first incomplete component substep
    run_target = None
    for s in component_states:
        if s['status'] != 'complete':
            run_target = s['name']
            break

    # Rerun target: first component (rerunning facts cascades to discussion)
    rerun_target = component_states[0]['name']

    # Sub-status for each component
    section_statuses = {
        s['name'].split('_')[-1]: s['status']
        for s in component_states
    }

    return {
        'type': 'merged',
        'name': group['key'],
        'display_name': group['display_name'],
        'step_group': group['step_group'],
        'status': combined_status,
        'can_start': combined_can_start,
        'blockers': combined_blockers,
        'tasks': merged_tasks,
        'component_substeps': group['substeps'],
        'run_target': run_target,
        'rerun_target': rerun_target,
        'section_statuses': section_statuses,
    }


def _check_substep_bulk(step_def, artifacts, prompts, reconciled, published):
    """
    Check if a single substep is complete using pre-fetched bulk data.

    Args:
        step_def: WorkflowStepDefinition instance
        artifacts: {extraction_type: count} for one case
        prompts: {concept_type: set(section_types)} for one case
        reconciled: bool - whether reconciliation_run exists for this case
        published: set of extraction_types with is_published=true for this case

    Returns:
        True if substep appears complete
    """
    if step_def.check_type == CheckType.RECONCILIATION_RUN:
        return reconciled or len(published) > 0

    if step_def.check_type == CheckType.PUBLISHED_ENTITIES:
        if step_def.published_types:
            return any(t in published for t in step_def.published_types)
        return len(published) > 0

    if step_def.check_type == CheckType.EXTRACTION_PROMPTS:
        for task in step_def.tasks:
            pattern = task.prompt_concept_type
            if pattern == 'phase4_narrative':
                if not any(ct.startswith('phase4') for ct in prompts):
                    return False
            else:
                if pattern not in prompts:
                    return False
        return True

    # ARTIFACTS check
    for task in step_def.tasks:
        total = sum(artifacts.get(t, 0) for t in task.artifact_types)
        if total < max(task.min_artifacts, 1):
            return False

        # Section-aware: verify extraction_prompts exist for the right section_type
        if step_def.section_type:
            has_section = any(
                step_def.section_type in prompts.get(ct, set())
                for ct in task.artifact_types
            )
            if not has_section:
                return False

    return True


def get_bulk_progress(case_ids):
    """
    Get pipeline progress for multiple cases using bulk SQL queries.

    Uses 5 SQL queries regardless of case count (no N+1). Returns a dict
    mapping case_id to progress summary with substep completion counts,
    coarse status, and active run info.

    Args:
        case_ids: List of case IDs to check

    Returns:
        Dict mapping case_id to:
            {complete, total, pct, status, active_run}
    """
    if not case_ids:
        return {}

    from sqlalchemy import text
    from app import db
    from app.models.pipeline_run import PipelineRun

    total_substeps = len(WORKFLOW_DEFINITION)
    default = {
        'complete': 0, 'total': total_substeps, 'pct': 0,
        'status': 'not_started', 'active_run': None,
    }

    try:
        # Query 1: Artifact counts per case per extraction_type
        artifact_rows = db.session.execute(text("""
            SELECT case_id, extraction_type, COUNT(*) as cnt
            FROM temporary_rdf_storage
            WHERE case_id = ANY(:ids)
            GROUP BY case_id, extraction_type
        """), {'ids': case_ids}).fetchall()

        artifacts = {}
        for row in artifact_rows:
            artifacts.setdefault(row[0], {})[row[1]] = row[2]

        # Query 2: Prompt existence (section-aware + Step 4 concept types)
        prompt_rows = db.session.execute(text("""
            SELECT case_id, concept_type, section_type
            FROM extraction_prompts
            WHERE case_id = ANY(:ids)
            GROUP BY case_id, concept_type, section_type
        """), {'ids': case_ids}).fetchall()

        prompts = {}
        for row in prompt_rows:
            case_prompts = prompts.setdefault(row[0], {})
            case_prompts.setdefault(row[1], set()).add(row[2])

        # Query 3: Reconciliation runs
        recon_rows = db.session.execute(text("""
            SELECT DISTINCT case_id
            FROM reconciliation_runs
            WHERE case_id = ANY(:ids)
        """), {'ids': case_ids}).fetchall()
        reconciled = {row[0] for row in recon_rows}

        # Query 4: Published entities per case per type
        pub_rows = db.session.execute(text("""
            SELECT case_id, extraction_type
            FROM temporary_rdf_storage
            WHERE case_id = ANY(:ids) AND is_published = true
            GROUP BY case_id, extraction_type
        """), {'ids': case_ids}).fetchall()

        published = {}
        for row in pub_rows:
            published.setdefault(row[0], set()).add(row[1])

        # Query 5: Active pipeline runs (non-terminal)
        terminal = ['completed', 'failed', 'extracted']
        active_runs = PipelineRun.query.filter(
            PipelineRun.case_id.in_(case_ids),
            ~PipelineRun.status.in_(terminal)
        ).order_by(PipelineRun.created_at.desc()).all()

        active_run_map = {}
        for run in active_runs:
            if run.case_id not in active_run_map:
                step_def = WORKFLOW_DEFINITION.get(run.current_step)
                display = step_def.display_name if step_def else (run.current_step or '')
                active_run_map[run.case_id] = {
                    'id': run.id,
                    'status': run.status,
                    'current_step': run.current_step,
                    'current_step_display': display,
                }

    except Exception as e:
        logger.error(f"Error in get_bulk_progress: {e}")
        return {cid: dict(default) for cid in case_ids}

    # Compute per-case progress
    result = {}
    for case_id in case_ids:
        case_artifacts = artifacts.get(case_id, {})
        case_prompts = prompts.get(case_id, {})
        case_reconciled = case_id in reconciled
        case_published = published.get(case_id, set())

        complete = 0
        for step_def in WORKFLOW_DEFINITION.values():
            if _check_substep_bulk(step_def, case_artifacts, case_prompts,
                                   case_reconciled, case_published):
                complete += 1

        # Coarse status (extends get_bulk_simple_status semantics)
        has_synthesis = (
            any(ct.startswith('phase4') for ct in case_prompts)
            or 'whole_case_synthesis' in case_prompts
        )
        has_any_artifacts = len(case_artifacts) > 0

        if has_synthesis and has_any_artifacts:
            status = 'synthesized'
        elif has_any_artifacts:
            status = 'extracted'
        else:
            status = 'not_started'

        pct = int((complete / total_substeps) * 100) if total_substeps > 0 else 0

        result[case_id] = {
            'complete': complete,
            'total': total_substeps,
            'pct': pct,
            'status': status,
            'active_run': active_run_map.get(case_id),
        }

    return result


def get_pipeline_state(case_id: int) -> PipelineState:
    """
    Quick access to pipeline state for a case.

    Usage:
        from app.services.pipeline_state_manager import get_pipeline_state

        state = get_pipeline_state(case_id)
        if state.can_start('step4_qc'):
            ...
    """
    manager = PipelineStateManager()
    return manager.get_pipeline_state(case_id)
