"""
Cascade Clearing Service

Handles clearing downstream artifacts when re-running pipeline substeps.
Walks the WORKFLOW_DEFINITION prerequisites graph in reverse to find all
transitively dependent substeps, then clears their artifacts.

Usage:
    from app.services.cascade_clearing_service import (
        get_downstream_substeps, get_cascade_preview, clear_cascade
    )

    # Preview what would be cleared
    preview = get_cascade_preview('pass1_facts')

    # Execute clearing
    stats = clear_cascade(case_id=7, target='pass1_facts')
"""

import logging
from collections import deque
from typing import Dict, List, Set, Any

from app.models import db, TemporaryRDFStorage, ExtractionPrompt
from app.models.reconciliation_run import ReconciliationRun
from app.models.case_ontology_commit import CaseOntologyCommit
from app.services.pipeline_state_manager import WORKFLOW_DEFINITION, CheckType

logger = logging.getLogger(__name__)


def get_downstream_substeps(target: str) -> List[str]:
    """Get all substeps that transitively depend on target.

    Walks the WORKFLOW_DEFINITION prerequisites graph in reverse (BFS).
    Does NOT include the target itself.

    Returns substeps in WORKFLOW_DEFINITION insertion order for consistency.
    """
    if target not in WORKFLOW_DEFINITION:
        return []

    # Build reverse adjacency: prerequisite -> set of dependents
    reverse_deps: Dict[str, Set[str]] = {}
    for name, defn in WORKFLOW_DEFINITION.items():
        for prereq in defn.prerequisites:
            reverse_deps.setdefault(prereq, set()).add(name)

    # BFS from target
    seen: Set[str] = set()
    queue = deque(reverse_deps.get(target, set()))
    while queue:
        step = queue.popleft()
        if step in seen:
            continue
        seen.add(step)
        for dep in reverse_deps.get(step, set()):
            if dep not in seen:
                queue.append(dep)

    # Return in WORKFLOW_DEFINITION order
    wf_order = list(WORKFLOW_DEFINITION.keys())
    return sorted(seen, key=lambda s: wf_order.index(s) if s in wf_order else 999)


def get_cascade_preview(target: str) -> Dict[str, Any]:
    """Preview what would be cleared if target substep is re-run.

    Returns a description suitable for a confirmation dialog.
    """
    if target not in WORKFLOW_DEFINITION:
        return {'error': f'Unknown substep: {target}'}

    target_def = WORKFLOW_DEFINITION[target]
    downstream = get_downstream_substeps(target)
    all_affected = [target] + downstream

    return {
        'target': target,
        'target_display': target_def.display_name,
        'downstream': downstream,
        'downstream_display': [
            WORKFLOW_DEFINITION[s].display_name
            for s in downstream if s in WORKFLOW_DEFINITION
        ],
        'affected_count': len(all_affected),
        'will_clear_reconciliation': 'reconcile' in all_affected,
        'will_clear_commits': any(s.startswith('commit') for s in all_affected),
    }


def clear_cascade(case_id: int, target: str) -> Dict[str, Any]:
    """Clear target substep and all downstream substep artifacts.

    Args:
        case_id: Case ID
        target: PSM substep name to re-run

    Returns:
        Dict with clearing statistics
    """
    if target not in WORKFLOW_DEFINITION:
        return {'error': f'Unknown substep: {target}'}

    downstream = get_downstream_substeps(target)
    to_clear = [target] + downstream

    stats = {
        'target': target,
        'downstream': downstream,
        'substeps_cleared': len(to_clear),
        'entities_deleted': 0,
        'prompts_deleted': 0,
        'reconciliation_deleted': 0,
        'published_reset': 0,
        'commits_deleted': 0,
    }

    for substep in to_clear:
        _clear_substep(case_id, substep, stats)

    # NOTE: Does NOT commit. Caller is responsible for db.session.commit()
    # so clearing + any subsequent operations (e.g., PipelineRun creation)
    # can be committed atomically.

    logger.info(f"Cascade clear for case {case_id}, target={target}: "
                f"entities={stats['entities_deleted']}, prompts={stats['prompts_deleted']}, "
                f"reconciliation={stats['reconciliation_deleted']}, "
                f"published_reset={stats['published_reset']}, commits={stats['commits_deleted']}")
    return stats


def _clear_substep(case_id: int, substep: str, stats: Dict[str, int]):
    """Clear artifacts for a single substep."""
    step_def = WORKFLOW_DEFINITION.get(substep)
    if not step_def:
        return

    # Collect all artifact types from tasks
    artifact_types = []
    for task in step_def.tasks:
        artifact_types.extend(task.artifact_types)

    # 1. Clear TRS entities
    if artifact_types:
        if step_def.section_type:
            count = _clear_section_entities(case_id, artifact_types, step_def.section_type)
        else:
            count = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.extraction_type.in_(artifact_types)
            ).delete(synchronize_session='fetch')
        stats['entities_deleted'] += count

    # 2. Clear extraction prompts
    prompt_count = _clear_substep_prompts(case_id, substep, step_def)
    stats['prompts_deleted'] += prompt_count

    # 3. Clear reconciliation
    if step_def.check_type == CheckType.RECONCILIATION_RUN:
        count = ReconciliationRun.query.filter_by(case_id=case_id).delete()
        stats['reconciliation_deleted'] += count

    # 4. Unpublish entities + clear commits
    # For commit_extraction (published_types=None), this resets ALL published
    # entities. This is safe because when commit_extraction is downstream,
    # all step4_* substeps are also downstream (they depend on it), so
    # synthesis entities will be deleted by their own clearing step.
    if step_def.check_type == CheckType.PUBLISHED_ENTITIES:
        reset_fields = {
            'is_published': False,
            'committed_at': None,
            'content_hash': None,
        }
        if step_def.published_types:
            count = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.is_published == True,
                TemporaryRDFStorage.extraction_type.in_(step_def.published_types)
            ).update(reset_fields, synchronize_session='fetch')
        else:
            count = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.is_published == True
            ).update(reset_fields, synchronize_session='fetch')
        stats['published_reset'] += count

        commit_count = CaseOntologyCommit.query.filter_by(case_id=case_id).delete()
        stats['commits_deleted'] += commit_count


def _clear_section_entities(case_id: int, extraction_types: List[str], section_type: str) -> int:
    """Clear TRS entities scoped to a specific section.

    Since TRS has no section_type column, we use extraction_session_ids
    from extraction_prompts to identify which entities belong to which section.
    """
    prompts = ExtractionPrompt.query.filter(
        ExtractionPrompt.case_id == case_id,
        ExtractionPrompt.section_type == section_type,
        ExtractionPrompt.concept_type.in_(extraction_types)
    ).all()

    session_ids = {p.extraction_session_id for p in prompts if p.extraction_session_id}

    if not session_ids:
        return 0

    return TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        TemporaryRDFStorage.extraction_type.in_(extraction_types),
        TemporaryRDFStorage.extraction_session_id.in_(list(session_ids))
    ).delete(synchronize_session='fetch')


def _clear_substep_prompts(case_id: int, substep: str, step_def) -> int:
    """Clear extraction_prompts produced by a substep.

    Scoping rules:
    - Section-aware (Steps 1-2): concept_type + section_type
    - pass3: step_number = 3
    - Step 4 substeps: step_number = 4 + concept_type from prompt_concept_type
    - reconcile/commit: no prompts produced
    """
    count = 0

    if step_def.section_type:
        # Section-aware (Steps 1-2): clear by concept_type + section_type
        concept_types = []
        for task in step_def.tasks:
            concept_types.extend(task.artifact_types)
        if concept_types:
            count = ExtractionPrompt.query.filter(
                ExtractionPrompt.case_id == case_id,
                ExtractionPrompt.concept_type.in_(concept_types),
                ExtractionPrompt.section_type == step_def.section_type
            ).delete(synchronize_session='fetch')

    elif substep == 'pass3':
        count = ExtractionPrompt.query.filter_by(
            case_id=case_id, step_number=3
        ).delete(synchronize_session='fetch')

    elif substep.startswith('step4_'):
        for task in step_def.tasks:
            pct = task.prompt_concept_type
            if not pct:
                continue
            if pct == 'phase4_narrative':
                count += ExtractionPrompt.query.filter(
                    ExtractionPrompt.case_id == case_id,
                    ExtractionPrompt.step_number == 4,
                    ExtractionPrompt.concept_type.like('phase4%')
                ).delete(synchronize_session='fetch')
            else:
                count += ExtractionPrompt.query.filter(
                    ExtractionPrompt.case_id == case_id,
                    ExtractionPrompt.step_number == 4,
                    ExtractionPrompt.concept_type == pct
                ).delete(synchronize_session='fetch')

    # reconcile and commit substeps don't produce extraction_prompts
    return count
