"""
Celery Tasks for ProEthica Scenario Pipeline

This module contains background tasks for automated case analysis.
Tasks run in Celery worker processes with Flask app context.

Pipeline Steps:
- Step 1: Pass 1 extraction (roles, states, resources) for facts/discussion
- Step 2: Pass 2 extraction (principles, obligations, constraints, capabilities)
- Step 3: Pass 3 extraction (actions, events)
- Step 4: Synthesis (provisions, questions, conclusions, transformation)
- Step 5: Scenario generation (participants, decisions)

Usage:
    # Queue a single case
    from app.tasks.pipeline_tasks import run_full_pipeline_task
    result = run_full_pipeline_task.delay(case_id=7)

    # Queue with specific configuration
    result = run_full_pipeline_task.delay(
        case_id=7,
        config={'skip_step5': True}
    )
"""

from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from celery_config import get_celery
from app import db
from app.models.pipeline_run import PipelineRun, PIPELINE_STATUS
from app.models.document import Document
from app.services.entity.case_entity_storage_service import CaseEntityStorageService
from datetime import datetime
import logging
import traceback
import uuid
import re

logger = logging.getLogger(__name__)

# Get Celery instance (lazy initialization)
celery = get_celery()


# Step 1: Pass 1 Extraction (roles, states, resources)
STEP1_ENTITY_TYPES = ['roles', 'states', 'resources']

# Step 2: Pass 2 Extraction (principles, obligations, constraints, capabilities)
STEP2_ENTITY_TYPES = ['principles', 'obligations', 'constraints', 'capabilities']

# Step 3: Pass 3 Extraction (actions and events separately)
STEP3_ENTITY_TYPES = ['actions', 'events']


def get_case_sections(case_id: int, segment_precedents: bool = True) -> dict:
    """
    Get facts and discussion sections for a case.

    The 'discussion' returned to the entity extractors (Step 1-3) has cited-precedent recaps
    removed at the source (see app.services.extraction.discussion_segmenter): those recaps narrate
    other cases' actors/scenarios and contaminate the present-case ontology, the worst form being
    a precedent that shares the present case's engineer letter, which no downstream filter can
    separate. The full discussion is preserved in 'discussion_full' for the legitimate
    precedent-reference lane. Pass segment_precedents=False to get the raw discussion.

    Returns:
        dict with 'facts', 'discussion' (present-case), 'discussion_full' (raw),
        and 'precedent_recaps' keys
    """
    case = Document.query.get(case_id)
    if not case:
        raise ValueError(f"Case {case_id} not found")

    metadata = case.doc_metadata or {}
    sections = metadata.get('sections_dual', {})

    # Extract text from section dicts (sections have 'text' and 'html' keys)
    facts = sections.get('facts', '')
    if isinstance(facts, dict):
        facts = facts.get('text', '')

    discussion_section = sections.get('discussion', '')
    if isinstance(discussion_section, dict):
        discussion_text = discussion_section.get('text', '')
        discussion_html = discussion_section.get('html', '')
    else:
        discussion_text = discussion_section
        discussion_html = ''

    result = {
        'facts': facts,
        'discussion': discussion_text,
        'discussion_full': discussion_text,
        'precedent_recaps': [],
    }
    if segment_precedents and discussion_html:
        seg = _present_case_discussion(case, discussion_html)
        if seg and seg.get('present_case_text'):
            result['discussion'] = seg['present_case_text']
            result['precedent_recaps'] = seg.get('precedent_recaps', [])
    return result


def _present_case_discussion(case, discussion_html: str) -> Optional[dict]:
    """Segment the discussion (cached per case in doc_metadata, keyed on the discussion HTML
    hash). Returns {'present_case_text', 'precedent_recaps', 'method'} or None on failure.

    The cache lives in a doc_metadata key SEPARATE from sections_dual (which must never be
    mutated by the pipeline). Best-effort: a write failure just means recomputation next call."""
    import hashlib
    src_hash = hashlib.md5(discussion_html.encode('utf-8')).hexdigest()[:16]
    meta = case.doc_metadata or {}
    cached = meta.get('discussion_segmentation')
    if isinstance(cached, dict) and cached.get('source_hash') == src_hash:
        return cached

    try:
        from app.services.extraction.discussion_segmenter import segment_discussion
        r = segment_discussion(discussion_html)
    except Exception:
        logger.warning("discussion segmentation failed for case %s; using full discussion",
                       getattr(case, 'id', '?'), exc_info=True)
        return None

    entry = {
        'source_hash': src_hash,
        'method': r.method,
        'present_case_text': r.present_case_text,
        'precedent_recaps': r.precedent_recaps,
    }
    try:
        from sqlalchemy.orm.attributes import flag_modified
        new_meta = dict(meta)
        new_meta['discussion_segmentation'] = entry
        case.doc_metadata = new_meta
        flag_modified(case, 'doc_metadata')
        db.session.commit()
        logger.info("case %s discussion segmented (method=%s, %d recap span(s))",
                    getattr(case, 'id', '?'), r.method, len(r.precedent_recaps))
    except Exception:
        db.session.rollback()
        logger.debug("could not cache discussion segmentation for case %s",
                     getattr(case, 'id', '?'), exc_info=True)
    return entry


def run_extraction(case_text: str, case_id: int,
                   section_type: str, entity_type: str, step_number: int = 1,
                   extractor_class=None) -> dict:
    """
    Run a single extraction using the shared concept extraction service.

    Thin wrapper around extract_concept() that returns counts for Celery
    task compatibility.

    Args:
        case_text: Text to extract from
        case_id: Case ID
        section_type: 'facts' or 'discussion'
        entity_type: Type of entity being extracted (roles, states, etc.)
        step_number: Pipeline step number (1, 2, or 3)
        extractor_class: Deprecated, ignored.

    Returns:
        dict with extraction result counts
    """
    from app.services.extraction.concept_extraction_service import extract_concept

    result = extract_concept(
        case_text=case_text,
        case_id=case_id,
        concept_type=entity_type,
        section_type=section_type,
        step_number=step_number,
    )

    return {
        'classes': len(result.classes),
        'individuals': len(result.individuals),
    }


def run_extraction_parallel(entity_types, case_text, case_id, section_type,
                            step_number, max_workers=3):
    """
    Run multiple entity type extractions in parallel using ThreadPoolExecutor.

    Mirrors the parallelization pattern from step1_enhanced.py and
    step2_enhanced.py SSE routes. Each thread gets its own Flask app context.

    Args:
        entity_types: List of entity types to extract (e.g., ['roles', 'states', 'resources'])
        case_text: Text to extract from
        case_id: Case ID
        section_type: 'facts' or 'discussion'
        step_number: Pipeline step number (1 or 2)
        max_workers: Number of parallel threads

    Returns:
        dict mapping entity_type -> extraction result dict
    """
    from flask import current_app
    app = current_app._get_current_object()

    def _extract_in_context(et):
        with app.app_context():
            return et, run_extraction(case_text, case_id, section_type, et, step_number)

    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_extract_in_context, et): et for et in entity_types}
        for future in as_completed(futures):
            entity_type = futures[future]
            try:
                _, result = future.result()
                results[entity_type] = result
            except Exception as e:
                logger.error(f"Parallel extraction failed for {entity_type}: {e}")
                results[entity_type] = {'classes': 0, 'individuals': 0, 'error': str(e)}
    return results


def _record_pass(run, activity_type, activity_name, result, plan=None,
                 agent_name=None, agent_type='extraction_service'):
    """Best-effort: record a non-LLM pipeline pass (reconciliation / enrichment) to provenance,
    run-scoped (session_id = PipelineRun id). Never fails the task; the surrounding step commits
    persist the row. This is the Tier-B counterpart to the commit-time Tier-A recording: it makes
    the reconciliation/enrichment passes (temporal sequencing, obligation engagement, entity
    reconcile, board-conclusion backfill, cited-provision auto-gen, citation-provenance,
    moral-intensity) visible as process steps, not prompts."""
    try:
        from app.services.provenance_service import get_provenance_service
        get_provenance_service().track_pass(
            activity_type=activity_type, activity_name=activity_name,
            case_id=run.case_id, session_id=str(run.id),
            agent_type=agent_type, agent_name=agent_name or activity_name,
            execution_plan=plan or {},
            result=result if isinstance(result, dict) else {'result': result},
        )
    except Exception:
        logger.warning("provenance _record_pass failed for %s (best-effort)",
                       activity_name, exc_info=True)


@celery.task(bind=True, name='proethica.tasks.run_step1')
def run_step1_task(self, run_id: int, section_type: str = 'facts'):
    """
    Execute Step 1 (Pass 1) extraction for a case.

    Extracts roles, states, and resources from the specified section.

    Args:
        run_id: PipelineRun ID
        section_type: 'facts' or 'discussion'

    Returns:
        dict with extraction results
    """
    logger.info(f"[Task {self.request.id}] Starting Step 1 ({section_type}) for run {run_id}")

    run = PipelineRun.query.get(run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found")

    step_name = f"step1_{section_type}"
    run.current_step = step_name
    run.set_status(PIPELINE_STATUS['STEP1_FACTS'] if section_type == 'facts' else PIPELINE_STATUS['STEP1_DISCUSSION'])
    db.session.commit()

    try:
        sections = get_case_sections(run.case_id)
        case_text = sections[section_type]

        if not case_text:
            raise ValueError(f"No {section_type} section found for case {run.case_id}")

        # Auto-clear uncommitted Pass 1 entities before running new extraction
        # Only clear on 'facts' run (first run) to avoid clearing discussion results
        if section_type == 'facts':
            run.current_step = "Clearing previous pass1 extraction"
            db.session.commit()
            clear_result = CaseEntityStorageService.clear_extraction_pass(
                case_id=run.case_id,
                extraction_pass='pass1'
            )
            if clear_result.get('success'):
                cleared_count = clear_result.get('entities_cleared', 0) + clear_result.get('prompts_cleared', 0)
                if cleared_count > 0:
                    logger.info(f"[Task {self.request.id}] Auto-cleared {cleared_count} uncommitted pass1 entities/prompts")
            else:
                logger.warning(f"[Task {self.request.id}] Auto-clear pass1 failed: {clear_result.get('error', 'Unknown')}")

        # Extract all 3 concept types in parallel (R||S||Rs)
        # Mirrors step1_enhanced.py ThreadPoolExecutor pattern
        run.current_step = f"step1_{section_type}_parallel"
        db.session.commit()
        logger.info(f"[Task {self.request.id}] Extracting R||S||Rs from {section_type} in parallel")

        results = run_extraction_parallel(
            STEP1_ENTITY_TYPES, case_text, run.case_id, section_type,
            step_number=1, max_workers=3
        )

        # Check for extraction errors
        for et, result in results.items():
            if 'error' in result:
                raise RuntimeError(f"Extraction failed for {et}: {result['error']}")

        # Reset current_step to canonical name (was set to progress messages)
        run.current_step = step_name
        run.mark_step_complete(step_name, results)
        mode = (run.config or {}).get('mode')
        if mode == 'single':
            run.set_status(PIPELINE_STATUS['COMPLETED'])
        elif mode == 'interactive':
            run.set_status(PIPELINE_STATUS['WAITING_REVIEW'])
        db.session.commit()

        logger.info(f"[Task {self.request.id}] Step 1 ({section_type}) completed: {results}")
        return {'success': True, 'step': step_name, 'results': results}

    except Exception as e:
        logger.error(f"[Task {self.request.id}] Step 1 ({section_type}) failed: {e}", exc_info=True)
        run.set_error(str(e), step_name)
        db.session.commit()
        raise


@celery.task(bind=True, name='proethica.tasks.run_step2')
def run_step2_task(self, run_id: int, section_type: str = 'facts'):
    """
    Execute Step 2 (Pass 2) extraction for a case.

    Extracts principles, obligations, constraints, and capabilities.

    Args:
        run_id: PipelineRun ID
        section_type: 'facts' or 'discussion'

    Returns:
        dict with extraction results
    """
    logger.info(f"[Task {self.request.id}] Starting Step 2 ({section_type}) for run {run_id}")

    run = PipelineRun.query.get(run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found")

    step_name = f"step2_{section_type}"
    run.current_step = step_name
    run.set_status(PIPELINE_STATUS['STEP2_FACTS'] if section_type == 'facts' else PIPELINE_STATUS['STEP2_DISCUSSION'])
    db.session.commit()

    try:
        sections = get_case_sections(run.case_id)
        case_text = sections[section_type]

        if not case_text:
            raise ValueError(f"No {section_type} section found for case {run.case_id}")

        # Auto-clear uncommitted Pass 2 entities before running new extraction
        # Only clear on 'facts' run (first run) to avoid clearing discussion results
        if section_type == 'facts':
            run.current_step = "Clearing previous pass2 extraction"
            db.session.commit()
            clear_result = CaseEntityStorageService.clear_extraction_pass(
                case_id=run.case_id,
                extraction_pass='pass2'
            )
            if clear_result.get('success'):
                cleared_count = clear_result.get('entities_cleared', 0) + clear_result.get('prompts_cleared', 0)
                if cleared_count > 0:
                    logger.info(f"[Task {self.request.id}] Auto-cleared {cleared_count} uncommitted pass2 entities/prompts")
            else:
                logger.warning(f"[Task {self.request.id}] Auto-clear pass2 failed: {clear_result.get('error', 'Unknown')}")

        # Phase 1: P then O sequential (O depends on P context)
        # Mirrors step2_enhanced.py hybrid pattern
        results = {}
        for entity_type in ['principles', 'obligations']:
            run.current_step = f"Extracting {entity_type} from {section_type}"
            db.session.commit()
            logger.info(f"[Task {self.request.id}] Extracting {entity_type} from {section_type}")
            results[entity_type] = run_extraction(
                case_text, run.case_id, section_type, entity_type,
                step_number=2
            )

        # Phase 2: Cs and Ca in parallel (both depend on O, independent of each other)
        run.current_step = f"step2_{section_type}_Cs_Ca_parallel"
        db.session.commit()
        logger.info(f"[Task {self.request.id}] Extracting Cs||Ca from {section_type} in parallel")

        parallel_results = run_extraction_parallel(
            ['constraints', 'capabilities'], case_text, run.case_id, section_type,
            step_number=2, max_workers=2
        )

        # Check for extraction errors
        for et, result in parallel_results.items():
            if 'error' in result:
                raise RuntimeError(f"Extraction failed for {et}: {result['error']}")

        results.update(parallel_results)

        # Reset current_step to canonical name (was set to progress messages)
        run.current_step = step_name
        run.mark_step_complete(step_name, results)
        mode = (run.config or {}).get('mode')
        if mode == 'single':
            run.set_status(PIPELINE_STATUS['COMPLETED'])
        elif mode == 'interactive':
            run.set_status(PIPELINE_STATUS['WAITING_REVIEW'])
        db.session.commit()

        logger.info(f"[Task {self.request.id}] Step 2 ({section_type}) completed: {results}")
        return {'success': True, 'step': step_name, 'results': results}

    except Exception as e:
        logger.error(f"[Task {self.request.id}] Step 2 ({section_type}) failed: {e}", exc_info=True)
        run.set_error(str(e), step_name)
        db.session.commit()
        raise


@celery.task(bind=True, name='proethica.tasks.run_step3')
def run_step3_task(self, run_id: int):
    """
    Execute Step 3 (Pass 3) extraction for a case.

    Uses the full 7-stage enhanced temporal dynamics LangGraph:
    - Stage 1: Section analysis (combine facts + discussion)
    - Stage 2: Temporal marker extraction
    - Stage 3: Action extraction (volitional decisions)
    - Stage 4: Event extraction (occurrences)
    - Stage 5: Causal chain analysis (NESS test, responsibility)
    - Stage 6: Temporal sequencing (timeline, Allen relations)
    - Stage 7: RDF storage (actions, events, causal_chains, timeline)

    This is the same extraction pipeline used by the UI, but runs
    synchronously without SSE streaming.

    Args:
        run_id: PipelineRun ID

    Returns:
        dict with extraction results
    """
    logger.info(f"[Task {self.request.id}] Starting Step 3 (Enhanced Temporal) for run {run_id}")

    run = PipelineRun.query.get(run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found")

    step_name = "step3"
    run.current_step = step_name
    run.set_status(PIPELINE_STATUS['STEP3'])
    db.session.commit()

    try:
        # Import the LangGraph builder
        from app.services.temporal_dynamics import build_temporal_dynamics_graph
        from app.services.entity.case_entity_storage_service import CaseEntityStorageService

        # Get case sections
        sections = get_case_sections(run.case_id)
        facts_text = sections.get('facts', '')
        discussion_text = sections.get('discussion', '')

        if not facts_text:
            raise ValueError(f"No facts section found for case {run.case_id}")

        logger.info(f"[Task {self.request.id}] Facts: {len(facts_text)} chars, Discussion: {len(discussion_text)} chars")

        # Auto-clear uncommitted Pass 3 entities before running new extraction
        run.current_step = "Clearing previous extraction"
        db.session.commit()

        clear_result = CaseEntityStorageService.clear_extraction_pass(
            case_id=run.case_id,
            extraction_pass='pass3'
        )
        if clear_result.get('success'):
            cleared_count = clear_result.get('entities_cleared', 0) + clear_result.get('prompts_cleared', 0)
            if cleared_count > 0:
                logger.info(f"[Task {self.request.id}] Auto-cleared {cleared_count} uncommitted entities/prompts")
        else:
            logger.warning(f"[Task {self.request.id}] Auto-clear failed: {clear_result.get('error', 'Unknown')}")

        # Initialize state for LangGraph (same as step3_enhanced.py)
        from datetime import datetime as dt
        initial_state = {
            'case_id': run.case_id,
            'facts_text': facts_text,
            'discussion_text': discussion_text,
            'extraction_session_id': str(uuid.uuid4()),
            'unified_narrative': {},
            'temporal_markers': {},
            'actions': [],
            'events': [],
            'causal_chains': [],
            'timeline': {},
            'current_stage': '',
            'progress_percentage': 0,
            'stage_messages': [],
            'errors': [],
            'start_time': dt.utcnow().isoformat(),
            'end_time': '',
            'llm_trace': []
        }

        # Build and run the LangGraph synchronously
        run.current_step = "Building temporal dynamics graph"
        db.session.commit()

        logger.info(f"[Task {self.request.id}] Building LangGraph for enhanced temporal extraction")
        graph = build_temporal_dynamics_graph()

        # Run the graph synchronously with streaming to track progress
        run.current_step = "Running 7-stage temporal extraction"
        db.session.commit()

        results = {
            'actions': 0,
            'events': 0,
            'causal_chains': 0,
            'allen_relations': 0,
            'stages_completed': []
        }

        logger.info(f"[Task {self.request.id}] Starting LangGraph execution")

        # Use stream() to get updates and track progress
        for chunk in graph.stream(initial_state, stream_mode="updates"):
            for node_name, updates in chunk.items():
                stage = updates.get('current_stage', '')
                progress = updates.get('progress_percentage', 0)
                messages = updates.get('stage_messages', [])
                errors = updates.get('errors', [])

                # Update pipeline run status with current stage
                if stage:
                    run.current_step = f"Stage: {stage} ({progress}%)"
                    db.session.commit()

                logger.info(f"[Task {self.request.id}] {node_name}: {stage} - {progress}%")

                if messages:
                    for msg in messages:
                        logger.info(f"[Task {self.request.id}] {msg}")

                if errors:
                    for err in errors:
                        logger.error(f"[Task {self.request.id}] Stage error: {err}")

                # Track completed stages
                if stage:
                    results['stages_completed'].append(stage)

                # Extract counts from final storage stage
                if node_name == 'store_rdf_node':
                    # Parse the storage message for counts
                    for msg in messages:
                        if 'Stored' in msg:
                            # Parse: "Stored X actions, Y events, Z causal chains..."
                            import re
                            action_match = re.search(r'(\d+) actions', msg)
                            event_match = re.search(r'(\d+) events', msg)
                            chain_match = re.search(r'(\d+) causal chains', msg)
                            allen_match = re.search(r'(\d+) Allen relations', msg)

                            if action_match:
                                results['actions'] = int(action_match.group(1))
                            if event_match:
                                results['events'] = int(event_match.group(1))
                            if chain_match:
                                results['causal_chains'] = int(chain_match.group(1))
                            if allen_match:
                                results['allen_relations'] = int(allen_match.group(1))

        # Chronological temporal sequencing (study-corrections A1): the
        # 7-stage graph stores Action/Event rows in extractor-pass order, not
        # chronology. Populate proeth:temporalSequence so the timeline view
        # renders in narrative time. Best-effort: never fail the step (the
        # view falls back to row id, and the backfill driver is the safety net).
        try:
            from app.services.extraction.temporal_sequence_apply import apply_temporal_sequence
            seq_result = apply_temporal_sequence(run.case_id)
            results['temporal_sequence'] = seq_result.get('status')
            logger.info(f"[Task {self.request.id}] Temporal sequencing: {seq_result}")
            _record_pass(run, 'reconciliation', 'temporal_sequence', seq_result,
                         plan={'orders': 'Actions/Events into narrative time (proeth:temporalSequence)'})
        except Exception as seq_err:
            logger.exception(f"[Task {self.request.id}] Temporal sequencing hook failed: {seq_err}")
            results['temporal_sequence'] = 'error'

        # Obligation engagement reclassification (study-corrections A3): split
        # each Action's obligations into fulfills / violates / raises. Runs
        # HERE (end of Step 3), not end of Step 2 as the original plan stated:
        # it consumes the temporal_dynamics_enhanced Action rows and their
        # proeth:temporalSequence, both produced by Step 3 (sequence set just
        # above by A1). Best-effort; never fails the step.
        try:
            from app.services.extraction.obligation_engagement_apply import apply_obligation_engagement
            eng_result = apply_obligation_engagement(run.case_id)
            results['obligation_engagement'] = eng_result.get('status')
            logger.info(f"[Task {self.request.id}] Obligation engagement: {eng_result}")
            _record_pass(run, 'reconciliation', 'obligation_engagement', eng_result,
                         plan={'repartitions': "each Action's obligations into fulfills / violates / "
                               "raises, reconciled against the case's extracted obligations"})
        except Exception as eng_err:
            logger.exception(f"[Task {self.request.id}] Obligation engagement hook failed: {eng_err}")
            results['obligation_engagement'] = 'error'

        # Reset current_step to canonical name (was set to stage progress)
        run.current_step = step_name
        run.mark_step_complete(step_name, results)
        mode = (run.config or {}).get('mode')
        if mode == 'single':
            run.set_status(PIPELINE_STATUS['COMPLETED'])
        elif mode == 'interactive':
            run.set_status(PIPELINE_STATUS['WAITING_REVIEW'])
        db.session.commit()

        logger.info(f"[Task {self.request.id}] Step 3 (Enhanced Temporal) completed: {results}")
        return {'success': True, 'step': step_name, 'results': results}

    except Exception as e:
        logger.error(f"[Task {self.request.id}] Step 3 failed: {e}", exc_info=True)
        run.set_error(str(e), step_name)
        db.session.commit()
        raise


@celery.task(bind=True, name='proethica.tasks.run_reconcile')
def run_reconcile_task(self, run_id: int):
    """Auto-merge near-duplicate entities across extraction passes.

    Uses EntityReconciliationService with auto-merge only (no human review).
    Called between Step 3 and commit in the batch pipeline.
    """
    logger.info(f"[Task {self.request.id}] Starting entity reconciliation for run {run_id}")

    run = PipelineRun.query.get(run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found")

    step_name = "reconcile"
    run.current_step = "Reconciling entities"
    db.session.commit()

    try:
        from app.services.entity.entity_reconciliation_service import EntityReconciliationService
        service = EntityReconciliationService()
        result = service.reconcile_auto(run.case_id)

        results = {
            'auto_merged': result.auto_merged,
            'skipped': result.skipped,
            'errors': result.errors
        }
        _record_pass(run, 'reconciliation', 'entity_reconcile', results,
                     plan={'rule': 'merge duplicate individuals across passes/sections '
                           '(auto + manual-queue)'})

        run.mark_step_complete(step_name, results)
        mode = (run.config or {}).get('mode')
        if mode == 'single':
            run.set_status(PIPELINE_STATUS['COMPLETED'])
        elif mode == 'interactive':
            run.set_status(PIPELINE_STATUS['WAITING_REVIEW'])
        db.session.commit()

        logger.info(
            f"[Task {self.request.id}] Reconciliation completed: "
            f"{result.auto_merged} merged, {result.skipped} skipped"
        )
        return {'success': True, 'step': step_name, 'results': results}

    except Exception as e:
        logger.error(f"[Task {self.request.id}] Reconciliation failed: {e}", exc_info=True)
        run.set_error(str(e), step_name)
        db.session.commit()
        raise


@celery.task(bind=True, name='proethica.tasks.run_full_pipeline')
def run_full_pipeline_task(self, case_id: int, config: dict = None,
                           user_id: int = None, run_id: int = None):
    """
    Execute complete pipeline for a case.

    Orchestrates all extraction steps in sequence:
    1. Step 1 facts (R, S, Rs)
    2. Step 1 discussion (R, S, Rs)
    3. Step 2 facts (P, O, Cs, Ca)
    4. Step 2 discussion (P, O, Cs, Ca)
    5. Step 3 (A, E)
    6. Commit to OntServe (optional, controlled by config)
    7. Step 4 (Case Synthesis) - optional, controlled by config

    Args:
        case_id: Document ID of the case to process
        config: Optional configuration dict with keys:
            - include_step4: bool (default: True) - run Step 4 synthesis
            - skip_step4: bool (default: False) - skip Step 4 (legacy)
            - commit_to_ontserve: bool (default: True) - commit entities to OntServe after Step 3
        user_id: Optional user who initiated
        run_id: Optional pre-created PipelineRun ID (from pipeline view dispatch)

    Returns:
        dict with overall results
    """
    config = config or {}
    include_step4 = config.get('include_step4', True) and not config.get('skip_step4', False)
    commit_to_ontserve = config.get('commit_to_ontserve', True)

    logger.info(f"[Task {self.request.id}] Starting full pipeline for case {case_id} (commit={commit_to_ontserve}, step4={include_step4})")

    # Verify case exists
    case = Document.query.get(case_id)
    if not case:
        raise ValueError(f"Case {case_id} not found")

    # Use pre-created PipelineRun if provided, otherwise create one
    if run_id:
        run = PipelineRun.query.get(run_id)
        if not run:
            raise ValueError(f"PipelineRun {run_id} not found")
        run.celery_task_id = self.request.id
        db.session.commit()
        logger.info(f"[Task {self.request.id}] Using existing PipelineRun {run_id}")
    else:
        run = PipelineRun(
            case_id=case_id,
            celery_task_id=self.request.id,
            config=config,
            initiated_by=user_id
        )
        run.set_status(PIPELINE_STATUS['RUNNING'])
        db.session.add(run)
        db.session.commit()
        run_id = run.id
        logger.info(f"[Task {self.request.id}] Created PipelineRun {run_id}")

    run_id = run.id

    # Clean up previous OntServe data for this case before re-extraction
    if commit_to_ontserve:
        try:
            from app.services.commit.ontserve_commit_service import OntServeCommitService
            svc = OntServeCommitService()
            ur = svc.uncommit_case(case_id)
            logger.info(f"[Task {self.request.id}] Pre-extraction uncommit: "
                        f"ttl={ur.get('ttl_deleted')}, db={ur.get('ontserve_cleared')}, "
                        f"reset={ur.get('entities_reset')}")
        except Exception as e:
            logger.warning(f"[Task {self.request.id}] Pre-extraction uncommit (non-fatal): {e}")

    try:
        # Step 1: Pass 1 extraction
        logger.info(f"[Task {self.request.id}] Running Step 1 facts...")
        run_step1_task.apply(args=[run_id, 'facts'])

        logger.info(f"[Task {self.request.id}] Running Step 1 discussion...")
        run_step1_task.apply(args=[run_id, 'discussion'])

        # Step 2: Pass 2 extraction
        logger.info(f"[Task {self.request.id}] Running Step 2 facts...")
        run_step2_task.apply(args=[run_id, 'facts'])

        logger.info(f"[Task {self.request.id}] Running Step 2 discussion...")
        run_step2_task.apply(args=[run_id, 'discussion'])

        # Step 3: Pass 3 extraction
        logger.info(f"[Task {self.request.id}] Running Step 3...")
        run_step3_task.apply(args=[run_id])

        # Reconcile: auto-merge near-duplicate entities across sections
        logger.info(f"[Task {self.request.id}] Running entity reconciliation...")
        run_reconcile_task.apply(args=[run_id])

        # Commit to OntServe (optional) - after reconciliation, before synthesis
        if commit_to_ontserve:
            logger.info(f"[Task {self.request.id}] Committing extraction entities to OntServe...")
            run_commit_task.apply(args=[run_id, 'commit_extraction'])

        # Step 4: Case Synthesis (optional)
        if include_step4:
            logger.info(f"[Task {self.request.id}] Running Step 4 (Case Synthesis)...")
            run_step4_task.apply(args=[run_id])

            # Second commit: commit Step 4 synthesis entities to OntServe
            if commit_to_ontserve:
                logger.info(f"[Task {self.request.id}] Committing synthesis entities to OntServe...")
                run_commit_task.apply(args=[run_id, 'commit_synthesis'])

        # Mark terminal status based on what was actually run
        run = PipelineRun.query.get(run_id)
        if include_step4:
            run.set_status(PIPELINE_STATUS['COMPLETED'])
            logger.info(f"[Task {self.request.id}] Full pipeline completed for case {case_id}")
        elif commit_to_ontserve:
            # Extraction + commit but no synthesis
            run.set_status(PIPELINE_STATUS['EXTRACTED'])
            logger.info(f"[Task {self.request.id}] Extraction + commit completed for case {case_id} (no synthesis)")
        else:
            run.set_status(PIPELINE_STATUS['EXTRACTED'])
            logger.info(f"[Task {self.request.id}] Extraction completed for case {case_id} (no commit/synthesis)")
        db.session.commit()

        return {
            'success': True,
            'run_id': run_id,
            'case_id': case_id,
            'steps_completed': run.steps_completed,
            'duration_seconds': run.duration_seconds,
            'included_step4': include_step4
        }

    except Exception as e:
        logger.error(f"[Task {self.request.id}] Pipeline failed for case {case_id}: {e}", exc_info=True)

        # Mark as failed
        run = PipelineRun.query.get(run_id)
        if run:
            run.set_error(str(e))
            db.session.commit()

        return {
            'success': False,
            'run_id': run_id,
            'case_id': case_id,
            'error': str(e)
        }


@celery.task(bind=True, name='proethica.tasks.resume_pipeline')
def resume_pipeline_task(self, run_id: int):
    """
    Resume a failed pipeline from the failed step.

    This allows continuing a pipeline that failed due to transient errors
    (like API timeouts) without re-running completed steps.

    Args:
        run_id: PipelineRun ID to resume

    Returns:
        dict with results
    """
    logger.info(f"[Task {self.request.id}] Resuming pipeline run {run_id}")

    run = PipelineRun.query.get(run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found")

    if run.status != PIPELINE_STATUS['FAILED']:
        raise ValueError(f"Can only resume failed runs (current status: {run.status})")

    # Get the failed step
    failed_step = run.error_step or run.current_step
    if not failed_step:
        raise ValueError("No failed step recorded - cannot resume")

    # Clear error and update status
    run.error_message = None
    run.error_step = None
    run.retry_count = (run.retry_count or 0) + 1
    run.set_status(PIPELINE_STATUS['RUNNING'])
    db.session.commit()

    logger.info(f"[Task {self.request.id}] Resuming from step: {failed_step} (retry #{run.retry_count})")

    try:
        # Determine which steps to run based on what failed
        completed = set(run.steps_completed or [])
        config = run.config or {}
        include_step4 = config.get('include_step4', True) and not config.get('skip_step4', False)
        commit_to_ontserve = config.get('commit_to_ontserve', True)

        # Step 1 facts
        if 'step1_facts' not in completed:
            logger.info(f"[Task {self.request.id}] Running Step 1 facts...")
            run_step1_task.apply(args=[run_id, 'facts'])

        # Step 1 discussion
        if 'step1_discussion' not in completed:
            logger.info(f"[Task {self.request.id}] Running Step 1 discussion...")
            run_step1_task.apply(args=[run_id, 'discussion'])

        # Step 2 facts
        if 'step2_facts' not in completed:
            logger.info(f"[Task {self.request.id}] Running Step 2 facts...")
            run_step2_task.apply(args=[run_id, 'facts'])

        # Step 2 discussion
        if 'step2_discussion' not in completed:
            logger.info(f"[Task {self.request.id}] Running Step 2 discussion...")
            run_step2_task.apply(args=[run_id, 'discussion'])

        # Step 3
        if 'step3' not in completed:
            logger.info(f"[Task {self.request.id}] Running Step 3...")
            run_step3_task.apply(args=[run_id])

        # Reconcile
        if 'reconcile' not in completed:
            logger.info(f"[Task {self.request.id}] Running entity reconciliation...")
            run_reconcile_task.apply(args=[run_id])

        # Commit extraction entities to OntServe (if configured)
        if commit_to_ontserve and 'commit_extraction' not in completed and 'commit' not in completed:
            logger.info(f"[Task {self.request.id}] Committing extraction entities to OntServe...")
            run_commit_task.apply(args=[run_id, 'commit_extraction'])

        # Step 4 (if configured)
        if include_step4 and 'step4' not in completed:
            logger.info(f"[Task {self.request.id}] Running Step 4 (Case Synthesis)...")
            run_step4_task.apply(args=[run_id])

            # Commit synthesis entities to OntServe
            if commit_to_ontserve and 'commit_synthesis' not in completed:
                logger.info(f"[Task {self.request.id}] Committing synthesis entities to OntServe...")
                run_commit_task.apply(args=[run_id, 'commit_synthesis'])

        # Mark as completed
        run = PipelineRun.query.get(run_id)
        run.set_status(PIPELINE_STATUS['COMPLETED'])
        db.session.commit()

        logger.info(f"[Task {self.request.id}] Pipeline resumed and completed for run {run_id}")

        return {
            'success': True,
            'run_id': run_id,
            'case_id': run.case_id,
            'steps_completed': run.steps_completed,
            'retry_count': run.retry_count,
            'duration_seconds': run.duration_seconds
        }

    except Exception as e:
        logger.error(f"[Task {self.request.id}] Resume failed for run {run_id}: {e}", exc_info=True)

        # Mark as failed again
        run = PipelineRun.query.get(run_id)
        if run:
            run.set_error(str(e))
            db.session.commit()

        return {
            'success': False,
            'run_id': run_id,
            'case_id': run.case_id if run else None,
            'error': str(e),
            'retry_count': run.retry_count if run else None
        }


@celery.task(bind=True, name='proethica.tasks.run_step4_substep')
def run_step4_substep_task(self, run_id: int, substep: str):
    """Execute a single Step 4 sub-phase for a case.

    Each Step 4 sub-phase (provisions, precedents, qc, transformation,
    rich_analysis, phase3, phase4) can be triggered individually from
    the pipeline view.

    Args:
        run_id: PipelineRun ID
        substep: PSM substep name (e.g. 'step4_provisions')

    Returns:
        dict with sub-phase results
    """
    logger.info(f"[Task {self.request.id}] Starting {substep} for run {run_id}")

    run = PipelineRun.query.get(run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found")

    run.current_step = substep
    run.set_status(PIPELINE_STATUS['RUNNING'])
    db.session.commit()

    try:
        from app.services.step4_synthesis_service import run_step4_substep

        def update_progress(stage: str, message: str):
            run.current_step = f"{substep}: {message}"
            db.session.commit()

        result = run_step4_substep(
            case_id=run.case_id,
            substep=substep,
            progress_callback=update_progress,
        )

        if result.get('error'):
            raise Exception(result['error'])

        # Reset current_step to canonical PSM name before terminal status
        run.current_step = substep
        run.mark_step_complete(substep, result)
        mode = (run.config or {}).get('mode')
        if mode == 'single':
            run.set_status(PIPELINE_STATUS['COMPLETED'])
        elif mode == 'interactive':
            run.set_status(PIPELINE_STATUS['WAITING_REVIEW'])
        else:
            # run_all mode -- parent task (run_full_pipeline_task) sets terminal status.
            # This branch should not execute for single/interactive dispatches.
            logger.warning(f"[Task {self.request.id}] Unexpected mode '{mode}' for substep {substep}")
        db.session.commit()

        logger.info(f"[Task {self.request.id}] {substep} completed: {result}")
        return {'success': True, 'step': substep, 'results': result}

    except Exception as e:
        logger.error(f"[Task {self.request.id}] {substep} failed: {e}", exc_info=True)
        run.set_error(str(e), substep)
        db.session.commit()
        raise


@celery.task(bind=True, name='proethica.tasks.run_step4')
def run_step4_task(self, run_id: int):
    """
    Execute Step 4 (Case Synthesis) for a case.

    Uses the unified step4_synthesis_service which runs the same code as
    the manual "Run Complete Synthesis" button, ensuring consistent behavior.

    Phases:
    - Phase 2A: Code Provisions
    - Phase 2B: Precedent Cases
    - Phase 2C: Questions & Conclusions
    - Phase 2D: Transformation Classification
    - Phase 2E: Rich Analysis (causal links, question emergence, resolution)
    - Phase 3: Decision Point Synthesis (E1-E3 + LLM fallback)
    - Phase 4: Narrative Construction (characters, timeline)

    Args:
        run_id: PipelineRun ID

    Returns:
        dict with synthesis results
    """
    logger.info(f"[Task {self.request.id}] Starting Step 4 (Case Synthesis) for run {run_id}")

    run = PipelineRun.query.get(run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found")

    step_name = "step4"
    run.current_step = step_name
    run.set_status(PIPELINE_STATUS['STEP4'])
    db.session.commit()

    try:
        from app.services.step4_synthesis_service import run_step4_synthesis

        # Progress callback to update run status
        def update_progress(stage: str, message: str):
            run.current_step = f"{stage}: {message}"
            db.session.commit()

        logger.info(f"[Task {self.request.id}] Running unified Step 4 synthesis for case {run.case_id}")

        # Run the unified synthesis service
        result = run_step4_synthesis(
            case_id=run.case_id,
            progress_callback=update_progress,
            skip_clear=False  # Always clear for pipeline runs
        )

        if not result.success:
            raise Exception(result.error or "Synthesis failed")

        # Extract results summary
        results = {
            'provisions_count': result.provisions_count,
            'questions_count': result.questions_count,
            'conclusions_count': result.conclusions_count,
            'transformation_type': result.transformation_type,
            'decision_points_count': result.decision_points_count,
            'causal_links_count': result.causal_links_count,
            'narrative_complete': result.narrative_complete,
            'duration_seconds': result.duration_seconds,
            'stages_completed': result.stages_completed
        }

        # Board-conclusion gap backfill (study-corrections A2): synthesize a
        # primary conclusion for any board-explicit question Step-4 synthesis
        # left unanswered. Runs after conclusions are stored; deduplicates
        # against existing conclusion labels. Best-effort; never fails the step.
        try:
            from app.services.extraction.board_conclusions_apply import apply_board_conclusions
            bc_result = apply_board_conclusions(run.case_id)
            results['board_conclusions'] = bc_result.get('status')
            logger.info(f"[Task {self.request.id}] Board-conclusion backfill: {bc_result}")
            _record_pass(run, 'enrichment', 'board_conclusion_backfill', bc_result,
                         plan={'fills': 'a primary conclusion for any board-explicit question left '
                               'unanswered by synthesis (dedup against existing)'})
        except Exception as bc_err:
            logger.exception(f"[Task {self.request.id}] Board-conclusion hook failed: {bc_err}")
            results['board_conclusions'] = 'error'

        # Cited-provision auto-generation (study-corrections A8): for every code
        # cited in a conclusion (including the board conclusions just added by
        # A2) with no code_provision_reference row, insert one with canonical
        # guideline_sections text. NO LLM; codes with no canonical leaf are
        # skipped. Runs after A2 so new conclusions' citations are covered.
        try:
            from app.services.extraction.cited_provisions_apply import apply_cited_provisions
            cp_result = apply_cited_provisions(run.case_id)
            results['cited_provisions'] = cp_result.get('status')
            logger.info(f"[Task {self.request.id}] Cited-provision auto-gen: {cp_result}")
            _record_pass(run, 'enrichment', 'cited_provision_autogen', cp_result,
                         plan={'inserts': 'a code_provision_reference (canonical guideline_sections '
                               'text, NO LLM) for every cited code lacking one'})
        except Exception as cp_err:
            logger.exception(f"[Task {self.request.id}] Cited-provision hook failed: {cp_err}")
            results['cited_provisions'] = 'error'

        # Citation provenance (study-corrections Phase 4): the complement of A8 --
        # for every cited provision that does NOT resolve to a guideline_sections
        # leaf (pre-2007 NSPE vocabulary, BER precedents, external laws, synthesized
        # labels, modern section-level codes with only sub-leaves), annotate a
        # proeth:citationProvenance field classifying why it is unmapped. NO LLM;
        # no crosswalk, no drop. Runs after A8 (which handles the resolvable ones).
        try:
            from app.services.extraction.citation_provenance_apply import apply_citation_provenance
            cpr_result = apply_citation_provenance(run.case_id)
            results['citation_provenance'] = cpr_result.get('status')
            logger.info(f"[Task {self.request.id}] Citation-provenance annotation: {cpr_result}")
            _record_pass(run, 'enrichment', 'citation_provenance_annotation', cpr_result,
                         plan={'classifies': 'why each unmapped cited provision does not resolve to '
                               'a guideline_sections leaf (NO LLM, no crosswalk, no drop)'})
        except Exception as cpr_err:
            logger.exception(f"[Task {self.request.id}] Citation-provenance hook failed: {cpr_err}")
            results['citation_provenance'] = 'error'

        # Moral-intensity per-tension rating (study-corrections A5): rate every
        # algorithmic tension in the phase4_narrative JSON on the five Jones
        # (1991) dimensions, not just the 2-5 the narrative prompt surfaces.
        # Runs after Phase-4 narrative is stored; idempotent. Best-effort.
        try:
            from app.services.extraction.moral_intensity_apply import apply_moral_intensity
            mi_result = apply_moral_intensity(run.case_id)
            results['moral_intensity'] = mi_result
            logger.info(f"[Task {self.request.id}] Moral-intensity rating: {mi_result}")
            _record_pass(run, 'enrichment', 'moral_intensity_rating', mi_result,
                         plan={'rates': 'each algorithmic tension on the five Jones (1991) moral-'
                               'intensity dimensions (LLM-backed; idempotent)'})
        except Exception as mi_err:
            logger.exception(f"[Task {self.request.id}] Moral-intensity hook failed: {mi_err}")
            results['moral_intensity'] = 'error'

        # Reset current_step to canonical name (was set to phase progress)
        run.current_step = step_name
        run.mark_step_complete(step_name, results)
        # Set terminal status only for single-substep or interactive runs.
        # Full pipeline runs get terminal status from run_full_pipeline_task.
        mode = (run.config or {}).get('mode')
        if mode == 'single':
            run.set_status(PIPELINE_STATUS['COMPLETED'])
        elif mode == 'interactive':
            run.set_status(PIPELINE_STATUS['WAITING_REVIEW'])
        db.session.commit()

        logger.info(f"[Task {self.request.id}] Step 4 completed in {result.duration_seconds:.1f}s: {results}")
        return {'success': True, 'step': step_name, 'results': results}

    except Exception as e:
        logger.error(f"[Task {self.request.id}] Step 4 failed: {e}", exc_info=True)
        run.set_error(str(e), step_name)
        db.session.commit()
        raise


@celery.task(bind=True, name='proethica.tasks.run_commit')
def run_commit_task(self, run_id: int, step_name: str = "commit_extraction"):
    """
    Commit extracted entities to OntServe using full commit service.

    Uses OntServeCommitService to:
    - Write classes to proethica-intermediate-extended.ttl
    - Write individuals to proethica-case-N.ttl
    - Mark entities as published
    - Refresh OntServe DB entities (with parent_uri)
    - Sync MCP cache

    Args:
        run_id: PipelineRun ID
        step_name: Step name for tracking ('commit_extraction' after Step 3,
                   'commit_synthesis' after Step 4)

    Returns:
        dict with commit results
    """
    logger.info(f"[Task {self.request.id}] Starting OntServe commit ({step_name}) for run {run_id}")

    run = PipelineRun.query.get(run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found")

    label = "extraction" if step_name == "commit_extraction" else "synthesis"
    run.current_step = f"Committing {label} entities to OntServe"
    db.session.commit()

    try:
        from app.services.commit.ontserve_commit_service import OntServeCommitService
        from app.models.temporary_rdf_storage import TemporaryRDFStorage

        # Get all unpublished entity IDs
        entities = TemporaryRDFStorage.query.filter_by(
            case_id=run.case_id, is_published=False
        ).all()
        entity_ids = [e.id for e in entities]

        if not entity_ids:
            results = {'total_entities': 0, 'skipped': True}
            run.mark_step_complete(step_name, results)
            mode = (run.config or {}).get('mode')
            if mode == 'single':
                run.set_status(PIPELINE_STATUS['COMPLETED'])
            elif mode == 'interactive':
                run.set_status(PIPELINE_STATUS['WAITING_REVIEW'])
            db.session.commit()
            logger.info(f"[Task {self.request.id}] No entities to commit")
            return {'success': True, 'step': step_name, 'results': results}

        commit_service = OntServeCommitService()
        result = commit_service.commit_selected_entities(run.case_id, entity_ids)

        results = {
            'classes_committed': result.get('classes_committed', 0),
            'individuals_committed': result.get('individuals_committed', 0),
            'ontserve_synced': result.get('ontserve_synced', False),
            'errors': result.get('errors', [])
        }

        run.mark_step_complete(step_name, results)
        mode = (run.config or {}).get('mode')
        if mode == 'single':
            run.set_status(PIPELINE_STATUS['COMPLETED'])
        elif mode == 'interactive':
            run.set_status(PIPELINE_STATUS['WAITING_REVIEW'])
        db.session.commit()

        logger.info(f"[Task {self.request.id}] OntServe commit completed: {results}")
        return {'success': True, 'step': step_name, 'results': results}

    except Exception as e:
        logger.error(f"[Task {self.request.id}] OntServe commit failed: {e}", exc_info=True)
        # Don't fail the whole pipeline for commit errors - log and continue.
        # For single/interactive mode, set terminal status so the run is not stuck.
        run.mark_step_complete(step_name, {'error': str(e), 'skipped': True})
        mode = (run.config or {}).get('mode')
        if mode == 'single':
            run.set_status(PIPELINE_STATUS['COMPLETED'])
        elif mode == 'interactive':
            run.set_status(PIPELINE_STATUS['WAITING_REVIEW'])
        db.session.commit()
        logger.warning(f"[Task {self.request.id}] Commit failed but pipeline will continue")
        return {'success': False, 'step': step_name, 'error': str(e)}


@celery.task(bind=True, name='proethica.tasks.process_queue')
def process_queue_task(self, limit: int = 10):
    """
    Process cases from the pipeline queue.

    Picks up queued cases and starts pipeline runs for them.

    Args:
        limit: Maximum number of cases to process

    Returns:
        dict with processing results
    """
    from app.models.pipeline_run import PipelineQueue

    logger.info(f"[Task {self.request.id}] Processing queue (limit={limit})")

    # Get queued items ordered by priority
    queue_items = PipelineQueue.query.filter_by(status='queued')\
        .order_by(PipelineQueue.priority.desc(), PipelineQueue.added_at.asc())\
        .limit(limit)\
        .all()

    processed = []
    for item in queue_items:
        queue_id = item.id
        case_id = item.case_id
        config = item.config or {}

        logger.info(f"[Task {self.request.id}] Processing queue item {queue_id} (case {case_id})")

        # Update queue status
        item.status = 'processing'
        item.started_at = datetime.utcnow()
        db.session.commit()

        try:
            # Start pipeline for this case with config from queue item
            # This runs synchronously and can take 10-15 minutes
            eager_result = run_full_pipeline_task.apply(args=[case_id], kwargs={'config': config})

            # Extract the actual result dict from EagerResult
            # Note: Don't call eager_result.get() - that triggers Celery's
            # "Never call result.get() within a task!" error
            result = eager_result.result

            # Re-fetch the queue item after long-running task to avoid stale session
            db.session.expire_all()
            item = PipelineQueue.query.get(queue_id)
            if item:
                item.status = 'completed' if result.get('success') else 'failed'
                db.session.commit()
            else:
                logger.warning(f"[Task {self.request.id}] Queue item {queue_id} not found after pipeline")

            processed.append({
                'queue_id': queue_id,
                'case_id': case_id,
                'success': result.get('success', False),
                'run_id': result.get('run_id')
            })

        except Exception as e:
            logger.error(f"[Task {self.request.id}] Queue item {queue_id} failed: {e}", exc_info=True)
            # Re-fetch and update status
            db.session.expire_all()
            item = PipelineQueue.query.get(queue_id)
            if item:
                item.status = 'failed'
                db.session.commit()

            processed.append({
                'queue_id': queue_id,
                'case_id': case_id,
                'success': False,
                'error': str(e)
            })

    logger.info(f"[Task {self.request.id}] Queue processing complete: {len(processed)} items")
    return {'processed': processed, 'count': len(processed)}


# Monitoring heartbeat task for Healthchecks.io
@celery.task(name='proethica.tasks.heartbeat', bind=True, max_retries=0)
def heartbeat_task(self):
    """
    Periodic heartbeat task to ping Healthchecks.io.

    This task runs every 5 minutes (configured in celery_config.py beat_schedule).
    If the ping stops, Healthchecks.io will send an alert indicating the
    Celery worker is down.
    """
    import os
    import urllib.request

    healthchecks_url = os.environ.get('HEALTHCHECKS_PING_URL')
    if not healthchecks_url:
        logger.debug("HEALTHCHECKS_PING_URL not configured, skipping heartbeat")
        return {'status': 'skipped', 'reason': 'URL not configured'}

    try:
        req = urllib.request.Request(
            healthchecks_url,
            headers={'User-Agent': 'ProEthica-Celery-Heartbeat/1.0'}
        )
        response = urllib.request.urlopen(req, timeout=10)
        status_code = response.getcode()
        logger.debug(f"Healthchecks.io heartbeat sent: {status_code}")
        return {'status': 'success', 'http_code': status_code}
    except Exception as e:
        logger.warning(f"Failed to send heartbeat to Healthchecks.io: {e}")
        return {'status': 'failed', 'error': str(e)}
