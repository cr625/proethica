"""
Pipeline workflow definitions.

The 15-substep pipeline model, the per-substep completion-check types, and the
dashboard display grouping. Split out of the former single-file
pipeline_state_manager module (the public API is re-exported from the package
``__init__``).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


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
    entity_type_filter: Optional[str] = None


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
            TaskDefinition('actions', 'Actions', ['temporal_dynamics_enhanced'], 'temporal',
                           entity_type_filter='actions'),
            TaskDefinition('events', 'Events', ['temporal_dynamics_enhanced'], 'temporal',
                           entity_type_filter='events'),
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
