"""
Enhanced Step 2 implementation with retry logic, partial success, and real-time updates.
"""
import json
import uuid
import time
from typing import Dict, Any, Optional, List
from flask import jsonify, request, Response
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.models import db
from app.utils import logger
from contextlib import nullcontext

# Retry configuration
RETRY_ATTEMPTS = 3
RETRY_MIN_WAIT = 2  # seconds
RETRY_MAX_WAIT = 10  # seconds


class ExtractionTimeoutError(Exception):
    """Custom exception for extraction timeouts"""
    pass


@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
    retry=retry_if_exception_type((ExtractionTimeoutError, ConnectionError))
)
def extract_with_retry(extractor_func, *args, **kwargs):
    """
    Wrapper function to add retry logic to any extractor.
    """
    try:
        return extractor_func(*args, **kwargs)
    except Exception as e:
        logger.warning(f"Extraction attempt failed: {str(e)}")
        # Check if it's a timeout or connection error
        if "timeout" in str(e).lower() or "connection" in str(e).lower():
            raise ExtractionTimeoutError(str(e))
        raise


def extract_concept_type(concept_type: str, section_text: str, case_id: int,
                         session_id: str, prov_service=None) -> Dict[str, Any]:
    """
    Extract a single concept type with error handling and retry logic.
    Returns a result dict with success status and data.
    """
    result = {
        'type': concept_type,
        'success': False,
        'data': None,
        'error': None,
        'retry_count': 0,
        'extraction_time': 0
    }

    start_time = time.time()

    try:
        if concept_type == 'principles':
            from app.services.extraction.dual_principles_extractor import DualPrinciplesExtractor
            extractor = DualPrinciplesExtractor()

            # Track extraction with provenance if available
            if prov_service:
                with prov_service.track_activity(
                    activity_type='llm_query',
                    activity_name='dual_principles_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='DualPrinciplesExtractor'
                ) as activity:
                    candidate_classes, individuals = extract_with_retry(
                        extractor.extract_dual_principles,
                        case_text=section_text,
                        case_id=case_id,
                        section_type='discussion'
                    )

                    # Record results
                    prov_service.record_extraction_results(
                        results=[{
                            'label': c.label,
                            'definition': c.definition,
                            'confidence': c.confidence,
                            'type': 'principle_class'
                        } for c in candidate_classes],
                        activity=activity,
                        entity_type='extracted_principle_classes',
                        metadata={'count': len(candidate_classes)}
                    )
            else:
                candidate_classes, individuals = extract_with_retry(
                    extractor.extract_dual_principles,
                    case_text=section_text,
                    case_id=case_id,
                    section_type='discussion'
                )

            result['data'] = {
                'classes': [serialize_principle_class(c) for c in candidate_classes],
                'individuals': [serialize_principle_individual(i) for i in individuals]
            }
            result['success'] = True

        elif concept_type == 'obligations':
            from app.services.extraction.dual_obligations_extractor import DualObligationsExtractor
            extractor = DualObligationsExtractor()

            if prov_service:
                with prov_service.track_activity(
                    activity_type='llm_query',
                    activity_name='dual_obligations_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='DualObligationsExtractor'
                ) as activity:
                    candidates = extract_with_retry(
                        extractor.extract_dual_obligations,
                        case_text=section_text,
                        case_id=case_id,
                        section_type='discussion'
                    )
                    candidate_classes, individuals = candidates
            else:
                candidate_classes, individuals = extract_with_retry(
                    extractor.extract_dual_obligations,
                    case_text=section_text,
                    case_id=case_id,
                    section_type='discussion'
                )

            result['data'] = {
                'classes': [serialize_obligation_class(c) for c in candidate_classes],
                'individuals': [serialize_obligation_individual(i) for i in individuals]
            }
            result['success'] = True

        elif concept_type == 'constraints':
            from app.services.extraction.dual_constraints_extractor import DualConstraintsExtractor
            extractor = DualConstraintsExtractor()

            if prov_service:
                with prov_service.track_activity(
                    activity_type='llm_query',
                    activity_name='dual_constraints_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='DualConstraintsExtractor'
                ) as activity:
                    candidates = extract_with_retry(
                        extractor.extract_dual_constraints,
                        case_text=section_text,
                        case_id=case_id,
                        section_type='discussion'
                    )
                    candidate_classes, individuals = candidates
            else:
                candidate_classes, individuals = extract_with_retry(
                    extractor.extract_dual_constraints,
                    case_text=section_text,
                    case_id=case_id,
                    section_type='discussion'
                )

            result['data'] = {
                'classes': [serialize_constraint_class(c) for c in candidate_classes],
                'individuals': [serialize_constraint_individual(i) for i in individuals]
            }
            result['success'] = True

        elif concept_type == 'capabilities':
            from app.services.extraction.dual_capabilities_extractor import DualCapabilitiesExtractor
            extractor = DualCapabilitiesExtractor()

            if prov_service:
                with prov_service.track_activity(
                    activity_type='llm_query',
                    activity_name='dual_capabilities_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='DualCapabilitiesExtractor'
                ) as activity:
                    candidates = extract_with_retry(
                        extractor.extract_dual_capabilities,
                        case_text=section_text,
                        case_id=case_id,
                        section_type='discussion'
                    )
                    candidate_classes, individuals = candidates
            else:
                candidate_classes, individuals = extract_with_retry(
                    extractor.extract_dual_capabilities,
                    case_text=section_text,
                    case_id=case_id,
                    section_type='discussion'
                )

            result['data'] = {
                'classes': [serialize_capability_class(c) for c in candidate_classes],
                'individuals': [serialize_capability_individual(i) for i in individuals]
            }
            result['success'] = True

    except Exception as e:
        logger.error(f"Failed to extract {concept_type} after retries: {str(e)}")
        result['error'] = str(e)
        # Check how many retries were attempted
        if hasattr(e, '__cause__'):
            result['retry_count'] = RETRY_ATTEMPTS

    result['extraction_time'] = time.time() - start_time
    return result


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
        'balancing_requirements': getattr(candidate, 'balancing_requirements', [])
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
        'type': 'principle_individual'
    }


def serialize_obligation_class(candidate):
    """Serialize an obligation class candidate to dict"""
    return {
        'label': candidate.label,
        'definition': candidate.definition,
        'type': 'obligation_class',
        'confidence': candidate.confidence,
        'derived_from_principle': getattr(candidate, 'derived_from_principle', ''),
        'duty_type': getattr(candidate, 'duty_type', ''),
        'enforcement_mechanism': getattr(candidate, 'enforcement_mechanism', ''),
        'violation_consequences': getattr(candidate, 'violation_consequences', '')
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
        'type': 'obligation_individual'
    }


def serialize_constraint_class(candidate):
    """Serialize a constraint class candidate to dict"""
    return {
        'label': candidate.label,
        'definition': candidate.definition,
        'type': 'constraint_class',
        'confidence': candidate.confidence,
        'constraint_type': getattr(candidate, 'constraint_type', ''),
        'flexibility': getattr(candidate, 'flexibility', ''),
        'violation_impact': getattr(candidate, 'violation_impact', ''),
        'mitigation_possible': getattr(candidate, 'mitigation_possible', False)
    }


def serialize_constraint_individual(individual):
    """Serialize a constraint individual to dict"""
    return {
        'identifier': individual.identifier,
        'constraint_class': individual.constraint_class,
        'confidence': individual.confidence,
        'constrained_entity': getattr(individual, 'constrained_entity', ''),
        'constraint_statement': getattr(individual, 'constraint_statement', ''),
        'source': getattr(individual, 'source', ''),
        'enforcement_mechanism': getattr(individual, 'enforcement_mechanism', ''),
        'type': 'constraint_individual'
    }


def serialize_capability_class(candidate):
    """Serialize a capability class candidate to dict"""
    return {
        'label': candidate.label,
        'definition': candidate.definition,
        'type': 'capability_class',
        'confidence': candidate.confidence,
        'capability_type': getattr(candidate, 'capability_type', ''),
        'skill_level': getattr(candidate, 'skill_level', ''),
        'acquisition_method': getattr(candidate, 'acquisition_method', ''),
        'norm_competence_related': getattr(candidate, 'norm_competence_related', False)
    }


def serialize_capability_individual(individual):
    """Serialize a capability individual to dict"""
    return {
        'identifier': individual.identifier,
        'capability_class': individual.capability_class,
        'confidence': individual.confidence,
        'possessed_by': getattr(individual, 'possessed_by', ''),
        'capability_statement': getattr(individual, 'capability_statement', ''),
        'proficiency_level': getattr(individual, 'proficiency_level', ''),
        'application_context': getattr(individual, 'application_context', ''),
        'type': 'capability_individual'
    }


def normative_pass_execute_streaming(case_id: int):
    """
    Execute normative pass with streaming updates for real-time UI feedback.
    Uses Server-Sent Events (SSE) to stream progress.
    """
    def generate():
        """Generator function for SSE streaming"""
        try:
            # Get request data
            section_text = request.json.get('section_text')
            if not section_text:
                yield f"data: {json.dumps({'error': 'section_text is required'})}\n\n"
                return

            logger.info(f"Starting streaming normative pass execution for case {case_id}")

            # Initialize provenance tracking
            from app.services.provenance_service import get_provenance_service
            try:
                from app.services.provenance_versioning_service import get_versioned_provenance_service
                prov = get_versioned_provenance_service(session=db.session)
                USE_VERSIONED = True
            except ImportError:
                prov = get_provenance_service(session=db.session)
                USE_VERSIONED = False

            session_id = str(uuid.uuid4())

            # Send initial status
            yield f"data: {json.dumps({'status': 'starting', 'session_id': session_id})}\n\n"

            # Track versioned workflow if available
            version_context = nullcontext()
            if USE_VERSIONED:
                version_context = prov.track_versioned_workflow(
                    workflow_name='step2_extraction_streaming',
                    description='Enhanced normative pass with retry and streaming',
                    version_tag='enhanced_streaming',
                    auto_version=True
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
                    agent_name='proethica_normative_pass_streaming'
                ) as main_activity:

                    # Extract each concept type sequentially with updates
                    for idx, concept_type in enumerate(concept_types):
                        # Send extraction starting event
                        yield f"data: {json.dumps({
                            'status': 'extracting',
                            'current': concept_type,
                            'progress': idx,
                            'total': len(concept_types)
                        })}\n\n"

                        # Extract with retry logic
                        result = extract_concept_type(
                            concept_type=concept_type,
                            section_text=section_text,
                            case_id=case_id,
                            session_id=session_id,
                            prov_service=prov
                        )

                        all_results.append(result)

                        # Send extraction complete event with data
                        yield f"data: {json.dumps({
                            'status': 'extracted',
                            'concept_type': concept_type,
                            'result': result,
                            'progress': idx + 1,
                            'total': len(concept_types)
                        })}\n\n"

            # Commit provenance records
            db.session.commit()

            # Send final complete event
            summary = {
                'total_success': sum(1 for r in all_results if r['success']),
                'total_failed': sum(1 for r in all_results if not r['success']),
                'total_entities': sum(
                    len(r['data'].get('classes', []) +
                        r['data'].get('individuals', []))
                    for r in all_results if r['success'] and r['data']
                )
            }

            yield f"data: {json.dumps({
                'status': 'complete',
                'summary': summary,
                'results': all_results,
                'session_id': session_id
            })}\n\n"

        except Exception as e:
            logger.error(f"Error in streaming normative pass: {str(e)}")
            yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream')