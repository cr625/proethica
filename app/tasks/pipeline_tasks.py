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

from celery_config import get_celery
from app import db
from app.models.pipeline_run import PipelineRun, PIPELINE_STATUS
from app.models.document import Document
from datetime import datetime
import logging
import traceback
import uuid
import json
import re

logger = logging.getLogger(__name__)

# Get Celery instance (lazy initialization)
celery = get_celery()


# Step 1: Pass 1 Extraction (roles, states, resources)
STEP1_ENTITY_TYPES = ['roles', 'states', 'resources']

# Step 2: Pass 2 Extraction (principles, obligations, constraints, capabilities)
STEP2_ENTITY_TYPES = ['principles', 'obligations', 'constraints', 'capabilities']

# Step 3: Pass 3 Extraction (actions/events combined)
STEP3_ENTITY_TYPES = ['actions_events']


def get_case_sections(case_id: int) -> dict:
    """
    Get facts and discussion sections for a case.

    Returns:
        dict with 'facts' and 'discussion' keys containing section text
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

    discussion = sections.get('discussion', '')
    if isinstance(discussion, dict):
        discussion = discussion.get('text', '')

    return {
        'facts': facts,
        'discussion': discussion
    }


def run_extraction(extractor_class, case_text: str, case_id: int,
                   section_type: str, entity_type: str, step_number: int = 1) -> dict:
    """
    Run a single extraction and return results.

    Also saves the prompt and response to the database for persistence,
    and stores extracted entities to TemporaryRDFStorage for entity review.

    Args:
        extractor_class: The extractor class to instantiate
        case_text: Text to extract from
        case_id: Case ID
        section_type: 'facts' or 'discussion'
        entity_type: Type of entity being extracted
        step_number: Pipeline step number (1, 2, or 3)

    Returns:
        dict with extraction results
    """
    from app.models.extraction_prompt import ExtractionPrompt
    from app.models import TemporaryRDFStorage
    from app.services.rdf_extraction_converter import RDFExtractionConverter

    # Generate unique session ID to link prompt and entities
    session_id = str(uuid.uuid4())

    extractor = extractor_class()

    if entity_type == 'roles':
        classes, individuals = extractor.extract_dual_roles(
            case_text=case_text, case_id=case_id, section_type=section_type
        )
    elif entity_type == 'states':
        classes, individuals = extractor.extract_dual_states(
            case_text=case_text, case_id=case_id, section_type=section_type
        )
    elif entity_type == 'resources':
        classes, individuals = extractor.extract_dual_resources(
            case_text=case_text, case_id=case_id, section_type=section_type
        )
    elif entity_type == 'principles':
        classes, individuals = extractor.extract_dual_principles(
            case_text=case_text, case_id=case_id, section_type=section_type
        )
    elif entity_type == 'obligations':
        classes, individuals = extractor.extract_dual_obligations(
            case_text=case_text, case_id=case_id, section_type=section_type
        )
    elif entity_type == 'constraints':
        classes, individuals = extractor.extract_dual_constraints(
            case_text=case_text, case_id=case_id, section_type=section_type
        )
    elif entity_type == 'capabilities':
        classes, individuals = extractor.extract_dual_capabilities(
            case_text=case_text, case_id=case_id, section_type=section_type
        )
    elif entity_type == 'actions_events':
        action_classes, action_individuals, event_classes, event_individuals = \
            extractor.extract_dual_actions_events(
                case_text=case_text, case_id=case_id, section_type=section_type
            )

        # Save prompt and response for actions_events with session_id
        raw_response = extractor.last_raw_response
        prompt_text = extractor.last_prompt or f"[Automated Pipeline] {entity_type} extraction for case {case_id}, {section_type}"
        try:
            ExtractionPrompt.save_prompt(
                case_id=case_id,
                concept_type='actions_events',
                prompt_text=prompt_text,
                raw_response=raw_response,
                step_number=step_number,
                section_type=section_type,
                llm_model='claude-sonnet-4-20250514',
                extraction_session_id=session_id,
                results_summary={
                    'action_classes': len(action_classes),
                    'action_individuals': len(action_individuals),
                    'event_classes': len(event_classes),
                    'event_individuals': len(event_individuals)
                }
            )
        except Exception as e:
            logger.warning(f"Could not save extraction prompt: {e}")

        # Store actions_events to TemporaryRDFStorage
        try:
            if raw_response:
                raw_data = _parse_raw_response(raw_response)
                rdf_converter = RDFExtractionConverter()
                rdf_converter.convert_actions_events_extraction_to_rdf(raw_data, case_id)
                rdf_data = rdf_converter.get_temporary_triples()
                TemporaryRDFStorage.store_extraction_results(
                    case_id=case_id,
                    extraction_session_id=session_id,
                    extraction_type='actions_events',
                    rdf_data=rdf_data,
                    extraction_model='claude-sonnet-4-20250514'
                )
                logger.info(f"Stored actions_events RDF entities for case {case_id}, session {session_id}")
        except Exception as e:
            logger.warning(f"Could not store actions_events RDF: {e}")

        return {
            'action_classes': len(action_classes),
            'action_individuals': len(action_individuals),
            'event_classes': len(event_classes),
            'event_individuals': len(event_individuals),
            'raw_response': raw_response
        }
    else:
        raise ValueError(f"Unknown entity type: {entity_type}")

    # Save prompt and response to database with session_id
    raw_response = extractor.last_raw_response
    prompt_text = extractor.last_prompt or f"[Automated Pipeline] {entity_type} extraction for case {case_id}, {section_type}"
    try:
        ExtractionPrompt.save_prompt(
            case_id=case_id,
            concept_type=entity_type,
            prompt_text=prompt_text,
            raw_response=raw_response,
            step_number=step_number,
            section_type=section_type,
            llm_model='claude-sonnet-4-20250514',
            extraction_session_id=session_id,
            results_summary={
                'classes': len(classes),
                'individuals': len(individuals)
            }
        )
    except Exception as e:
        logger.warning(f"Could not save extraction prompt: {e}")

    # Store entities to TemporaryRDFStorage for entity review
    try:
        if raw_response:
            raw_data = _parse_raw_response(raw_response)
            rdf_converter = RDFExtractionConverter()

            # Use appropriate converter method based on entity type
            if entity_type == 'roles':
                rdf_converter.convert_extraction_to_rdf(raw_data, case_id, section_type=section_type, pass_number=step_number)
            elif entity_type == 'states':
                rdf_converter.convert_states_extraction_to_rdf(raw_data, case_id)
            elif entity_type == 'resources':
                rdf_converter.convert_resources_extraction_to_rdf(raw_data, case_id)
            elif entity_type == 'principles':
                rdf_converter.convert_principles_extraction_to_rdf(raw_data, case_id)
            elif entity_type == 'obligations':
                rdf_converter.convert_obligations_extraction_to_rdf(raw_data, case_id)
            elif entity_type == 'constraints':
                rdf_converter.convert_constraints_extraction_to_rdf(raw_data, case_id)
            elif entity_type == 'capabilities':
                rdf_converter.convert_capabilities_extraction_to_rdf(raw_data, case_id)

            rdf_data = rdf_converter.get_temporary_triples()
            TemporaryRDFStorage.store_extraction_results(
                case_id=case_id,
                extraction_session_id=session_id,
                extraction_type=entity_type,
                rdf_data=rdf_data,
                extraction_model='claude-sonnet-4-20250514'
            )
            logger.info(f"Stored {entity_type} RDF entities for case {case_id}, session {session_id}")
    except Exception as e:
        logger.warning(f"Could not store {entity_type} RDF: {e}")

    return {
        'classes': len(classes),
        'individuals': len(individuals),
        'raw_response': raw_response
    }


def _parse_raw_response(raw_response: str) -> dict:
    """Parse raw LLM response JSON, handling mixed text/JSON responses."""
    try:
        return json.loads(raw_response)
    except json.JSONDecodeError:
        # Try to extract JSON from mixed response
        json_match = re.search(r'\{[\s\S]*\}', raw_response)
        if json_match:
            return json.loads(json_match.group())
        raise ValueError("Could not extract JSON from LLM response")


def get_extractor_class(entity_type: str):
    """Get the extractor class for an entity type."""
    if entity_type == 'roles':
        from app.services.extraction.dual_role_extractor import DualRoleExtractor
        return DualRoleExtractor
    elif entity_type == 'states':
        from app.services.extraction.dual_states_extractor import DualStatesExtractor
        return DualStatesExtractor
    elif entity_type == 'resources':
        from app.services.extraction.dual_resources_extractor import DualResourcesExtractor
        return DualResourcesExtractor
    elif entity_type == 'principles':
        from app.services.extraction.dual_principles_extractor import DualPrinciplesExtractor
        return DualPrinciplesExtractor
    elif entity_type == 'obligations':
        from app.services.extraction.dual_obligations_extractor import DualObligationsExtractor
        return DualObligationsExtractor
    elif entity_type == 'constraints':
        from app.services.extraction.dual_constraints_extractor import DualConstraintsExtractor
        return DualConstraintsExtractor
    elif entity_type == 'capabilities':
        from app.services.extraction.dual_capabilities_extractor import DualCapabilitiesExtractor
        return DualCapabilitiesExtractor
    elif entity_type == 'actions_events':
        from app.services.extraction.dual_actions_events_extractor import DualActionsEventsExtractor
        return DualActionsEventsExtractor
    else:
        raise ValueError(f"Unknown entity type: {entity_type}")


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

        results = {}
        for entity_type in STEP1_ENTITY_TYPES:
            # Update granular status for UI
            run.current_step = f"Extracting {entity_type} from {section_type}"
            db.session.commit()

            logger.info(f"[Task {self.request.id}] Extracting {entity_type} from {section_type}")
            extractor_class = get_extractor_class(entity_type)
            results[entity_type] = run_extraction(
                extractor_class, case_text, run.case_id, section_type, entity_type,
                step_number=1
            )

        run.mark_step_complete(step_name, results)
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

        results = {}
        for entity_type in STEP2_ENTITY_TYPES:
            # Update granular status for UI
            run.current_step = f"Extracting {entity_type} from {section_type}"
            db.session.commit()

            logger.info(f"[Task {self.request.id}] Extracting {entity_type} from {section_type}")
            extractor_class = get_extractor_class(entity_type)
            results[entity_type] = run_extraction(
                extractor_class, case_text, run.case_id, section_type, entity_type,
                step_number=2
            )

        run.mark_step_complete(step_name, results)
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

    Extracts actions and events with temporal relationships.

    Args:
        run_id: PipelineRun ID

    Returns:
        dict with extraction results
    """
    logger.info(f"[Task {self.request.id}] Starting Step 3 for run {run_id}")

    run = PipelineRun.query.get(run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found")

    step_name = "step3"
    run.current_step = step_name
    run.set_status(PIPELINE_STATUS['STEP3'])
    db.session.commit()

    try:
        sections = get_case_sections(run.case_id)
        # Step 3 typically uses combined text or facts
        case_text = sections['facts'] + "\n\n" + sections['discussion']

        extractor_class = get_extractor_class('actions_events')
        results = run_extraction(
            extractor_class, case_text, run.case_id, 'combined', 'actions_events',
            step_number=3
        )

        run.mark_step_complete(step_name, results)
        db.session.commit()

        logger.info(f"[Task {self.request.id}] Step 3 completed: {results}")
        return {'success': True, 'step': step_name, 'results': results}

    except Exception as e:
        logger.error(f"[Task {self.request.id}] Step 3 failed: {e}", exc_info=True)
        run.set_error(str(e), step_name)
        db.session.commit()
        raise


@celery.task(bind=True, name='proethica.tasks.run_full_pipeline')
def run_full_pipeline_task(self, case_id: int, config: dict = None, user_id: int = None):
    """
    Execute complete pipeline for a case.

    Orchestrates all extraction steps in sequence:
    1. Step 1 facts (R, S, Rs)
    2. Step 1 discussion (R, S, Rs)
    3. Step 2 facts (P, O, Cs, Ca)
    4. Step 2 discussion (P, O, Cs, Ca)
    5. Step 3 (A, E)

    Args:
        case_id: Document ID of the case to process
        config: Optional configuration dict
        user_id: Optional user who initiated

    Returns:
        dict with overall results
    """
    config = config or {}
    logger.info(f"[Task {self.request.id}] Starting full pipeline for case {case_id}")

    # Verify case exists
    case = Document.query.get(case_id)
    if not case:
        raise ValueError(f"Case {case_id} not found")

    # Create pipeline run record
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

        # Mark as completed
        run = PipelineRun.query.get(run_id)
        run.set_status(PIPELINE_STATUS['COMPLETED'])
        db.session.commit()

        logger.info(f"[Task {self.request.id}] Full pipeline completed for case {case_id}")

        return {
            'success': True,
            'run_id': run_id,
            'case_id': case_id,
            'steps_completed': run.steps_completed,
            'duration_seconds': run.duration_seconds
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
        logger.info(f"[Task {self.request.id}] Processing queue item {item.id} (case {item.case_id})")

        # Update queue status
        item.status = 'processing'
        item.started_at = datetime.utcnow()
        db.session.commit()

        try:
            # Start pipeline for this case
            result = run_full_pipeline_task.apply(args=[item.case_id])

            # Update queue status
            item.status = 'completed' if result.get('success') else 'failed'
            db.session.commit()

            processed.append({
                'queue_id': item.id,
                'case_id': item.case_id,
                'success': result.get('success', False),
                'run_id': result.get('run_id')
            })

        except Exception as e:
            logger.error(f"[Task {self.request.id}] Queue item {item.id} failed: {e}")
            item.status = 'failed'
            db.session.commit()

            processed.append({
                'queue_id': item.id,
                'case_id': item.case_id,
                'success': False,
                'error': str(e)
            })

    logger.info(f"[Task {self.request.id}] Queue processing complete: {len(processed)} items")
    return {'processed': processed, 'count': len(processed)}
