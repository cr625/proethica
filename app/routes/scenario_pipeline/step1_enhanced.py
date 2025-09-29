"""
Enhanced Step 1 implementation with retry logic, partial success, and real-time updates.
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


def extract_entity_type(entity_type: str, section_text: str, case_id: int,
                        session_id: str, prov_service=None) -> Dict[str, Any]:
    """
    Extract a single entity type with error handling and retry logic.
    Returns a result dict with success status and data.
    """
    result = {
        'type': entity_type,
        'success': False,
        'data': None,
        'error': None,
        'retry_count': 0,
        'extraction_time': 0
    }

    start_time = time.time()

    try:
        if entity_type == 'roles':
            from app.services.extraction.dual_role_extractor import DualRoleExtractor
            extractor = DualRoleExtractor()

            # Track extraction with provenance if available
            if prov_service:
                with prov_service.track_activity(
                    activity_type='llm_query',
                    activity_name='dual_roles_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='DualRoleExtractor'
                ) as activity:
                    candidate_classes, individuals = extract_with_retry(
                        extractor.extract_dual_roles,
                        case_text=section_text,
                        case_id=case_id,
                        section_type='facts'
                    )

                    # Record results
                    prov_service.record_extraction_results(
                        results=[{
                            'label': c.label,
                            'definition': c.definition,
                            'confidence': c.discovery_confidence,
                            'type': 'role_class'
                        } for c in candidate_classes],
                        activity=activity,
                        entity_type='extracted_role_classes',
                        metadata={'count': len(candidate_classes)}
                    )
            else:
                candidate_classes, individuals = extract_with_retry(
                    extractor.extract_dual_roles,
                    case_text=section_text,
                    case_id=case_id,
                    section_type='facts'
                )

            result['data'] = {
                'classes': [serialize_role_class(c) for c in candidate_classes],
                'individuals': [serialize_role_individual(i) for i in individuals]
            }
            result['success'] = True

        elif entity_type == 'resources':
            from app.services.extraction.resources import ResourcesExtractor
            extractor = ResourcesExtractor()

            if prov_service:
                with prov_service.track_activity(
                    activity_type='llm_query',
                    activity_name='resources_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='ResourcesExtractor'
                ) as activity:
                    candidates = extract_with_retry(
                        extractor.extract,
                        section_text,
                        guideline_id=case_id,
                        activity=activity
                    )
            else:
                candidates = extract_with_retry(
                    extractor.extract,
                    section_text,
                    guideline_id=case_id,
                    activity=None
                )

            result['data'] = {
                'resources': [serialize_resource(c) for c in candidates]
            }
            result['success'] = True

        elif entity_type == 'states':
            from app.services.extraction.enhanced_prompts_states_capabilities import EnhancedStatesExtractor
            from app.utils.llm_utils import get_llm_client

            llm_client = get_llm_client()
            extractor = EnhancedStatesExtractor(llm_client=llm_client, provenance_service=prov_service)

            if prov_service:
                with prov_service.track_activity(
                    activity_type='llm_query',
                    activity_name='states_extraction',
                    case_id=case_id,
                    session_id=session_id,
                    agent_type='extraction_service',
                    agent_name='EnhancedStatesExtractor'
                ) as activity:
                    candidates = extract_with_retry(
                        extractor.extract,
                        section_text,
                        context={'case_id': case_id},
                        activity=activity
                    )
            else:
                candidates = extract_with_retry(
                    extractor.extract,
                    section_text,
                    context={'case_id': case_id},
                    activity=None
                )

            result['data'] = {
                'states': [serialize_state(c) for c in candidates]
            }
            result['success'] = True

    except Exception as e:
        logger.error(f"Failed to extract {entity_type} after retries: {str(e)}")
        result['error'] = str(e)
        # Check how many retries were attempted
        if hasattr(e, '__cause__'):
            result['retry_count'] = RETRY_ATTEMPTS

    result['extraction_time'] = time.time() - start_time
    return result


def serialize_role_class(candidate):
    """Serialize a role class candidate to dict"""
    return {
        'label': candidate.label,
        'definition': candidate.definition,
        'type': 'role_class',
        'confidence': candidate.discovery_confidence,
        'distinguishing_features': candidate.distinguishing_features,
        'professional_scope': candidate.professional_scope,
        'typical_qualifications': candidate.typical_qualifications,
        'examples_from_case': candidate.examples_from_case,
        'is_novel': candidate.is_novel
    }


def serialize_role_individual(individual):
    """Serialize a role individual to dict"""
    return {
        'name': individual.name,
        'role_class': individual.role_class,
        'confidence': individual.confidence,
        'is_new_role_class': individual.is_new_role_class,
        'attributes': individual.attributes,
        'relationships': individual.relationships,
        'case_section': individual.case_section,
        'type': 'role_individual'
    }


def serialize_resource(candidate):
    """Serialize a resource candidate to dict"""
    debug_data = candidate.debug or {}
    return {
        'label': candidate.label,
        'description': candidate.description,
        'type': candidate.primary_type,
        'confidence': candidate.confidence,
        'resource_category': debug_data.get('resource_category'),
        'extensional_function': debug_data.get('extensional_function'),
        'professional_knowledge_type': debug_data.get('professional_knowledge_type'),
        'usage_context': debug_data.get('usage_context', []),
        'authority_level': debug_data.get('authority_level')
    }


def serialize_state(candidate):
    """Serialize a state candidate to dict"""
    debug_data = candidate.debug or {}
    return {
        'label': candidate.label,
        'description': candidate.description,
        'type': candidate.primary_type,
        'confidence': candidate.confidence,
        'state_category': debug_data.get('state_category'),
        'persistence_type': debug_data.get('persistence_type'),
        'temporal_aspect': debug_data.get('temporal_aspect')
    }


def entities_pass_execute_streaming(case_id: int):
    """
    Execute entities pass with streaming updates for real-time UI feedback.
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

            logger.info(f"Starting streaming entities pass execution for case {case_id}")

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
                    workflow_name='step1_extraction_streaming',
                    description='Enhanced entities pass with retry and streaming',
                    version_tag='enhanced_streaming',
                    auto_version=True
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
                    agent_name='proethica_entities_pass_streaming'
                ) as main_activity:

                    # Extract each entity type sequentially with updates
                    for idx, entity_type in enumerate(entity_types):
                        # Send extraction starting event
                        yield f"data: {json.dumps({
                            'status': 'extracting',
                            'current': entity_type,
                            'progress': idx,
                            'total': len(entity_types)
                        })}\n\n"

                        # Extract with retry logic
                        result = extract_entity_type(
                            entity_type=entity_type,
                            section_text=section_text,
                            case_id=case_id,
                            session_id=session_id,
                            prov_service=prov
                        )

                        all_results.append(result)

                        # Send extraction complete event with data
                        yield f"data: {json.dumps({
                            'status': 'extracted',
                            'entity_type': entity_type,
                            'result': result,
                            'progress': idx + 1,
                            'total': len(entity_types)
                        })}\n\n"

            # Commit provenance records
            db.session.commit()

            # Send final complete event
            summary = {
                'total_success': sum(1 for r in all_results if r['success']),
                'total_failed': sum(1 for r in all_results if not r['success']),
                'total_entities': sum(
                    len(r['data'].get('classes', []) +
                        r['data'].get('individuals', []) +
                        r['data'].get('resources', []) +
                        r['data'].get('states', []))
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
            logger.error(f"Error in streaming entities pass: {str(e)}")
            yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream')