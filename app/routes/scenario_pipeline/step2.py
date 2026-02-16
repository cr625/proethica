"""
Step 2: Normative Requirements Pass for Facts Section
Shows the facts section and provides extraction for Pass 2: Principles, Obligations, Constraints, and Capabilities.
Based on Chapter 2 literature: Capabilities are essential for norm competence (Tolmeijer et al. 2021) - 
agents need capabilities to store, recognize, apply, and resolve normative requirements.
"""

import logging
import json
import uuid
from datetime import datetime
from contextlib import nullcontext
from flask import render_template, request, jsonify, redirect, url_for, flash
from app.models import Document, db
from app.routes.scenario_pipeline.overview import _format_section_for_llm
from app.services.pipeline_status_service import PipelineStatusService
from app.services.extraction.enhanced_prompts_principles import create_enhanced_principles_prompt
from app.services.extraction.enhanced_prompts_obligations import create_enhanced_obligations_prompt
from app.services.extraction.enhanced_prompts_constraints import create_enhanced_constraints_prompt
from app.services.extraction.enhanced_prompts_states_capabilities import create_enhanced_capabilities_prompt

# Import provenance services
try:
    from app.services.provenance_versioning_service import get_versioned_provenance_service
    USE_VERSIONED_PROVENANCE = True
except ImportError:
    from app.services.provenance_service import get_provenance_service
    USE_VERSIONED_PROVENANCE = False

logger = logging.getLogger(__name__)

# Function to exempt specific routes from CSRF after app initialization
def init_step2_csrf_exemption(app):
    """Exempt Step 2 normative pass routes from CSRF protection"""
    if hasattr(app, 'csrf') and app.csrf:
        # Import the route functions that actually get called
        from app.routes.scenario_pipeline.interactive_builder import normative_pass_prompt, normative_pass_execute, step2_extract, step2_extract_individual
        # Exempt the normative pass routes from CSRF protection
        app.csrf.exempt(normative_pass_prompt)
        app.csrf.exempt(normative_pass_execute)
        app.csrf.exempt(step2_extract)
        app.csrf.exempt(step2_extract_individual)

def extract_individual_concept(case_id):
    """
    API endpoint to extract an individual concept type from the normative pass.
    This allows debugging of individual extractors (principles, obligations, constraints, capabilities).
    Supports section_type parameter for multi-section extraction.
    """
    from app import db  # Import db at the start of the function

    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        concept_type = data.get('concept_type')
        section_text = data.get('section_text')  # Get section text from request
        section_type = data.get('section_type', 'facts')  # Default to facts if not provided

        if not concept_type:
            return jsonify({'error': 'concept_type is required'}), 400

        if concept_type not in ['principles', 'obligations', 'constraints', 'capabilities']:
            return jsonify({'error': f'Invalid concept_type: {concept_type}'}), 400

        # Get the case
        case = Document.query.get_or_404(case_id)

        # If section_text was not provided, extract it from case metadata
        if not section_text:
            raw_sections = {}

            if case.doc_metadata:
                # Get sections from metadata
                if 'sections_dual' in case.doc_metadata:
                    raw_sections = case.doc_metadata['sections_dual']
                elif 'sections' in case.doc_metadata:
                    raw_sections = case.doc_metadata['sections']
                elif 'document_structure' in case.doc_metadata and 'sections' in case.doc_metadata['document_structure']:
                    raw_sections = case.doc_metadata['document_structure']['sections']

            # Look for the appropriate section based on section_type
            section_keywords = {
                'facts': 'fact',
                'discussion': 'discussion',
                'questions': 'question',
                'conclusions': 'conclusion',
                'references': 'reference'
            }

            search_keyword = section_keywords.get(section_type, 'fact')

            for section_key, section_content in raw_sections.items():
                if search_keyword in section_key.lower():
                    section_text = _format_section_for_llm(section_key, section_content, case)
                    break

            # If no matching section found, use first available section
            if not section_text and raw_sections:
                first_key = list(raw_sections.keys())[0]
                section_text = _format_section_for_llm(first_key, raw_sections[first_key], case)

            if not section_text:
                # Fallback to using available content
                section_text = case.content or case.description or ""
                if not section_text:
                    return jsonify({'error': f'No {section_type} section found'}), 400

        logger.info(f"Executing individual {concept_type} extraction for case {case_id}, section: {section_type}")

        # Initialize provenance service
        if USE_VERSIONED_PROVENANCE:
            prov = get_versioned_provenance_service()
        else:
            from app.services.provenance_service import get_provenance_service
            prov = get_provenance_service()

        # Create session ID for this extraction
        session_id = str(uuid.uuid4())

        # Perform the extraction based on concept type
        candidates = []
        extraction_prompt = ""
        raw_llm_response = ""
        activity = None

        if concept_type == 'principles':
            from app.services.extraction.unified_dual_extractor import UnifiedDualExtractor
            from models import ModelConfig

            extractor = UnifiedDualExtractor('principles')
            candidate_classes, principle_individuals = extractor.extract(
                case_text=section_text,
                case_id=case_id,
                section_type=section_type
            )
            extraction_prompt = extractor.last_prompt
            raw_llm_response = extractor.last_raw_response

            # Save prompt and response
            from app.models import ExtractionPrompt
            try:
                ExtractionPrompt.save_prompt(
                    case_id=case_id,
                    concept_type='principles',
                    prompt_text=extraction_prompt,
                    raw_response=raw_llm_response,
                    step_number=2,
                    llm_model=extractor.model_name,
                    extraction_session_id=session_id,
                    section_type=section_type
                )
            except Exception as e:
                logger.warning(f"Could not save extraction prompt: {e}")

            # Store Pydantic results directly (bypasses old RDFExtractionConverter)
            try:
                from app.services.extraction.extraction_graph import pydantic_to_rdf_data
                from app.models import TemporaryRDFStorage

                rdf_data = pydantic_to_rdf_data(
                    classes=candidate_classes,
                    individuals=principle_individuals,
                    concept_type='principles',
                    case_id=case_id,
                    section_type=section_type,
                    pass_number=2,
                )
                logger.info(
                    f"Converted Pydantic to rdf_data: "
                    f"{len(rdf_data['new_classes'])} classes, "
                    f"{len(rdf_data['new_individuals'])} individuals"
                )

                stored_entities = TemporaryRDFStorage.store_extraction_results(
                    case_id=case_id,
                    extraction_session_id=session_id,
                    extraction_type='principles',
                    rdf_data=rdf_data,
                    extraction_model=extractor.model_name,
                    provenance_data={
                        'section_type': section_type,
                        'extracted_at': datetime.utcnow().isoformat(),
                        'model_used': extractor.model_name,
                        'extraction_pass': 'normative_requirements',
                        'concept_type': 'principles'
                    }
                )
                logger.info(f"Stored {len(stored_entities)} principle entities for case {case_id}")
                db.session.commit()
            except Exception as e:
                logger.error(f"Failed to store principles entities: {e}")
                import traceback
                logger.error(traceback.format_exc())

            # Convert to candidates format for UI compatibility
            candidates = []
            from app.services.extraction.base import ConceptCandidate
            for cls in candidate_classes:
                candidates.append(ConceptCandidate(
                    label=cls.label,
                    description=cls.definition,
                    primary_type='principle',
                    category='principle',
                    confidence=cls.confidence,
                    debug={
                        'abstract_nature': getattr(cls, 'abstract_nature', ''),
                        'value_basis': getattr(cls, 'value_basis', ''),
                        'extensional_examples': getattr(cls, 'extensional_examples', []),
                        'operationalization': getattr(cls, 'operationalization', ''),
                        'derived_obligations': getattr(cls, 'derived_obligations', []),
                        'potential_conflicts': getattr(cls, 'potential_conflicts', []),
                        'is_class': True
                    }
                ))

            for ind in principle_individuals:
                candidates.append(ConceptCandidate(
                    label=ind.identifier,
                    description=getattr(ind, 'concrete_expression', '') or '',
                    primary_type='principle_instance',
                    category='principle',
                    confidence=ind.confidence,
                    debug={
                        'principle_class': ind.principle_class,
                        'invoked_by': getattr(ind, 'invoked_by', []),
                        'applied_to': getattr(ind, 'applied_to', []),
                        'interpretation': getattr(ind, 'interpretation', ''),
                        'balancing_with': getattr(ind, 'balancing_with', []),
                        'is_individual': True
                    }
                ))

        elif concept_type == 'obligations':
            from app.services.extraction.unified_dual_extractor import UnifiedDualExtractor
            from models import ModelConfig

            extractor = UnifiedDualExtractor('obligations')
            candidate_classes, obligation_individuals = extractor.extract(
                case_text=section_text,
                case_id=case_id,
                section_type=section_type
            )
            extraction_prompt = extractor.last_prompt
            raw_llm_response = extractor.last_raw_response

            from app.models import ExtractionPrompt
            try:
                ExtractionPrompt.save_prompt(
                    case_id=case_id,
                    concept_type='obligations',
                    prompt_text=extraction_prompt,
                    raw_response=raw_llm_response,
                    step_number=2,
                    llm_model=extractor.model_name,
                    extraction_session_id=session_id,
                    section_type=section_type
                )
            except Exception as e:
                logger.warning(f"Could not save extraction prompt: {e}")

            try:
                from app.services.extraction.extraction_graph import pydantic_to_rdf_data
                from app.models import TemporaryRDFStorage

                rdf_data = pydantic_to_rdf_data(
                    classes=candidate_classes,
                    individuals=obligation_individuals,
                    concept_type='obligations',
                    case_id=case_id,
                    section_type=section_type,
                    pass_number=2,
                )
                stored_entities = TemporaryRDFStorage.store_extraction_results(
                    case_id=case_id,
                    extraction_session_id=session_id,
                    extraction_type='obligations',
                    rdf_data=rdf_data,
                    extraction_model=extractor.model_name,
                    provenance_data={
                        'section_type': section_type,
                        'extracted_at': datetime.utcnow().isoformat(),
                        'model_used': extractor.model_name,
                        'extraction_pass': 'normative_requirements',
                        'concept_type': 'obligations'
                    }
                )
                logger.info(f"Stored {len(stored_entities)} obligation entities for case {case_id}")
                db.session.commit()
            except Exception as e:
                logger.error(f"Failed to store obligations entities: {e}")
                import traceback
                logger.error(traceback.format_exc())

            candidates = []
            from app.services.extraction.base import ConceptCandidate
            for obl_class in candidate_classes:
                candidates.append(ConceptCandidate(
                    label=obl_class.label,
                    description=obl_class.definition,
                    primary_type='obligations',
                    category='obligations_class',
                    confidence=obl_class.confidence,
                    debug={
                        'is_class': True,
                        'derived_from_principle': getattr(obl_class, 'derived_from_principle', ''),
                        'obligation_type': getattr(obl_class, 'obligation_type', ''),
                        'enforcement_level': getattr(obl_class, 'enforcement_level', ''),
                        'nspe_reference': getattr(obl_class, 'nspe_reference', ''),
                        'extraction_method': 'unified_extraction'
                    }
                ))

            for individual in obligation_individuals:
                candidates.append(ConceptCandidate(
                    label=individual.identifier,
                    description=getattr(individual, 'obligation_statement', '') or '',
                    primary_type='obligations',
                    category='obligations_individual',
                    confidence=individual.confidence,
                    debug={
                        'is_individual': True,
                        'obligation_class': individual.obligation_class,
                        'obligated_party': getattr(individual, 'obligated_party', ''),
                        'compliance_status': getattr(individual, 'compliance_status', ''),
                        'extraction_method': 'unified_extraction'
                    }
                ))

        elif concept_type == 'constraints':
            from app.services.extraction.unified_dual_extractor import UnifiedDualExtractor
            from models import ModelConfig

            extractor = UnifiedDualExtractor('constraints')
            candidate_classes, constraint_individuals = extractor.extract(
                case_text=section_text,
                case_id=case_id,
                section_type=section_type
            )
            extraction_prompt = extractor.last_prompt
            raw_llm_response = extractor.last_raw_response

            from app.models import ExtractionPrompt
            try:
                ExtractionPrompt.save_prompt(
                    case_id=case_id,
                    concept_type='constraints',
                    prompt_text=extraction_prompt,
                    raw_response=raw_llm_response,
                    step_number=2,
                    llm_model=extractor.model_name,
                    extraction_session_id=session_id,
                    section_type=section_type
                )
            except Exception as e:
                logger.warning(f"Could not save extraction prompt: {e}")

            try:
                from app.services.extraction.extraction_graph import pydantic_to_rdf_data
                from app.models import TemporaryRDFStorage

                rdf_data = pydantic_to_rdf_data(
                    classes=candidate_classes,
                    individuals=constraint_individuals,
                    concept_type='constraints',
                    case_id=case_id,
                    section_type=section_type,
                    pass_number=2,
                )
                stored_entities = TemporaryRDFStorage.store_extraction_results(
                    case_id=case_id,
                    extraction_session_id=session_id,
                    extraction_type='constraints',
                    rdf_data=rdf_data,
                    extraction_model=extractor.model_name,
                    provenance_data={
                        'section_type': section_type,
                        'extracted_at': datetime.utcnow().isoformat(),
                        'model_used': extractor.model_name,
                        'extraction_pass': 'normative_requirements',
                        'concept_type': 'constraints'
                    }
                )
                logger.info(f"Stored {len(stored_entities)} constraint entities for case {case_id}")
                db.session.commit()
            except Exception as e:
                logger.error(f"Failed to store constraints entities: {e}")
                import traceback
                logger.error(traceback.format_exc())

            candidates = []
            from app.services.extraction.base import ConceptCandidate
            for cons_class in candidate_classes:
                candidates.append(ConceptCandidate(
                    label=cons_class.label,
                    description=cons_class.definition,
                    primary_type='constraints',
                    category='constraints_class',
                    confidence=cons_class.confidence,
                    debug={
                        'is_class': True,
                        'constraint_type': getattr(cons_class, 'constraint_type', ''),
                        'flexibility': getattr(cons_class, 'flexibility', ''),
                        'violation_impact': getattr(cons_class, 'violation_impact', ''),
                        'extraction_method': 'unified_extraction'
                    }
                ))

            for individual in constraint_individuals:
                candidates.append(ConceptCandidate(
                    label=individual.identifier,
                    description=getattr(individual, 'constraint_statement', '') or '',
                    primary_type='constraints',
                    category='constraints_individual',
                    confidence=individual.confidence,
                    debug={
                        'is_individual': True,
                        'constraint_class': individual.constraint_class,
                        'constrained_entity': getattr(individual, 'constrained_entity', ''),
                        'severity': getattr(individual, 'severity', ''),
                        'extraction_method': 'unified_extraction'
                    }
                ))

        elif concept_type == 'capabilities':
            from app.services.extraction.unified_dual_extractor import UnifiedDualExtractor
            from models import ModelConfig

            extractor = UnifiedDualExtractor('capabilities')
            candidate_classes, capability_individuals = extractor.extract(
                case_text=section_text,
                case_id=case_id,
                section_type=section_type
            )
            extraction_prompt = extractor.last_prompt
            raw_llm_response = extractor.last_raw_response

            from app.models import ExtractionPrompt
            try:
                ExtractionPrompt.save_prompt(
                    case_id=case_id,
                    concept_type='capabilities',
                    prompt_text=extraction_prompt,
                    raw_response=raw_llm_response,
                    step_number=2,
                    llm_model=extractor.model_name,
                    extraction_session_id=session_id,
                    section_type=section_type
                )
            except Exception as e:
                logger.warning(f"Could not save extraction prompt: {e}")

            try:
                from app.services.extraction.extraction_graph import pydantic_to_rdf_data
                from app.models import TemporaryRDFStorage

                rdf_data = pydantic_to_rdf_data(
                    classes=candidate_classes,
                    individuals=capability_individuals,
                    concept_type='capabilities',
                    case_id=case_id,
                    section_type=section_type,
                    pass_number=2,
                )
                stored_entities = TemporaryRDFStorage.store_extraction_results(
                    case_id=case_id,
                    extraction_session_id=session_id,
                    extraction_type='capabilities',
                    rdf_data=rdf_data,
                    extraction_model=extractor.model_name,
                    provenance_data={
                        'section_type': section_type,
                        'extracted_at': datetime.utcnow().isoformat(),
                        'model_used': extractor.model_name,
                        'extraction_pass': 'normative_requirements',
                        'concept_type': 'capabilities'
                    }
                )
                logger.info(f"Stored {len(stored_entities)} capability entities for case {case_id}")
                db.session.commit()
            except Exception as e:
                logger.error(f"Failed to store capabilities entities: {e}")
                import traceback
                logger.error(traceback.format_exc())

            candidates = []
            from app.services.extraction.base import ConceptCandidate
            for cap_class in candidate_classes:
                candidates.append(ConceptCandidate(
                    label=cap_class.label,
                    description=cap_class.definition,
                    primary_type='capabilities',
                    category='capabilities_class',
                    confidence=cap_class.confidence,
                    debug={
                        'is_class': True,
                        'capability_category': getattr(cap_class, 'capability_category', ''),
                        'skill_level': getattr(cap_class, 'skill_level', ''),
                        'enables_actions': getattr(cap_class, 'enables_actions', []),
                        'extraction_method': 'unified_extraction'
                    }
                ))

            for individual in capability_individuals:
                candidates.append(ConceptCandidate(
                    label=individual.identifier,
                    description=getattr(individual, 'capability_statement', '') or '',
                    primary_type='capabilities',
                    category='capabilities_individual',
                    confidence=individual.confidence,
                    debug={
                        'is_individual': True,
                        'capability_class': individual.capability_class,
                        'possessed_by': getattr(individual, 'possessed_by', ''),
                        'proficiency_level': getattr(individual, 'proficiency_level', ''),
                        'extraction_method': 'unified_extraction'
                    }
                ))

        # Record extraction results in provenance
        if candidates and activity:
            prov.record_extraction_results(
                results=[{
                    'label': c.label,
                    'description': c.description,
                    'confidence': c.confidence,
                    'debug': c.debug
                } for c in candidates],
                activity=activity,
                entity_type=f'extracted_{concept_type}',
                metadata={'count': len(candidates)}
            )

        # Commit provenance records
        db.session.commit()

        # Convert candidates to response format
        results = []
        for candidate in candidates:
            result_data = {
                "label": candidate.label,
                "description": candidate.description or "",
                "type": concept_type.rstrip('s'),  # Remove plural 's'
                "confidence": candidate.confidence
            }

            # Add concept-specific metadata
            if concept_type == 'principles':
                result_data.update({
                    "principle_category": candidate.debug.get('principle_category', 'professional'),
                    "abstraction_level": candidate.debug.get('abstraction_level', 'high'),
                    "requires_interpretation": candidate.debug.get('requires_interpretation', True),
                    "potential_conflicts": candidate.debug.get('potential_conflicts', []),
                    "extensional_examples": candidate.debug.get('extensional_examples', []),
                    "derived_obligations": candidate.debug.get('derived_obligations', []),
                    "scholarly_grounding": candidate.debug.get('scholarly_grounding', '')
                })
            elif concept_type == 'obligations':
                result_data.update({
                    "obligation_type": candidate.debug.get('obligation_type', 'professional_practice'),
                    "enforcement_level": candidate.debug.get('enforcement_level', 'mandatory'),
                    "derived_from_principle": candidate.debug.get('derived_from_principle', ''),
                    "stakeholders_affected": candidate.debug.get('stakeholders_affected', []),
                    "potential_conflicts": candidate.debug.get('potential_conflicts', []),
                    "monitoring_criteria": candidate.debug.get('monitoring_criteria', ''),
                    "nspe_reference": candidate.debug.get('nspe_reference', ''),
                    "contextual_factors": candidate.debug.get('contextual_factors', '')
                })
            elif concept_type == 'constraints':
                result_data.update({
                    "constraint_category": candidate.debug.get('constraint_category', 'resource'),
                    "flexibility": candidate.debug.get('flexibility', 'non-negotiable'),
                    "impact_on_decisions": candidate.debug.get('impact_on_decisions', ''),
                    "affected_stakeholders": candidate.debug.get('affected_stakeholders', []),
                    "potential_violations": candidate.debug.get('potential_violations', ''),
                    "mitigation_strategies": candidate.debug.get('mitigation_strategies', []),
                    "temporal_aspect": candidate.debug.get('temporal_aspect', 'permanent'),
                    "quantifiable_metrics": candidate.debug.get('quantifiable_metrics', '')
                })
            elif concept_type == 'capabilities':
                result_data.update({
                    "capability_category": candidate.debug.get('capability_category', 'TechnicalCapability'),
                    "ethical_relevance": candidate.debug.get('ethical_relevance', ''),
                    "required_for_roles": candidate.debug.get('required_for_roles', []),
                    "enables_obligations": candidate.debug.get('enables_obligations', []),
                    "theoretical_grounding": candidate.debug.get('theoretical_grounding', ''),
                    "development_path": candidate.debug.get('development_path', '')
                })

            results.append(result_data)

        return jsonify({
            'success': True,
            'concept_type': concept_type,
            'results': results,
            'count': len(results),
            'prompt': extraction_prompt,
            'raw_llm_response': raw_llm_response,
            'session_id': session_id,
            'extraction_metadata': {
                'timestamp': datetime.now().isoformat(),
                'extraction_method': 'unified_dual_extractor',
                'provenance_tracked': True,
                'model_used': extractor.model_name
            }
        })

    except Exception as e:
        logger.error(f"Error extracting individual {concept_type} for case {case_id}: {str(e)}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500

def step2_data(case_id, section_type='facts'):
    """
    Helper function to get Step 2 data without rendering template.
    Used by both regular step2 and step2_streaming views.

    Args:
        case_id: The case ID
        section_type: Which section to load ('facts', 'discussion', 'questions', 'conclusions', 'references')
    """
    # Get the case
    case = Document.query.get_or_404(case_id)

    # Extract sections using the same logic as step1
    raw_sections = {}
    if case.doc_metadata:
        # Priority 1: sections_dual (contains formatted HTML with enumerated lists)
        if 'sections_dual' in case.doc_metadata:
            raw_sections = case.doc_metadata['sections_dual']
        # Priority 2: sections (basic sections)
        elif 'sections' in case.doc_metadata:
            raw_sections = case.doc_metadata['sections']
        # Priority 3: document_structure sections
        elif 'document_structure' in case.doc_metadata and 'sections' in case.doc_metadata['document_structure']:
            raw_sections = case.doc_metadata['document_structure']['sections']

    # If no sections found, create basic structure
    if not raw_sections:
        raw_sections = {
            'full_content': case.content or 'No content available'
        }

    # Find the facts section (same as step1)
    facts_section = None
    facts_section_key = None

    # Look for facts section (case insensitive)
    for section_key, section_content in raw_sections.items():
        if 'fact' in section_key.lower():
            facts_section_key = section_key
            facts_section = _format_section_for_llm(section_key, section_content, case_doc=case)
            break

    # If no facts section found, use first available section
    if not facts_section and raw_sections:
        first_key = list(raw_sections.keys())[0]
        facts_section_key = first_key
        facts_section = _format_section_for_llm(first_key, raw_sections[first_key], case_doc=case)

    # Load saved prompts for all concept types (filtered by section_type)
    from app.models import ExtractionPrompt
    saved_prompts = {}
    for concept_type in ['principles', 'obligations', 'constraints', 'capabilities']:
        # Get active prompt and check if it's for step 2 AND this section_type
        prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type=concept_type,
            step_number=2,
            section_type=section_type,
            is_active=True
        ).order_by(ExtractionPrompt.created_at.desc()).first()
        saved_prompts[concept_type] = prompt

    return case, facts_section, saved_prompts

def step2(case_id):
    """
    Step 2: Normative Pass for Facts Section
    Shows the facts section with a normative pass button for extracting principles, obligations, and constraints.
    """
    try:
        # Get data
        case, facts_section, saved_prompts = step2_data(case_id)

        # Find the facts section key for template
        facts_section_key = None
        raw_sections = {}
        if case.doc_metadata:
            if 'sections_dual' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections_dual']
            elif 'sections' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections']
            elif 'document_structure' in case.doc_metadata and 'sections' in case.doc_metadata['document_structure']:
                raw_sections = case.doc_metadata['document_structure']['sections']

        for section_key, section_content in raw_sections.items():
            if 'fact' in section_key.lower():
                facts_section_key = section_key
                break

        if not facts_section_key and raw_sections:
            facts_section_key = list(raw_sections.keys())[0]

        # Template context
        # Load saved prompts for all concept types (facts section)
        from app.models import ExtractionPrompt
        saved_prompts = {}
        for concept_type in ['principles', 'obligations', 'constraints', 'capabilities']:
            saved_prompt = ExtractionPrompt.query.filter_by(
                case_id=case_id,
                concept_type=concept_type,
                step_number=2,
                section_type='facts',
                is_active=True
            ).order_by(ExtractionPrompt.created_at.desc()).first()
            if saved_prompt:
                saved_prompts[concept_type] = saved_prompt

        # Get pipeline status for navigation
        pipeline_status = PipelineStatusService.get_step_status(case_id)

        context = {
            'case': case,
            'discussion_section': facts_section,  # Keep variable name for template compatibility
            'discussion_section_key': facts_section_key,
            'section_display_name': 'Facts Section',
            'current_step': 2,
            'step_title': 'Normative Pass - Facts Section',
            'next_step_url': url_for('scenario_pipeline.step2b', case_id=case_id),
            'next_step_name': 'Discussion Section',
            'prev_step_url': url_for('scenario_pipeline.step1b', case_id=case_id),
            'saved_prompts': saved_prompts,
            'pipeline_status': pipeline_status
        }

        return render_template('scenarios/step2_multi_section.html', **context)
        
    except Exception as e:
        logger.error(f"Error loading step 2 for case {case_id}: {str(e)}")
        flash(f'Error loading step 2: {str(e)}', 'danger')
        return redirect(url_for('cases.view_case', id=case_id))

def get_saved_prompt(case_id):
    """Get saved extraction prompt for a concept type in Step 2"""
    from app.models import ExtractionPrompt

    concept_type = request.args.get('concept_type')
    section_type = request.args.get('section_type', 'facts')  # Default to facts if not provided

    if not concept_type:
        return jsonify({'error': 'concept_type is required'}), 400

    saved_prompt = ExtractionPrompt.query.filter_by(
        case_id=case_id,
        concept_type=concept_type,
        step_number=2,
        section_type=section_type,
        is_active=True
    ).first()

    if saved_prompt:
        return jsonify({
            'success': True,
            'prompt_text': saved_prompt.prompt_text,
            'raw_response': saved_prompt.raw_response,
            'created_at': saved_prompt.created_at.isoformat() if saved_prompt.created_at else None,
            'section_type': saved_prompt.section_type
        })
    else:
        return jsonify({'success': False, 'message': f'No saved prompt found for {concept_type} in {section_type} section'})

def clear_saved_prompt(case_id):
    """Clear saved extraction prompt for a concept type in Step 2"""
    from app.models import ExtractionPrompt, db

    data = request.get_json()
    concept_type = data.get('concept_type')

    if not concept_type:
        return jsonify({'error': 'concept_type is required'}), 400

    try:
        # Delete existing prompts for this case/concept/step
        ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type=concept_type,
            step_number=2
        ).delete()

        db.session.commit()
        return jsonify({'success': True, 'message': f'Cleared prompt for {concept_type}'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to clear prompt: {str(e)}'}), 500

def normative_pass_prompt(case_id):
    """
    API endpoint to generate and return the LLM prompt for normative pass before execution.
    This will extract principles, obligations, and constraints.
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        section_text = data.get('section_text')
        if not section_text:
            return jsonify({'error': 'section_text is required'}), 400
        
        logger.info(f"Generating normative pass prompt for case {case_id}")
        
        # Use enhanced principles prompt from Chapter 2 literature with MCP context
        # MCP will be fetched dynamically from the external server
        principles_prompt = create_enhanced_principles_prompt(section_text, include_mcp_context=True)

        # Use enhanced obligations prompt with MCP context - include principles for full normative pass
        obligations_prompt = create_enhanced_obligations_prompt(section_text, include_mcp_context=True, include_principles=True)

        # Use enhanced constraints prompt with MCP context - include related entities for full normative pass
        constraints_prompt = create_enhanced_constraints_prompt(section_text, include_mcp_context=True, include_related_entities=True)
        
        # Use enhanced capabilities prompt with MCP context - retrieves capability types via recursive CTE
        capabilities_prompt = create_enhanced_capabilities_prompt(section_text, include_mcp_context=True)
        
        return jsonify({
            'success': True,
            'principles_prompt': principles_prompt,
            'obligations_prompt': obligations_prompt,
            'constraints_prompt': constraints_prompt,
            'capabilities_prompt': capabilities_prompt,
            'section_length': len(section_text)
        })
        
    except Exception as e:
        logger.error(f"Error generating normative pass prompt for case {case_id}: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500

def normative_pass_execute(case_id):
    """
    API endpoint to execute the normative pass extraction.
    This will run the actual LLM extraction for principles, obligations, and constraints.
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405
        
        # Get the case
        case = Document.query.get_or_404(case_id)
        
        # Get the facts section text (same logic as step2 view)
        section_text = None
        raw_sections = {}
        
        if case.doc_metadata:
            # Get sections from metadata
            if 'sections_dual' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections_dual']
            elif 'sections' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections']
            elif 'document_structure' in case.doc_metadata and 'sections' in case.doc_metadata['document_structure']:
                raw_sections = case.doc_metadata['document_structure']['sections']
        
        # Look for facts section
        for section_key, section_content in raw_sections.items():
            if 'fact' in section_key.lower():
                section_text = _format_section_for_llm(section_key, section_content, case)
                break
        
        # If no facts section found, use first available section
        if not section_text and raw_sections:
            first_key = list(raw_sections.keys())[0]
            section_text = _format_section_for_llm(first_key, raw_sections[first_key], case)
        
        if not section_text:
            # Fallback to using available content
            section_text = case.content or case.description or ""
            if not section_text:
                return jsonify({'error': 'No facts section found'}), 400
        
        logger.info(f"Executing normative pass for case {case_id}")

        from app.services.extraction.unified_dual_extractor import UnifiedDualExtractor
        from app.services.extraction.extraction_graph import pydantic_to_rdf_data
        from app.models import ExtractionPrompt, TemporaryRDFStorage

        # Initialize provenance service with versioning if available
        if USE_VERSIONED_PROVENANCE:
            prov = get_versioned_provenance_service()
            logger.info("Using versioned provenance service for Step 2")
        else:
            from app.services.provenance_service import get_provenance_service
            prov = get_provenance_service()
            logger.info("Using standard provenance service")

        # Create session ID for this normative pass
        session_id = str(uuid.uuid4())
        section_type = 'facts'

        # Track versioned workflow if available
        version_context = nullcontext()
        if USE_VERSIONED_PROVENANCE:
            version_context = prov.track_versioned_workflow(
                workflow_name='step2_normative_pass',
                description='Pass 2: Normative extraction of Principles, Obligations, Constraints, Capabilities',
                version_tag='unified_normative',
                auto_version=True
            )

        # Extraction results collected across all concepts
        all_classes = {}  # concept_type -> list of Pydantic class objects
        all_individuals = {}  # concept_type -> list of Pydantic individual objects
        model_used = None

        # Dependency order: principles -> obligations -> constraints -> capabilities
        # Each concept is stored in TemporaryRDFStorage before the next runs,
        # so cross-concept context is available via CROSS_CONCEPT_DEPS.
        concept_order = ['principles', 'obligations', 'constraints', 'capabilities']

        with version_context:
            with prov.track_activity(
                activity_type='extraction',
                activity_name='normative_pass_step2',
                case_id=case_id,
                session_id=session_id,
                agent_type='extraction_service',
                agent_name='proethica_normative_pass',
                execution_plan={
                    'pass_number': 2,
                    'concepts': concept_order,
                    'strategy': 'unified_dual_extractor',
                    'version': 'unified_normative' if USE_VERSIONED_PROVENANCE else 'standard'
                }
            ) as main_activity:

                prev_activity = main_activity

                for concept_type in concept_order:
                    with prov.track_activity(
                        activity_type='llm_query',
                        activity_name=f'{concept_type}_extraction',
                        case_id=case_id,
                        session_id=session_id,
                        agent_type='extraction_service',
                        agent_name='UnifiedDualExtractor'
                    ) as concept_activity:
                        logger.info(f"Extracting {concept_type} with UnifiedDualExtractor...")

                        extractor = UnifiedDualExtractor(concept_type)
                        classes, individuals = extractor.extract(
                            case_text=section_text,
                            case_id=case_id,
                            section_type=section_type
                        )

                        if model_used is None:
                            model_used = extractor.model_name

                        all_classes[concept_type] = classes
                        all_individuals[concept_type] = individuals

                        # Save prompt and response
                        try:
                            ExtractionPrompt.save_prompt(
                                case_id=case_id,
                                concept_type=concept_type,
                                prompt_text=extractor.last_prompt,
                                raw_response=extractor.last_raw_response,
                                step_number=2,
                                llm_model=extractor.model_name,
                                extraction_session_id=session_id,
                                section_type=section_type
                            )
                        except Exception as e:
                            logger.warning(f"Could not save {concept_type} extraction prompt: {e}")

                        # Store in TemporaryRDFStorage (enables cross-concept context for next concept)
                        try:
                            rdf_data = pydantic_to_rdf_data(
                                classes=classes,
                                individuals=individuals,
                                concept_type=concept_type,
                                case_id=case_id,
                                section_type=section_type,
                                pass_number=2,
                            )
                            stored_entities = TemporaryRDFStorage.store_extraction_results(
                                case_id=case_id,
                                extraction_session_id=session_id,
                                extraction_type=concept_type,
                                rdf_data=rdf_data,
                                extraction_model=extractor.model_name,
                                provenance_data={
                                    'section_type': section_type,
                                    'extracted_at': datetime.utcnow().isoformat(),
                                    'model_used': extractor.model_name,
                                    'extraction_pass': 'normative_requirements',
                                    'concept_type': concept_type
                                }
                            )
                            logger.info(f"Stored {len(stored_entities)} {concept_type} entities for case {case_id}")
                            db.session.commit()
                        except Exception as e:
                            logger.error(f"Failed to store {concept_type} entities: {e}")
                            import traceback
                            logger.error(traceback.format_exc())

                        # Record provenance
                        prov.record_extraction_results(
                            results=[{
                                'label': c.label,
                                'definition': c.definition,
                                'confidence': c.confidence,
                            } for c in classes],
                            activity=concept_activity,
                            entity_type=f'extracted_{concept_type}',
                            metadata={
                                'classes_count': len(classes),
                                'individuals_count': len(individuals),
                            }
                        )

                        prov.link_activities(concept_activity, prev_activity, 'sequence')
                        prev_activity = concept_activity

        # Commit provenance records
        db.session.commit()

        # Convert Pydantic results to response format
        def _serialize_enum(val):
            return val.value if hasattr(val, 'value') else val

        principles = []
        for cls in all_classes.get('principles', []):
            principles.append({
                "label": cls.label,
                "definition": cls.definition,
                "type": "principle",
                "principle_category": _serialize_enum(getattr(cls, 'principle_category', '')),
                "abstract_nature": getattr(cls, 'abstract_nature', ''),
                "value_basis": getattr(cls, 'value_basis', ''),
                "extensional_examples": getattr(cls, 'extensional_examples', []),
                "potential_conflicts": getattr(cls, 'potential_conflicts', []),
                "derived_obligations": getattr(cls, 'derived_obligations', []),
                "confidence": cls.confidence
            })
        for ind in all_individuals.get('principles', []):
            principles.append({
                "label": ind.identifier,
                "definition": getattr(ind, 'concrete_expression', '') or '',
                "type": "principle_instance",
                "principle_class": ind.principle_class,
                "confidence": ind.confidence
            })

        obligations = []
        for cls in all_classes.get('obligations', []):
            obligations.append({
                "label": cls.label,
                "definition": cls.definition,
                "type": "obligation",
                "obligation_type": _serialize_enum(getattr(cls, 'obligation_type', '')),
                "enforcement_level": _serialize_enum(getattr(cls, 'enforcement_level', '')),
                "derived_from_principle": getattr(cls, 'derived_from_principle', ''),
                "stakeholders_affected": getattr(cls, 'stakeholders_affected', []),
                "monitoring_criteria": getattr(cls, 'monitoring_criteria', ''),
                "nspe_reference": getattr(cls, 'nspe_reference', ''),
                "violation_consequences": getattr(cls, 'violation_consequences', ''),
                "confidence": cls.confidence
            })
        for ind in all_individuals.get('obligations', []):
            obligations.append({
                "label": ind.identifier,
                "definition": getattr(ind, 'obligation_statement', '') or '',
                "type": "obligation_instance",
                "obligation_class": ind.obligation_class,
                "obligated_party": getattr(ind, 'obligated_party', ''),
                "compliance_status": _serialize_enum(getattr(ind, 'compliance_status', '')),
                "confidence": ind.confidence
            })

        constraints = []
        for cls in all_classes.get('constraints', []):
            constraints.append({
                "label": cls.label,
                "definition": cls.definition,
                "type": "constraint",
                "constraint_type": _serialize_enum(getattr(cls, 'constraint_type', '')),
                "flexibility": _serialize_enum(getattr(cls, 'flexibility', '')),
                "violation_impact": getattr(cls, 'violation_impact', ''),
                "mitigation_strategies": getattr(cls, 'mitigation_strategies', []),
                "confidence": cls.confidence
            })
        for ind in all_individuals.get('constraints', []):
            constraints.append({
                "label": ind.identifier,
                "definition": getattr(ind, 'constraint_statement', '') or '',
                "type": "constraint_instance",
                "constraint_class": ind.constraint_class,
                "constrained_entity": getattr(ind, 'constrained_entity', ''),
                "severity": _serialize_enum(getattr(ind, 'severity', '')),
                "confidence": ind.confidence
            })

        capabilities = []
        for cls in all_classes.get('capabilities', []):
            capabilities.append({
                "label": cls.label,
                "definition": cls.definition,
                "type": "capability",
                "capability_category": _serialize_enum(getattr(cls, 'capability_category', '')),
                "skill_level": _serialize_enum(getattr(cls, 'skill_level', '')),
                "enables_actions": getattr(cls, 'enables_actions', []),
                "required_for_obligations": getattr(cls, 'required_for_obligations', []),
                "confidence": cls.confidence
            })
        for ind in all_individuals.get('capabilities', []):
            capabilities.append({
                "label": ind.identifier,
                "definition": getattr(ind, 'capability_statement', '') or '',
                "type": "capability_instance",
                "capability_class": ind.capability_class,
                "possessed_by": getattr(ind, 'possessed_by', ''),
                "proficiency_level": _serialize_enum(getattr(ind, 'proficiency_level', '')),
                "confidence": ind.confidence
            })

        # Summary statistics
        total_classes = sum(len(all_classes.get(c, [])) for c in concept_order)
        total_individuals = sum(len(all_individuals.get(c, [])) for c in concept_order)
        summary = {
            'principles_count': len(principles),
            'obligations_count': len(obligations),
            'constraints_count': len(constraints),
            'capabilities_count': len(capabilities),
            'total_classes': total_classes,
            'total_individuals': total_individuals,
            'total_entities': total_classes + total_individuals,
            'session_id': session_id,
            'version': 'unified_normative' if USE_VERSIONED_PROVENANCE else 'standard'
        }

        if USE_VERSIONED_PROVENANCE:
            summary['provenance_url'] = url_for('provenance.provenance_viewer')

        extraction_metadata = {
            'timestamp': datetime.now().isoformat(),
            'extraction_method': 'unified_dual_extractor',
            'extractor': 'UnifiedDualExtractor',
            'model_used': model_used or 'unknown',
            'provenance_tracked': True,
        }

        return jsonify({
            'success': True,
            'principles': principles,
            'obligations': obligations,
            'constraints': constraints,
            'capabilities': capabilities,
            'summary': summary,
            'extraction_metadata': extraction_metadata
        })
        
    except Exception as e:
        logger.error(f"Error executing normative pass for case {case_id}: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500

def step2b(case_id):
    """
    Step 2b: Normative Pass for Discussion Section
    Extracts principles, obligations, constraints, and capabilities from Discussion section

    Requires: Step 2 Facts extraction must be completed first
    """
    # Get pipeline status first to check prerequisites
    pipeline_status = PipelineStatusService.get_step_status(case_id)

    # Enforce prerequisite: Step 2 Facts must be completed
    if not pipeline_status.get('step2', {}).get('facts_complete', False):
        flash('Please complete Step 2 (Facts extraction) before proceeding to Discussion.', 'warning')
        return redirect(url_for('scenario_pipeline.step2', case_id=case_id))

    # Load data with section_type='discussion' to get discussion prompts
    case, facts_section, saved_prompts = step2_data(case_id, section_type='discussion')

    # Get the discussion section
    discussion_section = None
    discussion_section_key = None
    raw_sections = {}

    if case.doc_metadata:
        if 'sections_dual' in case.doc_metadata:
            raw_sections = case.doc_metadata['sections_dual']
        elif 'sections' in case.doc_metadata:
            raw_sections = case.doc_metadata['sections']

    for section_key, section_content in raw_sections.items():
        if 'discussion' in section_key.lower():
            discussion_section_key = section_key
            discussion_section = _format_section_for_llm(section_key, section_content, case_doc=case)
            break

    context = {
        'case': case,
        'discussion_section': discussion_section,
        'discussion_section_key': discussion_section_key,
        'section_display_name': 'Discussion Section',
        'current_step': 2,
        'step_title': 'Normative Pass - Discussion',
        'next_step_url': url_for('scenario_pipeline.step3', case_id=case_id),
        'next_step_name': 'Temporal Dynamics',
        'prev_step_url': url_for('scenario_pipeline.step2', case_id=case_id),
        'saved_prompts': saved_prompts,
        'pipeline_status': pipeline_status
    }

    return render_template('scenarios/step2_multi_section.html', **context)

def step2c(case_id):
    """
    Step 2c: Normative Pass for Questions Section
    Extracts principles, obligations, constraints, and capabilities from Questions section
    """
    # Load data with section_type='questions' to get questions prompts
    case, facts_section, saved_prompts = step2_data(case_id, section_type='questions')

    # Get the questions section
    questions_section = None
    questions_section_key = None
    raw_sections = {}

    if case.doc_metadata:
        if 'sections_dual' in case.doc_metadata:
            raw_sections = case.doc_metadata['sections_dual']
        elif 'sections' in case.doc_metadata:
            raw_sections = case.doc_metadata['sections']

    for section_key, section_content in raw_sections.items():
        if 'question' in section_key.lower():
            questions_section_key = section_key
            questions_section = _format_section_for_llm(section_key, section_content, case_doc=case)
            break

    # Template context
    # Get pipeline status for navigation
    pipeline_status = PipelineStatusService.get_step_status(case_id)

    context = {
        'case': case,
        'discussion_section': questions_section,  # Keep variable name for template compatibility
        'discussion_section_key': questions_section_key,
        'section_display_name': 'Questions Section',
        'current_step': 2,
        'step_title': 'Normative Pass - Questions',
        'next_step_url': url_for('scenario_pipeline.step2d', case_id=case_id),
        'prev_step_url': url_for('scenario_pipeline.step2b', case_id=case_id),
        'saved_prompts': saved_prompts,
        'pipeline_status': pipeline_status
    }

    return render_template('scenarios/step2_multi_section.html', **context)

def step2d(case_id):
    """
    Step 2d: Normative Pass for Conclusions Section
    Extracts principles, obligations, constraints, and capabilities from Conclusions section
    """
    # Load data with section_type='conclusions' to get conclusions prompts
    case, facts_section, saved_prompts = step2_data(case_id, section_type='conclusions')

    # Get the conclusions section
    conclusions_section = None
    conclusions_section_key = None
    raw_sections = {}

    if case.doc_metadata:
        if 'sections_dual' in case.doc_metadata:
            raw_sections = case.doc_metadata['sections_dual']
        elif 'sections' in case.doc_metadata:
            raw_sections = case.doc_metadata['sections']

    for section_key, section_content in raw_sections.items():
        if 'conclusion' in section_key.lower():
            conclusions_section_key = section_key
            conclusions_section = _format_section_for_llm(section_key, section_content, case_doc=case)
            break

    # Template context
    # Get pipeline status for navigation
    pipeline_status = PipelineStatusService.get_step_status(case_id)

    context = {
        'case': case,
        'discussion_section': conclusions_section,  # Keep variable name for template compatibility
        'discussion_section_key': conclusions_section_key,
        'section_display_name': 'Conclusions Section',
        'current_step': 2,
        'step_title': 'Normative Pass - Conclusions',
        'next_step_url': url_for('scenario_pipeline.step2e', case_id=case_id),
        'prev_step_url': url_for('scenario_pipeline.step2c', case_id=case_id),
        'saved_prompts': saved_prompts,
        'pipeline_status': pipeline_status
    }

    return render_template('scenarios/step2_multi_section.html', **context)

def step2e(case_id):
    """
    Step 2e: Normative Pass for References Section
    Extracts principles, obligations, constraints, and capabilities from References section
    Note: References section may reference NSPE Code provisions
    """
    # Load data with section_type='references' to get references prompts
    case, facts_section, saved_prompts = step2_data(case_id, section_type='references')

    # Get the references section
    references_section = None
    references_section_key = None
    raw_sections = {}

    if case.doc_metadata:
        if 'sections_dual' in case.doc_metadata:
            raw_sections = case.doc_metadata['sections_dual']
        elif 'sections' in case.doc_metadata:
            raw_sections = case.doc_metadata['sections']

    for section_key, section_content in raw_sections.items():
        if 'reference' in section_key.lower():
            references_section_key = section_key
            references_section = _format_section_for_llm(section_key, section_content, case_doc=case)
            break

    # Get pipeline status for navigation
    pipeline_status = PipelineStatusService.get_step_status(case_id)

    # Template context
    context = {
        'case': case,
        'discussion_section': references_section,  # Keep variable name for template compatibility
        'discussion_section_key': references_section_key,
        'section_display_name': 'References Section',
        'current_step': 2,
        'step_title': 'Normative Pass - References',
        'next_step_url': url_for('scenario_pipeline.step3', case_id=case_id),  # Last section goes to step3
        'prev_step_url': url_for('scenario_pipeline.step2d', case_id=case_id),
        'saved_prompts': saved_prompts,
        'pipeline_status': pipeline_status
    }

    return render_template('scenarios/step2_multi_section.html', **context)
