"""
Enhanced Step 2 implementation with retry logic, partial success, and real-time updates.
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

def serialize_principle_class(candidate):
    """Serialize a principle class candidate to dict"""
    return {
        'label': candidate.label,
        'definition': candidate.definition,
        'type': 'principle_class',
        'confidence': candidate.confidence,
        'abstract_nature': getattr(candidate, 'abstract_nature', ''),
        'value_basis': getattr(candidate, 'value_basis', ''),
        'operationalization': getattr(candidate, 'operationalization', ''),
        'balancing_requirements': getattr(candidate, 'balancing_requirements', []),
    }


def serialize_principle_individual(individual):
    """Serialize a principle individual to dict"""
    return {
        'identifier': individual.identifier,
        'principle_class': individual.principle_class,
        'confidence': individual.confidence,
        'concrete_expression': getattr(individual, 'concrete_expression', ''),
        'invoked_by': getattr(individual, 'invoked_by', []),
        'applied_to': getattr(individual, 'applied_to', []),
        'case_section': getattr(individual, 'case_section', ''),
        'type': 'principle_individual',
    }


def serialize_obligation_class(candidate):
    """Serialize an obligation class candidate to dict"""
    ot = getattr(candidate, 'obligation_type', None)
    el = getattr(candidate, 'enforcement_level', None)
    return {
        'label': candidate.label,
        'definition': candidate.definition,
        'type': 'obligation_class',
        'confidence': candidate.confidence,
        'derived_from_principle': getattr(candidate, 'derived_from_principle', ''),
        'obligation_type': ot.value if hasattr(ot, 'value') else (ot or ''),
        'enforcement_level': el.value if hasattr(el, 'value') else (el or ''),
        'violation_consequences': getattr(candidate, 'violation_consequences', ''),
        'nspe_reference': getattr(candidate, 'nspe_reference', ''),
    }


def serialize_obligation_individual(individual):
    """Serialize an obligation individual to dict"""
    return {
        'identifier': individual.identifier,
        'obligation_class': individual.obligation_class,
        'confidence': individual.confidence,
        'obligated_party': getattr(individual, 'obligated_party', ''),
        'obligation_statement': getattr(individual, 'obligation_statement', ''),
        'derived_from': getattr(individual, 'derived_from', ''),
        'enforcement_context': getattr(individual, 'enforcement_context', ''),
        'type': 'obligation_individual',
    }


def serialize_constraint_class(candidate):
    """Serialize a constraint class candidate to dict"""
    ct = getattr(candidate, 'constraint_type', None)
    fl = getattr(candidate, 'flexibility', None)
    return {
        'label': candidate.label,
        'definition': candidate.definition,
        'type': 'constraint_class',
        'confidence': candidate.confidence,
        'constraint_type': ct.value if hasattr(ct, 'value') else (ct or ''),
        'flexibility': fl.value if hasattr(fl, 'value') else (fl or ''),
        'violation_impact': getattr(candidate, 'violation_impact', ''),
        'mitigation_strategies': getattr(candidate, 'mitigation_strategies', []),
    }


def serialize_constraint_individual(individual):
    """Serialize a constraint individual to dict"""
    sv = getattr(individual, 'severity', None)
    return {
        'identifier': individual.identifier,
        'constraint_class': individual.constraint_class,
        'confidence': individual.confidence,
        'constrained_entity': getattr(individual, 'constrained_entity', ''),
        'constraint_statement': getattr(individual, 'constraint_statement', ''),
        'source': getattr(individual, 'source', ''),
        'severity': sv.value if hasattr(sv, 'value') else (sv or ''),
        'type': 'constraint_individual',
    }


def serialize_capability_class(candidate):
    """Serialize a capability class candidate to dict"""
    cc = getattr(candidate, 'capability_category', None)
    sl = getattr(candidate, 'skill_level', None)
    return {
        'label': candidate.label,
        'definition': candidate.definition,
        'type': 'capability_class',
        'confidence': candidate.confidence,
        'capability_category': cc.value if hasattr(cc, 'value') else (cc or ''),
        'skill_level': sl.value if hasattr(sl, 'value') else (sl or ''),
        'enables_actions': getattr(candidate, 'enables_actions', []),
        'required_for_obligations': getattr(candidate, 'required_for_obligations', []),
    }


def serialize_capability_individual(individual):
    """Serialize a capability individual to dict"""
    pl = getattr(individual, 'proficiency_level', None)
    return {
        'identifier': individual.identifier,
        'capability_class': individual.capability_class,
        'confidence': individual.confidence,
        'possessed_by': getattr(individual, 'possessed_by', ''),
        'capability_statement': getattr(individual, 'capability_statement', ''),
        'proficiency_level': pl.value if hasattr(pl, 'value') else (pl or ''),
        'demonstrated_through': getattr(individual, 'demonstrated_through', ''),
        'type': 'capability_individual',
    }


# Serializer dispatch -- maps concept_type to (class_serializer, individual_serializer)
SERIALIZERS = {
    'principles': (serialize_principle_class, serialize_principle_individual),
    'obligations': (serialize_obligation_class, serialize_obligation_individual),
    'constraints': (serialize_constraint_class, serialize_constraint_individual),
    'capabilities': (serialize_capability_class, serialize_capability_individual),
}


def _serialize_result_for_sse(concept_type: str, extraction: ExtractionResult) -> dict:
    """Serialize an ExtractionResult into the SSE data payload."""
    class_fn, ind_fn = SERIALIZERS[concept_type]
    return {
        'classes': [class_fn(c) for c in extraction.classes],
        'individuals': [ind_fn(i) for i in extraction.individuals],
    }


# --- Core extraction wrapper (provenance-aware) ---

def extract_concept_type(concept_type: str, section_text: str, case_id: int,
                         session_id: str, prov_service=None,
                         section_type: str = 'discussion') -> Dict[str, Any]:
    """
    Extract a single concept type with error handling and retry logic.
    Delegates to the shared concept_extraction_service.
    """
    result = {
        'type': concept_type,
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
                activity_name=f'dual_{concept_type}_extraction',
                case_id=case_id,
                session_id=session_id,
                agent_type='extraction_service',
                agent_name='UnifiedDualExtractor',
            ) as activity:
                extraction = extract_concept_with_retry(
                    case_text=section_text,
                    case_id=case_id,
                    concept_type=concept_type,
                    section_type=section_type,
                    step_number=2,
                    session_id=session_id,
                )
                prov_service.record_extraction_results(
                    results=[{
                        'label': c.label,
                        'definition': c.definition,
                        'confidence': c.confidence,
                        'type': f'{concept_type}_class',
                    } for c in extraction.classes],
                    activity=activity,
                    entity_type=f'extracted_{concept_type}_classes',
                    metadata={'count': len(extraction.classes)},
                )
        else:
            extraction = extract_concept_with_retry(
                case_text=section_text,
                case_id=case_id,
                concept_type=concept_type,
                section_type=section_type,
                step_number=2,
                session_id=session_id,
            )

        result['data'] = _serialize_result_for_sse(concept_type, extraction)
        result['prompt_text'] = extraction.prompt_text
        result['raw_response'] = extraction.raw_response
        result['success'] = True

    except Exception as e:
        logger.error(f"Failed to extract {concept_type} after retries: {e}")
        result['error'] = str(e)

    result['extraction_time'] = time.time() - start_time
    return result


# --- SSE streaming endpoint ---

def normative_pass_execute_streaming(case_id: int):
    """
    Execute normative pass with streaming updates for real-time UI feedback.
    Uses Server-Sent Events (SSE) to stream progress.
    """
    from app.models import Document
    from app.routes.scenario_pipeline.step2 import _resolve_section_text

    req_section_type = request.json.get('section_type', 'facts') if request.json else 'facts'
    case = Document.query.get(case_id)
    req_section_text = _resolve_section_text(case, req_section_type) if case else None

    def generate():
        try:
            section_type = req_section_type
            section_text = req_section_text
            if not section_text:
                yield f"data: {json.dumps({'error': f'No {section_type} section found for case {case_id}'})}\n\n"
                return

            logger.info(f"Starting streaming normative pass execution for case {case_id}, section={section_type}")

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
                    workflow_name='step2_extraction_streaming',
                    description='Enhanced normative pass with retry and streaming',
                    version_tag='enhanced_streaming',
                    auto_version=True,
                )

            all_results = []
            concept_types = ['principles', 'obligations', 'constraints', 'capabilities']

            with version_context:
                with prov.track_activity(
                    activity_type='extraction',
                    activity_name='normative_pass_step2_streaming',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='proethica_normative_pass_streaming',
                ) as main_activity:

                    # Stage 1-2: P then O (sequential, dependency chain)
                    sequential_concepts = ['principles', 'obligations']
                    for idx, concept_type in enumerate(sequential_concepts):
                        yield f"data: {json.dumps({
                            'status': 'extracting',
                            'current': concept_type,
                            'progress': idx,
                            'total': len(concept_types),
                        })}\n\n"

                        result = extract_concept_type(
                            concept_type=concept_type,
                            section_text=section_text,
                            case_id=case_id,
                            session_id=session_id,
                            prov_service=prov,
                            section_type=section_type,
                        )

                        all_results.append(result)

                        yield f"data: {json.dumps({
                            'status': 'extracted',
                            'concept_type': concept_type,
                            'result': result,
                            'progress': idx + 1,
                            'total': len(concept_types),
                        })}\n\n"

                    # Stage 3: Cs + Ca in parallel -- both depend on O
                    # but are independent of each other.
                    parallel_concepts = ['constraints', 'capabilities']

                    # Signal both starting (spinners appear simultaneously)
                    for concept_type in parallel_concepts:
                        yield f"data: {json.dumps({
                            'status': 'extracting',
                            'current': concept_type,
                            'progress': 2,
                            'total': len(concept_types),
                        })}\n\n"

                    app = current_app._get_current_object()

                    def _extract_in_context(ct):
                        with app.app_context():
                            return extract_concept_type(
                                concept_type=ct,
                                section_text=section_text,
                                case_id=case_id,
                                session_id=session_id,
                                prov_service=None,
                                section_type=section_type,
                            )

                    with ThreadPoolExecutor(max_workers=2) as executor:
                        futures = {
                            executor.submit(_extract_in_context, ct): ct
                            for ct in parallel_concepts
                        }
                        completed = 2  # P and O already done
                        for future in as_completed(futures):
                            concept_type = futures[future]
                            try:
                                result = future.result()
                            except Exception as e:
                                logger.error(
                                    f"Unexpected error extracting {concept_type}: {e}"
                                )
                                result = {
                                    'type': concept_type,
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
                                'concept_type': concept_type,
                                'result': result,
                                'progress': completed,
                                'total': len(concept_types),
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
            logger.error(f"Error in streaming normative pass: {e}")
            yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')
