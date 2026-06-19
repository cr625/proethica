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

This module was split from a single 1,139-line file into a package; the public
surface is unchanged and re-exported below, so `from app.services.pipeline_state_manager
import X` continues to resolve exactly as before. Internals now live in:
  - definitions.py  (TaskStatus / CheckType / TaskDefinition / WorkflowStepDefinition /
                     WORKFLOW_DEFINITION / STEP_GROUPS / DISPLAY_GROUPS)
  - manager.py      (PipelineStateManager)
  - read_model.py   (PipelineState + the bulk multi-case progress query)
"""

from .definitions import (
    TaskStatus,
    CheckType,
    TaskDefinition,
    WorkflowStepDefinition,
    WORKFLOW_DEFINITION,
    STEP_GROUPS,
    DISPLAY_GROUPS,
    SUBSTEP_TO_DISPLAY_ROW,
    _MERGED_SUBSTEPS,
)
from .manager import PipelineStateManager
from .read_model import (
    PipelineState,
    get_bulk_progress,
    get_pipeline_state,
    _build_merged_row,
    _check_substep_bulk,
)

__all__ = [
    "TaskStatus",
    "CheckType",
    "TaskDefinition",
    "WorkflowStepDefinition",
    "WORKFLOW_DEFINITION",
    "STEP_GROUPS",
    "DISPLAY_GROUPS",
    "SUBSTEP_TO_DISPLAY_ROW",
    "PipelineStateManager",
    "PipelineState",
    "get_bulk_progress",
    "get_pipeline_state",
]
