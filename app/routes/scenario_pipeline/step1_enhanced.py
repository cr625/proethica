"""
Enhanced Step 1 implementation with retry logic, partial success, and real-time updates.
"""
import json
import uuid
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any
from flask import current_app, request, Response, stream_with_context
from app.models import db
import logging
logger = logging.getLogger(__name__)
from contextlib import nullcontext

from app.services.extraction.concept_extraction_service import (
    extract_concept_with_retry,
    ExtractionResult,
)


# --- Serializer functions (concept-specific UI display formatting) ---

def _serialize_field(obj, field, default=None):
    """Get a field from a Pydantic model or dataclass, converting nested models to dicts."""
    val = getattr(obj, field, default)
    if hasattr(val, 'model_dump'):
        return val.model_dump()
    if hasattr(val, 'value'):  # Enum
        return val.value
    return val


def serialize_role_class(candidate):
    """Serialize a role class candidate to dict"""
    return {
        'label': candidate.label,
        'definition': getattr(candidate, 'definition', ''),
        'type': 'role_class',
        'confidence': getattr(candidate, 'confidence', 0.0),
        'role_category': _serialize_field(candidate, 'role_category'),
        'distinguishing_features': getattr(candidate, 'distinguishing_features', []),
        'professional_scope': getattr(candidate, 'professional_scope', None),
        'obligations_generated': getattr(candidate, 'obligations_generated', []),
        'text_references': getattr(candidate, 'text_references', getattr(candidate, 'examples_from_case', [])),
        'match_decision': _serialize_field(candidate, 'match_decision'),
    }


def serialize_role_individual(individual):
    """Serialize a role individual to dict"""
    return {
        'name': getattr(individual, 'name', ''),
        'role_class': getattr(individual, 'role_class', ''),
        'confidence': getattr(individual, 'confidence', 0.0),
        'attributes': getattr(individual, 'attributes', {}),
        'relationships': getattr(individual, 'relationships', []),
        'case_involvement': getattr(individual, 'case_involvement', None),
        'type': 'role_individual'
    }


def serialize_state_class(candidate):
    """Serialize a CandidateStateClass Pydantic model to dict."""
    return {
        'label': candidate.label,
        'definition': candidate.definition,
        'type': 'state_class',
        'confidence': candidate.confidence,
        'state_category': candidate.state_category.value if candidate.state_category else None,
        'persistence_type': candidate.persistence_type.value if candidate.persistence_type else 'inertial',
        'activation_conditions': candidate.activation_conditions,
        'termination_conditions': candidate.termination_conditions,
        'obligation_activation': candidate.obligation_activation,
        'action_constraints': candidate.action_constraints,
        'text_references': candidate.text_references,
        'importance': candidate.importance,
    }


def serialize_state_individual(individual):
    """Serialize a StateIndividual Pydantic model to dict."""
    return {
        'label': individual.identifier or individual.name,
        'definition': getattr(individual, 'definition', '') or '',
        'type': 'state_individual',
        'confidence': individual.confidence,
        'state_class': individual.state_class,
        'subject': individual.subject,
        'active_period': individual.active_period,
        'triggering_event': individual.triggering_event,
        'terminated_by': individual.terminated_by,
        'affected_parties': individual.affected_parties,
        'urgency_level': individual.urgency_level.value if individual.urgency_level else None,
    }


def serialize_resource_class(candidate):
    """Serialize a CandidateResourceClass Pydantic model to dict."""
    return {
        'label': candidate.label,
        'definition': candidate.definition,
        'type': 'resource_class',
        'confidence': candidate.confidence,
        'resource_category': candidate.resource_category.value if candidate.resource_category else None,
        'authority_source': candidate.authority_source,
        'extensional_function': candidate.extensional_function,
        'usage_context': candidate.usage_context,
        'text_references': candidate.text_references,
        'importance': candidate.importance,
    }


def serialize_resource_individual(individual):
    """Serialize a ResourceIndividual Pydantic model to dict."""
    return {
        'label': individual.identifier or individual.name,
        'definition': getattr(individual, 'definition', '') or '',
        'type': 'resource_individual',
        'confidence': individual.confidence,
        'resource_class': individual.resource_class,
        'document_title': individual.document_title,
        'created_by': individual.created_by,
        'version': individual.version,
        'used_by': individual.used_by,
        'used_in_context': individual.used_in_context,
    }


# Serializer dispatch -- maps concept_type to (class_serializer, individual_serializer)
SERIALIZERS = {
    'roles': (serialize_role_class, serialize_role_individual),
    'states': (serialize_state_class, serialize_state_individual),
    'resources': (serialize_resource_class, serialize_resource_individual),
}


def _serialize_result_for_sse(entity_type: str, extraction: ExtractionResult) -> dict:
    """Serialize an ExtractionResult into the SSE data payload."""
    class_fn, ind_fn = SERIALIZERS[entity_type]
    return {
        'classes': [class_fn(c) for c in extraction.classes],
        'individuals': [ind_fn(i) for i in extraction.individuals],
    }


# --- Core extraction wrapper (provenance-aware) ---

def extract_entity_type(entity_type: str, section_text: str, case_id: int,
                        session_id: str, prov_service=None,
                        section_type: str = 'facts') -> Dict[str, Any]:
    """
    Extract a single entity type with error handling and retry logic.
    Delegates to the shared concept_extraction_service.
    """
    result = {
        'type': entity_type,
        'success': False,
        'data': None,
        'error': None,
        'retry_count': 0,
        'extraction_time': 0,
    }

    start_time = time.time()

    try:
        if prov_service:
            with prov_service.track_activity(
                activity_type='llm_query',
                activity_name=f'dual_{entity_type}_extraction',
                case_id=case_id,
                session_id=session_id,
                agent_type='extraction_service',
                agent_name='UnifiedDualExtractor',
            ) as activity:
                extraction = extract_concept_with_retry(
                    case_text=section_text,
                    case_id=case_id,
                    concept_type=entity_type,
                    section_type=section_type,
                    step_number=1,
                    session_id=session_id,
                )
                prov_service.record_extraction_results(
                    results=[{
                        'label': c.label,
                        'definition': c.definition,
                        'confidence': c.confidence,
                        'type': f'{entity_type}_class',
                    } for c in extraction.classes],
                    activity=activity,
                    entity_type=f'extracted_{entity_type}_classes',
                    metadata={'count': len(extraction.classes)},
                )
        else:
            extraction = extract_concept_with_retry(
                case_text=section_text,
                case_id=case_id,
                concept_type=entity_type,
                section_type=section_type,
                step_number=1,
                session_id=session_id,
            )

        result['data'] = _serialize_result_for_sse(entity_type, extraction)
        result['prompt_text'] = extraction.prompt_text
        result['raw_response'] = extraction.raw_response
        result['success'] = True

    except Exception as e:
        logger.error(f"Failed to extract {entity_type} after retries: {e}")
        result['error'] = str(e)

    result['extraction_time'] = time.time() - start_time
    return result


# --- SSE streaming endpoint ---

def entities_pass_execute_streaming(case_id: int):
    """
    Execute entities pass with streaming updates for real-time UI feedback.
    Uses Server-Sent Events (SSE) to stream progress.
    """
    from app.models import Document
    from app.routes.scenario_pipeline.step2 import _resolve_section_text

    req_section_type = request.json.get('section_type', 'facts') if request.json else 'facts'
    case = Document.query.get(case_id)
    req_section_text = _resolve_section_text(case, req_section_type) if case else None

    def generate():
        try:
            section_text = req_section_text
            if not section_text:
                yield f"data: {json.dumps({'error': 'section_text is required'})}\n\n"
                return

            logger.info(f"Starting streaming entities pass execution for case {case_id}")

            from app.services.provenance_service import get_provenance_service
            try:
                from app.services.provenance_versioning_service import get_versioned_provenance_service
                prov = get_versioned_provenance_service(session=db.session)
                USE_VERSIONED = True
            except ImportError:
                prov = get_provenance_service(session=db.session)
                USE_VERSIONED = False

            session_id = str(uuid.uuid4())

            yield f"data: {json.dumps({'status': 'starting', 'session_id': session_id})}\n\n"

            version_context = nullcontext()
            if USE_VERSIONED:
                version_context = prov.track_versioned_workflow(
                    workflow_name='step1_extraction_streaming',
                    description='Enhanced entities pass with retry and streaming',
                    version_tag='enhanced_streaming',
                    auto_version=True,
                )

            all_results = []
            entity_types = ['roles', 'states', 'resources']

            with version_context:
                with prov.track_activity(
                    activity_type='extraction',
                    activity_name='entities_pass_step1_streaming',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='proethica_entities_pass_streaming',
                ) as main_activity:

                    # Signal all concepts starting (spinners appear simultaneously)
                    for idx, entity_type in enumerate(entity_types):
                        yield f"data: {json.dumps({
                            'status': 'extracting',
                            'current': entity_type,
                            'progress': 0,
                            'total': len(entity_types),
                        })}\n\n"

                    # Run all 3 concepts in parallel -- they have no
                    # cross-concept dependencies (CROSS_CONCEPT_DEPS is
                    # empty for roles, states, resources).
                    app = current_app._get_current_object()

                    def _extract_in_context(et):
                        with app.app_context():
                            return extract_entity_type(
                                entity_type=et,
                                section_text=section_text,
                                case_id=case_id,
                                session_id=session_id,
                                prov_service=None,
                                section_type=req_section_type,
                            )

                    with ThreadPoolExecutor(max_workers=3) as executor:
                        futures = {
                            executor.submit(_extract_in_context, et): et
                            for et in entity_types
                        }
                        completed = 0
                        for future in as_completed(futures):
                            entity_type = futures[future]
                            try:
                                result = future.result()
                            except Exception as e:
                                logger.error(
                                    f"Unexpected error extracting {entity_type}: {e}"
                                )
                                result = {
                                    'type': entity_type,
                                    'success': False,
                                    'data': None,
                                    'error': str(e),
                                    'retry_count': 0,
                                    'extraction_time': 0,
                                }
                            completed += 1
                            all_results.append(result)

                            yield f"data: {json.dumps({
                                'status': 'extracted',
                                'entity_type': entity_type,
                                'result': result,
                                'progress': completed,
                                'total': len(entity_types),
                            })}\n\n"

            db.session.commit()

            summary = {
                'total_success': sum(1 for r in all_results if r['success']),
                'total_failed': sum(1 for r in all_results if not r['success']),
                'total_entities': sum(
                    len(r['data'].get('classes', []) +
                        r['data'].get('individuals', []))
                    for r in all_results if r['success'] and r['data']
                ),
            }

            yield f"data: {json.dumps({
                'status': 'complete',
                'summary': summary,
                'results': all_results,
                'session_id': session_id,
            })}\n\n"

        except Exception as e:
            logger.error(f"Error in streaming entities pass: {e}")
            yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')
