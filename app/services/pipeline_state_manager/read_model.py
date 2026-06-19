"""
Pipeline read-model: the immutable per-case ``PipelineState`` snapshot and the
bulk multi-case progress query.

``from __future__ import annotations`` defers the ``PipelineStateManager``
annotation on ``PipelineState._manager`` to a string so this module can import
the manager at top level without a load-time cycle (the manager only needs
``PipelineState`` lazily, inside ``get_pipeline_state``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any

from .definitions import (
    WORKFLOW_DEFINITION, STEP_GROUPS, DISPLAY_GROUPS,
    SUBSTEP_TO_DISPLAY_ROW, _MERGED_SUBSTEPS, CheckType, TaskStatus,
)
from .manager import PipelineStateManager

logger = logging.getLogger(__name__)


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
        entity_type_counts = self._manager.get_entity_type_counts(self.case_id)

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
                if task.entity_type_filter:
                    # Use entity_type-filtered count for display
                    task_artifact_counts = {
                        task.name: sum(
                            entity_type_counts.get(atype, {}).get(task.entity_type_filter, 0)
                            for atype in task.artifact_types
                        )
                    }
                else:
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
