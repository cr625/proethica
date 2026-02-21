"""
Pipeline State Manager - Data-Driven State for Extraction Pipeline

Designed for future migration to NVIDIA NeMo Agent Toolkit.
Uses NeMo-compatible terminology:
- Task: A unit of work (substep in our UI)
- Artifact: Data produced by a task (entities in temporary_rdf_storage)
- Workflow: Collection of tasks with dependencies (our pipeline)

NeMo Migration Path:
- TaskDefinition -> nemo.tasks.Task
- WorkflowDefinition -> nemo.workflows.Workflow
- artifact_types -> nemo.artifacts.Artifact schemas
- prerequisites -> nemo.workflows.depends_on

Usage:
    from app.services.pipeline_state_manager import PipelineStateManager, get_pipeline_state

    # Quick access
    state = get_pipeline_state(case_id)
    if state.can_start('step4', 'questions'):
        enable_button()

    # Full API
    manager = PipelineStateManager()
    state = manager.get_pipeline_state(case_id)
    full_state = state.to_dict()  # For API/template
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of a pipeline task. Maps to NeMo task states."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"  # Some artifacts exist
    COMPLETE = "complete"        # All required artifacts exist
    ERROR = "error"              # Task failed (future use)
    SKIPPED = "skipped"          # Task intentionally skipped (future use)


@dataclass
class TaskDefinition:
    """
    A single extractable unit within a workflow step.

    NeMo equivalent: nemo.tasks.Task

    Attributes:
        name: Unique task identifier within the step
        display_name: Human-readable name for UI
        artifact_types: Entity types to check in temporary_rdf_storage
        prompt_concept_type: concept_type in extraction_prompts (for provenance)
        prerequisites: Other tasks that must complete first (within same step)
        min_artifacts: Minimum number of artifacts required for completion (default: 1)
    """
    name: str
    display_name: str
    artifact_types: List[str]
    prompt_concept_type: str
    prerequisites: List[str] = field(default_factory=list)
    min_artifacts: int = 1


@dataclass
class WorkflowStepDefinition:
    """
    A major step in the pipeline workflow.

    NeMo equivalent: A group of tasks within a nemo.workflows.Workflow

    Attributes:
        name: Unique step identifier
        display_name: Human-readable name for UI
        tasks: List of tasks in this step
        prerequisites: Other steps that must complete first
        route_name: Flask route name for navigation
    """
    name: str
    display_name: str
    tasks: List[TaskDefinition]
    prerequisites: List[str] = field(default_factory=list)
    route_name: str = ""


# Pipeline workflow definition
# This structure can be exported to NeMo workflow YAML format
#
# IMPORTANT: artifact_types must match EXACTLY the extraction_type values
# stored in temporary_rdf_storage. Check with:
#   SELECT DISTINCT extraction_type FROM temporary_rdf_storage;
#
WORKFLOW_DEFINITION: Dict[str, WorkflowStepDefinition] = {
    'pass1_facts': WorkflowStepDefinition(
        name='pass1_facts',
        display_name='Pass 1 - Facts Section',
        route_name='scenario_pipeline.step1',
        tasks=[
            # DB uses plural: 'roles', 'states', 'resources'
            TaskDefinition('roles', 'Roles', ['roles'], 'role'),
            TaskDefinition('states', 'States', ['states'], 'state'),
            TaskDefinition('resources', 'Resources', ['resources'], 'resource'),
        ],
        prerequisites=[]
    ),
    'pass1_discussion': WorkflowStepDefinition(
        name='pass1_discussion',
        display_name='Pass 1b - Discussion Section',
        route_name='scenario_pipeline.step1b',
        tasks=[
            # Discussion section uses same types - entities tagged by section
            TaskDefinition('roles', 'Roles', ['roles'], 'role'),
            TaskDefinition('states', 'States', ['states'], 'state'),
            TaskDefinition('resources', 'Resources', ['resources'], 'resource'),
        ],
        prerequisites=['pass1_facts']
    ),
    'pass2_facts': WorkflowStepDefinition(
        name='pass2_facts',
        display_name='Pass 2 - Facts Section',
        route_name='scenario_pipeline.step2',
        tasks=[
            # DB uses plural: 'principles', 'obligations', 'constraints', 'capabilities'
            TaskDefinition('principles', 'Principles', ['principles'], 'principle'),
            TaskDefinition('obligations', 'Obligations', ['obligations'], 'obligation'),
            TaskDefinition('constraints', 'Constraints', ['constraints'], 'constraint'),
            TaskDefinition('capabilities', 'Capabilities', ['capabilities'], 'capability'),
        ],
        prerequisites=['pass1_facts']
    ),
    'pass2_discussion': WorkflowStepDefinition(
        name='pass2_discussion',
        display_name='Pass 2b - Discussion Section',
        route_name='scenario_pipeline.step2b',
        tasks=[
            TaskDefinition('principles', 'Principles', ['principles'], 'principle'),
            TaskDefinition('obligations', 'Obligations', ['obligations'], 'obligation'),
            TaskDefinition('constraints', 'Constraints', ['constraints'], 'constraint'),
            TaskDefinition('capabilities', 'Capabilities', ['capabilities'], 'capability'),
        ],
        prerequisites=['pass2_facts']
    ),
    'pass3': WorkflowStepDefinition(
        name='pass3',
        display_name='Pass 3 - Temporal Extraction',
        route_name='scenario_pipeline.step3',
        tasks=[
            # DB uses 'temporal_dynamics_enhanced' for combined action/event extraction
            TaskDefinition('temporal', 'Actions & Events', ['temporal_dynamics_enhanced'], 'temporal'),
        ],
        prerequisites=['pass2_facts']
    ),
    'step4': WorkflowStepDefinition(
        name='step4',
        display_name='Step 4 - Case Analysis',
        route_name='scenario_pipeline.step4',
        tasks=[
            # Phase 2A: Code provisions from References section
            TaskDefinition('provisions', 'Code Provisions', ['code_provision_reference'], 'code_provision'),
            # Phase 2C: Questions extraction
            TaskDefinition('questions', 'Ethical Questions', ['ethical_question'], 'ethical_question',
                          prerequisites=['provisions']),
            # Phase 2C: Conclusions extraction
            TaskDefinition('conclusions', 'Board Conclusions', ['ethical_conclusion'], 'ethical_conclusion',
                          prerequisites=['provisions']),
            # Phase 2E: Rich analysis creates causal links, question emergence, resolution patterns
            TaskDefinition('rich_analysis', 'Rich Analysis',
                          ['causal_normative_link', 'question_emergence', 'resolution_pattern'], 'rich_analysis',
                          prerequisites=['questions', 'conclusions']),
            # Phase 3: Decision point synthesis (E1-E3 + LLM fallback)
            TaskDefinition('decision_points', 'Decision Points',
                          ['canonical_decision_point'], 'phase3_decision_synthesis',
                          prerequisites=['rich_analysis']),
            # Phase 4: Narrative construction (check extraction_prompts since entities vary)
            TaskDefinition('narrative', 'Narrative Construction',
                          [], 'phase4_narrative',  # Check prompt, not entities
                          prerequisites=['decision_points'], min_artifacts=0),
        ],
        prerequisites=['pass3']
    ),
    'step5': WorkflowStepDefinition(
        name='step5',
        display_name='Step 5 - Interactive Scenario',
        route_name='scenario_pipeline.step5',
        tasks=[
            TaskDefinition('participants', 'Participants', ['scenario_participant'], 'participant'),
            TaskDefinition('relationships', 'Relationships', ['scenario_relationship'], 'relationship'),
            TaskDefinition('timeline', 'Timeline', ['timeline_event'], 'timeline'),
        ],
        prerequisites=['step4']
    ),
}


class PipelineStateManager:
    """
    Unified state manager that derives state from actual data artifacts.

    NeMo Migration: This class would become a thin wrapper around
    nemo.workflows.WorkflowState with custom artifact checkers.

    Usage:
        manager = PipelineStateManager()
        state = manager.get_pipeline_state(case_id)

        # Check prerequisites
        if state.can_start('step4', 'questions'):
            # Enable questions extraction button

        # Get blockers for tooltip
        blockers = state.get_blockers('step4', 'transformation')
        # -> ['questions not complete', 'conclusions not complete']
    """

    def __init__(self, db_session=None):
        """
        Initialize state manager.

        Args:
            db_session: SQLAlchemy session (optional, uses db.session if not provided)
        """
        self._db_session = db_session
        self._artifact_cache: Dict[int, Dict[str, int]] = {}  # case_id -> {artifact_type: count}

    @property
    def db(self):
        """Get database session."""
        if self._db_session:
            return self._db_session
        from app import db
        return db.session

    def get_pipeline_state(self, case_id: int) -> 'PipelineState':
        """
        Get complete pipeline state for a case.

        Args:
            case_id: The case to get state for

        Returns:
            PipelineState object with convenience methods
        """
        return PipelineState(case_id, self)

    def get_artifact_counts(self, case_id: int) -> Dict[str, int]:
        """
        Get counts of all artifact types for a case.

        NeMo equivalent: Query artifact store for workflow run.

        Returns:
            Dict mapping artifact_type to count
        """
        # Check cache first
        if case_id in self._artifact_cache:
            return self._artifact_cache[case_id]

        from app.models import TemporaryRDFStorage
        from sqlalchemy import func

        try:
            # Single query to get all counts
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

    def invalidate_cache(self, case_id: int = None):
        """
        Invalidate artifact cache.

        Call after extraction completes to refresh state.

        Args:
            case_id: Specific case to invalidate, or None for all
        """
        if case_id is None:
            self._artifact_cache.clear()
        elif case_id in self._artifact_cache:
            del self._artifact_cache[case_id]

    def check_task_complete(self, case_id: int, step: str, task: str) -> bool:
        """
        Check if a task has produced required artifacts.

        Args:
            case_id: Case ID
            step: Step name (e.g., 'step4')
            task: Task name (e.g., 'questions')

        Returns:
            True if task has produced required artifacts
        """
        step_def = WORKFLOW_DEFINITION.get(step)
        if not step_def:
            return False

        task_def = next((t for t in step_def.tasks if t.name == task), None)
        if not task_def:
            return False

        counts = self.get_artifact_counts(case_id)

        # Check if any of the artifact types have enough items
        total_artifacts = sum(counts.get(atype, 0) for atype in task_def.artifact_types)
        return total_artifacts >= task_def.min_artifacts

    def check_step_complete(self, case_id: int, step: str) -> bool:
        """
        Check if all tasks in a step are complete.

        Args:
            case_id: Case ID
            step: Step name

        Returns:
            True if all tasks in step are complete
        """
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

        Args:
            case_id: Case ID
            step: Step name
            task: Optional task name (for task-level prereqs)

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
        """
        Get overall status of a step.

        Args:
            case_id: Case ID
            step: Step name

        Returns:
            TaskStatus enum value
        """
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
        """
        Get detailed progress for a step.

        Args:
            case_id: Case ID
            step: Step name

        Returns:
            Dict with progress details
        """
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
            'status': self.get_step_status(case_id, step).value
        }


@dataclass
class PipelineState:
    """
    Immutable snapshot of pipeline state for a case.

    Provides convenient API for UI/templates to query state.

    NeMo equivalent: nemo.workflows.WorkflowRunState
    """
    case_id: int
    _manager: PipelineStateManager

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
            Dict with complete pipeline state
        """
        result = {
            'case_id': self.case_id,
            'steps': {}
        }

        for step_name, step_def in WORKFLOW_DEFINITION.items():
            can_start, blockers = self._manager.check_prerequisites_met(self.case_id, step_name)

            step_state = {
                'name': step_name,
                'display_name': step_def.display_name,
                'route_name': step_def.route_name,
                'status': self.get_status(step_name).value,
                'can_start': can_start,
                'blockers': blockers,
                'progress': self.get_progress(step_name),
                'tasks': {}
            }

            for task in step_def.tasks:
                task_can_start, task_blockers = self._manager.check_prerequisites_met(
                    self.case_id, step_name, task.name
                )
                step_state['tasks'][task.name] = {
                    'name': task.name,
                    'display_name': task.display_name,
                    'complete': self.is_complete(step_name, task.name),
                    'can_start': task_can_start,
                    'blockers': task_blockers,
                    'artifact_types': task.artifact_types,
                }

            result['steps'][step_name] = step_state

        return result


# Convenience function for quick access
def get_pipeline_state(case_id: int) -> PipelineState:
    """
    Quick access to pipeline state for a case.

    Usage:
        from app.services.pipeline_state_manager import get_pipeline_state

        state = get_pipeline_state(case_id)
        if state.can_start('step4', 'questions'):
            ...
    """
    manager = PipelineStateManager()
    return manager.get_pipeline_state(case_id)


# Export workflow definition for NeMo conversion
def export_workflow_yaml() -> str:
    """
    Export workflow definition in NeMo-compatible YAML format.

    This can be used as a starting point for NeMo migration.
    """
    import yaml

    workflow = {
        'name': 'proethica_extraction_pipeline',
        'version': '1.0',
        'description': 'Professional ethics case extraction and analysis pipeline',
        'steps': {}
    }

    for step_name, step_def in WORKFLOW_DEFINITION.items():
        workflow['steps'][step_name] = {
            'display_name': step_def.display_name,
            'prerequisites': step_def.prerequisites,
            'tasks': [
                {
                    'name': task.name,
                    'display_name': task.display_name,
                    'artifact_types': task.artifact_types,
                    'prerequisites': task.prerequisites,
                }
                for task in step_def.tasks
            ]
        }

    return yaml.dump(workflow, default_flow_style=False, sort_keys=False)
